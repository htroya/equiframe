"""Reject repairs, discarded associations and partial publications in DW v1."""

import importlib.util
import subprocess
import sys
from datetime import date
from decimal import Decimal, Inexact, Rounded, localcontext
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).parents[1] / "packages/equiframe-sercop"
specification = importlib.util.spec_from_file_location(
    "secure_dw_loader", ROOT / "etl_load_ocds.py"
)
etl = importlib.util.module_from_spec(specification)
specification.loader.exec_module(etl)


@pytest.fixture
def database():
    connection = duckdb.connect(":memory:")
    connection.execute((ROOT / "dw_schema.sql").read_text(encoding="utf-8"))
    yield connection
    connection.close()


def test_missing_money_currency_dates_and_entities_remain_null(database):
    etl.load_batch(database, [{"id": "missing", "ocid": "o1"}], "s1")
    row = database.execute(
        "SELECT monto,moneda,fecha_procedimiento,fecha_adjudicacion,entidad_surrogate_key,proveedor_surrogate_key FROM fact_adjudicacion"
    ).fetchone()
    assert row == (None,) * 6
    assert database.execute("SELECT COUNT(*) FROM dim_fecha").fetchone()[0] == 0


def test_procedure_and_award_dates_are_independent(database):
    etl.load_batch(
        database,
        [
            {
                "id": "a1",
                "ocid": "o1",
                "date": "2025-02-03",
                "procedure_date": "2025-01-02",
                "value": {"amount": Decimal("0.00"), "currency": "EUR"},
            }
        ],
        "s1",
    )
    assert database.execute(
        "SELECT monto,moneda,fecha_procedimiento,fecha_adjudicacion FROM fact_adjudicacion"
    ).fetchone() == (Decimal("0.00"), "EUR", date(2025, 1, 2), date(2025, 2, 3))


@pytest.mark.parametrize(
    "value",
    [
        True,
        "1.25",
        1.25,
        Decimal("1.123456"),
        Decimal("1e-39"),
        Decimal("NaN"),
        Decimal("-0.00"),
        Decimal(10000000000000000),
    ],
)
def test_money_cannot_be_repaired_or_rounded_to_fit(database, value):
    with pytest.raises(ValueError):
        etl.load_batch(
            database, [{"id": "a1", "ocid": "o1", "value": {"amount": value}}], "s1"
        )
    assert database.execute("SELECT COUNT(*) FROM snapshot").fetchone()[0] == 0
    assert database.execute("SELECT COUNT(*) FROM fact_adjudicacion").fetchone()[0] == 0


def test_exact_money_is_independent_of_ambient_decimal_context(database):
    with localcontext() as context:
        context.prec = 2
        context.Emax = 2
        context.Emin = -2
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        etl.load_batch(
            database,
            [{"id": "a1", "ocid": "o1", "value": {"amount": Decimal("1234.560")}}],
            "s1",
        )
    assert database.execute("SELECT monto FROM fact_adjudicacion").fetchone() == (
        Decimal("1234.56"),
    )


@pytest.mark.parametrize("key", ["countryName", "country_name"])
def test_country_aliases_preserve_supplied_values(database, key):
    etl.load_batch(
        database,
        [
            {
                "id": "a1",
                "ocid": "o1",
                "suppliers": [{"id": "p1", "address": {key: "Ecuador"}}],
            }
        ],
        "s1",
    )
    assert database.execute(
        'SELECT "proveedor_país" FROM dim_proveedor'
    ).fetchone() == ("Ecuador",)


def test_conflicting_country_aliases_reject_without_writes(database):
    with pytest.raises(ValueError, match="Conflicting"):
        etl.load_batch(
            database,
            [
                {
                    "id": "a1",
                    "ocid": "o1",
                    "suppliers": [
                        {
                            "id": "p1",
                            "address": {
                                "countryName": "Ecuador",
                                "country_name": "Peru",
                            },
                        }
                    ],
                }
            ],
            "s1",
        )
    assert database.execute("SELECT COUNT(*) FROM snapshot").fetchone()[0] == 0


@pytest.mark.parametrize("field", ["suppliers", "items"])
def test_multiple_associations_rejected_before_any_writes(database, field):
    award = {
        "id": "a1",
        "ocid": "o1",
        field: [{"id": "one"}, {"id": "two"}],
        "procuringEntity": {"id": "entity"},
    }
    with pytest.raises(ValueError, match="multiple associations"):
        etl.load_batch(database, [award], "s1")
    for table in (
        "snapshot",
        "fact_adjudicacion",
        "dim_entidad",
        "dim_proveedor",
        "dim_item",
    ):
        assert database.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0


