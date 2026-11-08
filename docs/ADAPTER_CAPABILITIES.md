# Registro de capacidades de adaptadores

`ef.get_adapter_capabilities()` entrega cuatro registros declarativos inmutables:
`arrow`, `pandas`, `polars` y `duckdb`. Cada uno separa **captura**, **comparación**,
**ejecución nativa** y **migración**. Consultarlo no ejecuta código de usuario,
no sondea instalaciones y no importa motores opcionales. Las capacidades runtime
proceden de `PandasAdapter/PolarsAdapter/DuckDBAdapter.capabilities()`; no se crea
un segundo mecanismo de admisión que pueda ignorar sus validadores.

```python
import equiframe as ef

for adapter in ef.get_adapter_capabilities():
    print(adapter.model_dump_json())
    for stage in adapter.stages:
        print(adapter.adapter, stage.stage, stage.status)
        print(stage.conditions, stage.losses, stage.implementation, stage.tests)
```

`status="supported_with_conditions"` no significa soporte para todo producto de
tipos, políticas, versiones y sistemas operativos. `rejected` es una frontera
segura que puede tener una prueba aprobada; `not_applicable` indica que no existe
ese rol nativo. Los nodos pytest identifican el corpus propio, no una ejecución
reciente ni una certificación externa. Para afirmar conformidad se necesita el
recibo del candidato con comando, combinación instalada y resultado exactos.

## Propiedad y mantenimiento

