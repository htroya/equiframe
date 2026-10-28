"""Migration acceptance over actual engines; all data and expectations are synthetic."""

import json
from itertools import permutations
from pathlib import Path

import pyarrow as pa
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import equiframe as ef
from equiframe._comparison_io import file_ref
from equiframe.cli import app
from equiframe.evidence import describe_file, publish_json
from equiframe.local import local_path
from equiframe.migration import runner as migration_runner
from equiframe.profile_types import profile_digest


def contract():
    schema = ef.TableSchema(
        columns=(
            ef.ColumnSpec(
                name="id",
                logical_type=ef.IntegerType(bits=64, signed=True),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="identifier"),
            ),
            ef.ColumnSpec(
                name="value",
                logical_type=ef.StringType(),
                nullable=True,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
        ),
        keys=(),
        multiplicity="preserve",
        order=ef.IgnoredOrder(),
    )
    return ef.Contract(
        schema_version="1.0",
        contract_id="migration.synthetic",
        revision=1,
        family="nulls_types",
        inputs=(ef.TableSpec(name="input", schema_spec=schema),),
        output=ef.TableSpec(name="result", schema_spec=schema),
        preconditions=(),
        rules=(
            ef.RuleSpec(
                rule_id="schema",
                revision=1,
                required=True,
                severity="error",
                specification=ef.SchemaCheck(table="result"),
            ),
        ),
    )


def table():
    return pa.table({"id": [1, 2, 3], "value": ["a", None, "c"]})


def spec(source="pandas", target="duckdb", **kwargs):
    return ef.MigrationSpec(
        ir=ef.RelationalPlan(nodes=(ef.Scan(node_id="scan", table="input"),), output="scan"),
        contract=contract(),
        source_engine=source,
        target_engine=target,
        comparison_policy=ef.ComparisonPolicy(
            index="ignore",
            justification="Synthetic generated RangeIndex carries no business identity.",
        ),
        **kwargs,
    )


class Provider:
    def __init__(self, data=None):
        self.data = data if data is not None else table()
        self.calls = 0

    @property
    def table_names(self):
        return ("input",)

    def resolve(self, name, *, context):
        assert name == "input"
        self.calls += 1
        return ef.LoadedTable(self.data)


def spy_adapter(engine, action=None):
    native = {
        "pandas": ef.PandasAdapter,
        "polars": ef.PolarsAdapter,
        "duckdb": ef.DuckDBAdapter,
    }[engine]

    class Spy(native):
        # Preserve native adapter admission and private timestamp/checkpoint
        # handling while observing the real execution, including failures.
        def __init__(self):
            self.calls = 0

        def execute(self, transformation, inputs, context):
            self.calls += 1
            if action:
                action(context)
            return super().execute(transformation, inputs, context)

    return Spy()


def run(tmp_path, *, document=None, provider=None, **kwargs):
    return ef.migrate(
        document if document is not None else spec(),
        source=provider if provider is not None else Provider(),
        work_dir=tmp_path,
        **kwargs,
    )


@pytest.mark.parametrize("source,target", list(permutations(("pandas", "polars", "duckdb"), 2)))
def test_six_native_directions_capture_once_independent_expected(tmp_path, source, target):
    provider = Provider()
    adapters = {e: spy_adapter(e) for e in (source, target)}
    result = run(
        tmp_path,
        document=spec(source, target),
        provider=provider,
        adapters=adapters,
        expected=ef.ArrowInput(table()),
    )
    assert result.complete and result.exit_code == 0
    assert result.state == "equivalent" and result.verification == "correct"
    assert provider.calls == 1 and [a.calls for a in adapters.values()] == [1, 1]
    for p in (result.source, result.target):
        assert (
            p.execution.state == "completed" and p.execution.plan.engine == p.spec.execution.engine
        )
        assert ef.read_table(p.execution.output.data).to_pydict() == table().to_pydict()
        assert p.execution.inputs[0].data.sha256 == result.inputs[0].data.sha256
    assert ef.read_migration(tmp_path / result.migration_id) == result
    assert ef.inspect_evidence(tmp_path / result.migration_id)["finalized"]
    assert ef.MigrationResult.model_validate_json(result.model_dump_json()) == result
    assert len(list((tmp_path / result.migration_id).rglob("run.json"))) == 2


