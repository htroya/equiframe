# Arquitectura de EquiFrame

Actualización 2026-10-10: pareja privada core/benchmark A12. Añade diagnóstico de
instalación y ejercicios por rol sobre la API existente; no cambia la propiedad
de componentes, los motores ni R/M/B/H/O. Las secciones A7/A8 siguientes son
históricas. La admisión actual es Python 3.10–3.13; las matrices fechadas y sus
artefactos identifican qué combinaciones se ejecutaron realmente.

Nota de candidato de madurez 2026-10-08: a8 amplía la admisión objetivo a Python 3.10-3.13; consulte [el plan M01-M16](MATURITY_PLAN.md). Las secciones y recibos históricos siguientes conservan su candidato y no acreditan pruebas nuevas.

Estado actual: candidatos núcleo `0.12.0a7` y benchmark `0.12.0a7`, sobre pasos 1–10 técnicos y migrador, con Verify operacional y ETL local. Las revisiones actuales contribuyen a 11–13 y la preparación de distribución sin cerrar sus criterios externos. La aceptación del servicio/DW real, el corpus, las revisiones independientes y la evaluación científica siguen pendientes. Fuente histórica del diseño: borrador identificado en [trazabilidad](THESIS_TRACEABILITY.md). La [arquitectura del paso 8](STEP_08_DESIGN.md), el [paso 9](STEP_09_DESIGN.md), la [evaluación del paso 10](STEP_10_EVALUATION.md) y el [diseño del migrador](MIGRATION_DESIGN.md) conservan sus decisiones y evidencias. Las secciones fechadas por versiones anteriores describen esa evolución; no sustituyen este estado actual.

## 1. Propósito y alcance

EquiFrame permite a programadores y analistas expresar qué debe conservar una transformación tabular, compilar planes declarativos para motores concretos, ejecutarlos, obtener evidencia de incumplimientos y comparar resultados. La evaluación científica prevista estudia si Isolation Forest aporta detecciones frente a reglas operativas limitadas y cuánto cuestan esas detecciones. Una anomalía observada no constituye por sí sola una corrupción.

Se implementa como biblioteca Python de propósito general con contratos configurables, API `import equiframe as ef`, tipos e inyección de dependencias para proyectos externos, scripts y notebooks. La instalación base tiene utilidad propia; los motores son extras. El objetivo `pip install equiframe` exige una publicación verificable posterior. Estos requisitos de producto acordados por Hernán no se atribuyen como texto ya presente en el borrador histórico. Desarrolladores, analistas y arquitectos pueden reutilizar el núcleo sin SERCOP/OCI/DW. La extensibilidad del migrador se concreta en protocolos y registros explícitos; su IR inicial cubre una intersección de tres motores. El dominio SERCOP es un consumidor de las interfaces. El servicio, el procesamiento distribuido y la traducción de programas Python/SQL arbitrarios quedan fuera de ese IR.

El alcance científico principal contiene nulos/tipos (`nulls_types`), joins (`joins`) y agregaciones (`aggregations`), cruzados con Pandas–Polars, Pandas–DuckDB y Polars–DuckDB: nueve estratos. Las cinco familias genéricas del software añaden duplicados/orden (`duplicates_order`) y fechas (`dates`) como capacidades reutilizables. Declararlas en los formatos no obliga a presentar cinco familias como resultados científicos de la tesis. Verify es también una API operacional reutilizable del núcleo; su dimensión científica O conserva independencia y revisión. Los módulos y tipos `oracle` existentes mantienen su API mediante un puente tipado.

## 2. Distribuciones y dependencias

El acuerdo histórico A71 situó la disponibilidad pública después del paso 10 y
una nueva revisión. La publicación conserva su gate propio en la hoja de ruta:
instalaciones locales, inventarios de distribución y controles históricos de CI
no acreditan por sí solos una publicación o una instalación desde PyPI. Los
controles de distribución actuales y sus pendientes están registrados por
separado en la [revisión del migrador](MIGRATION_REVIEW.md).

Un monorepo, distribuciones separadas por responsabilidad:

