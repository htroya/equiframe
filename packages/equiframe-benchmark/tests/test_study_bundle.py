"""Relocation, exact quantities and rehashed tampering of portable study fixtures."""

import hashlib
import json

import equiframe as ef
import pytest
from test_freeze import native_definition

from equiframe_benchmark.fixtures import registry
from equiframe_benchmark.freeze import create_freeze
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.reproduction import ReproductionBundle, bundle_artifact
from equiframe_benchmark.study import run_study
from equiframe_benchmark.study_bundle import (
    _original_uri,
    bundle_study,
    reproduce_study_bundle,
)


@pytest.fixture(scope="module")
def portable(tmp_path_factory):
    root = tmp_path_factory.mktemp("portable")
    producer = root / "producer"
    producer.mkdir()
    definition = native_definition(producer / "data")
    definition = definition.model_copy(
        update={
            "cases": tuple(
                case.model_copy(
                    update={
                        "pipeline": case.pipeline.model_copy(
                            update={
                                "comparison_options": ef.ComparisonOptions(
                                    batch_rows=2, partitions=3, max_examples=0
                                )
                            }
                        )
                    }
                )
                for case in definition.cases
            )
        }
    )
    frozen = create_freeze(definition)
    result = run_study(frozen, registry=registry(), work_dir=producer)
    output = root / "portable"
    bundle = bundle_study(producer / result.study_id, output=output)
    original = definition.cases[0].candidate.output
    # No original input/output/provenance path remains available at its saved URI.
    producer.rename(root / "producer-relocated")
    return output, bundle, original


def test_relocation_regenerates_all_components_without_original_sources(portable):
    output, bundle, original = portable
    anchor = hashlib.sha256((output / "bundle.json").read_bytes()).hexdigest()
    receipt = reproduce_study_bundle(output, expected_sha256=anchor)
    assert receipt.status == "reproduced" and all(c.identical for c in receipt.components)
    assert json.loads(receipt.repeated.tables)["csv"].keys() == {
        "coverage.csv",
        "metrics.csv",
        "average_precision.csv",
        "incremental.csv",
        "bootstrap.csv",
        "cases.csv",
    }
    table = ef.read_table(bundle_artifact(bundle, output, original))
    assert all(str(value) == "10.20" for value in table.column("amount").to_pylist())


def test_portable_replay_preserves_frozen_comparison_options_and_role(portable, monkeypatch):
    from equiframe_benchmark.study import StudyResult

    output, _, _ = portable
    captured = load_document(StudyResult, output / "study" / "study.json")
    original_compare = ef.compare
    replays = []

    def captured_compare(*args, **kwargs):
        compared = original_compare(*args, **kwargs)
        replays.append(compared)
        return compared

    monkeypatch.setattr(ef, "compare", captured_compare)
    receipt = reproduce_study_bundle(output)
    assert receipt.status == "reproduced"
    confirmed = tuple(case for case in captured.cases if case.record.oracle_state == "confirmed")
    assert len(replays) == len(confirmed) > 0
    for replay, case in zip(replays, confirmed, strict=True):
        assert replay.options == case.output_replay.options
        assert replay.reference == case.output_replay.reference == "peer"
        assert replay.counts == case.output_replay.counts


