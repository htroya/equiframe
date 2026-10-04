#!/usr/bin/env python3
"""
Script para mostrar el estado actual del Data Warehouse.
"""

import duckdb
import pathlib
import sys

def main():
    db_path = pathlib.Path("dw_sercop.duckdb")
    if not db_path.exists():
        print(f"ERROR: Base de datos no encontrada en {db_path}")
        print("Ejecute primero: python3 etl_init.py")
        sys.exit(1)
    
    print(f"Conectando a DuckDB en {db_path}")
    con = duckdb.connect(database=str(db_path))
    
    print("\n" + "="*60)
    print("ESTADO DEL DATA WAREHOUSE SERCOP-OCDS")
    print("="*60)
    
    # Mostrar esquemas y conteos
    tablas = ["snapshot", "dim_entidad", "dim_proveedor", "dim_item", "dim_fecha", "fact_adjudicacion", "recon_excepciones"]
    
    for tabla in tablas:
        try:
            count = con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            print(f"\n{tabla.upper()}: {count} registros")
            
            # Mostrar algunas filas de muestra (máximo 3)
            if count > 0:
                muestra = con.execute(f"SELECT * FROM {tabla} LIMIT 3").fetchall()
                columnas = [desc[0] for desc in con.description]
                
                for i, fila in enumerate(muestra):
                    print(f"  Fila {i+1}:")
                    for j, valor in enumerate(fila):
                        print(f"    {columnas[j]}: {valor}")
                        
        except Exception as e:
            print(f"\n{tabla.upper()}: ERROR - {e}")
    
    # Mostrar información del snapshot más reciente
    print("\n"+ "-"*60)
    print("INFORMACIÓN DEL SNAPSHOT MÁS RECIENTE")
    print("-"*60)
    try:
        snapshot_info = con.execute("""
            SELECT snapshot_id, snapshot_timestamp, source, version 
            FROM snapshot 
            ORDER BY snapshot_timestamp DESC 
            LIMIT 1
        """).fetchone()
        
        if snapshot_info:
            print(f"ID Snapshot:     {snapshot_info[0]}")
            print(f"Timestamp:       {snapshot_info[1]}")
            print(f"Fuente:          {snapshot_info[2]}")
            print(f"Versión:         {snapshot_info[3]}")
        else:
            print("No hay snapshots disponibles")
    except Exception as e:
        print(f"Error al obtener información de snapshot: {e}")
    
    con.close()
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
