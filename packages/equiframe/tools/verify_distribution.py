"""Verify built wheel/sdist using a clean runtime-only locked environment."""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
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


def verify_extras(uv: str, wheel: Path, work: Path, env: dict[str, str]) -> None:
    for extra in ("arrow", "pandas", "polars", "duckdb", "engines", "ml"):
        project = work / ("consumer-" + extra)
        project.mkdir()
        environment = project / ".venv"
        profile_env = dict(env, UV_PROJECT_ENVIRONMENT=str(environment))
        run(
            [
                uv,
                "sync",
                "--locked",
                "--no-dev",
                "--no-install-project",
                "--extra",
                extra,
                "--python",
                sys.executable,
            ],
            cwd=ROOT,
            env=profile_env,
        )
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(
            [uv, "pip", "install", "--python", str(python), "--no-index", f"{wheel}[{extra}]"],
            cwd=project,
            env=profile_env,
        )
        run([uv, "pip", "check", "--python", str(python)], cwd=project, env=profile_env)
        check = r"""
import importlib.util, sys
from pathlib import Path
import equiframe as ef
assert Path(ef.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert not Path.cwd().resolve().is_relative_to(Path(sys.argv[2]).resolve())
assert not any(n in sys.modules for n in ('pandas','polars','duckdb','numpy','pyarrow','sklearn'))
extra=sys.argv[1]
for engine in ('pandas','polars','duckdb'):
    assert (importlib.util.find_spec(engine) is not None)==(extra in (engine,'engines'))
assert (importlib.util.find_spec('sklearn') is not None) == (extra == 'ml')
print('Clean installed profile:',extra,'outside checkout; light import verified')
"""
        run([str(python), "-I", "-c", check, extra, str(ROOT)], cwd=project, env=profile_env)
        if extra == "ml":
            example = project / "detectors_local.py"
            shutil.copyfile(ROOT / "examples" / "detectors_local.py", example)
            bundle = project / "detectors.json"
            run(
                [str(python), "-I", str(example), "--bundle", str(bundle)],
                cwd=project,
                env=profile_env,
            )
            base_python = (
                work / "runtime" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            )
            run(
                [str(base_python), "-I", str(example), "--bundle", str(bundle), "--restore-only"],
                cwd=project,
                env=profile_env,
            )
            continue
        comparison_example = project / "compare_local.py"
        shutil.copyfile(ROOT / "examples" / "compare_local.py", comparison_example)
        run([str(python), "-I", str(comparison_example)], cwd=project, env=profile_env)
        diff_example = project / "diff_local.py"
        shutil.copyfile(ROOT / "examples" / "diff_local.py", diff_example)
        direct_engines = (
            ("arrow", "pandas", "polars")
            if extra == "engines"
            else (extra if extra in ("pandas", "polars") else "arrow",)
        )
        for direct_engine in direct_engines:
            run(
                [str(python), "-I", str(diff_example), "--engine", direct_engine],
                cwd=project,
                env=profile_env,
            )
        report_example = project / "report_local.py"
        shutil.copyfile(ROOT / "examples" / "report_local.py", report_example)
        run(
            [str(python), "-I", str(report_example), "--output", str(project / "reports")],
            cwd=project,
            env=profile_env,
        )
        base_python = work / "runtime" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(
            [
                str(base_python),
                "-I",
                str(report_example),
                "--render-only",
                str(project / "reports" / "detail" / "report.json"),
            ],
            cwd=project,
            env=profile_env,
        )
        if extra == "arrow":
            verify_example = project / "verify_generic.py"
            shutil.copyfile(ROOT / "examples" / "verify_generic.py", verify_example)
            run(
                [str(python), "-I", str(verify_example), "--output", str(project / "verify-runs")],
                cwd=project,
                env=profile_env,
            )
            arrow_check = r"""
from pathlib import Path
import pyarrow as pa
import equiframe as ef
path=Path('table.arrow')
table=pa.table({'id':['001','001']})
with path.open('wb') as output, pa.ipc.new_file(output,table.schema) as writer:
    writer.write_table(table)
ref=ef.LocalArtifactStore(Path('store')).put(path,media_type='application/vnd.apache.arrow.file')
assert ef.read_table(ref).to_pylist()==[{'id':'001'},{'id':'001'}]
"""
            run([str(python), "-I", "-c", arrow_check], cwd=project, env=profile_env)
            rule_example = project / "rules_catalog.py"
            shutil.copyfile(ROOT / "examples" / "rules_catalog.py", rule_example)
            shutil.copytree(ROOT / "examples" / "rules", project / "rules")
            for fixture in (ROOT / "examples").glob("*.json"):
                shutil.copyfile(fixture, project / fixture.name)
            run(
                [str(python), "-I", str(rule_example), "--work-dir", str(project / "rule-runs")],
                cwd=project,
                env=profile_env,
            )
            reader_example = project / "rules_from_run.py"
            shutil.copyfile(ROOT / "examples" / "rules_from_run.py", reader_example)
            captured = next((project / "rule-runs").glob("nulls_types_*/run.json"))
            run(
                [
                    str(python),
                    "-I",
                    str(reader_example),
                    str(captured),
                    "--work-dir",
                    str(project / "rule-reader-runs"),
                ],
                cwd=project,
                env=profile_env,
            )
            profile_example = project / "profiles_from_run.py"
            shutil.copyfile(ROOT / "examples" / "profiles_from_run.py", profile_example)
            shutil.copytree(ROOT / "examples" / "profiles", project / "profiles")
            for family in ("nulls_types", "joins", "duplicates_order", "aggregations", "dates"):
                capture = next((project / "rule-runs").glob(family + "_*/run.json"))
                run(
                    [
                        str(python),
                        "-I",
                        str(profile_example),
                        str(capture),
                        str(project / "profiles" / (family + ".json")),
                        "--work-dir",
                        str(project / ("profiles-" + family)),
                    ],
                    cwd=project,
                    env=profile_env,
                )
            fitted_example = project / "preprocess_profiles.py"
            shutil.copyfile(ROOT / "examples" / "preprocess_profiles.py", fitted_example)
            training_profile = next((project / "profiles-nulls_types").glob("*/profile.json"))
            selection = project / "synthetic-selection.json"
            selection.write_text(
                '{"purpose":"normal_training","status":"synthetic API demonstration",'
                '"source":"rules_catalog.py/nulls_types"}',
                encoding="utf-8",
            )
            run(
                [
                    str(python),
                    "-I",
                    str(fitted_example),
                    "--training",
                    str(training_profile),
                    "--selection-manifest",
                    str(selection),
                    "--score",
                    str(training_profile),
                    "--output",
                    str(project / "preprocessor.json"),
                ],
                cwd=project,
                env=profile_env,
            )
        else:
            example = project / "execute_native.py"
            shutil.copyfile(ROOT / "examples" / "execute_native.py", example)
            command = [str(python), "-I", str(example), "--work-dir", str(project / "runs")]
            if extra != "engines":
                command += ["--engine", extra]
            run(command, cwd=project, env=profile_env)
            if extra == "engines":
                for name in ("retail_etl.py", "sercop_etl.py"):
                    shutil.copyfile(ROOT / "examples" / name, project / name)
                shutil.copytree(ROOT / "examples" / "sercop_offline", project / "sercop_offline")
                run(
                    [
                        str(python),
                        "-I",
                        str(project / "retail_etl.py"),
                        "--output",
                        str(project / "retail-etl"),
                    ],
                    cwd=project,
                    env=profile_env,
                )
                run(
                    [
                        str(python),
                        "-I",
                        str(project / "sercop_etl.py"),
                        "--snapshot",
                        str(project / "sercop_offline"),
                        "--expected",
                        str(project / "sercop_offline/expected.json"),
                        "--output",
                        str(project / "sercop-etl"),
                    ],
                    cwd=project,
                    env=profile_env,
                )
                migrated_example = project / "migrate_native.py"
                shutil.copyfile(ROOT / "examples" / "migrate_native.py", migrated_example)
                run(
                    [
                        str(python),
                        "-I",
                        str(migrated_example),
                        "--output",
                        str(project / "migration-runs"),
                    ],
                    cwd=project,
                    env=profile_env,
                )
            if extra == "duckdb":
                pipeline_example = project / "pipeline_local.py"
                shutil.copyfile(ROOT / "examples" / "pipeline_local.py", pipeline_example)
                shutil.copyfile(
                    ROOT / "examples" / "duplicates_order.json", project / "duplicates_order.json"
                )
                run(
                    [
                        str(python),
                        "-I",
                        str(pipeline_example),
                        "--output",
                        str(project / "pipeline-runs"),
                    ],
                    cwd=project,
                    env=profile_env,
                )
                minimum = (
                    (ROOT / "README.md")
                    .read_text(encoding="utf-8")
                    .split("```python\n", 1)[1]
                    .split("```", 1)[0]
                )
                minimal_script = project / "readme_example.py"
                minimal_script.write_text(minimum, encoding="utf-8")
                run([str(python), "-I", str(minimal_script)], cwd=project, env=profile_env)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args()
    uv = shutil.which(args.uv)
    if uv is None:
        parser.error("uv executable not found; use --uv /absolute/path/to/uv")
    package_version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    wheel = single(f"equiframe-{package_version}-*.whl")
    sdist = single(f"equiframe-{package_version}.tar.gz")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        if "equiframe/py.typed" not in names or "equiframe/__init__.py" not in names:
            raise RuntimeError("wheel is missing typed public package files")
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="equiframe-distribution-") as directory:
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
assert equiframe.__version__ == importlib.metadata.version('equiframe') == sys.argv[1]
for name in ('pandas', 'polars', 'duckdb', 'sklearn', 'numpy', 'pyarrow',
             'pytest', 'hypothesis', 'IPython', 'jupyter'):
    assert importlib.util.find_spec(name) is None, name
