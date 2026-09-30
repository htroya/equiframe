# Comparación completa — EquiFrame 0.3.0

Decisiones de ingeniería del paso 3, 2026-09-30. La API compara salidas ya
materializadas; no ejecuta transformaciones, R, perfiles, M, B, H ni revisiones O.
`equivalent` significa equivalencia de las salidas bajo el esquema y las políticas
de comparación declarados. No acredita que una transformación implemente su
intención, ni que sus precondiciones/reglas operativas hayan sido evaluadas.
Dos motores pueden compartir un error. El comparador es una herramienta del
futuro oráculo, cuya revisión independiente sigue pendiente.

## API e instalación

Con el wheel del equipo y el extra `arrow` basta; no se requiere ningún motor,
SERCOP, OCI, credenciales o benchmark. El soporte declarado sigue siendo
`>=3.12,<3.13`. Publicación PyPI y licencia siguen pendientes del paso 10.

```python
result = ef.compare(
    candidate, expected,
    contract=contract,
    reference="expected",
    options=ef.ComparisonOptions(batch_rows=4096, max_examples=20),
    work_dir=Path("evidence"),
)
```

Cada lado admite `ArrowInput`, `ArtifactRef` local, `Path` a Arrow IPC **file** o
Parquet, `TableArtifact` y `ExecutionResult`. Un DataFrame se captura primero con
la API de ejecución o se convierte explícitamente a un transporte que conserve
sus distinciones; no se infiere desde listas/dicts ni se ejecutan callbacks aquí.
Una `Path` se identifica al capturar sus bytes; una referencia además exige que
coincidan tamaño y SHA-256. Los archivos originales no se modifican.

Un `ExecutionResult` debe ser `completed`, revalidar su contrato/huella y contener
la salida y todas sus entradas. Se verifica el contenido de los artefactos de
entrada, salida e índices frente a sus hashes, esquema físico, filas y conteos
NULL/NaN. Dos ejecuciones requieren las mismas entradas por nombre, hash de bytes
y tamaño, y los mismos parámetros. Se rechazan entradas serializadas de forma
diferente aunque puedan representar datos equivalentes: use un snapshot común.
Para comparar resultados intencionalmente provenientes de entradas diferentes,
el consumidor puede comparar sus `TableArtifact` explícitamente, sin afirmar que
las ejecuciones tuvieron entradas iguales. `engine_type` es metadato capturado;
no se vuelve a ejecutar el motor para reconstruirlo.

Ejemplos completos: [consumidor Arrow](../packages/equiframe/examples/compare_local.py)
y [cinco familias con motores reales](../packages/equiframe/examples/execute_native.py).
Este último usa esperados pequeños con valores/esquemas escritos explícitamente,
compara cada motor con ellos y cada pareja con las mismas entradas verificadas.

## Versiones y autorización

El paquete es **0.3.0**. `Contract`, `ExecutionPlan`, `ExecutionResult` y
`ArtifactRef` conservan formato **1.0**, campos, defaults y bytes canónicos previos.
La `revision` de cada contrato sigue identificando su revisión semántica.

El nuevo documento `ComparisonSpec` tiene su propio formato **1.0** e incorpora
el contrato completo y `ComparisonPolicy`. Su huella se calcula con JSON ASCII
escapado, claves ordenadas, defaults/null incluidos, sin espacios ni salto final
(`equiframe-comparison-json-v1`). Se registra además la huella original del
contrato. No se interpreta un formato antiguo como si contuviera permisos nuevos.
Para modificar un permiso se crea una especificación nueva, con huella nueva;
no hay migración implícita. Los cuatro esquemas `comparison-*-1.0.schema.json`
se generan desde los modelos públicos. Las restricciones cruzadas requieren la API.

| Política suplementaria | Default conservador | Autorización disponible |
|---|---|---|
| `column_order` | `significant`: nombres en el orden del contrato | `ignored`: alinear por nombre |
| `physical_types` | `exact`: misma firma lógica | `lossless`: variantes de la misma familia si cada valor cabe exactamente |
| `index` | `reject`: índice separado impide evaluación | `ignore`: excluirlo explícitamente; se verifica su integridad |

Cualquier permiso no conservador requiere `justification`. El índice nunca se
convierte automáticamente en clave. Si tiene significado, se promueve a columnas
antes de la captura y se incluye en el contrato. La política `ignore` excluye
todo índice separado, incluso un RangeIndex; el resultado registra su aplicación.

## Esquema y normalización

El esquema físico observado se guarda por separado. Nombres ausentes/adicionales,
orden no autorizado y tipos incompatibles son incumplimientos observables, aunque
ambos lados sean idénticos. Se comprueban nullable, `allowed_values`, intervalos,
granularidad, claves, multiplicidad y orden del esquema de salida.

Firma lógica: boolean; integer con ancho/signo; float con ancho; decimal con
precisión/escala; string; date; timestamp con unidad/zona. Los almacenamientos
string/large_string/string_view representan el mismo tipo lógico string;
decimal128/256 con la misma precisión/escala representan el mismo decimal;
date32/date64 representan días, comprobando que date64 no contenga fracciones.
Estas correspondencias se documentan como parte del formato de comparación.

