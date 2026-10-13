"""
Carga releases_2025.json → DataFrames de Polars.

Produce 4 DataFrames planos listos para análisis o para subir a DuckDB:
  - df_releases   : un registro por release (info general)
  - df_tender     : un registro por proceso de contratación
  - df_awards     : un registro por adjudicación
  - df_parties    : un registro por parte (comprador, proveedor, etc.)
"""

import json
from decimal import Decimal
from pathlib import Path

import polars as pl

RUTA_JSON = Path(__file__).resolve().parent.parent / "releases_2025.json"


# ── helpers ──────────────────────────────────────────────────────────────────


def _val(obj, *keys, default=None):
    """Navigate mappings and indexed arrays without dropping zero or False."""
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k)
        elif isinstance(obj, list) and type(k) is int and 0 <= k < len(obj):
            obj = obj[k]
        else:
            return default
    return obj if obj is not None else default


def _extraer_ruc(party_id: str | None) -> str:
    """EC-RUC-1360051890001-74622  →  1360051890001"""
    if not party_id:
        return ""
    partes = party_id.split("-")
    return partes[2] if len(partes) >= 3 else party_id


def _validate_section(section: dict) -> None:
    """Reject malformed extracted structures without inventing domain conversions."""
    for field in ("value", "identifier", "address", "buyer", "tenderPeriod", "awardPeriod"):
        item = section.get(field)
        if item is not None and not isinstance(item, dict):
            raise ValueError("Invalid nested record")
    amount = _val(section, "value", "amount")
    if amount is not None and (
        type(amount) not in (int, Decimal) or isinstance(amount, Decimal) and not amount.is_finite()
    ):
        raise ValueError("Invalid monetary amount")
    if isinstance(amount, Decimal) and amount.is_zero() and amount.is_signed():
        raise ValueError("Signed monetary zero is not representable by this extractor")
    currency = _val(section, "value", "currency")
    if currency is not None and (
        not isinstance(currency, str)
        or len(currency) != 3
        or not all("A" <= char <= "Z" for char in currency)
    ):
        raise ValueError("Invalid currency format")
    for field in ("tag", "roles"):
        items = section.get(field)
        if items is not None and (
            not isinstance(items, list) or any(not isinstance(item, str) for item in items)
        ):
            raise ValueError("Invalid text collection")
    for field in ("suppliers", "items"):
        items = section.get(field)
        if items is not None and (
            not isinstance(items, list) or any(not isinstance(item, dict) for item in items)
        ):
            raise ValueError("Invalid nested collection")
    suppliers = section.get("suppliers") or []
    if any(item.get("id") is not None and not isinstance(item["id"], str) for item in suppliers):
        raise ValueError("Invalid supplier identity")
    if any(
        item.get("name") is not None and not isinstance(item["name"], str) for item in suppliers
    ):
        raise ValueError("Invalid supplier name")


def _state(record, field):
    return "missing" if field not in record else "null" if record[field] is None else "present"


def _frame(rows, *, monetary=False, suppliers=False):
    """Infer across all bounded rows, with explicit reversible monetary storage."""
    overrides = {}
    expected = []
    if monetary and rows:
        expected = [None if row["monto_usd"] is None else Decimal(row["monto_usd"]) for row in rows]
        scale = max(
            (max(0, -value.as_tuple().exponent) for value in expected if value is not None),
            default=0,
        )
        if scale > 38:
            raise ValueError("Monetary scale exceeds supported decimal storage")
        for value in expected:
            if (
                value is not None
                and not value.is_zero()
                and len(value.as_tuple().digits) + value.as_tuple().exponent + scale > 38
            ):
                raise ValueError("Monetary precision exceeds supported decimal storage")
        overrides["monto_usd"] = pl.Decimal(precision=38, scale=scale)
    if suppliers and rows:
        overrides["proveedores"] = pl.List(
            pl.Struct(
                {
                    "id": pl.String,
                    "nombre": pl.String,
                    "id_estado": pl.String,
                    "nombre_estado": pl.String,
                }
            )
        )
    result = pl.DataFrame(rows, schema_overrides=overrides, infer_schema_length=None, strict=True)
    if monetary and rows and result["monto_usd"].to_list() != expected:
        raise ValueError("Monetary conversion is not reversible")
    return result


