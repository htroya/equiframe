"""
Endpoints SERCOP — consultan el DW DuckDB via DWReader.

Esquema real del DW de Jhair (13-Nov-2026):
    fact_adjudicacion(fact_id, snapshot_id, ocid, award_id,
        monto, moneda, estado, fecha_procedimiento, fecha_adjudicacion,
        entidad_surrogate_key, proveedor_surrogate_key,
        item_surrogate_key, fecha_surrogate_key)
    dim_entidad(entidad_surrogate_key, entidad_id, entidad_nombre,
        entidad_tipo, entidad_ubicación)
    dim_proveedor(proveedor_surrogate_key, proveedor_id,
        proveedor_nombre, proveedor_tipo, proveedor_país)
    dim_fecha(fecha_surrogate_key, fecha, año, mes, día, trimestre)
    dim_item(item_surrogate_key, item_id, item_descripcion, item_unidad_medida)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "equiframe-data"))

from dw_access import DWReader          # noqa: E402
from api.config import DW_FILE, SNAPSHOT_ID, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE  # noqa: E402

router = APIRouter(prefix="/sercop", tags=["sercop"])


def _records(df):
    """Convierte DataFrame a lista de dicts, reemplazando NaN/Inf con None."""
    return json.loads(df.to_json(orient='records', date_format='iso', default_handler=str))

# Base FROM con JOINs a dimensiones — reutilizado en todas las queries
_FROM = """
    FROM fact_adjudicacion f
    JOIN dim_entidad   e ON f.entidad_surrogate_key   = e.entidad_surrogate_key
    JOIN dim_proveedor p ON f.proveedor_surrogate_key = p.proveedor_surrogate_key
