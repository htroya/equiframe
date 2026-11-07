"""Full-source accounting and exact proposed inputs never manufacture training."""

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def cohort():
    path = Path(__file__).parents[1] / "tools/prepare_sercop_cohort.py"
    spec = importlib.util.spec_from_file_location("owned_test_cohort", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def archive(tmp_path, payload):
    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "x") as bundle:
        bundle.writestr("releases_2025.json", payload)
    return path


def bind(cohort, monkeypatch, path, counts):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(cohort, "SOURCE_SHA256", digest)
    monkeypatch.setattr(cohort, "EXPECTED_SOURCE_COUNTS", counts)
    return digest


def test_year_proposal_accounts_for_every_record_and_exact_money(
    tmp_path, cohort, monkeypatch
):
    payload = b"""[
      {"releases":[{"ocid":"one","date":"2025-01-01T00:00:00Z","awards":[{"id":"a","value":{"currency":"USD","amount":12.30}},{"id":"b","value":null}]}]},
      {"releases":[{"ocid":"two","date":"2026-01-01T00:00:00Z","awards":[{"id":"c","value":{"currency":"USD","amount":1}}]}]},
      {"releases":[{"ocid":"three","date":"2025-02-01T00:00:00Z","awards":[]}]}]"""
    path = archive(tmp_path, payload)
    original = bind(cohort, monkeypatch, path, (3, 3))
    out = tmp_path / "proposal"
    result = cohort.prepare(path, out, publication_year=2025)
    assert result["candidate_ocid_units"] == 1
    assert result["excluded_ocid_units"] == 2
    assert result["exclusion_reasons"] == {
        "outside_proposed_publication_year": 1,
        "no_awards": 1,
    }
    entry = result["candidate_shards"][0]
    raw = (out / entry["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
    unit = json.loads(raw)
    assert unit["awards"][0]["amount"] == "12.30" and unit["decimal_scale"] == 2
    assert (
        unit["awards"][1]["value_state"] == "null"
        and unit["awards"][1]["amount"] is None
    )
    assert unit["normality"] == "UNREVIEWED" and unit["native_profiles_prepared"] == 0
    assert result["scientific_ready"] is False and result["human_labels"] is None
    assert result["native_executions"] == 0
    assert set(result["n_fit_accredited_per_family"].values()) == {0}
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original


def test_no_hidden_year_filter_and_large_integer_stays_exact(
    tmp_path, cohort, monkeypatch
):
    payload = b"""[{"releases":[{"ocid":"future","date":"2026-03-01T00:00:00Z","awards":[{"id":"a","value":{"currency":"USD","amount":10000000000000000001}}]}]}]"""
    path = archive(tmp_path, payload)
    bind(cohort, monkeypatch, path, (1, 1))
    result = cohort.prepare(path, tmp_path / "proposal")
    assert (
        result["proposed_publication_year"] is None
        and result["candidate_ocid_units"] == 1
    )
    unit = json.loads(
        (tmp_path / "proposal" / result["candidate_shards"][0]["file"]).read_text()
    )
    assert unit["awards"][0]["amount"] == "10000000000000000001"


def test_duplicate_source_identity_never_publishes_a_ready_proposal(
    tmp_path, cohort, monkeypatch
):
    payload = b"""[{"releases":[{"ocid":"same","awards":[]}]},{"releases":[{"ocid":"same","awards":[]}]}]"""
    path = archive(tmp_path, payload)
    original = bind(cohort, monkeypatch, path, (2, 0))
    out = tmp_path / "proposal"
    with pytest.raises(ValueError, match="ambiguous_release_identity"):
        cohort.prepare(path, out)
    assert not (out / "cohort-proposal.json").exists()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original


def test_shards_enforce_both_byte_and_record_budgets(tmp_path, cohort, monkeypatch):
    monkeypatch.setattr(cohort, "MAX_SHARD_RECORDS", 2)
    monkeypatch.setattr(cohort, "MAX_SHARD_BYTES", 64)
    shards = cohort.Shards(tmp_path, "inputs")
    for number in range(5):
        shards.write({"id": number})
    shards.finish()
    assert [entry["records"] for entry in shards.files] == [2, 2, 1]
    assert all(entry["bytes"] <= 64 for entry in shards.files)


@pytest.mark.parametrize("year", [True, 0, 10000, "2025"])
def test_invalid_year_fails_before_creating_output(tmp_path, cohort, year):
    out = tmp_path / "proposal"
    with pytest.raises(ValueError):
        cohort.prepare(tmp_path / "missing.zip", out, publication_year=year)
    assert not out.exists()
