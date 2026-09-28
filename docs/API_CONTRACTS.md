# API Python y contratos de intercambio

Versión implementada: `equiframe 0.2.0`, formatos `1.0`, pasos 1 y 2. El [README del
paquete](../packages/equiframe/README.md) contiene instalación, comandos y un
ejemplo Python ejecutable. Los componentes siguientes siguen en la hoja de ruta.

## 1. API disponible

| Servicio | Comportamiento comprobable |
|---|---|
| `validate_contract(document) -> Contract` | Texto JSON, bytes UTF-8 o mapping compatible con JSON; validación estricta y cruzada |
| `read_contract(path) -> Contract` | Lee un archivo y usa el mismo validador |
| `write_contract(contract, path) -> None` | Revalida y escribe exactamente los bytes canónicos |
| `canonical_contract_bytes(contract) -> bytes` | Representación de metadatos canónica v1 |
| `contract_fingerprint(contract) -> str` | SHA-256 hexadecimal de esos bytes; no equivalencia tabular |
| `contract_json_schema() -> dict[str, object]` | JSON Schema generado desde `Contract` |

La API explícita está en `equiframe.__all__`; `__version__` es `0.2.0`.
Los constructores usan Pydantic estricto/inmutable, rechazan extras y conservan
colecciones como tuplas. La validación de JSON permite arrays sin introducir
coerciones numéricas con pérdida. No se interpreta código en documentos.

## 2. Modelos materializados

| Tipo | Campos y restricciones de este paso |
|---|---|
| `LogicalType` | Unión discriminada: `BooleanType`, `IntegerType(bits, signed)`, `StringType`, `DecimalType(precision, scale)`, `FloatType(bits)`, `DateType`, `TimestampType(unit, timezone)` |
| `ColumnSpec` | `name`, `logical_type`, `nullable`, `null_policy`, `nan_policy`, `numeric_policy`, `temporal_policy`, `allowed_values` |
| `NullPolicy` | Representaciones explícitas `null`, `empty_string`, `zero`; equivalencias requieren justificación y columna nullable |
| `NaNPolicy` | `forbid`, `distinct`, `as_null`; solo floats, equivalencia justificada |
| `NumericPolicy` | Comparación exacta/aproximada, unidad, redondeo decimal justificado y tolerancia opcional |
| `Tolerance` | Límites decimal-textuales absoluto/relativo no negativos, unidad y justificación obligatorias |
| `TemporalPolicy` | Unión de `DatePolicy` y `TimestampPolicy`; granularidad, zona/política sin offset, DST e intervalos explícitos |
| `KeySpec` | Nombre, columnas, `unique`, política `incomplete`, ámbito `KeyScope` global/tabla/columnas |
| `TableSchema` | Columnas, claves, `multiplicity` y `order`; referencias locales verificadas |
| `TableSpec` | `name`, `schema_spec`; nombres de entrada/salida distintos |
| `OrderPolicy` | `IgnoredOrder` o `SignificantOrder(by, ties)`; `SortSpec(column, direction, nulls)` |
| `Contract` | Versión obligatoria, ID, revisión positiva, familia, `inputs`, `output`, `preconditions`, `rules` |
| `PreconditionSpec` | ID y `requirement` declarativo, con referencias verificadas |
| `RuleSpec` | ID/revisión, `specification`, severidad, obligatoriedad, referencias `applicability` a precondiciones |
| `RuleDefinition` | Formas cerradas `SchemaCheck`, `KeyCheck`, `CardinalityCheck`, `JoinCheck`, `OrderCheck`, `AggregateCheck` |
| `ScalarValue` | Literales etiquetados de ausencia, NaN, infinito, booleano, entero, cadena, decimal, float, día y timestamp |
| `SchemaRef` | ID, revisión y SHA-256 de un esquema declarado |
| `ArtifactRef` | Versión, URI sin credenciales/query/fragmento, SHA-256, formato, `media_type`, `size_bytes`, esquema opcional |

La validación comprueba nombres únicos, claves/ámbitos/columnas existentes,
referencias a tablas/precondiciones, parejas y tipos de joins, medidas/grupos
agregados, precisión/escala, políticas compatibles, unidades, zonas IANA e
intervalos coherentes. No procesa tablas, comprueba unicidad real, aplica
redondeo ni ejecuta las reglas declaradas. Nuevas formas incompatibles exigen
versión de esquema y migración expresa; no hay migración automática.

Joins y agrupaciones numéricos requieren unidades iguales. `sum`/`min`/`max`
conservan la unidad; `sum` admite tipos más amplios de la misma familia sin
reducir rango entero, capacidad entera/escala decimal ni bits de float.
`min`/`max` conservan el tipo lógico. No se declaran conversiones implícitas.
`OrderCheck.columns` coincide con todas las columnas de la política
`SignificantOrder.by`, en el mismo orden. La política define dirección,
posición de ausencias y empates. Un literal float32 exacto no puede requerir
redondeo ni subdesbordamiento. Son restricciones de metadatos, no pruebas de datos.

