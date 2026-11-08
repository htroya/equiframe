"""Workflow fixes inputs once, binds checkpoints, and propagates failed dependencies."""

import pandas as pd
import pyarrow as pa
import pytest
from test_migration_backends import column, contract

import equiframe as ef
from equiframe.contracts import IntegerType
from equiframe.local import LocalArtifactStore
from equiframe.migration.runner_types import MigrationSpec
from equiframe.migration.types import Column, NamedExpression, Project, RelationalPlan, Scan
from equiframe.workflow import (
    InputBinding,
    WorkflowSpec,
    WorkflowStage,
    read_workflow,
    run_workflow,
)


def reference(table, path):
    with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, table.schema) as writer:
        writer.write_table(table)
    return LocalArtifactStore(path.parent / "reference-artifacts").put(
        path, media_type="application/vnd.apache.arrow.file"
    )


def stage(stage_id, parent=None):
    schema = contract(
        {"input": [column("n", IntegerType(bits=64, signed=True))]},
        [column("n", IntegerType(bits=64, signed=True))],
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="s", table="input"),
            Project(
                node_id="p",
                source="s",
                columns=(NamedExpression(name="n", expression=Column(name="n")),),
            ),
        ),
        output="p",
    )
    return WorkflowStage(
        stage_id=stage_id,
        migration=MigrationSpec(
            ir=plan,
            contract=schema,
            source_engine="pandas",
            target_engine="polars",
            require_rules=False,
            comparison_policy=ef.ComparisonPolicy(
                index="ignore", justification="Generated index has no ETL meaning"
            ),
        ),
        inputs=(
            InputBinding(name="input", source="output" if parent else "original", stage=parent),
        ),
    )


class CountingSource:
    table_names = ("original",)

    def __init__(self):
        self.calls = 0

    def resolve(self, name, *, context):
        self.calls += 1
        return ef.ArrowInput(pa.table({"n": [self.calls, 2]})).load(context)


def test_multiple_checkpoints_capture_once_and_roundtrip(tmp_path):
    source = CountingSource()
    spec = WorkflowSpec(
        workflow_id="generic", stages=(stage("first"), stage("second", "first"), stage("parallel"))
    )
    result = run_workflow(spec, source=source, work_dir=tmp_path)
    assert result.complete and result.exit_code == 0
    assert source.calls == 1
    assert set(result.outputs) == {"first", "second", "parallel"}
    assert all(
        ef.read_table(ref).to_pylist() == [{"n": 1}, {"n": 2}] for ref in result.outputs.values()
    )
    assert read_workflow(tmp_path / result.run_id) == result


def test_expected_divergence_blocks_dependent_but_not_independent_stage(tmp_path):
    expected = reference(pa.table({"n": [0, 2]}), tmp_path / "expected.arrow")
    result = run_workflow(
        WorkflowSpec(
            workflow_id="generic",
            stages=(stage("first"), stage("dependent", "first"), stage("independent")),
        ),
        source=CountingSource(),
        expected={"first": expected},
        work_dir=tmp_path,
    )
    assert result.first_divergent_stage == "first"
    assert [c.state for c in result.checkpoints] == ["failed", "skipped", "passed"]
    assert result.checkpoints[1].migration is None
    assert result.exit_code == 1
    assert result.checkpoints[0].migration.state == "equivalent"
    assert result.checkpoints[0].migration.verification == "divergent"


def test_cancelled_workflow_does_not_fabricate_stages(tmp_path):
    token = ef.CancellationToken()
    token.cancel()
    result = run_workflow(
        WorkflowSpec(workflow_id="cancelled", stages=(stage("one"), stage("two", "one"))),
        source=CountingSource(),
        work_dir=tmp_path,
        cancellation=token,
    )
    assert not result.complete
    assert all(c.state == "skipped" and c.migration is None for c in result.checkpoints)
    assert result.exit_code == 3