# ── extractores por sección ───────────────────────────────────────────────────


def _fila_release(r: dict) -> dict:
    return {
        "ocid": r.get("ocid", ""),
        "release_id": r.get("id", ""),
        "fecha_release": r.get("date", ""),
        "tags": ",".join(r.get("tag") or []),
        "initiation_type": r.get("initiationType", ""),
        "buyer_id": _val(r, "buyer", "id", default=""),
        "buyer_nombre": _val(r, "buyer", "name", default=""),
    }


def _fila_tender(ocid: str, t: dict) -> dict:
    return {
        "ocid": ocid,
        "tender_id": t.get("id", ""),
        "titulo": t.get("title", ""),
        "descripcion": t.get("description") or "",
        "status": t.get("status", ""),
        "procurement_method": t.get("procurementMethod", ""),
        "procurement_method_det": t.get("procurementMethodDetails", ""),
        "categoria_principal": t.get("mainProcurementCategory", ""),
        "criterio_adj": t.get("awardCriteria", ""),
        "n_oferentes": t.get("numberOfTenderers"),
        "monto_usd": _val(t, "value", "amount"),
        "moneda": _val(t, "value", "currency", default=""),
        "fecha_inicio_convocatoria": _val(t, "tenderPeriod", "startDate", default=""),
        "fecha_fin_convocatoria": _val(t, "tenderPeriod", "endDate", default=""),
        "fecha_inicio_adj": _val(t, "awardPeriod", "startDate", default=""),
        "fecha_fin_adj": _val(t, "awardPeriod", "endDate", default=""),
        "dias_adj": _val(t, "awardPeriod", "durationInDays"),
    }


def _filas_awards(ocid: str, awards: list) -> list[dict]:
    filas = []
    for a in awards:
        proveedor_id = _val(a, "suppliers", 0, "id", default="")
        proveedor_nombre = _val(a, "suppliers", 0, "name", default="")
        filas.append(
            {
                "ocid": ocid,
                "award_id": a.get("id", ""),
                "fecha_award": a.get("date", ""),
                "status": a.get("status", ""),
                "monto_usd": _val(a, "value", "amount"),
                "moneda": _val(a, "value", "currency", default=""),
                "n_items": len(a.get("items") or []),
                "proveedor_id": proveedor_id,
                "proveedor_ruc": _extraer_ruc(proveedor_id),
                "proveedor_nombre": proveedor_nombre,
                "proveedores_estado": _state(a, "suppliers"),
                "proveedores": [
                    {
                        "id": supplier.get("id"),
                        "nombre": supplier.get("name"),
                        "id_estado": _state(supplier, "id"),
                        "nombre_estado": _state(supplier, "name"),
                    }
                    for supplier in a.get("suppliers") or []
                ],
                "descripcion": a.get("description") or "",
            }
        )
    return filas


def _filas_parties(ocid: str, parties: list) -> list[dict]:
    filas = []
    for p in parties:
        filas.append(
            {
                "ocid": ocid,
                "party_id": p.get("id", ""),
                "ruc": _extraer_ruc(p.get("id")),
                "nombre": p.get("name", ""),
                "nombre_legal": _val(p, "identifier", "legalName", default=""),
                "roles": ",".join(p.get("roles") or []),
                "region": _val(p, "address", "region", default=""),
                "localidad": _val(p, "address", "locality", default=""),
                "pais": _val(p, "address", "countryName", default=""),
            }
        )
    return filas


# ── carga principal ───────────────────────────────────────────────────────────


