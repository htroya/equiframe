# EquiFrame 0.10.0 — migración nativa y evidencia verificable

Contratos estrictos, comparación completa y ejecución local con Pandas, Polars y DuckDB.
Se requiere Python 3.12; los motores se instalan mediante extras. La configuración
CI cubre Windows x64, Ubuntu x64/ARM64 y macOS Intel/Apple Silicon.
La [evidencia de revisión](../../docs/STEP_08_REVIEW.md)
registra los controles completados. No se requiere una VM ni un DW para usar el
núcleo. Licencia y publicación externa pendientes; no hay paquete del equipo en PyPI.


## Instalación base y extras

La distribución todavía no está publicada en PyPI. `pip install equiframe` es
la experiencia pública objetivo, posterior al paso 10 y a una nueva ronda de revisión; podría resolver un
paquete ajeno. Use el wheel del equipo o este checkout:

```bash
python -m pip install ./dist/equiframe-0.10.0-py3-none-any.whl
python -m pip install "./dist/equiframe-0.10.0-py3-none-any.whl[duckdb]"
# Alternativas: [arrow], [pandas], [polars], [engines] o [ml].
# Desde el checkout del equipo:
python -m pip install ".[engines]"
```

Base: contratos, JSON, CLI, modelos/registro de ejecución y almacén local de
archivos con integridad. Tablas requieren `arrow` o un extra de motor; cada
motor incluye PyArrow. `engines` combina los tres y se comprueba por separado.
La importación `import equiframe as ef` no carga motores, Arrow, NumPy ni ML,
incluso cuando estén instalados. Una dependencia ausente produce
`missing_optional_dependency` e indica el extra. No se necesitan cambios de
`sys.path`, rutas del repositorio ni VM.

## Ejecución mínima funcional

Con el wheel y el extra `duckdb`, desde cualquier directorio:

```python
from pathlib import Path
import equiframe as ef
import pyarrow as pa

schema = ef.TableSchema(
    columns=(
        ef.ColumnSpec(
            name="id",
            logical_type=ef.StringType(),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
        ),
    ),
    keys=(),
    multiplicity="preserve",
    order=ef.IgnoredOrder(),
)
contract = ef.Contract(
    schema_version="1.0",
    contract_id="retail.select",
    revision=1,
    family="duplicates_order",
    inputs=(ef.TableSpec(name="inventory", schema_spec=schema),),
    output=ef.TableSpec(name="result", schema_spec=schema),
    preconditions=(),
    rules=(),
)
registry = ef.TransformationRegistry()
registry.register(
    ef.DuckDBTransformation(
        "select_id",
        'SELECT id FROM "inventory" WHERE id=$chosen',
        "my-project.v1",
    )
)
result = ef.execute(
    ef.ExecutionPlan(
        contract=contract,
        engine="duckdb",
        transformation_id="select_id",
        parameters=(ef.Parameter(name="chosen", value=ef.StringValue(value="001")),),
    ),
    source=ef.LocalDataSource(
        {
            "inventory": ef.ArrowInput(pa.table({"id": ["001", "001", "002"]})),
        }
    ),
    registry=registry,
    work_dir=Path("my-runs"),
)
assert result.state == "completed" and result.output is not None
assert ef.read_table(result.output.data).to_pylist() == [{"id": "001"}, {"id": "001"}]
print(result.run_id, result.state)
```

`completed` significa ejecución terminada y salida materializada; no acredita
corrección, equivalencia ni ausencia de anomalías. No se ejecutan precondiciones,
R, comparación o detectores. `ExecutionPlan` contiene contrato, motor, ID/revisión,
parámetros etiquetados y `ExecutionOptions`; se revalida al entrar. El registro es
por instancia y no sobrescribe implementaciones con igual ID/motor/revisión.
`code_version` es la versión declarada del código confiable, no un hash calculado
del callback ni garantía de reproducibilidad de sus efectos externos.

