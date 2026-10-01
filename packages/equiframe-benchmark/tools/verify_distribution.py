"""Install both distributions with pip outside the checkout, then run the native pilot."""

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT.parent / "equiframe"


def run(args: list[str], cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def main() -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv must be on PATH")
    wheel = ROOT / "dist" / "equiframe_benchmark-0.7.0-py3-none-any.whl"
    core_wheel = CORE / "dist" / "equiframe-0.7.0-py3-none-any.whl"
    sdist = ROOT / "dist" / "equiframe_benchmark-0.7.0.tar.gz"
    for artifact in (wheel, core_wheel, sdist):
        if not artifact.is_file():
            raise SystemExit("build both distributions first: " + artifact.name)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)
    with tempfile.TemporaryDirectory(prefix="equiframe-step6-") as temporary:
        work = Path(temporary).resolve()
        environment = work / ".venv"
        env["UV_PROJECT_ENVIRONMENT"] = str(environment)
        run(
            [
                uv,
                "sync",
                "--locked",
                "--all-extras",
                "--no-install-project",
                "--no-install-package",
                "equiframe",
                "--python",
                sys.executable,
            ],
            ROOT,
            env,
        )
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run([str(python), "-m", "ensurepip"], work, env)
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(CORE / "dist"),
                "--find-links",
                str(ROOT / "dist"),
                "equiframe==0.7.0",
                "equiframe-benchmark==0.7.0",
            ],
            work,
            env,
        )
        run([str(python), "-m", "pip", "check"], work, env)
        check = """
import importlib.metadata, sys
from pathlib import Path
import equiframe as ef
assert 'equiframe_benchmark' not in sys.modules
assert not any(n in sys.modules for n in ('pyarrow','pandas','polars','duckdb','numpy','sklearn'))
import equiframe_benchmark as eb
assert not any(n in sys.modules for n in ('pyarrow','pandas','polars','duckdb','numpy','sklearn'))
for module in (ef, eb):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert not Path.cwd().is_relative_to(Path(sys.argv[1]))
assert importlib.metadata.version('equiframe-benchmark') == '0.7.0'
"""
        run([str(python), "-I", "-c", check, str(ROOT.parents[1])], work, env)
        shutil.copytree(
            ROOT / "tests", work / "tests", ignore=shutil.ignore_patterns("__pycache__")
        )
        run(
            [
                str(python),
                "-I",
                "-m",
                "pytest",
                "-q",
                "-x",
                "--tb=short",
                "--basetemp=" + str(work / "pytest-tmp"),
                "tests",
            ],
            work,
            env,
        )
        run(
            [str(python), "-I", "-m", "equiframe_benchmark.pilot", "--output", str(work / "pilot")],
            work,
            env,
        )
        extracted = work / "sdist"
        with tarfile.open(sdist) as archive:
            archive.extractall(extracted, filter="data")
        project = next(extracted.iterdir())
        run([sys.executable, "-m", "build", "--no-isolation", "--wheel"], project, env)
        rebuilt = project / "dist" / wheel.name
        if (
            hashlib.sha256(rebuilt.read_bytes()).digest()
            != hashlib.sha256(wheel.read_bytes()).digest()
        ):
            raise RuntimeError("sdist did not reproduce the same wheel bytes")
        print(
            "pip installation, installed tests, native pilot and identical sdist rebuild verified"
        )


if __name__ == "__main__":
    main()
