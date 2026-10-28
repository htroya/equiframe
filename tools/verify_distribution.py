"""Verify built wheel/sdist using a clean runtime-only locked environment."""

import argparse
import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

from release_manifest import repository_root
from verify_first_use import verify_first_use

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    subprocess.run(args, cwd=cwd, env=env, check=True)


def typed_consumer_command(python: Path, config: Path, consumer: Path) -> list[str]:
    """Check against the actual installed consumer interpreter, retaining strict mode."""
    probe = subprocess.run(
        [str(python), "-I", "-c", "import sys; print('.'.join(map(str, sys.version_info[:2])))"],
        capture_output=True,
        text=True,
        check=True,
    )
    minor = probe.stdout.strip()
    if minor not in {"3.10", "3.11", "3.12", "3.13"}:
        raise RuntimeError("typed consumer interpreter is outside the committed Python matrix")
    return [
        str(python),
        "-I",
        "-m",
        "mypy",
        "--strict",
        "--python-version",
        minor,
        "--config-file",
        str(config),
        str(consumer),
    ]


def single(pattern: str) -> Path:
    paths = tuple((ROOT / "dist").glob(pattern))
    if len(paths) != 1:
        raise RuntimeError("expected one built artifact matching " + pattern)
    return paths[0]


def readme_consumer_script(readme: str) -> str:
    """Execute the three literal blocks with files and independent assertions."""
    blocks = [part.split("```", 1)[0] for part in readme.split("```python\n")[1:]]
    if (
        len(blocks) != 3
        or 'ef.load_dataset("orders.json")' not in blocks[0]
        or 'ef.load_dataset("orders.parquet"' not in blocks[1]
        or "ef.diff(" not in blocks[2]
    ):
        raise RuntimeError("README examples changed; review the installed consumer assertions")
    fixtures = """
import json as _qa_json
from pathlib import Path as _qa_Path
import pyarrow as _qa_pa
import pyarrow.parquet as _qa_pq
_qa_rows = [{"id": f"{i:06d}", "amount": (i % 997) - 498} for i in range(30000)]
_qa_Path("orders.json").write_text(_qa_json.dumps(_qa_rows), encoding="utf-8")
_qa_pq.write_table(_qa_pa.Table.from_pylist(_qa_rows), "orders.parquet")
"""
    loaded = """
assert pandas_df.to_dict(orient="records") == _qa_rows
assert polars_df.to_dicts() == _qa_rows
assert loaded.info.rows == converted.info.rows == 30000
assert converted.target == "duckdb"
"""
    parquet = """
assert polars_df.to_dicts() == _qa_rows
assert loaded.info.rows == 30000 and loaded.target == "polars"
"""
    comparison = """
assert result.state == "different" and result.complete
_qa_changes = tuple(ef.iter_differences(result.differences))
assert len(_qa_changes) == 1 and _qa_changes[0].column == "amount"
assert _qa_changes[0].key[0].value == "2"
assert _qa_changes[0].left[0].value == "200" and _qa_changes[0].right[0].value == "201"
try:
    ef.assert_equivalent(result)
except ef.EquivalenceAssertionError as _qa_error:
    assert _qa_error.code == "different"
else:
    raise AssertionError("README regression was accepted")
print("Three literal README blocks verified: JSON/Parquet 30000 rows and value 200 -> 201")
"""
    return fixtures + blocks[0] + loaded + blocks[1] + parquet + blocks[2] + comparison


def sync_consumer(
    uv: str, wheel: Path, work: Path, env: dict[str, str], *, extra: str | None
) -> None:
    """Replace the actual consumer profile in one sequential environment."""
    command = [uv, "sync", "--locked", "--no-dev", "--no-install-project"]
    if extra is not None:
        command += ["--extra", extra]
    command += ["--python", sys.executable]
    run(command, cwd=ROOT, env=env)
    python = work / "runtime" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    requirement = str(wheel) + (f"[{extra}]" if extra is not None else "")
    run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            "--no-index",
            "--reinstall-package",
            "equiframe",
            requirement,
        ],
        cwd=work,
        env=env,
    )
    run([uv, "pip", "check", "--python", str(python)], cwd=work, env=env)


def run_base_consumer(
    arguments: list[str],
    *,
    uv: str,
    wheel: Path,
    work: Path,
    extra: str,
    cwd: Path,
    env: dict[str, str],
) -> None:
    """Read produced evidence with optional packages genuinely uninstalled.

    No consumer processes overlap a sync. Restore the selected native profile
    before its next subprocess; the absence assertions in the reader remain
    unchanged and use normal Python discovery.
    """
    sync_consumer(uv, wheel, work, env, extra=None)
    try:
        run(arguments, cwd=cwd, env=env)
    finally:
        sync_consumer(uv, wheel, work, env, extra=extra)


