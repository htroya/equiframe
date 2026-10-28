import equiframe as ef
import pytest
from conftest import oracle
from test_splits import independent_scenario

import equiframe_benchmark as eb


def selection_data(make_case, tmp_path):
    data = make_case(native=True)
    s, c, _p, _a, e, profile = data
    result = oracle(data, tmp_path)
    catalog = eb.Catalog(catalog_id="test", synthetic=True, scenarios=(s,))
    splits = eb.make_splits(catalog, seed=3, weights=(3, 1, 2))
    kwargs = dict(
        candidates={c.candidate_id: c},
        oracles={c.candidate_id: result},
        profiles={c.candidate_id: profile},
        executions={c.candidate_id: e},
    )
    return catalog, splits, kwargs


def test_reviewed_selection_supplies_only_vectors(make_case, tmp_path):
    catalog, splits, kwargs = selection_data(make_case, tmp_path)
    selected = eb.select_normal_training(catalog, splits, **kwargs)
    eb.save_document(selected, tmp_path / "selection.json")
    assert eb.load_document(eb.TrainingSelection, tmp_path / "selection.json") == selected
    bundle = ef.fit_preprocessor(selected.training, spec=selected.training.profiles[0].spec)
    matrix = ef.transform_profiles(bundle, selected.training.profiles)
    assert len(matrix.values) == 1
    for forbidden in (
        "test-reviewer",
        "candidate_id",
        "scenario_id",
        '"normal"',
        "duckdb",
        "partition",
    ):
        assert forbidden not in matrix.model_dump_json()
    assert selected.training.selection_manifest_sha256 == eb.digest(selected.manifest)


def test_selection_vector_substitution_rejected(make_case, tmp_path):
    catalog, splits, kwargs = selection_data(make_case, tmp_path)
    selected = eb.select_normal_training(catalog, splits, **kwargs)
    record = selected.manifest.records[0].model_copy(update={"vector_sha256": "f" * 64})
    manifest = selected.manifest.model_copy(update={"records": (record,)})
    training = selected.training.model_copy(
        update={"selection_manifest_sha256": eb.digest(manifest)}
    )
    with pytest.raises(ValueError, match="vectors"):
        eb.TrainingSelection(manifest=manifest, training=training)


@pytest.mark.parametrize("partition", ("training", "calibration"))
def test_selection_rejects_hash_valid_difference_inventory_contradicting_o(
    make_case, tmp_path, partition
):
    catalog, splits, kwargs = selection_data(make_case, tmp_path)
    if partition == "calibration":
        scenario = catalog.scenarios[0]
        others = tuple(independent_scenario(scenario, i, (f"isolated:{i}",)) for i in range(5))
        catalog = catalog.model_copy(update={"scenarios": (scenario, *others)})
        for seed in range(100):
            splits = eb.make_splits(catalog, seed=seed, weights=(3, 1, 2))
            if any(
                a.scenario_id == scenario.scenario_id and a.partition == partition
                for a in splits.assignments
            ):
                break
        else:
            pytest.fail("test fixture did not produce the intended calibration partition")
    key = next(iter(kwargs["candidates"]))
    scenario = catalog.scenarios[0]
    expected = ef.read_table(scenario.expected)
    different = ef.compare(
        ef.ArrowInput(expected.slice(0, expected.num_rows - 1)),
        scenario.expected,
        contract=scenario.comparison.contract,
        policy=scenario.comparison.policy,
        reference="expected",
        work_dir=tmp_path,
    )
    assert different.state == "different" and different.counts.difference_records > 0
    original = kwargs["oracles"][key]
    kwargs["oracles"][key] = eb.OracleResult.model_validate(
        original.model_copy(
            update={
                "comparison": original.comparison.model_copy(
                    update={"differences": different.differences}
                )
            }
        )
    )
    selector = (
        eb.select_normal_training if partition == "training" else eb.select_normal_calibration
    )
    with pytest.raises(
        ValueError, match="oracle difference inventory disagrees with recorded counts"
    ):
        selector(catalog, splits, **kwargs)


@pytest.mark.parametrize(
    "fault",
    (
        "pending",
        "foreign_execution",
        "missing_output",
        "spec",
        "implementation",
        "input",
        "keys",
        "corrupt",
    ),
)
def test_selection_rejects_untrusted_lineage(make_case, tmp_path, fault):
    catalog, splits, kwargs = selection_data(make_case, tmp_path)
    key = next(iter(kwargs["candidates"]))
    if fault == "pending":
        o = kwargs["oracles"][key]
        kwargs["oracles"][key] = o.model_copy(
            update={"status": "pending", "label": None, "reviews": ()}
        )
    if fault in ("foreign_execution", "missing_output", "spec"):
        p = kwargs["profiles"][key]
        if fault == "spec":
            vector = p.vector.model_copy(update={"spec_sha256": "f" * 64})
            kwargs["profiles"][key] = p.model_copy(update={"vector": vector})
        else:
            update = (
                {"execution_sha256": "f" * 64}
                if fault == "foreign_execution"
                else {"artifacts": ()}
            )
            kwargs["profiles"][key] = p.model_copy(
                update={"metadata": p.metadata.model_copy(update=update)}
            )
    if fault == "implementation":
        e = kwargs["executions"][key]
        kwargs["executions"][key] = e.model_copy(update={"implementation_version": "wrong"})
    if fault == "input":
        e = kwargs["executions"][key]
        first = e.inputs[0]
        changed = first.data.model_copy(update={"sha256": "f" * 64})
        kwargs["executions"][key] = e.model_copy(
            update={"inputs": (first.model_copy(update={"data": changed}),)}
        )
    if fault == "keys":
        kwargs["profiles"] = {}
    if fault == "corrupt":
        from equiframe.local import local_path

        local_path(kwargs["candidates"][key].output).write_bytes(b"corrupt")
    with pytest.raises((ValueError, ef.EquiFrameError)):
        eb.select_normal_training(catalog, splits, **kwargs)


@pytest.mark.parametrize("partition", ("test", "calibration"))
def test_test_and_calibration_never_enter_fit(make_case, tmp_path, partition):
    catalog, _, kwargs = selection_data(make_case, tmp_path)
    scenario = catalog.scenarios[0]
    others = tuple(independent_scenario(scenario, i, (f"isolated:{i}",)) for i in range(5))
    catalog = catalog.model_copy(update={"scenarios": (scenario, *others)})
    for seed in range(100):
        splits = eb.make_splits(catalog, seed=seed, weights=(3, 1, 2))
        if any(
            a.scenario_id == scenario.scenario_id and a.partition == partition
            for a in splits.assignments
        ):
            break
    else:
        pytest.fail("test fixture did not produce the intended held-out partition")
    with pytest.raises(ValueError, match="only training"):
        eb.select_normal_training(catalog, splits, **kwargs)
