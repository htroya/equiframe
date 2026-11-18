"""Bounded native preparation must preserve data and keep normality unapproved."""

import hashlib
import importlib.util
import json
import math
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def batch():
    path = Path(__file__).parents[1] / "tools/prepare_sercop_native_batch.py"
    spec = importlib.util.spec_from_file_location("owned_test_batch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_unit():
    return {
        "source_record_ordinal": 0,
        "ocid": "one",
        "decimal_scale": 2,
        "release_date": "2026-01-01T00:00:00Z",
        "release_date_state": "present",
        "dependencies": ["ocid:one"],
        "normality": "UNREVIEWED",
        "native_profiles_prepared": 0,
        "awards": [
            {
                "ocid": "one",
                "award_id": "a",
                "currency": "USD",
                "amount": "10000000000000000001.30",
                "value_state": "present",
                "currency_state": "present",
                "amount_state": "present",
            },
            {
                "ocid": "one",
                "award_id": "b",
                "currency": "USD",
                "amount": "12.30",
                "value_state": "present",
                "currency_state": "present",
                "amount_state": "present",
            },
            {
                "ocid": "one",
                "award_id": "c",
                "currency": None,
                "amount": None,
                "value_state": "null",
                "currency_state": "not_applicable",
                "amount_state": "not_applicable",
            },
        ],
    }


def helper(batch, name):
    return batch.owned("owned_test_" + name, batch.ROOT / "tools" / (name + ".py"))


@pytest.mark.parametrize("family", ["nulls_types", "joins", "aggregations"])
def test_real_native_controls_preserve_large_money_absence_and_counts(
    batch, tmp_path, family
):
    import equiframe as ef
    import pyarrow as pa
    from equiframe_benchmark.pilot import write_table

    unit = fixture_unit()
    reader = helper(batch, "sercop_validation_workload")
    rows, release = batch.decode_unit(unit, reader)
    awards, releases = batch.unit_inputs(rows, release, 2, pa)
    contract, profile, reference_table, expected_features = batch.plan_family(
        ef, pa, awards, releases, family, rows, release, 0
    )
    if family == "aggregations":
        assert reference_table.to_pylist() == [
            {"currency": "USD", "award_count": 2},
            {"currency": None, "award_count": 1},
        ]
        assert expected_features == [math.log1p(2), 2 / 3]
    else:
        assert (
            str(reference_table.to_pylist()[0]["amount"]) == "10000000000000000001.30"
        )
        assert reference_table.to_pylist()[2]["value_state"] == "null"
        assert expected_features == [math.log1p(3), 1 / 3]
    reference = write_table(reference_table, tmp_path / "expected.arrow")
    implementations = helper(batch, "prepare_sercop_experiment")
    registry, name = implementations.registry(family, "control", "", 2)
    for engine in batch.ENGINES:
        result = ef.run_pipeline(
            ef.PipelineSpec(
                execution=ef.ExecutionPlan(
                    contract=contract,
                    engine=engine,
                    transformation_id=name,
                    options=ef.ExecutionOptions(duckdb_threads=1),
                ),
                profile=profile,
                comparison_reference="expected",
                comparison_policy=ef.ComparisonPolicy(
                    physical_types="lossless",
                    index="ignore",
                    justification="Explicit identity columns; metadata indexes excluded in this synthetic technical test.",
                ),
            ),
            source=ef.LocalDataSource(
                {
                    "awards": ef.ArrowInput(awards),
                    **(
                        {"releases": ef.ArrowInput(releases)}
                        if family == "joins"
                        else {}
                    ),
                }
            ),
            registry=registry,
            comparison=reference,
            work_dir=tmp_path / engine,
        )
        assert result.complete and result.comparison.state == "equivalent"
        assert result.comparison.counts.difference_records == 0
        assert result.rules.complete and result.rules.decision == "no_alert"
        assert [o.value for o in result.profile.vector.observations] == pytest.approx(
            expected_features
        )
    assert unit["normality"] == "UNREVIEWED" and unit["native_profiles_prepared"] == 0


def test_shard_hash_and_source_interval_before_execution(batch, tmp_path):
    io = helper(batch, "thesis_packet_io")
    reader = helper(batch, "sercop_validation_workload")
    units = []
    for number in range(3):
        unit = fixture_unit()
        unit["ocid"] = f"u{number}"
        unit["dependencies"] = ["ocid:" + unit["ocid"]]
        unit["source_record_ordinal"] = number * 2
        for row in unit["awards"]:
            row["ocid"] = unit["ocid"]
        if number == 0:
            unit["awards"] = unit["awards"][:1]
        units.append(unit)
    raw = b"".join(json.dumps(u).encode() + b"\n" for u in units)
    path = tmp_path / "candidate-inputs-000.jsonl"
    path.write_bytes(raw)
    manifest = {
        "candidate_ocid_units": 3,
        "candidate_shards": [
            {
                "file": path.name,
                "bytes": len(raw),
                "records": 3,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        ],
    }
    selected = batch.selected_units(tmp_path, manifest, 1, 1, io, reader)
    assert len(selected) == 1 and selected[0][0]["ocid"] == "u1"
    assert selected[0][0]["source_record_ordinal"] == 2
    multi = batch.selected_units(tmp_path, manifest, 1, 1, io, reader, min_awards=2)
    assert multi[0][0]["ocid"] == "u2" and multi[0][0]["source_record_ordinal"] == 4
    assert path.read_bytes() == raw
    path.write_bytes(raw.replace(b"12.30", b"12.31"))
    with pytest.raises(ValueError, match="shard_identity_differs"):
        batch.selected_units(tmp_path, manifest, 1, 1, io, reader)
    assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]


@pytest.mark.parametrize(
    "amount", ["-0.00", "NaN", "Infinity", "not-a-number", "1E2", "1.001", "9" * 39]
)
def test_unsupported_money_is_never_repaired(batch, amount):
    unit = fixture_unit()
    unit["awards"][0]["amount"] = amount
    with pytest.raises(ValueError):
        batch.decode_unit(unit, helper(batch, "sercop_validation_workload"))
    assert unit["awards"][0]["amount"] == amount


@pytest.mark.parametrize(
    "change", ["duplicate_award", "false_null", "approved", "wrong_ocid"]
)
def test_identity_presence_and_normality_cannot_be_laundered(batch, change):
    unit = fixture_unit()
    if change == "duplicate_award":
        unit["awards"][1]["award_id"] = "a"
    elif change == "false_null":
        unit["awards"][0]["amount_state"] = "null"
    elif change == "approved":
        unit["normality"] = "NORMAL"
    else:
        unit["awards"][0]["ocid"] = "other"
    with pytest.raises(ValueError):
        batch.decode_unit(unit, helper(batch, "sercop_validation_workload"))


@pytest.mark.parametrize(
    "raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e9999}', b"\xff", b"[" * 1200]
)
def test_untrusted_json_rejected_without_execution(batch, raw):
    with pytest.raises(ValueError):
        batch.strict_json(raw)


@pytest.mark.parametrize("count", [0, True, 257, "1"])
def test_invalid_native_budget_creates_no_output(batch, tmp_path, count):
    out = tmp_path / "not-created"
    with pytest.raises(ValueError, match="invalid_batch_interval"):
        batch.prepare(
            tmp_path / "missing",
            "0" * 64,
            tmp_path / "missing-binding",
            out,
            count=count,
        )
    assert not out.exists()


def test_compaction_preserves_bytes_and_confines_removal(batch, tmp_path):
    output = tmp_path / "batch"
    output.mkdir()
    unit = output / "unit-000001"
    unit.mkdir()
    originals = {
        "input.arrow": b"\x00\xff\x00",
        "pipeline/control.json": b'{"normality":"UNREVIEWED"}\n',
    }
    for name, raw in originals.items():
        path = unit / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    outside = tmp_path / "untouched.bin"
    outside.write_bytes(b"not batch output")
    result = batch.compact_unit(output, unit)
    assert not unit.exists() and outside.read_bytes() == b"not batch output"
    path = output / result["file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == result["sha256"]
    with zipfile.ZipFile(path) as archived:
        assert all(archived.read(name) == raw for name, raw in originals.items())
        manifest = json.loads(archived.read("closed-unit.json"))
        assert manifest["original_prefix"] == str(unit)
        assert {r["file"] for r in manifest["files"]} == set(originals)
    foreign = tmp_path / "unit-000002"
    foreign.mkdir()
    (foreign / "keep").write_bytes(b"keep")
    with pytest.raises(ValueError, match="generated_unit_outside_batch"):
        batch.compact_unit(output, foreign)
    assert (foreign / "keep").read_bytes() == b"keep"


def test_corrupt_compaction_never_removes_generated_originals(
    batch, tmp_path, monkeypatch
):
    unit = tmp_path / "unit-000003"
    unit.mkdir()
    path = unit / "control.json"
    path.write_bytes(b"original bytes")
    original = zipfile.ZipFile.writestr

    def corrupt(archive, name, raw, *args, **kwargs):
        return original(
            archive,
            name,
            b"altered bytes" if name == "control.json" else raw,
            *args,
            **kwargs,
        )

    monkeypatch.setattr(zipfile.ZipFile, "writestr", corrupt)
    with pytest.raises(ValueError, match="unit_archive_(size_differs|bytes_differ)"):
        batch.compact_unit(tmp_path, unit)
    assert path.read_bytes() == b"original bytes"
