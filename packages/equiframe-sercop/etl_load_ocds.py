"""Bounded DW v1 prototype: exact money, NULL absences and transactional batches.

Temporal projection and bridge schemas remain domain decisions. Unsupported
timestamp precision or multiple suppliers/items are rejected without publication.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import date, datetime
from datetime import timezone as _timezone
from decimal import Context, Decimal, InvalidOperation, localcontext
from pathlib import Path

import duckdb

DIMENSIONS = {
    "dim_entidad": (
        "entidad_id",
        "entidad_surrogate_key",
        ("entidad_nombre", "entidad_tipo", "entidad_ubicación"),
    ),
    "dim_proveedor": (
        "proveedor_id",
        "proveedor_surrogate_key",
        ("proveedor_nombre", "proveedor_tipo", "proveedor_país"),
    ),
    "dim_item": (
        "item_id",
        "item_surrogate_key",
        ("item_descripcion", "item_unidad_medida"),
    ),
}
MAX_INPUT_BYTES = 64 * 1024**2
MAX_AWARDS = 100000
UTC = _timezone.utc  # noqa: UP017 -- preserve Python 3.10 compatibility


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, *, required=False, maximum=65536):
    if value is None and not required:
        return None
    require(
        isinstance(value, str)
        and (not required or bool(value))
        and len(value) <= maximum,
        "Invalid text field",
    )
    return value


def mapping(value):
    require(value is None or isinstance(value, dict), "Invalid nested record")
    return value or {}


def calendar_date(value):
    if value is None:
        return None
    require(
        isinstance(value, str)
        and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is not None,
        "DW v1 requires explicit calendar dates; timestamp projection is not approved",
    )
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid calendar date") from None


def money(value):
    if value is None:
        return None
    require(
        type(value) in (int, Decimal), "Money requires exact decimal or integer input"
    )
    value = Decimal(value)
    require(
        value.is_finite() and not (value.is_zero() and value.is_signed()),
        "Unsupported monetary value",
    )
    try:
        with localcontext(Context(prec=64)):
            stored = value.quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError("Money does not fit DW v1") from None
    require(
        value == stored and stored.copy_abs() <= Decimal("9999999999999999.99"),
        "Money does not fit DECIMAL(18,2) exactly",
    )
    return stored


def single_collection(value):
    require(value is None or isinstance(value, list), "Invalid association collection")
    values = value or []
    require(
        len(values) <= 1,
        "DW v1 does not support multiple associations; nothing may be discarded",
    )
    require(
        all(isinstance(item, dict) for item in values), "Invalid association record"
    )
    return values[0] if values else None


def country_name(address):
    current = text(address.get("countryName"))
    legacy = text(address.get("country_name"))
    require(
        current is None or legacy is None or current == legacy,
        "Conflicting country names",
    )
    return current if current is not None else legacy


def normalize_award(award):
    require(isinstance(award, dict), "Invalid award")
    identity = (
        text(award.get("ocid"), required=True, maximum=512),
        text(award.get("id"), required=True, maximum=512),
    )
    value = mapping(award.get("value"))
    amount = money(value.get("amount"))
    currency = value.get("currency")
    require(
        currency is None
        or isinstance(currency, str)
        and re.fullmatch(r"[A-Z]{3}", currency) is not None,
        "Invalid currency",
    )
    entity = mapping(award.get("procuringEntity"))
    supplier = single_collection(award.get("suppliers"))
    item = single_collection(award.get("items"))
    dimensions = {}
    for name, record in (
        ("dim_entidad", entity or None),
        ("dim_proveedor", supplier),
        ("dim_item", item),
    ):
        if record is None:
            dimensions[name] = None
            continue
        natural = text(record.get("id"), required=True, maximum=512)
        if name == "dim_entidad":
            address = mapping(record.get("address"))
            parts = [text(address.get(key)) for key in ("locality", "region")]
            parts.append(country_name(address))
            location = (
                ", ".join(part for part in parts if part is not None)
                if any(part is not None for part in parts)
                else None
            )
            attributes = [
                text(record.get("name")),
                text(record.get("entityType")),
                location,
            ]
        elif name == "dim_proveedor":
            address = mapping(record.get("address"))
            attributes = [
                text(record.get("name")),
                text(record.get("entityType")),
                country_name(address),
            ]
        else:
            unit = mapping(record.get("unit"))
            attributes = [text(record.get("description")), text(unit.get("name"))]
        dimensions[name] = (natural, attributes)
    return {
        "ocid": identity[0],
        "award_id": identity[1],
        "amount": amount,
        "currency": currency,
        "status": text(award.get("status"), maximum=50),
        "award_date": calendar_date(award.get("date")),
        "procedure_date": calendar_date(award.get("procedure_date")),
        "dimensions": dimensions,
    }


def quoted(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def get_or_create_dimension(
    con,
    table_name,
    natural_key_col,
    natural_key_value,
    surrogate_key_col,
    attribute_cols,
    attribute_values,
):
    require(
        table_name in DIMENSIONS
        and (natural_key_col, surrogate_key_col, tuple(attribute_cols))
        == DIMENSIONS[table_name],
        "Unsupported dimension identifiers",
    )
    require(
        len(attribute_cols) == len(attribute_values), "Invalid dimension attributes"
    )
    text(natural_key_value, required=True, maximum=512)
    for value in attribute_values:
        text(value)
    table, natural, surrogate = map(
        quoted, (table_name, natural_key_col, surrogate_key_col)
    )
    stored_columns = ", ".join(map(quoted, attribute_cols))
    existing = con.execute(
        f"SELECT {surrogate}, {stored_columns} FROM {table} WHERE {natural} = ?",
        [natural_key_value],
    ).fetchone()
    if existing is not None:
        require(
            tuple(existing[1:]) == tuple(attribute_values),
            "DW v1 cannot overwrite historical dimension attributes",
        )
        return existing[0]
    key = con.execute(
        f"SELECT COALESCE(MAX({surrogate}), 0) + 1 FROM {table}"
    ).fetchone()[0]
    columns = ", ".join(
        map(quoted, (surrogate_key_col, natural_key_col, *attribute_cols))
    )
    placeholders = ", ".join("?" for _ in range(2 + len(attribute_cols)))
    con.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        [key, natural_key_value, *attribute_values],
    )
    return key


def _insert_award(con, award, snapshot_id):
    keys = {}
    for table, value in award["dimensions"].items():
        if value is None:
            keys[table] = None
        else:
            natural, surrogate, columns = DIMENSIONS[table]
            keys[table] = get_or_create_dimension(
                con, table, natural, value[0], surrogate, list(columns), value[1]
            )
    observed_date = award["award_date"]
    date_key = None
    if observed_date is not None:
        date_key = (
            observed_date.year * 10000 + observed_date.month * 100 + observed_date.day
        )
        con.execute(
            'INSERT OR IGNORE INTO dim_fecha (fecha_surrogate_key, fecha, "año", mes, "día", trimestre) VALUES (?, ?, ?, ?, ?, ?)',
            [
                date_key,
                observed_date,
                observed_date.year,
                observed_date.month,
                observed_date.day,
                (observed_date.month - 1) // 3 + 1,
            ],
        )
    con.execute(
        """INSERT INTO fact_adjudicacion (fact_id, snapshot_id, ocid, award_id, monto, moneda, estado,
        fecha_procedimiento, fecha_adjudicacion, entidad_surrogate_key, proveedor_surrogate_key,
        item_surrogate_key, fecha_surrogate_key) VALUES
        ((SELECT COALESCE(MAX(fact_id),0)+1 FROM fact_adjudicacion), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            snapshot_id,
            award["ocid"],
            award["award_id"],
            award["amount"],
            award["currency"],
            award["status"],
            award["procedure_date"],
            observed_date,
            keys["dim_entidad"],
            keys["dim_proveedor"],
            keys["dim_item"],
            date_key,
        ],
    )
    return {
        "entidad_id": award["dimensions"]["dim_entidad"][0]
        if award["dimensions"]["dim_entidad"]
        else None,
        "proveedor_id": award["dimensions"]["dim_proveedor"][0]
        if award["dimensions"]["dim_proveedor"]
        else None,
        "item_id": award["dimensions"]["dim_item"][0]
        if award["dimensions"]["dim_item"]
        else None,
        "fecha": observed_date.isoformat() if observed_date else None,
    }


