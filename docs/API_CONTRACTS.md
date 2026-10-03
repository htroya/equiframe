# API Python y contratos de intercambio

Versiones implementadas: `equiframe 0.9.0` y `equiframe-benchmark 0.10.0`, formatos independientes `1.0`, pasos 1 a 10 técnicos. El [README del
paquete](../packages/equiframe/README.md) contiene instalación, comandos y un
ejemplo Python ejecutable. La aceptación del servicio real y la evaluación científica conservan sus requisitos externos.

## 1. API disponible

| Servicio | Comportamiento comprobable |
|---|---|
| `validate_contract(document) -> Contract` | Texto JSON, bytes UTF-8 o mapping compatible con JSON; validación estricta y cruzada |
| `read_contract(path) -> Contract` | Lee un archivo y usa el mismo validador |
| `write_contract(contract, path) -> None` | Revalida y escribe exactamente los bytes canónicos |
| `canonical_contract_bytes(contract) -> bytes` | Representación de metadatos canónica v1 |
| `contract_fingerprint(contract) -> str` | SHA-256 hexadecimal de esos bytes; no equivalencia tabular |
| `contract_json_schema() -> dict[str, object]` | JSON Schema generado desde `Contract` |

La API explícita está en `equiframe.__all__`; `__version__` es `0.9.0`.
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
12–16. El cliente autenticado, DW y operación del servicio siguen bajo los
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

Siete esquemas nuevos 1.0. `DetectorVersions` acepta 0.7.0/0.8.0/0.8.1/0.9.0 sin cambiar el
algoritmo IF/MAD. El núcleo no importa benchmark ni acepta O como entrada del
runner. [Uso y códigos CLI](ORCHESTRATION.md), [diseño y límites](STEP_08_DESIGN.md).

## 15. Consumidor e integración experimental en 0.9.0

La implementación original del paso 9 requiere núcleo 0.8.1; la distribución
actual `equiframe-benchmark 0.10.0` requiere núcleo 0.9.0.

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

## 16. Congelación, evaluación y reproducción en 0.10.0

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
