"""Only explicit boolean False selects a metadata-only evidence read."""

from decimal import Decimal

import pytest
from test_migration import run as run_migration
from test_pipeline import run as run_pipeline
from test_workflow import CountingSource, stage

import equiframe as ef


class TruthMustNotRun:
    def __bool__(self):
        raise AssertionError("invalid verification option was truth-tested")


@pytest.fixture(scope="module", params=["pipeline", "migration", "workflow"])
def recorded_operation(request, tmp_path_factory):
    kind = request.param
    root = tmp_path_factory.mktemp(f"strict-{kind}-reader-flag")
    if kind == "pipeline":
        result = run_pipeline(root)
        directory = root / result.pipeline_id
        reader, config = ef.read_pipeline, "pipeline.json"
    elif kind == "migration":
        result = run_migration(root)
        directory = root / result.migration_id
        reader, config = ef.read_migration, "spec.json"
    else:
        result = ef.run_workflow(
            ef.WorkflowSpec(workflow_id="reader-flags", stages=(stage("one"),)),
            source=CountingSource(),
            work_dir=root,
        )
        directory = root / result.run_id
        reader, config = ef.read_workflow, "workflow-spec.json"
    assert result.complete and reader(directory) == result
    return reader, directory, config, result


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        0.0,
        1.0,
        None,
        "",
        "false",
        "true",
        [],
        {},
        (),
        Decimal(0),
        object(),
        TruthMustNotRun(),
    ],
    ids=[
        "int-zero",
        "int-one",
        "float-zero",
        "float-one",
        "none",
        "empty-text",
        "false-text",
        "true-text",
        "list",
        "dict",
        "tuple",
        "decimal",
        "object",
        "truth-hook",
    ],
)
def test_non_boolean_verification_options_are_rejected(recorded_operation, value):
    reader, directory, _, _ = recorded_operation
    with pytest.raises(TypeError, match="verify must be a bool"):
        reader(directory, verify=value)


def test_only_explicit_false_can_skip_corrupt_evidence(recorded_operation):
    reader, directory, config, original = recorded_operation
    path = directory / config
    before = path.read_bytes()
    try:
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(ef.ArtifactIntegrityError):
            reader(directory, verify=True)
        # Metadata retains the producer's decision; this call does not prove integrity.
        assert reader(directory, verify=False) == original
        with pytest.raises(TypeError, match="verify must be a bool"):
            reader(directory, verify=0)
    finally:
        path.write_bytes(before)
    assert reader(directory, verify=True) == original


@pytest.mark.parametrize("reader", [ef.read_pipeline, ef.read_migration, ef.read_workflow])
def test_invalid_flag_is_rejected_before_missing_evidence_io(tmp_path, reader):
    with pytest.raises(TypeError, match="verify must be a bool"):
        reader(tmp_path / "missing", verify=None)