| Distribución / import | Responsable | Dependencias y finalidad |
|---|---|---|
| `equiframe` / `equiframe` | Hernán | Contratos, ejecución, migración declarativa, comparación, reglas, perfiles, detectores, evidencia y API/CLI operacional |
| `equiframe-benchmark` / `equiframe_benchmark` | Hernán | Depende de `equiframe`; escenarios, EquiFrame Verify, particiones, mutaciones, freeze, evaluación, costes y reproducción |
| `equiframe-data` / `equiframe_data` | José | Cliente de acceso a snapshots y trabajos; compatible con los formatos de intercambio |
| `equiframe-sercop` / `equiframe_sercop` | Jhair | Esquema, mapeos, preparación, carga y reconciliación del DW; consume los contratos de integración |
| `services/data-gateway` | José | Proceso servidor, coordinación de escrituras y publicación de versiones |

Los nombres de distribución son internos hasta comprobar disponibilidad y acordar publicación. La biblioteca `equiframe` no importa `equiframe_benchmark`, `equiframe_data` ni `equiframe_sercop`. Los plugins concretos se registran explícitamente; no se descubre ni ejecuta código arbitrario al importar.

Base declarada actual: Python 3.12 y 3.13 (`>=3.12,<3.14`); los resultados medidos y las plataformas no verificadas están en [STEP6](STEP6_CANDIDATE.md). El paso 1 verificó Windows x64 y Linux x64; ARM64 requiere validación antes de declarar soporte para la VM A1. `pyproject.toml`, estructura `src/`, marcadores `py.typed`, wheel/sdist y versiones semánticas. Durante 0.x los cambios incompatibles requieren changelog y migración explícita.

Dependencias del paso 1: Pydantic 2 para formatos estrictos, `tzdata` como base IANA exclusiva en Windows/Ubuntu y Typer para CLI. Versiones de ejecución, desarrollo y backend resueltas y fijadas con hashes en `packages/equiframe/uv.lock`. Paso 2 añade extras funcionales `arrow`, `pandas`, `polars`, `duckdb` y `engines`; cada motor requiere PyArrow. El paso 7 añade el extra funcional `ml` para el ajuste de Isolation Forest. Cada perfil de instalación debe verificarse desde wheel fuera del checkout. Pandas/Polars/DuckDB/scikit-learn/NumPy/PyArrow no se importan al hacer `import equiframe`.

El almacenamiento tabular Arrow no reemplaza la semántica del contrato. La extracción conserva tipo físico, tipo lógico, máscara de ausencia y NaN antes de cualquier conversión. Un adaptador que no pueda preservar una distinción exigida debe informar incompatibilidad; no adivinarla.

## 3. Vista de componentes

```mermaid
flowchart TD
    User[Python / Notebook / CLI] --> Runner[Runner de EquiFrame]
    Contract[Contrato y configuración versionados] --> Runner
    Source[Snapshot inmutable / proveedor de datos] --> Runner
    Runner --> Engines[Adaptadores Pandas / Polars / DuckDB]
    Engines --> Output[Salida materializada y trazable]
    Output --> Rules[Reglas R]
    Output --> Profile[Perfil de una ejecución]
    Profile --> IF[Isolation Forest M]
    Profile --> MAD[Referencia MAD B]
    Rules --> Hybrid[Decisión H = R OR M]
    IF --> Hybrid
    Rules --> Evidence[Evidencia y reportes]
    IF --> Evidence
    MAD --> Evidence
    Hybrid --> Evidence
    Output --> Compare[Comparación completa]
    Expected[Resultados esperados revisados] --> Compare
    Compare --> Oracle[EquiFrame Verify O y revisión independiente]
    Oracle --> Evaluation[Evaluación pareada]
    Evidence --> Evaluation
```

No existe flecha desde O, etiquetas o mutaciones hacia los perfiles o detectores. La selección de ejecuciones normales para entrenar usa etiquetas confirmadas en el paquete experimental; entrega a los detectores exclusivamente la matriz permitida y su manifiesto.

## 4. Módulos de la biblioteca de Hernán