def test_agreement_can_share_error_and_expected_is_not_detector_input(tmp_path):
    original = spec()
    wrong = ef.RelationalPlan(
        nodes=(
            ef.Scan(node_id="scan", table="input"),
            ef.Project(
                node_id="project",
                source="scan",
                columns=(
                    ef.NamedExpression(
                        name="id",
                        expression=ef.LiteralExpression(
                            logical_type=ef.IntegerType(bits=64, signed=True),
                            value=ef.IntegerValue(value=99),
                            unit="identifier",
                        ),
                    ),
                    ef.NamedExpression(name="value", expression=ef.Column(name="value")),
                ),
            ),
        ),
        output="project",
    )
    result = run(
        tmp_path,
        document=original.model_copy(update={"ir": wrong}),
        expected=ef.ArrowInput(table()),
    )
    assert result.complete and result.state == "equivalent"
    assert result.verification == "divergent" and result.exit_code == 1
    assert result.verification_source.state == result.verification_target.state == "different"
    assert result.source.rules.decision == result.target.rules.decision == "no_alert"
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_without_expected_only_observed_equivalence(tmp_path):
    result = run(tmp_path)
    assert result.complete and result.verification == "not_requested"
    assert ef.migration_summary(result)["equivalence_is_independent_correctness"] is False


def test_empty_rules_need_explicit_optional_rules_mode(tmp_path):
    c = contract().model_copy(update={"rules": ()})
    base = spec().model_copy(update={"contract": c})
    required = run(tmp_path / "required", document=base)
    assert not required.complete and required.exit_code == 3
    optional = run(tmp_path / "optional", document=base.model_copy(update={"require_rules": False}))
    assert optional.complete and optional.exit_code == 0
    assert optional.source.rules.decision == "not_evaluable"
    assert not optional.source.complete
    assert ef.read_migration(tmp_path / "optional" / optional.migration_id) == optional


def test_date64_capability_rejected_before_either_native_execution(tmp_path):
    from datetime import date

    col = ef.ColumnSpec(
        name="day",
        logical_type=ef.DateType(),
        nullable=False,
        null_policy=ef.NullPolicy(representations=("null",)),
        temporal_policy=ef.DatePolicy(closed="both"),
    )
    schema = ef.TableSchema(
        columns=(col,), keys=(), multiplicity="preserve", order=ef.IgnoredOrder()
    )
    c = contract().model_copy(
        update={
            "inputs": (ef.TableSpec(name="input", schema_spec=schema),),
            "output": ef.TableSpec(name="result", schema_spec=schema),
        }
    )
    document = spec("pandas", "polars").model_copy(update={"contract": c})
    adapters = {e: spy_adapter(e) for e in ("pandas", "polars")}
    result = run(
        tmp_path,
        document=document,
        provider=Provider(pa.table({"day": pa.array([date(2025, 1, 1)], type=pa.date64())})),
        adapters=adapters,
    )
    assert result.exit_code == 2 and result.stages[1].code == "unsupported_capability"
    assert all(a.calls == 0 for a in adapters.values())