Con `lossless`, enteros de otro ancho/signo deben caber en el tipo declarado;
float64→float32 exige representabilidad exacta; decimales de otra escala deben
ser divisibles exactamente y caber en la precisión declarada. No se convierte
entre integer, float, decimal o string. Una columna Arrow `null` solo puede
especializarse con este permiso y si el contrato admite ausencia. Una tabla vacía
conserva y valida su esquema, sin inferir tipos a partir de valores inexistentes.

Ausencia, NaN, cadena vacía y cero se mantienen distintos salvo `NullPolicy` y
`NaNPolicy` expresas. `forbid` es incumplimiento; `distinct` trata NaN como una
categoría diferente de NULL y de todos los números, con multiplicidad; `as_null`
lo normaliza a ausencia. No distingue payload/signaling de NaN. Ceros float con
signo tienen igual valor numérico, conservando el signo original en la evidencia.
No se recortan cadenas, normaliza Unicode ni eliminan ceros de identificadores.

Decimales se comparan con aritmética racional exacta, sin float, sin depender del
contexto Decimal y sin redondear. `rounding` describe la transformación; no concede
permiso para corregir su salida. Monedas/unidades declaradas no se convierten.
Los valores de una columna moneda son contenido ordinario que debe coincidir.
Una unidad física no codificada en los datos no se puede verificar por inferencia.

## Claves, multiplicidad y orden

Se verifican **todas** las claves del esquema, antes y después de normalizar.
`scope=columns` antepone esas columnas a la clave compuesta. `table` y `global`
usan la clave completa sobre la salida comparada: este servicio no certifica
unicidad en otras tablas, snapshots o catálogos externos. Ausencia lógica en
cualquier componente de clave/ámbito es incompletitud; NaN distinto es un valor
presente. `reject` genera incumplimiento. `allow` conserva las filas incompletas
y las excluye de la prueba de unicidad, sin inventar claves ni descartarlas.
Las representaciones autorizadas como ausencia cuentan como incompletas también
en la comprobación previa: repetir claves vacías/cero/NaN declaradas ausentes
no crea un falso duplicado bajo `incomplete=allow`.

Si el orden se ignora, se selecciona la primera clave `unique=True` declarada;
solo se usa si se comprobaron unicidad y completitud en ambos lados. Si no,
se compara el multiconjunto íntegro. Los valores de clave se alinean exactamente,
incluso si la columna declara tolerancia para medidas: no hay claves aproximadas.
Las demás claves siguen siendo restricciones verificadas.

`multiplicity=preserve` cuenta cada ocurrencia. `distinct` exige que cada fila
normalizada aparezca como máximo una vez; no autoriza deduplicar la salida.
La proximidad aproximada nunca define unicidad ni deduplicación.

`SignificantOrder` exige secuencia en el orden declarado, verificando dirección y
ubicación de NULL. `ties=preserve` conserva la posición relativa observada en los
empates; un intercambio de filas distintas dentro del empate es una diferencia.
`ties=reject` exige valores de orden sin empate. No se ordena para reparar salidas.
Para ordenar floats: −infinito < finitos < +infinito < NaN; NULL usa `SortSpec.nulls`.
Comparaciones y empates de orden usan valores exactos, sin tolerancia.

## Tiempo y aproximaciones

Fechas son días enteros desde 1970-01-01. Timestamps se leen como enteros de su
unidad física y se llevan exactamente a nanosegundos; no pasan por float ni por
`datetime` para comparar fracciones. `instant` compara el instante; `wall_time`
compara hora local. Cambios de zona solo se permiten con `lossless` y `instant`;
hora local exige la zona declarada. Cambio de unidad debe preservar exactamente
la granularidad del contrato. `naive=preserve` conserva hora local sin zona;
`reject` rechaza observaciones naive; `assume_zone` aplica la zona y resolución
DST declaradas, conservando ns. Los huecos DST siempre son incumplimiento.

Cálculos de zona/DST usan exclusivamente tzdata y, cuando requieren calendario,
años 1..9999; fuera de esa capacidad se devuelve `not_evaluable`. Enteros temporales
extremos sin conversión de zona se conservan. Arrow no conserva el offset textual
original por fila, signo de cero decimal ni exponentes originales distintos de
una columna decimal fija. No se recuperan distinciones perdidas antes del transporte;
si son parte del requisito, deben almacenarse en columnas explícitas.

Para integer/float con tolerancia ya fijada en el contrato:

`abs(a-b) <= max(absolute or 0, (relative or 0) * max(abs(a), abs(b)))`.

Fórmula simétrica e inclusiva; los números IEEE finitos se evalúan como sus
racionales exactos y las tolerancias como decimales exactos. Infinitos solo
coinciden con el mismo signo; NaN sigue su política, sin entrar en la fórmula.
No se estiman tolerancias con los datos. La relación no es transitiva.

Multiconjuntos aproximados se dividen únicamente por columnas de igualdad exacta.
Dentro de cada grupo se construye el grafo completo de parejas permitidas y se
obtiene un emparejamiento máximo mediante caminos aumentantes. Se preservan las
ocurrencias y se registran todas las no emparejadas. Un grupo demasiado grande
produce `not_evaluable`; no se usa agrupación aproximada ni asignación voraz.

