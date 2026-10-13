"""
Carga releases_2025.json → DataFrames de Polars.

Produce 4 DataFrames planos listos para análisis o para subir a DuckDB:
  - df_releases   : un registro por release (info general)
  - df_tender     : un registro por proceso de contratación
  - df_awards     : un registro por adjudicación
  - df_parties    : un registro por parte (comprador, proveedor, etc.)
"""

import json
from pathlib import Path
import polars as pl

RUTA_JSON = Path(__file__).resolve().parent.parent / "releases_2025.json"


# ── helpers ──────────────────────────────────────────────────────────────────

def _val(obj, *keys, default=None):
    """Navega un dict anidado de forma segura."""
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k)
    return obj if obj is not None else default


def _extraer_ruc(party_id: str | None) -> str:
    """EC-RUC-1360051890001-74622  →  1360051890001"""
    if not party_id:
        return ""
    partes = party_id.split("-")
    return partes[2] if len(partes) >= 3 else party_id


# ── extractores por sección ───────────────────────────────────────────────────

def _fila_release(r: dict) -> dict:
    return {
        "ocid":            r.get("ocid", ""),
        "release_id":      r.get("id", ""),
        "fecha_release":   r.get("date", ""),
        "tags":            ",".join(r.get("tag") or []),
        "initiation_type": r.get("initiationType", ""),
        "buyer_id":        _val(r, "buyer", "id", default=""),
        "buyer_nombre":    _val(r, "buyer", "name", default=""),
    }


def _fila_tender(ocid: str, t: dict) -> dict:
    return {
        "ocid":                    ocid,
        "tender_id":               t.get("id", ""),
        "titulo":                  t.get("title", ""),
        "descripcion":             (t.get("description") or "")[:300],
        "status":                  t.get("status", ""),
        "procurement_method":      t.get("procurementMethod", ""),
        "procurement_method_det":  t.get("procurementMethodDetails", ""),
        "categoria_principal":     t.get("mainProcurementCategory", ""),
        "criterio_adj":            t.get("awardCriteria", ""),
        "n_oferentes":             t.get("numberOfTenderers"),
        "monto_usd":               _val(t, "value", "amount"),
        "fecha_inicio_convocatoria": _val(t, "tenderPeriod", "startDate", default=""),
        "fecha_fin_convocatoria":    _val(t, "tenderPeriod", "endDate", default=""),
        "fecha_inicio_adj":          _val(t, "awardPeriod", "startDate", default=""),
        "fecha_fin_adj":             _val(t, "awardPeriod", "endDate", default=""),
        "dias_adj":                  _val(t, "awardPeriod", "durationInDays"),
    }


def _filas_awards(ocid: str, awards: list) -> list[dict]:
    filas = []
    for a in awards:
        proveedor_id   = _val(a, "suppliers", 0, "id", default="")
        proveedor_nombre = _val(a, "suppliers", 0, "name", default="")
        filas.append({
            "ocid":             ocid,
            "award_id":         a.get("id", ""),
            "fecha_award":      a.get("date", ""),
            "status":           a.get("status", ""),
            "monto_usd":        _val(a, "value", "amount"),
            "moneda":           _val(a, "value", "currency", default="USD"),
            "n_items":          len(a.get("items") or []),
            "proveedor_id":     proveedor_id,
            "proveedor_ruc":    _extraer_ruc(proveedor_id),
            "proveedor_nombre": proveedor_nombre,
            "descripcion":      (a.get("description") or "")[:200],
        })
    return filas


def _filas_parties(ocid: str, parties: list) -> list[dict]:
    filas = []
    for p in parties:
        filas.append({
            "ocid":        ocid,
            "party_id":    p.get("id", ""),
            "ruc":         _extraer_ruc(p.get("id")),
            "nombre":      p.get("name", ""),
            "nombre_legal": _val(p, "identifier", "legalName", default=""),
            "roles":       ",".join(p.get("roles") or []),
            "region":      _val(p, "address", "region", default=""),
            "localidad":   _val(p, "address", "locality", default=""),
            "pais":        _val(p, "address", "countryName", default=""),
        })
    return filas


# ── carga principal ───────────────────────────────────────────────────────────

def cargar(ruta: Path = RUTA_JSON) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    print(f"Leyendo {ruta} ...")
    with open(ruta, encoding="utf-8") as f:
        paquetes = json.load(f)

    rows_rel, rows_ten, rows_awa, rows_par = [], [], [], []
    total = 0

    for pkg in paquetes:
        for r in pkg.get("releases", []):
            total += 1
            ocid = r.get("ocid", "")

            rows_rel.append(_fila_release(r))

            if t := r.get("tender"):
                rows_ten.append(_fila_tender(ocid, t))

            for fila in _filas_awards(ocid, r.get("awards") or []):
                rows_awa.append(fila)

            for fila in _filas_parties(ocid, r.get("parties") or []):
                rows_par.append(fila)

    print(f"Releases procesados : {total:,}")

    df_releases = pl.DataFrame(rows_rel)
    df_tender   = pl.DataFrame(rows_ten)
    df_awards   = pl.DataFrame(rows_awa)
    df_parties  = pl.DataFrame(rows_par)

    print(f"df_releases : {df_releases.shape}")
    print(f"df_tender   : {df_tender.shape}")
    print(f"df_awards   : {df_awards.shape}")
    print(f"df_parties  : {df_parties.shape}")

    return df_releases, df_tender, df_awards, df_parties


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    df_releases, df_tender, df_awards, df_parties = cargar()

    print("\n-- Muestra df_releases --")
    print(df_releases.head(3))

    print("\n-- Muestra df_awards --")
    print(df_awards.head(3))

    print("\n-- Muestra df_parties --")
    print(df_parties.head(3))