@pytest.mark.parametrize("batch_rows", [1, 5, 4096])
@pytest.mark.parametrize("format_name", ["arrow", "parquet"])
def test_expected_physical_capture_statistics_independent_of_comparison_chunks(
    tmp_path,
    batch_rows,
    format_name,
):
    data = pa.table(
        {"id": list(range(13)), "value": [None if i % 3 == 0 else "a" for i in range(13)]}
    )
    document = spec(comparison_options=ef.ComparisonOptions(batch_rows=batch_rows))
    if format_name == "arrow":
        expected = ef.ArrowInput(data)
    else:
        import pyarrow.parquet as pq

        path = tmp_path / "expected.parquet"
        pq.write_table(data, path, row_group_size=5)
        expected = file_ref(path, "parquet")
    result = run(tmp_path, document=document, provider=Provider(data), expected=expected)
    assert result.complete and result.verification == "correct"
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_wrong_expected_shape_is_not_evaluable(tmp_path):
    result = run(tmp_path, expected=ef.ArrowInput(pa.table({"wrong": [1]})))
    assert not result.complete and result.exit_code == 3
    assert result.state == "equivalent" and result.verification == "not_evaluable"
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_invalid_physical_input_never_gets_cast_to_contract(tmp_path):
    provider = Provider(
        pa.table(
            {
                "id": pa.array([1, 2], type=pa.int32()),
                "value": ["a", "b"],
            }
        )
    )
    adapters = {e: spy_adapter(e) for e in ("pandas", "duckdb")}
    result = run(tmp_path, provider=provider, adapters=adapters)
    assert not result.complete and result.exit_code == 2 and result.source is result.target is None
    assert all(a.calls == 0 for a in adapters.values())
    assert provider.calls == 1
    assert ef.read_migration(tmp_path / result.migration_id) == result


@pytest.mark.parametrize("fault", ["null", "columns", "allowed"])
def test_input_constraints_fail_before_both_etls(tmp_path, fault):
    document = spec()
    data = table()
    if fault == "null":
        data = pa.table({"id": [1, None, 3], "value": ["a", None, "c"]})
    elif fault == "columns":
        data = table().select(["value", "id"])
    else:
        c = document.contract
        inp = c.inputs[0]
        col = inp.schema_spec.columns[0].model_copy(
            update={"allowed_values": (ef.IntegerValue(value=1),)}
        )
        inp = inp.model_copy(
            update={
                "schema_spec": inp.schema_spec.model_copy(
                    update={
                        "columns": (col, inp.schema_spec.columns[1]),
                    }
                )
            }
        )
        document = document.model_copy(update={"contract": c.model_copy(update={"inputs": (inp,)})})
    result = run(tmp_path, document=document, provider=Provider(data))
    assert result.exit_code == 2 and result.source is result.target is None


def test_preflight_checks_both_compilers_before_provider(tmp_path):
    document = spec(target="unknown")
    provider = Provider()
    result = run(tmp_path, document=document, provider=provider)
    assert result.exit_code == 2 and provider.calls == 0 and not result.inputs
    assert result.stages[0].code == "unsupported_capability"
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_missing_target_dependency_before_any_etl_or_resolve(tmp_path, monkeypatch):
    real = migration_runner.require_dependency

    def missing(name, extra):
        if name == "duckdb":
            raise ef.MissingDependencyError("synthetic missing target")
        real(name, extra)

    monkeypatch.setattr(migration_runner, "require_dependency", missing)
    provider = Provider()
    result = run(tmp_path, provider=provider)
    assert result.exit_code == 2 and provider.calls == 0 and result.source is result.target is None


def test_provider_binding_error_is_preflight_invalid(tmp_path):
    provider = Provider()

    class WrongProvider(Provider):
        @property
        def table_names(self):
            return ("missing",)

    result = run(tmp_path, provider=WrongProvider())
    assert result.exit_code == 2 and not result.inputs
    assert provider.calls == 0


def test_borrowed_provider_buffers_are_isolated_from_native_callback(tmp_path):
    original = table()
    provider = Provider(original)

    def mutate(_):
        import numpy as np

        np.frombuffer(original["id"].chunk(0).buffers()[1], dtype=np.int64)[0] = 99

    adapters = {"pandas": spy_adapter("pandas", mutate), "duckdb": spy_adapter("duckdb")}
    result = run(tmp_path, provider=provider, adapters=adapters, expected=ef.ArrowInput(table()))
    assert result.complete and result.verification == "correct"
    assert original["id"][0].as_py() == 99
    assert ef.read_table(result.inputs[0].data)["id"][0].as_py() == 1