Pandas: `PandasTransformation(id, callback, code_version)`; el callback recibe
`Mapping[str, pandas.DataFrame]` y `RunContext`, devuelve un DataFrame. Polars:
`PolarsTransformation` recibe DataFrames y puede devolver DataFrame/LazyFrame;
se registra planificación y `collect()` por separado. DuckDB: SQL confiable
registrado, una consulta SELECT/WITH; valores `$nombre` parametrizados y nombres
de entradas ASCII controlados. Conexión propia `:memory:`, ICU del wheel, acceso
externo y descargas de extensiones deshabilitados, cierre en éxito/fallo/interrupción.
El adaptador no abre la base real del DW. El acceso al DW se integra mediante un
proveedor externo; consulte el [contrato OCI](../../docs/OCI_INTEGRATION.md).

La API admite `adapter`, `artifact_store`, `source`, `work_dir` y
`cancellation` inyectados. Los Protocols completos están en `ef`.
`LoadedTable` es el intercambio del puerto: tabla Arrow, tipos nativos, índice
opcional, origen y notas. Un proveedor externo es responsable de materializar
su snapshot explícito; la implementación local rechaza URI remotas.

## Transporte fiel y capacidades comprobadas

| Tipo/formato | Pandas | Polars | DuckDB local |
|---|---|---|---|
| bool, enteros con signo/sin signo 8–64, texto, float32/64 | Sí | Sí | Sí |
| decimal exacto Arrow | decimal128/256, hasta 76 dígitos | decimal128, escala no negativa, hasta 38 | decimal128, escala no negativa, hasta 38 |
| fechas | date32/date64 de días enteros | date32; date64 rechazado | DATE; date64 de días enteros |
| timestamp sin zona | s/ms/us/ns | s ingresa como ms si cabe en int64; ms/us/ns | s/ms/us/ns finitos |
| timestamp con zona | s/ms/us/ns | s ingresa como ms si cabe en int64; ms/us/ns | s/ms/us representables en us; zona igual a `duckdb_timezone` |
| Arrow IPC **file** / Parquet locales | Sí | Sí | Sí, vía Arrow registrado |
| diccionarios/categorías, nested, binario, objetos arbitrarios, Arrow streams | No incluidos | No incluidos | No incluidos |

La tabla delimita transporte e identidad, no garantiza que cualquier operación
nativa soporte cada tipo. Las capacidades declaradas y los tipos reales se
comprueban antes de una conversión que pudiera perder información. El contrato
admite decimal 1–76: no se reduce para satisfacer un motor. Una capacidad
incompatible produce diagnóstico explícito. La salida se captura sin usar el
esquema esperado para hacer casts, ordenar, rellenar nulos, deduplicar o redondear.
Se guardan tipos físicos nativos/Arrow, filas, máscaras NULL y conteos NaN.
Un cambio de columnas/tipo que puede representarse permanece en la salida para
validadores posteriores. Unidades/políticas declaradas permanecen en el contrato;
no se infieren unidades observadas ni se propaga metadata arbitraria como si la
hubiera generado la transformación.

Entradas: `ArrowInput`, `PandasInput`, `PolarsInput` o `ArtifactRef` local dentro de
`LocalDataSource`. Arrow se desacopla de buffers mutables del consumidor mediante
IPC; Pandas copia datos, índice y etiquetas de columnas y admite solo celdas
escalares inmutables;
Polars usa su copia y materializa lazy de entrada. El índice de Pandas se conserva
en un artefacto separado, con nombres en notas; otro motor exige
`index_policy="columns"` o `"discard"` explícito si el índice tiene significado.
Los dtypes NumPy/nullable conservan ancho y signo; Float32/Float64 nullable
conservan su máscara. Se rechazan categorías también en índices/etiquetas y
columnas `object` que mezclen tipos numéricos, antes de inferir un tipo que borre
la distinción. No se convierte automáticamente el índice en una clave. `read_table(ref)` verifica
hash/tamaño antes de leer y cierra archivos también en Windows.

