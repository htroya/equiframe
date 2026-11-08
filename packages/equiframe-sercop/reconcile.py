#!/usr/bin/env python3
"""
Script de reconciliación del DW (placeholder).
Lee el diccionario y compara datos de origen vs DW (implementación futura).
"""

import pathlib
import duckdb
import csv
import sys

def load_dictionary(dict_path):
    """Devuelve lista de filas del CSV de diccionario."""
    rows = []
    with open(dict_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def main():
    base_dir = pathlib.Path(__file__).parent
    db_path = base_dir / "dw_sercop.duckdb"
    dict_path = base_dir / "dw_dictionary.csv"

    if not db_path.exists():
        print(f"ERROR: Base de datos no encontrada en {db_path}. Ejecuta etl_init.py primero.", file=sys.stderr)
        sys.exit(1)
    if not dict_path.exists():
        print(f"ERROR: Diccionario no encontrado en {dict_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Conectando a DuckDB: {db_path}")
    con = duckdb.connect(database=str(db_path), read_only=True)

    print("Cargando diccionario...")
    rows = load_dictionary(dict_path)
    print(f"  {len(rows)} entradas de diccionario cargadas.")

    # Placeholder: simplemente mostrar algunas tablas y conteos
    tablas = [
        "snapshot", "dim_entidad", "dim_proveedor", "dim_item",
        "dim_fecha", "fact_adjudicacion", "recon_excepciones"
    ]
    print("\nConteos en DW:")
    for t in tablas:
        try:
            cnt = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t}: {cnt}")
        except Exception as e:
            print(f"  {t}: ERROR ({e})")

    # TODO: Implementar comparación real con fuentes de origen (JSON/CSV)
    print("\n[Placeholder] La reconciliación real compararía datos de origen (JSON OCDS) con el DW y registraría excepciones en recon_excepciones.")
    print("Este script solo verifica que el DW esté accesible y muestra conteos.")

    con.close()
    print("\nReconciliación placeholder completada.")

if __name__ == "__main__":
    main()
