# Captura explícita de DuckDB (STEP7)

`ef.capture_duckdb` ejecuta una consulta confiable y entrega un `TableArtifact`
desacoplado. Después pueden cerrarse la conexión y sus fuentes: `compare`, `diff`,
las aserciones y los reportes consumen los archivos capturados sin reejecutar SQL.
Es una API experimental aditiva del candidato privado, no una publicación PyPI,
un nuevo migrador ni una garantía sobre cualquier SQL o plataforma.

## Recorrido ejecutable, sin datos externos

El [ejemplo completo](../packages/equiframe/examples/capture_duckdb.py) requiere
el candidato instalado con el extra `duckdb` (DuckDB y PyArrow). Funciona al copiar
ese único script fuera del checkout: no modifica `sys.path`, no busca archivos
del repositorio, no descarga datos y no usa red, credenciales ni pandas.
La instalación del candidato y sus dependencias es un paso previo; consulte el
[paquete](../packages/equiframe/README.md#instalación-reproducible).

```bash
# Desde una carpeta que contiene la copia del script y con el candidato instalado:
python capture_duckdb.py
python capture_duckdb.py --output duckdb-report
```

El segundo comando exige una carpeta de reporte nueva. Ambos deben salir con
código 0 y mostrar `equivalent`, cinco filas verificadas y captura eliminada.
El ejemplo:

1. Declara antes de capturar un contrato de multiconjunto, sin clave inventada,
   con multiplicidad conservada e importes USD `DECIMAL(12,2)` exactos.
2. Ejecuta SQL nativo sobre cinco filas sintéticas: dos filas idénticas,
   `Decimal`, NULL, `café`, `空`, `niño`, cadena vacía y cero.
3. Captura una sola vez en lotes de dos filas; luego actualiza y elimina la
   tabla fuente y cierra la conexión.
4. Compara el artefacto con un esperado Arrow literal, independiente y en otro
   orden. No obtiene el esperado convirtiendo ni reejecutando la salida DuckDB.
5. Publica un reporte redactado y exige equivalencia con evidencia persistida.
   Vuelve a leerlo y renderiza texto/HTML después de eliminar las capturas.

Sin `--output`, todos los archivos son temporales. Con `--output` sólo quedan
`report.json`, `report.txt`, `report.html` y `evidence-manifest.json`, sin valores,
nombres ni rutas de la captura. Los archivos crudos siempre se mantienen en una
carpeta temporal separada y se eliminan al terminar. El reporte guardado es una
vista verificable del resultado; no conserva la evidencia necesaria para repetir
la comparación. El caso prueba comportamiento técnico sintético, no aceptación
del DW, corrección de un sistema real o validación científica.

## API y propiedad

```python
captured = ef.capture_duckdb(
    sql,
    work_dir=Path("private-captures"),
    name="result",
    connection=connection,          # omitir para una sesión privada
    exclusive_connection=True,       # obligatorio si se presta una conexión
    parameters={"minimum": 1},       # SQL: ... WHERE quantity >= $minimum
    options=ef.DuckDBCaptureOptions(batch_rows=4096, max_rows=1_000_000),
    cancellation=token,              # CancellationToken opcional
)
```

- `sql` es una cadena no vacía con exactamente una sentencia `SELECT`/`WITH`
  clasificada como consulta por DuckDB. No se aceptan scripts de varias
  sentencias, relaciones lazy, resultados ya ejecutados ni lectores que podrían
  estar consumidos parcialmente. `diff` tampoco ejecuta relaciones por comodidad.
- `parameters` es un mapping de nombres ASCII de forma `[A-Za-z][A-Za-z0-9_]*`;
  deben coincidir exactamente con los parámetros de la consulta. Se admiten
  `None`, `bool`, `str`, `float`, enteros de `-2**63` a `2**64-1` y `Decimal`
  finito de escala no negativa y precisión hasta 38, excepto cero negativo.
  Los Decimal se enlazan como valores nativos tipados desde texto decimal exacto,
  conservando escala y dígitos sin pasar por float. Esto evita que la inferencia
  Python de DuckDB convierta, por ejemplo, `Decimal("1E-38")` en DOUBLE.
  La misma protección se aplica a parámetros de `DuckDBAdapter`; enteros fuera
  del rango indicado y representaciones Decimal no admitidas se rechazan.
  No se admiten parámetros posicionales ni objetos temporales/UUID/arbitrarios.
  Para literales temporales use texto y un cast SQL explícito, conservando sus
  decisiones de zona/unidad. Parámetros enlazados no vuelven seguro SQL ajeno.
- El `name` debe coincidir con `contract.output.name`; los constructores
  `bag_contract`, `keyed_contract` y `sequence_contract` usan `result`.
  La captura no infiere el contrato ni introduce conversiones para cumplirlo.
- El resultado es el `TableArtifact` existente, sin un nuevo formato de tabla:
  nombre, referencia local con tamaño/SHA-256, filas, tipos nativos y Arrow,
  conteos NULL/NaN y notas. Se publica un directorio único `duckdb-<id>` dentro
  de `work_dir`, con `snapshot.arrow` (Arrow IPC **file**) y `capture.json`
  (serialización del mismo artefacto).
- El lector y la relación creados por la captura se consumen una sola vez y se
  cierran antes de publicar. No se retienen conexiones en el artefacto ni se usa
  la conexión global de DuckDB. Una excepción no publica una captura completa;
  el staging se limpia. La retención de las capturas exitosas corresponde al
  llamante: la API no las elimina automáticamente.

### Conexión prestada

Debe ser una `DuckDBPyConnection` explícita, con
`autoinstall_known_extensions=False` y `autoload_known_extensions=False` ya
configurados por su propietario. La captura rechaza la configuración contraria;
no la cambia silenciosamente. Por ejemplo:

```python
connection = duckdb.connect(
    ":memory:",
    config={
        "autoinstall_known_extensions": False,
        "autoload_known_extensions": False,
    },
)
```

`exclusive_connection=True` es el compromiso del llamante de que no hay un
resultado/lector pendiente, SQL concurrente ni fuentes externas mutando durante
la captura. El bloqueo interno sólo coordina otras capturas de esta API; no
impide SQL de otro código ni detecta un consumidor previo.

La captura usa el slot de resultado de la conexión y puede interrumpirla por
cancelación/timeout. No la cierra, cambia sus ajustes, registra/desregistra tablas,
ni hace `BEGIN`, `COMMIT` o `ROLLBACK`. Un error puede abortar la transacción del
llamante; éste debe decidir cómo recuperarla. Mantiene memoria, hilos, spill,
zona y demás capacidades de esa sesión. Si el SQL usa funciones con efectos o
acceso externo, conserva esos riesgos y permisos. La API no proporciona un
sandbox de SQL, sistema operativo, transacciones ni consistencia distribuida.
DuckDB explica por qué [SQL no confiable equivale a ejecutar código y qué
restricciones pueden aplicarse](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview).

### Sesión privada

Al omitir `connection`, EquiFrame crea y cierra su propia sesión `:memory:` con
UTC, un hilo, `memory_limit='512MB'`, `max_temp_directory_size='0B'`, acceso
externo deshabilitado, autoload/autoinstall de extensiones deshabilitados y
replacement scans de Python deshabilitados. Estos ajustes son fijos en esta API,
no argumentos adicionales de `DuckDBCaptureOptions`.

Úsela para consultas autocontenidas confiables, por ejemplo `SELECT ... FROM
(VALUES ...)`. No ve tablas registradas en otra conexión ni variables Python
por nombre. Si necesita una sesión propia, configúrela explícitamente y préstela
bajo el contrato anterior. Las restricciones de la sesión privada tampoco
convierten SQL arbitrario en entrada segura.

## Tipos nativos, valores y límites de fidelidad

Primero se comprueba el tipo nativo, antes de exportarlo a Arrow. Después se exige
el esquema Arrow exacto y se valida cada lote, sin pandas, inferencia de valores,
casts implícitos ni normalización. La misma admisión se usa en el adaptador de
ejecución DuckDB. Los nombres observados deben ser únicos y no vacíos; use alias
SQL explícitos cuando haga falta.

| Tipo DuckDB admitido | Representación capturada |
|---|---|
| `BOOLEAN` | Arrow boolean |
| `TINYINT`, `SMALLINT`, `INTEGER`, `BIGINT` | Enteros con signo de 8/16/32/64 bits |
| `UTINYINT`, `USMALLINT`, `UINTEGER`, `UBIGINT` | Enteros sin signo de 8/16/32/64 bits |
| `FLOAT`, `DOUBLE` | Arrow float32/float64; NULL y NaN se cuentan por separado |
| `DECIMAL(p,s)`, `1 <= p <= 38`, `0 <= s <= p` | Arrow decimal128 con precisión/escala iguales |
| `VARCHAR` | Arrow string, sin normalización Unicode |
| `DATE` finita | Arrow date32; sigue siendo un día |
| `TIMESTAMP_S`, `TIMESTAMP_MS`, `TIMESTAMP`, `TIMESTAMP_NS` finitos | Arrow timestamp s/ms/us/ns sin zona |
| `TIMESTAMP WITH TIME ZONE` finito | Arrow timestamp us, con la zona efectiva de la sesión |

Se rechazan `HUGEINT` y `UHUGEINT`, incluso cuando un valor concreto cabe en un
rango menor: una exportación Arrow válida no demuestra fidelidad del tipo nativo.
También quedan fuera UUID, tipos anidados (`LIST`, `ARRAY`, `STRUCT`, `MAP`,
`UNION`), ENUM/diccionarios, binarios/BLOB/BIT, TIME/TIMETZ, INTERVAL y tipos de
extensiones u otros tipos no incluidos. Los valores de infinito/sentinel de
DATE/TIMESTAMP no se presentan como fechas o instantes ordinarios.

Si su dominio permite una representación distinta, hágala explícita en el SQL y
en el contrato: por ejemplo, un cast comprobado de `HUGEINT` a `BIGINT` o a
`DECIMAL(p,0)` cuyo rango alcance. No es una conversión universal: `DECIMAL(38,0)`
no representa todo el rango de 128 bits. Convertir UUID a texto descarta su tipo
original; esta API no lo decide por usted. DuckDB documenta sus
[rangos enteros y decimales](https://duckdb.org/docs/current/sql/data_types/numeric).

La admisión sólo garantiza el transporte de las distinciones todavía observables
en el resultado DuckDB. No recupera nulabilidad original (los campos de resultado
Arrow se describen nullable), collations, signo de cero decimal, etiquetas de
zona por valor o precisión perdida durante una operación anterior.

### Fechas, timestamps y sesión

`DATE`, timestamp sin zona e instante con zona no son intercambiables. La captura
mantiene la unidad nativa; no asigna automáticamente una zona al timestamp naive.
En `TIMESTAMPTZ` DuckDB ya almacena instantes con resolución de microsegundos:
la zona del esquema Arrow describe la sesión, no la etiqueta original de cada
fila. Leer una fuente con nanosegundos y semántica zoned puede haber perdido
precisión **antes** de llegar a esta API; capturar o comparar después no restaura
esos nanosegundos. Véanse los [tipos temporales de
DuckDB](https://duckdb.org/docs/current/sql/data_types/timestamp).

La zona, los casts entre DATE/timestamp/TIMESTAMPTZ y las operaciones de calendario
pueden cambiar qué filas selecciona la consulta. Configure el contexto antes de
capturar; no cambie la sesión o los datos mientras se lee. La sesión privada fija
UTC; la prestada conserva sus ajustes. La nota de captura registra un conjunto
acotado de ajustes efectivos, versiones DuckDB/PyArrow e intervalo temporal, no
todo el entorno ni una prueba de versión de la fuente. DuckDB describe los
[efectos de la zona en casts y filtros](https://duckdb.org/docs/current/guides/sql_features/timestamps).

El orden observado se conserva en el archivo. Sólo un orden SQL explícito y
total permite exigir reproducibilidad de secuencia; operaciones, empates y
paralelismo pueden afectar el orden sin él. Un contrato de multiconjunto conserva
los duplicados sin exigir posición. Consulte las [reglas de preservación de
orden](https://duckdb.org/docs/current/sql/dialect/order_preservation).

## Presupuestos, errores y privacidad

| Opción | Default | Control |
|---|---:|---|
| `batch_rows` | 4 096 | Filas solicitadas por lote Arrow |
| `max_rows` | 1 000 000 | Filas acumuladas; admite cero para exigir salida vacía |
| `max_batch_bytes` | 64 MiB | `nbytes` del lote Arrow ya obtenido |
| `max_bytes` | 256 MiB | Tamaño serializado del archivo IPC, incluido su cierre |
| `timeout_seconds` | `None` | Tiempo cooperativo desde el inicio; positivo si se fija |

Son checkpoints cooperativos, separados de `ComparisonOptions` y
`DiffCaptureOptions`. Un lote puede haberse asignado antes de comprobar su tamaño;
el archivo puede superar el presupuesto antes del siguiente control. El binding
de constantes o parámetros y los operadores DuckDB pueden materializar resultados
antes de entregar el primer lote. Un lector de lotes no implica streaming de toda
la consulta, zero-copy, memoria constante ni límites duros de RSS o latencia.
Tampoco `memory_limit` limita toda la memoria del proceso; consulte las
[consideraciones de memoria de DuckDB](https://duckdb.org/docs/current/configuration/pragmas#memory-limit).

El timeout o `CancellationToken.cancel()` solicita interrupción de la conexión y
se comprueba durante la captura, hashing y publicación. No preempta cualquier
asignación nativa o función externa en un plazo garantizado. No hay truncamiento
exitoso al alcanzar un límite. Los errores relevantes son:

- `InvalidExecutionInput`: SQL/propiedad/parámetros no admitidos
- `CapabilityError`: tipo, representación o configuración no admitidos
- `MissingDependencyError`: falta DuckDB o PyArrow
- `ResourceLimitError`, `ExecutionTimeout`, `ExecutionCancelled`: no se obtuvo
  una captura completa dentro de las condiciones requeridas
- `NativeEngineError`: fallo nativo; las causas encadenadas pueden contener SQL,
  valores o rutas, aunque el diagnóstico público omita esos detalles
- Errores de validación o I/O: configuración inválida o persistencia fallida

Estas excepciones no son `equivalent`, ni garantizan un reporte de comparación:
la captura precede al juicio. Una comparación posterior conserva sus tres
estados y debe aceptarse mediante `assert_equivalent`, no `bool(result)`.

El archivo IPC contiene sus datos. `capture.json` conserva esquema, conteos,
ruta local y contexto limitado; no guarda SQL ni parámetros. Esa omisión no
anonimiza valores que la propia consulta devolvió. Use almacenamiento privado,
controle permisos/retención y no suba capturas, bases o resultados reales a Git.
La API no publica ni envía esos archivos. No registre sin revisar un traceback
completo. El [reporte común](REPORTS.md) oculta valores y metadatos por defecto;
su política de divulgación no protege una carpeta de capturas que se comparta
por separado.

## Relación con comparación, ejecución y migración

Use `diff(captured, expected, contract=declaration, ...)` o
`compare(captured, ArrowInput(expected), contract=contract, reference="expected",
...)` con el contrato explícito correspondiente. La captura no exige el runner
ni calcula un esperado. Una coincidencia sólo describe las capturas y políticas
evaluadas; no acredita independencia o corrección del esperado.

El nuevo ingreso no amplía el [IR acotado de migración](MIGRATION.md), no traduce
SQL a pandas/Polars y no añade tipos u operaciones a ese IR. Poder capturar un
timestamp no implica que cualquier migración temporal esté admitida. La ejecución
registrada existente también aplica el guard nativo compartido y puede rechazar
resultados antes tolerados cuya fidelidad no estaba demostrada.

La API relacional de DuckDB representa consultas lazy; una relación no equivale
a una captura inmutable. Esta frontera exige SQL y conexión de propiedad clara
para comprobar tipos y consumo antes de publicar; véase la [API relacional
oficial](https://duckdb.org/docs/current/clients/python/relational_api).