| Módulo | Responsabilidad | Límite |
|---|---|---|
| `contracts` | Esquemas lógicos, claves, multiplicidad, nulos, precisión, tiempo, precondiciones, especificaciones de reglas | No contiene nombres OCDS obligatorios ni código ejecutable en JSON |
| `types` | Referencias a artefactos, estados, identificadores y resultados tipados | Tipos públicos estables y serialización versionada |
| `ports` | Protocols `DataSource`, `ArtifactStore`, `EngineAdapter` | No requiere infraestructura concreta |
| `adapters` | Ejecutar callbacks nativos o SQL registrado; describir y materializar salidas | No traducir automáticamente Pandas a Polars/SQL |
| `migration.types`, `migration.validation`, `migration.ports`, `migration.backends` | IR cerrado, inferencia y compilación nativa por motor; `PlanCompiler` y registro explícito | Capacidades por pareja; sin código/importaciones de plugins en JSON |
| `migration.runner`, `migration.runner_types`, `migration.io` | Captura fijada, dos pipelines, comparación, esperado opcional y evidencia local | Integridad y equivalencia observada separadas de la independencia/corrección del esperado |
| `normalization` | Aplicar únicamente equivalencias autorizadas por contrato | Sin relleno de nulos, deduplicación ni redondeo implícitos |
| `comparison` | Igualdad de esquema lógico, valores, filas, multiplicidad y orden cuando aplique | Diferencias completas/localizables; independiente de R/M/B |
| `rules` | Reglas R evaluables sobre entrada y salida de una ejecución | Sin consultar otra implementación ni la etiqueta O |
| `profiles` | Variables por familia con denominadores, aplicabilidad y motivos | Sin IDs, motor, mutación, etiqueta o partición como features |
| `preprocessing`, `detectors`, `detector_types` | Preprocesamiento ajustado, Isolation Forest, MAD y calibración | Entrenamiento, calibración e inferencia separados |
| `decision` | Tabla de verdad de H y disponibilidad de componentes | Una regla que alerta no queda anulada por M |
| `execution` | Orquestación, materialización forzada, límites y captura de fallos | Corridas aisladas y reproducibles; no administrar la VM |
| `pipeline`, `pipeline_types`, `evidence`, `reporting`, `reduction` | Orquestación operacional, manifiestos, eventos, hashes, reportes JSON/HTML y reducción acotada | No sobrescribir corridas ni ejecutar contenido del reporte |
| `cli` | Entradas operacionales estables sobre la misma API Python | Sin lógica semántica duplicada |

`equiframe_benchmark` implementa catálogo/EquiFrame Verify en `models`, `oracle`,
`splits`, `selection`, `training_types`, `io`, `fixtures`, `mutations` y un
piloto ejecutable. El paso 8 añade CLI validate/split/pilot y orquesta sus capturas.
El paso 10 implementa `freeze`, `study`, `evaluation`, `tables`, `costs`,
`reproduction`, `study_bundle` y `distribution`. Las métricas y CSV pueden
regenerarse desde registros capturados; los resultados científicos y la repetición
humana independiente siguen pendientes.
O no se importa desde las reglas o los detectores. Las revisiones reales
no se sustituyen por las identidades ficticias de las pruebas.

## 5. Flujo de una ejecución

1. Paso 2: validar metadatos de contrato/configuración, versión, registro, disponibilidad/capacidades y nombres de entradas. Precondiciones ejecutables y validadores quedan para sus pasos.
2. Resolver una versión inmutable de entrada; comprobar hashes y permisos de lectura. Nunca resolver `latest` de nuevo a mitad de la corrida.
3. Registrar `run_id`, `execution_id`, escenario/variante fuera del vector del modelo, hashes, versión del código y entorno.
4. Ejecutar la implementación registrada en un contexto propio. DuckDB recibe conexión propia a una base temporal o de solo lectura; Polars lazy registra planificación y materialización separadas; el tiempo total incluye ambas y solo se declara completed después de collect.
5. Capturar salida fiel, tipos físicos nativos/Arrow, índices, ausencias/NaN, filas y artefacto tabular. Esquema esperado del contrato y esquema observado permanecen separados; no hay normalización en el paso 2.
6. Aplicar precondiciones posteriores, R y perfil. Evaluar M y B solo si sus bundles son compatibles. Componer H con estado de disponibilidad.
7. Persistir evidencia por escritura temporal y publicación atómica del manifiesto final. Un fallo deja estado fallido y diagnóstico, nunca un resultado exitoso incompleto.
8. En evaluación, calcular O mediante EquiFrame Verify desde el resultado esperado revisado y comparar métodos únicamente después. En uso operacional, el esperado puede omitirse; una comparación entre motores informa equivalencia observada sin acreditar corrección independiente.

