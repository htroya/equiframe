# Scripts del Módulo DW (equiframe-sercop)

Este documento describe todos los scripts disponibles para las responsabilidades de Jhair en relación al Data Warehouse (DW) SERCOP–OCDS.

## Scripts Disponibles

### 1. **Inicialización y Gestión Básica**

#### `etl_init.py`
- **Propósito**: Inicializa el DW creando la base DuckDB, ejecutando el DDL y cargando datos de ejemplo.
- **Uso**: `python3 etl_init.py`
- **Qué hace**:
  - Crea/actualiza la base de datos DuckDB (`dw_sercop.duckdb`)
  - Ejecuta el esquema SQL (`dw_schema.sql`)
  - Inserta datos de ejemplo en todas las tablas
  - Muestra conteos de verificación

#### `show_dw.py`
- **Propósito**: Muestra el estado actual del DW incluyendo todos los datos y metadata.
- **Uso**: `python3 show_dw.py`
- **Qué hace**:
  - Conecta a la base DW existente
  - Muestra conteos y datos de muestra de todas las tablas
  - Información del snapshot más reciente

### 2. **Carga de Datos OCDS**

#### `etl_load_ocds.py`
- **Propósito**: ETL completo para cargar datos OCDS JSON en el DW.
- **Uso**: `python3 etl_load_ocds.py <archivo_json> --snapshot-id <ID> [opciones]`
- **Opciones**:
  - `--snapshot-id`: ID único del snapshot (requerido)
  - `--snapshot-timestamp`: Timestamp del snapshot (opcional, default: ahora)
  - `--source`: Fuente de los datos (default: SERCOP-OCDS)
  - `--version`: Versión del snapshot (default: 1.0)
  - `--db-path`: Ruta a la base DuckDB (default: dw_sercop.duckdb)
- **Qué hace**:
  - Lee archivo(s) JSON OCDS
  - Extrae y transforma datos según las reglas de negocio
  - Carga/actualiza dimensiones (entidad, proveedor, item, fecha)
  - Inserta hechos en la tabla de adjudicaciones
  - Mantiene idempotencia usando INSERT OR IGNORE + UPDATE
  - Muestra conteos y resumen de carga

### 3. **Reconciliación y Validación**

#### `reconcile.py` (Placeholder Original)
- **Propósito**: Script original que verifica acceso al DW y muestra conteos.
- **Uso**: `python3 reconcile.py`
- **Nota**: Este es el script placeholder original. Use `reconcile_enhanced.py` para funcionalidad completa.

#### `reconcile_enhanced.py`
- **Propósito**: Script completo de reconciliación que compara datos OCDS origen con el DW y registra excepciones.
- **Uso**: `python3 reconcile_enhanced.py --source <ruta_origen> --snapshot-id <ID> [opciones]`
- **Opciones**:
  - `--source`: Archivo o directorio JSON OCDS de origen (requerido)
  - `--snapshot-id`: ID del snapshot a reconciliar (requerido)
  - `--db-path`: Ruta a la base DuckDB (default: dw_sercop.duckdb)
  - `--dictionary`: Ruta al diccionario de datos (default: dw_dictionary.csv)
  - `--mode`: Modo de salida (`summary` o `detail`, default: summary)
  - `--max-exceptions`: Máximo número de excepciones a mostrar en modo detail (default: 100)
- **Qué hace**:
  - Lee datos OCDS de origen (archivo único o directorio)
  - Lee el estado actual del DW para el snapshot especificado
  - Compara campos clave: entidad_id, proveedor_id, item_id, monto, moneda, estado, fecha_adjudicacion
  - Registra todas las discrepancias encontradas en la tabla `recon_excepciones`
  - Calcula diferencias numéricas para campos como monto
  - Muestra resumen detallado de coincidencias y excepciones
  - Limpia excepciones previas para el mismo snapshot antes de cada ejecución

### 4. **Utilidades Adicionales**

#### Archivos de Ejemplo y Referencia

- `sample_ocds_award.json`: Ejemplo de award OCDS que coincide con los datos de ejemplo del DW
- `sample_ocds_award_discrepant.json`: Ejemplo de award OCDS con discrepancies intencionales para testing
- `dw_schema.sql`: Esquema completo del DW (star style)
- `dw_dictionary.csv`: Diccionario de datos que describe todas las tablas y columnas

## Flujo de Trabajo Típico

### 1. Primera configuración del DW
```bash
# Desde el directorio equiframe-sercop/
python3 etl_init.py          # Crea la DW y carga datos de ejemplo
python3 show_dw.py           # Verifica el estado inicial
```

### 2. Carga de datos OCDS reales
```bash
# Asumiendo que tienes un archivo awards.json con datos OCDS
python3 etl_load_ocds.py awards.json --snapshot-id 20231001
python3 show_dw.py           # Verifica que los datos se cargaron correctamente
```

### 3. Ejecutar reconciliación
```bash
# Comparar los datos cargados en DW con los archivos fuente originales
python3 reconcile_enhanced.py --source awards.json --snapshot-id 20231001 --mode detail
```

### 4. Revisar excepciones
```bash
# Ver qué discrepancias se encontraron
python3 -c "import duckdb; con=duckdb.connect('dw_sercop.duckdb'); print(con.execute('SELECT * FROM recon_excepciones ORDER BY excepción_id').fetchall())"
```

## Estructura del DW

El DW sigue un modelo estrella (star schema):

### Tablas de Dimensión
- **dim_entidad**: Información de la entidad contratante (clave natural: entidad_id)
- **dim_proveedor**: Información del proveedor (clave natural: proveedor_id)  
- **dim_item**: Bien/servicio adjudicado (clave natural: item_id)
- **dim_fecha**: Dimensión de tiempo (año, mes, día, trimestre)
- **snapshot**: Metadata del lote de datos (timestamp, fuente, versión)

### Tabla de Hecho
- **fact_adjudicacion**: Contains measurements (monto, moneda, estado, fechas) and foreign keys to dimensions
  - Grano: combinación única de (snapshot_id, ocid, award_id)

### Tabla de Reconciliación
- **recon_excepciones**: Almacena discrepancias entre datos de origen y DW para análisis y reporte

## Consideraciones Importantes

1. **Idempotencia**: Todos los scripts de carga están diseñados para ser re-ejecutables sin crear duplicados.

2. **Versionado de Snapshots**: Cada ejecución debe usar un `snapshot_id` único (generalmente timestamp de formato YYYYMMDD o similar) para mantener trazabilidad histórica.

3. **Manejo de Errores**: Los scripts capturan y reportan errores sin detener todo el proceso, permitiendo el procesamiento por lotes incluso con algunos registros problemáticos.

4. **Rendimiento**: Para grandes volúmenes, considere ejecutar las operaciones en transacciones más grandes o procesar en batches.

5. **Extensibilidad**: El esquema incluye espacio para expansión - se pueden añadir más columnas a las tablas existentes según se necesiten nuevos campos de OCDS o requisitos de negocio.

## Integración con el Resto de EquiFrame

El DW está diseñado para ser consumido por otros componentes de EquiFrame a través de:
- El puerto `DataSource` (sin requerir importación directa del núcleo de EquiFrame en este módulo)
- Contratos de integración definidos por Hernán en `equiframe/contracts`
- Los scripts de ETL pueden ser llamados directamente por el benchmark o procesos de José según sea necesario
