#!/usr/bin/env python3
"""Bounded deterministic resource observations, with no accepted SLO or scientific claim."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

StorageKind = Literal["disk", "tmpfs"]
_RAM_FILESYSTEMS = frozenset({"tmpfs", "ramfs", "mfs", "memfs"})


@dataclass(frozen=True)
class FilesystemObservation:
    filesystem: str
    storage: StorageKind
    method: str
    mount_point: str
    backing_kind: str
    limitations: tuple[str, ...]

    def record(self) -> dict[str, object]:
        return {
            "filesystem": self.filesystem,
            "storage": self.storage,
            "method": self.method,
            "mount_point": self.mount_point,
            "backing_kind": self.backing_kind,
            "limitations": list(self.limitations),
        }


def _storage_for_filesystem(filesystem: str) -> StorageKind:
    normalized = filesystem.strip().casefold()
    if not normalized:
        raise RuntimeError("Observed filesystem type is empty")
    return "tmpfs" if normalized in _RAM_FILESYSTEMS else "disk"


def _observe_linux_filesystem(
    directory: Path, *, mountinfo: Path = Path("/proc/self/mountinfo")
) -> FilesystemObservation:
    """Observe the containing filesystem in the current Linux mount namespace."""
    selected = None
    try:
        rows = mountinfo.read_text("utf-8").splitlines()
    except OSError as error:
        raise RuntimeError(
            "Cannot observe filesystem type for the measurement"
        ) from error
    for row in rows:
        before, separator, after = row.partition(" - ")
        if not separator:
            continue
        fields = before.split()
        after_fields = after.split()
        if len(fields) < 5 or not after_fields:
            continue
        decoded = re.sub(
            r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), fields[4]
        )
        mount = Path(decoded)
        if directory.resolve().is_relative_to(mount) and (
            selected is None or len(mount.parts) > selected[0]
        ):
            selected = (len(mount.parts), after_fields[0], mount)
    if selected is None:
        raise RuntimeError(
            "Measurement filesystem was not found in this mount namespace"
        )
    filesystem = selected[1]
    return FilesystemObservation(
        filesystem=filesystem,
        storage=_storage_for_filesystem(filesystem),
        method="linux_proc_self_mountinfo",
        mount_point=str(selected[2]),
        backing_kind="current_mount_namespace",
        limitations=(
            (
                "The filesystem type comes from the current mount namespace; disk means the type "
                "is not an explicit RAM filesystem and does not establish physical media, "
                "locality, cache state, or durability."
            ),
        ),
    )


def _windows_volume_details(directory: Path) -> tuple[str, int, str]:
    """Return filesystem, Win32 drive type and containing volume path."""
    import ctypes
    from ctypes import wintypes

    loader = getattr(ctypes, "WinDLL", None)
    if loader is None:
        raise RuntimeError("Win32 volume APIs are unavailable")
    kernel32 = loader("kernel32", use_last_error=True)
    get_volume_path = kernel32.GetVolumePathNameW
    get_volume_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_volume_path.restype = wintypes.BOOL
    get_volume_information = kernel32.GetVolumeInformationW
    get_volume_information.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.LPDWORD,
        wintypes.LPDWORD,
        wintypes.LPDWORD,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    get_volume_information.restype = wintypes.BOOL
    get_drive_type = kernel32.GetDriveTypeW
    get_drive_type.argtypes = [wintypes.LPCWSTR]
    get_drive_type.restype = wintypes.UINT

    volume_path = ctypes.create_unicode_buffer(32768)
    if not get_volume_path(str(directory.resolve()), volume_path, len(volume_path)):
        code = ctypes.get_last_error()
        raise OSError(code, "GetVolumePathNameW failed: " + ctypes.FormatError(code))
    volume_name = ctypes.create_unicode_buffer(261)
    filesystem_name = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    maximum_component = wintypes.DWORD()
    flags = wintypes.DWORD()
    if not get_volume_information(
        volume_path.value,
        volume_name,
        len(volume_name),
        ctypes.byref(serial),
        ctypes.byref(maximum_component),
        ctypes.byref(flags),
        filesystem_name,
        len(filesystem_name),
    ):
        code = ctypes.get_last_error()
        raise OSError(code, "GetVolumeInformationW failed: " + ctypes.FormatError(code))
    return (
        filesystem_name.value,
        int(get_drive_type(volume_path.value)),
        volume_path.value,
    )


def _windows_observation_from_details(
    filesystem: str, drive_type: int, mount_point: str
) -> FilesystemObservation:
    filesystem = filesystem.strip()
    if not filesystem:
        raise RuntimeError("Observed Windows filesystem type is empty")
    if not mount_point:
        raise RuntimeError("Observed Windows volume path is empty")
    drive_types = {2: "removable", 3: "fixed", 4: "remote", 6: "ramdisk"}
    backing = drive_types.get(drive_type)
    if backing is None:
        raise RuntimeError(
            "Containing Windows drive type cannot support an observed measurement"
        )
    storage: StorageKind = "tmpfs" if drive_type == 6 else "disk"
    limitations = [
        (
            "The filesystem and drive type come from Win32 for the containing volume; disk does "
            "not establish physical media, virtualization, cache state, or durability."
        )
    ]
    if drive_type == 4:
        limitations.append("Win32 reports the containing volume as a remote drive.")
    if drive_type == 2:
        limitations.append("Win32 reports the containing volume as removable media.")
    return FilesystemObservation(
        filesystem=filesystem,
        storage=storage,
        method="windows_get_volume_information_and_drive_type",
        mount_point=mount_point,
        backing_kind=backing,
        limitations=tuple(limitations),
    )


def _observe_windows_filesystem(directory: Path) -> FilesystemObservation:
    try:
        return _windows_observation_from_details(*_windows_volume_details(directory))
    except OSError as error:
        raise RuntimeError(
            "Cannot observe Windows filesystem for the measurement"
        ) from error


def _observe_macos_filesystem(
    directory: Path, *, mount_output: str | None = None
) -> FilesystemObservation:
    """Observe the deepest containing entry from macOS's native mount table."""
    if mount_output is None:
        try:
            completed = subprocess.run(
                ["/sbin/mount"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="strict",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError(
                "Cannot observe macOS mount table for the measurement"
            ) from error
        if completed.returncode != 0:
            raise RuntimeError("Cannot observe macOS mount table for the measurement")
        mount_output = completed.stdout
    selected = None
    resolved = directory.resolve()
    for row in mount_output.splitlines():
        before_options, separator, options = row.rpartition(" (")
        device, on_separator, encoded_mount = before_options.partition(" on ")
        if not separator or not on_separator or not device or not options.endswith(")"):
            continue
        decoded = re.sub(
            r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), encoded_mount
        )
        mount = Path(decoded)
        filesystem = options[:-1].split(",", 1)[0].strip()
        if (
            resolved.is_relative_to(mount)
            and filesystem
            and (selected is None or len(mount.parts) > selected[0])
        ):
            selected = (len(mount.parts), filesystem, mount)
    if selected is None:
        raise RuntimeError(
            "Measurement filesystem was not found in the macOS mount table"
        )
    filesystem = selected[1]
    return FilesystemObservation(
        filesystem=filesystem,
        storage=_storage_for_filesystem(filesystem),
        method="macos_sbin_mount_table",
        mount_point=str(selected[2]),
        backing_kind="mount_table_filesystem_type",
        limitations=(
            (
                "The filesystem type comes from the native mount table; disk means the type is "
                "not an explicit RAM filesystem and does not establish physical media, "
                "virtualization, cache state, or durability."
            ),
        ),
    )


def observe_filesystem(
    directory: Path, *, system: str | None = None
) -> FilesystemObservation:
    """Observe storage without inferring a successful measurement from missing platform facts."""
    if not directory.is_dir():
        raise ValueError(
            "measurement directory must exist before observing its filesystem"
        )
    selected_system = platform.system() if system is None else system
    if selected_system == "Linux":
        return _observe_linux_filesystem(directory)
    if selected_system == "Windows":
        return _observe_windows_filesystem(directory)
    if selected_system == "Darwin":
        return _observe_macos_filesystem(directory)
    raise RuntimeError("Unsupported operating system for filesystem observation")


def observed_filesystem(directory: Path) -> str:
    """Compatibility helper for existing Linux mount-table unit tests."""
    return _observe_linux_filesystem(directory).filesystem


def validate_resource_contract(
    summary: dict[str, object], *, contract_id: str, measurement_platform: str
) -> None:
    """Reject a summary that is not bound to the contract selected before the run."""
    contract = summary.get("resource_measurement_contract")
    if not isinstance(contract, dict):
        raise TypeError("measurement summary omitted its resource contract")
    if (
        contract.get("id") != contract_id
        or contract.get("platform") != measurement_platform
    ):
        raise ValueError("measurement summary used a different resource contract")
    metrics = contract.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("measurement summary omitted metric-level resource coverage")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--storage", required=True, choices=("disk", "tmpfs"))
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("choose a new measurement directory")
    args.output.mkdir(parents=True)
    filesystem_observation = observe_filesystem(args.output)
    if filesystem_observation.storage != args.storage:
        raise ValueError("requested storage label differs from observed filesystem")
    import equiframe as ef
    import equiframe_benchmark as eb
    from equiframe_benchmark.scale_process import (
        MEASUREMENT_CONTRACT_ID,
        current_measurement_platform,
    )
    from equiframe_benchmark.scale_types import SCALE_SAMPLE_INTERVAL_SECONDS

    measurement_platform = current_measurement_platform()
    resource_contract = {
        "id": MEASUREMENT_CONTRACT_ID,
        "platform": measurement_platform,
    }

    protocol = {
        "rows": [100, 1000],
        "width": 2,
        "repetitions": 3,
        "rss_budget_bytes": 512 * 1024**2,
        "disk_budget_bytes": 64 * 1024**2,
        "timeout_seconds": 120,
        "supervisor_sample_interval_seconds": SCALE_SAMPLE_INTERVAL_SECONDS,
        "threads_per_engine": 1,
        "expected_state": "different",
        "storage": filesystem_observation.storage,
        "filesystem_observed": filesystem_observation.filesystem,
        "filesystem_observation": filesystem_observation.record(),
        "resource_measurement_contract": resource_contract,
        "concurrent_known_loads": "No other task-controlled suite; shared host not controlled",
        "os_cache": "uncontrolled",
        "slo_accepted": False,
        "scope": "local synthetic capture/compare/evidence; no network transport or VM claim",
        "python": platform.python_version(),
        "machine": platform.machine(),
        "executable": sys.executable,
    }
    (args.output / "protocol.json").write_text(
        json.dumps(protocol, indent=2) + "\n", encoding="utf-8"
    )
    results = []
    for rows in protocol["rows"]:
        spec = eb.ScaleSpec(
            case_id=f"maturity-{rows}",
            rows=rows,
            width=2,
            difference_last=True,
            repetitions=3,
            timeout_seconds=120,
            rss_budget_bytes=protocol["rss_budget_bytes"],
            disk_budget_bytes=protocol["disk_budget_bytes"],
            comparison_options=ef.ComparisonOptions(
                max_rows=2000, max_disk_bytes=32 * 1024**2, timeout_seconds=60
            ),
            concurrent_loads=protocol["concurrent_known_loads"],
        )
        result = eb.measure_scale(spec, work_dir=args.output / f"rows-{rows}")
        restored = eb.read_scale(args.output / f"rows-{rows}" / result.run_id)
        if restored != result:
            raise ValueError("measured evidence readback differs")
        summary = eb.summarize_scale(result)
        validate_resource_contract(
            summary,
            contract_id=MEASUREMENT_CONTRACT_ID,
            measurement_platform=measurement_platform,
        )
        results.append(summary)
        (args.output / "summary.json").write_text(
            json.dumps({"protocol": protocol, "results": results}, indent=2) + "\n",
            encoding="utf-8",
        )
        # Independent sizes continue even when one instrument is incomplete.
        # The final return code remains nonzero; no partial measurement becomes a pass.
    # A separate tiny case exercises cooperative admission, never an OOM or shared-host disruption.
    import pyarrow as pa

    table = pa.table({"id": [1, 2], "value": [10, 20]})
    limited = ef.diff(
        table,
        table,
        options=ef.ComparisonOptions(max_rows=1),
        work_dir=args.output / "bounded-limit",
    )
    if limited.state != "not_evaluable" or limited.complete:
        raise ValueError("resource limit was incorrectly converted into equivalence")
    (args.output / "bounded-limit.json").write_text(
        limited.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    complete = all(
        item["complete"] and item["resource_measurement_complete"] for item in results
    )
    status = "passed" if complete else "partial"
    print(
        json.dumps(
            {
                "status": status,
                "sizes": protocol["rows"],
                "repetitions_each": 3,
                "storage": filesystem_observation.storage,
                "filesystem_observed": filesystem_observation.filesystem,
                "filesystem_observation": filesystem_observation.record(),
                "resource_measurement_contract": resource_contract,
                "slo_accepted": False,
            }
        )
    )
    return 0 if complete else 3


if __name__ == "__main__":
    raise SystemExit(main())
