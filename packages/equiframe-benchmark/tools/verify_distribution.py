"""Verify both installed distributions, native pilot and the integration example."""

import argparse
import hashlib
import os
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def stage_installed_test_inputs(package: Path, work: Path) -> None:
    """Copy the fixed shipped inputs required by the installed test suite."""
    for name in ("tests", "examples", "schemas"):
        shutil.copytree(package / name, work / name, ignore=shutil.ignore_patterns("__pycache__"))
    tools = work / "tools"
    tools.mkdir()
    for name in ("generate_assets.py", "generate_assets_v2.py", "verify_distribution.py"):
        shutil.copy2(package / "tools" / name, tools / name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    parser.add_argument(
        "--qa-workspace", type=Path, help="Temporary workspace outside the checkout."
    )
    args = parser.parse_args()
    uv = shutil.which(args.uv)
    if uv is None:
        raise SystemExit("uv must be on PATH")
    core = (
        ROOT
        / tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["tool"]["uv"]["sources"][
            "equiframe"
        ]["path"]
    ).resolve()
    repository = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=ROOT, text=True
        ).strip()
    ).resolve()
    version = runpy.run_path(str(core / "tools" / "release_version.py"))["project_version"]
    package_version = version(ROOT, require_tag=True)
    core_version = version(core, require_tag=True)
    wheel = ROOT / "dist" / f"equiframe_benchmark-{package_version}-py3-none-any.whl"
    core_wheel = core / "dist" / f"equiframe-{core_version}-py3-none-any.whl"
    sdist = ROOT / "dist" / f"equiframe_benchmark-{package_version}.tar.gz"
    for artifact in (wheel, core_wheel, sdist):
        if not artifact.is_file():
            raise SystemExit("build both distributions first: " + artifact.name)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)
    workspace = args.qa_workspace.resolve() if args.qa_workspace is not None else None
    if workspace is not None:
        if workspace.is_relative_to(repository):
            parser.error("QA workspace must be outside the checkout")
        workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="equiframe-benchmark-check-", dir=workspace
    ) as temporary:
        work = Path(temporary).resolve()
        cache = Path(env.get("UV_CACHE_DIR", str(work / "cache" / "uv"))).resolve()
        if cache.is_relative_to(repository):
            parser.error("QA cache must be outside the checkout")
        scratch = work / "temporary"
        scratch.mkdir()
        env.update(
            UV_CACHE_DIR=str(cache),
            TMPDIR=str(scratch),
            TMP=str(scratch),
            TEMP=str(scratch),
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            HYPOTHESIS_STORAGE_DIRECTORY=str(work / "hypothesis"),
        )
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
                str(core / "dist"),
                "--find-links",
                str(ROOT / "dist"),
                f"equiframe=={core_version}",
                f"equiframe-benchmark=={package_version}",
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
assert callable(eb.oracle_verification_bridge)
assert callable(eb.evaluate_pairwise)
assert callable(ef.verify) and callable(ef.read_bundle)
assert not any(n in sys.modules for n in ('pyarrow','pandas','polars','duckdb','numpy','sklearn'))
for module in (ef, eb):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert not Path.cwd().is_relative_to(Path(sys.argv[1]))
assert importlib.metadata.version('equiframe-benchmark') == sys.argv[2]
assert importlib.metadata.version('equiframe') == sys.argv[3]
"""
        run(
            [str(python), "-I", "-c", check, str(repository), package_version, core_version],
            work,
            env,
        )
        stage_installed_test_inputs(ROOT, work)
        sources = work / "declared-source-packages"
        for project in (core, ROOT):
            metadata = tomllib.loads((project / "pyproject.toml").read_text("utf-8"))["project"]
            target = sources / metadata["name"]
            target.mkdir(parents=True)
            for name in ("pyproject.toml", "uv.lock", "README.md"):
                shutil.copy2(project / name, target / name)
            readme = metadata["readme"]
            if readme != "README.md":
                shutil.copy2(project / readme, target / readme)
            for pattern in metadata.get("license-files", []):
                for path in project.glob(pattern):
                    if (
                        path.is_symlink()
                        or not path.is_file()
                        or not path.resolve().is_relative_to(project.resolve())
                    ):
                        raise RuntimeError("declared license source is not a regular package file")
                    destination = target / path.relative_to(project)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
            shutil.copytree(
                project / "src", target / "src", ignore=shutil.ignore_patterns("__pycache__")
            )
        env["EQUIFRAME_TEST_SOURCE_PACKAGES"] = str(sources)
        run(
            [
                str(python),
                "-I",
                "-m",
                "pytest",
                "-q",
                "-x",
                "--tb=short",
                "-p",
                "no:cacheprovider",
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
        example = work / "integration_local.py"
        shutil.copy2(ROOT / "examples" / "integration_local.py", example)
        run(
            [str(python), "-I", str(example), "--output", str(work / "integration-example")],
            work,
            env,
        )
        evaluation = work / "evaluation_local.py"
        shutil.copy2(ROOT / "examples" / "evaluation_local.py", evaluation)
        run(
            [str(python), "-I", str(evaluation), "--output", str(work / "evaluation-example")],
            work,
            env,
        )
        scaling = work / "scale_local.py"
        shutil.copy2(ROOT / "examples" / "scale_local.py", scaling)
        run(
            [str(python), "-I", str(scaling), "--output", str(work / "scale-example")],
            work,
            env,
        )
        extracted = work / "sdist"
        with tarfile.open(sdist) as archive:
            archive.extractall(extracted, filter="data")
        project = next(extracted.iterdir())
        run([sys.executable, "-m", "build", "--no-isolation"], project, env)
        rebuilt = project / "dist" / wheel.name
        if (
            hashlib.sha256(rebuilt.read_bytes()).digest()
            != hashlib.sha256(wheel.read_bytes()).digest()
        ):
            raise RuntimeError("sdist did not reproduce the same wheel bytes")
        if (project / "dist" / sdist.name).read_bytes() != sdist.read_bytes():
            raise RuntimeError("sdist did not reproduce the same sdist bytes")
        print(
            "pip installation, installed tests, native pilot, integration/evaluation examples "
            "scale example and identical sdist rebuild verified"
        )


if __name__ == "__main__":
    main()
