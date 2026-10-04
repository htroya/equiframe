#!/usr/bin/env python3
"""
ETL para cargar datos OCDS en el DW de Jhair (equiframe-sercop).
Lee archivos JSON OCDS y los carga en el Data Warehouse DuckDB.
"""

import duckdb
import pathlib
import sys
import json
from datetime import datetime
import argparse

def get_or_create_dimension(con, table_name, natural_key_col, natural_key_value, 
                           surrogate_key_col, attribute_cols, attribute_values):
    """
    Generic function to get or create a dimension row.
    Returns the surrogate key.
    If the row exists, updates the attributes and returns the existing surrogate key.
    If not, inserts a new row with a new surrogate key (max+1) and returns it.
    
    Parameters:
    - table_name: name of the dimension table
    - natural_key_col: column name of the natural key
    - natural_key_value: value of the natural key
    - surrogate_key_col: column name of the surrogate key
    - attribute_cols: list of attribute column names (to update if exists)
    - attribute_values: list of attribute values corresponding to attribute_cols
    """
    # First, try to get the surrogate key by the natural key
    result = con.execute(f"""
        SELECT {surrogate_key_col} FROM {table_name} 
        WHERE {natural_key_col} = ?
    """, (natural_key_value,)).fetchone()
    
    if result is not None:
        sk = result[0]
        # Update the attributes if they changed
        set_clause = ", ".join([f"{col} = ?" for col in attribute_cols])
        con.execute(f"""
            UPDATE {table_name} 
            SET {set_clause}
            WHERE {natural_key_col} = ?
        """, attribute_values + [natural_key_value])
        return sk
    else:
        # Insert a new row with a new surrogate key
        new_sk = con.execute(f"""
            SELECT COALESCE(MAX({surrogate_key_col}), 0) + 1 FROM {table_name}
        """).fetchone()[0]
        cols = [surrogate_key_col, natural_key_col] + attribute_cols
        placeholders = ", ".join(["?"] * len(cols))
        con.execute(f"""
            INSERT INTO {table_name} ({cols})
            VALUES ({placeholders})
        """, [new_sk, natural_key_value] + attribute_values)
        return new_sk