def test_index_is_not_implicitly_ignored(tmp_path):
    document = spec().model_copy(update={"comparison_policy": ef.ComparisonPolicy()})
    result = run(tmp_path, document=document)
    assert not result.complete and result.exit_code == 3
    assert result.comparison.state == "not_evaluable"
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_meaningful_pandas_index_requires_columns_even_with_ignore_policy(tmp_path):
    import pandas as pd

    frame = pd.DataFrame({"id": [1, 2], "value": ["a", "b"]}, index=["x", "y"])
    result = ef.migrate(
        spec(),
        source=ef.LocalDataSource({"input": ef.PandasInput(frame)}),
        work_dir=tmp_path,
    )
    assert result.exit_code == 2 and result.source is result.target is None
    assert frame.index.tolist() == ["x", "y"]


def test_capture_budget_counts_expected_and_all_inputs(tmp_path):
    document = spec(options=ef.MigrationOptions(max_capture_rows=5))
    result = run(tmp_path, document=document, expected=ef.ArrowInput(table()))
    assert result.exit_code == 3 and not result.complete
    assert result.stages[1].code == "resource_exhausted"
    assert result.source is result.target is None


def test_pre_cancelled_and_global_timeout_are_not_success(tmp_path):
    token = ef.CancellationToken()
    token.cancel()
    result = run(tmp_path / "cancel", cancellation=token)
    assert result.cancelled and not result.complete and result.exit_code == 3
    timed = run(
        tmp_path / "timeout", document=spec(options=ef.MigrationOptions(timeout_seconds=1e-9))
    )
    assert not timed.complete and timed.exit_code == 3
    assert timed.stages[0].code == "timeout"
    assert ef.read_migration(tmp_path / "cancel" / result.migration_id) == result


def test_cancellation_during_origin_does_not_execute_destination(tmp_path):
    token = ef.CancellationToken()
    src, dst = spy_adapter("pandas", lambda _: token.cancel()), spy_adapter("duckdb")
    result = run(tmp_path, cancellation=token, adapters={"pandas": src, "duckdb": dst})
    assert src.calls == 1 and dst.calls == 0
    assert result.cancelled and result.exit_code == 3
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_native_failure_remains_failure_and_other_motor_can_complete(tmp_path):
    def fail(_):
        raise RuntimeError("synthetic failure")

    result = run(
        tmp_path,
        adapters={
            "pandas": spy_adapter("pandas", fail),
            "duckdb": spy_adapter("duckdb"),
        },
    )
    assert result.source.execution.state == "failed"
    assert result.target.execution.state == "completed"
    assert result.comparison is None and not result.complete and result.exit_code == 3
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_finite_budgets_bind_effective_timeouts(tmp_path):
    result = run(
        tmp_path,
        document=spec(
            options=ef.MigrationOptions(timeout_seconds=60.0),
            execution_options=ef.ExecutionOptions(timeout_seconds=30.0),
            comparison_options=ef.ComparisonOptions(timeout_seconds=20.0),
        ),
    )
    assert result.complete
    assert 0 < result.source.execution.plan.options.timeout_seconds <= 30
    assert 0 < result.comparison.options.timeout_seconds <= 20
    raw = result.model_dump()
    cmp = result.comparison.model_dump()
    cmp["options"]["max_rows"] += 1
    raw["comparison"] = cmp
    with pytest.raises(ValidationError, match="configuration"):
        ef.MigrationResult.model_validate(raw)


def test_reports_are_verified_after_rehashing_inventory(tmp_path):
    result = run(tmp_path)
    directory = tmp_path / result.migration_id
    (directory / "report.json").write_text('{"complete":true}', encoding="utf-8")
    raw = result.model_dump()
    raw["evidence"] = tuple(
        describe_file(p, directory)
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.name != "migration.json"
    )
    forged = ef.MigrationResult.model_validate(raw)
    (directory / "migration.json").write_text(forged.model_dump_json(), encoding="utf-8")
    with pytest.raises(ef.ArtifactIntegrityError, match="report"):
        ef.read_migration(directory)