def test_corrupt_closed_workflow_evidence_is_rejected(tmp_path):
    result = run_workflow(
        WorkflowSpec(workflow_id="test", stages=(stage("one"),)),
        source=CountingSource(),
        work_dir=tmp_path,
    )
    (tmp_path / result.run_id / "injected.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(ef.ArtifactIntegrityError):
        read_workflow(tmp_path / result.run_id)


def test_cycles_unknown_outputs_resume_are_rejected():
    with pytest.raises(ValueError):
        WorkflowSpec(workflow_id="bad", stages=(stage("one", "two"), stage("two", "one")))
    with pytest.raises(ValueError):
        WorkflowSpec(workflow_id="bad", stages=(stage("one"),), resume=True)


def test_checkpoint_must_bind_fixed_source_and_declared_plan(tmp_path):
    result = run_workflow(
        WorkflowSpec(workflow_id="test", stages=(stage("one"),)),
        source=CountingSource(),
        work_dir=tmp_path,
    )
    assert result.complete
    substituted = reference(pa.table({"n": [9, 2]}), tmp_path / "replacement.arrow")
    input_table = result.inputs[0].model_copy(update={"data": substituted})
    with pytest.raises(ValueError, match="fixed dependency"):
        type(result).model_validate(result.model_copy(update={"inputs": (input_table,)}))
    modified_stage = result.spec.stages[0].model_copy(
        update={
            "migration": result.spec.stages[0].migration.model_copy(update={"require_rules": True})
        }
    )
    with pytest.raises(ValueError, match="stage contract"):
        type(result).model_validate(
            result.model_copy(
                update={"spec": result.spec.model_copy(update={"stages": (modified_stage,)})}
            )
        )


@pytest.mark.parametrize("deadline", [None, 60.0])
def test_checkpoint_options_only_allow_timeout_reduction_with_global_deadline(tmp_path, deadline):
    planned_stage = stage("one")
    if deadline is not None:
        planned_stage = planned_stage.model_copy(
            update={
                "migration": planned_stage.migration.model_copy(
                    update={
                        "options": planned_stage.migration.options.model_copy(
                            update={"timeout_seconds": 120.0}
                        )
                    }
                )
            }
        )
    result = run_workflow(
        WorkflowSpec(workflow_id="options", stages=(planned_stage,), timeout_seconds=deadline),
        source=CountingSource(),
        work_dir=tmp_path,
    )
    assert result.complete
    assert read_workflow(tmp_path / result.run_id) == result
    actual_timeout = result.checkpoints[0].migration.spec.options.timeout_seconds
    if deadline is None:
        assert actual_timeout is None
    else:
        assert actual_timeout is not None and 0 < actual_timeout <= deadline

    for field in ("max_capture_rows", "max_capture_bytes"):
        modified_options = planned_stage.migration.options.model_copy(
            update={field: getattr(planned_stage.migration.options, field) + 1}
        )
        modified_stage = planned_stage.model_copy(
            update={
                "migration": planned_stage.migration.model_copy(
                    update={"options": modified_options}
                )
            }
        )
        with pytest.raises(ValueError, match="stage contract/plan/options"):
            type(result).model_validate(
                result.model_copy(
                    update={"spec": result.spec.model_copy(update={"stages": (modified_stage,)})}
                )
            )

    if deadline is None:
        modified_options = planned_stage.migration.options.model_copy(
            update={"timeout_seconds": 120.0}
        )
        modified_stage = planned_stage.model_copy(
            update={
                "migration": planned_stage.migration.model_copy(
                    update={"options": modified_options}
                )
            }
        )
        modified_spec = result.spec.model_copy(update={"stages": (modified_stage,)})
    else:
        modified_spec = result.spec.model_copy(update={"timeout_seconds": actual_timeout / 2})
    with pytest.raises(ValueError, match="stage contract/plan/options"):
        type(result).model_validate(result.model_copy(update={"spec": modified_spec}))

    if deadline is not None:
        modified_stage = planned_stage.model_copy(
            update={
                "migration": planned_stage.migration.model_copy(
                    update={
                        "options": planned_stage.migration.options.model_copy(
                            update={"timeout_seconds": actual_timeout / 2}
                        )
                    }
                )
            }
        )
        with pytest.raises(ValueError, match="stage contract/plan/options"):
            type(result).model_validate(
                result.model_copy(
                    update={"spec": result.spec.model_copy(update={"stages": (modified_stage,)})}
                )
            )


@pytest.mark.parametrize("meaningful", [False, True])
@pytest.mark.parametrize("ignore_index", [False, True])
def test_external_index_keeps_direct_migration_admission(tmp_path, meaningful, ignore_index):
    frame = pd.DataFrame({"n": [1, 2]})
    if meaningful:
        frame.index = pd.Index(["a", "b"], name="business_id")
    planned = stage("indexed")
    if not ignore_index:
        planned = planned.model_copy(
            update={
                "migration": planned.migration.model_copy(
                    update={"comparison_policy": ef.ComparisonPolicy()}
                )
            }
        )
    direct = ef.migrate(
        planned.migration,
        source=ef.LocalDataSource({"input": ef.PandasInput(frame)}),
        work_dir=tmp_path / "direct",
    )
    result = run_workflow(
        WorkflowSpec(workflow_id="indexed", stages=(planned,)),
        source=ef.LocalDataSource({"original": ef.PandasInput(frame)}),
        work_dir=tmp_path / "workflow",
    )
    migration = result.checkpoints[0].migration
    assert migration is not None
    assert migration.exit_code == direct.exit_code
    assert result.complete is (ignore_index and not meaningful)
    assert result.inputs[0].index is not None
    if result.complete:
        assert migration.inputs[0].index is not None
        assert migration.inputs[0].index.sha256 == result.inputs[0].index.sha256
        assert migration.inputs[0].notes == result.inputs[0].notes
        assert migration.inputs[0].origin == result.inputs[0].data
    else:
        assert result.checkpoints[0].state == "not_evaluable"
        assert migration.stages[1].code == "unsupported_capability"
    assert read_workflow(tmp_path / "workflow" / result.run_id) == result


def test_checkpoint_source_index_is_not_dropped_from_next_stage(tmp_path):
    first = stage("first")
    second = stage("second", "first")
    second = second.model_copy(
        update={"inputs": (second.inputs[0].model_copy(update={"output": "source"}),)}
    )
    result = run_workflow(
        WorkflowSpec(workflow_id="source_index", stages=(first, second)),
        source=CountingSource(),
        work_dir=tmp_path,
    )
    assert result.complete
    source_output = result.checkpoints[0].migration.source.execution.output
    next_input = result.checkpoints[1].migration.inputs[0]
    assert source_output.index is not None and next_input.index is not None
    assert next_input.index.sha256 == source_output.index.sha256
    assert next_input.origin == source_output.data
    assert next_input.notes == source_output.notes
    assert read_workflow(tmp_path / result.run_id) == result


@pytest.mark.parametrize("broken_name", ["a_broken", "z_broken"])
def test_unavailable_external_input_only_skips_its_dependents(tmp_path, broken_name):
    class PartialSource:
        table_names = (broken_name, "good")

        def __init__(self):
            self.calls = []

        def resolve(self, name, *, context):
            self.calls.append(name)
            if name == broken_name:
                raise ValueError("Synthetic source unavailable")
            return ef.ArrowInput(pa.table({"n": [1, 2]})).load(context)

    source = PartialSource()
    bad = stage("bad").model_copy(
        update={"inputs": (InputBinding(name="input", source=broken_name),)}
    )
    good = stage("good").model_copy(update={"inputs": (InputBinding(name="input", source="good"),)})
    result = run_workflow(
        WorkflowSpec(workflow_id="isolated", stages=(bad, stage("dependent", "bad"), good)),
        source=source,
        work_dir=tmp_path,
    )
    assert sorted(source.calls) == sorted(source.table_names)
    assert [checkpoint.state for checkpoint in result.checkpoints] == [
        "skipped",
        "skipped",
        "passed",
    ]
    assert result.checkpoints[0].code == "ValueError"
    assert result.checkpoints[1].code == "dependency_not_approved"
    assert not result.complete and result.exit_code == 3
    assert set(result.outputs) == {"good"}
    assert read_workflow(tmp_path / result.run_id) == result


def test_unavailable_expected_only_skips_its_stage_and_dependents(tmp_path):
    expected = reference(pa.table({"n": [1, 2]}), tmp_path / "expected.arrow")
    expected = expected.model_copy(update={"sha256": "0" * 64})
    result = run_workflow(
        WorkflowSpec(
            workflow_id="expected_isolation",
            stages=(stage("bad"), stage("dependent", "bad"), stage("independent")),
        ),
        source=CountingSource(),
        expected={"bad": expected},
        work_dir=tmp_path,
    )
    assert [checkpoint.state for checkpoint in result.checkpoints] == [
        "skipped",
        "skipped",
        "passed",
    ]
    assert result.checkpoints[0].code == "ArtifactIntegrityError"
    assert not result.complete and result.exit_code == 3
    assert set(result.outputs) == {"independent"}
    assert read_workflow(tmp_path / result.run_id) == result


@pytest.mark.parametrize("limit", ["rows", "bytes", "capture_rows", "capture_bytes"])
@pytest.mark.parametrize("shared", [False, True])
def test_capture_budgets_follow_consumers_and_keep_stage_limits(tmp_path, limit, shared):
    class SizedSource:
        table_names = ("small", "large")

        def __init__(self):
            self.calls = []

        def resolve(self, name, *, context):
            self.calls.append(name)
            values = [1] if name == "small" else list(range(200)) if limit == "bytes" else [1, 2]
            return ef.ArrowInput(pa.table({"n": values})).load(context)

    def limited(stage_id, source, size):
        planned = stage(stage_id)
        options_field = "options" if limit.startswith("capture_") else "execution_options"
        field = {
            "rows": "max_input_rows",
            "bytes": "max_transport_bytes",
            "capture_rows": "max_capture_rows",
            "capture_bytes": "max_capture_bytes",
        }[limit]
        migration = planned.migration.model_copy(
            update={
                options_field: getattr(planned.migration, options_field).model_copy(
                    update={field: size}
                )
            }
        )
        return planned.model_copy(
            update={
                "migration": migration,
                "inputs": (InputBinding(name="input", source=source),),
            }
        )

    strict_limit, loose_limit = (
        (1024, 8192) if limit == "bytes" else (8, 80) if limit == "capture_bytes" else (1, 10)
    )
    strict = limited("strict", "large" if shared else "small", strict_limit)
    loose = limited("loose", "large", loose_limit)
    source = SizedSource()
    result = run_workflow(
        WorkflowSpec(workflow_id="budget_isolation", stages=(strict, loose)),
        source=source,
        work_dir=tmp_path,
    )
    assert sorted(source.calls) == (["large"] if shared else ["large", "small"])
    assert result.checkpoints[1].state == "passed"
    assert result.checkpoints[0].state == ("not_evaluable" if shared else "passed")
    if shared:
        assert result.checkpoints[0].migration.stages[1].code == "resource_exhausted"
        assert not result.complete and result.exit_code == 3
    else:
        assert result.complete
    assert read_workflow(tmp_path / result.run_id) == result


def test_decoded_capture_budget_is_not_used_as_serialized_file_limit(tmp_path):
    data = pa.table({"n": [1]})
    artifact = reference(data, tmp_path / "input.arrow")
    assert artifact.size_bytes > data.nbytes
    planned = stage("tiny")
    planned = planned.model_copy(
        update={
            "migration": planned.migration.model_copy(
                update={"options": ef.MigrationOptions(max_capture_bytes=data.nbytes)}
            )
        }
    )
    direct = ef.migrate(
        planned.migration,
        source=ef.LocalDataSource({"input": artifact}),
        work_dir=tmp_path / "direct",
    )
    result = run_workflow(
        WorkflowSpec(workflow_id="serialized_overhead", stages=(planned,)),
        source=ef.LocalDataSource({"original": artifact}),
        work_dir=tmp_path / "workflow",
    )
    assert direct.exit_code == 0
    assert result.complete and result.exit_code == 0
    assert read_workflow(tmp_path / "workflow" / result.run_id) == result


def test_failed_migration_retains_and_reads_partial_input_capture(tmp_path):
    planned = stage("partial")
    original = planned.migration.contract.inputs[0]
    schema = planned.migration.contract.model_copy(
        update={
            "inputs": (
                original.model_copy(update={"name": "left"}),
                original.model_copy(update={"name": "right"}),
            )
        }
    )
    plan = RelationalPlan(
        nodes=(
            Scan(node_id="left", table="left"),
            Scan(node_id="right", table="right"),
            ef.Concatenate(node_id="both", sources=("left", "right")),
        ),
        output="both",
    )
    planned = planned.model_copy(
        update={
            "migration": planned.migration.model_copy(update={"contract": schema, "ir": plan}),
            "inputs": (
                InputBinding(name="left", source="left"),
                InputBinding(name="right", source="right"),
            ),
        }
    )
    result = run_workflow(
        WorkflowSpec(workflow_id="partial_input", stages=(planned,)),
        source=ef.LocalDataSource(
            {
                "left": ef.ArrowInput(pa.table({"n": [1]})),
                "right": ef.PandasInput(pd.DataFrame({"n": [2]}, index=["business-id"])),
            }
        ),
        work_dir=tmp_path,
    )
    assert not result.complete and result.exit_code == 3
    checkpoint = result.checkpoints[0]
    assert checkpoint.state == "not_evaluable"
    assert checkpoint.migration is not None
    assert [table.name for table in checkpoint.migration.inputs] == ["left"]
    assert checkpoint.migration.stages[1].code == "unsupported_capability"
    assert read_workflow(tmp_path / result.run_id) == result


@pytest.mark.parametrize("invalid", [False, 0, [], (), ""])
def test_invalid_expected_mapping_fails_before_capture(tmp_path, invalid):
    source = CountingSource()
    with pytest.raises(TypeError, match="expected must be a mapping"):
        run_workflow(
            WorkflowSpec(workflow_id="expected_mapping", stages=(stage("one"),)),
            source=source,
            expected=invalid,
            work_dir=tmp_path,
        )
    assert source.calls == 0
    assert not list(tmp_path.iterdir())


def test_empty_expected_mapping_keeps_expected_verification_unrequested(tmp_path):
    result = run_workflow(
        WorkflowSpec(workflow_id="empty_expected", stages=(stage("one"),)),
        source=CountingSource(),
        expected={},
        work_dir=tmp_path,
    )
    assert result.complete
    assert result.checkpoints[0].migration.verification == "not_requested"
