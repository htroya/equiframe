"""Consumer-side conformance uses synthetic fixtures, never a real DW acceptance."""

from collections import Counter

import equiframe as ef
import pytest
from equiframe.local import LocalArtifactStore, local_path
from pydantic import ValidationError

from equiframe_benchmark.fixtures import (
    COMPARISON_POLICY,
    cases,
    expected_table,
    pandas_transform,
    polars_transform,
)
from equiframe_benchmark.integration import (
    ENGINES,
    IntegrationResult,
    IntegrationSpec,
    read_integration,
    run_integration,
)
from equiframe_benchmark.pilot import profile_spec, write_table
from equiframe_benchmark.snapshot import (
    SnapshotColumn,
    SnapshotDataSource,
    SnapshotManifest,
    SnapshotTable,
)


class TestSnapshotClient:
    __test__ = False

    def __init__(self, manifest, *, corrupt_download=None):
        self.manifest = manifest
        self.requests = []
        self.downloads = 0
        self.corrupt_download = corrupt_download

    def get_snapshot(self, snapshot_id):
        self.requests.append(snapshot_id)
        return self.manifest

    def download_artifact(self, ref, destination):
        self.downloads += 1
        LocalArtifactStore(destination.parent).get(ref, destination)
        if self.downloads == self.corrupt_download:
            with destination.open("ab") as output:
                output.write(b"corrupt test bytes")


def environment(tmp_path, *, family="nulls_types", sql=None, corrupt_download=None):
    case = next(case for case in cases() if case.contract.family == family)
    if sql is None:
        sql = {
            "nulls_types": 'SELECT * FROM "items"',
            "duplicates_order": 'SELECT * FROM "items"',
            "joins": 'SELECT o.id, o.product_id, p.category FROM "orders" o '
            'LEFT JOIN "products" p ON o.product_id=p.product_id ORDER BY o.id',
            "aggregations": 'SELECT warehouse, sum(amount) AS total, count(*) AS rows FROM "items" '
            "GROUP BY warehouse",
            "dates": 'SELECT sensor_id, CAST(recorded_at AS DATE) AS day FROM "readings"',
        }[family]
    tables = []
    for declared in case.contract.inputs:
        data = case.inputs[declared.name]
        tables.append(
            SnapshotTable(
                name=declared.name,
                artifact=write_table(data, tmp_path / (declared.name + ".arrow")),
                row_count=data.num_rows,
                columns=tuple(
                    SnapshotColumn(
                        name=column.name,
                        physical_type=str(data.schema.field(column.name).type),
                        logical_type=column.logical_type,
                        nullable=column.nullable,
                    )
                    for column in declared.schema_spec.columns
                ),
            )
        )
    manifest = SnapshotManifest(
        snapshot_id="synthetic-snapshot-v1",
        domain_schema_revision="synthetic-domain-v1",
        extraction_revision="synthetic-extraction-v1",
        provenance=("synthetic engineering fixture; not a Jose or Jhair deliverable",),
        tables=tuple(tables),
    )
    client = TestSnapshotClient(manifest, corrupt_download=corrupt_download)
    source = SnapshotDataSource(manifest.snapshot_id, client=client)
    counters = Counter()

    def pandas(tables, context):
        counters["pandas"] += 1
        return pandas_transform(tables, context)

    def polars(tables, context):
        counters["polars"] += 1
        return polars_transform(tables, context)

    registry = ef.TransformationRegistry()
    registry.register(ef.PandasTransformation(family, pandas, "synthetic-pandas-v1"))
    registry.register(ef.PolarsTransformation(family, polars, "synthetic-polars-v1"))
    registry.register(ef.DuckDBTransformation(family, sql, "synthetic-duckdb-v1"))
    spec = IntegrationSpec(
        pipelines=tuple(
            ef.PipelineSpec(
                execution=ef.ExecutionPlan(
                    contract=case.contract, engine=engine, transformation_id=family
                ),
                profile=profile_spec(case.contract.family),
            )
            for engine in ENGINES
        ),
        domain_schema_revision=manifest.domain_schema_revision,
        comparison_policy=COMPARISON_POLICY,
    )
    return spec, source, registry, client, counters, case


