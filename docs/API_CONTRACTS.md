# API Python y contratos de intercambio

Especificación propuesta v0.1. No describe funciones ya implementadas. Los nombres se congelan tras las pruebas del paso 1 y cualquier ajuste queda registrado.

## 1. Principios

API síncrona para cálculos locales y objetos inmutables de configuración/resultados. La espera de trabajos remotos pertenece al cliente de José. No mantener una conexión global ni estado compartido implícito. Serialización estricta: campos desconocidos rechazados, coerciones con pérdida rechazadas y versión de esquema obligatoria.

Los formatos de intercambio se generan desde los modelos tipados y se verifican con ejemplos válidos e inválidos. Los JSON no contienen callbacks, expresiones Python, SQL arbitrario, contraseñas ni rutas ejecutables. Una transformación se referencia por ID y se resuelve en un registro explícito de código confiable.

## 2. Tipos públicos mínimos

| Tipo | Campos y restricciones |
|---|---|
| `LogicalType` | Unión discriminada: boolean, integer con tamaño/signo, string, decimal con precisión/escala, float con ancho, date, timestamp con unidad/zona. Tipos adicionales requieren versión y soporte del adaptador |
| `ColumnSpec` | `name`, `logical_type`, `nullable`, política NaN cuando corresponda. Nombres únicos en el esquema |
| `KeySpec` | Columnas existentes, unicidad requerida, política de claves incompletas y alcance de identificación |
| `NullPolicy` | Representaciones que cuentan como ausencia, política independiente de NaN; nunca cadena vacía/cero implícitos |
| `NumericPolicy` | Exactitud, redondeo explícito si aplica, tolerancia por columna con unidad y motivo |
| `TemporalPolicy` | Zona IANA, granularidad, tratamiento de timestamps sin offset, errores y límites de intervalos |
| `Contract` | `schema_version`, `contract_id`, `revision`, familia, esquemas de entradas/salida, claves, multiplicidad, orden, políticas, precondiciones y `RuleSpec[]` |
| `RuleSpec` | ID, tipo registrado, parámetros validados, columnas/etapas, severidad informativa y aplicabilidad. El resultado de alerta no se deriva de una severidad visual |
| `ArtifactRef` | URI sin secretos, SHA-256, formato, bytes, esquema asociado; semántica inmutable. Hash real requerido al ejecutar |
| `SnapshotManifest` | Versión, `snapshot_id`, revisión, archivos con hashes/cobertura/licencia, exclusiones y procedencia; distingue raw de tablas derivadas |
| `TableArtifact` | Referencia a tabla materializada, esquema físico y lógico, filas, metadatos de ausencia/NaN, particiones y procedencia |
| `RunContext` | IDs de corrida/ejecución, semillas, directorio de trabajo, límites, deadline, versión de código y ambiente |
| `ExecutionPlan` | Contrato, snapshot, ID de transformación, adaptador, versión/configuración, parámetros tipados y referencias de entrada |
| `ExecutionResult` | Estado, entradas/salida, tiempos por etapa, conversiones, esquema observado y error tipado si aplica |
| `RuleResult` | ID/revisión, decisión, valor observado/esperado, motivo, referencias de evidencia y completitud |
| `FeatureValue` | Nombre, valor opcional, aplicabilidad, numerador/denominador cuando corresponda, razón de ausencia y etapa |
| `ExecutionProfile` | Familia, versión de features, valores por orden fijo y procedencia. No incluye etiquetas en la matriz |
| `DetectorBundle` | Detector/familia, versiones, features y orden, imputación, parámetros, hashes de ajuste/calibración, semilla, alpha y umbral o motivo no estimable |
| `DecisionResult` | Método, decisión, score/umbral si existen, motivo y disponibilidad de componentes |
| `ComparisonResult` | `equivalent`, `different` o `not_evaluable`; conteos, localización, evidencia, normalización aplicada y recorrido completo |
| `OracleRecord` | Etiqueta, resultado esperado y su hash, comparación, controles del dominio, revisores y resolución |
| `RunReport` | Composición de resultados con referencias; no colapsa alerta, diferencia y etiqueta en un booleano |
| `FreezeManifest` | Hashes de contratos/reglas/features/splits/etiquetas/configuración/modelos, decisiones resueltas, fecha y responsables |

Decimal en JSON se expresa con representación textual y tipo/escala declarados. Infinitos y NaN se codifican como objetos etiquetados; nunca como tokens JSON no estándar. Timestamps conservan offset/zona y los días se representan como fechas. `null` significa ausencia del campo de resultado según el esquema, no un cero estadístico.

## 3. Estados independientes

- Ejecución: `completed`, `invalid_input`, `failed`, `timeout`, `resource_exhausted`, `cancelled`.
- Decisión de detector/reglas: `alert`, `no_alert`, `not_evaluable`.
- Etiqueta del oráculo: `correct`, `divergent`, `pending`, `not_evaluable`.
- Ajuste/calibración: `ready`, `not_estimable`, `incompatible`.
- Trabajo remoto: `queued`, `running`, `succeeded`, `failed`, `cancelled`.

Un mutante sin efecto es metadato de la variante; si O verifica su corrección, su etiqueta es `correct`. No se marca divergente por haber sido generado como mutación.

Tabla completa de H:

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

R agrega sus reglas con el mismo principio: cualquier incumplimiento probado alerta; solo `no_alert` cuando todas las reglas obligatorias aplicables se evaluaron y pasaron. Una regla no aplicable debe tener precondición documentada, no eliminarse silenciosamente. Un conjunto vacío de reglas no acredita evaluación: `not_evaluable` con motivo `no_applicable_rules`.

## 4. Puertos e interfaces

