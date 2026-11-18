"""Caller-selected operation roots are inspected before creating any output."""

import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pyarrow as pa
import pytest

import equiframe as ef

OPERATIONS = (
    "execute",
    "run_pipeline",
    "compare",
    "diff",
    "migrate",
    "verify",
    "evaluate_rules",
    "profile_execution",
    "reduce_case",
    "run_workflow",
    "ingest_file",
    "capture_duckdb",
    "ParquetDestination",
)


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp("output-admission-inputs")
    column = ef.ColumnSpec(
        name="id",
        logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="count"),
    )
    contract = ef.bag_contract((column,)).spec.contract
    contract = ef.Contract.model_validate(
        contract.model_copy(
            update={
                "rules": (
                    ef.RuleSpec(
                        rule_id="schema",
                        revision=1,
                        specification=ef.SchemaCheck(table="result"),
                        required=True,
                        severity="error",
                    ),
                )
            }
        )
    )
    data = pa.table({"id": [1, 2]})
    source = ef.LocalDataSource({"source": ef.ArrowInput(data)})
    registry = ef.TransformationRegistry()
    registry.register(
        ef.PandasTransformation(
            "identity", lambda inputs, context: inputs["source"].copy(), "owned-fixture-v1"
        )
    )
    plan = ef.ExecutionPlan(contract=contract, engine="pandas", transformation_id="identity")
    execution = ef.execute(plan, source=source, registry=registry, work_dir=root / "baseline")
    assert execution.state == "completed" and execution.output is not None
    assert ef.read_table(execution.output.data).to_pylist() == [{"id": 1}, {"id": 2}]
    ir = ef.RelationalPlan(nodes=(ef.Scan(node_id="scan", table="source"),), output="scan")
    migration = ef.MigrationSpec(
        ir=ir,
        contract=contract,
        source_engine="pandas",
        target_engine="polars",
        require_rules=False,
        comparison_policy=ef.ComparisonPolicy(
            index="ignore", justification="Fixture index is transport metadata"
        ),
    )
    workflow = ef.WorkflowSpec(
        workflow_id="owned",
        stages=(
            ef.WorkflowStage(
                stage_id="one",
                migration=migration,
                inputs=(ef.WorkflowInputBinding(name="source", source="source"),),
            ),
        ),
    )
    profile = ef.ProfileSpec(
        family="nulls_types",
        features=(ef.ProfileFeature(name="rows", metric="log_filas", table="result"),),
    )
    source_file = root / "source.csv"
    source_file.write_bytes(b"id\n1\n2\n")
    return {
        "contract": contract,
        "data": data,
        "source": source,
        "registry": registry,
        "plan": plan,
        "execution": execution,
        "migration": migration,
        "workflow": workflow,
        "profile": profile,
        "source_file": source_file,
        "column": column,
    }