`allowed_values` es una restricción declarativa tipada. Los contratos en
`examples/` son fixtures sintéticos para las cinco familias; no escenarios
científicos revisados ni datos del benchmark. Sus decisiones no fijan valores SERCOP.

## 3. Serialización y versiones

`schema_version`, `revision` y versión del paquete tienen funciones separadas:
formato, significado del contrato y API. Se admite únicamente esquema `1.0`.
JSON de miembros duplicados, tokens NaN/Infinity y UTF-8 inválido se rechaza.

`equiframe-metadata-json-v1` incluye defaults/nulls, ordena miembros de objetos
por puntos de código Unicode, preserva arrays, usa UTF-8 sin BOM/normalización,
sin espacios ni salto final. No es JCS/RFC 8785. El hash incluye ID y revisión.
Decimal usa texto `str(Decimal)` con capitalización `E` fijada en contexto local,
conservando signo, dígitos y exponente/escala,
sin float intermedio. Instantes conservan texto ISO hasta ns, offset y zona;
los días siguen siendo días. No se admiten leap seconds ni offset `-00:00`.
Especiales se representan como objetos etiquetados, nunca tokens no estándar.
El contexto decimal del consumidor no cambia la huella. Las zonas IANA se
resuelven exclusivamente con `tzdata` bloqueado, independientemente de la base
del sistema o `PYTHONTZPATH`. Actualizar esa dependencia requiere revalidación.
La especificación completa y las limitaciones están en el README del paquete.

JSON Schema estructural se genera en `schemas/`; referencias cruzadas,
coherencia entre campos y zonas/DST requieren `validate_contract`.
La huella de metadatos no verifica artefactos reales ni tablas equivalentes.

## 4. Estados públicos separados

Los estados son alias `Literal` públicos, sin funciones de decisión en este paso:

- `ExecutionState`: `completed`, `invalid_input`, `failed`, `timeout`, `resource_exhausted`, `cancelled`.
- `DecisionState`: `alert`, `no_alert`, `not_evaluable`.
- `ComparisonState`: `equivalent`, `different`, `not_evaluable`.
- `OracleState`: `correct`, `divergent`, `pending`, `not_evaluable`.
- `FitState`: `ready`, `not_estimable`, `incompatible`.
- `JobState`: `queued`, `running`, `succeeded`, `failed`, `cancelled`.

Un fallo o componente no estimable nunca se define como ausencia de alerta.
La composición H = R OR M y la agregación de reglas son requisitos de pasos
posteriores. La tabla prevista se conserva para implementación:

| R | M | H | Evaluación completa |
|---|---|---|---|
| alert | alert | alert | sí |
| alert | no_alert | alert | sí |
| alert | not_evaluable | alert | no |
| no_alert | alert | alert | sí |
| no_alert | no_alert | no_alert | sí |
| no_alert | not_evaluable | not_evaluable | no |
| not_evaluable | alert | alert | no |
| not_evaluable | no_alert | not_evaluable | no |
| not_evaluable | not_evaluable | not_evaluable | no |

Un conjunto vacío de reglas no acredita evaluación. Mutante sin efecto es
metadato; la etiqueta depende de O, nunca del origen de la variante.

## 5. Integración actual y futura

`ArtifactStore` conserva su firma materializada como `typing.Protocol`:
`put(path: Path, *, media_type: str) -> ArtifactRef` y
`get(ref: ArtifactRef, destination: Path) -> Path`. El paso 2 aporta `LocalArtifactStore`: copias exclusivas, hash/tamaño comprobados y URI locales. No hay descargas.

`DataSource` y `EngineAdapter` tienen tipos completos e implementaciones desde el paso 2. `Rule`, `Profiler` y `Detector` quedan para sus pasos. `SnapshotManifest`, observaciones semánticas, perfiles, bundles, reportes completos,
oráculo y freeze siguen siendo diseño en [arquitectura](ARCHITECTURE.md) y
[hoja de ruta](HERNAN_ROADMAP.md). No están expuestos como APIs vacías.
Observaciones/perfiles futuros no contienen etiqueta O, mutación ni salidas de
otro motor. La integración compartida se acuerda por PR con José/Jhair.

## 6. CLI funcional y errores

`equiframe contract validate <archivo>` usa `read_contract` de la API pública.

| Salida | Semántica de este comando |
|---|---|
| 0 | Contrato válido; ID/revisión y huella de metadatos en stdout |
| 2 | Argumentos, JSON, contrato o versión inválidos |
| 3 | Fallo de lectura del archivo |