Arrow decimal no representa cero decimal negativo, NaN/Infinity Decimal ni
exponentes diferentes por celda de una columna fija. Si todavía están presentes
en objetos Pandas, se rechazan antes de perderlos. No se afirma recuperar signo,
escala o distinciones que ya se perdieron al construir Arrow/Pandas/Polars.
El float NumPy conserva NaN observado; carece de máscara NULL separada. ArrowDtype
u objetos escalares con None/NaN separados permiten conservar las distinciones
que sí existen. No se reconstruye None a partir de NaN.

DuckDB rechaza los sentinels de infinito temporal en entradas y salidas: Arrow
no puede distinguirlos de épocas finitas. Los timestamps zoned s/ms deben caber
en microsegundos; Polars rechaza segundos que desborden al convertirlos en ms.
Las tablas de cero columnas se conservan donde el motor retiene su cardinalidad
o se rechazan explícitamente.

Arrow representa instantes y una zona por columna, sin conservar el texto ISO ni
el offset original por fila; para conservarlos, el consumidor debe aportar columnas
explícitas de texto. Timestamp zoned ns se rechaza en DuckDB, incluso si un caso
concreto fuera divisible por us. Contratos usan tzdata Python fijado; Pandas usa
el proveedor tzinfo de la entrada, Polars chrono-tz compilado y DuckDB ICU del wheel.
No se presupone una base IANA común: se registran versiones del motor/runtime,
proveedor/configuración, y la falta de versión IANA expuesta cuando corresponda.
[DuckDB documenta la precisión zoned](https://duckdb.org/docs/current/sql/data_types/timestamp);
[Polars documenta casts de tipos no admitidos](https://docs.pola.rs/api/python/stable/reference/api/polars.from_arrow.html).

## Estados, evidencia y controles locales

Cada llamada obtiene IDs y carpeta propios `work_dir/run_id/execution_id`.
Entradas capturadas y salida son Arrow IPC con referencias SHA-256; el manifiesto
`run.json` incluye plan/contrato/huella, código, versiones, configuración efectiva,
referencias originales, tipos observados, tiempos, estado y diagnóstico. Publicación
exclusiva mediante temporal y enlace local atómico; nunca reemplaza otra corrida.
El almacén requiere un sistema de archivos local con enlaces duros (compatibilidad registrada en la matriz CI). Un fallo de publicación se eleva; no se retorna
un éxito sin manifiesto. No hay reintentos automáticos ni servicio de concurrencia.
Si falla el guardado del índice después de publicar datos, el resultado fallido
conserva la referencia de datos y una nota de captura incompleta. Esa entrada o
salida parcial no acredita una tabla íntegra; el diagnóstico identifica la etapa.
Los fallos de descarga limpian sus temporales y los fallos durante el setup DuckDB
cierran también la conexión creada. Un pánico FFI de Polars se registra como
`failed` con código `native_engine_error`.

El manifiesto verifica su huella contra el contrato incorporado, nombres de
entradas/salida y coherencia de los conteos/esquemas físicos. Esos controles son
estructurales: no comparan los datos con el esquema esperado.

| Estado | Alcance |
|---|---|
| completed | Transformación y materialización completadas; semántica pendiente |
| invalid_input | Fuente/registro/capacidad/dependencia no utilizable |
| failed | Callback, SQL, conversión o I/O fallida |
| timeout | Presupuesto superado en checkpoint o consulta interrumpida |
| resource_exhausted | MemoryError, límite DuckDB o presupuesto tabular agotado |
| cancelled | Señal de cancelación observada en checkpoint o consulta interrumpida |

Planes inválidos, motor desconocido sin adaptador inyectado y fallos de crear/publicar
la carpeta se elevan al llamante; fallos operativos dentro de una corrida producen
`ExecutionResult.problem`. No se vuelcan valores/SQL/mensajes arbitrarios de
excepciones de callbacks. El contrato/parámetros y artefactos pueden contener datos
del consumidor: el directorio elegido sigue bajo su responsabilidad.

`CancellationToken.cancel()` y `RunContext.check()` son cooperativos. Pandas,
callbacks de Polars y `collect()` no se ejecutan en procesos descartables: un
callback que ignora checkpoints puede seguir hasta retornar. La función espera
ese retorno y reporta timeout; no promete límite duro ni devuelve mientras queda
un callback propio ejecutándose. DuckDB tiene monitor por corrida que interrumpe
consulta, se une y cierra conexión; no ofrece un límite de reloj duro para toda la
carga/captura Python. `duckdb_memory_mb` limita memoria administrada por el motor,
`duckdb_threads` controla hilos y spill está deshabilitado; no son un límite RSS
para Arrow/Python. `max_input_rows`, `max_output_rows` y `max_transport_bytes` se
comprueban por tabla materializada (bytes de buffers y tamaño declarado de archivo
entrante, incluidos los buffers del índice); no impiden una asignación previa ni son cuotas agregadas de servicio.
Callbacks/SQL son código confiable del usuario, no un sandbox.

Ejemplos ejecutables de comercio y telemetría para cinco familias:

```bash
uv run --locked --all-extras python examples/execute_native.py --work-dir .cache/examples
# Funciona con cada extra individual:
python examples/execute_native.py --engine polars --work-dir my-runs
```

Los esperados pequeños son explícitos e independientes de las salidas. Los ejemplos
no son el benchmark de 60 escenarios ni aprobación científica de EquiFrame Verify.

## Instalación reproducible

Desde la raíz del repositorio, con Python 3.12 instalado (Windows):

```powershell
python -m venv .tools
.\.tools\Scripts\python.exe -m pip install --no-deps uv==0.11.6
Set-Location packages/equiframe
$uvEquiframe = (Resolve-Path ..\..\.tools\Scripts\uv.exe).Path
& $uvEquiframe sync --locked --python 3.12
& $uvEquiframe run --locked equiframe contract validate examples/nulls_types.json
```

`uv.lock` fija versiones y hashes, incluidos los marcadores de plataforma.
`sync` crea `.venv` editable para desarrollo; `--no-dev` instala solo ejecución.
No se reutiliza Anaconda como entorno de dependencias; puede proporcionar
el intérprete base. `.tools` solo contiene el gestor uv fijado.

Linux o macOS, desde la raíz, con `python3.12` instalado:

```bash
python3.12 -m venv .tools
.tools/bin/python -m pip install --no-deps uv==0.11.6
cd packages/equiframe
../../.tools/bin/uv sync --locked --all-extras --python 3.12
../../.tools/bin/uv run --locked --all-extras equiframe contract validate examples/nulls_types.json
```

Los comandos siguientes usan `uv` en PATH; en Windows puede sustituirse por
`& $uvEquiframe`, y en Linux/macOS por `../../.tools/bin/uv`.

## API pública

Desde `packages/equiframe`, con el paquete instalado:

```python
from pathlib import Path
from equiframe import (
    ContractValidationError,
    canonical_contract_bytes,
    contract_fingerprint,
    contract_json_schema,
    read_contract,
    validate_contract,
    write_contract,
)

contract = read_contract("examples/aggregations.json")
assert validate_contract(canonical_contract_bytes(contract)) == contract
print(contract.contract_id, contract.revision, contract_fingerprint(contract))
Path(".cache").mkdir(exist_ok=True)
write_contract(contract, ".cache/contract.json")
schema = contract_json_schema()

try:
    validate_contract('{"schema_version":"99.0"}')
except ContractValidationError as error:
    for issue in error.issues:
        print(issue.path, issue.code, issue.message)
```

`validate_contract` acepta texto JSON, bytes UTF-8 o un mapping compatible con
JSON. Los constructores aceptan tipos Python declarados: tuplas para colecciones
inmutables, `Decimal` o texto decimal exacto; booleanos/enteros no se convierten
desde cadenas. Se rechazan campos desconocidos, miembros duplicados de JSON,
versiones desconocidas, números JSON NaN/Infinity y decimales desde números.
`equiframe.__all__` enumera la API explícita; `py.typed` declara tipado.

Tipos lógicos: booleano, entero (8/16/32/64 bits y signo), cadena, decimal
(precisión 1–76 y escala 0–precisión), float (32/64), día y timestamp
(s/ms/us/ns, zona opcional). El límite decimal es una decisión del formato;
no garantiza soporte de ese intervalo por un futuro adaptador.

Los esquemas declaran claves/ámbito (`table`, `global`, `columns`), claves
incompletas, multiplicidad y orden. `preserve` conserva multiplicidad;
`distinct` exige filas normalizadas únicas, sin deduplicar. `significant` declara columnas,
dirección, posición de ausencias y empates. El validador comprueba coherencia
y referencias; no verifica datos ni unicidad real.

Ausencia, NaN, cadena vacía y cero son distintos. Equivalencias vacío/cero con
ausencia o NaN con ausencia requieren política explícita, columna nullable y
justificación. NaN solo es válido en floats. Columnas numéricas requieren unidad
y comparación explícitas; decimal siempre exacto. Tolerancias aproximadas:
límites no negativos, unidad coincidente y justificación. Redondeo decimal:
modo y motivo explícitos; no se aplica al validar ni serializar.

Timestamps: texto ISO hasta nueve dígitos fraccionarios, offset y zona IANA
separada, sin float ni truncamiento a microsegundos. No se admiten leap seconds
ni offset desconocido `-00:00`. Se validan calendario, granularidad, offset/zona,
intervalos y política de timestamps sin offset. Asignar zona exige resolución
explícita de horas ambiguas; huecos DST se rechazan. Fechas siguen siendo días.
Las reglas IANA se leen exclusivamente del paquete `tzdata` fijado en `uv.lock`,
también en Ubuntu. La base del sistema y `PYTHONTZPATH` no alteran la validación;
actualizar `tzdata` exige revisar políticas y repetir las pruebas.
`allowed_values` declara restricciones tipadas, no tablas de prueba.

Reglas/precondiciones: seis formas cerradas (`schema`, `key`, `cardinality`,
`join`, `order`, `aggregate`), con referencias verificadas, revisión, severidad,
obligatoriedad y aplicabilidad. No se ejecutan ni aceptan callbacks/SQL/expresiones.
Las reglas ejecutables se registran mediante `RuleRegistry` desde el paso 4.
Joins y grupos numéricos conservan unidades. `sum`, `min` y `max` conservan
la unidad de la medida; `min`/`max` también su tipo lógico. Una suma admite
ampliación explícita dentro de la misma familia numérica, sin reducir el dominio
del tipo fuente: rango entero, dígitos enteros/escala decimal o bits de float.
Esto no garantiza que datos concretos sumados quepan en el resultado.
No hay conversiones implícitas de moneda ni de decimal a float. `OrderCheck`
remite a todas las columnas, en su orden, de la política `significant`, que
aporta dirección, ausencias y empates. Los literales float32 de comparación
exacta deben ser representables sin redondeo ni subdesbordamiento.

`ArtifactRef` describe URI, SHA-256, formato, tamaño y esquema opcional. Rechaza
credenciales, query y fragmentos de URI. La referencia declara metadatos; el almacén local verifica hash y tamaño al copiar. `ArtifactStore`, `DataSource` y `EngineAdapter` tienen tipos completos e implementaciones locales. Snapshots remotos, reglas ejecutables, perfiles y detectores se definen en pasos posteriores.
Se valida sintaxis de puertos, separadores y escapes porcentuales; solo HTTPS
admite puerto explícito. Se aceptan IPv6 y rutas con espacios codificados.

## JSON canónico y huella

`equiframe-metadata-json-v1`: volcado JSON de modelos revalidados, todos los
campos/defaults/`null` incluidos, claves de objetos ordenadas por puntos de
código Unicode según Python, arrays en su orden declarado, UTF-8 sin BOM,
sin normalización Unicode, espacios ni salto final. No es RFC 8785/JCS.
Floats finitos usan `json.dumps` de Python 3.12; no se repara precisión perdida
antes de validar. La CLI usa la misma lógica que la API.

Decimal usa `str(Decimal)` con `capitals=1` en un contexto local: conserva signo
(incluido cero negativo), dígitos y
exponente/escala. `"1.0"` y `"1.00"` pueden tener huellas distintas. Timestamps
mantienen texto, fracción, offset y zona, sin conversión a UTC. Valores
especiales etiquetados: `{"kind":"null"}`, `{"kind":"nan"}` y
`{"kind":"infinity","sign":"positive"}`; vacío y cero siguen separados.
Cambiar precisión, capitalización, límites de exponentes o flags del contexto
decimal del consumidor no cambia los bytes canónicos ni modifica su contexto.

`contract_fingerprint` es SHA-256 de los bytes canónicos e incluye ID/revisión.
El orden/espaciado de miembros del JSON original no cambia la huella; el orden
de arrays y las políticas sí forman parte de la representación. No compara
datos, prueba equivalencia tabular ni acredita revisión científica.

Los archivos `schemas/contract-1.0.schema.json` y
`schemas/artifact-ref-1.0.schema.json` se generan desde los modelos. JSON Schema
cubre estructura/tipos; referencias, zonas, DST y coherencia entre campos
requieren la API. Solo se admite versión de esquema `1.0`, obligatoria.
No hay migración automática.

## CLI y errores

```bash
uv run --locked --all-extras equiframe contract validate examples/dates.json
uv run --locked --all-extras python -m equiframe contract validate examples/joins.json
```

| Código | Significado de `contract validate` |
|---|---|
| 0 | Contrato válido; imprime ID/revisión y SHA-256 de metadatos |
| 2 | JSON, contrato, versión o argumentos inválidos |
| 3 | Fallo de lectura del archivo |

Errores a stderr con ruta JSON y código concreto. El comando no usa 1 porque
no evalúa alertas/diferencias. `ContractValidationError.issues` contiene ubicación,
código y mensaje; `SchemaVersionError` y `ContractParseError` son subclases.
`ContractIOError` identifica I/O fallida. Constructores directos usan
`pydantic.ValidationError`; los servicios públicos traducen errores de validación.
Miembros JSON duplicados identifican su ruta anidada; claves con controles o
surrogates se escapan para que el diagnóstico se pueda imprimir. Errores de
literales temporales conservan el código específico y su ubicación. Los mensajes
de constructores omiten valores de entrada; `ValidationError.errors()` y la
cadena de causas pueden conservarlos y no se deben registrar indiscriminadamente.

## Verificación y distribución

Desde `packages/equiframe`, después de `uv sync --locked --all-extras`:

```bash
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy
uv run --locked --all-extras python tools/generate_assets.py --check
uv run --locked --all-extras pytest -q
uv run --locked --all-extras python -m build --no-isolation
uv run --locked --all-extras python tools/verify_distribution.py
```

El backend y sus dependencias están en el lock; `--no-isolation` usa ese entorno.
Build produce `dist/equiframe-0.4.0-py3-none-any.whl` y
`dist/equiframe-0.4.0.tar.gz`. El verificador crea entornos temporales fuera del checkout, instala dependencias runtime del lock y el wheel sin editable,
comprueba `py.typed` e importación sin motores/ML/dev, valida cinco ejemplos por
CLI y reconstruye desde el sdist comparando todos los bytes del wheel.
También instala cada extra y la combinación engines sin editable, ejecuta los ejemplos copiados fuera del checkout y comprueba roundtrips de API y errores/códigos de CLI instalada, ejecuta
la batería completa y la regeneración de assets desde el sdist contra el wheel
instalado, y verifica un consumidor de la API con mypy estricto.
Acepta `--uv /ruta/al/uv` si el gestor no está en PATH.

Regeneración intencional de esquemas/fixtures:

```bash
uv run --locked --all-extras python tools/generate_assets.py
```

Cambiar dependencias exige resolver un nuevo lock y repetir CI. `pip install
dist/equiframe-0.4.0-py3-none-any.whl` funciona, pero solo el lock reproduce el
entorno comprobado. Los fixtures no fijan cohorte, escala monetaria real, alpha
ni tamaño del benchmark. Detectores y perfiles permanecen fuera de esta versión.

Las versiones concretas comprobadas son las del `uv.lock`, no todas las combinaciones admitidas por los rangos de metadatos. La suite conserva los contratos anteriores y añade regresiones con motores reales.
El mínimo de DuckDB es 1.5.6: versiones anteriores admitidas por 0.2.0 no
ofrecían toda la API usada. No se certifican todas las versiones del intervalo.

DuckDB rechaza columnas de entrada cuyos nombres coinciden ignorando mayúsculas
y minúsculas, antes de registrarlas: el motor las renombraría automáticamente.

## Comparación completa de salidas

La nueva API solo necesita el extra `arrow`. Acepta `ArrowInput`, `ArtifactRef`,
`Path` a Arrow IPC file/Parquet local, `TableArtifact` y `ExecutionResult` completed.
No ejecuta de nuevo la transformación ni necesita los otros motores instalados.

Desde otro proyecto, con un contrato y salidas locales propios:

```python
from pathlib import Path
import equiframe as ef

contract = ef.read_contract(Path("my-contract.json"))
result = ef.compare(
    Path("candidate.parquet"),
    Path("independent-expected.parquet"),
    contract=contract,
    reference="expected",
    work_dir=Path("comparison-evidence"),
    options=ef.ComparisonOptions(batch_rows=4096, max_examples=20),
)
print(result.state, result.complete, result.counts)
for difference in ef.iter_differences(result.differences):
    print(difference.code, difference.key, difference.column)
```

Ejemplo autocontenido, sin archivos previos ni motores:

```bash
python examples/compare_local.py --work-dir comparison-runs
```

`ComparisonPolicy()` conserva orden de columnas, firma lógica e índices por
defecto (índices separados no evaluables). Permisos suplementarios requieren
justificación: `column_order="ignored"`, `physical_types="lossless"` o
`index="ignore"`. Son parte de `ComparisonSpec`, documento independiente 1.0;
no cambian bytes/huellas de Contract 1.0. La versión del paquete es 0.7.0 y la
revisión del contrato conserva su función propia.

Se verifican datos y restricciones del esquema de salida, incluidas claves antes
y después de normalizar, multiplicidad y orden. Se alinean claves solo si se
comprobaron únicas/completas; se comparan secuencias o multiconjuntos completos.
Tolerancias usan `abs(a-b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))` con
aritmética exacta sobre valores representados. En multiconjuntos se calcula un
emparejamiento máximo, con límites explícitos por grupo, sin asumir transitividad.
Decimales no se redondean para coincidir y timestamps conservan nanosegundos.

`equivalent` exige completitud sin incumplimientos. `different` tiene evidencia
completa; una referencia esperada inválida, incapacidad técnica, cancelación o
presupuesto agotado produce `not_evaluable`. Los conteos incompletos llevan
`final=False`. El resumen limita ejemplos, mientras `differences.jsonl` conserva
todos los registros con valores tipados/multiplicidades y referencia SHA-256.

La lectura es por lotes y el trabajo usa SQLite privado en disco. Lotes, filas,
trabajo, disco, evidencia, parejas, tamaño de grupos y tiempo se configuran en
`ComparisonOptions`. Son controles cooperativos y presupuestos contables, no
cuotas RSS ni tiempos duros. IPC puede decodificar un lote almacenado antes de
comprobar sus bytes. Los detalles normativos están en
[semántica, estados y límites](../../docs/COMPARISON.md).

El alcance declarado es `output_schema`: no ejecuta reglas/precondiciones R,
perfiles, M/B/H ni revisión O. Dos motores pueden coincidir en un error. La CLI
operacional y la evaluación experimental continúan en sus pasos posteriores.
El verificador de distribución ejecuta estos ejemplos y la comparación entre
motores desde wheel instalado fuera del checkout, además del consumidor mypy.

## Reglas operativas R

Con `run.json` y sus artefactos accesibles, el extra `arrow` es suficiente:

```python
from pathlib import Path
import equiframe as ef

run = ef.ExecutionResult.model_validate_json(Path("run.json").read_bytes())
evaluation = ef.evaluate_rules(run, work_dir=Path("rule-evidence"))
print(evaluation.decision, evaluation.complete, evaluation.coverage)
for check in evaluation.rules:
    if check.findings is not None:
        for finding in ef.iter_rule_findings(check.findings):
            print(finding.code, finding.table, finding.position)
```

La [semántica y tabla de decisiones](../../docs/RULES.md) especifica los seis
chequeos, precondiciones, evidencia, límites y huellas. El
[catálogo técnico](examples/rules/catalog-1.0.json) y
[`rules_catalog.py`](examples/rules_catalog.py) ejecutan cinco controles
sintéticos sin los tres motores.
[`rules_from_run.py`](examples/rules_from_run.py) relee un `run.json` guardado
y evalúa sus artefactos sin cargar motores.

## Perfiles y preprocesamiento

Con el extra `arrow`, `ef.profile_execution(run, spec=spec)` calcula las diez
fórmulas de la sección 3.6 de la tesis según una especificación explícita por
familia. Conserva conteos, denominadores, motivos y evidencia de una sola captura.
Las conversiones fallidas exigen recibos instrumentados; no se infieren de NULL.

`ef.fit_preprocessor` ajusta medianas solo con `NormalTrainingProfiles` y
`ef.transform_profiles` produce una matriz numérica común para M/B.
Medianas y orden persisten en JSON; los fallos técnicos no se imputan. La selección
de entrenamiento normal necesita un manifiesto externo: el núcleo no valida O
ni los grupos de procedencia. No se entrenan detectores en este paso.

```bash
python examples/profiles_from_run.py ruta/run.json examples/profiles/nulls_types.json
python examples/preprocess_profiles.py --training ruta/profile.json --selection-manifest seleccion.json --score ruta/prueba/profile.json --output preprocessor.json
```

Las cinco especificaciones de `examples/profiles/` corresponden a las capturas
sintéticas de `rules_catalog.py`. El verificador del wheel ejecuta todas y restaura
el preprocesador fuera del checkout. [API, fórmulas, estados y límites](../../docs/PROFILES.md).

## Detectores M/B/H desde 0.7.0

Instale `python -m pip install ".[ml]"` para entrenar Isolation Forest.
`ef.fit_detectors` utiliza las mismas medianas congeladas y la misma matriz para
M y MAD. `ef.calibrate_detectors` recibe una selección normal distinta y alpha
explícito; `ef.detect` aplica umbrales sin reajustar. `ef.combine_decisions`
conserva las alertas y la incompletitud de R/M. El paquete base restaura e
infiere bundles JSON sin sklearn, NumPy ni motores.

Ejemplo sintético ejecutable:

```bash
python examples/detectors_local.py --bundle detectors.json
python examples/detectors_local.py --bundle detectors.json --restore-only
```

Cada ruta de bundle es nueva; no se sobrescribe. [Guía de detectores](../../docs/DETECTORS.md)
y [diseño del paso 7](../../docs/STEP_07_DESIGN.md) detallan estados, fórmulas,
independencia, persistencia y límites. Los ejemplos no acreditan normalidad
científica ni el control poblacional de falsas alarmas. PyPI sigue pendiente.

## Migración nativa desde 0.10.0

`ef.migrate` ejecuta un plan relacional declarado en origen y destino, compara
salidas y permite verificarlas contra un esperado capturado por separado.
`ef.check_migration` comprueba metadatos sin ETL; `ef.read_migration` valida
la evidencia sin reejecutar motores. La [guía de EquiFrame Migrate](../../docs/MIGRATION.md)
describe IR, API/CLI, componentes requeridos, extensiones y límites reales.

Con el extra `engines`, el ejemplo sintético comprueba las seis direcciones:

```bash
python examples/migrate_native.py --output migration-runs
```

`require_rules=True` conserva R como requisito; `False` permite exigir solo
los componentes solicitados y mantiene los estados originales de R/H.
Equivalencia entre motores no acredita corrección independiente. No se entrena
durante la migración ni se traduce código Python/SQL arbitrario.
