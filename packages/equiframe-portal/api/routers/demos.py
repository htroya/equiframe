"""
Endpoints de demostraciones EquiFrame.
Los casos sintéticos siempre están disponibles.
Los casos con datos reales requieren el DW.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "equiframe-data"))

router = APIRouter(prefix="/demos", tags=["demos"])

# ── Casos sintéticos (siempre disponibles) ────────────────────────────────

CASOS_SINTETICOS = {
    "montos_intercambiados": {
        "titulo": "Montos intercambiados",
        "descripcion": (
            "Dos adjudicaciones conservan un total de 300,00 USD. "
            "La salida intercambia los valores: el total es correcto pero "
            "los montos individuales están asignados a la entidad equivocada."
        ),
        "tipo_datos": "sintéticos",
        "motor_origen": "Pandas",
        "motor_destino": "Polars",
        "entrada": [
            {"ocid": "ocds-001", "entidad": "Entidad A", "monto": 100.00},
            {"ocid": "ocds-002", "entidad": "Entidad B", "monto": 200.00},
        ],
        "salida_pandas": [
            {"ocid": "ocds-001", "entidad": "Entidad A", "monto": 100.00},
            {"ocid": "ocds-002", "entidad": "Entidad B", "monto": 200.00},
        ],
        "salida_polars": [
            {"ocid": "ocds-001", "entidad": "Entidad A", "monto": 200.00},
            {"ocid": "ocds-002", "entidad": "Entidad B", "monto": 100.00},
        ],
        "diferencias": [
            {"campo": "monto", "ocid": "ocds-001", "esperado": 100.00, "obtenido": 200.00, "tipo": "valor_incorrecto"},
            {"campo": "monto", "ocid": "ocds-002", "esperado": 200.00, "obtenido": 100.00, "tipo": "valor_incorrecto"},
        ],
        "contrato": {"suma_total": 300.00, "igualdad_exacta_por_clave": True},
        "resultado": "DIVERGENCIA",
    },
    "duplicados_orden": {
        "titulo": "Duplicados y orden",
        "descripcion": (
            "Un JOIN puede multiplicar filas si hay claves duplicadas. "
            "La suma de montos cambia aunque el esquema sea idéntico."
        ),
        "tipo_datos": "sintéticos",
        "motor_origen": "Pandas",
        "motor_destino": "Polars",
        "entrada": [
            {"award_id": "A1", "monto": 500.00, "proveedor_id": "P1"},
            {"award_id": "A1", "monto": 500.00, "proveedor_id": "P2"},
        ],
        "diferencias": [
            {"campo": "orden_filas", "descripcion": "Polars no garantiza orden sin ORDER BY explícito", "tipo": "orden"},
        ],
        "contrato": {"filas_esperadas": 2, "duplicados_permitidos": False},
        "resultado": "OK_CON_ADVERTENCIA",
    },
    "tipos_fechas": {
        "titulo": "Tipos y fechas",
        "descripcion": (
            "Identificadores leídos como entero pierden ceros iniciales. "
            "Zonas horarias distintas producen fechas diferentes al comparar."
        ),
        "tipo_datos": "sintéticos",
        "motor_origen": "Pandas",
        "motor_destino": "DuckDB",
        "entrada": [
            {"ocid": "0012345", "fecha_adjudicacion": "2025-03-15T00:00:00-05:00", "monto": 1234.56},
        ],
        "salida_pandas": [
            {"ocid": "0012345", "fecha_adjudicacion": "2025-03-15T00:00:00-05:00", "monto": 1234.56},
        ],
        "salida_duckdb": [
            {"ocid": 12345, "fecha_adjudicacion": "2025-03-15T05:00:00Z", "monto": 1234.56},
        ],
        "diferencias": [
            {"campo": "ocid", "tipo": "tipo_dato", "pandas": "string '0012345'", "duckdb": "integer 12345"},
            {"campo": "fecha_adjudicacion", "tipo": "zona_horaria", "pandas": "-05:00", "duckdb": "UTC"},
        ],
        "contrato": {"ocid_tipo": "string", "fecha_con_zona": True},
        "resultado": "DIVERGENCIA",
    },
    "migracion_motores": {
        "titulo": "Migración entre motores",
        "descripcion": (
            "Misma transformación de agregación ejecutada en Pandas, Polars y DuckDB. "
            "Se compara el resultado por clave."
        ),
        "tipo_datos": "sintéticos",
        "motor_origen": "Pandas",
        "parejas": ["Pandas→Polars", "Pandas→DuckDB", "Polars→DuckDB"],
        "resumen": [
            {"pareja": "Pandas→Polars",  "resultado": "OK",          "diferencias": 0, "filas": 183891},
            {"pareja": "Pandas→DuckDB",  "resultado": "DIVERGENCIA", "diferencias": 3, "filas": 183891},
            {"pareja": "Polars→DuckDB",  "resultado": "DIVERGENCIA", "diferencias": 3, "filas": 183891},
        ],
        "contrato": {"agrupacion": ["entidad_id"], "suma": "monto", "moneda_separada": True},
        "resultado": "DIVERGENCIA_PARCIAL",
    },
}


@router.get("")
def list_demos():
    """Lista todos los casos disponibles."""
    return [
        {"key": k, "titulo": v["titulo"], "resultado": v["resultado"], "tipo_datos": v["tipo_datos"]}
        for k, v in CASOS_SINTETICOS.items()
    ]


@router.get("/{key}")
def get_demo(key: str):
    """Devuelve el detalle completo de un caso."""
    if key not in CASOS_SINTETICOS:
        raise HTTPException(status_code=404, detail=f"Caso '{key}' no encontrado")
    return CASOS_SINTETICOS[key]
