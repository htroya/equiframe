# API Python y contratos de intercambio

Versiones candidatas actuales: `equiframe 0.12.0a4` y `equiframe-benchmark 0.12.0a4`, formatos independientes `1.0`, Verify operacional, migrador y ETL local. El [README del
paquete](../packages/equiframe/README.md) contiene instalación, comandos y un
ejemplo Python ejecutable. Las secciones por versión conservan la evolución de la API. La aceptación del servicio real, la evaluación científica y la comprobación final de las distribuciones actuales conservan sus controles propios.

El alcance científico principal comprende `nulls_types`, `joins` y `aggregations`
en las parejas Pandas–Polars, Pandas–DuckDB y Polars–DuckDB: nueve estratos. El
software conserva además `duplicates_order` y `dates` como capacidades genéricas.
EquiFrame Verify es el nombre comercial de la validación independiente de
equivalencia; la notación O y los nombres existentes `oracle`, `OracleResult`,
`OracleState` y `evaluate_oracle` conservan compatibilidad.

## 1. API disponible

| Servicio | Comportamiento comprobable |
|---|---|
| `validate_contract(document) -> Contract` | Texto JSON, bytes UTF-8 o mapping compatible con JSON; validación estricta y cruzada |
| `read_contract(path) -> Contract` | Lee un archivo y usa el mismo validador |
| `write_contract(contract, path) -> None` | Revalida y escribe exactamente los bytes canónicos |
| `canonical_contract_bytes(contract) -> bytes` | Representación de metadatos canónica v1 |
| `contract_fingerprint(contract) -> str` | SHA-256 hexadecimal de esos bytes; no equivalencia tabular |
| `contract_json_schema() -> dict[str, object]` | JSON Schema generado desde `Contract` |

La API explícita está en `equiframe.__all__`; `__version__` es `0.12.0a4`.
Desde STEP6 cada export, comando y esquema tiene clasificación explícita en
[compatibilidad](COMPATIBILITY.md), consultable con `get_stability_register()`.
`get_compatibility_policy()` publica los avisos/plazos; `get_adapter_capabilities()`
separa captura, comparación, ejecución y migración. Estas descripciones no admiten
por sí solas una ejecución ni acreditan una plataforma; los registros de la
[matriz ejecutada](STEP6_CANDIDATE.md) fijan su alcance observado.

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
intervalos coherentes. Esta validación de metadatos no procesa tablas ni comprueba
unicidad real, y tampoco aplica redondeo o ejecuta las reglas declaradas. Nuevas
formas incompatibles exigen versión de esquema y migración expresa de esos
formatos; no hay actualización automática de documentos antiguos.

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

Los estados son alias `Literal` públicos; ejecución y comparación tienen APIs operativas:

- `ExecutionState`: `completed`, `invalid_input`, `failed`, `timeout`, `resource_exhausted`, `cancelled`.
- `DecisionState`: `alert`, `no_alert`, `not_evaluable`.
- `ComparisonState`: `equivalent`, `different`, `not_evaluable`.
- `OracleState`: `correct`, `divergent`, `pending`, `not_evaluable`.
- `FitState`: `ready`, `not_estimable`, `incompatible`.
- `JobState`: `queued`, `running`, `succeeded`, `failed`, `cancelled`.