@pytest.mark.parametrize("kind", ["mutate", "extra", "missing"])
def test_closed_inventory_detects_changes(tmp_path, kind):
    result = run(tmp_path)
    directory = tmp_path / result.migration_id
    if kind == "mutate":
        (directory / "report.html").write_text("changed", encoding="utf-8")
    elif kind == "extra":
        (directory / "extra.json").write_text("{}", encoding="utf-8")
    else:
        (directory / "report.json").unlink()
    with pytest.raises(ef.ArtifactIntegrityError):
        ef.read_migration(directory)


def test_reader_does_not_execute_compilers_or_providers(tmp_path, monkeypatch):
    result = run(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("verification must not execute ETL")

    monkeypatch.setattr(migration_runner, "migrate", forbidden)
    monkeypatch.setattr(migration_runner, "native_compiler_registry", forbidden)
    monkeypatch.setattr(ef.PandasAdapter, "execute", forbidden)
    monkeypatch.setattr(ef.DuckDBAdapter, "execute", forbidden)
    assert ef.read_migration(tmp_path / result.migration_id) == result


def test_difference_file_counts_are_verified_after_consistent_rehash(tmp_path):
    result = run(
        tmp_path,
        expected=ef.ArrowInput(
            pa.table(
                {
                    "id": [8, 9, 10],
                    "value": ["x", None, "y"],
                }
            )
        ),
    )
    directory = tmp_path / result.migration_id
    cmp = result.comparison
    path = directory / cmp.comparison_id / "differences.jsonl"
    path.write_text(
        result.verification_source.examples[0].model_dump_json() + "\n", encoding="utf-8"
    )
    cmp = cmp.model_copy(update={"differences": file_ref(path, "jsonl")})
    (directory / cmp.comparison_id / "comparison.json").write_text(
        cmp.model_dump_json(), encoding="utf-8"
    )
    raw = result.model_dump()
    raw["comparison"] = cmp
    raw["evidence"] = tuple(
        describe_file(p, directory)
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.name != "migration.json"
    )
    result = ef.MigrationResult.model_validate(raw)
    (directory / "migration.json").write_text(result.model_dump_json(), encoding="utf-8")
    with pytest.raises(ef.ArtifactIntegrityError, match="counts"):
        ef.read_migration(directory)


def test_external_artifact_is_rejected_before_any_physical_decode(tmp_path, monkeypatch):
    from equiframe.migration import io as migration_io

    result = run(tmp_path)
    directory = tmp_path / result.migration_id
    outside = tmp_path / "foreign.arrow"
    original = local_path(result.inputs[0].data)
    outside.write_bytes(original.read_bytes())
    ref = result.inputs[0].data.model_copy(update={"uri": outside.resolve().as_uri()})
    captured = result.inputs[0].model_copy(update={"data": ref})
    raw = result.model_dump()
    raw["inputs"] = (captured,)
    receipt = json.loads((directory / "capture.json").read_text(encoding="utf-8"))
    receipt["inputs"] = [captured.model_dump(mode="json")]
    (directory / "capture.json").write_text(json.dumps(receipt), encoding="utf-8")
    raw["evidence"] = tuple(
        describe_file(p, directory)
        for p in sorted(directory.rglob("*"))
        if p.is_file() and p.name != "migration.json"
    )
    result = ef.MigrationResult.model_validate(raw)
    (directory / "migration.json").write_text(result.model_dump_json(), encoding="utf-8")

    def forbidden(_):
        raise AssertionError("external reference must not be decoded")

    monkeypatch.setattr(migration_io, "verify_table_metadata", forbidden)
    with pytest.raises(ef.ArtifactIntegrityError, match="escapes"):
        ef.read_migration(directory)


def test_failed_publication_does_not_claim_finalization(tmp_path, monkeypatch):
    real = migration_runner.publish_json

    def fail(value, path):
        if path.name == "migration.json":
            raise OSError("synthetic publication failure")
        real(value, path)

    monkeypatch.setattr(migration_runner, "publish_json", fail)
    with pytest.raises(OSError):
        run(tmp_path)
    assert len(list(tmp_path.glob("migration_*"))) == 1
    assert not list(tmp_path.rglob("migration.json"))
    assert list(tmp_path.rglob("report.json"))


def test_profile_and_detector_do_not_receive_expected_results(tmp_path):
    from test_pipeline import profile_spec, trained_bundle

    bundle = trained_bundle()
    document = spec(profile=profile_spec())
    good = run(
        tmp_path / "good",
        document=document,
        detector_bundle=bundle,
        expected=ef.ArrowInput(table()),
    )
    bad = run(
        tmp_path / "bad",
        document=document,
        detector_bundle=bundle,
        expected=ef.ArrowInput(pa.table({"id": [8, 9, 10], "value": ["x", None, "y"]})),
    )
    assert good.source.profile.vector == bad.source.profile.vector
    assert good.target.profile.vector == bad.target.profile.vector
    assert good.source.detection.m[0].result == bad.source.detection.m[0].result
    assert good.target.detection.b[0].result == bad.target.detection.b[0].result
    assert good.verification == "correct" and bad.verification == "divergent"
    assert ef.read_migration(tmp_path / "bad" / bad.migration_id) == bad


def write_arrow(path: Path, data):
    with path.open("wb") as output, pa.ipc.new_file(output, data.schema) as writer:
        writer.write_table(data)
    return file_ref(path, "arrow")


def test_cli_validate_run_and_integrity_verify(tmp_path):
    runner = CliRunner()
    document = spec("polars", "duckdb")
    config = tmp_path / "spec.json"
    publish_json(document, config)
    validated = runner.invoke(app, ["migration", "validate", str(config)])
    assert validated.exit_code == 0 and json.loads(validated.stdout)["compilation_only"]
    ref = write_arrow(tmp_path / "input.arrow", table())
    request = tmp_path / "request.json"
    publish_json(
        ef.MigrationRequest(
            spec=document,
            inputs=(ef.PipelineInput(name="input", artifact=ref),),
            expected=ref,
        ),
        request,
    )
    output = tmp_path / "runs"
    executed = runner.invoke(app, ["migration", "run", str(request), "--output", str(output)])
    assert executed.exit_code == 0, executed.output
    summary = json.loads(executed.stdout)
    verified = runner.invoke(app, ["migration", "verify", str(output / summary["migration_id"])])
    assert verified.exit_code == 0 and json.loads(verified.stdout)["integrity_verified"]


def test_cli_unsupported_and_duplicate_json_are_invalid(tmp_path):
    runner = CliRunner()
    bad = tmp_path / "bad.json"
    publish_json(spec(target="unknown"), bad)
    assert runner.invoke(app, ["migration", "validate", str(bad)]).exit_code == 2
    bad.write_text('{"schema_version":"1.0","schema_version":"1.0"}', encoding="utf-8")
    assert runner.invoke(app, ["migration", "validate", str(bad)]).exit_code == 2


def test_spec_and_request_are_strict_and_frozen(tmp_path):
    with pytest.raises(ValidationError):
        ef.MigrationSpec.model_validate({**spec().model_dump(), "source_engine": "duckdb"})
    with pytest.raises(ValidationError):
        ef.MigrationSpec.model_validate({**spec().model_dump(), "extra": True})
    document = spec()
    with pytest.raises(ValidationError):
        document.target_engine = "polars"
    with pytest.raises(ValidationError):
        ef.MigrationRequest(spec=document, inputs=())
    assert profile_digest(document.model_dump(mode="json")) == profile_digest(
        ef.MigrationSpec.model_validate_json(document.model_dump_json()).model_dump(mode="json")
    )
