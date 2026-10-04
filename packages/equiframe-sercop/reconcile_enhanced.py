#!/usr/bin/env python3
"""
Script de reconciliación mejorado del DW (equiframe-sercop).
Compara datos de origen OCDS JSON con el DW y registra excepciones.
"""

import pathlib
import duckdb
import csv
import sys
import json
from datetime import datetime, timedelta, date
import argparse

def load_dictionary(dict_path):
    """Devuelve lista de filas del CSV de diccionario."""
    rows = []
    with open(dict_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def load_ocds_source(source_path):
    """
    Carga datos OCDS desde un archivo JSON o directorio de JSONs.
    Retorna lista de awards.
    """
    source_path = pathlib.Path(source_path)
    awards = []
    
    if source_path.is_file():
        # Archivo único
        with open(source_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Manejar diferentes formatos
        if isinstance(data, dict) and 'awards' in data:
            awards = data['awards']
        elif isinstance(data, dict) and 'ocid' in data:
            awards = [data]
        elif isinstance(data, list):
            awards = data
        else:
            raise ValueError(f"Formato OCDS no reconocido en {source_path}")
            
    elif source_path.is_dir():
        # Directorio con múltiples JSONs
        for json_file in source_path.glob("*.json"):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'awards' in data:
                awards.extend(data['awards'])
            elif isinstance(data, dict) and 'ocid' in data:
                awards.append(data)
            elif isinstance(data, list):
                awards.extend(data)
    
    return awards

def procesar_fecha(date_str, tipo):
    """Procesa una fecha ISO y devuelve el componente solicitado."""
    if not date_str:
        return None
    try:
        if 'T' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(date_str)
        
        if tipo == 'date_only':
            return dt.date()
        elif tipo == 'year':
            return dt.year
        elif tipo == 'month':
            return dt.month
        elif tipo == 'day':
            return dt.day
        elif tipo == 'quarter':
            return (dt.month - 1) // 3 + 1
        elif tipo == 'adjudication_date':
            return dt.date()
        elif tipo == 'procedure_date':
            # Aproximación: 15 días antes de la adjudicación
            return (dt - timedelta(days=15)).date()
    except Exception:
        return None

def ubicacion_entidad(entity):
    """Extrae la ubicación de la entidad contratante."""
    if not entity or 'address' not in entity:
        return ''
    addr = entity['address']
    parts = [
        addr.get('locality', ''),
        addr.get('region', ''),
        addr.get('country_name', '')
    ]
    return ', '.join([p for p in parts if p])

def main():
    parser = argparse.ArgumentParser(description='Reconciliación entre datos OCDS origen y DW')
    parser.add_argument('--source', required=True, help='Archivo o directorio JSON OCDS de origen')
    parser.add_argument('--snapshot-id', required=True, help='ID del snapshot a reconciliar (ej: 20231001)')
    parser.add_argument('--db-path', default='dw_sercop.duckdb', help='Ruta a la base DuckDB')
    parser.add_argument('--dictionary', default='dw_dictionary.csv', help='Ruta al diccionario de datos')
    parser.add_argument('--mode', choices=['summary', 'detail'], default='summary', 
                       help='Modo de salida: summary (solo conteos) o detail (detalles de excepciones)')
    parser.add_argument('--max-exceptions', type=int, default=100, 
                       help='Máximo número de excepciones a reportar en modo detail')
    
    args = parser.parse_args()
    
    # Rutas
    base_dir = pathlib.Path(__file__).parent
    db_path = base_dir / args.db_path
    dict_path = base_dir / args.dictionary
    
    # Verificaciones iniciales
    if not db_path.exists():
        print(f"ERROR: Base de datos no encontrada en {db_path}. Ejecuta etl_init.py o etl_load_ocds.py primero.", file=sys.stderr)
        sys.exit(1)
    if not dict_path.exists():
        print(f"ERROR: Diccionario no encontrado en {dict_path}", file=sys.stderr)
        sys.exit(1)
    
    source_path = pathlib.Path(args.source)
    if not source_path.exists():
        print(f"ERROR: Fuente de datos no encontrada en {source_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Conectando a DuckDB: {db_path}")
    con = duckdb.connect(database=str(db_path), read_only=False)  # Read-write para insertar excepciones
    
    print("Cargando diccionario...")
    dict_rows = load_dictionary(dict_path)
    print(f"  {len(dict_rows)} entradas de diccionario cargadas.")
    
    print(f"Cargando datos OCDS de origen: {source_path}")
    try:
        source_awards = load_ocds_source(source_path)
        print(f"  {len(source_awards)} award(s) cargados de origen.")
    except Exception as e:
        print(f"ERROR: No se pudo cargar los datos de origen: {e}")
        sys.exit(1)
    
    # Preparar tabla de excepciones (limpiar si existe)
    print("\nPreparando tabla de excepciones...")
    con.execute("DELETE FROM recon_excepciones WHERE snapshot_id = ?", (args.snapshot_id,))
    print(f"  Limpiadas excepciones anteriores para snapshot {args.snapshot_id}")
    
    # Estadísticas
    stats = {
        'source_records': len(source_awards),
        'dw_records': 0,
        'exceptions': 0,
        'processed': 0
    }
    
    # Obtener registros actuales del DW para este snapshot
    # Incluir tanto las columnas de hecho como las naturales de las dimensiones
    dw_facts = con.execute("""
        SELECT 
            fa.fact_id,
            fa.snapshot_id,
            fa.ocid,
            fa.award_id,
            fa.monto,
            fa.moneda,
            fa.estado,
            fa.fecha_procedimiento,
            fa.fecha_adjudicacion,
            e.entidad_id,
            p.proveedor_id,
            i.item_id,
            f.fecha
        FROM fact_adjudicacion fa
        LEFT JOIN dim_entidad e ON fa.entidad_surrogate_key = e.entidad_surrogate_key
        LEFT JOIN dim_proveedor p ON fa.proveedor_surrogate_key = p.proveedor_surrogate_key
        LEFT JOIN dim_item i ON fa.item_surrogate_key = i.item_surrogate_key
        LEFT JOIN dim_fecha f ON fa.fecha_surrogate_key = f.fecha_surrogate_key
        WHERE fa.snapshot_id = ?
    """, (args.snapshot_id,)).fetchall()
    
    stats['dw_records'] = len(dw_facts)
    print(f"  Registros en DW para snapshot {args.snapshot_id}: {stats['dw_records']}")
    
    # Crear diccionario de búsqueda rápido para DW por award_id
    dw_by_award = {row[3]: row for row in dw_facts}  # award_id está en posición 3
    
    # Definir cómo extraer cada campo del award de origen
    def extract_field_from_award(award, campo):
        """Extrae un campo específico del award según su nombre."""
        try:
            if campo == 'entidad_id':
                entidad = award.get('procuringEntity', {})
                return str(entidad.get('id', ''))
            elif campo == 'proveedor_id':
                suppliers = award.get('suppliers', [])
                return str(suppliers[0].get('id', '')) if suppliers else ''
            elif campo == 'item_id':
                items = award.get('items', [])
                return str(items[0].get('id', '')) if items else ''
            elif campo == 'monto':
                return str(award.get('value', {}).get('amount', ''))
            elif campo == 'moneda':
                return str(award.get('value', {}).get('currency', ''))
            elif campo == 'estado':
                return str(award.get('status', ''))
            elif campo == 'fecha_adjudicacion':
                date_str = award.get('date', '')
                fecha_obj = procesar_fecha(date_str, 'date_only')
                return str(fecha_obj) if fecha_obj else ''
            else:
                return f"CAMPO_NO_SOPORTADO: {campo}"
        except Exception as e:
            return f"ERROR_EXTRACTION: {e}"
    
    # Procesar cada award de origen
    exceptions = []
    
    print(f"\nIniciando reconciliación de {len(source_awards)} awards...")
    
    for idx, award in enumerate(source_awards):
        award_id = award.get('id', f'UNKNOWN_{idx}')
        ocid = award.get('ocid', 'UNKNOWN')
        
        # Buscar en DW
        dw_record = dw_by_award.get(award_id)
        
        if dw_record is None:
            # Award no encontrado en DW - registrar como excepción
            exceptions.append({
                'award_id': award_id,
                'ocid': ocid,
                'campo': 'RECORD_EXISTENCE',
                'valor_origen': 'PRESENTE',
                'valor_destino': 'AUSENTE',
                'diferencia': None,
                'descripcion': 'Award presente en origen pero ausente en DW'
            })
            continue
        
        # Campos a comparar
        campos_a_comparar = [
            'entidad_id',
            'proveedor_id', 
            'item_id',
            'monto',
            'moneda',
            'estado',
            'fecha_adjudicacion'
        ]
        
        # Comparar cada campo
        for campo in campos_a_comparar:
            # Obtener valor de origen
            valor_origen = extract_field_from_award(award, campo)
            
            # Obtener valor de destino (DW)
            # Mapear campo a índice en dw_record
            campo_to_indice = {
                'entidad_id': 9,
                'proveedor_id': 10,
                'item_id': 11,
                'monto': 4,
                'moneda': 5,
                'estado': 6,
                'fecha_adjudicacion': 8
            }
            
            indice = campo_to_indice.get(campo)
            valor_destino = ''
            try:
                if indice is not None and indice < len(dw_record):
                    valor_raw = dw_record[indice]
                    if valor_raw is None:
                        valor_destino = ''
                    elif isinstance(valor_raw, date):
                        # Handle date objects properly
                        valor_destino = str(valor_raw)
                    else:
                        valor_destino = str(valor_raw)
                else:
                    valor_destino = 'NO_MAPEADO'
            except Exception as e:
                valor_destino = f"ERROR_ACCESS: {e}"
            
            # Normalizar para comparación
            v_origen_norm = str(valor_origen).strip() if valor_origen else ''
            v_destino_norm = str(valor_destino).strip() if valor_destino else ''
            
            # Comparar
            es_igual = False
            if v_origen_norm == '' and v_destino_norm == '':
                es_igual = True  # Ambos vacíos
            elif v_origen_norm == v_destino_norm:
                es_igual = True
            elif campo == 'monto' and v_origen_norm.replace('.', '', 1).isdigit() and v_destino_norm.replace('.', '', 1).isdigit():
                # Comparación numérica para montos
                try:
                    if float(v_origen_norm) == float(v_destino_norm):
                        es_igual = True
                except ValueError:
                    pass
            
            if not es_igual:
                # Calcular diferencia si es numérico
                diferencia = None
                try:
                    if campo == 'monto':
                        diferencia = float(v_origen_norm) - float(v_destino_norm)
                except (ValueError, TypeError):
                    pass
                
                exceptions.append({
                    'award_id': award_id,
                    'ocid': ocid,
                    'campo': campo,
                    'valor_origen': valor_origen,
                    'valor_destino': valor_destino,
                    'diferencia': diferencia,
                    'descripcion': f'Discrepancia en {campo}: origen="{valor_origen}" vs destino="{valor_destino}"'
                })
        
        stats['processed'] += 1
        if (idx + 1) % 50 == 0 or idx == len(source_awards) - 1:
            print(f"  Procesados {idx + 1}/{len(source_awards)} awards...")
    
    stats['exceptions'] = len(exceptions)
    
    # Insertar excepciones en la tabla recon_excepciones
    if exceptions:
        print(f"\nInsertando {len(exceptions)} excepciones en la tabla recon_excepciones...")
        for i, exc in enumerate(exceptions):
            # Generar ID de excepción (simple)
            excepcion_id = (con.execute("SELECT COALESCE(MAX(excepción_id), 0) FROM recon_excepciones").fetchone()[0] or 0) + i + 1
            
            con.execute("""
                INSERT INTO recon_excepciones 
                (excepción_id, snapshot_id, ocid, award_id, campo, valor_origen, valor_destino, diferencia, descripción)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                excepcion_id,
                args.snapshot_id,
                exc['ocid'],
                exc['award_id'],
                exc['campo'],
                exc['valor_origen'],
                exc['valor_destino'],
                exc['diferencia'],
                exc['descripcion']
            ))
    
    # Mostrar resultados
    print(f"\n{'='*60}")
    print(f"RESUMEN DE RECONCILIACIÓN")
    print(f"{'='*60}")
    print(f"Snapshot ID:        {args.snapshot_id}")
    print(f"Registros origen:   {stats['source_records']}")
    print(f"Registros DW:       {stats['dw_records']}")
    print(f"Procesados:         {stats['processed']}")
    print(f"Excepciones encontradas: {stats['exceptions']}")
    
    if stats['exceptions'] > 0 and args.mode == 'detail':
        print(f"\nPrimeras {min(args.max_exceptions, stats['exceptions'])} excepciones:")
        print("-" * 60)
        for i, exc in enumerate(exceptions[:args.max_exceptions]):
            print(f"{i+1:3d}. [{exc['award_id']}] {exc['campo']}:")
            print(f"      Origen:    '{exc['valor_origen']}'")
            print(f"      Destino:   '{exc['valor_destino']}'")
            if exc['diferencia'] is not None:
                print(f"      Diferencia: {exc['diferencia']}")
            print(f"      Descripción: {exc['descripcion']}")
            print()
        
        if stats['exceptions'] > args.max_exceptions:
            print(f"... y {stats['exceptions'] - args.max_exceptions} excepciones más.")
    
    # Mostrar conteos de tablas incluyendo excepciones
    print(f"\nConteos en DW:")
    tablas = ["snapshot", "dim_entidad", "dim_proveedor", "dim_item", "dim_fecha", "fact_adjudicacion", "recon_excepciones"]
    for t in tablas:
        try:
            cnt = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t}: {cnt}")
        except Exception as e:
            print(f"  {t}: ERROR ({e})")
    
    con.close()
    print(f"\nReconciliación completada. Resultados guardados en recon_excepciones.")

if __name__ == "__main__":
    main()