def verify_extras(uv: str, wheel: Path, work: Path, env: dict[str, str]) -> None:
    for extra in ("arrow", "pandas", "polars", "duckdb", "engines", "files", "ml"):
        project = work / ("consumer-" + extra)
        project.mkdir()
        environment = work / "runtime"
        profile_env = dict(env, UV_PROJECT_ENVIRONMENT=str(environment))
        sync_consumer(uv, wheel, work, profile_env, extra=extra)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        check = r"""
import importlib.util, sys
from pathlib import Path
import equiframe as ef
assert Path(ef.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert not Path.cwd().resolve().is_relative_to(Path(sys.argv[2]).resolve())
assert not any(n in sys.modules for n in (
    'pandas','polars','duckdb','numpy','pyarrow','sklearn','openpyxl','xlrd','defusedxml'))
extra=sys.argv[1]
for engine in ('pandas','polars','duckdb'):
    expected = extra in (engine, 'engines') or (extra == 'files' and engine == 'pandas')
    assert (importlib.util.find_spec(engine) is not None) == expected
for reader in ('openpyxl', 'xlrd', 'defusedxml'):
    assert (importlib.util.find_spec(reader) is not None) == (extra == 'files')
assert (importlib.util.find_spec('sklearn') is not None) == (extra == 'ml')
print('Clean installed profile:',extra,'outside checkout; light import verified')
"""
        run([str(python), "-I", "-c", check, extra, str(ROOT)], cwd=project, env=profile_env)
        if extra == "files":
            # This reader profile is not an execution engine. A single bounded
            # installed consumer covers its wiring without passing --engine files
            # to the independent native-transform examples below.
            files_check = r"""
import hashlib
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
import equiframe as ef
source = Path('dataset.json')
raw = b'[{"id":"001","amount":12.30}]'
source.write_bytes(raw)
with ef.load_dataset(source) as dataset:
    assert dataset.target == 'pandas'
    assert dataset.pandas['id'].tolist() == ['001']
    assert dataset.pandas['amount'].tolist() == [Decimal('12.30')]
    assert dataset.provenance is not None
    assert dataset.provenance.source.sha256 == hashlib.sha256(raw).hexdigest()
    assert dataset.provenance.source.size_bytes == len(raw)
    assert 'provenance' not in dataset.info.to_dict()
    dataset.to_parquet('dataset-copy.parquet')
assert ef.inspect_dataset('dataset-copy.parquet').rows == 1
assert files('equiframe').joinpath('_r_review.R').read_text(encoding='utf-8').strip()
print('Installed files reader profile: bounded loading, provenance and export')
"""
            run([str(python), "-I", "-c", files_check], cwd=project, env=profile_env)
            continue
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
            run_base_consumer(
                [str(base_python), "-I", str(example), "--bundle", str(bundle), "--restore-only"],
                uv=uv,
                wheel=wheel,
                work=work,
                extra=extra,
                cwd=project,
                env=profile_env,
            )
            continue
        if extra in ("duckdb", "engines"):
            snapshot_example = project / "snapshot_source.py"
            shutil.copyfile(ROOT / "examples" / "snapshot_source.py", snapshot_example)
            run(
                [str(python), "-I", str(snapshot_example), "--output", str(project / "snapshot")],
                cwd=project,
                env=profile_env,
            )
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
        if extra in ("duckdb", "engines"):
            capture_example = project / "capture_duckdb.py"
            shutil.copyfile(ROOT / "examples" / "capture_duckdb.py", capture_example)
            run(
                [
                    str(python),
                    "-I",
                    str(capture_example),
                    "--output",
                    str(project / "duckdb-capture-report"),
                ],
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
        run_base_consumer(
            [
                str(base_python),
                "-I",
                str(report_example),
                "--render-only",
                str(project / "reports" / "detail" / "report.json"),
            ],
            uv=uv,
            wheel=wheel,
            work=work,
            extra=extra,
            cwd=project,
            env=profile_env,
        )
        assertion_example = project / "assertion_ci.py"
        shutil.copyfile(ROOT / "examples" / "assertion_ci.py", assertion_example)
        assertion_engines = (
            ("arrow", "pandas", "polars", "duckdb")
            if extra == "engines"
            else (extra if extra in ("pandas", "polars", "duckdb") else "arrow",)
        )
        for engine in assertion_engines:
            for scenario, expected_exit in (
                ("equivalent", 0),
                ("different", 1),
                ("not_evaluable", 3),
            ):
                destination = project / f"assertion-{engine}-{scenario}"
                private = project / f"private-{engine}-{scenario}"
                completed = subprocess.run(
                    [
                        str(python),
                        "-I",
                        str(assertion_example),
                        "--case",
                        scenario,
                        "--engine",
                        engine,
                        "--output",
                        str(destination),
                        "--work-dir",
                        str(private),
                    ],
                    cwd=project,
                    env=profile_env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if completed.returncode != expected_exit:
                    raise RuntimeError(
                        f"installed assertion recipe {engine}/{scenario} returned "
                        f"{completed.returncode}, expected {expected_exit}: {completed.stderr}"
                    )
                if "Traceback" in completed.stdout + completed.stderr:
                    raise RuntimeError("installed assertion recipe exposed a traceback")
                print(f"Installed assertion recipe {engine}/{scenario}: exit {expected_exit}")
                consumer_check = r"""
import importlib.util, sys
from pathlib import Path
import equiframe as ef
private, report, scenario = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
assert {p.name for p in report.iterdir()} == {
    'report.json', 'report.txt', 'report.html', 'evidence-manifest.json'}
result, = [ef.read_comparison(p) for p in private.glob('*/comparison.json')]
decision = ef.equivalence_decision(result,
    policy=ef.EquivalencePolicy(require_persisted_evidence=True), evidence_root=private)
assert decision.state == scenario and decision.accepted == (scenario == 'equivalent')
assert decision.evidence_status == 'verified'
assert ef.EquivalenceDecision.model_validate_json(decision.model_dump_json()) == decision
try:
    ef.assert_equivalent(result)
except ef.EquivalenceAssertionError as error:
    assert scenario != 'equivalent' and error.code == scenario
else:
    assert scenario == 'equivalent'
for name in ('pyarrow', 'pandas', 'polars', 'duckdb', 'numpy', 'sklearn', 'pytest'):
    assert importlib.util.find_spec(name) is None, name
print('Base-only installed assertion consumer:', scenario)
"""
                run_base_consumer(
                    [
                        str(base_python),
                        "-I",
                        "-c",
                        consumer_check,
                        str(private),
                        str(destination),
                        scenario,
                    ],
                    uv=uv,
                    wheel=wheel,
                    work=work,
                    extra=extra,
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
            if extra == "engines":
                minimum = readme_consumer_script(
                    (ROOT / "README.en.md").read_text(encoding="utf-8")
                )
                minimal_script = project / "readme_example.py"
                minimal_script.write_text(minimum, encoding="utf-8")
                run([str(python), "-I", str(minimal_script)], cwd=project, env=profile_env)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    parser.add_argument(
        "--qa-workspace", type=Path, help="Temporary workspace outside the checkout."
    )
    args = parser.parse_args()
    uv = shutil.which(args.uv)
    if uv is None:
        parser.error("uv executable not found; use --uv /absolute/path/to/uv")
    package_version = runpy.run_path(str(Path(__file__).with_name("release_version.py")))[
        "project_version"
    ](ROOT, require_tag=True)
    wheel = single(f"equiframe-{package_version}-*.whl")
    sdist = single(f"equiframe-{package_version}.tar.gz")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        required = {
            "equiframe/py.typed",
            "equiframe/__init__.py",
            "equiframe/datasets.py",
            "equiframe/_dataset_provenance.py",
            "equiframe/r_review.py",
            "equiframe/_r_review.R",
            "equiframe/docs/lectura-conversion.md",
            "equiframe/docs/r_review.md",
            "equiframe/schemas/r-review-options-1.0.schema.json",
            "equiframe/schemas/r-review-binding-1.0.schema.json",
            "equiframe/schemas/r-execution-binding-1.0.schema.json",
            "equiframe/schemas/r-review-result-1.0.schema.json",
            "equiframe/schemas/reviewed-decision-1.0.schema.json",
        }
        if not required.issubset(names):
            raise RuntimeError("wheel is missing typed public files or reader/reviewer resources")
    workspace = args.qa_workspace.resolve() if args.qa_workspace is not None else None
    if workspace is not None:
        if workspace.is_relative_to(repository_root(ROOT)):
            parser.error("QA workspace must be outside the checkout")
        workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="equiframe-distribution-", dir=workspace) as directory:
        work = Path(directory).resolve()
        runtime = work / "runtime"
        cache = Path(os.environ.get("UV_CACHE_DIR", str(work / "cache" / "uv"))).resolve()
        if cache.is_relative_to(repository_root(ROOT)):
            parser.error("QA cache must be outside the checkout")
        temporary = work / "temporary"
        temporary.mkdir()
        env = dict(
            os.environ,
            UV_PROJECT_ENVIRONMENT=str(runtime),
            UV_CACHE_DIR=str(cache),
            TMPDIR=str(temporary),
            TMP=str(temporary),
            TEMP=str(temporary),
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            HYPOTHESIS_STORAGE_DIRECTORY=str(work / "hypothesis"),
        )
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
            [uv, "pip", "install", "--python", str(python), "--no-index", str(wheel)],
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
from importlib.resources import files
handbook = files('equiframe').joinpath('docs')
for title in ('index','quickstart','recipes','api','semantics','compatibility',
              'performance','upgrading','contributing','security','releasing','dependencies',
              'adoption','maintenance','extending','lectura-conversion','r_review'):
    assert handbook.joinpath(title + '.md').read_text(encoding='utf-8').strip()
assert equiframe.__version__ == importlib.metadata.version('equiframe') == sys.argv[1]
for name in ('pandas', 'polars', 'duckdb', 'sklearn', 'numpy', 'pyarrow',
             'openpyxl', 'xlrd', 'defusedxml',
             'pytest', 'hypothesis', 'IPython', 'jupyter', 'equiframe_benchmark'):
    assert importlib.util.find_spec(name) is None, name
print('Installed wheel imports from clean site-packages without engines/ML/dev tools')
assert equiframe.ComparisonOptions().batch_rows > 0
assert callable(equiframe.compare) and callable(equiframe.iter_differences)
assert callable(equiframe.assert_equivalent) and callable(equiframe.equivalence_decision)
assert equiframe.EquivalencePolicy().guarantee == 'observed_contract'
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
assert equiframe.SnapshotManifest.model_json_schema()
assert callable(equiframe.SnapshotDataSource) and callable(equiframe.snapshot_fingerprint)
assert callable(equiframe.load_dataset) and callable(equiframe.inspect_dataset)
assert callable(equiframe.convert_dataset)
assert callable(equiframe.DatasetSource) and callable(equiframe.DatasetProvenance)
assert callable(equiframe.review_with_r) and callable(equiframe.finalize_with_r)
assert callable(equiframe.finalize_execution_with_r)
assert callable(equiframe.RReviewBinding) and callable(equiframe.RExecutionBinding)
assert files('equiframe').joinpath('_r_review.R').read_text(encoding='utf-8').strip()
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
        for arguments, expected, diagnostics in (
            ([str(invalid)], 2, ("invalid_input", "hint[document_validation]")),
            ([str(unsupported)], 2, ("invalid_input", "hint[document_validation]")),
            ([str(work / "missing.json")], 3, ("operation_failed", "hint[missing_path]")),
            ([], 2, ("Missing argument",)),
        ):
            result = subprocess.run(
                [str(cli), "contract", "validate", *arguments],
                cwd=work,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != expected or not all(
                diagnostic in result.stderr for diagnostic in diagnostics
            ):
                raise RuntimeError(
                    "installed CLI returned an incorrect diagnostic: " + result.stderr
                )
            if "Traceback" in result.stderr or result.stdout:
                raise RuntimeError(
                    "installed CLI exposed a traceback or reported success on failure"
                )
        verify_extras(uv, wheel, work, env)
        verify_first_use(work / "first-use", uv=uv, environment=env, consumer_environment=runtime)
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
            "examples/snapshot_source.py",
            "schemas/snapshot-manifest-1.0.schema.json",
            "docs/extending.md",
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
            "docs/index.md",
            "docs/quickstart.md",
            "docs/recipes.md",
            "docs/api.md",
            "docs/lectura-conversion.md",
            "docs/r_review.md",
            "src/equiframe/datasets.py",
            "src/equiframe/_dataset_provenance.py",
            "src/equiframe/r_review.py",
            "src/equiframe/_r_review.R",
            "schemas/r-review-options-1.0.schema.json",
            "schemas/r-review-binding-1.0.schema.json",
            "schemas/r-execution-binding-1.0.schema.json",
            "schemas/r-review-result-1.0.schema.json",
            "schemas/reviewed-decision-1.0.schema.json",
            "docs/semantics.md",
            "docs/compatibility.md",
            "docs/performance.md",
            "docs/upgrading.md",
            "docs/contributing.md",
            "docs/security.md",
            "docs/releasing.md",
            "docs/dependencies.md",
            "docs/adoption.md",
            "docs/maintenance.md",
            "tools/check_adoption.py",
            "examples/adoption/empty-registry.json",
            "examples/adoption_replay.py",
            "tests/test_adoption_records.py",
            "tests/test_adoption_replay.py",
            "tools/build_first_use_kit.py",
            "tools/verify_first_use.py",
            "examples/first_use/README.md",
            "examples/first_use/INTERPRETATION.md",
            "examples/first_use/OBSERVATION.md",
            "examples/first_use/requirements.lock",
            "examples/first_use/verify_kit.py",
            "examples/refactor_comparison.py",
            "examples/migrate_duckdb_recipe.py",
        ):
            if not (source / path).is_file():
                raise RuntimeError("sdist is missing " + path)
        # Rebuild both archives with the locked backend; compare every byte.
        source_env = dict(env, UV_PROJECT_ENVIRONMENT=str(runtime))
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
        source_python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(
            [str(source_python), "-m", "build", "--no-isolation"],
            cwd=source,
            env=source_env,
        )
        rebuilt = next((source / "dist").glob("*.whl"))
        if rebuilt.read_bytes() != wheel.read_bytes():
            raise RuntimeError("wheel rebuilt from sdist is not byte reproducible")
        rebuilt_sdist = next((source / "dist").glob("*.tar.gz"))
        if rebuilt_sdist.read_bytes() != sdist.read_bytes():
            raise RuntimeError("sdist rebuilt from sdist is not byte reproducible")
        run(
            [uv, "pip", "install", "--python", str(source_python), "--no-index", str(rebuilt)],
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
        run(
            [
                str(source_python),
                "-I",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(work / "installed-pytest"),
            ],
            cwd=source,
            env=source_env,
        )
        checker = source / "tools" / "check_adoption.py"
        adoption = subprocess.run(
            [
                str(python),
                "-I",
                str(checker),
                str(source / "examples/adoption/empty-registry.json"),
            ],
            cwd=work,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        empty_summary = json.loads(adoption.stdout)
        if (
            empty_summary["human_attempts"] != 0
            or empty_summary["human_adoption_verified"] is not False
            or empty_summary["integration_seconds_total"] is not None
        ):
            raise RuntimeError("empty adoption registry must not fabricate human evidence")
        replay_output = work / "adoption-replay"
        run(
            [
                str(source_python),
                "-I",
                str(source / "examples/adoption_replay.py"),
                "--output",
                str(replay_output),
                "--wheel-sha256",
                hashlib.sha256(wheel.read_bytes()).hexdigest(),
            ],
            cwd=work,
            env=source_env,
        )
        replay = json.loads((replay_output / "receipt.json").read_text("utf-8"))
        if (
            replay["technical_pass"] is not True
            or len(replay["observations"]) != 24
            or replay["human_adoption"] is not False
            or replay["production_ci_job"] is not False
        ):
            raise RuntimeError(
                "installed repeat replay did not establish the scoped technical checks"
            )
        print("Installed adoption tools: empty human record; 24 synthetic repeat checks")

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
            "def acceptance(result: ef.ComparisonResult, root: Path) -> ef.EquivalenceDecision:\n"
            "    policy = ef.EquivalencePolicy(require_persisted_evidence=True)\n"
            "    ef.assert_equivalent(result, policy=policy, evidence_root=root)\n"
            "    return ef.equivalence_decision(result, policy=policy, evidence_root=root)\n"
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
            "    return ef.export_bundle(source, destination)\n"
            "def dataset(path: Path) -> ef.DatasetResult:\n"
            "    return ef.load_dataset(path, target='pandas', options=ef.DatasetReadOptions())\n"
            "def dataset_info(path: Path) -> ef.DatasetInfo:\n"
            "    return ef.inspect_dataset(path)\n"
            "def r_review(a: ef.ArrowInput, b: ef.ArrowInput, "
            "contract: ef.Contract) -> ef.RReviewResult:\n"
            "    return ef.review_with_r(a, b, contract=contract)\n"
            "def bound_r(execution: ef.ExecutionResult, rules: ef.RuleEvaluation, "
            "profile: ef.ProfileResult, detection: ef.ComponentDetectionResult, "
            "comparison: ef.ComparisonResult) -> ef.ReviewedDecision:\n"
            "    return ef.finalize_execution_with_r(execution, rules, profile, "
            "detection, comparison=comparison)\n",
            encoding="utf-8",
        )
        run(
            typed_consumer_command(source_python, source / "pyproject.toml", consumer),
            cwd=work,
            env=source_env,
        )
    print(
        "Verified base/extras outside checkout, API/CLI, typed consumer, "
        "sdist tests and byte-identical wheel/sdist rebuild"
    )


if __name__ == "__main__":
    main()
