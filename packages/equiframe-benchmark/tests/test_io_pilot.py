import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import equiframe_benchmark as eb
from equiframe_benchmark.pilot import run_pilot


def test_atomic_exclusive_publication(make_case, tmp_path):
    scenario = make_case()[0]
    path = tmp_path / "scenario.json"

    def save():
        try:
            eb.save_document(scenario, path)
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(lambda _: save(), range(4))) == 1
    assert eb.load_document(eb.Scenario, path) == scenario
    assert not tuple(tmp_path.glob("*.part"))


@pytest.mark.parametrize("fault", ("duplicate", "unknown", "coercion", "nan", "version"))
def test_strict_json(make_case, tmp_path, fault):
    s = make_case()[0]
    raw = s.model_dump(mode="json")
    if fault == "unknown":
        raw["label"] = "normal"
    if fault == "coercion":
        raw["scenario_id"] = 4
    if fault == "nan":
        raw["expected"]["size_bytes"] = float("nan")
    if fault == "version":
        raw["schema_version"] = "2.0"
    text = json.dumps(raw)
    if fault == "duplicate":
        text = text.replace('"scenario_id":', '"scenario_id":"shadow", "scenario_id":')
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        eb.load_document(eb.Scenario, path)


def test_complete_native_pilot_with_pending_reviews(tmp_path):
    result = run_pilot(tmp_path / "pilot")
    assert result["scenarios"] == 5 and result["groups"] == 4
    assert result["profiles"] == 15 and result["candidates"] == 35
    assert result["confirmed"] == 0 and result["pending"] == 35
    assert result["effects"] == {"changed": 10, "no_effect": 5}
    assert result["comparisons"] == {"equivalent": 25, "different": 10}
    assert result["review_agreement"] is None
    assert not result["scientific_freeze_ready"]
    with pytest.raises(FileExistsError):
        run_pilot(tmp_path / "pilot")
