"""Verify built wheel/sdist using a clean runtime-only locked environment."""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def single(pattern: str) -> Path:
    paths = tuple((ROOT / "dist").glob(pattern))
    if len(paths) != 1:
        raise RuntimeError("expected one built artifact matching " + pattern)
    return paths[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args()
    uv = shutil.which(args.uv)
    if uv is None:
        parser.error("uv executable not found; use --uv /absolute/path/to/uv")
    wheel = single("equiframe-*.whl")
    sdist = single("equiframe-*.tar.gz")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        if "equiframe/py.typed" not in names or "equiframe/__init__.py" not in names:
            raise RuntimeError("wheel is missing typed public package files")
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="distribution-", dir=cache) as directory:
        work = Path(directory).resolve()
        runtime = work / "runtime"
        env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(runtime), UV_CACHE_DIR=str(cache / "uv"))
        # The development checkout is deliberately absent from the clean environment.
        env.pop("PYTHONPATH", None)
        env.pop("VIRTUAL_ENV", None)
        run(
            [
                uv,
                "sync",
                "--locked",
                "--no-dev",
                "--no-install-project",
                "--python",
                sys.executable,
            ],
            cwd=ROOT,
            env=env,
        )
        python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(
            [uv, "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
            cwd=work,
            env=env,
        )
        run([uv, "pip", "check", "--python", str(python)], cwd=work, env=env)
        check = """
import importlib.metadata
import importlib.util
from pathlib import Path
import sys
import equiframe
root = Path(sys.prefix).resolve()
assert Path(equiframe.__file__).resolve().is_relative_to(root), equiframe.__file__
assert Path(equiframe.__file__).with_name('py.typed').is_file()
assert equiframe.__version__ == importlib.metadata.version('equiframe') == '0.1.0'
for name in ('pandas', 'polars', 'duckdb', 'sklearn', 'numpy', 'pyarrow', 'pytest', 'hypothesis'):
    assert importlib.util.find_spec(name) is None, name
print('Installed wheel imports from clean site-packages without engines/ML/dev tools')
"""
        run([str(python), "-I", "-c", check], cwd=work, env=env)
        for fixture in sorted((ROOT / "examples").glob("*.json")):
            run(
                [str(python), "-I", "-m", "equiframe", "contract", "validate", str(fixture)],
                cwd=work,
                env=env,
            )
        cli = runtime / ("Scripts/equiframe.exe" if os.name == "nt" else "bin/equiframe")
        run(
            [str(cli), "contract", "validate", str(ROOT / "examples" / "dates.json")],
            cwd=work,
            env=env,
        )
        source_dir = work / "sdist"
        source_dir.mkdir()
        with tarfile.open(sdist, "r:gz") as archive:
            archive.extractall(source_dir, filter="data")
        source = next(source_dir.iterdir())
        for path in (
            "pyproject.toml",
            "uv.lock",
            "src/equiframe/py.typed",
            "tests/test_contracts.py",
            "examples/dates.json",
            "schemas/contract-1.0.schema.json",
        ):
            if not (source / path).is_file():
                raise RuntimeError("sdist is missing " + path)
        # Rebuild from the sdist with the same locked backend and compare all wheel bytes.
        source_env = dict(env, UV_PROJECT_ENVIRONMENT=str(work / "source-build"))
        run(
            [uv, "sync", "--locked", "--no-install-project", "--python", sys.executable],
            cwd=source,
            env=source_env,
        )
        source_python = (
            work / "source-build" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        run(
            [str(source_python), "-m", "build", "--wheel", "--no-isolation"],
            cwd=source,
            env=source_env,
        )
        rebuilt = next((source / "dist").glob("*.whl"))
        if rebuilt.read_bytes() != wheel.read_bytes():
            raise RuntimeError("wheel rebuilt from sdist is not byte reproducible")
    print("Verified clean wheel installation, CLI, sdist contents and reproducible wheel rebuild")


if __name__ == "__main__":
    main()
