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
        api_check = """
from pathlib import Path
import sys
from equiframe import (
    canonical_contract_bytes, contract_fingerprint, read_contract,
    validate_contract, write_contract,
)
for source in sorted(Path(sys.argv[1]).glob('*.json')):
    contract = read_contract(source)
    wire = canonical_contract_bytes(contract)
    assert validate_contract(wire) == contract
    target = Path('roundtrip.json')
    write_contract(contract, target)
    assert target.read_bytes() == wire
    assert contract_fingerprint(read_contract(target)) == contract_fingerprint(contract)
print('Installed wheel API roundtrips all five fixtures exactly')
"""
        run([str(python), "-I", "-c", api_check, str(ROOT / "examples")], cwd=work, env=env)
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
        invalid = work / "invalid.json"
        unsupported = work / "unsupported.json"
        invalid.write_text("{", encoding="utf-8")
        unsupported.write_text('{"schema_version":"99.0"}', encoding="utf-8")
        for arguments, expected, code in (
            ([str(invalid)], 2, "json_syntax"),
            ([str(unsupported)], 2, "unsupported_schema_version"),
            ([str(work / "missing.json")], 3, "cannot read contract file"),
            ([], 2, "Missing argument"),
        ):
            result = subprocess.run(
                [str(cli), "contract", "validate", *arguments],
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != expected or code not in result.stderr:
                raise RuntimeError(
                    "installed CLI returned an incorrect diagnostic: " + result.stderr
                )
            if "Traceback" in result.stderr or result.stdout:
                raise RuntimeError(
                    "installed CLI exposed a traceback or reported success on failure"
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
        run(
            [uv, "pip", "install", "--python", str(source_python), "--no-deps", str(rebuilt)],
            cwd=work,
            env=source_env,
        )
        # Run the shipped tests against installed site-packages, without an editable src checkout.
        location_check = """
from pathlib import Path
import sys
import equiframe
assert Path(equiframe.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
"""
        run([str(source_python), "-I", "-c", location_check], cwd=source, env=source_env)
        run(
            [str(source_python), "-I", "tools/generate_assets.py", "--check"],
            cwd=source,
            env=source_env,
        )
        run([str(source_python), "-I", "-m", "pytest", "-q"], cwd=source, env=source_env)
        consumer = work / "typed_consumer.py"
        consumer.write_text(
            "from pathlib import Path\n"
            "from equiframe import ArtifactRef, ArtifactStore, Contract, read_contract, "
            "canonical_contract_bytes, validate_contract, contract_fingerprint\n"
            "def roundtrip(path: Path) -> tuple[Contract, str]:\n"
            "    contract = read_contract(path)\n"
            "    restored = validate_contract(canonical_contract_bytes(contract))\n"
            "    return restored, contract_fingerprint(restored)\n"
            "def publish(store: ArtifactStore, path: Path) -> ArtifactRef:\n"
            "    return store.put(path, media_type='application/json')\n",
            encoding="utf-8",
        )
        run(
            [str(source_python), "-I", "-m", "mypy", "--strict", str(consumer)],
            cwd=work,
            env=source_env,
        )
    print(
        "Verified installed wheel API/CLI, typed consumer, sdist tests and byte-identical rebuild"
    )


if __name__ == "__main__":
    main()