def test_rehashed_csv_tampering_contradicts_original_study_inventory(portable, tmp_path):
    import shutil

    original, _, _ = portable
    output = tmp_path / "changed"
    shutil.copytree(original, output)
    path = output / "study" / "tables" / "metrics.csv"
    path.write_bytes(path.read_bytes() + b"forged,row\n")
    bundle = load_document(ReproductionBundle, output / "bundle.json")
    files = tuple(
        type(item).model_validate(
            {
                **item.model_dump(mode="python"),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
        )
        if item.path == "study/tables/metrics.csv"
        else item
        for item in bundle.files
    )
    (output / "bundle.json").unlink()
    save_document(
        type(bundle).model_validate({**bundle.model_dump(mode="python"), "files": files}),
        output / "bundle.json",
    )
    with pytest.raises(ValueError, match="original study inventory"):
        reproduce_study_bundle(output)


def test_original_windows_paths_are_not_resolved_on_foreign_host():
    assert _original_uri("C:\\producer\\code.py") == "file:///C:/producer/code.py"
    assert _original_uri("/var/data/code.py") == "file:///var/data/code.py"


@pytest.mark.parametrize("document", ("audit-before.json", "evaluation.json"))
def test_rehashed_original_document_cannot_contradict_embedded_study(portable, tmp_path, document):
    import shutil

    from equiframe_benchmark.evaluation import EvaluationReport, evaluate_records
    from equiframe_benchmark.freeze import FreezeAudit
    from equiframe_benchmark.reproduction import read_bundle
    from equiframe_benchmark.study import StudyResult

    original, _, _ = portable
    output = tmp_path / "contradictory-source"
    shutil.copytree(original, output)
    path = output / "study" / document
    if document == "audit-before.json":
        audit = load_document(FreezeAudit, path)
        count = audit.counts[0].model_copy(update={"scenarios": audit.counts[0].scenarios + 1})
        changed = audit.model_copy(update={"counts": (count, *audit.counts[1:])})
    else:
        report = load_document(EvaluationReport, path)
        config = report.config.model_copy(
            update={
                "bootstrap": report.config.bootstrap.model_copy(
                    update={"seed": report.config.bootstrap.seed + 1}
                )
            }
        )
        changed = evaluate_records(report.records, config)
    path.unlink()
    save_document(changed, path)
    study_path = output / "study" / "study.json"
    captured = load_document(StudyResult, study_path)
    evidence = tuple(
        item.model_copy(
            update={
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size,
            }
        )
        if item.path == document
        else item
        for item in captured.evidence
    )
    changed_study = captured.model_copy(update={"evidence": evidence})
    study_path.unlink()
    save_document(changed_study, study_path)
    manifest_path = output / "bundle.json"
    bundle = load_document(ReproductionBundle, manifest_path)
    changed_names = {"study/" + document, "study/study.json"}
    files = tuple(
        item.model_copy(
            update={
                "sha256": hashlib.sha256((output / item.path).read_bytes()).hexdigest(),
                "size_bytes": (output / item.path).stat().st_size,
            }
        )
        if item.path in changed_names
        else item
        for item in bundle.files
    )
    manifest_path.unlink()
    save_document(bundle.model_copy(update={"files": files}), manifest_path)
    # Both byte inventories are consistent; only the original document disagrees.
    assert read_bundle(output).files == files
    with pytest.raises(ValueError, match="source document contradicts"):
        reproduce_study_bundle(output)


def test_study_record_budget_is_checked_before_json_model_loading(portable, monkeypatch):
    import equiframe_benchmark.study_bundle as module
    from equiframe_benchmark.reproduction import BundleLimits

    output, _, _ = portable
    maximum = 32
    monkeypatch.setattr(module, "BundleLimits", lambda: BundleLimits(max_record_bytes=maximum))
    with pytest.raises(ef.ResourceLimitError, match="JSON exceeds byte budget"):
        reproduce_study_bundle(output)


def test_rehashed_replay_observations_must_match_actual_portable_rows(portable, tmp_path):
    import shutil

    from equiframe_benchmark.reproduction import read_bundle
    from equiframe_benchmark.study import StudyResult

    original, bundle, _ = portable
    output = tmp_path / "forged-replay-counts"
    shutil.copytree(original, output)
    path = output / "study" / "study.json"
    study = load_document(StudyResult, path)
    case = study.cases[0]
    replay = case.output_replay
    assert case.record.oracle_state == "confirmed" and replay.state == "equivalent"
    # Change the whole receipt chain coherently while preserving the actual rows.
    # Hash integrity alone must not authorize invented replay observations.
    counts = replay.counts.model_copy(
        update={
            "left_rows": replay.counts.left_rows + 1,
            "right_rows": replay.counts.right_rows + 1,
            "matched_rows": replay.counts.matched_rows + 1,
        }
    )
    # STEP4 rejects count contradictions against retained capture metadata before
    # a forged document can enter the portable receipt chain.
    with pytest.raises(ValueError, match="final row count differs from captured table metadata"):
        ef.ComparisonResult.model_validate(replay.model_copy(update={"counts": counts}))
    # Keep the deeper rehashed-chain attack: a structurally valid but invented
    # alignment observation must still be checked against the actual replay.
    # The output/capture bindings and recorded rows remain intact.
    invented_strategy = "multiset" if replay.strategy != "multiset" else "sequence"
    replay = ef.ComparisonResult.model_validate(
        replay.model_copy(update={"strategy": invented_strategy, "selected_key": None})
    )
    case = case.model_copy(update={"output_replay": replay})
    replay_uri = replay.differences.uri.rsplit("/", 1)[0] + "/comparison.json"
    replay_file = next(item for item in bundle.files if item.source_uri == replay_uri)
    changed = {
        replay_file.path: replay,
        "study/case-0/case.json": case,
    }
    for name, document in changed.items():
        target = output / name
        target.unlink()
        save_document(document, target)
    evidence = tuple(
        item.model_copy(
            update={
                "sha256": hashlib.sha256((output / "study" / item.path).read_bytes()).hexdigest(),
                "size_bytes": (output / "study" / item.path).stat().st_size,
            }
        )
        if "study/" + item.path in changed
        else item
        for item in study.evidence
    )
    forged = study.model_copy(update={"cases": (case, *study.cases[1:]), "evidence": evidence})
    path.unlink()
    save_document(forged, path)
    changed["study/study.json"] = forged
    files = tuple(
        item.model_copy(
            update={
                "sha256": hashlib.sha256((output / item.path).read_bytes()).hexdigest(),
                "size_bytes": (output / item.path).stat().st_size,
            }
        )
        if item.path in changed
        else item
        for item in bundle.files
    )
    manifest = output / "bundle.json"
    manifest.unlink()
    save_document(bundle.model_copy(update={"files": files}), manifest)
    assert read_bundle(output).files == files
    with pytest.raises(ValueError, match="replay observations differ from actual captured rows"):
        reproduce_study_bundle(output)