def invoke(operation, work_dir, fixture):
    f = fixture
    if operation == "execute":
        return ef.execute(f["plan"], source=f["source"], registry=f["registry"], work_dir=work_dir)
    if operation == "run_pipeline":
        return ef.run_pipeline(
            ef.PipelineSpec(execution=f["plan"]),
            source=f["source"],
            registry=f["registry"],
            work_dir=work_dir,
        )
    if operation == "compare":
        return ef.compare(
            ef.ArrowInput(f["data"]),
            ef.ArrowInput(f["data"]),
            contract=f["contract"],
            work_dir=work_dir,
        )
    if operation == "diff":
        return ef.diff(f["data"], f["data"], contract=f["contract"], work_dir=work_dir)
    if operation == "migrate":
        return ef.migrate(f["migration"], source=f["source"], work_dir=work_dir)
    if operation == "verify":
        return ef.verify(
            {"owned": f["execution"]},
            contract=f["contract"],
            snapshots={table.name: table.data for table in f["execution"].inputs},
            policy=ef.ComparisonPolicy(
                index="ignore",
                justification="Fixture RangeIndex is transport metadata; id remains explicit",
            ),
            work_dir=work_dir,
        )
    if operation == "evaluate_rules":
        return ef.evaluate_rules(f["execution"], work_dir=work_dir)
    if operation == "profile_execution":
        return ef.profile_execution(f["execution"], spec=f["profile"], work_dir=work_dir)
    if operation == "reduce_case":
        return ef.reduce_case(
            {"source": ef.ArrowInput(f["data"])},
            predicate=lambda tables: ef.ReductionObservation(
                preconditions="satisfied", failure_signature="owned"
            ),
            predicate_version="owned-v1",
            failure_signature="owned",
            work_dir=work_dir,
        )
    if operation == "run_workflow":
        return ef.run_workflow(f["workflow"], source=f["source"], work_dir=work_dir)
    if operation == "ingest_file":
        return ef.ingest_file(
            f["source_file"],
            spec=ef.IngestionSpec(
                format="csv", fields=(ef.FieldMapping(column=f["column"], path=("id",)),)
            ),
            work_dir=work_dir,
        )
    if operation == "capture_duckdb":
        return ef.capture_duckdb("SELECT 1 AS id", work_dir=work_dir)
    return ef.ParquetDestination(work_dir)


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("bad", [0, False, {"wrong": 1}])
def test_wrong_directory_types_cannot_fall_back_to_default(
    tmp_path, monkeypatch, prepared, operation, bad
):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TypeError):
        invoke(operation, bad, prepared)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_linked_output_root_is_rejected_before_writing(tmp_path, prepared, operation, kind):
    if kind == "junction" and os.name != "nt":
        pytest.skip("Windows directory junction")
    real = tmp_path / "real"
    real.mkdir()
    marker = real / "keep.bin"
    marker.write_bytes(b"unchanged")
    link = tmp_path / "linked"
    if kind == "symlink":
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError:
            pytest.skip("Host does not permit directory symlinks")
    else:
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(real)],
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr
    try:
        with pytest.raises(ef.ArtifactIntegrityError):
            invoke(operation, link / "new", prepared)
        assert list(real.iterdir()) == [marker] and marker.read_bytes() == b"unchanged"
    finally:
        if kind == "junction":
            link.rmdir()


@pytest.mark.parametrize("operation", OPERATIONS)
def test_occupied_regular_file_retains_os_error_without_writing(tmp_path, prepared, operation):
    occupied = tmp_path / "occupied"
    occupied.write_bytes(b"previous bytes")
    with pytest.raises(NotADirectoryError):
        invoke(operation, occupied, prepared)
    assert occupied.read_bytes() == b"previous bytes"
    assert list(tmp_path.iterdir()) == [occupied]


@pytest.mark.parametrize("operation", OPERATIONS)
def test_ordinary_parent_navigation_retains_compatibility(tmp_path, prepared, operation):
    traversed = tmp_path / "traversed"
    traversed.mkdir()
    destination = traversed / ".." / "result"
    result = invoke(operation, destination, prepared)
    if operation == "ParquetDestination":
        assert result.current() is None
    else:
        assert (tmp_path / "result").is_dir()
        if operation == "execute":
            assert result.state == "completed" and result.output.row_count == 2
        elif operation == "run_pipeline":
            assert result.complete and result.execution.state == "completed"
        elif operation in {"compare", "diff", "migrate"}:
            assert result.complete and result.state == "equivalent"
        elif operation == "verify":
            assert result.operational_state == "passed"
        elif operation == "evaluate_rules":
            assert result.complete and result.decision == "no_alert"
        elif operation == "profile_execution":
            assert result.complete
        elif operation == "reduce_case":
            assert result.baseline_verified and result.status == "reduced"
        elif operation == "run_workflow":
            assert result.complete
            assert ef.read_table(result.outputs["one"]).to_pylist() == [{"id": 1}, {"id": 2}]
        elif operation == "ingest_file":
            assert result.state == "completed" and result.accepted_records == 2
        elif operation == "capture_duckdb":
            assert result.row_count == 1
    assert list(traversed.iterdir()) == []