@pytest.mark.parametrize(
    "family", ["nulls_types", "joins", "duplicates_order", "aggregations", "dates"]
)
def test_three_native_runs_share_pinned_snapshot_without_reexecution(tmp_path, family):
    spec, source, registry, client, counters, case = environment(tmp_path, family=family)
    result = run_integration(
        spec,
        source=source,
        registry=registry,
        expected=ef.ArrowInput(expected_table(case)),
        work_dir=tmp_path,
    )
    assert result.complete and result.inputs_verified
    # Native group-by outputs preserve their actual dtypes: Pandas retains
    # decimal(18,2), Polars counts uint32, while the supplied contract asks for
    # decimal(38,2)/int64. R reports these, even when lossless comparison agrees.
    assert result.exit_code == (1 if family == "aggregations" else 0)
    if family == "aggregations":
        assert [run.result.rules.decision for run in result.runs] == ["alert", "alert", "no_alert"]
    assert client.requests == ["synthetic-snapshot-v1"]
    assert client.downloads == 3 * len(case.inputs)
    assert counters == {"pandas": 1, "polars": 1}
    assert len(result.runs) == 3 and len(result.comparisons) == 6
    assert all(item.result.state == "equivalent" for item in result.comparisons)
    assert all(run.result.profile.complete for run in result.runs)
    assert not result.scientific_equivalence_confirmed
    assert read_integration(tmp_path / result.integration_id) == result


def test_native_difference_remains_completed_evidence(tmp_path):
    spec, source, registry, *_ = environment(tmp_path, sql='SELECT * FROM "items" LIMIT 1')
    result = run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    assert result.complete and result.exit_code == 1
    assert [item.result.state for item in result.comparisons] == [
        "equivalent",
        "different",
        "different",
    ]
    assert read_integration(tmp_path / result.integration_id) == result


def test_failed_engine_preserves_independent_pair_and_evidence(tmp_path):
    spec, source, registry, *_ = environment(tmp_path, sql='SELECT missing FROM "items"')
    result = run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    assert not result.complete and result.exit_code == 3
    assert result.runs[2].result.execution.state != "completed"
    assert result.comparisons[0].result.state == "equivalent"
    assert all(item.result.state == "not_evaluable" for item in result.comparisons[1:])
    assert read_integration(tmp_path / result.integration_id) == result


def test_corrupt_input_never_becomes_equivalent_or_no_alert(tmp_path):
    spec, source, registry, *_ = environment(tmp_path, corrupt_download=3)
    result = run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    assert not result.complete and not result.inputs_verified and result.exit_code == 3
    assert result.runs[2].result.execution.state == "invalid_input"
    assert result.comparisons[0].result.state == "equivalent"
    assert all(item.result is None for item in result.comparisons[1:])
    assert read_integration(tmp_path / result.integration_id) == result


def test_cancelled_integration_retains_three_unavailable_native_results(tmp_path):
    spec, source, registry, client, counters, _ = environment(tmp_path)
    cancellation = ef.CancellationToken()
    cancellation.cancel()
    result = run_integration(
        spec, source=source, registry=registry, work_dir=tmp_path, cancellation=cancellation
    )
    assert result.cancelled and not result.complete and result.exit_code == 3
    assert client.downloads == 0 and not counters
    assert all(run.result.cancelled and run.result.execution is None for run in result.runs)
    assert all(item.result is None for item in result.comparisons)
    assert read_integration(tmp_path / result.integration_id) == result


@pytest.mark.parametrize("changed", ["contract", "transformation_id", "transformation_revision"])
def test_incompatible_native_plans_are_rejected(tmp_path, changed):
    spec, *_ = environment(tmp_path)
    raw = spec.model_dump()
    if changed == "contract":
        raw["pipelines"][1]["execution"][changed]["revision"] += 1
    elif changed == "transformation_revision":
        raw["pipelines"][1]["execution"][changed] += 1
    else:
        raw["pipelines"][1]["execution"][changed] = "other-transformation"
    with pytest.raises(ValidationError, match="same contract"):
        IntegrationSpec.model_validate(raw)


