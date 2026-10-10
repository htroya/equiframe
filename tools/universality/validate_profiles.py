"""Finite profile conformance on unchanged A11 archives, not full platform matrix."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

p = argparse.ArgumentParser()
for name in (
    "uv",
    "base-python",
    "cache",
    "pins",
    "artifacts",
    "source",
    "benchmark-source",
    "output",
):
    p.add_argument("--" + name, required=True, type=Path)
p.add_argument("--offline", action="store_true")
p.add_argument("--package", choices=("core", "benchmark", "all"), default="all")
p.add_argument(
    "--profile",
    action="append",
    choices=(
        "base",
        "arrow",
        "pandas",
        "polars",
        "duckdb",
        "engines",
        "ml",
        "resources",
        "all",
    ),
)
p.add_argument("--benchmark-probe", required=True, type=Path)
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
env = {
    k: v
    for k, v in os.environ.items()
    if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")
}
env.update(
    UV_CACHE_DIR=str(a.cache.resolve()),
    UV_NO_CONFIG="1",
    UV_PYTHON_DOWNLOADS="never",
    OPENBLAS_NUM_THREADS="1",
    OMP_NUM_THREADS="1",
    POLARS_MAX_THREADS="2",
    PYTHONUTF8="1",
)
source = a.source.resolve()
bsource = a.benchmark_source.resolve()
core = next(a.artifacts.resolve().glob("equiframe-*.whl"))
bench = next(a.artifacts.resolve().glob("equiframe_benchmark-*.whl"))
manifest = {
    "checkout": str(source),
    "version": "0.12.0a11",
    "runtime_files": {},
    "artifact_sha256": {
        w.name: hashlib.sha256(w.read_bytes()).hexdigest() for w in (core, bench)
    },
}
with zipfile.ZipFile(core) as z:
    for name in z.namelist():
        if name.startswith("equiframe/") and not name.endswith("/"):
            raw = z.read(name)
            manifest["runtime_files"][name] = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
shutil.copyfile(a.pins.resolve(), out / "pins.txt")
shutil.copyfile(source / "tools/compatibility_probe.py", out / "compatibility_probe.py")
shutil.copyfile(a.benchmark_probe.resolve(), out / "benchmark_probe.py")
summary = {
    "candidate": "0.12.0a11",
    "state": "running",
    "manual": True,
    "cells": [],
    "artifact_sha256": manifest["artifact_sha256"],
    "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}


def save():
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


class Runner:
    def __init__(self, directory):
        self.directory = directory
        self.steps = []

    def run(self, command, stage, expected_exit=0):
        if shutil.disk_usage(out).free < 4 * 1024**3:
            raise RuntimeError("Disk guard")
        begin = time.monotonic()
        result = subprocess.run(
            [str(x) for x in command],
            cwd=self.directory,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1200,
            check=False,
        )
        (self.directory / (stage + ".log")).write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
        self.steps.append(
            {
                "name": stage,
                "exit_code": result.returncode,
                "expected": expected_exit,
                "seconds": time.monotonic() - begin,
            }
        )
        print(self.directory.name, stage, result.returncode, flush=True)
        if result.returncode != expected_exit:
            raise RuntimeError(stage + " failed; see retained log")
        return result


def examples(r, py, profile):
    # Real public native implementations; independent fixture checks occur in examples.
    engines = (
        ("pandas", "polars", "duckdb")
        if profile in ("engines", "all")
        else (profile,)
        if profile in ("pandas", "polars", "duckdb")
        else ()
    )
    for engine in engines:
        r.run(
            [
                py,
                "-I",
                source / "examples/execute_native.py",
                "--engine",
                engine,
                "--work-dir",
                r.directory / ("native-" + engine),
            ],
            "native-" + engine,
        )
    if profile in ("engines", "all"):
        r.run(
            [
                py,
                "-I",
                source / "examples/migrate_native.py",
                "--output",
                r.directory / "six-migrations",
            ],
            "native-six-directions",
        )
    if profile in ("ml", "all"):
        r.run(
            [
                py,
                "-I",
                source / "examples/detectors_local.py",
                "--bundle",
                r.directory / "detectors.json",
            ],
            "ml-fit-calibrate-detect",
        )


try:
    for package, profiles in (
        (
            "core",
            ("base", "arrow", "pandas", "polars", "duckdb", "engines", "ml", "all"),
        ),
        ("benchmark", ("base", "engines", "ml", "resources", "all")),
    ):
        if a.package not in ("all", package):
            continue
        for profile in profiles:
            if a.profile and profile not in a.profile:
                continue
            cell = out / (package + "-" + profile)
            cell.mkdir()
            receipt = {"package": package, "profile": profile, "state": "running"}
            summary["cells"].append(receipt)
            r = Runner(cell)
            try:
                py = (
                    cell
                    / "venv"
                    / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                )
                uv = a.uv.resolve()
                r.run(
                    [uv, "venv", "--python", a.base_python.resolve(), cell / "venv"],
                    "create-venv",
                )
                name = "equiframe" if package == "core" else "equiframe-benchmark"
                extras = (
                    (
                        "arrow,pandas,polars,duckdb,engines,ml"
                        if package == "core"
                        else "engines,ml,resources"
                    )
                    if profile == "all"
                    else ""
                    if profile == "base"
                    else profile
                )
                requirements = [
                    name
                    + ("[" + extras + "]" if extras else "")
                    + " @ "
                    + (core if package == "core" else bench).as_uri()
                ]
                if package == "benchmark":
                    requirements.append("equiframe @ " + core.as_uri())
                (cell / "requirements.txt").write_text("\n".join(requirements) + "\n")
                r.run(
                    [
                        uv,
                        "pip",
                        "install",
                        *(
                            ["--offline"]
                            if a.offline
                            else ["--index-url", "https://pypi.org/simple"]
                        ),
                        "--python",
                        py,
                        "--link-mode",
                        "copy",
                        "-c",
                        "../pins.txt",
                        "-r",
                        "requirements.txt",
                    ],
                    "normal-profile-resolution",
                )
                r.run([uv, "pip", "check", "--python", py], "pip-check")
                if package == "core":
                    r.run(
                        [
                            py,
                            "-I",
                            out / "compatibility_probe.py",
                            "--manifest",
                            out / "manifest.json",
                            "--source",
                            source,
                            "--profile",
                            profile,
                            "--output",
                            cell / "binding.json",
                        ],
                        "public-api-positive-negative",
                    )
                    examples(r, py, profile)
                else:
                    r.run(
                        [
                            py,
                            "-I",
                            out / "benchmark_probe.py",
                            "--manifest",
                            out / "manifest.json",
                            "--wheel",
                            bench,
                            "--source",
                            source,
                            "--profile",
                            profile,
                            "--output",
                            cell / "binding.json",
                        ],
                        "public-api-positive-negative",
                    )
                    examples(
                        r, py, "arrow" if profile in ("base", "resources") else profile
                    )
                    resources = profile in ("resources", "all")
                    completed = r.run(
                        [
                            py,
                            "-I",
                            bsource / "examples/scale_local.py",
                            "--rows",
                            "1000",
                            "--output",
                            cell / "scale",
                        ],
                        "bounded-scale" if resources else "missing-resource-negative",
                        expected_exit=0 if resources else 3,
                    )
                    measured = json.loads(completed.stdout)
                    if resources:
                        if (
                            not measured["complete"]
                            or measured["correct_complete_repetitions"] != 3
                        ):
                            raise ValueError(
                                "Resource-enabled scale did not complete three actual repetitions"
                            )
                        if measured["process"]["sample_count"] <= 0:
                            raise ValueError("Resources profile lacks actual samples")
                    else:
                        if (
                            measured["complete"]
                            or measured["observed_repetitions"] != 0
                            or not any(
                                item.startswith("resources_extra_unavailable:")
                                for item in measured["process"]["monitoring_errors"]
                            )
                        ):
                            raise ValueError(
                                "Missing resources did not preserve its explicit limitation"
                            )
                    receipt["bounded_scale"] = measured
                invalid = cell / "invalid-contract.json"
                invalid.write_text('{"schema_version":"invalid"}\n')
                r.run(
                    [py, "-I", "-m", "equiframe", "contract", "validate", invalid],
                    "invalid-contract",
                    expected_exit=2,
                )
                r.run([py, "-I", "-m", "equiframe", "--help"], "core-cli-help")
                if package == "benchmark":
                    r.run(
                        [py, "-I", "-m", "equiframe_benchmark", "--help"],
                        "benchmark-cli-help",
                    )
                receipt["binding"] = json.loads((cell / "binding.json").read_text())
                receipt["state"] = "passed"
            except Exception as error:
                receipt["state"] = "failed"
                receipt["error"] = type(error).__name__ + ": " + str(error)
                raise
            finally:
                receipt["steps"] = r.steps
                (cell / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
                save()
    expected_cells = {"core": 8, "benchmark": 5, "all": 13}[a.package]
    if a.profile:
        groups = {
            "core": (
                "base",
                "arrow",
                "pandas",
                "polars",
                "duckdb",
                "engines",
                "ml",
                "all",
            ),
            "benchmark": ("base", "engines", "ml", "resources", "all"),
        }
        expected_cells = sum(
            profile in a.profile
            for package, profiles in groups.items()
            if a.package in ("all", package)
            for profile in profiles
        )
    if not expected_cells:
        raise ValueError("Requested profiles do not belong to selected package")
    if len(summary["cells"]) != expected_cells or any(
        c["state"] != "passed" for c in summary["cells"]
    ):
        raise RuntimeError("Incomplete profiles")
    summary["state"] = "passed"
except Exception as error:
    summary["state"] = "failed"
    summary["error"] = type(error).__name__ + ": " + str(error)
    raise
finally:
    summary["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save()
