"""Portable bytes, closed inventories and no ETL execution during read/import."""

import hashlib
import json

import pytest
from test_migration import run, table
from test_verify import artifact

import equiframe as ef
from equiframe.bundle import export_bundle, import_bundle, inspect_bundle, read_bundle
from equiframe.verify import verify


def test_migration_bundle_survives_relocation_without_original(tmp_path):
    result = run(tmp_path / "runs", expected=ef.ArrowInput(table()))
    operation = tmp_path / "runs" / result.migration_id
    original = (operation / "migration.json").read_bytes()
    bundle = export_bundle(operation, tmp_path / "portable")
    digest = hashlib.sha256((tmp_path / "portable" / "bundle.json").read_bytes()).hexdigest()
    operation.rename(tmp_path / "hidden_original")
    imported = import_bundle(tmp_path / "portable", tmp_path / "moved", expected_sha256=digest)
    assert imported == bundle
    assert (tmp_path / "moved" / "operation" / "migration.json").read_bytes() == original
    assert read_bundle(tmp_path / "moved", expected_sha256=digest) == bundle


def test_verification_bundle_survives_relocation(tmp_path):
    ref = artifact(tmp_path, "external", table())
    result = verify(
        {"one": ref},
        contract=__import__("test_migration").contract(),
        expected=ref,
        work_dir=tmp_path,
    )
    operation = tmp_path / result.verification_id
    bundle = export_bundle(operation, tmp_path / "portable")
    operation.rename(tmp_path / "hidden_original")
    (tmp_path / "external.arrow").unlink()
    assert import_bundle(tmp_path / "portable", tmp_path / "moved") == bundle


@pytest.mark.parametrize(
    "fault", ["extra", "corrupt", "traversal", "outside_reference", "wrong_root"]
)
def test_closed_bundle_rejects_faults(tmp_path, fault):
    result = run(tmp_path / "runs")
    root = tmp_path / "portable"
    bundle = export_bundle(tmp_path / "runs" / result.migration_id, root)
    manifest = root / "bundle.json"
    if fault == "extra":
        (root / "extra.json").write_text("{}", encoding="utf-8")
    elif fault == "corrupt":
        (root / bundle.root_document).write_text("{}", encoding="utf-8")
    else:
        data = json.loads(manifest.read_bytes())
        if fault == "traversal":
            data["files"][0]["path"] = "../outside.json"
        elif fault == "outside_reference":
            data["references"][0]["uri"] = (tmp_path / "outside.arrow").as_uri()
        else:
            data["root_document"] = "../outside.json"
        manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises((ValueError, ef.ArtifactIntegrityError)):
        read_bundle(root)


def test_context_is_restored_after_bundle_failure(tmp_path):
    result = run(tmp_path / "runs")
    root = tmp_path / "portable"
    export_bundle(tmp_path / "runs" / result.migration_id, root)
    (root / "operation" / "report.html").write_text("broken", encoding="utf-8")
    with pytest.raises(ef.ArtifactIntegrityError):
        read_bundle(root)
    assert ef.read_table(result.source.execution.output.data).num_rows == 3


def test_bundle_inspection_retains_semantic_failure_and_executes_no_callbacks(
    tmp_path, monkeypatch
):
    wrong = artifact(
        tmp_path,
        "wrong",
        __import__("pyarrow").table({"id": [99, 99, 99], "value": ["a", None, "c"]}),
    )
    expected = artifact(tmp_path, "expected", table())
    result = verify(
        {"one": wrong},
        contract=__import__("test_migration").contract(),
        expected=expected,
        work_dir=tmp_path,
    )
    root = tmp_path / "portable"
    export_bundle(tmp_path / result.verification_id, root)

    def prohibited(*args, **kwargs):
        raise AssertionError("portable inspection must not execute callbacks")

    monkeypatch.setattr("equiframe.migration.runner.migrate", prohibited)
    monkeypatch.setattr("equiframe.pipeline.run_pipeline", prohibited)
    summary = inspect_bundle(root)
    assert summary["integrity"] == "passed"
    assert summary["outcome"]["operational_state"] == "failed"


def test_symlink_is_rejected_when_platform_allows_creation(tmp_path):
    result = run(tmp_path / "runs")
    root = tmp_path / "portable"
    export_bundle(tmp_path / "runs" / result.migration_id, root)
    try:
        (root / "link").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("Windows account cannot create symlinks")
    with pytest.raises(ef.ArtifactIntegrityError):
        read_bundle(root)


def test_multistage_workflow_bundle_survives_relocation(tmp_path):
    from test_workflow import CountingSource, stage

    from equiframe.workflow import WorkflowSpec, run_workflow

    result = run_workflow(
        WorkflowSpec(
            workflow_id="portable.workflow", stages=(stage("first"), stage("second", "first"))
        ),
        source=CountingSource(),
        work_dir=tmp_path / "runs",
    )
    operation = tmp_path / "runs" / result.run_id
    original = (operation / "workflow.json").read_bytes()
    root = tmp_path / "portable"
    export_bundle(operation, root)
    operation.rename(tmp_path / "hidden_original")
    import_bundle(root, tmp_path / "relocated")
    inspected = inspect_bundle(tmp_path / "relocated")
    assert inspected["outcome"]["complete"]
    assert inspected["outcome"]["exit_code"] == 0
    assert (tmp_path / "relocated" / "operation" / "workflow.json").read_bytes() == original