def load_ocds_award(con, award_data, snapshot_id):
    award = normalize_award(award_data)
    text(snapshot_id, required=True, maximum=128)
    con.execute("BEGIN TRANSACTION")
    try:
        result = _insert_award(con, award, snapshot_id)
        con.execute("COMMIT")
        return result
    except Exception:
        con.execute("ROLLBACK")
        raise


def load_batch(
    con,
    awards,
    snapshot_id,
    *,
    snapshot_timestamp=None,
    source="SERCOP-OCDS",
    version="1.0",
):
    text(snapshot_id, required=True, maximum=128)
    text(source, required=True, maximum=256)
    text(version, required=True, maximum=128)
    require(
        isinstance(awards, list) and 0 < len(awards) <= MAX_AWARDS,
        "Invalid bounded award batch",
    )
    prepared = [normalize_award(award) for award in awards]
    require(
        len({(award["ocid"], award["award_id"]) for award in prepared})
        == len(prepared),
        "Duplicate award grain",
    )
    stamp = (
        datetime.now(UTC)
        if snapshot_timestamp is None
        else datetime.fromisoformat(
            text(snapshot_timestamp, required=True, maximum=64).replace("Z", "+00:00")  # noqa: FURB162 -- ISO Z needs translation on Python 3.10
        )
    )
    require(stamp.tzinfo is not None, "Snapshot timestamp requires timezone")
    con.execute("BEGIN TRANSACTION")
    try:
        require(
            con.execute(
                "SELECT 1 FROM snapshot WHERE snapshot_id = ?", [snapshot_id]
            ).fetchone()
            is None,
            "Published snapshot ID cannot be replaced; use a new ID",
        )
        con.execute(
            "INSERT INTO snapshot (snapshot_id, snapshot_timestamp, source, version) VALUES (?, ?, ?, ?)",
            [
                snapshot_id,
                stamp.astimezone(UTC).replace(tzinfo=None),
                source,
                version,
            ],
        )
        for award in prepared:
            _insert_award(con, award, snapshot_id)
        require(
            con.execute(
                "SELECT COUNT(*) FROM fact_adjudicacion WHERE snapshot_id = ?",
                [snapshot_id],
            ).fetchone()[0]
            == len(prepared),
            "Award count reconciliation failed",
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return len(prepared)


def read_input(path):
    helper_path = Path(__file__).resolve().parents[1] / "equiframe-data/safe_io.py"
    spec = importlib.util.spec_from_file_location("_dw_input_validation", helper_path)
    require(
        spec is not None and spec.loader is not None, "Input validation unavailable"
    )
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    with helper.open_regular(path) as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    require(len(raw) <= MAX_INPUT_BYTES, "Input budget exhausted")
    try:
        data = json.loads(
            raw.decode("utf-8"),
            parse_float=Decimal,
            object_pairs_hook=helper._members,
            parse_constant=helper._constant,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Invalid input JSON") from None
    if isinstance(data, dict):
        data = data.get("awards", [data])
    require(isinstance(data, list), "Invalid award batch")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--snapshot-timestamp")
    parser.add_argument("--source", default="SERCOP-OCDS")
    parser.add_argument("--version", default="1.0")
    parser.add_argument("--db-path", type=Path, default=Path("dw_sercop.duckdb"))
    args = parser.parse_args()
    con = None
    try:
        awards = read_input(args.input_file)
        for award in awards:
            normalize_award(award)
        require(
            not args.db_path.is_symlink(), "Linked database paths are not supported"
        )
        con = duckdb.connect(str(args.db_path))
        con.execute(
            Path(__file__).with_name("dw_schema.sql").read_text(encoding="utf-8")
        )
        count = load_batch(
            con,
            awards,
            args.snapshot_id,
            snapshot_timestamp=args.snapshot_timestamp,
            source=args.source,
            version=args.version,
        )
    except (ValueError, OSError, duckdb.Error, InvalidOperation):
        print(
            "ETL rechazado; el lote no se publicó. Revise contrato y evidencia privada.",
            file=sys.stderr,
        )
        return 1
    finally:
        if con is not None:
            con.close()
    print(f"ETL completado: {count} adjudicaciones publicadas atómicamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
