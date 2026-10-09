#!/usr/bin/env python3
"""Resolve and exercise one exact paired-wheel benchmark profile on actual Python."""

from __future__ import annotations

import argparse
import json
import subprocess
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from run_vm_lab import Recorder, now, python_at, sha

PROFILES = ("base", "engines", "ml", "resources", "all")


def requirements(core: Path, benchmark: Path, profile: str, env: dict) -> list[str]:
    def metadata(path: Path):
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise ValueError("expected one METADATA")
            return BytesParser().parsebytes(archive.read(names[0]))

    core_meta, benchmark_meta = metadata(core), metadata(benchmark)
    selected = (
        {"engines", "ml", "resources"}
        if profile == "all"
        else set()
        if profile == "base"
        else {profile}
    )
    core_extras, result = set(), set()
    for meta, extras in [(benchmark_meta, selected), (core_meta, core_extras)]:
        for raw in meta.get_all("Requires-Dist", []):
            req = Requirement(raw)
            if req.marker and not any(
                req.marker.evaluate({**env, "extra": extra}) for extra in ("", *extras)
            ):
                continue
            if canonicalize_name(req.name) == "equiframe":
                if core_meta["Version"] not in req.specifier:
                    raise ValueError("paired core version is outside benchmark requirement")
                core_extras.update(req.extras)
                continue
            if req.url:
                raise ValueError("only registry dependency requirements are expected")
            req.marker = None
            result.add(str(req))
    return sorted(result)


def resolution_command(
    uv: list[str], runtime_input: Path, python: str, endpoint: str, lock: Path
) -> list[str]:
    """Resolve only versions that can also satisfy the binary-only installation gate."""
    if endpoint not in ("minimum", "latest"):
        raise ValueError("unknown benchmark profile endpoint: " + endpoint)
    return [
        *uv,
        "pip",
        "compile",
        str(runtime_input),
        "--python",
        python,
        "--generate-hashes",
        "--only-binary",
        ":all:",
        "--resolution",
        "lowest-direct" if endpoint == "minimum" else "highest",
        "--refresh",
        "--index-url",
        "https://pypi.org/simple",
        "--output-file",
        str(lock),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True)
    parser.add_argument("--uv", required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--endpoint", choices=("minimum", "latest"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    directory = args.output.resolve()
    receipt = {
        "schema": "equiframe-benchmark-profile-1",
        "status": "running",
        "started_at": now(),
        "profile": args.profile,
        "endpoint": args.endpoint,
        "artifacts": {
            "core_wheel": sha(args.core),
            "benchmark_wheel": sha(args.benchmark),
        },
        "commands": [],
        "errors": [],
    }
    record = Recorder(directory, receipt)
    try:
        probe = (
            "import json,platform,sys; print(json.dumps({"
            "'python_version':'.'.join(map(str,sys.version_info[:2])),"
            "'python_full_version':platform.python_version(),"
            "'platform_machine':platform.machine(),'platform_system':platform.system(),"
            "'sys_platform':sys.platform,'os_name':__import__('os').name}))"
        )
        info = json.loads(record.run("interpreter", [args.python, "-I", "-c", probe]).stdout)
        receipt["interpreter"] = info
        selected = requirements(
            args.core, args.benchmark, args.profile, {**default_environment(), **info}
        )
        (directory / "runtime.in").write_text("\n".join(selected) + "\n", encoding="utf-8")
        receipt["selected_requirements"] = selected
        uv = [args.uv, "--no-config", "--cache-dir", str(directory / "uv-cache")]
        lock = directory / "runtime.lock"
        record.run(
            "resolve",
            resolution_command(uv, directory / "runtime.in", args.python, args.endpoint, lock),
        )
        receipt["runtime_lock_sha256"] = sha(lock)
        venv = directory / "venv"
        record.run(
            "venv",
            [*uv, "venv", "--python", args.python, "--no-python-downloads", str(venv)],
        )
        python = python_at(venv)
        record.run(
            "dependencies",
            [
                *uv,
                "pip",
                "sync",
                "--python",
                python,
                "--require-hashes",
                "--only-binary",
                ":all:",
                "--link-mode",
                "copy",
                str(lock),
            ],
        )
        record.run(
            "install-wheels",
            [
                *uv,
                "pip",
                "install",
                "--python",
                python,
                "--no-index",
                "--link-mode",
                "copy",
                str(args.core),
                str(args.benchmark),
            ],
        )
        record.run("pip-check", [*uv, "pip", "check", "--python", python])
        binding = directory / "runtime-binding.json"
        record.run(
            "binding",
            [
                python,
                "-I",
                str(Path(__file__).with_name("installed_pair_probe.py")),
                "--core",
                str(args.core),
                "--benchmark",
                str(args.benchmark),
                "--profile",
                args.profile,
                "--output",
                str(binding),
            ],
        )
        receipt["runtime_binding_sha256"] = sha(binding)
        record.run(
            "cli-help",
            [python, "-I", "-m", "equiframe_benchmark", "--help"],
            timeout=120,
        )
        # Native pilot needs all engines; ML and resources are exercised separately.
        if args.profile in ("engines", "all"):
            record.run(
                "native-pilot",
                [
                    python,
                    "-I",
                    "-m",
                    "equiframe_benchmark.pilot",
                    "--output",
                    str(directory / "pilot"),
                ],
                timeout=600,
            )
        record.run(
            "optional-boundary",
            [
                python,
                "-I",
                str(Path(__file__).with_name("profile_boundary_probe.py")),
                "--profile",
                args.profile,
                "--output",
                str(directory / "boundary.json"),
            ],
            timeout=120,
        )
        receipt["status"] = "passed"
    except (Exception, subprocess.SubprocessError) as error:
        receipt["status"] = "failed"
        receipt["errors"].append({"type": type(error).__name__, "message": str(error)})
    finally:
        receipt["finished_at"] = now()
        record.save()
    print(json.dumps({"status": receipt["status"], "output": str(directory)}))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