def test_domain_version_is_explicit_and_not_silently_adapted(tmp_path):
    spec, source, registry, *_ = environment(tmp_path)
    changed = spec.model_copy(update={"domain_schema_revision": "another-domain-version"})
    with pytest.raises(ValueError, match="schema revision"):
        run_integration(changed, source=source, registry=registry, work_dir=tmp_path)
    assert not list(tmp_path.glob("integration_*"))


def test_selected_tables_can_be_subset_of_full_dw_snapshot(tmp_path):
    spec, source, registry, _, _, _ = environment(tmp_path)
    extra = source.manifest.tables[0].model_copy(update={"name": "unrelated_dw_table"})
    manifest = source.manifest.model_copy(update={"tables": (*source.manifest.tables, extra)})
    client = TestSnapshotClient(manifest)
    selected = SnapshotDataSource(manifest.snapshot_id, client=client, table_names=("items",))
    result = run_integration(spec, source=selected, registry=registry, work_dir=tmp_path)
    assert result.complete and result.exit_code == 0
    assert len(result.snapshot.tables) == 2 and client.downloads == 3
    assert all(len(run.result.execution.inputs) == 1 for run in result.runs)
    assert read_integration(tmp_path / result.integration_id) == result


def test_snapshot_logical_schema_must_match_supplied_domain_contract(tmp_path):
    spec, source, registry, *_ = environment(tmp_path)
    table = source.manifest.tables[0]
    changed_column = table.columns[0].model_copy(
        update={"logical_type": ef.IntegerType(bits=64, signed=True)}
    )
    changed_table = table.model_copy(update={"columns": (changed_column, *table.columns[1:])})
    source._manifest = source.manifest.model_copy(update={"tables": (changed_table,)})
    with pytest.raises(ValueError, match="logical schema"):
        run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    assert not list(tmp_path.glob("integration_*"))


def test_mutable_expected_path_is_captured_once(tmp_path, monkeypatch):
    spec, source, registry, _, _, case = environment(tmp_path)
    expected_path = tmp_path / "expected.arrow"
    original = write_table(expected_table(case), expected_path)
    compare = ef.compare
    expected_comparisons = 0

    def compare_and_change_original(*args, **kwargs):
        nonlocal expected_comparisons
        result = compare(*args, **kwargs)
        if kwargs.get("reference") == "expected":
            expected_comparisons += 1
            expected_path.write_bytes(b"changed after the first expected comparison")
        return result

    monkeypatch.setattr(ef, "compare", compare_and_change_original)
    result = run_integration(
        spec, source=source, registry=registry, expected=expected_path, work_dir=tmp_path
    )
    assert result.complete and result.exit_code == 0 and expected_comparisons == 3
    assert result.expected_artifact.sha256 == original.sha256
    assert all(item.result.state == "equivalent" for item in result.comparisons)
    assert read_integration(tmp_path / result.integration_id) == result