El comando no usa 1: no evalúa alerta/diferencia. Errores a stderr con rutas
JSON, código y mensaje, sin volcar documentos completos.
`ContractValidationError.issues` es una tupla de `ValidationIssue` inmutables:
`code`, `location`, `message`, propiedad `path`.
`SchemaVersionError` y `ContractParseError` son subclases específicas;
`ContractIOError` cubre lectura/escritura. Todas derivan de `EquiFrameError`.
Construcción directa de modelos usa `pydantic.ValidationError`; las funciones
públicas traducen errores de validación a la jerarquía EquiFrame.
Las rutas de miembros JSON duplicados incluyen objetos/arrays anidados y
escapan claves no imprimibles. Errores temporales mantienen causa específica
en `allowed_values`. Los textos de errores directos omiten las entradas;
la API de Pydantic `.errors()` y las causas pueden conservarlas.

Otros comandos (`run`, `compare`, `report`, entrenamiento/evaluación) y errores
de ejecución/recursos/modelos se definen en sus pasos. No hay subcomandos vacíos.
Los códigos operacionales futuros mantienen distinción entre alerta/diferencia
(1), entrada inválida (2) y fallo/no evaluable (3), con evidencia independiente.


## 7. API de ejecución disponible (producto 0.2)

Reutilización general, instalación pip local y alias `ef` son requisitos de producto
nuevos; conservan el objetivo científico pero no se atribuyen al texto del borrador.
Publicación PyPI pendiente del paso 10. Ejemplo íntegro y ejecutable, instalación y
matriz de tipos: [README](../packages/equiframe/README.md).

| Tipo/servicio | Contrato implementado |
|---|---|
| `execute(plan, *, source, registry, adapter, artifact_store, work_dir, cancellation)` | Defaults opcionales; ejecuta una implementación registrada y devuelve `ExecutionResult` |
| `ExecutionPlan` | Contrato, motor, ID/revisión de transformación, parámetros `ScalarValue`, opciones estrictas |
| `ExecutionOptions` | Tiempo cooperativo, presupuestos de filas/buffers, memoria/hilos/zona DuckDB |
| `RunContext` | IDs/carpeta/plan/store, parámetros, token/deadline, checkpoints y mediciones por etapa |
| `EngineCapabilities` | Precisión decimal, unidades temporales/zoned, lazy, cancelación, controles y dependencias |
| `ExecutionResult` | Formato 1.0; plan/huella, IDs, código, versiones/configuración, estados/diagnóstico, tiempos, entradas/salida |
| `TableArtifact` / `PhysicalColumn` | Referencia de datos/origen/índice, filas, esquema físico motor/Arrow, NULL/NaN y notas; sin cast al contrato |
| `TransformationRegistry` | Instancia explícita; `register(Transformation)` y `resolve(plan)`; no reemplaza la misma clave |
| `PandasTransformation` / `PolarsTransformation` | ID, revisión, code_version y callback nativo tipado `(tables, context)` |
| `DuckDBTransformation` | ID, revisión, code_version y SELECT/WITH SQL confiable; `$nombre` de valores del plan |
| `DataSource` | `table_names` y `resolve(name, *, context) -> LoadedTable` |
| `EngineAdapter` | `engine`, `capabilities()` y `execute(transformation, inputs, context) -> LoadedTable` |
| `LocalDataSource` | Entradas nombradas `ArrowInput`/`PandasInput`/`PolarsInput`/`ArtifactRef`; local sin conexión implícita |
| `LocalArtifactStore` | Mismo `ArtifactStore.put/get`; solo formatos declarados/locales y copias con hash/tamaño |
| `read_table(ref)` | Lee Arrow IPC file/Parquet local tras verificar integridad; sin modificación ni descarga |

Errores completos: `InvalidExecutionInput`, `CapabilityError`,
`MissingDependencyError`, `ArtifactIntegrityError`, `ArtifactIOError`,
`ExecutionCancelled`, `ExecutionTimeout`, `ResourceLimitError`; todos reutilizan
`EquiFrameError`. Operaciones fallidas dentro de una corrida se traducen a estados
existentes, con código/etapa/tipo; plan inválido y fallos de carpeta/publicación se
elevan. Los esquemas JSON de plan/resultado son generados, independientes del
formato de contrato conservado del paso 1. El resultado se revalida al construir;
completed requiere artefacto de salida y ningún problema.

No ejecuta reglas/precondiciones ni corrige discrepancias de datos con el contrato.
Salida completed puede ser diferente o anómala; no existe comparación o etiqueta O
en estos modelos. IDs únicos impiden mezclar corridas locales independientes.
Arrow no recupera offset textual por fila, signo decimal cero o None perdido al
construir una tabla; notas/capacidades exponen esas limitaciones. Ningún límite
cooperativo se describe como timeout duro o sandbox.
