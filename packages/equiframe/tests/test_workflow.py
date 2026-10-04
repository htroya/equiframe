"""Workflow fixes inputs once, binds checkpoints, and propagates failed dependencies."""

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
