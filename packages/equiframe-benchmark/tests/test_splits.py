import hashlib

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import equiframe_benchmark as eb


def independent_scenario(template, index, dependencies):
    def ref(original, suffix):
        return original.model_copy(
            update={"sha256": hashlib.sha256(f"{index}:{suffix}".encode()).hexdigest()}
        )

    return template.model_copy(
        update={
            "scenario_id": f"scenario.{index}",
            "dependencies": tuple(dependencies),
            "expected": ref(template.expected, "expected"),
            "inputs": tuple(
                i.model_copy(update={"artifact": ref(i.artifact, i.name)}) for i in template.inputs
            ),
        }
    )


def test_transitive_group_and_exact_artifact_dependencies(make_case):
    base = make_case()[0]
    a = independent_scenario(base, 1, ("template:a",))
    b = independent_scenario(base, 2, ("template:a", "ocid:b"))
    c = independent_scenario(base, 3, ("ocid:b",))
    d = independent_scenario(base, 4, ("independent",))
    e = independent_scenario(base, 5, ("omitted-by-author",)).model_copy(
        update={"inputs": d.inputs}
    )
    catalog = eb.Catalog(catalog_id="test", synthetic=True, scenarios=(a, b, c, d, e))
    assert eb.dependency_groups(catalog) == (
        ("scenario.1", "scenario.2", "scenario.3"),
        ("scenario.4", "scenario.5"),
    )
    splits = eb.make_splits(catalog, seed=7, weights=(3, 1, 2))
    eb.validate_splits(catalog, splits)
    group_a = {
        x.partition
        for x in splits.assignments
        if x.scenario_id in ("scenario.1", "scenario.2", "scenario.3")
    }
    assert len(group_a) == 1
    assert len({x.partition for x in splits.assignments}) == 2  # Never split groups to fill quotas.


def test_property_group_split_no_leakage_and_order_invariance(make_case):
    base = make_case()[0]

    # Generation is bounded to 15 masks of seven bits. Host scheduling under
    # load must not turn a correctness property into a speed test.
    @settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(
        # Every nonempty subset of seven dependencies, without duplicate-draw rejection.
        st.lists(
            st.integers(1, 127).map(lambda mask: {bit for bit in range(7) if mask & (1 << bit)}),
            min_size=1,
            max_size=15,
        ),
        st.integers(0, 10000),
    )
    def check(dependencies, seed):
        scenarios = tuple(
            independent_scenario(base, i, tuple(f"source:{j}" for j in sorted(d)))
            for i, d in enumerate(dependencies)
        )
        catalog = eb.Catalog(catalog_id="test", synthetic=True, scenarios=scenarios)
        split = eb.make_splits(catalog, seed=seed, weights=(3, 1, 2))
        eb.validate_splits(catalog, split)
        reversed_catalog = catalog.model_copy(update={"scenarios": tuple(reversed(scenarios))})
        assert (
            eb.make_splits(reversed_catalog, seed=seed, weights=(3, 1, 2)).assignments
            == split.assignments
        )
        assigned = {a.scenario_id: a.partition for a in split.assignments}
        for i, left in enumerate(dependencies):
            for j, right in enumerate(dependencies):
                if left & right:
                    assert assigned[f"scenario.{i}"] == assigned[f"scenario.{j}"]

    check()


@pytest.mark.parametrize("fault", ("catalog", "coverage", "group", "partition", "duplicate"))
def test_reject_altered_splits(make_case, fault):
    base = make_case()[0]
    scenarios = tuple(independent_scenario(base, i, ("shared",)) for i in range(3))
    catalog = eb.Catalog(catalog_id="test", synthetic=True, scenarios=scenarios)
    splits = eb.make_splits(catalog, seed=3, weights=(3, 1, 2))
    assignments = splits.assignments
    if fault == "catalog":
        splits = splits.model_copy(update={"catalog_sha256": "f" * 64})
    elif fault == "coverage":
        splits = splits.model_copy(update={"assignments": assignments[:-1]})
    elif fault == "duplicate":
        splits = splits.model_copy(update={"assignments": (*assignments, assignments[0])})
    else:
        field, value = ("group_id", "f" * 64) if fault == "group" else ("partition", "test")
        splits = splits.model_copy(
            update={
                "assignments": (assignments[0].model_copy(update={field: value}), *assignments[1:])
            }
        )
    with pytest.raises(ValueError):
        eb.validate_splits(catalog, splits)


@pytest.mark.parametrize(
    "seed,weights", [(True, (3, 1, 2)), (-1, (3, 1, 2)), (1, (0, 1, 2)), (1, (True, 1, 2))]
)
def test_strict_split_parameters(make_case, seed, weights):
    catalog = eb.Catalog(catalog_id="test", synthetic=True, scenarios=(make_case()[0],))
    with pytest.raises(ValueError):
        eb.make_splits(catalog, seed=seed, weights=weights)