@pytest.mark.parametrize("kind", ["directory", "symlink"])
def test_ingestion_rejects_special_source_without_creating_an_operation(tmp_path, prepared, kind):
    source = tmp_path / "input.csv"
    if kind == "directory":
        source.mkdir()
    else:
        original = tmp_path / "original.csv"
        original.write_bytes(b"id\n1\n")
        try:
            source.symlink_to(original)
        except OSError:
            pytest.skip("Host does not permit file symlinks")
    work = tmp_path / "output"
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.ingest_file(
            source,
            spec=ef.IngestionSpec(
                format="csv", fields=(ef.FieldMapping(column=prepared["column"], path=("id",)),)
            ),
            work_dir=work,
        )
    assert not work.exists()


def test_ingestion_reads_only_the_declared_budget_plus_one(tmp_path, prepared, monkeypatch):
    from equiframe import ingestion

    source = tmp_path / "source.csv"
    payload = b"id\n1\n2\n"
    source.write_bytes(payload)
    sizes = []
    original = ingestion.open_regular_file

    @contextmanager
    def measured(path):
        with original(path) as reader:

            class LimitedReader:
                def read(self, size):
                    sizes.append(size)
                    return reader.read(size)

            yield LimitedReader()

    monkeypatch.setattr(ingestion, "open_regular_file", measured)
    work = tmp_path / "output"
    with pytest.raises(ef.ResourceLimitError):
        ef.ingest_file(
            source,
            spec=ef.IngestionSpec(
                format="csv",
                fields=(ef.FieldMapping(column=prepared["column"], path=("id",)),),
                max_source_bytes=2,
            ),
            work_dir=work,
        )
    assert sizes == [3]
    assert source.read_bytes() == payload
    assert not list(work.rglob("ingestion.json"))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO")
def test_ingestion_fifo_never_waits_for_a_writer(tmp_path):
    source = tmp_path / "source.csv"
    os.mkfifo(source, 0o600)
    work = tmp_path / "output"
    child = """
import json,sys
from pathlib import Path
import equiframe as ef
column=ef.ColumnSpec(name='id',logical_type=ef.StringType(),nullable=False,null_policy=ef.NullPolicy(representations=('null',)))
spec=ef.IngestionSpec(format='csv',fields=(ef.FieldMapping(column=column,path=('id',)),))
try:
    ef.ingest_file(Path(sys.argv[1]),spec=spec,work_dir=Path(sys.argv[2]))
except ef.ArtifactIntegrityError:
    print(json.dumps({'rejected':True,'sdk':ef.__file__}))
else:
    raise AssertionError('FIFO input was accepted')
"""
    result = subprocess.run(
        [sys.executable, "-c", child, str(source), str(work)],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["rejected"] is True
    assert Path(observed["sdk"]).resolve() == Path(ef.__file__).resolve()
    assert not work.exists()


@pytest.mark.parametrize("child", ["versions", ".staging", ".validation"])
@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_publication_rejects_linked_owned_subdirectories(tmp_path, prepared, child, kind):
    if kind == "junction" and os.name != "nt":
        pytest.skip("Windows directory junction")
    ref = prepared["execution"].output.data
    report = ef.verify(
        {"candidate": ref},
        contract=prepared["contract"],
        expected=ref,
        work_dir=tmp_path / "verification",
    )
    assert report.publishable
    root = tmp_path / "published"
    root.mkdir()
    destination = ef.ParquetDestination(root)
    real = tmp_path / "outside"
    real.mkdir()
    marker = real / "keep.bin"
    marker.write_bytes(b"unchanged")
    link = root / child
    if kind == "symlink":
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError:
            pytest.skip("Host does not permit directory symlinks")
    else:
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(real)],
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert created.returncode == 0, created.stderr
    try:
        with pytest.raises(ef.ArtifactIntegrityError):
            destination.publish({"table": ref}, run_id="owned", verifications={"table": report})
        assert list(real.iterdir()) == [marker] and marker.read_bytes() == b"unchanged"
        assert list(root.iterdir()) == [link]
    finally:
        if kind == "junction":
            link.rmdir()
