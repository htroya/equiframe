#!/usr/bin/env python3
"""Run the exact private candidate in an isolated owned ARM64 lab; never use SSH keys.

Run on the VM from the already-authorized Codex executor. Receipts are unsigned
observations, not operator authentication or independent human acceptance.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from frozen_tests import candidate_manifests

try:
    import resource
except ImportError:  # Windows imports shared receipt helpers for the offline lifecycle check.
    resource = None  # type: ignore[assignment]

from manifest_scope import receipt_schema, required_pythons

PROFILES = ("base", "arrow", "pandas", "polars", "duckdb", "engines", "ml", "all")
PROBE = (
    "import hashlib,json,platform,sys; from pathlib import Path; print(json.dumps({"
    "'python':platform.python_version(),'executable':sys.executable,"
    "'system':platform.system(),'machine':platform.machine(),'prefix':sys.prefix,"
    "'executable_sha256':hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()}))"
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(path: Path, data: object) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def checked_member(root: Path, name: str) -> Path:
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("manifest member missing, linked or outside kit: " + name)
    return path


def verify_kit(kit: Path) -> dict:
    manifest = json.loads((kit / "candidate.json").read_text("utf-8"))
    required_pythons(manifest)
    for name, record in manifest["files"].items():
        path = checked_member(kit, name)
        if path.stat().st_size != record["size_bytes"] or sha(path) != record["sha256"]:
            raise ValueError("candidate member hash/size differs: " + name)
    expected = {
        name + suffix
        for name in ("core", "benchmark", "consumer")
        for suffix in ("_wheel", "_sdist")
    }
    if (
        set(manifest.get("artifacts", {})) != expected
        or set(manifest.get("artifact_hashes", {})) != expected
    ):
        raise ValueError("candidate must identify all six exact distribution artifacts")
    for key, name in manifest["artifacts"].items():
        if (
            name not in manifest["files"]
            or manifest["files"][name]["sha256"] != manifest["artifact_hashes"][key]
        ):
            raise ValueError("artifact identity disagrees with the candidate file manifest")
    if not manifest.get("source"):
        raise ValueError("candidate source identity is required")
    candidate_manifests(kit, manifest)
    return manifest


def write_runtime_constraints(path: Path, versions: dict) -> None:
    """Use exact solved runtime pins without implicitly enabling pip hash mode."""
    if not versions or any(
        not isinstance(name, str)
        or not isinstance(version, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) is None
        or re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]*", version) is None
        for name, version in versions.items()
    ):
        raise ValueError("runtime constraints must be exact registry name/version pairs")
    path.write_text(
        "\n".join(f"{name}=={version}" for name, version in sorted(versions.items())) + "\n",
        encoding="utf-8",
    )


class Recorder:
    def __init__(self, directory: Path, receipt: dict):
        self.directory, self.receipt = directory, receipt
        allowed = {
            "APPDATA",
            "COLORTERM",
            "COMMONPROGRAMFILES",
            "COMMONPROGRAMFILES(X86)",
            "COMMONPROGRAMW6432",
            "COMSPEC",
            "CURL_CA_BUNDLE",
            "DEVELOPER_DIR",
            "HOME",
            "HOMEDRIVE",
            "HOMEPATH",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "LOCALAPPDATA",
            "MACOSX_DEPLOYMENT_TARGET",
            "PATH",
            "PATHEXT",
            "PROGRAMDATA",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "PROGRAMW6432",
            "REQUESTS_CA_BUNDLE",
            "SDKROOT",
            "SSL_CERT_DIR",
            "SSL_CERT_FILE",
            "SYSTEMDRIVE",
            "SYSTEMROOT",
            "TEMP",
            "TERM",
            "TMP",
            "TMPDIR",
            "TZ",
            "USERPROFILE",
            "WINDIR",
        }
        self.environment = {
            key: value for key, value in os.environ.items() if key.upper() in allowed
        }
        self.environment.update(
            PYTHONNOUSERSITE="1",
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONUTF8="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            OMP_NUM_THREADS="1",
            OPENBLAS_NUM_THREADS="1",
            POLARS_MAX_THREADS="1",
            UV_PYTHON_DOWNLOADS="never",
            UV_CACHE_DIR=str(directory / "uv-cache"),
            TMPDIR=str(directory / "temporary"),
        )
        (directory / "temporary").mkdir()
        (directory / "logs").mkdir()
        self.save()

    def save(self) -> None:
        write(self.directory / "receipt.json", self.receipt)

    def run(
        self,
        label: str,
        command: list[str],
        *,
        expected: int = 0,
        timeout: int = 1800,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess:
        number = len(self.receipt["commands"])
        log = self.directory / "logs" / f"{number:03d}-{label}.log"
        record = {
            "label": label,
            "command": command,
            "cwd": str(cwd or self.directory),
            "expected_exit": expected,
            "started_at": now(),
            "timeout_seconds": timeout,
            "exit_code": None,
            "status": "running",
            "log": str(log.relative_to(self.directory)),
        }
        self.receipt["commands"].append(record)
        self.save()
        start = time.monotonic()
        try:
            available = shutil.disk_usage(self.directory).free
            record["disk_free_before_bytes"] = available
            if available < 1024**3:
                record.update(status="blocked_resource", error="Less than 1 GiB free disk")
                log.write_text(
                    "Stopped before command: less than 1 GiB free disk\n",
                    encoding="utf-8",
                )
                raise RuntimeError("Resource guard: less than 1 GiB free disk")
            process = subprocess.Popen(
                command,
                cwd=cwd or self.directory,
                env=self.environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Signal only the process group created for this exact command.
                if os.name == "nt":
                    # Venv Python can be a launcher with a child interpreter.
                    # Terminate its owned tree so it cannot retain pipes/cwd.
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=5,
                        check=False,
                    )
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        process.kill()
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(
                    command, timeout, output=stdout, stderr=stderr
                ) from None
            result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            log.write_text(result.stdout + result.stderr, encoding="utf-8")
            record.update(
                exit_code=result.returncode,
                status="passed" if result.returncode == expected else "failed",
            )
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or "") + (error.stderr or "")
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            log.write_text(output, encoding="utf-8")
            record["status"] = "timeout"
            raise
        except OSError as error:
            record.update(status="failed_to_start", error=type(error).__name__)
            log.write_text(str(error) + "\n", encoding="utf-8")
            raise
        finally:
            record.update(seconds=time.monotonic() - start, finished_at=now())
            if log.exists():
                record["log_sha256"] = sha(log)
            self.save()
        if result.returncode != expected:
            raise RuntimeError(
                f"{label}: exit {result.returncode}, expected {expected}; preserve {log}"
            )
        return result


def python_at(venv: Path) -> str:
    candidates = (venv / "Scripts/python.exe", venv / "bin/python")
    for candidate in candidates:
        # A POSIX venv normally links to its selected base interpreter. Keep
        # the venv entry point: resolving it would lose the environment prefix.
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(f"virtual-environment Python is missing under {venv}")


def extract(sdist: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(sdist) as archive:
        archive.extractall(destination, filter="data")
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("unexpected sdist root")
    return roots[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--executor",
        required=True,
        help="Actual operator/Codex task identity; not a fabricated reviewer",
    )
    parser.add_argument("--python310", default="/usr/bin/python3.10")
    parser.add_argument("--python311", default="/usr/bin/python3.11")
    parser.add_argument("--python312", default="/usr/bin/python3.12")
    parser.add_argument("--python313", default="/usr/bin/python3.13")
    parser.add_argument("--lab-parent", type=Path, default=Path.home())
    parser.add_argument(
        "--cloud-validation",
        action="store_true",
        help="Test this runner on cloud x64; never counts as VM evidence",
    )
    parser.add_argument("--keep-successful-venvs", action="store_true")
    args = parser.parse_args()
    if not args.executor.strip() or "NOMBRE REAL" in args.executor:
        raise ValueError("record the actual executor, not the placeholder")
    kit = args.kit.resolve()
    manifest = verify_kit(kit)
    candidate_manifests(kit, manifest, required=True)
    minors = required_pythons(manifest)
    actual = {
        "hostname": socket.gethostname(),
        "user": getpass.getuser(),
        "uid": os.getuid(),
        "system": platform.system(),
        "machine": platform.machine(),
        "kernel": platform.release(),
    }
    if not args.cloud_validation and (
        actual["hostname"] != "maestria-vnic"
        or actual["user"] != "hernan"
        or actual["uid"] != 1003
        or actual["system"] != "Linux"
        or actual["machine"] != "aarch64"
    ):
        raise RuntimeError(
            "VM identity differs; stop and verify the environment before installation"
        )
    parent = args.lab_parent.resolve()
    if not parent.is_dir() or parent.stat().st_uid != os.getuid():
        raise ValueError("lab parent must already exist and be owned/authorized")
    if shutil.disk_usage(parent).free < 6 * 1024**3:
        raise RuntimeError(
            "Need 6 GiB free before preparing the lab; consumer retains its 4 GiB guard"
        )
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith(("MemTotal:", "MemAvailable:")):
            name, amount, _unit = line.split()
            memory[name.rstrip(":")] = int(amount) * 1024
    if memory.get("MemAvailable", 0) < 2 * 1024**3:
        raise RuntimeError("Need at least 2 GiB available memory before lab work")
    cgroup = {}
    for name in ("memory.max", "memory.current", "memory.high", "cpu.max"):
        try:
            cgroup[name] = Path("/sys/fs/cgroup", name).read_text().strip()
        except (OSError, ValueError) as error:
            cgroup[name] = {"unavailable": type(error).__name__}
    if isinstance(cgroup.get("memory.max"), str) and cgroup["memory.max"].isdigit():
        if (
            not isinstance(cgroup.get("memory.current"), str)
            or not cgroup["memory.current"].isdigit()
        ):
            raise RuntimeError("Finite cgroup memory limit without readable current usage")
        headroom = int(cgroup["memory.max"]) - int(cgroup["memory.current"])
        if headroom < 2 * 1024**3:
            raise RuntimeError("Need at least 2 GiB effective cgroup memory headroom")
    if resource is None:
        raise RuntimeError("the ARM64 lab requires POSIX resource limits")
    actual["resources"] = {
        "cpu_count": os.cpu_count(),
        "memory_bytes": memory,
        "cgroup_observed": cgroup,
        "rlimit_as": list(resource.getrlimit(resource.RLIMIT_AS)),
        "rlimit_cpu": list(resource.getrlimit(resource.RLIMIT_CPU)),
        "rlimit_nofile": list(resource.getrlimit(resource.RLIMIT_NOFILE)),
        "budget_is_system_quota": False,
    }
    os.umask(0o077)
    lab = Path(tempfile.mkdtemp(prefix="equiframe-maturity-", dir=parent))
    receipt = {
        "schema": receipt_schema(manifest),
        "required_python_versions": list(minors),
        "status": "running",
        "started_at": now(),
        "executor_declared": args.executor,
        "operator_authenticated": False,
        "independent_human_acceptance": False,
        "cloud_validation_only": args.cloud_validation,
        "actual_host": actual,
        "source": manifest["source"],
        "tooling_source": manifest.get("tooling_source"),
        "script_hashes": {
            name: sha(kit / name) for name in manifest["files"] if name.startswith("scripts/")
        },
        "controller_lock_sha256": sha(kit / "locks/controller.lock"),
        "data_manifest_sha256": sha(kit / "consumer-data/manifest.json"),
        "candidate_manifest_sha256": sha(kit / "candidate.json"),
        "artifact_hashes": manifest["artifact_hashes"],
        "test_manifests": manifest["test_manifests"],
        "lab": str(lab),
        "preflight_disk_free_bytes": shutil.disk_usage(parent).free,
        "commands": [],
        "python_cells": [],
        "created_environments": [],
        "removed_successful_environments": [],
        "errors": [],
    }
    record = Recorder(lab, receipt)
    print("Isolated lab:", lab, flush=True)
    artifacts = {name: kit / path for name, path in manifest["artifacts"].items()}
    try:
        control = lab / "controller"
        record.run("controller-venv", [sys.executable, "-m", "venv", str(control)])
        receipt["created_environments"].append(str(control))
        cp = python_at(control)
        record.run("controller-pip", [cp, "-m", "ensurepip", "--upgrade"])
        record.run(
            "controller-tools",
            [
                cp,
                "-m",
                "pip",
                "--isolated",
                "install",
                "--no-cache-dir",
                "--index-url",
                "https://pypi.org/simple",
                "--require-hashes",
                "-r",
                str(kit / "locks/controller.lock"),
            ],
        )
        uv = str(control / "bin/uv")
        sources = lab / "source"
        core = extract(artifacts["core_sdist"], sources / "core")
        benchmark = extract(artifacts["benchmark_sdist"], sources / "benchmark")
        consumer = extract(artifacts["consumer_sdist"], sources / "consumer")
        declared = lab / "declared-source-packages"
        for project, name in ((core, "equiframe"), (benchmark, "equiframe-benchmark")):
            target = declared / name
            target.mkdir(parents=True)
            for filename in ("pyproject.toml", "uv.lock", "README.md"):
                shutil.copy2(project / filename, target / filename)
            shutil.copytree(project / "src", target / "src")
        record.environment["EQUIFRAME_TEST_SOURCE_PACKAGES"] = str(declared)
        for minor in minors:
            interpreter = getattr(args, "python" + minor.replace(".", ""))
            cell = {
                "minor": minor,
                "status": "running",
                "profiles": [],
                "benchmark_profiles": [],
                "errors": [],
            }
            receipt["python_cells"].append(cell)
            try:
                info = json.loads(
                    record.run("python-" + minor, [interpreter, "-I", "-c", PROBE]).stdout
                )
                if (
                    not info["python"].startswith(minor + ".")
                    or info["machine"] != actual["machine"]
                ):
                    raise ValueError(
                        "requested interpreter version/architecture differs from reality"
                    )
                cell["interpreter"] = info
                for profile in PROFILES:
                    for endpoint in ("minimum", "latest"):
                        output = lab / f"py{minor}-{profile}-{endpoint}"
                        try:
                            record.run(
                                "core-" + minor + "-" + profile + "-" + endpoint,
                                [
                                    cp,
                                    str(core / "tools/verify_compatibility.py"),
                                    "--wheel",
                                    str(artifacts["core_wheel"]),
                                    "--sdist",
                                    str(artifacts["core_sdist"]),
                                    "--test-manifest",
                                    str(kit / manifest["test_manifests"]["core"]["path"]),
                                    "--python",
                                    interpreter,
                                    "--profile",
                                    profile,
                                    "--endpoint",
                                    endpoint,
                                    "--uv",
                                    uv,
                                    "--timeout",
                                    "1800",
                                    "--output",
                                    str(output),
                                ],
                                timeout=3600,
                            )
                            matrix = json.loads((output / "matrix.json").read_text("utf-8"))
                            if matrix["status"] != "passed":
                                raise RuntimeError("core matrix cell did not pass")
                        except Exception as error:
                            cell["profiles"].append(
                                {
                                    "profile": profile,
                                    "endpoint": endpoint,
                                    "status": "failed",
                                    "error": {
                                        "type": type(error).__name__,
                                        "message": str(error),
                                    },
                                }
                            )
                            cell["errors"].append(
                                {
                                    "profile": profile,
                                    "endpoint": endpoint,
                                    "message": str(error),
                                }
                            )
                            record.save()
                            continue
                        inner = output / f"python-1-{profile}-{endpoint}"
                        cell["profiles"].append(
                            {
                                "profile": profile,
                                "endpoint": endpoint,
                                "matrix": str((output / "matrix.json").relative_to(lab)),
                                "matrix_sha256": sha(output / "matrix.json"),
                                "status": "passed",
                            }
                        )
                        env = inner / "venv"
                        receipt["created_environments"].append(str(env))
                        if profile == "all" and endpoint == "latest":
                            all_python = python_at(env)
                            solved_core = json.loads((inner / "receipt.json").read_text("utf-8"))
                            constraints = inner / "pair-constraints.txt"
                            write_runtime_constraints(constraints, solved_core["runtime_versions"])
                            cell["paired_runtime_constraints_sha256"] = sha(constraints)
                            record.run(
                                "all-pip-" + minor,
                                [all_python, "-m", "ensurepip", "--upgrade"],
                            )
                            record.run(
                                "pip-upgrade-" + minor,
                                [
                                    all_python,
                                    "-m",
                                    "pip",
                                    "--isolated",
                                    "install",
                                    "--no-cache-dir",
                                    "--index-url",
                                    "https://pypi.org/simple",
                                    "pip==25.2",
                                ],
                            )
                            record.run(
                                "install-pair-consumer-" + minor,
                                [
                                    all_python,
                                    "-m",
                                    "pip",
                                    "--isolated",
                                    "install",
                                    "--no-cache-dir",
                                    "--index-url",
                                    "https://pypi.org/simple",
                                    "--report",
                                    str(inner / "pair-install-report.json"),
                                    "--constraint",
                                    str(constraints),
                                    str(artifacts["benchmark_wheel"]) + "[engines,ml,resources]",
                                    str(artifacts["consumer_wheel"]),
                                ],
                            )
                            record.run(
                                "pair-pip-check-" + minor,
                                [all_python, "-m", "pip", "check"],
                            )
                            record.run(
                                "benchmark-suite-" + minor,
                                [
                                    all_python,
                                    "-I",
                                    "-m",
                                    "pytest",
                                    "-p",
                                    "_hypothesis_pytestplugin",
                                    "-q",
                                    str(benchmark / "tests"),
                                    "--junitxml",
                                    str(inner / "benchmark-junit.xml"),
                                    "--basetemp",
                                    str(inner / "benchmark-pytest"),
                                ],
                                timeout=1800,
                            )
                            record.run(
                                "consumer-suite-" + minor,
                                [
                                    all_python,
                                    "-I",
                                    "-m",
                                    "pytest",
                                    "-p",
                                    "_hypothesis_pytestplugin",
                                    "-q",
                                    str(consumer / "tests"),
                                    "--junitxml",
                                    str(inner / "consumer-junit.xml"),
                                    "--basetemp",
                                    str(inner / "consumer-pytest"),
                                ],
                                timeout=1800,
                            )
                            for scenario, expected in (
                                ("good", 0),
                                ("different", 1),
                                ("not_evaluable", 3),
                                ("error", 2),
                            ):
                                target = inner / ("optimized-H-" + scenario)
                                record.run(
                                    "optimized-H-" + minor + "-" + scenario,
                                    [
                                        all_python,
                                        "-I",
                                        "-O",
                                        "-m",
                                        "equiframe.examples.journeys.h_portable_ci",
                                        "--case",
                                        scenario,
                                        "--output",
                                        str(target),
                                    ],
                                    expected=expected,
                                    timeout=120,
                                )
                            try:
                                record.run(
                                    "measure-bounded-" + minor,
                                    [
                                        all_python,
                                        "-I",
                                        str(kit / "scripts/measure_maturity.py"),
                                        "--output",
                                        str(inner / "measurements"),
                                        "--storage",
                                        "disk",
                                    ],
                                    timeout=600,
                                )
                            except (
                                RuntimeError,
                                OSError,
                                subprocess.TimeoutExpired,
                            ) as error:
                                cell["errors"].append(
                                    {
                                        "stage": "bounded-measurements",
                                        "type": type(error).__name__,
                                        "message": str(error),
                                    }
                                )
                                record.save()
                            record.run(
                                "consumer-" + minor,
                                [
                                    all_python,
                                    "-I",
                                    "-m",
                                    "equiframe_consumer_lab",
                                    "run",
                                    "--all",
                                    "--data",
                                    str(kit / "consumer-data"),
                                    "--output",
                                    str(inner / "consumer"),
                                ],
                                timeout=1800,
                            )
                            record.run(
                                "consumer-optimized-" + minor,
                                [
                                    all_python,
                                    "-I",
                                    "-O",
                                    "-m",
                                    "equiframe_consumer_lab",
                                    "run",
                                    "--all",
                                    "--require-optimized",
                                    "--data",
                                    str(kit / "consumer-data"),
                                    "--output",
                                    str(inner / "consumer-optimized"),
                                ],
                                timeout=1800,
                            )
                            record.run(
                                "consumer-recovery-" + minor,
                                [
                                    all_python,
                                    "-I",
                                    "-O",
                                    "-m",
                                    "equiframe_consumer_lab",
                                    "fault-checks",
                                    "--output",
                                    str(inner / "consumer-faults"),
                                ],
                                timeout=120,
                            )
                            summary = json.loads(
                                (inner / "consumer/summary.json").read_text("utf-8")
                            )
                            optimized_summary = json.loads(
                                (inner / "consumer-optimized/summary.json").read_text("utf-8")
                            )
                            if (
                                summary["status"] != "PASS"
                                or summary["distinct_cases"] != 72
                                or summary.get("optimization_required") is not False
                                or summary.get("optimized") is not False
                                or optimized_summary["status"] != "PASS"
                                or optimized_summary["distinct_cases"] != 72
                                or optimized_summary.get("optimization_required") is not True
                                or optimized_summary.get("optimized") is not True
                            ):
                                raise RuntimeError("consumer did not execute all 72 required cases")
                            cell["consumer"] = {
                                "summary": str((inner / "consumer/summary.json").relative_to(lab)),
                                "sha256": sha(inner / "consumer/summary.json"),
                                "accepted": summary["accepted_cases"],
                                "rejected": summary["rejected_cases"],
                            }
                            cell["consumer_optimized"] = {
                                "summary": str(
                                    (inner / "consumer-optimized/summary.json").relative_to(lab)
                                ),
                                "sha256": sha(inner / "consumer-optimized/summary.json"),
                                "accepted": optimized_summary["accepted_cases"],
                                "rejected": optimized_summary["rejected_cases"],
                            }
                            record.run(
                                "pair-binding-" + minor,
                                [
                                    all_python,
                                    "-I",
                                    str(kit / "scripts/installed_pair_probe.py"),
                                    "--core",
                                    str(artifacts["core_wheel"]),
                                    "--benchmark",
                                    str(artifacts["benchmark_wheel"]),
                                    "--consumer",
                                    str(artifacts["consumer_wheel"]),
                                    "--output",
                                    str(inner / "pair-binding.json"),
                                ],
                            )
                            # Rebuild each immutable sdist and compare every artifact byte.
                            cell["sdist_rebuilds"] = {}
                            for name in ("core", "benchmark", "consumer"):
                                rebuild_source = extract(
                                    artifacts[name + "_sdist"],
                                    inner / (name + "-rebuild"),
                                )
                                record.run(
                                    "sdist-build-" + name + "-" + minor,
                                    [all_python, "-m", "build"],
                                    cwd=rebuild_source,
                                    timeout=600,
                                )
                                rebuilt = rebuild_source / "dist" / artifacts[name + "_wheel"].name
                                if sha(rebuilt) != sha(artifacts[name + "_wheel"]):
                                    raise RuntimeError(
                                        name + " sdist did not reproduce the exact wheel"
                                    )
                                rebuilt_sdist = (
                                    rebuild_source / "dist" / artifacts[name + "_sdist"].name
                                )
                                if sha(rebuilt_sdist) != sha(artifacts[name + "_sdist"]):
                                    raise RuntimeError(
                                        name + " sdist did not reproduce the exact sdist"
                                    )
                                cell["sdist_rebuilds"][name] = {
                                    "wheel_sha256": sha(rebuilt),
                                    "sdist_sha256": sha(rebuilt_sdist),
                                }
                            sdvenv = inner / "sdist-environment"
                            record.run(
                                "sdist-venv-" + minor,
                                [interpreter, "-m", "venv", str(sdvenv)],
                            )
                            receipt["created_environments"].append(str(sdvenv))
                            sp = python_at(sdvenv)
                            record.run(
                                "sdist-pip-" + minor,
                                [sp, "-m", "ensurepip", "--upgrade"],
                            )
                            record.run(
                                "sdist-pip-upgrade-" + minor,
                                [
                                    sp,
                                    "-m",
                                    "pip",
                                    "--isolated",
                                    "install",
                                    "--no-cache-dir",
                                    "--index-url",
                                    "https://pypi.org/simple",
                                    "pip==25.2",
                                ],
                            )
                            record.run(
                                "sdist-install-" + minor,
                                [
                                    sp,
                                    "-m",
                                    "pip",
                                    "--isolated",
                                    "install",
                                    "--no-cache-dir",
                                    "--index-url",
                                    "https://pypi.org/simple",
                                    "--report",
                                    str(inner / "sdist-install-report.json"),
                                    "--constraint",
                                    str(constraints),
                                    str(artifacts["core_sdist"]) + "[engines,ml]",
                                    str(artifacts["benchmark_sdist"]) + "[resources]",
                                    str(artifacts["consumer_sdist"]),
                                ],
                                timeout=1800,
                            )
                            record.run("sdist-pip-check-" + minor, [sp, "-m", "pip", "check"])
                            record.run(
                                "sdist-consumer-" + minor,
                                [
                                    sp,
                                    "-I",
                                    "-O",
                                    "-m",
                                    "equiframe_consumer_lab",
                                    "fault-checks",
                                    "--output",
                                    str(inner / "sdist-consumer"),
                                ],
                                timeout=120,
                            )
                            # This direct sdist journey is additional to the 72-case wheel run.
                            # Keep the same consumer disk reserve; never use it to bypass run_all.
                            if shutil.disk_usage(inner).free < 4 * 1024**3:
                                raise RuntimeError(
                                    "Less than 4 GiB free before the sdist consumer journey"
                                )
                            cell["sdist_consumer_cases"] = []
                            for variant, expected in (
                                ("good", 0),
                                ("defect", 1),
                                ("not_evaluable", 3),
                            ):
                                destination = inner / ("sdist-native-" + variant)
                                record.run(
                                    "sdist-native-" + minor + "-" + variant,
                                    [
                                        sp,
                                        "-I",
                                        "-O",
                                        "-m",
                                        "equiframe_consumer_lab",
                                        "run",
                                        "--program",
                                        "reconciliation",
                                        "--variant",
                                        variant,
                                        "--source",
                                        "pandas",
                                        "--target",
                                        "duckdb",
                                        "--data",
                                        str(kit / "consumer-data"),
                                        "--output",
                                        str(destination),
                                    ],
                                    expected=expected,
                                    timeout=300,
                                )
                                case_file = destination / "case.json"
                                case = json.loads(case_file.read_text("utf-8"))
                                if (
                                    case.get("observed_exit_code") != expected
                                    or case.get("accepted") is not (variant == "good")
                                    or case.get("published") is not (variant == "good")
                                ):
                                    raise RuntimeError("sdist native consumer outcome differs")
                                cell["sdist_consumer_cases"].append(
                                    {
                                        "variant": variant,
                                        "receipt": str(case_file.relative_to(lab)),
                                        "sha256": sha(case_file),
                                    }
                                )
                            record.run(
                                "sdist-binding-" + minor,
                                [
                                    sp,
                                    "-I",
                                    str(kit / "scripts/installed_pair_probe.py"),
                                    "--core",
                                    str(artifacts["core_wheel"]),
                                    "--benchmark",
                                    str(artifacts["benchmark_wheel"]),
                                    "--consumer",
                                    str(artifacts["consumer_wheel"]),
                                    "--output",
                                    str(inner / "sdist-binding.json"),
                                ],
                            )
                            cell["sdist_verified"] = True
                            if not args.keep_successful_venvs:
                                shutil.rmtree(sdvenv)
                                receipt["removed_successful_environments"].append(str(sdvenv))
                        if not args.keep_successful_venvs:
                            shutil.rmtree(env)
                            receipt["removed_successful_environments"].append(str(env))
                        if not args.keep_successful_venvs:
                            cache = output / "uv-cache"
                            if cache.is_dir() and not cache.is_symlink():
                                shutil.rmtree(cache)
                                receipt.setdefault("removed_reconstructible_caches", []).append(
                                    str(cache)
                                )
                        record.save()
            except Exception as error:
                cell["status"] = "failed"
                cell["errors"].append({"type": type(error).__name__, "message": str(error)})
            if "interpreter" in cell:
                for profile in ("base", "engines", "ml", "resources", "all"):
                    for endpoint in ("minimum", "latest"):
                        out = lab / f"benchmark-{minor}-{profile}-{endpoint}"
                        item = {
                            "profile": profile,
                            "endpoint": endpoint,
                            "status": "running",
                        }
                        cell["benchmark_profiles"].append(item)
                        try:
                            record.run(
                                f"benchmark-profile-{minor}-{profile}-{endpoint}",
                                [
                                    cp,
                                    str(kit / "scripts/check_benchmark_profile.py"),
                                    "--python",
                                    interpreter,
                                    "--uv",
                                    uv,
                                    "--core",
                                    str(artifacts["core_wheel"]),
                                    "--benchmark",
                                    str(artifacts["benchmark_wheel"]),
                                    "--profile",
                                    profile,
                                    "--endpoint",
                                    endpoint,
                                    "--output",
                                    str(out),
                                ],
                                timeout=1800,
                            )
                            checked = json.loads((out / "receipt.json").read_text("utf-8"))
                            if checked.get("status") != "passed":
                                raise RuntimeError("benchmark profile did not pass")
                            item.update(
                                status="passed",
                                receipt=str((out / "receipt.json").relative_to(lab)),
                                receipt_sha256=sha(out / "receipt.json"),
                            )
                            if not args.keep_successful_venvs:
                                for name in ("venv", "uv-cache"):
                                    target = out / name
                                    if target.is_dir() and not target.is_symlink():
                                        shutil.rmtree(target)
                                        receipt.setdefault(
                                            "removed_reconstructible_profile_directories",
                                            [],
                                        ).append(str(target))
                        except Exception as error:
                            item.update(
                                status="failed",
                                error={
                                    "type": type(error).__name__,
                                    "message": str(error),
                                },
                            )
                            cell["errors"].append(item)
                        record.save()
                cell["status"] = (
                    "passed"
                    if not cell["errors"]
                    and all(profile["status"] == "passed" for profile in cell["profiles"])
                    and len(cell["profiles"]) == 16
                    and cell.get("sdist_verified")
                    and len(cell["benchmark_profiles"]) == 10
                    and all(profile["status"] == "passed" for profile in cell["benchmark_profiles"])
                    else "failed"
                )
            record.save()
        receipt["status"] = (
            "passed"
            if len(receipt["python_cells"]) == len(minors)
            and all(cell["status"] == "passed" for cell in receipt["python_cells"])
            else "failed"
        )
    except Exception as error:
        receipt["status"] = "failed"
        receipt["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        try:
            verify_kit(kit)
            receipt["kit_unchanged_after_run"] = True
        except Exception as error:
            receipt["kit_unchanged_after_run"] = False
            receipt["status"] = "failed"
            receipt["errors"].append({"stage": "final-kit-integrity", "type": type(error).__name__})
        receipt["finished_at"] = now()
        receipt["final_disk_free_bytes"] = shutil.disk_usage(parent).free
        record.save()
        files = {}
        for path in sorted(lab.rglob("*")):
            if (
                path.is_file()
                and not path.is_symlink()
                and not any(
                    part
                    in {
                        "venv",
                        "controller",
                        "uv-cache",
                        "temporary",
                        "sdist-environment",
                        "__pycache__",
                    }
                    for part in path.relative_to(lab).parts
                )
            ):
                files[str(path.relative_to(lab))] = {
                    "sha256": sha(path),
                    "size_bytes": path.stat().st_size,
                }
        write(lab / "evidence-inventory.json", {"files": files, "unsigned": True})
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "lab": str(lab),
                "cloud_validation_only": args.cloud_validation,
            }
        )
    )
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
