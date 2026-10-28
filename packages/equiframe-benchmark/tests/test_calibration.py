"""Synthetic selection tests, never independent human scientific reviews."""

import equiframe as ef
import pytest
from test_selection import selection_data
from test_splits import independent_scenario

import equiframe_benchmark as eb


def partitioned(make_case, tmp_path, partition):
    catalog, _, kwargs = selection_data(make_case, tmp_path)
    scenario = catalog.scenarios[0]
    others = tuple(independent_scenario(scenario, i, (f"independent:{i}",)) for i in range(5))
    catalog = catalog.model_copy(update={"scenarios": (scenario, *others)})
    for seed in range(100):
        splits = eb.make_splits(catalog, seed=seed, weights=(3, 1, 2))
        if any(
            a.scenario_id == scenario.scenario_id and a.partition == partition
            for a in splits.assignments
        ):
            return catalog, splits, kwargs
    pytest.fail("partition fixture not found")


def test_reviewed_calibration_roundtrip_and_profile_only_boundary(make_case, tmp_path):
    catalog, splits, kwargs = partitioned(make_case, tmp_path, "calibration")
    selected = eb.select_normal_calibration(catalog, splits, **kwargs)
    assert selected.calibration.purpose == "normal_calibration"
    assert selected.calibration.selection_manifest_sha256 == eb.digest(selected.manifest)
    eb.save_document(selected, tmp_path / "calibration.json")
    assert eb.load_document(eb.CalibrationSelection, tmp_path / "calibration.json") == selected
    with pytest.raises(ValueError, match="only training"):
        eb.select_normal_training(catalog, splits, **kwargs)
    with pytest.raises(ValueError):
        ef.fit_preprocessor(selected.calibration, spec=selected.calibration.profiles[0].spec)


@pytest.mark.parametrize("partition", ["training", "test"])
def test_non_calibration_splits_never_calibrate(make_case, tmp_path, partition):
    catalog, splits, kwargs = partitioned(make_case, tmp_path, partition)
    with pytest.raises(ValueError, match="only calibration"):
        eb.select_normal_calibration(catalog, splits, **kwargs)


@pytest.mark.parametrize("fault", ["pending", "wrong_execution", "missing_artifact", "wrong_spec"])
def test_calibration_rejects_invalid_lineage(make_case, tmp_path, fault):
    catalog, splits, kwargs = partitioned(make_case, tmp_path, "calibration")
    key = next(iter(kwargs["profiles"]))
    if fault == "pending":
        kwargs["oracles"][key] = kwargs["oracles"][key].model_copy(
            update={"status": "pending", "label": None, "reviews": ()}
        )
    else:
        p = kwargs["profiles"][key]
        if fault == "wrong_spec":
            kwargs["profiles"][key] = p.model_copy(
                update={"vector": p.vector.model_copy(update={"spec_sha256": "f" * 64})}
            )
        else:
            update = (
                {"execution_sha256": "f" * 64} if fault == "wrong_execution" else {"artifacts": ()}
            )
            kwargs["profiles"][key] = p.model_copy(
                update={"metadata": p.metadata.model_copy(update=update)}
            )
    with pytest.raises(ValueError):
        eb.select_normal_calibration(catalog, splits, **kwargs)


def pair_fixture(make_case, tmp_path):
    # Declarative audit fixtures: selection lineage is tested against actual artifacts above.
    catalog, splits, kwargs = selection_data(make_case, tmp_path)
    selected = eb.select_normal_training(catalog, splits, **kwargs)
    record = selected.manifest.records[0].model_copy(
        update={
            "scenario_id": "calibration.scenario",
            "candidate_id": "calibration.candidate",
            "group_id": "c" * 64,
            "execution_sha256": "d" * 64,
            "profile_sha256": "e" * 64,
        }
    )
    manifest = eb.CalibrationManifest(
        catalog_sha256=selected.manifest.catalog_sha256,
        splits_sha256=selected.manifest.splits_sha256,
        records=(record,),
    )
    calibration = eb.CalibrationSelection(
        manifest=manifest,
        calibration=ef.NormalCalibrationProfiles(
            purpose="normal_calibration",
            selection_manifest_sha256=eb.digest(manifest),
            profiles=selected.training.profiles,
        ),
    )
    return selected, calibration


def test_group_support_does_not_confuse_profile_equality_with_leakage(make_case, tmp_path):
    t, c = pair_fixture(make_case, tmp_path)
    audit = eb.audit_detector_selections(
        t, c, min_training_groups=2, min_calibration_groups=2, rationale="test minima"
    )
    assert audit.training_groups == audit.calibration_groups == 1
    assert audit.state == "not_estimable"
    assert (
        eb.audit_detector_selections(
            t, c, min_training_groups=1, min_calibration_groups=1, rationale="test only"
        ).state
        == "eligible"
    )


@pytest.mark.parametrize(
    "field",
    [
        "group_id",
        "scenario_id",
        "candidate_id",
        "execution_sha256",
        "profile_sha256",
    ],
)
def test_pair_rejects_shared_group_or_execution(make_case, tmp_path, field):
    t, c = pair_fixture(make_case, tmp_path)
    record = c.manifest.records[0].model_copy(update={field: getattr(t.manifest.records[0], field)})
    manifest = c.manifest.model_copy(update={"records": (record,)})
    c = c.model_copy(
        update={
            "manifest": manifest,
            "calibration": c.calibration.model_copy(
                update={"selection_manifest_sha256": eb.digest(manifest)}
            ),
        }
    )
    with pytest.raises(ValueError, match="leakage"):
        eb.audit_detector_selections(
            t, c, min_training_groups=1, min_calibration_groups=1, rationale="test"
        )


def test_changed_catalog_or_replaced_vectors_rejected(make_case, tmp_path):
    t, c = pair_fixture(make_case, tmp_path)
    manifest = c.manifest.model_copy(update={"catalog_sha256": "f" * 64})
    changed = c.model_copy(
        update={
            "manifest": manifest,
            "calibration": c.calibration.model_copy(
                update={"selection_manifest_sha256": eb.digest(manifest)}
            ),
        }
    )
    with pytest.raises(ValueError, match="same catalog"):
        eb.audit_detector_selections(
            t, changed, min_training_groups=1, min_calibration_groups=1, rationale="test"
        )
    with pytest.raises(ValueError, match="size"):
        eb.CalibrationSelection.model_validate(
            c.model_copy(
                update={
                    "calibration": c.calibration.model_copy(update={"profiles": ()}),
                }
            )
        )