def load_ocds_award(con, award_data, snapshot_id):
    """
    Carga un award OCDS en las tablas del DW.
    Retorna los IDs de las dimensiones creadas/usadas.
    """
    
    # Extract key fields from award
    award_id = award_data.get('id', 'UNKNOWN')
    ocid = award_data.get('ocid', 'UNKNOWN')
    
    # Extract value information
    value_info = award_data.get('value', {})
    monto = value_info.get('amount', 0.0)
    moneda = value_info.get('currency', 'USD')
    
    # Extract status
    estado = award_data.get('status', 'UNKNOWN')
    
    # Procesar entidad contratante (procuringEntity)
    entity = award_data.get('procuringEntity', {})
    entidad_id = entity.get('id', 'UNKNOWN')
    entidad_nombre = entity.get('name', '')
    entidad_tipo = entity.get('entityType', '')
    entidad_ubicación = ''
    if 'address' in entity and entity['address']:
        addr = entity['address']
        localidad = addr.get('locality', '')
        region = addr.get('region', '')
        pais = addr.get('country_name', '')
        parts = [localidad, region, pais]
        entidad_ubicación = ', '.join([p for p in parts if p])
    
    # Get or create entidad
    entidad_sk = get_or_create_dimension(
        con, 'dim_entidad', 'entidad_id', entidad_id,
        'entidad_surrogate_key',
        ['entidad_nombre', 'entidad_tipo', 'entidad_ubicación'],
        [entidad_nombre, entidad_tipo, entidad_ubicación]
    )
    
    # Procesar proveedores (suppliers)
    proveedor_sk = None
    suppliers = award_data.get('suppliers', [])
    if suppliers:
        # Tomar el primer proveedor (en OCDS puede haber múltiples)
        supplier = suppliers[0]
        proveedor_id = supplier.get('id', 'UNKNOWN')
        proveedor_nombre = supplier.get('name', '')
        proveedor_tipo = 'Privado'  # Default, podría mejorarse
        proveedor_país = ''
        if 'address' in supplier and supplier['address']:
            addr = supplier['address']
            proveedor_país = addr.get('country_name', '')
        
        # Get or create proveedor
        proveedor_sk = get_or_create_dimension(
            con, 'dim_proveedor', 'proveedor_id', proveedor_id,
            'proveedor_surrogate_key',
            ['proveedor_nombre', 'proveedor_tipo', 'proveedor_país'],
            [proveedor_nombre, proveedor_tipo, proveedor_país]
        )
    
    # Procesar items
    item_sk = None
    items = award_data.get('items', [])
    if items:
        # Tomar el primer item (simplificación)
        item = items[0]
        item_id = item.get('id', 'UNKNOWN')
        item_descripcion = item.get('description', '')
        item_unidad_medida = ''
        if 'unit' in item and item['unit']:
            item_unidad_medida = item['unit'].get('name', '')
        
        # Get or create item
        item_sk = get_or_create_dimension(
            con, 'dim_item', 'item_id', item_id,
            'item_surrogate_key',
            ['item_descripcion', 'item_unidad_medida'],
            [item_descripcion, item_unidad_medida]
        )
    
    # Procesar fecha
    fecha_str = award_data.get('date', '')
    fecha_sk = None
    fecha_date = None
    if fecha_str:
        try:
            # Parsear fecha ISO
            if 'T' in fecha_str:
                fecha_dt = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            else:
                fecha_dt = datetime.fromisoformat(fecha_str)
            fecha_date = fecha_dt.date()
            
            # Generar surrogate key como YYYYMMDD
            fecha_sk = int(fecha_date.strftime('%Y%m%d'))
            
            # Insert or ignore (since attributes are deterministic from date)
            con.execute("""
                INSERT OR IGNORE INTO dim_fecha 
                (fecha_surrogate_key, fecha, año, mes, día, trimestre)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                fecha_sk,
                fecha_date,
                fecha_date.year,
                fecha_date.month,
                fecha_date.day,
                (fecha_date.month - 1) // 3 + 1  # Trimestre
            ))
        except Exception as e:
            print(f"Advertencia: No se pudo parsear fecha '{fecha_str}': {e}")
            # Usar fecha actual como fallback
            fecha_date = datetime.now().date()
            fecha_sk = int(fecha_date.strftime('%Y%m%d'))
            
            con.execute("""
                INSERT OR IGNORE INTO dim_fecha 
                (fecha_surrogate_key, fecha, año, mes, día, trimestre)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                fecha_sk,
                fecha_date,
                fecha_date.year,
                fecha_date.month,
                fecha_date.day,
                (fecha_date.month - 1) // 3 + 1
            ))
    else:
        # If no date, use today
        fecha_date = datetime.now().date()
        fecha_sk = int(fecha_date.strftime('%Y%m%d'))
        
        con.execute("""
            INSERT OR IGNORE INTO dim_fecha 
            (fecha_surrogate_key, fecha, año, mes, día, trimestre)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            fecha_sk,
            fecha_date,
            fecha_date.year,
            fecha_date.month,
            fecha_date.day,
            (fecha_date.month - 1) // 3 + 1
        ))
    
    # Use the parsed date (or fallback) for both procedure and adjudication dates
    fecha_procedimiento = fecha_date
    fecha_adjudicacion = fecha_date
    
    # Insertar hecho (fact_adjudicacion)
    # We use INSERT OR IGNORE then UPDATE to handle idempotency
    con.execute("""
        INSERT OR IGNORE INTO fact_adjudicacion (
            fact_id, snapshot_id, ocid, award_id, monto, moneda, estado,
            fecha_procedimiento, fecha_adjudicacion,
            entidad_surrogate_key, proveedor_surrogate_key,
            item_surrogate_key, fecha_surrogate_key
        ) VALUES (
            (SELECT COALESCE(MAX(fact_id), 0) + 1 FROM fact_adjudicacion),
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?, ?
        )
    """, (
        snapshot_id, ocid, award_id, monto, moneda, estado,
        fecha_procedimiento, fecha_adjudicacion,
        entidad_sk, proveedor_sk, item_sk, fecha_sk
    ))
    
    # Actualizar si ya existía (por la restricción UNIQUE)
    con.execute("""
        UPDATE fact_adjudicacion 
        SET monto = ?, moneda = ?, estado = ?,
            fecha_procedimiento = ?, fecha_adjudicacion = ?,
            entidad_surrogate_key = ?, proveedor_surrogate_key = ?,
            item_surrogate_key = ?, fecha_surrogate_key = ?
        WHERE snapshot_id = ? AND ocid = ? AND award_id = ?
    """, (
        monto, moneda, estado,
        fecha_procedimiento, fecha_adjudicacion,
        entidad_sk, proveedor_sk, item_sk, fecha_sk,
        snapshot_id, ocid, award_id
    ))
    
    return {
        'entidad_id': entidad_id,
        'proveedor_id': proveedor_id if suppliers else None,
        'item_id': item_id if items else None,
        'fecha': fecha_str
    }

def main():
    parser = argparse.ArgumentParser(description='Cargar datos OCDS en el DW')
    parser.add_argument('input_file', help='Archivo JSON OCDS de entrada')
    parser.add_argument('--snapshot-id', required=True, help='ID del snapshot (ej: 20231001)')
    parser.add_argument('--snapshot-timestamp', default=None, help='Timestamp del snapshot (ISO format)')
    parser.add_argument('--source', default='SERCOP-OCDS', help='Fuente de los datos')
    parser.add_argument('--version', default='1.0', help='Versión del snapshot')
    parser.add_argument('--db-path', default='dw_sercop.duckdb', help='Ruta a la base DuckDB')
    
    args = parser.parse_args()
    
    # Ruta a la base DuckDB
    db_path = pathlib.Path(args.db_path)
    print(f"Conectando a DuckDB en {db_path}")
    
    # Verificar que exista la base, si no crearla
    if not db_path.exists():
        print(f"Base de datos no encontrada. Creando nueva base en {db_path}")
        # Ejecutar etl_init.py para crear esquema y datos básicos
        import subprocess
        import sys
        result = subprocess.run([sys.executable, 'etl_init.py'], 
                              capture_output=True, text=True, cwd=pathlib.Path(__file__).parent)
        if result.returncode != 0:
            print(f"ERROR: Falló la creación de la base: {result.stderr}")
            sys.exit(1)
        print("Base de datos creada exitosamente.")
    
    con = duckdb.connect(database=str(db_path))
    
    # Leer archivo OCDS
    print(f"Leyendo archivo OCDS: {args.input_file}")
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: No se pudo leer el archivo {args.input_file}: {e}")
        sys.exit(1)
    
    # Manejar tanto un solo award como un paquete de awards
    awards = []
    if isinstance(data, dict) and 'awards' in data:
        # Formato paquete con lista de awards
        awards = data['awards']
    elif isinstance(data, dict) and 'ocid' in data:
        # Single award
        awards = [data]
    elif isinstance(data, list):
        # Lista directa de awards
        awards = data
    else:
        print(f"ERROR: Formato OCDS no reconocido en {args.input_file}")
        sys.exit(1)
    
    print(f"Procesando {len(awards)} award(s)...")
    
    # Insertar metadata del snapshot
    snapshot_timestamp = args.snapshot_timestamp
    if not snapshot_timestamp:
        snapshot_timestamp = datetime.now().isoformat()
    
    con.execute("""
        INSERT OR REPLACE INTO snapshot 
        (snapshot_id, snapshot_timestamp, source, version)
        VALUES (?, ?, ?, ?)
    """, (args.snapshot_id, snapshot_timestamp, args.source, args.version))
    
    # Procesar cada award
    procesados = 0
    errores = 0
    
    for i, award in enumerate(awards):
        try:
            result = load_ocds_award(con, award, args.snapshot_id)
            procesados += 1
            if (i + 1) % 10 == 0 or i == len(awards) - 1:
                print(f"  Procesados {i + 1}/{len(awards)} awards...")
        except Exception as e:
            errores += 1
            print(f"ERROR procesando award {i}: {e}")
            # Continuar con los otros awards
    
    # Verificaciones simples
    print("\nVerificación de conteos:")
    for table in ["snapshot", "dim_entidad", "dim_proveedor", "dim_item", "dim_fecha", "fact_adjudicacion"]:
        cnt = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {cnt}")
    
    print(f"\nResumen:")
    print(f"  Awards procesados exitosamente: {procesados}")
    print(f"  Awards con errores: {errores}")
    print(f"  Total awards: {len(awards)}")
    
    con.close()
    print(f"\nETL completado. Base DuckDB disponible en: {db_path.resolve()}")

if __name__ == "__main__":
    main()