Un fallo o componente no estimable nunca se define como ausencia de alerta.
La composición H = R OR M está implementada desde el paso 7. R agrega las reglas
según la [tabla del paso 4](RULES.md#estados-cobertura-y-prioridad). La tabla
de H conserva las nueve combinaciones:

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

`DataSource` y `EngineAdapter` tienen tipos completos e implementaciones desde el
paso 2. `RuleRegistry` y `RuleContext` funcionan desde el paso 4. Los perfiles y
bundles de preprocesamiento funcionan desde el paso 5 (sección 11), sin etiquetas,
mutaciones ni otra salida de motor. Los detectores, reportes, validación independiente
de equivalencia, snapshots y freeze tienen APIs implementadas en las secciones
12–16; el migrador del núcleo está en la sección 17. El cliente autenticado, DW y operación del servicio siguen bajo los
responsables y requisitos de [integración](TEAM_INTEGRATION.md).

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

Los comandos `run`, `compare`, `report`, `evidence verify` y `reduce` están
implementados desde el paso 8; entrenamiento/evaluación conservan APIs separadas.
Los códigos operacionales mantienen distinción entre alerta/diferencia
(1), entrada inválida (2) y fallo/no evaluable (3), con evidencia independiente.


## 7. API de ejecución disponible (producto 0.2)

Reutilización general, instalación pip local y alias `ef` son requisitos de producto
nuevos; conservan el objetivo científico pero no se atribuyen al texto del borrador.
Publicación PyPI prevista en el paso 19, después de la evaluación y revisión de
los pasos 10–18. Ejemplo íntegro y ejecutable, instalación y
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
`MissingDependencyError`, `NativeEngineError`, `ArtifactIntegrityError`, `ArtifactIOError`,
`ExecutionCancelled`, `ExecutionTimeout`, `ResourceLimitError`; todos reutilizan
`EquiFrameError`. Operaciones fallidas dentro de una corrida se traducen a estados
existentes, con código/etapa/tipo; plan inválido y fallos de carpeta/publicación se
elevan. Los esquemas JSON de plan/resultado son generados, independientes del
formato de contrato conservado del paso 1. El resultado se revalida al construir;
completed requiere artefacto de salida y ningún problema.

No ejecuta reglas/precondiciones ni corrige discrepancias de datos con el contrato.
Salida completed puede ser diferente o anómala; no incluye comparación ni etiqueta O.
`ef.compare` evalúa esas salidas por separado. IDs únicos impiden mezclar corridas.
Arrow no recupera offset textual por fila, signo decimal cero o None perdido al
construir una tabla; notas/capacidades exponen esas limitaciones. Ningún límite
cooperativo se describe como timeout duro o sandbox.


## 8. Validación y captura en 0.2.1

Las fuentes externas declaran `table_names` como tupla estricta, sin duplicados,
y resuelven `LoadedTable` con tabla Arrow. Los adaptadores inyectados exponen
capacidades revalidadas y devuelven el mismo tipo de intercambio.

El resultado verifica SHA-256 del contrato incorporado, nombres de entradas
únicos/declarados y, para completed, todas las entradas, motor y nombre de salida.
`TableArtifact` requiere datos/índice Arrow o Parquet, nombres físicos únicos,
conteos NULL+NaN compatibles con filas e índice referenciado cuando declara columnas.
La validación no exige que el esquema observado coincida con el esperado.

Si publicar un índice falla después de guardar datos, el resultado fallido retiene
la referencia parcial y una nota explícita; no presenta esa tabla como íntegra.
`max_transport_bytes` comprueba los buffers de datos y del índice por tabla.
Las mediciones anidadas restablecen la etapa del padre al terminar correctamente,
y conservan la etapa interna cuando ocurre un fallo.

Tipos NumPy/nullable Pandas conservan anchos, signo y máscaras; categorías y objetos
numéricos de tipos mezclados se rechazan. Decimal256/escala negativa se rechaza en
Polars/DuckDB. Segundos Polars y s/ms zoned DuckDB se comprueban contra los límites
de la unidad destino. Infinito/sentinels temporales DuckDB no se exportan como
épocas finitas. Un pánico FFI Polars produce `NativeEngineError`/estado failed.
Los límites completos permanecen en la matriz de transporte del paquete.

Estos controles no añaden campos ni cambian la versión de formato 1.0.
Integración remota prevista: [OCI](OCI_INTEGRATION.md).

## 9. Comparación disponible en 0.3.0

| API/modelo | Comportamiento |
|---|---|
| `compare(left, right, *, contract, policy, options, reference, work_dir, cancellation)` | Evalúa contenido completo ya capturado, sin motores; `reference="expected"` identifica esperado independiente a la derecha |
| `ComparisonInput` | ArrowInput, ArtifactRef, Path local, TableArtifact o ExecutionResult |
| `ComparisonSpec` / `ComparisonPolicy` | Documento propio 1.0 con contrato intacto y permisos explícitos de columnas/tipos/índices |
| `ComparisonOptions` | Lotes, particiones, disco, trabajo, matching, tiempo y evidencia |
| `ComparisonResult` / `ComparisonCounts` | Estado, completitud, alcance output_schema, referencias, huellas, estrategia, conteos y versiones |
| `ComparisonSource` / `AppliedPolicy` | Esquema observado separado, referencia verificada y operaciones aplicadas |
| `ComparisonDifference` / `ComparisonValue` | Clave/posición/columna, valores originales tipados y multiplicidades sin pérdida |
| `ComparisonDiagnostic` | Fallo técnico/capacidad/recursos/cancelación o esperado inválido |
| `comparison_fingerprint(spec)` | Identidad de la especificación completa; no prueba igualdad de datos |
| `read_comparison(path)` / `iter_differences(ref)` | Revalidar manifiesto / verificar integridad y leer toda la evidencia |

Semántica, estados, límites, permisos y ejemplos: [Comparación](COMPARISON.md).
Modelos antiguos 1.0 conservan campos/bytes y validación; cuatro esquemas nuevos
se generan por separado. `equivalent` no evalúa reglas/precondiciones operativas,
ni produce una etiqueta O. El registro independiente de reglas está en
[R](RULES.md).

## 10. Reglas R disponibles en 0.4.0

`evaluate_rules(execution, *, registry, options, work_dir, cancellation)`
evalúa una sola captura `ExecutionResult` sin reejecutar el ETL. Exporta
`RuleRegistry`, `RuleContext`, `RuleOptions`, `CheckResult`, `RuleFinding`,
`RuleCoverage`, `RuleEvaluation`, `rule_set_fingerprint`,
`read_rule_evaluation` e `iter_rule_findings`. Los documentos suplementarios
`rule-options`, `rule-finding`, `rule-check-result` y `rule-evaluation` usan
esquema 1.0 independiente; el contrato 1.0 no cambia. Véanse semántica,
agregación, presupuestos y catálogo en [Reglas R](RULES.md).

## 11. Perfiles y preprocesamiento disponibles en 0.5.0

| API/modelo | Comportamiento |
|---|---|
| `ProfileSpec`, `ProfileFeature` | Familia, versión, orden fijo y diez fórmulas cerradas |
| `profile_execution(execution, *, spec, options, work_dir, cancellation, conversions)` | Perfil de una sola captura; persiste `profile.json` |
| `FeatureObservation`, `FeatureSupport` | Valor, estado, numerador/denominador y conteos separados |
| `ProfileResult`, `ProfileMetadata`, `ProfileVector` | Metadatos y estadísticas separados; sin etiquetas ni mutaciones |
| `ConversionReceipt` | Intentos/fallos instrumentados, hashes y columna fuente; ausencia no se infiere desde output NULL |
| `NormalTrainingProfiles` | Frontera de selección normal de entrenamiento con manifiesto externo |
| `fit_preprocessor(training, *, spec, empty_policy)` | Medianas y retiro de variables ajustados una sola vez |
| `PreprocessorBundle`, `FeatureFit` | Orden, medianas, soporte, huellas y estados ready/not_estimable |
| `transform_profiles(bundle, profiles) -> FeatureMatrix` | Matriz finita común para M/B; errores no se imputan |
| `profile_spec_fingerprint`, `read_profile`, `read_preprocessor`, `write_preprocessor` | Identidad y persistencia JSON estricta, sin sobrescritura |

Los formatos nuevos conservan Contract/ExecutionResult/Comparison/Rules 1.0.
`ProfileOptions` fija presupuestos cooperativos. Detalles y limitaciones:
[Perfiles](PROFILES.md). Detectores disponibles desde 0.7.0; la CLI integrada está disponible desde 0.8.0;
los scripts de ejemplo ya son ejecutables.

## 12. Benchmark disponible en 0.6.0

Distribución/import separados: `equiframe-benchmark` / `equiframe_benchmark`.
No modifica los formatos ni la API operacional de `equiframe 0.5.0`.

| API/modelo | Comportamiento |
|---|---|
| `InputBinding`, `Scenario`, `Catalog`, `Candidate` | Entradas, esperado, contrato/política, autores, dependencias, versiones y huellas |
| `review_packet(scenario, candidate, *, directory)` | Copia verificada a carpeta con token aleatorio y nombres neutros; persiste paquete |
| `ReviewAssignment`, `Review` | Dos revisores/árbitro distintos, fechas UTC, razón, hash y declaración de ceguera |
| `evaluate_oracle(..., packet, assignment, reviews, resolution, work_dir)` | Comparación independiente y control de revisión; conserva `ComparisonResult` completo |
| `OracleResult` | Pending/disagreement/confirmed/not_evaluable; solo confirmed lleva etiqueta normal/divergent |
| `dependency_groups(catalog)` | Componentes transitivos de dependencias declaradas y artefactos compartidos |
| `make_splits(catalog, *, seed, weights)`, `validate_splits`, `split_counts` | Particiones deterministas por grupos completos; cobertura y cantidades por familia |
| `select_normal_training(..., candidates, oracles, profiles, executions)` | Mapas por candidato; verifica normalidad revisada, entrenamiento y procedencia exacta |
| `TrainingSelection`, `TrainingManifest`, `TrainingRecord` | Manifiesto completo enlazado por hash; `.training` cruza al preprocesador del núcleo |
| `save_document`, `load_document`, `digest` | JSON canónico estricto, sin sobrescritura y con revalidación al leer/escribir |

Diez esquemas JSON públicos 1.0 se generan y comprueban en CI. `ReviewPacket`
no incluye metadatos del candidato; `OracleResult` permanece con el coordinador
y sí conserva decisión, comparación y revisiones. Las URI son locales: mover
artefactos exige publicar referencias/paquetes nuevos, con nuevas huellas;
no se promete portabilidad de rutas absolutas ni firmas autenticadas.
Uso y límites: [paquete](../packages/equiframe-benchmark/README.md) y
[diseño](STEP_06_DESIGN.md).

## 13. Detectores y calibración disponibles en 0.7.0

| API/modelo | Comportamiento |
|---|---|
| `IsolationForestConfig`, `DetectorSupport` | Semilla, árboles/submuestra, mínimos técnicos y justificación |
| `fit_detectors(training, *, spec, config, support, empty_policy)` | Ajusta medianas, IF y MAD con una matriz común; retorna `DetectorFit` |
| `score_detectors(fit, profiles)` | Scores de ambos métodos, número de filas y hashes; no reajusta ni decide |
| `NormalCalibrationProfiles` | Selección normal distinta de entrenamiento; perfiles sin etiquetas |
| `calibrate_detectors(fit, calibration, *, alpha)` | Bundle con alpha decimal explícito, n, rango y cuantil sin interpolar |
| `detect(bundle, profiles)` | Scores, umbrales, decisiones y motivos; errores de contrato se elevan |
| `detect_component(bundle, profiles, *, method) -> ComponentDetectionResult` | Desde 0.9.0: puntúa y decide únicamente `"isolation_forest"` o `"mad"`; hashes de bundle, fit, perfiles y matriz, scores y decisiones |
| `ComponentDecision`, `combine_decisions(r, m)`, `HybridDecision` | OR de tres estados, R completo/parcial y M; no incorpora B |
| `detector_fingerprint`, `write_detector_bundle`, `read_detector_bundle` | JSON declarativo 1.0, validación/huellas, escritura exclusiva, límite 64 MiB |
| `select_normal_calibration` (benchmark) | O normal confirmado y procedencia completa en partición calibration |
| `audit_detector_selections` (benchmark) | Igual catálogo/split/features, grupos disjuntos y mínimos explícitos |

Se añaden seis esquemas del núcleo y tres del benchmark. Contratos, ejecuciones,
R y perfiles previos conservan su formato. Los estados no estimables no se
convierten en no alerta. Detalles y límites: [detectores](DETECTORS.md).
`detect_component` conserva el preprocesamiento, calibración y decisiones de
`detect`, sin ajustar ni calcular el otro detector. Su propiedad `complete` exige
decisiones completas; soporte ausente produce motivos no evaluables.

## 14. Orquestación y evidencia en 0.8.0

| API/modelo | Comportamiento |
|---|---|
| `PipelineSpec`, `PipelineRequest`, `PipelineInput` | Configuración estricta y bindings verificables; sin código en JSON |
| `run_pipeline(spec, *, source, registry, ...)` | Captura única, R/perfil/M/B/H y comparación opcional |
| `PipelineResult`, `StageRecord` | Procedencia cruzada, estados, completitud de lo solicitado y `exit_code` |
| `EvidenceEvent`, `EvidenceFile` | Secuencias/hash previo y archivos relativos con SHA-256/tamaño |
| `read_pipeline`, `verify_events`, `inspect_evidence` | Verificación local e identificación de interrupciones |
| `pipeline_summary`, `render_report`, `write_report` | Resumen seleccionado y reportes JSON/HTML exclusivos con escape |
| `ReductionOptions`, `ReductionObservation`, `ReducedTable`, `ReductionResult` | Presupuestos, precondiciones/firma, posiciones y estados de reducción |
| `reduce_case`, `read_reduction` | Reducción por filas entre tablas y lectura de evidencia verificada |

Siete esquemas nuevos 1.0 en el paso 8. `DetectorVersions` acepta actualmente 0.7.0/0.8.0/0.8.1/0.9.0/0.10.0/0.11.0/0.11.1 sin cambiar el
algoritmo IF/MAD. El núcleo no importa benchmark ni acepta O como entrada del
runner. [Uso y códigos CLI](ORCHESTRATION.md), [diseño y límites](STEP_08_DESIGN.md).

## 15. Consumidor e integración experimental en 0.9.0

La implementación original del paso 9 requiere núcleo 0.8.1; la distribución
actual `equiframe-benchmark 0.11.0` requiere exactamente núcleo 0.11.0 con el extra
Arrow. Esa dependencia no acredita la instalación final de los nuevos paquetes.

| API/modelo | Comportamiento |
|---|---|
| `SnapshotColumn`, `SnapshotTable`, `SnapshotManifest` | Recibo publicado e inmutable con tipos, revisión, filas y artefactos |
| `SnapshotClient`, `SnapshotDataSource` | Cliente explícito, fijación del recibo y selección de tablas con comprobaciones |
| `snapshot_fingerprint` | Identidad canónica del manifiesto completo |
| `IntegrationSpec`, `IntegrationResult` | Tres planes nativos compatibles, snapshot, decisiones y evidencia |
| `run_integration`, `read_integration` | Ejecución única por motor y verificación local de referencias/manifiestos |
| `AwardReconciliationSpec`, `AwardReconciliationResult`, `reconcile_awards` | Grano, importes exactos, monedas y puente configurables; ausencias explícitas |

Cinco esquemas nuevos 1.0. Los resultados no confirman etiquetas científicas.
El contrato del cliente no implementa transporte, autenticación, DDL ni operación
del servicio. [Diseño](STEP_09_DESIGN.md), [uso CLI](../packages/equiframe-benchmark/README.md).

## 16. Congelación, evaluación y reproducción desde benchmark 0.10.0

Las APIs siguientes se exportan desde `equiframe_benchmark.__all__`. Sus documentos
estrictos usan formato `1.0`; el núcleo conserva sus formatos y no recibe etiquetas O.
El [protocolo y alcance](STEP_10_EVALUATION.md) contiene las fórmulas y controles completos.

| API/modelo | Contrato implementado |
|---|---|
| `FreezeDefinition`, `TestCaseDefinition`, `FrozenFamilyModel`, `FrozenInput`, `SelectionEvidence`, `EnvironmentPin`, `ExperimentalDecision` | Catálogo/splits, casos, modelos y selecciones declaradas, archivos/entorno, decisiones y protocolos fijados antes de test |
| `audit_freeze(definition, *, rule_registry=None, work_dir=None) -> FreezeAudit` | Verifica fuentes físicas, procedencia, soporte y bloqueos; no ejecuta ETL ni ajusta IF |
| `create_freeze(definition, *, rule_registry=None, work_dir=None) -> FreezeManifest` | Emite el sello cuando pasa el gate correspondiente; su persistencia usa `save_document` |
| `read_freeze(path, *, expected_sha256=None, rule_registry=None, work_dir=None, max_bytes=64*1024**2)` | Reaudita fuentes y sello, con SHA de archivo opcional y límite de lectura |
| `run_study(manifest, *, registry, rule_registry=None, work_dir=None, cancellation=None) -> StudyResult` | Consume un sello existente y ejecuta cada caso nativo una vez, con su bundle congelado y sin fit |
| `StudyCaseResult`, `StudyResult`, `read_study(directory, *, rule_registry=None, max_bytes=64*1024**2)` | Conservan casos fallidos, auditorías antes/después, pipelines, evaluación, tablas e inventario; lectura sin ETL, con recomparación física cuando un replay autoriza O confirmado |
| `BootstrapPlan`, `EvaluationConfig`, `EvaluationRecord`, `EvaluationReport` | Configuración, decisiones originales, cobertura y métricas con motivos explícitos para valores indefinidos |
| `evaluate_records(records, config)`, `evaluation_protocol_sha256(config)` | Cálculo puro desde una tupla de registros; soporte principal común R/M/B/H y protocolo identificable sin circularidad |
| `table_payloads(report)`, `write_tables(report, directory) -> TableExport`, `read_tables(directory, *, report)` | Seis CSV deterministas y recibo; lectura contrasta cada byte con su regeneración |
| `CostProtocol`, `CostSpec`, `ProfileMCostResult`, `ResourceSample`, `ResourceMeasurement`, `CostComparisonResult` | Capturas fijadas, protocolo, resultados originales y mediciones completas/parciales/ausentes |
| `measure_costs(spec, *, profile_m, comparison, work_dir=None, cancellation=None, probe_factory=None)` | Dos callbacks síncronos confiables `(Path, CancellationToken)`; un par de warmup y cinco pares alternados, primer orden fijado por semilla |
| `read_costs(path)`, `write_cost_table(directory, *, output)` | Verifican evidencia/capturas y exportan las doce observaciones crudas, incluidos fallos y warmup |
| `make_reproduction_record(*, configuration, splits, labels, decisions, tables)`, `compare_reproductions(recorded, repeated)` | Contenido JSON canónico completo; `ReproductionRecord` y `ComparisonReceipt` con estado `reproduced` o `different` |
| `create_bundle(files, *, directory, bundle_id, record_path=None, artifacts=None, expected_files=None, limits=None)` | Copias verificadas e inventario cerrado; `ReproductionBundle` publicado al final bajo `BundleLimits` |
| `read_bundle(directory, *, expected_sha256=None, limits=None)`, `bundle_artifact(bundle, directory, original, *, limits=None)` | Verifican archivos y permiten resolver una URI portátil conservando identidad, hash, tamaño y formato originales |
| `reproduce_bundle(directory, *, regenerator, expected_sha256=None, limits=None)` | Regenerador confiable explícito de registros capturados; ningún callback se importa desde JSON |
| `bundle_study(directory, *, output)`, `regenerate_study_record(record)`, `reproduce_study_bundle(directory, *, expected_sha256=None)` | Bundle portátil del estudio, verificación de capturas y regeneración de métricas/seis CSV, sin reejecutar ETL |
| `inspect_distribution(package_directory, wheel_path=None, *, name_check=None) -> DistributionReadiness`, `NameCheck` | Inventario local de fuente/lock/wheel y observación externa del nombre; no construye, instala, consulta PyPI ni publica |

`FreezeAudit.technical_ready` y `.scientific_ready` son garantías distintas:
`pilot` conserva bloqueos científicos; `final` exige resolverlos. `StudyResult`
separa `.complete`, `.scientific` y `.exit_code`; un caso sin ejecución válida conserva
cuatro componentes no evaluables, y una etapa posterior fallida conserva R disponible.
O confirmado requiere mismos inputs/implementación y salida fresca equivalente a la
revisada. `evaluate_records` calcula sobre registros entregados; la comprobación de
fuentes y del freeze corresponde a las APIs de estudio, no al cálculo puro.

`run_integration` captura una vez cada motor y compara las tres parejas; un
`run_study` consume casos de un estudio congelado. Articular tres estudios por
pareja exige preservar catálogo, grupos, splits e identidad de capturas, sin
convertir las comparaciones reutilizadas en nuevas muestras independientes. La
API no proporciona un consolidador científico automático ni una escala común de
scores entre modelos diferentes. Pandas no actúa como O: el esperado y su revisión
independiente pertenecen a EquiFrame Verify.

El freeze genérico exige cinco slots de modelos, incluidos los no soportados con
motivo explícito. El protocolo final declara las cinco familias; las dos fuera
del alcance principal pueden quedar sin casos/bundle y deben distinguirse de los
nueve estratos de la tesis. El corpus real, las revisiones humanas, el
entrenamiento/calibración con soporte real y la reproducción externa siguen
pendientes. El criterio `N_fit > 10_000` corresponde a registros reales de la matriz
efectiva de aprendizaje; no se satisface con adjudicaciones fuente, sumas entre
modelos, capturas reutilizadas o registros de calibration/test. Se informa N por modelo/familia, soporte y grupos,
sin atribuir al PDF del anteproyecto un mínimo literal por familia. Un sello piloto
no resuelve esas condiciones científicas.

Los costes incluyen perfilado/inferencia M y comparación operacional sobre salidas
ya materializadas, con su I/O y evidencia internos; excluyen lectura DW/ETL/captura
inicial. RSS muestreado es máximo absoluto observado y límite inferior del pico,
no incremento atribuible a la operación. Fallos conservan resultados y ausencias,
sin ceros ficticios; el extra `resources` aporta psutil y los controles declarados
no son cuotas duras. Las repeticiones no aumentan la muestra de detección.

La CLI `run-study` usa 0 para evaluación técnica completa sin alerta/diferencia,
1 para alerta/diferencia completa y 3 para parcial/no evaluable; `costs` usa 0/3
según completitud. Entradas inválidas o freeze bloqueado usan 2. Los verificadores
usan 0 al validar la evidencia, aunque el resultado almacenado sea parcial, y 3
si falla la verificación. Reproducción distinta usa 1. Véase el
[README del benchmark](../packages/equiframe-benchmark/README.md) para comandos.

La reproducción compara configuración, splits, etiquetas, decisiones y tablas
declaradas; preserva costes crudos sin exigir tiempos/CPU/RSS idénticos. No acredita
una repetición humana independiente ni autentica revisores. `DistributionReadiness`
mantiene `build_install_verified=False` y `publication_ready=False`: el inventario
no acredita instalación, control del nombre, licencia resuelta o publicación PyPI.

## 17. Migrador declarativo en núcleo 0.10.0

El migrador compila el mismo IR cerrado a transformaciones nativas y ejecuta dos
motores contra una captura común. Su ámbito es un plan tabular declarativo;
no traduce Python arbitrario ni acepta SQL libre o imports de plugins desde JSON.
El [diseño](MIGRATION_DESIGN.md) registra sus decisiones de arquitectura.

| API/modelo | Contrato implementado |
|---|---|
| `RelationalPlan`, `Scan`, `Project`, `Filter`, `Cast`, `EquiJoin`, `Aggregate`, `Sort` | IR 1.0, DAG topológico acotado, referencias y tipos cerrados |
| `Column`, `LiteralExpression`, `Compare`, `Boolean`, `Not`, `IsNull`, `IsNaN`, `NamedExpression`, `Measure` | Expresiones/predicados tipados; valores etiquetados mediante `ScalarValue` |
| `validate_ir(plan, contract) -> ValidatedIR`, `ir_fingerprint(plan)` | Validación semántica de metadatos y SHA-256 canónico; sin leer datos |
| `PlanCompiler`, `CompilationCheck`, `CompiledPlan`, `CompilerRegistry`, `native_compiler_registry()` | Compiladores registrados explícitamente; transformación nativa e identidad determinista de IR/contrato/motor |
| `MigrationSpec` | IR, contrato, motores distintos, `require_rules`, políticas y opciones de ejecución/comparación/R/perfil/migración |
| `MigrationOptions` | Timeout cooperativo y máximos de captura: por defecto 10 000 000 filas y 512 MiB de buffers |
| `MigrationRequest` | Spec, entradas locales Arrow/Parquet declaradas exactamente y esperado opcional |
| `check_migration(spec, *, compilers=None)` | Dos comprobaciones de compilación sin ETL, resolución de entradas ni imports de motores |
| `migrate(spec, *, source, work_dir=None, expected=None, compilers=None, adapters=None, rule_registry=None, detector_bundle=None, cancellation=None)` | Captura aislada, dos pipelines nativos, comparación entre pares y verificación opcional contra esperado fijado aparte |
| `MigrationResult`, `MigrationStage`, `migration_summary(result)` | Siete etapas, hijos/evidencia, `state`, `verification`, `complete`, `exit_code` y alcance `rules_required` |
| `read_migration(path, *, verify=True)` | Lectura local con integridad física y enlaces de evidencia; no ejecuta ETL |

Los compiladores Pandas, Polars y DuckDB cargan sus bibliotecas de motor sólo al
usarlas. El registro admite extensiones confiables mediante `PlanCompiler` y
`EngineAdapter`; registrar un compilador no declara soportadas sus capacidades.
Las identidades compiladas vinculan IR, contrato y semántica versionada del
compilador. No hay fallback a un resultado calculado por otro motor.

El IR admite joins inner/left con igualdad de claves NULL explícita, grupos NULL
retenidos/descartados, sumas vacías NULL/cero y orden/empates declarados. Cast
preserva identidad o amplía enteros/precisión decimal sin cambiar escala. SUM usa
enteros o Decimal exactos; min/max conservan tipo y las unidades se cotejan.
El rango común decimal es precisión hasta 38; timestamps, claves de
join/agrupación/orden float y SUM/min/max float no están soportados en este IR.
`count_valid` sí admite columnas float. Fechas y
otras representaciones físicas se comprueban para ambos motores antes de ejecutar
cualquiera. Polars usa una cota conservadora de SUM que puede rechazar sumas con
cancelación segura. DuckDB rechaza Aggregate o Sort con rechazo de empates si un
nodo posterior distinto de Sort pudiera podar errores intermedios; no simula
semántica eager. Identificadores incompatibles, tipos fuera del rango o pérdidas
de precisión producen diagnósticos explícitos, sin conversión silenciosa.

Antes de ejecutar, el runner comprueba ambos compiladores, dependencias y
capacidades; luego resuelve cada tabla una sola vez y comprueba tipos/valores y
restricciones físicas para los dos motores. Las entradas no se normalizan ni
modifican. Un índice Pandas significativo se rechaza; descartar RangeIndex exige
política explícita y justificación. El esperado se copia una vez, no alimenta
perfiles/detectores y no participa como entrada del ETL. R, perfiles y M/B/H se
reutilizan sin entrenar; aportar un detector bundle es opcional.

`require_rules=True` es el default y exige la completitud de cada pipeline.
`require_rules=False` debe declararse explícitamente: exige ETL y los perfiles/
detectores solicitados, conserva R/H no evaluables o alertas parciales y no cambia
el `complete` ni `exit_code` de los `PipelineResult` hijos. Un conjunto vacío de
reglas sigue sin acreditar R. El resumen hace visible ese alcance.

El resumen ampliado conserva `independent_verification` como clave histórica y
añade `expected_output_comparison`, así como el estado/completitud/ID/conteo de
cada comparación origen–destino, origen–esperado y destino–esperado.
`equiframe_verify` identifica EquiFrame Verify (O) y conserva `not_established`:
comparar el esperado aportado no acredita su autoría independiente ni las dos
revisiones humanas. No se convierte ese estado en una etiqueta ni se incorpora O
al vector de aprendizaje. Los reportes previos completos siguen siendo legibles.

| Campo/código | Significado |
|---|---|
| `state` | `equivalent`, `different`, `not_evaluable`: comparación entre los dos motores |
| `verification` | `correct`, `divergent`, `not_evaluable`, `not_requested`: comparación con el esperado declarado |
| `complete` | Completitud de las etapas exigidas por el alcance, incluida verificación si se pidió |
| run 0 | Completo sin alerta/diferencia |
| run 1 | Completo con alerta/diferencia |
| run 2 | Entrada/capacidad/dependencia inválida en preflight o captura |
| run 3 | Parcial/no evaluable |

La CLI ofrece `equiframe migration validate SPEC.json`, `migration run
REQUEST.json --output DIR` y `migration verify DIR`; run admite `--bundle` para
inferencia con detectores congelados. Validate comprueba metadatos/compilación;
verify usa 0 si la evidencia local es íntegra, incluso si la corrida almacenada es
parcial, y 3 si falla esa comprobación.

El lector verifica inventario cerrado, tamaños/SHA antes de decodificar,
secuencia de eventos, configuración y referencias de hijos, filas/esquema/NULL/
NaN/índice físicos, captura, snapshots de comparación y diferencias/reportes.
Integridad no autentica al autor o revisor, ni certifica independencia/corrección
del esperado. Dos motores equivalentes pueden compartir el mismo error.

Los `ArtifactRef` conservan URI locales absolutas; la evidencia del migrador no
es un bundle portátil del benchmark. Los presupuestos y la cancelación son
cooperativos; resolver/materializar entradas puede asignar memoria antes del
checkpoint. No se promete cuota dura de RSS ni preempción de callbacks. Los
controles reales de wheel/sdist/instalación y sus límites están registrados en la
[revisión del migrador](MIGRATION_REVIEW.md), que distingue los controles del
núcleo y del benchmark. La publicación sigue pendiente.

## APIs aditivas 0.11.0

| API / formato | Contrato y evidencia |
|---|---|
| `verify` / `VerificationRequest`, `VerificationResult` | Artefactos/ejecuciones externos; entradas, técnica, integridad, acuerdo, esperado, R, cobertura y O separados |
| `verify_migration`, `read_verification`, `verification_summary` | Adaptar expediente sin ETL; lector cerrado reconstruye decisiones y vínculos |
| `ExpectedProvenance`, `IndependentReviewEvidence` | Método/autores/dependencia declarados y revisión ligada a hashes; no autenticación humana |
| `ingest_file`, `FileInput`, `IngestionSpec`, `IngestionResult` | CSV/JSON/JSONL de esquema explícito, fuente original y recibos; grano/rutas declarados |
| `run_workflow`, `read_workflow`, `WorkflowRequest`, `WorkflowResult` | Captura única, dependencias/checkpoints, fallo y etapas saltadas; sin resume |
| `Destination`, `ParquetDestination`, `LoadReceipt` | Publicación local de tablas verificadas, staging, versiones, idempotencia y puntero |
| `export_bundle`, `import_bundle`, `read_bundle`, `inspect_bundle` | Inventario cerrado, relocalización y lectura sin callbacks de Verify/migración/workflow |
| `OracleVerificationBridge`, `oracle_verification_bridge` (benchmark) | Puente científico preservando APIs previas; core sin dependencia de benchmark |

Se añaden once JSON Schema públicos y las solicitudes CLI son datos tipados.
`WorkflowInputBinding` evita confusión con bindings internos de ejecución;
`IngestionConversionReceipt` evita colisión con recibos históricos de perfiles.
`Arithmetic`, `Coalesce`, `Conditional`, `Concatenate`, `Deduplicate` y semi/anti
join amplían el IR común. [Soporte por prueba](SEMANTIC_SUPPORT.md),
[Verify](VERIFY.md) y [ETL](ETL.md) definen restricciones y códigos de salida.

Los formatos previos de migración no se reescriben: el bundle conserva sus bytes
y resuelve URI históricas sólo a miembros capturados de hash/tamaño idénticos.
Un hash confiable externo puede fijar el manifiesto del bundle. Campos nuevos de
expedientes 0.11.0 no se anuncian como lectores de candidatos intermedios privados.

## Revisión del candidato 0.11.1

La entrega [STEP4: aserciones e integración](ASSERTIONS.md) incorpora
`assert_equivalent`, `equivalence_decision`, `EquivalencePolicy`,
`EquivalenceDecision` y la familia de errores `Equivalence*Error`. Los esquemas
policy/decision 1.0 complementan el resultado existente y no sustituyen su
veredicto. Persistencia verificada es un requisito opcional explícito.

**Cambio observable de compatibilidad:** `ComparisonResult.__bool__` lanza
`TypeError` para todos los estados; migre `assert result` al gate y comprobaciones
de ausencia a `result is not None`. La decisión exige su campo `.accepted`.
Los campos y esquemas anteriores conservan sus bytes. La validación del
resultado completo también rechaza conteos que contradigan metadatos de filas
en capturas presentes; un expediente inconsistente no gana compatibilidad por
haber sido aceptado antes. Este cambio se documenta
aunque el candidato permanezca privado y Alpha.


La entrega aditiva [STEP3: reporte común](REPORTS.md) incorpora
`ComparisonReport`, `ReportOptions`, `ReportCount`, `ReportValue`,
`ReportWitness`, `ReportPolicy`, `ReportViewPolicy`, `ReportEvidenceManifest`,
`ReportPublicationManifest`, `comparison_report`, `write_comparison_report`,
`read_comparison_report` y los tres `render_comparison_*`. Sus esquemas 1.0
son independientes de los formatos anteriores. La misma vista filtrada alimenta
JSON/texto/HTML/notebook, preservando juicio y cobertura. La lectura opcional de
evidencia exige una raíz explícita; la reproducción exportada solo conserva
comparaciones materializadas admitidas y su contexto. No cambia la captura
original, no añade aserciones ni reejecuta fuentes.


La entrega aditiva [STEP2: entrada directa](DIFF.md) incorpora `diff`,
`DiffCaptureOptions`, `DiffContract`, `PolicyProvenance`, `bag_contract`,
`keyed_contract`, `sequence_contract`, `infer_diff_contract` y
`read_diff_contract`. La firma, procedencia, ejemplos y límites se definen en
esa página. `diff` devuelve el `ComparisonResult` existente y usa referencia
derecha esperada por defecto; `compare` mantiene el default peer. Contratos,
especificaciones y resultados anteriores conservan sus esquemas 1.0; los dos
esquemas nuevos pertenecen a la declaración/las opciones de captura de la
fachada. No incluye nuevos métodos de presentación ni aserciones.

`equiframe_benchmark.evaluate_pairwise(report) -> PairwiseReport` deriva seis
soportes descriptivos R/M/B/H desde un EvaluationReport validado. Conserva el
informe/digest/protocolo original y recalcula sus métricas al leer; incorpora
un JSON Schema propio 1.0, sin cambiar EvaluationReport ni los seis CSV.
O debe estar confirmado y ambos métodos completos; alertas parciales y motivos
de exclusión permanecen visibles. El resultado conserva `scientific=False` y
no reemplaza una congelación previa. [Semántica y ejemplo](PAIRWISE_EVALUATION.md).

Ingestión y operaciones decimales nativas/R usan contexto propio sin alterar
el del consumidor; pérdida de escala/rango sigue siendo rechazo. La expansión
JSON y el registro de errores de parser respetan max_records. No se añaden
formatos de ejecución, tipos de dominio ni permisos del servicio/DW.
[Pruebas completas y compatibilidad](COMPREHENSIVE_REVIEW_20261003.md).


## Captura explícita DuckDB (STEP7)

`capture_duckdb(sql, *, work_dir, name="result", connection=None,
exclusive_connection=False, parameters=None, options=None, cancellation=None)`
ejecuta una sola consulta SELECT/WITH confiable y entrega el `TableArtifact`
existente, con tipo nativo observado y Arrow IPC desacoplado.
`DuckDBCaptureOptions` fija lotes, filas, bytes por lote, bytes del archivo y
tiempo cooperativo. Ambas superficies son experimentales; formatos previos 1.0
permanecen intactos. [Uso, propiedad y límites](DUCKDB_CAPTURE.md).

La conexión prestada requiere exclusividad explícita y autoload/autoinstall
desactivados por el propietario; no se cierra, configura, registra ni termina
su transacción. Su result slot se consume y un error puede requerir rollback
del llamante. La conexión privada se cierra antes de publicar. Ni el reporte ni
la comparación reejecutan SQL. Los límites no son cuotas duras de memoria, tiempo
o consistencia entre sistemas externos. No se aceptan relaciones/resultados
previos cuyo consumo y tipos nativos no puedan verificarse.

La admisión nativa compartida cierra además una pérdida en ejecución existente:
HUGEINT/UHUGEINT, UUID y otros tipos sin representación fiel declarada se rechazan
antes de Arrow. El SQL del consumidor puede convertir explícitamente a un tipo
admitido solo cuando la semántica/rango de su caso lo permita. No hay cast
implícito, recuperación de información perdida ni ampliación del IR de migración.

Los parámetros de ambas rutas DuckDB usan enlace Decimal exacto con precisión y
escala comprobadas; `1E-38` no se infiere como DOUBLE. Decimal no finito, cero
negativo, exponente positivo o >38 dígitos/escala e enteros fuera de signed/unsigned
64 bits se rechazan antes del SQL del consumidor. Texto y casts SQL explícitos
conservan disponibles conversiones deliberadas dentro del alcance de su contrato.

## Engineering scale measurements (STEP8)

The separate `equiframe_benchmark` package exposes experimental `ScaleSpec`,
`ScaleTrial`, `ScaleRun`, `measure_scale(spec, *, work_dir)`,
`read_scale(directory)` and `summarize_scale(result)`. This bounded synthetic
protocol does not replace the scientific cost experiment. `complete` means
expected workload/verdict completion, while `resource_measurement_complete`
separately records monitoring coverage. `scale` and `verify-scale` return 3 for
missing/invalid finalization or unsuccessful measurement. Native comparison
acceptance remains a separate core assertion. [Full scope and limits](SCALING.md).

## Post-roadmap core integration refactor (2026-10-06)

The generic pinned-snapshot types and consumer are now exported by core:
`SnapshotClient`, `SnapshotColumn`, `SnapshotTable`, `SnapshotManifest`,
`SnapshotDataSource` and `snapshot_fingerprint`. Existing benchmark imports are
identity-preserving aliases. The manifest schema, canonical ASCII JSON and
fingerprints are unchanged; the new core producer surface is experimental.
No transport, service/DW implementation or core-to-benchmark dependency is added.
The packaged [extension guide](../packages/equiframe/docs/extending.md) describes
core-only use and lower-level compiler input preconditions.

Workflow captures preserve index/provenance and isolate independent source
failures/consumer budgets. Native arithmetic corrections and strict optional
configuration validation are described in the current packaged changelog and
upgrading guide. These are ordinary functional/architectural changes; historical
scientific evidence is not rewritten or reinterpreted.


## Extensión nativa de producto 0.12.0a4

[Contrato detallado](../packages/equiframe/docs/migration-ir.md): joins right/full
con cardinalidad de claves emparejables, deduplicación determinista por clave,
multiplicación Decimal exacta, `DecimalRound`, división Decimal con escala y
redondeo declarados, transporte timestamp de unidad/zona exactas y
`LocalizeTimestamp` con gap rechazado y fold reject/earlier/later.
Pandas, Polars y DuckDB ejecutan implementaciones propias. Los límites por motor
y la restricción de sufijos Sort para controles DuckDB permanecen explícitos.
Los defaults nuevos se omiten en nodos con forma histórica, conservando los
fingerprints IR/spec 1.0. No se reescriben expedientes anteriores ni se cambia
el alcance metodológico o la independencia R/M/B/H/O.