## Lotes, disco y límites

El comparador usa lectores por lotes, sin `read_table`/`read_all`, y una base SQLite
privada con índices de valores completos en disco. Todas las corridas usan spill,
incluidas las pequeñas. El hash solo selecciona partición; un índice BLOB contiene
los valores canónicos completos. Una colisión de hash no fusiona grupos distintos.
La ruta exacta recorre grupos con memoria independiente de su número de filas;
la ruta aproximada limita explícitamente cada grupo, incluso con fuerte sesgo.

| Presupuesto | Default / alcance |
|---|---|
| `batch_rows` / `max_batch_bytes` | 4096 filas / 64 MiB por lote decodificado |
| `max_row_bytes` | 1 MiB de representación JSON original + normalizada |
| `partitions` / `sqlite_cache_kib` | 16 particiones / sugerencia de caché SQLite 4096 KiB |
| `max_rows` | 10 millones de filas de salida combinadas |
| `max_work` | 100 millones de unidades: visitas/celdas/aristas e instrucciones SQLite |
| `max_disk_bytes` | 4 GiB de snapshots, evidencia y trabajo observado; páginas SQLite limitadas |
| `max_evidence_bytes` / `max_examples` | 512 MiB de diferencias completas / 20 ejemplos en resumen |
| `max_matching_rows` | 2000 ocurrencias combinadas en un grupo aproximado |
| `max_matching_bytes` | 32 MiB de presupuesto contable para JSON, estructuras y aristas |
| `max_pair_checks` | 2 millones de parejas evaluadas |
| `max_numeric_digits` | 4096 dígitos o magnitud de exponente de las tolerancias; evita expansiones racionales ilimitadas |
| `timeout_seconds` | Sin default; reloj cooperativo y token `CancellationToken` |

Estos controles son presupuestos del algoritmo y checkpoints, **no cuotas de RSS
ni tiempo duro**. El tamaño de un lote IPC almacenado es indivisible durante su
decodificación: puede asignarse antes del control de bytes. Parquet también puede
asignar buffers internos antes del checkpoint. El input Arrow en memoria ya es
propiedad del consumidor. SQLite y Python tienen sobrecostos; el presupuesto de
matching contabiliza representaciones/aristas, no mide el heap real. La escritura
de un bloque puede preceder al control de disco. Publicar el manifiesto final y
cerrar recursos queda fuera del presupuesto para poder informar su agotamiento.

Lectores, conexiones y archivos temporales de trabajo se cierran/eliminan en
éxito, error o cancelación cooperativa. Se conservan los snapshots completos
referenciados y la evidencia parcial para auditoría. Una terminación forzada del
proceso o fallo físico del disco no tiene garantía de limpieza/publicación.

Lectores oficiales: [ParquetFile.iter_batches](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html)
y [RecordBatchFileReader.get_batch](https://arrow.apache.org/docs/python/generated/pyarrow.ipc.RecordBatchFileReader.html).
Los límites anteriores se comprueban contra el lock del proyecto.

## Estados y evidencia

`equivalent` exige terminar todas las comprobaciones de este alcance sin
diferencias/incumplimientos; `different` exige recorrido completo con evidencia.
Un fallo técnico, cancelación, dependencia ausente, capacidad o presupuesto
insuficiente produce `not_evaluable`, con motivo, `complete=False`, conteos
parciales `counts.final=False` y diferencias ya observadas. En modo
`reference="expected"`, una referencia derecha que incumple el contrato produce
`not_evaluable / invalid_expected`, aunque el recorrido haya terminado
(`complete=True`). Un candidato inválido frente a esperado válido produce
`different`. En modo `peer`, incumplimientos de cualquiera producen `different`.

Cada carpeta exclusiva `comparison-<uuid>` contiene `comparison.json`,
`differences.jsonl` y snapshots. El manifiesto incluye contrato y huellas,
esquemas observados, ejecuciones/referencias, opciones, políticas efectivamente
aplicadas, estrategia/clave, versiones, tiempo, trabajo, disco, diagnósticos y
completitud. `difference_records` cuenta registros, no necesariamente filas:
una fila puede tener varios incumplimientos/celdas diferentes. `matched_rows`
cuenta parejas coincidentes bajo la estrategia; no anula incumplimientos.

Cada diferencia localiza clave o posición, columna cuando procede, valores
originales etiquetados y multiplicidades. Decimal e integer son texto exacto;
temporales son épocas enteras con unidad/zona; NaN/NULL/infinitos son etiquetas.
El resumen limita ejemplos, nunca el recorrido. Los multiconjuntos exactos usan
representantes con conteos completos; los snapshots permiten recuperar cada
representación original. `iter_differences` comprueba SHA-256/tamaño y devuelve
todos los registros. `read_comparison` revalida el manifiesto; la lectura de sus
artefactos es explícita. Fallos de creación/publicación de evidencia se elevan al
llamante, porque no puede entregarse un resultado persistido fiable.