print('Installed wheel imports from clean site-packages without engines/ML/dev tools')
assert equiframe.ComparisonOptions().batch_rows > 0
assert callable(equiframe.compare) and callable(equiframe.iter_differences)
assert callable(equiframe.evaluate_rules) and callable(equiframe.iter_rule_findings)
assert callable(equiframe.profile_execution) and callable(equiframe.fit_preprocessor)
assert callable(equiframe.transform_profiles) and callable(equiframe.read_preprocessor)
assert callable(equiframe.run_pipeline) and callable(equiframe.read_pipeline)
assert callable(equiframe.reduce_case) and callable(equiframe.inspect_evidence)
assert callable(equiframe.migrate) and callable(equiframe.read_migration)
assert callable(equiframe.check_migration) and callable(equiframe.native_compiler_registry)
assert callable(equiframe.verify) and callable(equiframe.verify_migration)
assert callable(equiframe.read_verification) and callable(equiframe.export_bundle)
assert callable(equiframe.read_bundle) and callable(equiframe.import_bundle)
assert callable(equiframe.ingest_file) and callable(equiframe.run_workflow)
assert callable(equiframe.read_workflow) and callable(equiframe.ParquetDestination)
"""
        run([str(python), "-I", "-c", check, package_version], cwd=work, env=env)
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
        verify_extras(uv, wheel, work, env)
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
            "examples/rules/catalog-1.0.json",
            "examples/rules_catalog.py",
            "examples/rules_from_run.py",
            "schemas/contract-1.0.schema.json",
            "schemas/rule-evaluation-1.0.schema.json",
            "schemas/profile-result-1.0.schema.json",
            "schemas/preprocessor-bundle-1.0.schema.json",
            "examples/profiles/nulls_types.json",
            "examples/profiles_from_run.py",
            "examples/preprocess_profiles.py",
            "examples/detectors_local.py",
            "schemas/detector-bundle-1.0.schema.json",
            "schemas/pipeline-result-1.0.schema.json",
            "schemas/reduction-result-1.0.schema.json",
            "examples/pipeline_local.py",
            "examples/verify_generic.py",
            "examples/retail_etl.py",
            "examples/sercop_etl.py",
            "examples/sercop_offline/snapshot.json",
            "schemas/verification-request-1.0.schema.json",
            "schemas/verification-result-1.0.schema.json",
            "schemas/evidence-bundle-1.0.schema.json",
            "schemas/workflow-request-1.0.schema.json",
            "schemas/workflow-result-1.0.schema.json",
            "schemas/ingestion-spec-1.0.schema.json",
            "schemas/load-receipt-1.0.schema.json",
            "tools/release_manifest.py",
        ):
            if not (source / path).is_file():
                raise RuntimeError("sdist is missing " + path)
        # Rebuild from the sdist with the same locked backend and compare all wheel bytes.
        source_env = dict(env, UV_PROJECT_ENVIRONMENT=str(work / "source-build"))
        run(
            [
                uv,
                "sync",
                "--locked",
                "--all-extras",
                "--no-install-project",
                "--python",
                sys.executable,
            ],
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
            "    return store.put(path, media_type='application/json')\n"
            "import equiframe as ef\n"
            "def execute(\n"
            "    plan: ef.ExecutionPlan, source: ef.DataSource,\n"
            "    registry: ef.TransformationRegistry,\n"
            ") -> ef.ExecutionResult:\n"
            "    return ef.execute(plan, source=source, registry=registry)\n"
            "def compare(a: ef.ArtifactRef, b: ef.ExecutionResult, "
            "contract: ef.Contract) -> ef.ComparisonResult:\n"
            "    options = ef.ComparisonOptions(batch_rows=2)\n"
            "    return ef.compare(a, b, contract=contract, options=options)\n"
            "def direct(a: ef.DiffInput, b: ef.DiffInput) -> ef.ComparisonResult:\n"
            "    result = ef.diff(a, b, keys=['id'], "
            "capture_options=ef.DiffCaptureOptions(max_rows=100))\n"
            "    declaration: ef.DiffContract = ef.read_diff_contract(result)\n"
            "    return ef.diff(a, b, contract=declaration)\n"
            "def builders(columns: tuple[ef.ColumnSpec, ...], "
            "order: tuple[ef.SortSpec, ...]) -> tuple[ef.DiffContract, ...]:\n"
            "    return (ef.bag_contract(columns), ef.keyed_contract(columns, keys=['id']), "
            "ef.sequence_contract(columns, by=order))\n"
            "def presentation(result: ef.ComparisonResult) -> tuple[ef.ComparisonReport, str]:\n"
            "    report = ef.comparison_report(result, options=ef.ReportOptions())\n"
            "    return report, report.to_html()\n"
            "import pandas as pd\n"
            "import polars as pl\n"
            "import pyarrow as pa\n"
            "def native_diff(a: pd.DataFrame, b: pl.DataFrame) -> ef.ComparisonResult:\n"
            "    declaration = ef.infer_diff_contract(pa.schema([('id', pa.int64())]), "
            "keys=['id'])\n"
            "    return ef.diff(a, b, contract=declaration)\n"
            "def profile(run: ef.ExecutionResult, spec: ef.ProfileSpec) -> ef.ProfileResult:\n"
            "    return ef.profile_execution(run, spec=spec)\n"
            "def matrix(training: ef.NormalTrainingProfiles, spec: ef.ProfileSpec, "
            "profiles: tuple[ef.ProfileVector, ...]) -> ef.FeatureMatrix:\n"
            "    bundle = ef.fit_preprocessor(training, spec=spec)\n"
            "    return ef.transform_profiles(bundle, profiles)\n"
            "def migration(spec: ef.MigrationSpec, source: ef.DataSource) -> ef.MigrationResult:\n"
            "    return ef.migrate(spec, source=source)\n"
            "def migration_read(path: Path) -> ef.MigrationResult:\n"
            "    return ef.read_migration(path)\n"
            "def verify_external(ref: ef.ArtifactRef, contract: ef.Contract) "
            "-> ef.VerificationResult:\n"
            "    return ef.verify({'external': ref}, contract=contract)\n"
            "def ingest(path: Path, spec: ef.IngestionSpec, root: Path) "
            "-> ef.IngestionResult:\n"
            "    return ef.ingest_file(path, spec=spec, work_dir=root)\n"
            "def workflow(spec: ef.WorkflowSpec, source: ef.DataSource, root: Path) "
            "-> ef.WorkflowResult:\n"
            "    return ef.run_workflow(spec, source=source, work_dir=root)\n"
            "def load(destination: ef.Destination, ref: ef.ArtifactRef, "
            "report: ef.VerificationResult) -> ef.LoadReceipt:\n"
            "    return destination.publish({'table': ref}, run_id='consumer', "
            "verifications={'table': report})\n"
            "def bundle(source: Path, destination: Path) -> ef.EvidenceBundle:\n"
            "    return ef.export_bundle(source, destination)\n",
            encoding="utf-8",
        )
        run(
            [
                str(source_python),
                "-I",
                "-m",
                "mypy",
                "--strict",
                "--config-file",
                str(source / "pyproject.toml"),
                str(consumer),
            ],
            cwd=work,
            env=source_env,
        )
    print(
        "Verified base/extras outside checkout, API/CLI, typed consumer, "
        "sdist tests and byte-identical wheel rebuild"
    )


if __name__ == "__main__":
    main()