@pytest.mark.parametrize(
    "value", ["invalid", "2025-02-30", "2025-01-01T12:30:00Z", 20250101]
)
def test_temporal_values_are_not_replaced_by_today(database, value):
    with pytest.raises(ValueError):
        etl.load_batch(database, [{"id": "a1", "ocid": "o1", "date": value}], "s1")
    assert database.execute("SELECT COUNT(*) FROM snapshot").fetchone()[0] == 0


def test_failure_after_first_insert_rolls_back_entire_batch(database, monkeypatch):
    etl.load_batch(database, [{"id": "old", "ocid": "o0"}], "previous")
    before = database.execute("SELECT * FROM fact_adjudicacion").fetchall()
    insert = etl._insert_award
    attempted = []

    def fail_second(connection, award, snapshot):
        attempted.append(award["award_id"])
        if len(attempted) == 2:
            raise RuntimeError("controlled failure after first write")
        return insert(connection, award, snapshot)

    monkeypatch.setattr(etl, "_insert_award", fail_second)
    with pytest.raises(RuntimeError):
        etl.load_batch(
            database,
            [
                {"id": "a1", "ocid": "o1", "procuringEntity": {"id": "new-entity"}},
                {"id": "a2", "ocid": "o1"},
            ],
            "new",
        )
    assert attempted == ["a1", "a2"]
    assert database.execute("SELECT * FROM fact_adjudicacion").fetchall() == before
    assert database.execute("SELECT snapshot_id FROM snapshot").fetchall() == [
        ("previous",)
    ]
    assert database.execute("SELECT COUNT(*) FROM dim_entidad").fetchone()[0] == 0


def test_dimension_change_cannot_rewrite_an_older_snapshot(database):
    old = {
        "id": "old",
        "ocid": "o1",
        "procuringEntity": {"id": "entity", "name": "Original"},
    }
    etl.load_batch(database, [old], "s1")
    before = database.execute("SELECT * FROM dim_entidad").fetchall()
    with pytest.raises(ValueError, match="historical dimension"):
        etl.load_batch(
            database,
            [
                {
                    "id": "new",
                    "ocid": "o1",
                    "procuringEntity": {"id": "entity", "name": "Changed"},
                }
            ],
            "s2",
        )
    assert database.execute("SELECT * FROM dim_entidad").fetchall() == before
    assert database.execute("SELECT snapshot_id FROM snapshot").fetchall() == [("s1",)]
    assert database.execute("SELECT award_id FROM fact_adjudicacion").fetchall() == [
        ("old",)
    ]


def test_published_snapshot_cannot_be_overwritten(database):
    etl.load_batch(database, [{"id": "a1", "ocid": "o1"}], "s1")
    before = database.execute("SELECT * FROM fact_adjudicacion").fetchall()
    with pytest.raises(ValueError, match="cannot be replaced"):
        etl.load_batch(database, [{"id": "a2", "ocid": "o2"}], "s1")
    assert database.execute("SELECT * FROM fact_adjudicacion").fetchall() == before


def test_json_duplicate_keys_and_nonfinite_tokens_are_rejected(tmp_path):
    path = tmp_path / "source.json"
    for data in ('{"awards":[],"awards":[]}', '[{"value":{"amount":NaN}}]'):
        path.write_text(data)
        with pytest.raises(ValueError):
            etl.read_input(path)


def test_json_fraction_is_exact_and_cli_does_not_create_demo_data(tmp_path):
    path = tmp_path / "source.json"
    path.write_text(
        '[{"id":"a1","ocid":"o1","value":{"amount":12.30,"currency":"USD"}}]'
    )
    assert etl.read_input(path)[0]["value"]["amount"] == Decimal("12.30")
    target = tmp_path / "specified.duckdb"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(ROOT / "etl_load_ocds.py"),
            str(path),
            "--snapshot-id",
            "s1",
            "--db-path",
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    connection = duckdb.connect(str(target), read_only=True)
    try:
        assert (
            connection.execute("SELECT COUNT(*) FROM fact_adjudicacion").fetchone()[0]
            == 1
        )
        assert connection.execute("SELECT COUNT(*) FROM dim_entidad").fetchone()[0] == 0
    finally:
        connection.close()
