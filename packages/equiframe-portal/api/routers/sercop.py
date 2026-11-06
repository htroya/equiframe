"""
Endpoints de datos SERCOP — consultan el DW DuckDB via DWReader.

Esquema esperado del DW (acordar con Jhair):
    fact_adjudicacion(
        snapshot_id, ocid TEXT, award_id TEXT,
        entidad_id  TEXT, nombre_entidad TEXT,
        proveedor_id TEXT, nombre_proveedor TEXT,
        monto DECIMAL, moneda TEXT,
        fecha_adjudicacion DATE,
        estado TEXT, modalidad TEXT
    )
    -- El monto aparece UNA SOLA VEZ por adjudicación;
    -- los proveedores adicionales están en dim_proveedor_award.

Ajustar los nombres de columna según el DDL real de Jhair.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "equiframe-data"))

from dw_access import DWReader          # noqa: E402
from api.config import DW_FILE, SNAPSHOT_ID, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE  # noqa: E402

router = APIRouter(prefix="/sercop", tags=["sercop"])


def _reader():
    """Context manager para DWReader con mensaje de error claro."""
    if not DW_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "DW_NO_DISPONIBLE",
                "mensaje": f"El archivo DW no existe en '{DW_FILE}'. "
                           "Jhair debe ejecutar el ETL y publicar el DuckDB.",
            }
        )
    return DWReader(DW_FILE)


# ── GET /snapshots ────────────────────────────────────────────────────────

@router.get("/snapshots")
def get_snapshots():
    """Lista de versiones del conjunto disponibles."""
    with _reader() as db:
        rows = db.query(
            "SELECT DISTINCT snapshot_id, MIN(fecha_adjudicacion) AS fecha_inicio, "
            "MAX(fecha_adjudicacion) AS fecha_fin, COUNT(*) AS registros "
            "FROM fact_adjudicacion GROUP BY snapshot_id ORDER BY snapshot_id DESC"
        )
    return rows.to_dicts()


# ── GET /indicadores ──────────────────────────────────────────────────────

@router.get("/indicadores")
def get_indicadores(
    snapshot: str = Query(SNAPSHOT_ID, description="ID del snapshot"),
    periodo:  Optional[str] = Query(None,  description="Ej. 2025-Q1"),
    entidad:  Optional[str] = Query(None),
    moneda:   Optional[str] = Query(None, description="USD (default)"),
):
    where, params = _build_where(snapshot, periodo, entidad, moneda=moneda)
    sql = f"""
        SELECT
            COUNT(*)                      AS total_adjudicaciones,
            SUM(monto)                    AS monto_total,
            COUNT(DISTINCT entidad_id)    AS entidades_unicas,
            COUNT(DISTINCT proveedor_id)  AS proveedores_unicos,
            '{snapshot}'                  AS snapshot_id
        FROM fact_adjudicacion
        {where}
    """
    with _reader() as db:
        row = db.query(sql).to_dicts()
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
            strftime(fecha_adjudicacion, '%Y-%m')  AS mes,
            SUM(monto)                              AS monto,
            COUNT(*)                                AS adjudicaciones
        FROM fact_adjudicacion
        {where}
        GROUP BY mes
        ORDER BY mes
    """
    with _reader() as db:
        rows = db.query(sql)
    return rows.to_dicts()


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
            nombre_entidad             AS entidad,
            SUM(monto)                 AS monto,
            COUNT(*)                   AS adjudicaciones
        FROM fact_adjudicacion
        {where}
        GROUP BY entidad_id, nombre_entidad
        ORDER BY monto DESC
        LIMIT {limit}
    """
    with _reader() as db:
        rows = db.query(sql)
    return rows.to_dicts()


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
    where, _ = _build_where(snapshot, periodo, entidad, estado, modalidad, moneda)
    sql_count = f"SELECT COUNT(*) AS total FROM fact_adjudicacion {where}"
    sql_data  = f"""
        SELECT
            ocid, award_id,
            nombre_entidad  AS entidad,
            nombre_proveedor AS proveedor,
            monto, moneda,
            fecha_adjudicacion::TEXT AS fecha,
            estado, modalidad
        FROM fact_adjudicacion
        {where}
        ORDER BY fecha_adjudicacion DESC, ocid
        LIMIT {size} OFFSET {page * size}
    """
    with _reader() as db:
        total = db.query(sql_count).to_dicts()[0]["total"]
        rows  = db.query(sql_data).to_dicts()
    return {"total": total, "page": page, "size": size, "items": rows}


# ── GET /adjudicacion/{ocid}/{award_id} ───────────────────────────────────

@router.get("/adjudicacion/{ocid}/{award_id}")
def get_adjudicacion(ocid: str, award_id: str, snapshot: str = Query(SNAPSHOT_ID)):
    sql = """
        SELECT
            f.snapshot_id, f.ocid, f.award_id,
            f.nombre_entidad  AS entidad,
            f.nombre_proveedor AS proveedor,
            f.monto, f.moneda,
            f.fecha_adjudicacion::TEXT AS fecha,
            f.estado, f.modalidad
        FROM fact_adjudicacion f
        WHERE f.snapshot_id = ? AND f.ocid = ? AND f.award_id = ?
    """
    with _reader() as db:
        rows = db.query_params(sql, [snapshot, ocid, award_id]).to_dicts()
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
    conds = [f"snapshot_id = '{snapshot}'"]
    if periodo:
        # Formato: 2025-Q1, 2025-Q2, 2025-Q3, 2025-Q4
        q_map = {"Q1": ("01","03"), "Q2": ("04","06"), "Q3": ("07","09"), "Q4": ("10","12")}
        year, q = periodo.split("-")
        m1, m2 = q_map.get(q, ("01","12"))
        conds.append(
            f"fecha_adjudicacion BETWEEN DATE '{year}-{m1}-01' "
            f"AND DATE '{year}-{m2}-30'"
        )
    if entidad:
        conds.append(f"nombre_entidad = '{entidad.replace(chr(39), chr(39)*2)}'")
    if estado:
        conds.append(f"estado = '{estado}'")
    if modalidad:
        conds.append(f"modalidad = '{modalidad}'")
    if moneda:
        conds.append(f"moneda = '{moneda}'")
    return ("WHERE " + " AND ".join(conds)) if conds else ("", [])