Firmas de diseño, a materializar como `typing.Protocol` y modelos tipados:

```python
class DataSource(Protocol):
    def resolve_snapshot(self, snapshot_id: str) -> SnapshotManifest: ...
    def materialize(self, artifact: ArtifactRef, destination: Path) -> Path: ...

class ArtifactStore(Protocol):
    def put(self, path: Path, *, media_type: str) -> ArtifactRef: ...
    def get(self, ref: ArtifactRef, destination: Path) -> Path: ...

class EngineAdapter(Protocol):
    def capabilities(self) -> EngineCapabilities: ...
    def execute(self, plan: ExecutionPlan, context: RunContext) -> ExecutionResult: ...

class Rule(Protocol):
    def evaluate(self, observation: ExecutionObservation,
                 spec: RuleSpec) -> RuleResult: ...

class Profiler(Protocol):
    def compute(self, observation: ExecutionObservation,
                spec: FeatureSetSpec) -> ExecutionProfile: ...

class Detector(Protocol):
    def fit(self, training: ProfileMatrix, spec: FitSpec) -> FittedDetector: ...
    def calibrate(self, fitted: FittedDetector,
                  calibration: ProfileMatrix, spec: CalibrationSpec) -> DetectorBundle: ...
    def score(self, profile: ExecutionProfile,
              bundle: DetectorBundle) -> DecisionResult: ...
```

`ExecutionObservation` contiene las entradas, la salida y medidas de una única ejecución. No contiene resultado esperado, otro motor, etiqueta ni mutación. `ProfileMatrix` contiene solo columnas permitidas y un manifiesto de procedencia separado de la matriz. `EngineCapabilities` declara versión y tipos/operaciones admitidos; el plan se rechaza cuando no es realizable fielmente.

Servicios públicos previstos:

```python
validate_contract(document) -> Contract
run(plan, *, source, artifacts, adapters) -> RunReport
compare(expected, actual, *, contract, limits) -> ComparisonResult
evaluate_rules(observation, *, contract) -> tuple[RuleResult, ...]
profile(observation, *, feature_spec) -> ExecutionProfile
decide_hybrid(rules_decision, model_decision) -> DecisionResult
render_report(report, *, destination, format) -> ArtifactRef
```

`run` recibe dependencias explícitas y configuración; no abre una base remota de manera implícita. Para callbacks, se registra ID y versión del código antes de ejecutar. Las transformaciones confiables usan DataFrames/SQL nativos y deben devolver salidas nuevas o declarar cualquier mutación del objeto de entrada.

## 5. CLI prevista

| Comando | Función |
|---|---|
| `equiframe contract validate <archivo>` | Validar contrato y emitir errores localizables |
| `equiframe run --config <archivo>` | Ejecutar plan operacional versionado |
| `equiframe compare --config <archivo>` | Comparación completa con contrato |
| `equiframe report <run-id> --format json\|html` | Renderizar evidencia existente |
| `equiframe-benchmark catalog validate <ruta>` | Integridad del catálogo y procedencia |
| `equiframe-benchmark split --config <archivo>` | Construir/verificar grupos y particiones |
| `equiframe-benchmark fit --config <archivo>` | Ajustar detectores con normales de entrenamiento |
| `equiframe-benchmark calibrate --config <archivo>` | Calibrar con normales separados |
| `equiframe-benchmark freeze --config <archivo>` | Verificar y congelar requisitos de evaluación |
| `equiframe-benchmark evaluate --freeze <archivo>` | Evaluación final y métricas |

Reconciliación del DW: Jhair registra una operación de dominio invocable por configuración; Hernán provee el mecanismo y el reporte, no SQL SERCOP dentro del núcleo. No se publica un comando vacío de reconciliación.

Códigos de salida operacionales: 0 evaluación completada sin alerta/diferencia según el comando; 1 alerta o diferencia observada; 2 configuración/entrada inválida; 3 fallo de ejecución, recurso o resultado no evaluable. Para benchmark, 0 significa ejecución experimental completa aunque existan divergencias; el JSON contiene decisiones y cobertura. Cuando coexisten alerta y fallo, el reporte conserva ambos y el código 3 tiene prioridad. La CLI documenta esta diferencia para automatización.

## 6. Errores y recuperación

Jerarquía prevista: `EquiFrameError` con código estable y detalles tipados; `ContractValidationError`, `InputValidationError`, `UnsupportedEngineFeature`, `ArtifactIntegrityError`, `SchemaVersionError`, `ExecutionFailure`, `ResourceLimitError`, `ModelCompatibilityError` y `RemoteDataError`.

Errores de construcción/configuración se lanzan al invocar la API; errores de una ejecución iniciada se registran en `ExecutionResult` y `RunReport`. Nunca capturar `Exception` y devolver éxito. Los adaptadores preservan la causa saneada, sin secretos. Una opción explícita de la API puede relanzar después de persistir evidencia.

Reintentos: solo lecturas idempotentes y operaciones remotas con clave de idempotencia comprobada. Timeout del cliente no prueba que una escritura falló; consultar su trabajo antes de repetirla.

## 7. Versiones, extensibilidad y recursos

`schema_version` gobierna la lectura de formatos; revisión del contrato gobierna significado; versión de paquete gobierna API. Cambios incompatibles se rechazan o migran mediante función explícita con evidencia. Los hashes se calculan sobre representación canónica documentada, no `repr()` ni `hash()` de Python.

Límites de memoria/tiempo, hilos, disco temporal, tamaño de lote y máximo de diferencias mostradas pertenecen al plan. La cancelación debe cerrar recursos y registrar artefactos parciales. `RunContext` no contiene secretos; el proveedor de credenciales del servicio permanece fuera de la evidencia.