No se reintenta automáticamente una transformación con efectos externos. Una corrida repetida conserva el mismo plan/hash pero obtiene otro `run_id`; reproducibilidad significa igual contenido lógico y decisiones, no iguales timestamps.

## 6. Semántica de comparación

- Clave única comprobada: alinear por clave y localizar filas/columnas faltantes o diferentes. No asumir unicidad por declararla.
- Repeticiones permitidas: comparar multiconjuntos completos con sus multiplicidades. Un conjunto de hashes o una muestra no certifican igualdad.
- Orden significativo: comparar secuencia con las reglas de desempate declaradas. Orden ignorado solo por autorización del contrato.
- Dinero: decimal exacto con escala y redondeo declarados. Sin conversión intermedia a float. Monedas conservadas y separadas.
- Ausencia lógica, NaN, cadena vacía y cero: estados distintos salvo equivalencia explícita del contrato. Si el motor ya perdió información, queda registrado como incumplimiento o caso no evaluable según la evidencia.
- Fechas: separar instante, zona y día. No asignar zona a timestamps sin offset sin política expresa. Preservar granularidad original.
- Tolerancias aproximadas: por columna con unidad, absoluto/relativo y justificación. No se introducen para dinero exacto ni tras observar un fallo.
- Grandes tablas: particionar por representación canónica de clave/fila; comparar contenido exacto dentro de particiones con spill a disco. Los hashes sirven para distribuir y verificar integridad, no como sustituto de comparar valores. El paso 3 implementa índices SQLite de valores completos; véase [comparación](COMPARISON.md).

Una limitación de memoria o tiempo produce comparación `not_evaluable`, no equivalencia. El resumen puede truncar los ejemplos de diferencias; el manifiesto registra conteos totales, artefacto de diferencias y si el recorrido se completó.

## 7. Persistencia y trazabilidad

Paso 2 produce `run.json`, entradas capturadas y salida Arrow con referencias, tamaños y SHA-256 en un directorio propio. Paso 3 añade `comparison.json`, diferencias JSONL y snapshots en carpetas independientes. Paso 4 añade `rules.json` y hallazgos JSONL en otra carpeta propia. Paso 5 añade `profile.json` y bundles JSON de preprocesamiento. El paso 8 integra `environment.json`, `events.jsonl`, resultados de componentes y `report.html`, con manifiesto final exclusivo e inventario verificable. El paso 10 añade freeze, estudios, evaluación, seis CSV verificables, observaciones de costes y bundles de reproducción en el benchmark. El migrador añade `spec.json`, `capture.json`, pipelines/comparaciones y `migration.json` final. Cada formato tiene `schema_version`.

Artefactos grandes: Arrow/Parquet con esquema y hashes; JSON para metadatos y valores especiales etiquetados. Un hash de archivo verifica bytes; un digest lógico versionado puede resumir contenido canónico, pero no reemplaza la prueba exacta. El manifiesto final contiene hashes de sus artefactos y el estado de completitud.

La evidencia es append-only a nivel de corrida. Las revisiones generan registros nuevos enlazados; los reportes no borran decisiones previas. Credenciales, URLs firmadas y valores sensibles no se registran. Los reportes HTML escapan valores de entrada.

## 8. Integración con la VM y el DW

La VM es un entorno opcional de colaboración. El núcleo usa archivos locales; la matriz CI incluye Windows, Linux y macOS. El cliente de José debe entregar snapshots y recibos; un adaptador del lado consumidor implementa `DataSource` sin que EquiFrame importe el cliente al arrancar.

