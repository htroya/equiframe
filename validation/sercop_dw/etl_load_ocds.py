"""Load explicit local award JSON into the optional, curated SERCOP DW.

SPDX-License-Identifier: MIT
Original modalidad/procedimiento contribution: Jhair Alarcon; see README.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    import duckdb

MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_AWARDS = 100_000
TABLES = (
    "snapshot",
    "dim_entidad",
    "dim_proveedor",
    "dim_item",
    "dim_fecha",
    "fact_adjudicacion",
    "recon_excepciones",
)


class InputError(ValueError):
    """A fixed diagnostic containing no input records or native SQL errors."""


class Award(NamedTuple):
    ocid: str
    award_id: str
    amount: Decimal
    currency: str
    status: str | None
    award_date: date
    modality: str | None
    procedure: str | None
    entity_id: str
    entity_name: str | None
    entity_type: str | None
    entity_location: str | None
    supplier_id: str | None
    supplier_name: str | None
    supplier_country: str | None
    item_id: str | None
    item_description: str | None
    item_unit: str | None


def safe_path(path: Path, *, required: bool) -> Path:
    """Reject links/special files; the caller controls the local directory."""
    path = Path(os.path.abspath(path))
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise InputError("path ancestors must be ordinary directories")
    try:
        info = path.lstat()
    except FileNotFoundError:
        if required:
            raise InputError("required local file does not exist") from None
    else:
        if (
            not stat.S_ISREG(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & 0x400
            or info.st_nlink != 1
        ):
            raise InputError("local files must be regular files without links or aliases")
    return path


def text(value: object, *, required: bool = False, limit: int = 1024) -> str | None:
    if value is None and not required:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(char) < 32 for char in value)
    ):
        raise InputError("text fields must be nonempty, bounded strings without controls")
    return value


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise InputError("award objects must be JSON objects")
    return value


def single(value: object) -> dict[str, object]:
    if not isinstance(value, list) or len(value) > 1:
        raise InputError("this prototype admits at most one supplier and one item per award")
    return mapping(value[0]) if value else {}


def award_row(raw: object, inherited_ocid: object = None) -> Award:
    record = mapping(raw)
    value = mapping(record.get("value"))
    amount = value.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, Decimal)):
        raise InputError("amount must be a JSON number")
    amount = Decimal(amount)
    if (
        not amount.is_finite()
        or amount < 0
        or amount > Decimal("9999999999999999.99")
        or amount != amount.quantize(Decimal("0.01"))
    ):
        raise InputError("amount must fit nonnegative DECIMAL(18,2) exactly")
    amount = amount.quantize(Decimal("0.01"))
    currency = text(value.get("currency"), required=True, limit=3)
    if re.fullmatch(r"[A-Z]{3}", currency or "") is None:
        raise InputError("currency must contain exactly three uppercase letters")
    try:
        stamp = str(text(record.get("date"), required=True))
        if re.match(r"^\d{4}-\d{2}-\d{2}(?:$|T)", stamp) is None:
            raise ValueError
        award_date = datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
    except ValueError:
        raise InputError("award date must be an explicit ISO date or timestamp") from None
    entity = mapping(record.get("procuringEntity"))
    address = mapping(entity.get("address", {}))
    supplier = single(record.get("suppliers", []))
    supplier_address = mapping(supplier.get("address", {}))
    item = single(record.get("items", []))
    location = [text(address.get(key)) for key in ("locality", "region", "country_name")]
    return Award(
        str(text(record.get("ocid", inherited_ocid), required=True, limit=200)),
        str(text(record.get("id"), required=True, limit=200)),
        amount,
        str(currency),
        text(record.get("status"), limit=50),
        award_date,
        text(record.get("modalidad"), limit=50),
        text(record.get("procedimiento"), limit=50),
        str(text(entity.get("id"), required=True, limit=200)),
        text(entity.get("name")),
        text(entity.get("entityType")),
        ", ".join(part for part in location if part) or None,
        text(supplier.get("id"), required=bool(supplier), limit=200),
        text(supplier.get("name")),
        text(supplier_address.get("country_name")),
        text(item.get("id"), required=bool(item), limit=200),
        text(item.get("description")),
        text(mapping(item.get("unit", {})).get("name")),
    )


def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON object keys are rejected")
        result[key] = value
    return result


def invalid_number(_value: str) -> None:
    raise InputError("nonfinite JSON numbers are rejected")


def read_awards(input_file: Path) -> list[Award]:
    path = safe_path(input_file, required=True)
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    )
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_INPUT_BYTES:
            raise InputError("JSON input must be a regular file of at most 64 MiB")
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise InputError("JSON input exceeds 64 MiB")
    data = json.loads(
        raw.decode("utf-8"),
        parse_float=Decimal,
        parse_constant=invalid_number,
        object_pairs_hook=unique_pairs,
    )
    inherited = None
    if isinstance(data, dict) and "awards" in data:
        inherited = data.get("ocid")
        data = data["awards"]
    elif isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not 0 < len(data) <= MAX_AWARDS:
        raise InputError("input must contain between 1 and 100000 awards")
    rows = sorted((award_row(record, inherited) for record in data), key=lambda row: row[:2])
    if len({row[:2] for row in rows}) != len(rows):
        raise InputError("duplicate (ocid, award id) keys in one batch are rejected")
    for start, end in ((8, 12), (12, 15), (15, 18)):
        dimensions: dict[object, tuple[object, ...]] = {}
        for row in rows:
            key = row[start]
            attrs = tuple(row[start + 1 : end])
            if key is not None and key in dimensions and dimensions[key] != attrs:
                raise InputError("dimension attributes conflict within one batch")
            dimensions[key] = attrs
    return rows


def connection(path: Path) -> duckdb.DuckDBPyConnection:
    import duckdb

    return duckdb.connect(
        str(path),
        config={
            "threads": 1,
            "memory_limit": "512MB",
            "max_temp_directory_size": "0B",
            "enable_external_access": False,
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
            "python_enable_replacements": False,
        },
    )


@contextmanager
def database(path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    path = safe_path(path, required=False)
    existed = path.exists()
    with tempfile.TemporaryDirectory(prefix=".sercop-dw-", dir=path.parent) as temporary:
        target = path if existed else Path(temporary) / "database.duckdb"
        session = connection(target)
        try:
            session.execute("BEGIN TRANSACTION")
            if existed:
                if session.execute("SELECT version FROM _sercop_dw_schema").fetchall() != [(1,)]:
                    raise InputError("database schema is not the curated DW version 1")
            else:
                schema = safe_path(Path(__file__).with_name("dw_schema.sql"), required=True)
                session.execute(schema.read_text("utf-8"))
            yield session
            session.execute("COMMIT")
        except BaseException:
            with suppress(Exception):
                session.execute("ROLLBACK")
            raise
        finally:
            session.close()
        if not existed:
            # A closed, valid database is published without replacing a racing destination.
            os.link(target, path)


def initialize(path: Path) -> None:
    """Create an empty schema; preserve an existing curated database."""
    with database(path):
        pass


def populate(session: duckdb.DuckDBPyConnection, rows: list[Award], snapshot_id: str) -> None:
    session.execute("""CREATE TEMP TABLE _awards (
        ocid VARCHAR, award_id VARCHAR, amount DECIMAL(18,2), currency VARCHAR,
        status VARCHAR, award_date DATE, modality VARCHAR, procedure_code VARCHAR,
        entity_id VARCHAR, entity_name VARCHAR, entity_type VARCHAR, entity_location VARCHAR,
        supplier_id VARCHAR, supplier_name VARCHAR, supplier_country VARCHAR,
        item_id VARCHAR, item_description VARCHAR, item_unit VARCHAR)""")
    session.executemany("INSERT INTO _awards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    # Identifiers are closed literals, never JSON fields or command-line values.
    for table, sequence, key, attributes, fields in (
        (
            "dim_entidad",
            "entidad_seq",
            "entidad_id",
            "entidad_nombre,entidad_tipo,entidad_ubicacion",
            "entity_id,entity_name,entity_type,entity_location",
        ),
        (
            "dim_proveedor",
            "proveedor_seq",
            "proveedor_id",
            "proveedor_nombre,proveedor_pais",
            "supplier_id,supplier_name,supplier_country",
        ),
        (
            "dim_item",
            "item_seq",
            "item_id",
            "item_descripcion,item_unidad_medida",
            "item_id,item_description,item_unit",
        ),
    ):
        source_key = fields.split(",")[0]
        source = f"(SELECT DISTINCT {fields} FROM _awards WHERE {source_key} IS NOT NULL)"
        session.execute(f"""INSERT INTO {table}
            SELECT nextval('{sequence}'), s.* FROM {source} s
            WHERE NOT EXISTS (SELECT 1 FROM {table} d WHERE d.{key}=s.{source_key})""")
        assignments = ",".join(
            f"{column}=s.{field}"
            for column, field in zip(attributes.split(","), fields.split(",")[1:], strict=True)
        )
        session.execute(
            f"UPDATE {table} SET {assignments} FROM {source} s WHERE {table}.{key}=s.{source_key}"
        )
    session.execute("""INSERT INTO dim_fecha
        SELECT DISTINCT CAST(strftime(award_date, '%Y%m%d') AS BIGINT), award_date,
            year(award_date), month(award_date), day(award_date), quarter(award_date)
        FROM _awards a WHERE NOT EXISTS (SELECT 1 FROM dim_fecha d WHERE d.fecha=a.award_date)""")
    session.execute(
        """INSERT INTO fact_adjudicacion
        SELECT nextval('fact_seq'), ?, a.ocid, a.award_id, a.amount, a.currency, a.status,
            a.award_date, a.award_date, a.modality, a.procedure_code,
            e.entidad_surrogate_key, p.proveedor_surrogate_key, i.item_surrogate_key,
            f.fecha_surrogate_key
        FROM _awards a JOIN dim_entidad e ON e.entidad_id=a.entity_id
        LEFT JOIN dim_proveedor p ON p.proveedor_id=a.supplier_id
        LEFT JOIN dim_item i ON i.item_id=a.item_id
        JOIN dim_fecha f ON f.fecha=a.award_date""",
        [snapshot_id],
    )


def load(
    input_file: Path,
    db_path: Path,
    *,
    snapshot_id: str,
    timestamp: str,
    source: str = "SERCOP-OCDS",
    version: str = "1.0",
) -> dict[str, object]:
    rows = read_awards(input_file)
    db_path = safe_path(db_path, required=False)
    if db_path.exists() and os.path.samefile(input_file, db_path):
        raise InputError("input and database must be different files")
    snapshot_id = str(text(snapshot_id, required=True, limit=200))
    source = str(text(source, required=True, limit=200))
    version = str(text(version, required=True, limit=100))
    stamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise InputError("snapshot timestamp requires an explicit UTC offset")
    stamp = stamp.astimezone(timezone.utc).replace(tzinfo=None)
    digest = hashlib.sha256(
        json.dumps(
            rows, default=str, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    with database(db_path) as session:
        previous = session.execute(
            """SELECT snapshot_timestamp, source, version, input_sha256
            FROM snapshot WHERE snapshot_id=?""",
            [snapshot_id],
        ).fetchone()
        if previous is not None:
            if previous != (stamp, source, version, digest):
                raise InputError("snapshot id already exists with different content or metadata")
            return {"awards": len(rows), "repeated": True}
        session.execute(
            "INSERT INTO snapshot VALUES (?,?,?,?,?)", [snapshot_id, stamp, source, version, digest]
        )
        populate(session, rows, snapshot_id)
    return {"awards": len(rows), "repeated": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load explicit local awards into the optional DW")
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--snapshot-timestamp", required=True)
    parser.add_argument("--source", default="SERCOP-OCDS")
    parser.add_argument("--version", default="1.0")
    args = parser.parse_args(argv)
    try:
        result = load(
            args.input_file,
            args.db_path,
            snapshot_id=args.snapshot_id,
            timestamp=args.snapshot_timestamp,
            source=args.source,
            version=args.version,
        )
    except (InputError, ValueError, ArithmeticError, OSError):
        print(
            "error: local input, path or snapshot validation failed",
            file=sys.stderr,
        )
        return 1
    except ImportError:
        print("error: this optional tool requires DuckDB", file=sys.stderr)
        return 1
    except Exception:
        print("error: database operation failed; inspect destination before retry", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
