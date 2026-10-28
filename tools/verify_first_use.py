"""Install and exercise the portable first-use kit outside the checkout.

A retained --output directory contains the immutable kit, isolated virtualenv,
synthetic private evidence and a machine execution receipt. It is not a safe
upload directory or a human first-use acceptance record. --offline requires an
already populated uv cache; it never downloads missing dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from datetime import timezone as _timezone
from pathlib import Path
from typing import Any

from build_first_use_kit import ROOT, build_kit, file_record
from release_manifest import repository_root

UTC = _timezone.utc

_INSTALL_PROBE = r"""
import hashlib, importlib.metadata, importlib.util, json, re, sys
from pathlib import Path
import equiframe as ef
kit, checkout = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
manifest = json.loads((kit / 'manifest.json').read_text('utf-8'))
origin = Path(ef.__file__).resolve()
assert origin.is_relative_to(Path(sys.prefix).resolve()), origin
assert not origin.is_relative_to(checkout), origin
assert not Path.cwd().resolve().is_relative_to(checkout)
assert ef.__version__ == importlib.metadata.version('equiframe') == manifest['package']['version']
assert not any(name in sys.modules for name in ('pandas','duckdb','pyarrow','numpy'))
assert importlib.util.find_spec('polars') is None
assert importlib.util.find_spec('sklearn') is None
for name, record in manifest['runtime_payload']['files'].items():
    path = origin.parent.parent / name
    assert path.is_file() and not path.is_symlink(), name
    raw = path.read_bytes()
    assert len(raw) == record['size_bytes']
    assert hashlib.sha256(raw).hexdigest() == record['sha256'], name
versions = {}
for name, version in re.findall(r'^([a-z0-9-]+)==([^\s]+)',
        (kit / 'requirements.lock').read_text('utf-8'), re.M):
    actual = importlib.metadata.version(name)
    assert actual == version, (name, actual, version)
    versions[name] = actual
print(json.dumps({'equiframe_origin': str(origin), 'version': ef.__version__,
                  'python': sys.version, 'dependencies': versions}, sort_keys=True))