@pytest.mark.parametrize("mismatch", ["inputs", "parameters"])
def test_expected_execution_keeps_input_and_parameter_preconditions(tmp_path, mismatch):
    query = (
        'SELECT * FROM "items" WHERE $example_parameter > 0 LIMIT 1'
        if mismatch == "parameters"
        else 'SELECT * FROM "items" LIMIT 1'
    )
    spec, source, registry, _, _, case = environment(tmp_path, sql=query)
    if mismatch == "parameters":
        actual_parameter = ef.Parameter(name="example_parameter", value=ef.IntegerValue(value=1))
        spec = IntegrationSpec.model_validate(
            spec.model_copy(
                update={
                    "pipelines": tuple(
                        pipeline.model_copy(
                            update={
                                "execution": pipeline.execution.model_copy(
                                    update={"parameters": (actual_parameter,)}
                                )
                            }
                        )
                        for pipeline in spec.pipelines
                    )
                }
            )
        )
    expected_input = (
        case.inputs["items"].slice(0, 3) if mismatch == "inputs" else case.inputs["items"]
    )
    expected_plan = spec.pipelines[2].execution
    if mismatch == "parameters":
        expected_plan = expected_plan.model_copy(
            update={
                "parameters": (
                    ef.Parameter(name="example_parameter", value=ef.IntegerValue(value=2)),
                )
            }
        )
    expected = ef.execute(
        expected_plan,
        source=ef.LocalDataSource({"items": ef.ArrowInput(expected_input)}),
        registry=registry,
        work_dir=tmp_path / "external-expected",
    )
    assert expected.state == "completed"
    result = run_integration(
        spec, source=source, registry=registry, expected=expected, work_dir=tmp_path
    )
    native = result.runs[2].result.execution
    assert native.output.data.sha256 == expected.output.data.sha256  # identical output bytes
    compared = result.comparisons[5].result
    assert compared.state == "not_evaluable" and not result.complete and result.exit_code == 3
    assert compared.right.execution is not None
    assert compared.right.execution.plan == expected.plan
    diagnostic = (
        "execution_inputs_differ" if mismatch == "inputs" else "execution_parameters_differ"
    )
    assert any(diagnostic in problem.message for problem in compared.diagnostics)
    assert read_integration(tmp_path / result.integration_id) == result


def test_snapshot_version_in_execution_must_match_pinned_manifest(tmp_path):
    spec, source, registry, *_ = environment(tmp_path)
    source._fingerprint = "b" * 64
    result = run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    assert not result.complete and result.exit_code == 3
    assert result.input_reason == "snapshot_configuration_mismatch"
    assert all(item.result is None for item in result.comparisons)
    assert read_integration(tmp_path / result.integration_id) == result


def test_index_policy_remains_explicit(tmp_path):
    spec, source, registry, *_ = environment(tmp_path)
    strict = spec.model_copy(
        update={
            "comparison_policy": ef.ComparisonPolicy(
                physical_types="lossless", justification="Lossless test widths; index is rejected"
            )
        }
    )
    result = run_integration(strict, source=source, registry=registry, work_dir=tmp_path)
    assert not result.complete and result.exit_code == 3
    assert all(item.result.state == "not_evaluable" for item in result.comparisons[:2])
    assert result.comparisons[2].result.state == "equivalent"


def test_relaunch_uses_new_evidence_directory(tmp_path):
    spec, source, registry, *_ = environment(tmp_path)
    first = run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    second = run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    assert first.integration_id != second.integration_id
    assert read_integration(tmp_path / first.integration_id) == first
    assert read_integration(tmp_path / second.integration_id) == second


def test_integration_capture_tamper_is_rejected(tmp_path):
    spec, source, registry, *_ = environment(tmp_path)
    result = run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    directory = tmp_path / result.integration_id
    with local_path(result.runs[0].result.execution.output.data).open("ab") as output:
        output.write(b"tampered")
    with pytest.raises(ef.ArtifactIntegrityError):
        read_integration(directory)


def test_publication_failure_leaves_partial_evidence(tmp_path, monkeypatch):
    import equiframe_benchmark.integration as integration

    spec, source, registry, *_ = environment(tmp_path)
    publish = integration.publish_json

    def fail_final(value, path):
        if path.name == "integration.json":
            raise OSError("synthetic publication failure")
        return publish(value, path)

    monkeypatch.setattr(integration, "publish_json", fail_final)
    with pytest.raises(OSError):
        run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    directory = next(tmp_path.glob("integration_*"))
    assert not (directory / "integration.json").exists()
    assert len(list(directory.glob("pipeline_*/manifest.json"))) == 3
    assert (directory / "events.jsonl").exists()


def test_input_verification_cannot_be_forged(tmp_path):
    spec, source, registry, *_ = environment(tmp_path)
    result = run_integration(spec, source=source, registry=registry, work_dir=tmp_path)
    raw = result.model_dump()
    raw["input_reason"] = "input_capture_unavailable"
    with pytest.raises(ValidationError, match="input verification"):
        IntegrationResult.model_validate(raw)