"""


def _reader():
    if not DW_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DW_NO_DISPONIBLE",
                "mensaje": f"El archivo DW no existe en '{DW_FILE}'. "
                           "Ejecutar el ETL para publicar el DuckDB.",
            }
        )
    return DWReader(DW_FILE)


# ── GET /snapshots ────────────────────────────────────────────────────────

@router.get("/snapshots")
def get_snapshots():
    """Lista de versiones del conjunto disponibles."""
    with _reader() as db:
        rows = db.query(
            "SELECT snapshot_id, MIN(fecha_adjudicacion) AS fecha_inicio, "
            "MAX(fecha_adjudicacion) AS fecha_fin, COUNT(*) AS registros "
            "FROM fact_adjudicacion GROUP BY snapshot_id ORDER BY snapshot_id DESC"
        )
    return _records(rows)


# ── GET /indicadores ──────────────────────────────────────────────────────

@router.get("/indicadores")
def get_indicadores(
    snapshot: str = Query(SNAPSHOT_ID, description="ID del snapshot"),
    periodo:  Optional[str] = Query(None,  description="Ej. 2025-Q1"),
    entidad:  Optional[str] = Query(None),
    moneda:   Optional[str] = Query(None, description="USD (default)"),
):
    where, _ = _build_where(snapshot, periodo, entidad, moneda=moneda)
    sql = f"""
        SELECT
            COUNT(*)                             AS total_adjudicaciones,
            SUM(f.monto)                         AS monto_total,
            COUNT(DISTINCT f.entidad_surrogate_key)   AS entidades_unicas,
            COUNT(DISTINCT f.proveedor_surrogate_key) AS proveedores_unicos,
            '{snapshot}'                         AS snapshot_id
        {_FROM}
        {where}
    """
    with _reader() as db:
        row = _records(db.query(sql))
    return row[0] if row else {}


# ── GET /serie-temporal ───────────────────────────────────────────────────

@router.get("/serie-temporal")
def get_serie_temporal(
    snapshot: str = Query(SNAPSHOT_ID),
    entidad:  Optional[str] = Query(None),
    moneda:   Optional[str] = Query(None),
):
    where, _ = _build_where(snapshot, entidad=entidad, moneda=moneda)
    sql = f"""
        SELECT
            strftime(f.fecha_adjudicacion, '%Y-%m') AS mes,
            SUM(f.monto)                             AS monto,
            COUNT(*)                                 AS adjudicaciones
        {_FROM}
        {where}
        GROUP BY mes
        ORDER BY mes
    """
    with _reader() as db:
        rows = db.query(sql)
    return _records(rows)


# ── GET /entidades/top ────────────────────────────────────────────────────

@router.get("/entidades/top")
def get_top_entidades(
    snapshot: str = Query(SNAPSHOT_ID),
    limit:    int = Query(10, ge=1, le=50),
    moneda:   Optional[str] = Query(None),
):
    where, _ = _build_where(snapshot, moneda=moneda)
    sql = f"""
        SELECT
            e.entidad_nombre    AS entidad,
            SUM(f.monto)        AS monto,
            COUNT(*)            AS adjudicaciones
        {_FROM}
        {where}
        GROUP BY e.entidad_surrogate_key, e.entidad_nombre
        ORDER BY monto DESC
        LIMIT {limit}
    """
    with _reader() as db:
        rows = db.query(sql)
    return _records(rows)


# ── GET /adjudicaciones ───────────────────────────────────────────────────

@router.get("/adjudicaciones")
def get_adjudicaciones(
    snapshot:  str = Query(SNAPSHOT_ID),
    periodo:   Optional[str] = Query(None),
    entidad:   Optional[str] = Query(None),
    estado:    Optional[str] = Query(None),
    modalidad: Optional[str] = Query(None),
    moneda:    Optional[str] = Query(None),
    page:      int = Query(0, ge=0),
    size:      int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    where, _ = _build_where(snapshot, periodo, entidad, estado, moneda=moneda)
    sql_count = f"SELECT COUNT(*) AS total {_FROM} {where}"
    sql_data  = f"""
        SELECT
            f.ocid,
            f.award_id,
            e.entidad_nombre             AS entidad,
            p.proveedor_nombre           AS proveedor,
            f.monto,
            f.moneda,
            f.fecha_adjudicacion::TEXT   AS fecha,
            f.estado,
            NULL                         AS modalidad
        {_FROM}
        {where}
        ORDER BY f.fecha_adjudicacion DESC, f.ocid
        LIMIT {size} OFFSET {page * size}
    """
    with _reader() as db:
        total = _records(db.query(sql_count))[0]["total"]
        rows  = _records(db.query(sql_data))
    return {"total": total, "page": page, "size": size, "items": rows}


# ── GET /adjudicacion/{ocid}/{award_id} ───────────────────────────────────

@router.get("/adjudicacion/{ocid}/{award_id}")
def get_adjudicacion(ocid: str, award_id: str, snapshot: str = Query(SNAPSHOT_ID)):
    sql = f"""
        SELECT
            f.snapshot_id,
            f.ocid,
            f.award_id,
            e.entidad_nombre             AS entidad,
            p.proveedor_nombre           AS proveedor,
            f.monto,
            f.moneda,
            f.fecha_adjudicacion::TEXT   AS fecha,
            f.estado,
            NULL                         AS modalidad
        {_FROM}
        WHERE f.snapshot_id = ? AND f.ocid = ? AND f.award_id = ?
    """
    with _reader() as db:
        rows = _records(db.query_params(sql, [snapshot, ocid, award_id]))
    if not rows:
        raise HTTPException(status_code=404, detail="Adjudicación no encontrada")
    return rows[0]


# ── Helpers ───────────────────────────────────────────────────────────────

def _build_where(
    snapshot:  str,
    periodo:   Optional[str] = None,
    entidad:   Optional[str] = None,
    estado:    Optional[str] = None,
    modalidad: Optional[str] = None,
    moneda:    Optional[str] = None,
) -> tuple[str, list]:
    conds = [f"f.snapshot_id = '{snapshot}'"]
    if periodo:
        q_map = {"Q1": ("01", "03"), "Q2": ("04", "06"),
                 "Q3": ("07", "09"), "Q4": ("10", "12")}
        year, q = periodo.split("-")
        m1, m2 = q_map.get(q, ("01", "12"))
        conds.append(
            f"f.fecha_adjudicacion BETWEEN DATE '{year}-{m1}-01' "
            f"AND DATE '{year}-{m2}-30'"
        )
    if entidad:
        conds.append(f"e.entidad_nombre = '{entidad.replace(chr(39), chr(39)*2)}'")
    if estado:
        conds.append(f"f.estado = '{estado}'")
    if moneda:
        conds.append(f"f.moneda = '{moneda}'")
    return ("WHERE " + " AND ".join(conds), []) if conds else ("", [])