"""

_REPORT_PROBE = r"""
import json, runpy, sys
from pathlib import Path
import equiframe as ef
kit, directory, state = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
runpy.run_path(str(kit / 'assertion_ci.py'))['verify_upload_directory'](directory)
report = ef.read_comparison_report(directory / 'report.json')
assert report.state == state, (report.state, state)
print('Redacted report manifest verified:', state)
"""


_REFACTOR_PROBE = r"""
import sys
from pathlib import Path
import equiframe as ef
output, state, strategy = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
assert {p.name for p in output.iterdir()} == {'contract.json', 'report'}
contract = ef.DiffContract.model_validate_json((output / 'contract.json').read_bytes())
report = ef.read_comparison_report(output / 'report' / 'report.json')
assert report.state == state and report.complete
assert report.strategy == strategy
assert contract.spec.contract.output.schema_spec.order.kind == 'ignored'
print('Inspectable refactor contract and report:', state, strategy)
"""


def verify_first_use(
    work: Path,
    *,
    uv: str,
    offline: bool = False,
    environment: dict[str, str] | None = None,
    consumer_environment: Path | None = None,
) -> dict[str, Any]:
    """Fail the release gate on any incorrect install, exit code or report."""
    if sys.version_info[:2] not in {(3, 10), (3, 11), (3, 12), (3, 13)}:
        raise RuntimeError("the first-use candidate requires Python 3.10-3.13")
    checkout = repository_root(ROOT)
    if work.resolve().is_relative_to(checkout):
        raise ValueError("consumer environment and output must be outside the checkout")
    work.mkdir(parents=True, exist_ok=False)
    work = work.resolve()
    logs = work / "logs"
    logs.mkdir()
    env = dict(os.environ if environment is None else environment)
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        env.pop(key, None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.setdefault("UV_CACHE_DIR", str(work / "cache" / "uv"))
    uv_command = [uv, "--no-config", *(["--offline"] if offline else [])]
    receipt: dict[str, Any] = {
        "schema": "equiframe-first-use-execution-1",
        "started_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "offline": offline,
        "synthetic_data_only": True,
        "human_acceptance": "not_performed",
        "remote_ci": "not_established",
        "passed": False,
        "commands": [],
    }

    def execute(
        label: str,
        arguments: list[str],
        *,
        cwd: Path = work,
        expected: int = 0,
        allow_traceback: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            arguments,
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        stdout, stderr = logs / (label + ".stdout.txt"), logs / (label + ".stderr.txt")
        stdout.write_text(result.stdout, "utf-8")
        stderr.write_text(result.stderr, "utf-8")
        record = {
            "label": label,
            "command": arguments,
            "cwd": str(cwd),
            "expected_exit": expected,
            "actual_exit": result.returncode,
            "stdout": {"file": stdout.relative_to(work).as_posix(), **file_record(stdout)},
            "stderr": {"file": stderr.relative_to(work).as_posix(), **file_record(stderr)},
        }
        receipt["commands"].append(record)
        if result.returncode != expected:
            raise RuntimeError(
                f"first-use {label}: exit {result.returncode}, expected {expected}; logs: {logs}"
            )
        if not allow_traceback and "Traceback" in result.stdout + result.stderr:
            raise RuntimeError("first-use recipe exposed an unexpected traceback: " + label)
        print(f"First-use {label}: expected exit {expected}")
        return result

    try:
        kit = work / "kit"
        manifest = build_kit(kit, python_minor=f"{sys.version_info[0]}.{sys.version_info[1]}")
        receipt["kit_manifest"] = file_record(kit / "manifest.json")
        receipt["wheel"] = {"file": manifest["wheel"], **manifest["files"][manifest["wheel"]]}
        receipt["source_payload"] = manifest["source_payload"]
        execute("kit-before", [sys.executable, "-I", "-B", str(kit / "verify_kit.py")])
        runtime = work / "runtime"
        clear = []
        if consumer_environment is not None:
            runtime = consumer_environment.absolute()
            if runtime != work.parent / "runtime" or runtime.is_symlink():
                raise ValueError("shared consumer must be the adjacent QA runtime directory")
            clear = ["--clear"]
        execute(
            "create-environment",
            [*uv_command, "venv", *clear, "--python", sys.executable, str(runtime)],
        )
        python = str(runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        execute(
            "install-locked-dependencies",
            [
                *uv_command,
                "pip",
                "install",
                "--python",
                python,
                "--require-hashes",
                "--only-binary",
                ":all:",
                "-r",
                str(kit / "requirements.lock"),
            ],
        )
        execute(
            "install-exact-wheel",
            [
                *uv_command,
                "pip",
                "install",
                "--python",
                python,
                "--no-index",
                str(kit / manifest["wheel"]),
            ],
        )
        execute("dependency-check", [*uv_command, "pip", "check", "--python", python])
        installed = execute(
            "installed-origin",
            [python, "-I", "-B", "-c", _INSTALL_PROBE, str(kit), str(checkout)],
        )
        receipt["installed"] = json.loads(installed.stdout)
        results = work / "results"
        results.mkdir()
        for scenario, expected in (("equivalent", 0), ("different", 1)):
            for without_key in (False, True):
                name = "refactor-" + scenario + ("-without-key" if without_key else "")
                destination = results / name
                execute(
                    name,
                    [
                        python,
                        "-I",
                        "-B",
                        str(kit / "refactor_comparison.py"),
                        "--case",
                        scenario,
                        "--output",
                        str(destination),
                        "--work-dir",
                        str(results / (name + "-private")),
                        *(["--without-key"] if without_key else []),
                    ],
                    expected=expected,
                )
                execute(
                    name + "-report",
                    [
                        python,
                        "-I",
                        "-B",
                        "-c",
                        _REFACTOR_PROBE,
                        str(destination),
                        scenario,
                        "multiset" if without_key else "key",
                    ],
                )
        for scenario, expected in (("equivalent", 0), ("different", 1), ("not_evaluable", 3)):
            name = "migration-" + scenario
            execute(
                name,
                [
                    python,
                    "-I",
                    "-B",
                    str(kit / "migrate_duckdb_recipe.py"),
                    "--case",
                    scenario,
                    "--output",
                    str(results / name),
                    "--work-dir",
                    str(results / (name + "-private")),
                ],
                expected=expected,
            )
            for report_name in ("source-target", "source-expected", "target-expected"):
                state = (
                    "equivalent"
                    if scenario == "different" and report_name == "source-target"
                    else scenario
                )
                execute(
                    name + "-" + report_name,
                    [
                        python,
                        "-I",
                        "-B",
                        "-c",
                        _REPORT_PROBE,
                        str(kit),
                        str(results / name / report_name),
                        state,
                    ],
                )
        for scenario, expected in (("equivalent", 0), ("different", 1), ("not_evaluable", 3)):
            name = "assertion-" + scenario
            report = results / name
            execute(
                name,
                [
                    python,
                    "-I",
                    "-B",
                    str(kit / "assertion_ci.py"),
                    "--case",
                    scenario,
                    "--output",
                    str(report),
                    "--work-dir",
                    str(results / (name + "-private")),
                ],
                expected=expected,
            )
            execute(
                name + "-report",
                [python, "-I", "-B", "-c", _REPORT_PROBE, str(kit), str(report), scenario],
            )
            case = results / ("pytest-" + scenario)
            case.mkdir()
            execute(
                "pytest-" + scenario,
                [
                    python,
                    "-I",
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "-o",
                    "addopts=",
                    "--confcutdir",
                    str(kit),
                    str(kit / "test_assertion_recipe.py")
                    + f"::test_materialized_output[{scenario}]",
                ],
                cwd=case,
                expected=0 if scenario == "equivalent" else 1,
                allow_traceback=True,
            )
            execute(
                "pytest-" + scenario + "-report",
                [
                    python,
                    "-I",
                    "-B",
                    "-c",
                    _REPORT_PROBE,
                    str(kit),
                    str(case / "ci-reports" / scenario),
                    scenario,
                ],
            )
        execute("kit-after", [python, "-I", "-B", str(kit / "verify_kit.py")])
        receipt["passed"] = True
    finally:
        receipt["finished_at"] = datetime.now(UTC).isoformat()
        (work / "receipt.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n", "utf-8"
        )
    print("First-use kit passed a clean installed consumer rehearsal; no human acceptance claimed")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--offline", action="store_true", help="use only the existing uv cache")
    parser.add_argument(
        "--output", type=Path, help="retain evidence in a fresh directory outside Git"
    )
    args = parser.parse_args()
    uv = shutil.which(args.uv)
    if uv is None:
        parser.error("uv executable not found; use --uv /absolute/path/to/uv")
    if args.output is not None:
        verify_first_use(args.output, uv=uv, offline=args.offline)
        print("Execution receipt: " + str(args.output.resolve() / "receipt.json"))
    else:
        with tempfile.TemporaryDirectory(prefix="equiframe-first-use-") as directory:
            verify_first_use(Path(directory) / "consumer", uv=uv, offline=args.offline)


if __name__ == "__main__":
    main()