def cargar(
    ruta: Path = RUTA_JSON,
    *,
    max_input_bytes: int = 64 * 1024**2,
    max_releases: int = 250000,
    max_flat_rows: int = 2000000,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Bounded prototype extraction; no approval of OCDS domain or scientific cohort."""
    if type(max_input_bytes) is not int or not 1 <= max_input_bytes <= 2 * 1024**3:
        raise ValueError("Invalid input byte budget")
    if type(max_releases) is not int or not 1 <= max_releases <= 250000:
        raise ValueError("Invalid release budget")
    if type(max_flat_rows) is not int or not 1 <= max_flat_rows <= 2000000:
        raise ValueError("Invalid output row budget")
    if __package__:
        from ..safe_io import _constant, _members, open_regular
    else:
        # Direct script execution must use this checkout's helper, without
        # importing a same-named module from the working directory or PYTHONPATH.
        import importlib.util

        helper_path = Path(__file__).resolve().parents[1] / "safe_io.py"
        spec = importlib.util.spec_from_file_location("_equiframe_data_etl_safe_io", helper_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Input validation helper unavailable")
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        _constant, _members, open_regular = helper._constant, helper._members, helper.open_regular
    with open_regular(Path(ruta)) as stream:
        payload = stream.read(max_input_bytes + 1)
    if len(payload) > max_input_bytes:
        raise ValueError("Input byte budget exhausted")
    try:
        paquetes = json.loads(
            payload.decode("utf-8-sig"),
            parse_float=Decimal,
            object_pairs_hook=_members,
            parse_constant=_constant,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Invalid input JSON") from exc
    if not isinstance(paquetes, list):
        raise ValueError("Expected an array of release packages")

    rows_rel, rows_ten, rows_awa, rows_par = [], [], [], []
    total = 0
    flat_rows = 0

    for pkg in paquetes:
        if not isinstance(pkg, dict) or not isinstance(pkg.get("releases"), list):
            raise ValueError("Invalid release package")
        for r in pkg["releases"]:
            if not isinstance(r, dict) or not isinstance(r.get("ocid"), str) or not r["ocid"]:
                raise ValueError("Invalid release identity")
            total += 1
            if total > max_releases:
                raise ValueError("Release budget exhausted")
            for field in ("awards", "parties"):
                entries = r.get(field)
                if entries is not None and (
                    not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries)
                ):
                    raise ValueError("Invalid release collection")
            if r.get("tender") is not None and not isinstance(r["tender"], dict):
                raise ValueError("Invalid tender structure")
            awards = r.get("awards") or []
            parties = r.get("parties") or []
            flat_rows += 1 + int(bool(r.get("tender"))) + len(awards) + len(parties)
            flat_rows += sum(
                len(award.get("suppliers") or [])
                for award in awards
                if isinstance(award.get("suppliers"), list)
            )
            if flat_rows > max_flat_rows:
                raise ValueError("Output row budget exhausted")
            _validate_section(r)
            if r.get("tender"):
                _validate_section(r["tender"])
            for entries in (awards, parties):
                for entry in entries:
                    _validate_section(entry)
            if any(p.get("id") is not None and not isinstance(p["id"], str) for p in parties):
                raise ValueError("Invalid party identity")
            ocid = r.get("ocid", "")

            rows_rel.append(_fila_release(r))

            if t := r.get("tender"):
                rows_ten.append(_fila_tender(ocid, t))

            for fila in _filas_awards(ocid, r.get("awards") or []):
                rows_awa.append(fila)

            for fila in _filas_parties(ocid, r.get("parties") or []):
                rows_par.append(fila)

    print(f"Releases procesados : {total:,}")

    df_releases = _frame(rows_rel)
    df_tender = _frame(rows_ten, monetary=True)
    df_awards = _frame(rows_awa, monetary=True, suppliers=True)
    df_parties = _frame(rows_par)

    print(f"df_releases : {df_releases.shape}")
    print(f"df_tender   : {df_tender.shape}")
    print(f"df_awards   : {df_awards.shape}")
    print(f"df_parties  : {df_parties.shape}")

    return df_releases, df_tender, df_awards, df_parties


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    df_releases, df_tender, df_awards, df_parties = cargar()