Todos estos adaptadores pertenecen a `packages/equiframe`, componente de Hernán
según [TEAM_INTEGRATION](TEAM_INTEGRATION.md#1-propiedad-y-dependencias). No hay una
asignación individual explícita por adaptador: `maintainer=null` y
`maintenance_status="unassigned"`. La propiedad del componente no se presenta
como aceptación personal del mantenimiento de cada integración. No se reasignan
responsabilidades de José o Jhair ni se implementa su servicio/DW.

## Fronteras por etapa

| Entrada/motor | Captura directa `diff` | Comparación | Ejecución nativa | Migración IR |
|---|---|---|---|---|
| Arrow | Tabla eager admitida, aislada y validada | Captura materializada y contrato explícito/inferido | No existe adaptador Arrow incorporado | Puede alimentar entradas; no es motor destino |
| Pandas | DataFrame eager real; índice aparte | Captura con política expresa de índice | Callback Pandas confiable sobre copias | Compilador Pandas independiente, IR acotado |
| Polars | DataFrame eager real; LazyFrame se rechaza sin `collect` | Captura materializada | Callback Polars; salida DataFrame/LazyFrame materializada | Compilador Polars independiente, límites comunes y nativos |
| DuckDB | Relación en `diff` rechazada; `capture_duckdb` explícito por lotes | Salida previamente capturada o artefacto | SELECT/WITH confiable, conexión propia `:memory:` | Compilador DuckDB independiente, sin fallback a otro motor |

### Captura y pérdidas

- Transporte escalar admitido por cada ruta: NULL, booleanos, enteros con signo y
  sin signo, float32/64, texto, Decimal de escala fija, fechas y timestamps. No
  desenvolver categorías, diccionarios, estructuras, binarios o tipos extendidos
  para aparentar soporte
- Arrow directo comprueba integridad física completa, nombres únicos/no vacíos y
  rechaza metadata semántica de esquema/campos sin política. Se desacoplan buffers
  mediante IPC; la captura no puede cambiar después por mutar el origen
- Pandas conserva anchos y máscaras reconocidas. Un índice significativo permanece
  separado. Metadatos no interpretables, `attrs`, eje de columnas con nombre,
  categorías, extensiones desconocidas, subclases y objetos numéricos heterogéneos
  se rechazan. Timestamp de tipo object exige dtype temporal explícito. Decimal
  no finito, cero con signo o exponentes distintos por celda no se convierte
  silenciosamente a escala fija
- Polars mantiene las distinciones del frame eager. Categorías, anidados/object e
  int128 no se convierten implícitamente; LazyFrame es una ejecución pendiente y
  no una captura directa
- Una conversión aceptada debe conservar filas y columnas. Una tabla sin columnas
  pero con filas sólo se acepta cuando la conversión de la versión instalada
  conserva su cardinalidad; si la pierde, se rechaza. No se equiparan dos tablas
  vacías después de haber descartado sus filas
- NULL/NaN ya confundidos al construir el input, offset textual por celda/proveedor
  de zona o distinciones Decimal ya eliminadas no se reconstruyen. Conservar
  valores observados no demuestra preservar información que dejó de existir
- Los presupuestos de captura se comprueban antes/después de conversiones según
  la ruta; no son una cuota dura de RSS ni un sandbox

Funciones de frontera: `tables.check_arrow`, `tables.pandas_capture`,
`_diff_capture.capture_native`. Los nombres privados se citan para trazabilidad,
no como nuevas APIs públicas. Tests: `test_diff_capture.py` y regresiones de
`test_execution_regressions.py`.

### Comparación

La comparación utiliza el núcleo común sobre **capturas materializadas**, sin
atribuirle una nueva ejecución nativa. Contrato de salida, claves explícitas,
multiconjunto/secuencia, multiplicidad, ausencia, precisión, moneda/unidad y
política temporal conservan su significado. No rellenar NULL, redondear dinero,
normalizar texto ni deduplicar para hacer pasar la comparación.

Tipos físicos exactos son el default; mapeo lossless, orden de columnas ignorado o
índice descartado requieren autorización/justificación. Las claves deben cumplir
su política real. Expected inválido, presupuesto agotado o recorrido incompleto
no establecen equivalencia. `equivalent` significa equivalencia observada bajo
ese contrato; acuerdo entre motores no convierte Pandas ni otro motor en oráculo.

Trazabilidad: `comparison.compare`, `diff.diff`, pruebas completas de
`test_comparison.py` y [semántica](COMPARISON.md).

### Ejecución nativa

| Motor | Condiciones específicas |
|---|---|
| Pandas | Transformación devuelve DataFrame; Decimal transportable hasta precisión 76; índice aparte; filas sin columnas no admitidas |
| Polars | Salida eager o lazy materializada; decimal128 hasta 38 y escala no negativa; date64 rechazado; segundos→milisegundos sólo con comprobación de rango |
| DuckDB | Un SELECT/WITH registrado, parámetros ligados, sin acceso SQL externo; decimal128 hasta 38 y escala no negativa; rechaza nombres que colisionan ignorando mayúsculas y tablas sin columnas |

Para Polars/DuckDB un índice Pandas significativo requiere convertirlo
explícitamente en columnas o descartarlo con la política disponible. DuckDB exige
identificadores de tablas de entrada ASCII admitidos. Rechaza timestamp zoned ns,
zona distinta de sesión y valores temporales infinitos/sentinela; zoned s/ms debe
caber como microsegundos finitos. Esas restricciones no se evitan ampliando el
contrato. La captura conserva orden observado, pero SQL sin ORDER BY no lo garantiza.

`EngineCapabilities` informa precisión/unidades, lazy, dependencias, cancelación y
controles generales. No sustituye `_input_capabilities`, validadores físicos ni
las restricciones adicionales de migración. Los callbacks son código confiable;
los límites son cooperativos. DuckDB puede interrumpir una consulta y acotar
memoria administrada por el motor, no toda la memoria del proceso.

### Migración

Estado implementado antes de esta revisión, conservado desde A8; no son funciones nuevas de R2. [Contrato detallado vigente](../packages/equiframe/docs/migration-ir.md).


El registro común admite únicamente el IR cerrado implementado: Scan, Project,
Filter, Cast de ampliación exacta, EquiJoin inner/left/right/full/semi/anti, Aggregate, Sort,
Concatenate y Deduplicate idéntico o selección determinista con orden y rechazo de empates. Expresiones tipadas, lógica de tres
valores, claves NULL y sumas/grupos vacíos conservan políticas explícitas.

- Decimal común hasta precisión 38; Cast conserva escala, no introduce redondeo
- Timestamp IR condicionado por unidad/zona y motor; Pandas admite s/ms/us/ns,
  Polars ms/us/ns y DuckDB naive s/ms/us/ns o UTC us. Localización DST: Pandas/Polars
  con fold explícito y gaps rechazados; DuckDB la rechaza. Claves float de
  join/group/sort y sum/min/max float rechazados; `count_valid` puede recibir float
- Aritmética usa los operadores/tipos/cotas que valida `validate_ir`; no se promete
  aritmética genérica: multiply exacto/round tienen cotas nativas explícitas;
  divide Decimal está implementado en Pandas y rechazado por Polars/DuckDB
- Polars impone una cota conservadora para sumas Decimal; puede rechazar términos
  grandes cuya cancelación matemática produciría un total pequeño
- DuckDB restringe Aggregate/Sort intermedios que el optimizador podría eliminar;
  las formas finales admitidas conservan comprobaciones nativas
- `check_migration` valida contrato/IR y ambos compiladores sin leer datos.
  `migrate` debe comprobar además los inputs físicos, dependencias y presupuestos
- Los dos motores reciben las mismas capturas y ejecutan pipelines independientes.
  No traducir programas Python/SQL arbitrarios ni calcular una salida común para
  simular tres motores. No aceptar plugins/importaciones desde un documento JSON

Las seis direcciones tienen casos acotados en
[test_migration_semantic_directions.py](../packages/equiframe/tests/test_migration_semantic_directions.py).
Eso no acredita todas las operaciones/tipos en las seis direcciones. El
[registro semántico](SEMANTIC_SUPPORT.md) conserva sus condiciones y pendientes.

## Cómo sostener o retirar una afirmación

1. Identificar etapa, entrada, política, combinación y nodo parametrizado exacto
2. Ejecutarlo sobre bytes del candidato fijados, conservar resultados y fallos
3. Separar éxito semántico, rechazo seguro, fallo técnico y prueba no ejecutada;
   no trasladar resultados de otra versión, plataforma o corpus
4. Ante pérdida de cardinalidad, cambio de tipo o falso éxito, cerrar la ruta,
   añadir regresión y documentar recuperación antes de ampliar la afirmación

Los tests del registro cotejan runtime, compilers, dependencias, referencias y
cada superficie de estabilidad. Son controles de correspondencia, no certifican
por sí solos el motor. La [política de compatibilidad](COMPATIBILITY.md) define
avisos, ventana de retirada y excepciones fail-closed.


## Captura y admisión nativa STEP7

La etapa `capture` DuckDB pasa a `supported_with_conditions` mediante la API
explícita [capture_duckdb](DUCKDB_CAPTURE.md); no cambia la negativa de `diff` a
ejecutar relaciones lazy. Requiere conexión privada o préstamo exclusivo sin
lectores pendientes, extensiones automáticas desactivadas, consulta confiable y
presupuestos cooperativos. Guarda tipos nativos, versión, ajustes de sesión
seleccionados e intervalo; no declara snapshot distribuido o fuente inmutable.

El resultado nativo se admite antes de convertir a Arrow tanto en captura como
en ejecución. HUGEINT/UHUGEINT, UUID, ENUM, BLOB, TIME/TIMETZ, INTERVAL, nested y
extensiones no tienen mapeo admitido. Decimal128 hasta precisión 38 conserva
precisión/escala; la división SQL Decimal se observa como DOUBLE, sin convertirla
de nuevo a exacta. DATE y timestamps finitos conservan unidad y zona efectiva
cuando existe. TIMESTAMPTZ no conserva nombre de zona por fila ni ns perdidos al
leer la fuente con DuckDB. No amplía la semántica del IR de migración.
