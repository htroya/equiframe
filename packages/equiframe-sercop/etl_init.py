#!/usr/bin/env python3
"""
Inicialización del DW de Jhair (equiframe-sercop).
Crea una base DuckDB, ejecuta el DDL y carga datos de ejemplo.
"""

import duckdb
import pathlib
import sys

def main():
    # Ruta a la base DuckDB (archivo local)
    db_path = pathlib.Path("dw_sercop.duckdb")
    print(f"Conectando a DuckDB en {db_path}")
    con = duckdb.connect(database=str(db_path))

    # Leer y ejecutar el DDL
    sql_path = pathlib.Path("dw_schema.sql")
    if not sql_path.is_file():
        print(f"ERROR: No se encontró {sql_path}", file=sys.stderr)
        sys.exit(1)
    sql_sql = sql_path.read_text(encoding="utf-8")
    print("Ejecutando DDL...")
    con.execute(sql_sql)
    print("DDL ejecutado exitosamente.")

    # Insertar datos de ejemplo (opcional)
    print("Insertando datos de ejemplo...")
    # Snapshot de ejemplo
    con.execute("""
        INSERT OR IGNORE INTO snapshot (snapshot_id, snapshot_timestamp, source, version)
        VALUES ('20231001', TIMESTAMP '2023-10-01 12:00:00', 'SERCOP-OCDS', '1.0')
    """)
    # Entidad
    con.execute("""
        INSERT OR IGNORE INTO dim_entidad (entidad_surrogate_key, entidad_id, entidad_nombre, entidad_tipo, entidad_ubicación)
        VALUES (1, 'ENT-001', 'Ministerio de Salud', 'Gobierno', 'Guayaquil')
    """)
    # Proveedor
    con.execute("""
        INSERT OR IGNORE INTO dim_proveedor (proveedor_surrogate_key, proveedor_id, proveedor_nombre, proveedor_tipo, proveedor_país)
        VALUES (1, 'PROV-001', 'Company S.A.', 'Privado', 'Ecuador')
    """)
    # Item
    con.execute("""
        INSERT OR IGNORE INTO dim_item (item_surrogate_key, item_id, item_descripcion, item_unidad_medida)
        VALUES (1, 'ITEM-001', 'Medicamentos', 'Und')
    """)
    # Fecha
    con.execute("""
        INSERT OR IGNORE INTO dim_fecha (fecha_surrogate_key, fecha, año, mes, día, trimestre)
        VALUES (20231001, DATE '2023-10-01', 2023, 10, 1, 4)
    """)
    # Fact adjudicacion
    con.execute("""
        INSERT OR IGNORE INTO fact_adjudicacion (
            fact_id, snapshot_id, ocid, award_id, monto, moneda, estado,
            fecha_procedimiento, fecha_adjudicacion,
            entidad_surrogate_key, proveedor_surrogate_key,
            item_surrogate_key, fecha_surrogate_key
        ) VALUES (
            1, '20231001', 'ocds-123abc', 'award-001',
            15000.75, 'USD', 'adjudicado',
            DATE '2023-09-15', DATE '2023-10-01',
            1, 1, 1, 20231001
        )
    """)
    print("Datos de ejemplo insertados.")

    # Verificaciones simples
    print("\nVerificación de conteos:")
    for table in ["snapshot", "dim_entidad", "dim_proveedor", "dim_item", "dim_fecha", "fact_adjudicacion"]:
        cnt = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {cnt}")

    con.close()
    print("\nInicialización completada. Base DuckDB disponible en:", db_path.resolve())

if __name__ == "__main__":
    main()