Propuesta para el servicio de José: un proceso propietario de la base mutable recibe trabajos, coordina transacciones y publica snapshots inmutables en directorios versionados. Los lectores usan la última versión publicada o una versión fijada; el escritor construye la siguiente. Un catálogo/puntero se publica solo después de los controles. No se reemplaza un archivo abierto, especialmente en Windows, ni se borran snapshots todavía utilizados.

Así tres personas pueden desarrollar y consultar a la vez; las escrituras al mismo estado pueden esperar en una cola. No se promete ausencia de esperas ni conflictos. Lectura de un snapshot publicado significa aislamiento y puede tener retraso respecto de la carga en curso.

DuckDB embebido permite lecturas/escrituras dentro de un proceso o varios procesos de solo lectura. La documentación actual también describe acceso remoto y otras alternativas; José deberá fijar una versión y demostrar su estrategia. Este diseño no depende de una extensión beta ni añade otra base de datos por defecto. Referencia: [concurrencia de DuckDB](https://duckdb.org/docs/current/connect/concurrency).

Jhair entrega el modelo lógico/físico, esquemas versionados, contratos de dominio y reconciliación. EquiFrame produce evidencia y validadores reutilizables; Jhair decide la publicación del DW mediante sus controles completos. Una ausencia de alerta H no autoriza una carga ni reemplaza la reconciliación.

## 9. Calidad profesional y límites verificables

Tipos públicos, errores específicos, compatibilidad documentada, pruebas por propiedades, pruebas entre motores, wheel instalable, CI y documentación de ejemplos ejecutables son requisitos de entrega. La matriz de cobertura está en [calidad](QUALITY.md).

Los límites de memoria, tiempo, hilos, tamaño de lote, spill, ejemplos de diferencias y reducción son configurables y se registran. Inicialmente no se promete latencia o tamaño máximo sin mediciones. La VM prevista de 2 OCPU/12 GB requiere límites agregados del servicio; tres procesos no pueden reservar cada uno 12 GB.

Para medir rendimiento se ejecuta un experimento a la vez, con recursos y caché documentados. El desarrollo concurrente es compatible con la plataforma; un benchmark comparativo durante cargas de otros usuarios no produce una medición controlada.

## 10. Evolución del borrador

El código admite contratos y configuraciones versionados. Fecha de cohorte, escala decimal, reglas de claves incompletas, alpha, familias estimables y tamaños de grupos se fijan con evidencia durante el piloto. El modo final exige un `FreezeManifest` completo. Modificar una decisión congelada crea una nueva versión experimental y no reescribe las métricas anteriores.

La calidad del software puede ser profesional aunque el estudio siga exploratorio. No se declara uso productivo en SERCOP ni una ventaja de H hasta obtener resultados.


## 11. API y alcance implementado del paso 2

`ef.execute(plan, *, source, registry, adapter=None, artifact_store=None,
work_dir=None, cancellation=None) -> ExecutionResult` es la entrada funcional.
Se ajusta el runner completo previsto: ahora solo resuelve datos, ejecuta código
registrado, materializa y persiste evidencia. La orquestación R/perfiles/modelos/
comparación permanece en pasos 3–8. Contratos JSON contienen declaraciones,
nunca callbacks o SQL; estos se registran explícitamente como código confiable.

`ExecutionPlan`, `ExecutionOptions`, `ExecutionResult`, `EngineCapabilities`,
`PhysicalColumn`, `TableArtifact`, parámetros/timings/versiones son modelos frozen
estrictos. `RunContext`, `CancellationToken`, registro y `LoadedTable` son objetos
runtime por corrida/consumidor. `ArtifactStore`, `DataSource` y `EngineAdapter`
son puertos completos; no hay registro, conexión o runner global.

Entradas Arrow/locales o nativas explícitas: `ArrowInput`, `PandasInput`,
`PolarsInput`, `ArtifactRef`. Almacén local verifica copia/hash/tamaño y publica
sin sobrescritura por enlace duro. Arrow IPC file es la salida principal; Parquet
es entrada soportada. No hay lector SQL sobre base compartida, descargas ni URI
remotas implícitas. Extender `DataSource` después permitirá integrar el cliente de
José, sin importarlo desde el núcleo. Contratos de Jhair siguen fuera del núcleo.

Pandas protege datos/índice del consumidor; Polars materializa lazy y mide
planificación/captura; DuckDB abre `:memory:` propio, parametriza valores, controla
nombres y desactiva SQL externo/extensiones descargadas. Cada motor usa su código
nativo. La [matriz de transporte](../packages/equiframe/README.md) delimita decimal,
NULL/NaN, fechas, ns, zonas, índices y objetos no capturables. La política temporal
del contrato usa tzdata Python; los motores registran su proveedor real y no se
asume igualdad de versiones IANA.

Los presupuestos de tabla son checkpoints tras materialización, no cuotas de
asignación/RSS. Timeout/cancelación de callbacks y Polars collect son cooperativos;
DuckDB además interrumpe consulta y une el monitor antes de cerrar. No se abandona
un callback propio ejecutándose para aparentar un timeout duro. El manifiesto usa
los estados del paso 1 y no emite juicio semántico ni alerta.

La planificación inicial del producto 0.2 vinculaba distribución pública y paso
10. La hoja de ruta posterior separa el cierre técnico de la publicación: licencia,
control del nombre, metadatos, versiones soportadas e instalación desde PyPI
necesitan comprobaciones propias. Esta sección conserva el alcance histórico de
ejecución y no acredita la distribución final actual ni su publicación.


## 12. Revisión 0.2.1 e integración OCI

La captura conserva anchos/máscaras nativos y rechaza pérdidas conocidas antes de
convertir. Los límites temporales y decimales son propios de cada motor; no se
reduce el contrato para ajustarlo a una implementación. Evidencia parcial publicada
se retiene en el manifiesto fallido cuando el guardado del índice se interrumpe.
Puertos runtime y manifiestos se validan sin comparar salida y esquema esperado.

El [contrato OCI](OCI_INTEGRATION.md) sitúa el DW y su programa de conexión dentro
de la VM. EquiFrame puede ejecutarse allí o recibir snapshots por un proveedor
externo explícito. CI verifica el mismo código en runners GitHub temporales;
no despliega OCI ni acredita la integración real pendiente del paso 9.

## 13. Comparación operativa en 0.3.0

`ef.compare` consume salidas locales ya materializadas, valida el esquema de salida,
aplica exclusivamente equivalencias declaradas y compara todo el contenido por
secuencia, clave comprobada, multiconjunto exacto o emparejamiento máximo aproximado.
Lectores por lotes y SQLite privado permiten spill sin materializar tablas completas.
Publica `comparison.json`, diferencias JSONL completas y snapshots referenciados.
Los estados incompletos conservan evidencia parcial y nunca equivalencia.

La [especificación de comparación](COMPARISON.md) define políticas suplementarias
versionadas, mapeos físicos/lógicos, alcance, algoritmos y presupuestos. Contratos
1.0 y sus huellas no cambian. Índices separados requieren decisión expresa.
El comparador no implementa R, perfiles, detectores, benchmark, CLI operacional ni EquiFrame Verify (O).

## 14. Perfiles y preprocesamiento en 0.5.0

`profile_execution` usa exclusivamente tablas verificadas de una captura y una
`ProfileSpec` de fórmulas cerradas. Metadatos y `ProfileVector` están separados.
No importa reglas ni invoca la comparación; utiliza las primitivas de valores
exactos y tiempo ya disponibles. No modifica las tablas ni imputa sus ausencias.

`fit_preprocessor` acepta perfiles seleccionados como entrenamiento normal;
`transform_profiles` aplica el bundle inmutable, sin reajustarlo. Produce un único
`FeatureMatrix` para M/B del paso 7. La selección científica y sus grupos son
responsabilidad del benchmark, no del núcleo. No se infiere normalidad a partir de R.

Publica `profile.json`; perfiles y bundles tienen formato propio 1.0 y lectura
estricta. Los recibos suplementarios registran intentos de conversión de la misma
captura. Límites contables y cancelación son cooperativos; no hay spill para el
perfilado en esta versión. [Fórmulas y límites](PROFILES.md).

## 15. Detectores implementados en 0.7.0

`DetectorFit` conserva preprocesamiento compartido, configuración, versiones,
soporte, bosque declarativo y parámetros MAD. `DetectorBundle` incorpora
calibración normal independiente con n/alpha/k/umbral y huellas. La inferencia
no carga objetos ejecutables ni requiere ML. `decision.combine_decisions`
implementa OR de tres estados y disponibilidad. `equiframe_benchmark` incorpora
selección normal de calibración y auditoría de grupos sin transmitir etiquetas
a features. [Diseño](STEP_07_DESIGN.md), [semántica y uso](DETECTORS.md).
El ensamble operacional completo y su manifiesto están implementados desde el
paso 8; véase [orquestación](ORCHESTRATION.md).

## 16. Paso 10 técnico y alcance científico actual

`FreezeManifest` fija catálogo, grupos, splits, modelos/selecciones, decisiones,
archivos, entorno y protocolos. `pilot` requiere integridad técnica y conserva
bloqueos científicos; `final` exige resolverlos. `run_study` reaudita antes/después,
ejecuta cada caso sin entrenar y conserva fallos/no evaluables. O confirmado se
reutiliza sólo después de comprobar entradas, implementación y salida fresca.
`evaluate_records` calcula métricas/cobertura/intervalos desde registros y
`write_tables` publica seis CSV deterministas. Los costes miden operaciones sobre
capturas ya materializadas; sus repeticiones no aumentan la muestra de detección.

Las tres parejas usan la misma semántica y un esperado independiente; Pandas no
se convierte en O por actuar como origen. `run_integration` ejecuta tres motores
una vez y compara las tres parejas. Los estudios que se articulen por pareja
deben fijar el mismo catálogo, particiones y componentes de dependencia, conservar
identidades de ejecución y evitar contar una captura reutilizada como observación
independiente adicional. No hay un consolidador automático de tres estudios que
resuelva estas decisiones metodológicas ni una escala común implícita de scores
de modelos diferentes.

El formato genérico de freeze conserva cinco slots de familia; una familia sin
bundle necesita motivo explícito. En modo final el protocolo declara las cinco,
aunque familias fuera del alcance principal puedan tener cero casos y soporte
ausente. Los nueve estratos principales de la tesis deben distinguirse de esas
declaraciones genéricas y estratos vacíos. El corpus real, las etiquetas/revisiones
humanas, el soporte de entrenamiento/calibración y la repetición externa siguen
pendientes. El criterio `N_fit > 10_000` corresponde a registros reales de la
matriz efectiva de aprendizaje, no al número de adjudicaciones fuente ni a la
suma de capturas reutilizadas o registros de calibration/test. Deben informarse
N por modelo/familia, soporte y grupos;
no se atribuye al PDF del anteproyecto un mínimo literal por cada familia.

## 17. Migrador declarativo del núcleo 0.10.0

`check_migration` comprueba ambos compiladores sin ETL ni lectura de entradas.
`migrate` comprueba dependencias/capacidades, resuelve cada tabla una vez, aísla
buffers, valida sus valores/tipos y comprueba restricciones físicas de ambos
motores antes de ejecutar. Dos pipelines reciben las mismas capturas; el esperado
opcional se fija aparte y sólo participa en las dos verificaciones de salida.
La API usa `MigrationSpec`, `MigrationOptions`, `MigrationRequest` y
`MigrationResult`; la CLI ofrece `migration validate/run/verify`.

El IR 1.0 admite Scan, Project, Filter, Cast exacto, EquiJoin inner/left,
Aggregate y Sort, con DAG acotado y expresiones tipadas cerradas. Preserva NULL,
NaN, lógica booleana de tres valores, multiplicidad, unidades, políticas de claves
NULL, grupos ausentes y sumas vacías. Cast sólo amplía enteros o precisión decimal
sin cambiar escala. Los agregados exactos usan enteros/Decimal; el rango común
decimal llega a precisión 38. Timestamps, claves de join/agrupación/orden float y
SUM/min/max float no forman parte de este IR inicial; `count_valid` sí admite
columnas float. Polars comprueba una cota conservadora antes de
SUM y puede rechazar cancelaciones seguras; DuckDB sólo admite Aggregate/Sort con
rechazo de empates finales o con sufijo Sort, para impedir que la optimización
elimine errores intermedios. Se informa capacidad no soportada, sin fallback.

`require_rules=True` exige la completitud de los pipelines. Usar explícitamente
`require_rules=False` exige ETL y los perfiles/detectores solicitados, conservando
R/H no evaluables y alertas parciales; no cambia el estado ni el código de salida
original de cada `PipelineResult`. La equivalencia entre pares (`state`) y la
verificación contra esperado (`verification`) son campos separados. Códigos de
run: 0 completo sin alerta/diferencia, 1 completo con alerta/diferencia, 2 entrada
o capacidad/dependencia de preflight inválida, 3 parcial/no evaluable.

`read_migration` verifica inventario, hashes, eventos, configuraciones, hijos,
metadatos físicos, snapshots y diferencias/reportes sin ejecutar ETL. Esa lectura
acredita integridad local, no autenticidad humana, independencia o corrección del
esperado. Los `ArtifactRef` locales mantienen rutas absolutas: este conjunto de
evidencias no es un bundle portátil del benchmark. Los presupuestos son
checkpoints cooperativos; no ofrecen una cuota dura de RSS. Los controles reales
de wheel/sdist/instalación y sus límites están en la
[revisión del migrador](MIGRATION_REVIEW.md); la publicación sigue pendiente.

## Recorrido local 0.11.0

`ingest_file` fija fuente original y esquema; `run_workflow` fija entradas y
encadena migraciones nativas ya existentes. Cada checkpoint conserva comparación
entre motores y frente a esperado. `verify_migration` inspecciona después esa
evidencia sin ejecutar. `ParquetDestination` vuelve a leer el gate de Verify,
valida staging y publica una versión mediante un puntero local. `bundle` permite
copiar el expediente cerrado sin cambiar bytes históricos.

No existe dependencia core→benchmark ni acceso desde M/B a O/otras salidas.
La publicación local no implementa el gateway/DW. Ingestión materializa JSON y
recibos; los presupuestos siguen siendo cooperativos y por etapas. El IR común
no acepta cualquier ETL; la [matriz](SEMANTIC_SUPPORT.md) identifica condiciones,
rechazos y huecos sin extrapolar todos los cruces posibles.

## Consolidación privada: fronteras compartidas y descubrimiento

El candidato posterior a `c4be1c5a` conserva la fachada pública y los formatos.
La ruta pequeña de uso está en el [inicio español](../packages/equiframe/docs/inicio.md)
y la [selección de API](../packages/equiframe/docs/choosing-api.md), sin otra capa
que duplique comparación, ejecución, migración o Verify.

`_document_io` reúne únicamente publicación exclusiva de bytes y lectura JSON
con el mismo contrato que tenían los helpers de perfiles. Cada consumidor sigue
siendo dueño de su serialización, newline, huella y versión. No se fusionan la
codificación ASCII de snapshots/benchmark, los contratos ni JSON históricos.
Los aliases anteriores de `profiles` conservan identidad. `_physical` reúne la
observación de tablas capturadas y sus metadatos; Verify ya no depende del módulo
privado del migrador para esa tarea. Los aliases de `migration._physical` siguen
apuntando a las mismas funciones.

`tools/check_architecture.py --check` comprueba estas fronteras por AST y puede
escribir el grafo estático observado con `--output archivo-nuevo.json`. En el diagnóstico de
`c4be1c5a` se identificaron siete dependencias entre responsabilidades distintas y dos
consumos internos del migrador que esta extracción redirige al primitivo común. El grafo pasó de 72 a 74 módulos y de 520 a 526
importaciones registradas: se conserva la compatibilidad de aliases, no se
reivindica reducir líneas ni todas las aristas. No había ciclos de imports
sintácticamente directos antes y no se introducen. Persisten seis componentes
cíclicos al incluir imports locales/de tipos; se muestran en el informe en vez
de afirmar que el grafo completo es acíclico. Análisis estático no demuestra
todo comportamiento dinámico. No se dividieron archivos solo por tamaño.
