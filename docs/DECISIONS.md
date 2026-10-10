# Registro de decisiones

Fecha inicial: 2026-09-28. Estado de arquitectura: propuesta concreta para implementación; cambios se registran con ID, motivo, impacto, autor y fecha. La aprobación metodológica requiere evidencia del equipo, no se presume a partir de este documento.

| ID | Decisión | Motivo / consecuencia | Estado |
|---|---|---|---|
| A01 | Monorepo privado `htroya/equiframe` | Colaboración y cambios de contratos revisables; datos/tesis fuera de Git | Repositorio creado |
| A02 | Dos distribuciones de Hernán: `equiframe` y `equiframe-benchmark` | Evitar dependencias experimentales y etiquetas dentro de biblioteca operacional | Diseño propuesto |
| A03 | Paquetes/servicio propios para José y dominio propio para Jhair | Dependencias dirigidas, propiedad explícita e integración por formatos | Diseño propuesto para acordar |
| A04 | Python 3.12, `src/`, tipado, pyproject y extras | Instalación profesional y versiones comprobables; ARM64 requiere prueba | Base implementada; extras se difieren a sus pasos |
| A05 | Contratos estrictos y versionados | Borrador evoluciona sin reglas implícitas ni coerción con pérdida | Implementado en paso 1, esquema 1.0 |
| A06 | R/M/B/H separados de O | Evitar circularidad y fuga de etiquetas | Requisito de tesis |
| A07 | H con tres estados y disponibilidad | Fallo o falta de modelo no equivalen a corrección | Requisito de tesis |
| A08 | Snapshots inmutables y coordinación central de escrituras | Lectura estable y escritores controlados; puede haber espera de cola | Propuesta a José |
| A09 | Comparaciones por contenido completo; hashes para integridad/particionado | No probar igualdad por muestras o hashes exclusivamente | Diseño derivado de tesis |
| A10 | Configuración piloto vs congelación final | No fijar prematuramente alpha/cohorte/precisión/grupos | Requisito de tesis |
| A11 | Implementación íntegra a cargo de Sol en diez pasos | Preparación actual contiene solo diseño y gestión del repositorio | Instrucción expresa de Hernán |
| A12 | `htroya` propietario; invitaciones pendientes de logins | GitHub personal no permite tres propietarios/admin equivalentes | Limitación verificada |
| A13 | Runtime del paso 1: Pydantic, Typer y tzdata; uv 0.11.6 con lock universal | Arrow/motores/ML no se usan todavía; evitar dependencias y extras sin implementación. Runtime/dev/backend separados y fijados por hashes | Ingeniería, Sol, 2026-09-28; implementado |
| A14 | Formato 1.0 y canónico `equiframe-metadata-json-v1` | Defaults/nulls incluidos, objetos ordenados, arrays preservados, UTF-8 sin normalización; Decimal textual y timestamps hasta ns con offset/zona. SHA-256 identifica metadatos, no equivalencia tabular | Ingeniería, Sol, 2026-09-28; implementado |
| A15 | Un único Protocol `ArtifactStore` en paso 1 | `ArtifactRef` está completo; snapshots/observaciones/resultados/features aún no. No introducir `Any`, tipos incompletos ni implementaciones ficticias | Ingeniería, Sol, 2026-09-28; implementado |
| A16 | Seis especificaciones cerradas de reglas y precondiciones | Validar parámetros, referencias y compatibilidad sin ejecutar expresiones ni crear registro operativo. Nuevas formas incompatibles requieren versión de esquema | Ingeniería, Sol, 2026-09-28; implementado |
| A17 | Decimal con precisión 1–76, escala no negativa y comparación exacta; unidad explícita | Capacidad genérica, no escala SERCOP ni garantía por motores. Tolerancias justificadas en integer/float; nunca en decimal exacto | Ingeniería, Sol, 2026-09-28; dominio/escala real pendientes |
| A18 | Coherencia de reglas declarativas sin conversiones implícitas | Joins/grupos preservan unidades; sum/min/max preservan unidad; sum admite ampliación dentro de familia sin reducir dominio y min/max mantienen tipo. OrderCheck usa la política significant completa. Float32 exacto requiere literal representable | Ingeniería, Sol, 2026-09-28; segunda revisión del paso 1 |
| A19 | Zonas IANA exclusivamente desde tzdata bloqueado | La base del sistema puede diferir entre Windows/Ubuntu; cargar recursos del paquete evita que TZPATH cambie la validación. Actualizaciones de tzdata exigen revalidación | Ingeniería, Sol, 2026-09-28; segunda revisión del paso 1 |
| A20 | Decimal canónico independiente del contexto y entrega probada fuera del checkout | Fijar capitals=1 localmente conserva bytes del formato inicial; ejecutar toda la batería contra el wheel instalado desde el sdist, además de API/CLI runtime-only y consumidor tipado | Ingeniería, Sol, 2026-09-28; segunda revisión del paso 1 |

Estas decisiones del paso 1 no cambian requisitos metodológicos del borrador ni cierran cohorte, alpha, revisión humana o cantidades experimentales. La tesis conserva el hash registrado.

## Decisiones que impiden cerrar evaluación, pero no empezar a programar

1. Perfilado y regla de cohorte/fecha de reserva con Jhair.
2. Precisión decimal, claves incompletas, estados y alcance de identificadores.
3. Catálogo y grupos independientes suficientes; revisión del reparto nominal 30/10/20.
4. Alpha tolerable y suficiencia de calibración por familia.
5. Variables/modelos estimables y tratamiento de MAD con soporte degenerado.
6. Revisores asignados, arbitraje y conflicto de autoría con tres integrantes.
7. Protocolo de costos aislado frente a uso concurrente de VM.
8. Licencia de software y condiciones de redistribución del corpus.

## Fuentes técnicas consultadas

- [Concurrencia DuckDB](https://duckdb.org/docs/current/connect/concurrency): modo embebido y alternativas remotas; comprobar versión elegida por José.
- [Permisos de repositorio personal GitHub](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository): propietario y colaboradores.
- [IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html): puntuación y parámetros.
- [Guía pyproject](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/): declaración de distribuciones y dependencias.
- [Contexto Decimal de Python 3.12](https://docs.python.org/3.12/library/decimal.html): capitalización de exponentes y contexto local, comprobados por propiedades.
- [ZoneInfo de Python 3.12](https://docs.python.org/3.12/library/zoneinfo.html): precedencia de TZPATH y carga desde archivo; prueba aislada con base del host alterada.

La consulta técnica no sustituye la prueba contra las versiones que Sol seleccione y bloquee.


## Decisiones del paso 2 — producto 0.2, Sol, 2026-09-28

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A21 | Biblioteca de propósito general, API ef y distribución pública en paso 10 | Pedido nuevo de Hernán, separado del texto científico; base útil, extras y contratos sin SERCOP/OCI/VM. Mantiene diez pasos e independencia experimental |
| A22 | `execute` limita orquestación a ejecución/captura | Tipos completos y DI ahora; reglas/precondiciones operativas, comparación/perfiles/modelos esperan sus pasos. completed no acredita semántica |
| A23 | Arrow IPC file como captura y Arrow/Parquet locales de entrada | Máscaras/NaN/decimal/épocas temporales, esquema físico separado; rechazo previo de objetos/exponentes/signed decimal zero/zoned ns DuckDB no representables. No reconstruye pérdidas anteriores |
| A24 | Registro explícito por instancia y SQL confiable parametrizado | No evalúa contrato JSON, no globals; callbacks propios por motor. DuckDB solo conexión :memory: local con acceso externo/descargas/spill deshabilitados y cierre verificable |
| A25 | Controles cooperativos; interrupción nativa de consulta DuckDB | Sin sandbox ni promesa de timeout duro para callbacks/collect; checkpoint de filas/buffers y memoria/hilos propios del motor no equivalen a RSS o cuotas remotas. Monitores se unen antes de cerrar |
| A26 | Extras y wheel fuera del checkout, CI para PR dependientes | arrow/pandas/polars/duckdb/engines instalados y probados; import ligero; base del PR es step-01 mientras #11 siga abierto. Formato contrato/ArtifactRef 1.0 intacto; API 0.2 con changelog/lock |

El paso 2 no publica en PyPI, no integra PR ni cambia carpetas de José/Jhair.
Los proveedores temporales reales se registran: contrato tzdata Python, entrada
Pandas tzinfo, Polars chrono-tz del runtime, DuckDB ICU del wheel. No se atribuye una
versión IANA común o expuesta sin evidencia. Los enlaces técnicos del README apoyan
las limitaciones; pruebas contra el lock fijan el comportamiento de esta entrega.


## Decisiones de revisión 0.2.1 — 2026-09-28

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A27 | Preservar anchos/máscaras y rechazar inferencia ambigua Pandas | NumPy uint64 extremo/nullable y categorías revelaron pérdida o rechazo incorrecto; tipos mezclados se rechazan antes de inferir |
| A28 | Rechazar capacidades temporales/decimales no fieles | Decimal256 de baja precisión provoca pánico Polars; segundos pueden desbordar; DuckDB usa sentinels de infinito y microsegundos zoned. Diagnóstico explícito conserva la entrada |
| A29 | Retener evidencia parcialmente publicada en estado fallido | El índice puede fallar tras publicar datos; se conserva la referencia y la incompletitud, sin anunciar completed. Presupuesto incluye índice y descarga limpia temporales |
| A30 | Validar puertos runtime y coherencia estructural del manifiesto | Fuentes/adaptadores externos deben respetar tipos; huella, entradas/conteos/formato/salida incoherentes se rechazan sin ajustar observaciones al contrato |
| A31 | DuckDB mínimo 1.5.6 y CI en cinco plataformas | El rango anterior incluía API no disponible; lock comprobado. Matriz añade macOS x64/ARM64 y Ubuntu ARM64, para todas las ramas. Los checks prueban código, no despliegan OCI |
| A32 | Conexión al DW alojada en OCI, integración externa al núcleo | Pedido del usuario: programa de conexión y base en la VM. EquiFrame puede ejecutarse allí o consumir snapshots; servicio real y contratos de dominio siguen siendo dependencias del paso 9 |

A27–A31 corrigen ingeniería y pruebas; A32 explicita la ubicación de la integración.
No cambian el experimento, R/M/B/H/O ni el documento DOCX.

## Paso 3 — ingeniería, Sol, 2026-09-30

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A33 | Paquete 0.3.0, documentos de comparación 1.0 independientes | `ComparisonSpec` incorpora Contract 1.0 intacto y permisos nuevos; conserva huella antigua y registra huella compuesta. Sin cambio silencioso de significado ni migración de formatos existentes |
| A34 | Orden de columnas significativo, tipos físicos exactos e índice rechazado por defecto | El contrato anterior no autoriza ignorarlos. `ComparisonPolicy` permite relajaciones explícitas justificadas; índices con significado deben ser columnas |
| A35 | Todas las claves se comprueban antes/después de normalizar; primera única utilizable | Ámbitos por columnas entran en la clave; incompletas permitidas quedan en multiconjunto. No alineación aproximada, no deduplicación; distinct exige unicidad de filas |
| A36 | Orden significativo es secuencia y validación del orden | Empates preserve conservan posición relativa; reject exige desempate. Esquema observado permanece separado y dos salidas inválidas no producen equivalent |
| A37 | Aritmética racional exacta y tolerancia simétrica predeclarada | Sin float intermedio para decimales/enteros/tiempo, sin redondeo correctivo. NaN es categoría propia o ausencia autorizada. Matching máximo conserva multiplicidad sin asumir transitividad |
| A38 | Lotes, SQLite privado y partición por valores exactos | Hash distribuye, BLOB completo decide; spill incluso para tablas pequeñas. Presupuestos cooperativos de trabajo/disco/representaciones y límites explícitos de grupos aproximados; no cuotas RSS ni reloj duro |
| A39 | Evidencia completa JSONL y snapshots, resumen acotado | Conteos parciales se etiquetan; límites/cancelación fallan como not_evaluable. Esperado inválido tiene diagnóstico separado; comparación completa no equivale a oráculo científico |
| A40 | Reloj controlado para timeout y verificación externa desde este incremento | La prueba de 50 ms mezclaba timeout previo y durante callback. Se prueban ambos sin sleeps arbitrarios. Base/extras/wheel/sdist y cinco plataformas conservan sus controles |

La [especificación normativa de comparación](COMPARISON.md) documenta fórmula,
mapa de tipos, índices, tiempo, capacidades y alcance `output_schema`. Estas
decisiones precisan ingeniería; no congelan políticas SERCOP, experimentos ni O.

## Paso 4 — ingeniería, Sol, 2026-09-30

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A41 | Corregir validación `equivalent` del paso 3 | La coherencia estructural exige recorrido completo, cero diferencias/diagnósticos y `matched_rows == left_rows == right_rows`, incluso al releer JSON; las referencias JSONL se verifican aparte |
| A42 | R recibe una captura y usa registro explícito | `RuleContext` expone solo contrato y tablas verificadas de una ejecución. Los seis evaluadores no invocan el ETL ni `compare`; código y configuración entran en huella |
| A43 | Precondiciones y cuatro estados por chequeo | Falso verificable habilita `not_applicable`; falta de evidencia/capacidad/implementación produce `not_evaluable`. Alerta observada persiste ante incompletitud; conjunto vacío no da `no_alert` |
| A44 | `required` mide cobertura y `severity` prioridad, nunca ocultan hallazgos | Cualquier incumplimiento alerta; cualquier regla no evaluable impide `no_alert` completo, incluso opcional. Omisiones justificadas y cobertura obligatoria constan en el manifiesto |
| A45 | Semántica de joins, grupos y ausencias fijada para contrato 1.0 | Claves NULL no emparejan; `unmatched=reject` comprueba ambas direcciones; `count` distingue filas y presentes; suma decimal exacta y float requiere tolerancia. No se amplía silenciosamente el contrato |
| A46 | Catálogo técnico suplementario 1.0 | Cinco fixtures previos conservan bytes; catálogo fija huella de contrato, reglas, implementación y opciones antes de variantes finales. No constituye benchmark revisado ni validación del DW |
| A47 | Conversiones fallidas anteriores a la captura no inferibles | SchemaCheck valida observación; una estadística de intentos/conversiones fallidas necesita recibo adicional versionado. Se informa falta de evidencia, no se fabrica un recuento |

Estas decisiones implementan requisitos de tesis sobre R independiente y fijado
antes de prueba final (T06/T10). La tabla de agregación, límites y
reconciliaciones seleccionadas son ingeniería documentada en [R](RULES.md).
No resuelven la cohorte/fecha, revisión humana, alpha, particiones ni
políticas SERCOP pendientes del piloto. El DOCX no se edita.

## Paso 5 — ingeniería, 2026-10-01

Fuente contrastada: mismo SHA-256 del DOCX registrado en trazabilidad; §3.6/Tabla 13.

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A48 | Fórmulas cerradas, orden explícito y huella suplementaria 1.0 | Evita features arbitrarias tomadas de metadatos. Cambiar columnas, orden o políticas invalida compatibilidad; la selección definitiva por familia queda para el piloto |
| A49 | Conservar conteos separados y no imputar errores técnicos | Vacío, cero válido, NULL, NaN y no aplicabilidad no se confunden. Las tasas usan denominadores por columna/etapa; no se normalizan datos para producir un perfil |
| A50 | Recibos de conversión instrumentados ligados a fuente/columna/salida | Materializa A47: sin evidencia de intentos no se deduce una tasa a partir de NULL ni de un cast hipotético. El productor confiable responde por la veracidad/completitud del recibo |
| A51 | Matriz única con medianas congeladas e indicadores para M/B | Ajuste recibe solo selección normal de entrenamiento, registra soporte y hash del manifiesto externo; inferencia jamás recalcula medianas. El núcleo no certifica normalidad ni grupos de procedencia |
| A52 | Retiro documentado o no estimable cuando falta soporte | Por defecto retira la variable de ambos detectores futuros; política estricta puede declarar no estimable. Sin variables útiles no hay matriz. Ready del preprocesador no garantiza un modelo estimable |
| A53 | Perfilado acotado en memoria, sin spill | Compatible con Arrow sin importar motores/ML. Cuenta bytes/filas/trabajo/distintos; no promete cuotas RSS ni tiempo duro. La limitación se medirá al contrastar H3 |
| A54 | Distribución privada 0.5.0 para este despliegue | El paso 5 es biblioteca, no servicio. Se construyen wheel/sdist y se verifica consumo externo; PyPI, licencia final y mediciones científicas permanecen en el paso 10 |

Estas decisiones precisan implementación de T10/T15; no fijan alpha, cohorte,
resultados, etiquetas, grupos ni revisiones humanas. No alteran el DOCX ni
los contratos/catálogos de R del paso 4. Un cambio posterior de fórmulas o
selección experimental exige nueva versión y evaluación explícita.

## Paso 6 — ingeniería y alcance experimental, 2026-10-01

Fuente contrastada: DOCX con el mismo SHA-256, §1.3, §3.3.4, §3.4 y §3.7.

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A55 | Distribución `equiframe-benchmark 0.6.0` sobre núcleo 0.5.0 intacto | Mantener etiquetas/revisiones fuera de la biblioteca general instalable; dependencias en una sola dirección |
| A56 | Esperados manuales y comparación completa no confirman O automáticamente | O necesita dos revisiones, acuerdo con comparación y resolución independiente ante desacuerdo; mutación sin efecto no es divergencia |
| A57 | Paquetes ciegos copiados con nombres neutros y asignación previa | Los nombres originales revelaban motor/mutación. Se incluyen entradas; hashes vinculan revisiones. Identidades/fechas siguen siendo declaraciones, no firmas |
| A58 | Prohibir también autoría de esperado/escenario y árbitro | Criterio conservador de independencia: puede requerir otro revisor cuando tres autores no bastan. El equipo debe resolver disponibilidad, sin autoadjudicación |
| A59 | Componentes transitivos antes de asignar con semilla/pesos explícitos | Dependencias declaradas más igualdad de artefactos; no romper grupos para conseguir 30/10/20. No garantiza balance por familia ni soporte suficiente |
| A60 | Selección normal valida ejecución completa y persiste manifiesto | Corrige el riesgo de aceptar un hash de selección declarado sin comprobar O/splits. Se mantiene la interfaz del paso 5 y la matriz sin metadatos |
| A61 | Piloto pequeño honesto y mutaciones de artefacto explícitas | Cinco escenarios y cuatro grupos no sostienen calibración por familia. Los 35 candidatos, 15 perfiles y revisiones pendientes son ingeniería, no evidencia científica ni 60/300 |
| A62 | Verificar pip por nombre desde wheels y separar publicación Git/PyPI | Se conserva el objetivo público `pip install equiframe`. Licencia, control del nombre y publicación pública siguen pendientes; no se elige licencia unilateralmente |

A55/A57/A60/A62 son decisiones de ingeniería. A56 implementa la revisión
del borrador; A58 endurece independencia y exige resolver la composición real
del equipo. A59 es un algoritmo versionado de piloto, no una aprobación del
reparto final. A61 reduce el alcance observado a lo comprobado y obliga a ampliar
grupos antes del experimento. No cambian objetivos, hipótesis ni DOCX. Cambios
metodológicos finales y apertura de prueba se registrarán en una versión nueva.

## Paso 7 — ingeniería y condiciones experimentales, 2026-10-01

Fuente: mismo SHA-256 del DOCX; §1.3, §3.4.3, §3.6–3.7. Núcleo/benchmark 0.7.0.

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A63 | Separar ajuste, score, calibración e inferencia por familia | Impide reajuste accidental en prueba; reutiliza una matriz/preprocesador para M/B y registra sus huellas |
| A64 | Alpha decimal obligatorio y rango exacto con fracciones | Cumple el cuantil sin interpolación de §3.6, evitando redondeos binarios en `ceil`; 5% sigue sin aprobación experimental |
| A65 | Bosque declarativo JSON y evaluador versionado | Evita cargar objetos ejecutables; inferencia en paquete base, pruebas contra score_samples. No se supone el mismo rendimiento que sklearn; medir costo en 10 |
| A66 | Soporte de filas y auditoría de grupos explícitos | El piloto 5/4/15 y sus 35 revisiones pendientes no acredita entrenamiento. Mínimos técnicos no equivalen a potencia estadística ni garantía de FPR |
| A67 | Selección normal de calibración comparte validación de procedencia de entrenamiento | Rechaza prueba, pendientes y capturas ajenas; auditoría exige mismo catálogo/split y grupos disjuntos. Normalidad/grupos permanecen fuera del vector |
| A68 | MAD cero conserva infinito etiquetado y H conserva alerta parcial | Cumple §3.6/§3.4.3; umbral infinito es no estimable, igualdad no alerta y B nunca interviene en H |
| A69 | Extra ML y distribuciones 0.7.0; publicar código en Git | Biblioteca consumible sin VM; wheel/sdist y pip por nombre verificados. Licencia/control de nombre y publicación PyPI siguen pendientes del paso 10 |

A63/A65/A67/A69 precisan ingeniería. A64/A68 implementan fórmulas del borrador.
A66 conserva una condición metodológica pendiente: ampliar y revisar grupos,
justificar alpha y registrar el FreezeManifest antes de la evaluación final.
La conversión float32 de M se declara; pérdida de variación o rango no se
ocultan mediante normalización. El DOCX, R y los contratos previos no se cambian.

A70 (verificación de distribución): el generador heredado de conjuntos de
dependencias agotó la comprobación de velocidad de Hypothesis en un consumidor
limpio (3 entradas válidas en 1,04 s), sin contraejemplo de partición. Se cambia
a máscaras de bits 1–127: conserva los 127 subconjuntos no vacíos de siete
dependencias y las propiedades de fuga/orden, eliminando rechazo por duplicados.
No se suprimen health checks ni se modifica el algoritmo de particiones.

## A71 — aclaración de producto posterior al paso 7, 2026-10-01

Hernán precisa que `pip install equiframe` significa disponibilidad pública en
PyPI para cualquier persona, no instalar EquiFrame localmente ni en GitHub.
Este objetivo se abordará después de completar el paso 10 y una nueva ronda
de revisión. Sustituye el calendario de publicación propuesto en A21/A62/A69;
no altera las fórmulas, objetivos científicos ni resultados de las pruebas.

Se retiran las instalaciones locales de prueba de EquiFrame por petición de
Hernán. Las verificaciones históricas de empaquetado conservan su valor técnico,
pero no acreditan el objetivo de distribución pública. El código y las pruebas
permanecen versionados; no hubo publicación en PyPI ni despliegue de servicios.

## Paso 8 — orquestación y evidencia, 2026-10-01

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A72 | Runner compuesto sobre captura única con componentes independientes | No reejecuta ETL para medir ni entrena/calibra al inferir; fallos de una etapa no borran evidencia de otras |
| A73 | Completitud de lo solicitado y códigos 0/1/2/3 | Alerta/diferencia completa es 1; fallo/no evaluable prevalece como 3 conservando alertas parciales; R sin detector no se presenta como H evaluable |
| A74 | Journal SHA-256 sincronizado y manifiesto final exclusivo | Relanzar crea UUID; una interrupción sin manifiesto no declara éxito. Integridad local, sin promesa de firma/WORM ni recuperación tras avería de disco |
| A75 | Reportes con campos seleccionados y escape HTML | No incluyen datos, parámetros ni texto de excepciones; los artefactos técnicos completos siguen siendo privados. Autenticación fuera del plan |
| A76 | Reducción por eliminación de filas con predicado versionado y firma específica | Conserva precondiciones, orden, multiplicidad/esquema; presupuestos y repetición explícitos. Solo minimalidad de una fila para predicados deterministas; nunca mínimo global |
| A77 | CLI operacional y experimental separadas, distribuciones 0.8.0 | Núcleo no importa benchmark; el piloto usa la orquestación sin crear etiquetas ni entrenamiento científico |
| A78 | Compatibilidad declarativa de bundles 0.7/0.8 | Se registra versión emisora sin alterar IF/MAD 1.0; se mantienen fórmulas, alpha, R y particiones anteriores |

Son decisiones de ingeniería. No modifican hipótesis, objetivos, DOCX, criterios
humanos del oráculo o decisiones experimentales pendientes. A71 y el calendario
de veinte pasos siguen vigentes. Uso: [orquestación](ORCHESTRATION.md).

## Revisión del paso 8 — ingeniería, 2026-10-02

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A79 | Verificar cierre del inventario y vínculo de cada captura propia | Un manifiesto no puede omitir su tabla y seguir declarando evidencia íntegra. Las fuentes externas conservan procedencia; sus capturas privadas deben permanecer en la corrida |
| A80 | Releer posiciones, confirmaciones y observaciones de reducción sin ejecutar el predicado | Vincula el resultado final con los intentos conservados y con las filas originales; una etiqueta `one_minimal` necesita evidencia de las supresiones individuales restantes. Mantiene formatos 1.0 y límites de autenticidad local |
| A81 | Versión correctiva 0.8.1 y errores de integridad CLI con código 3 | Conserva bundles anteriores y las dependencias fijadas. Corrupción de evidencia es un fallo operativo, distinto de una solicitud inválida |

El DOCX conserva el SHA-256 registrado. Estas correcciones sostienen T09/T11 y
no cambian alpha, features, hipótesis, etiquetas, particiones ni criterios de O.
La [segunda revisión](STEP_08_SECOND_REVIEW.md) distingue los controles técnicos
del cierre científico y de la publicación pública prevista en el paso 19.

## Paso 9 — consumidor y conformidad local, 2026-10-02

Hernán confirmó que no están disponibles cliente/snapshot/DDL y autorizó el
desarrollo de EquiFrame en paralelo. Las dependencias externas permanecen abiertas.

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A82 | Recibo completo fijado una vez y selección explícita de tablas | Consumir un subconjunto no cambia la versión del DW. El consumidor verifica bytes/tipos; el cliente controla transporte/autenticación/timeouts. El esquema de integración necesita adaptación acordada cuando llegue el cliente real |
| A83 | Tres planes compatibles y esperado capturado una sola vez | Mantiene ejecuciones nativas y comparación pareada sobre la misma entrada; impide que un esperado mutable cambie entre motores. Una comparación completa no confirma O |
| A84 | Reconciliación declarativa, decimal exacto y total no evaluable ante importe ausente | No redefine el DW ni normaliza diferencias. La suma entera evita redondeo por contexto Decimal, conserva monedas y muestra importes ausentes; puente con varios proveedores no multiplica la medida |
| A85 | Benchmark 0.9.0 sobre núcleo 0.8.1, integración real pendiente | Aporta código consumidor/CLI y conformidad instalada. No administra el servicio, crea el DW ni certifica OCI. PyPI permanece en 19 |

Precisan ingeniería de T03/T09/T13–T14. No modifican cohorte, alpha, fórmulas,
etiquetas, grupos ni criterios de revisión. Diseño y controles:
[paso 9](STEP_09_DESIGN.md), [verificación](STEP_09_REVIEW.md).

## Edición académica y nombre del componente, 2026-10-02

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A86 | Ampliar los capítulos 2/3 y aplicar APA 7 e índices paginados después del paso 9 | Solicitud explícita de Hernán. Word guardado y revisado: 125 páginas, 15 figuras, 17 tablas, 61 referencias y 107 destinos. Conserva A4 y la portada del TFM como adaptaciones del formato original; no acredita resultados ni cambia el contenido pendiente de 4/5 |
| A87 | Nombre de producto EquiFrame Verify para la validación independiente O | Solicitud de un nombre acorde al producto. Cambia presentación, sección e imagen; conserva O, comparación completa, esperado independiente y revisión humana. Los títulos bibliográficos auténticos y los identificadores anteriores de API mantienen su significado |
| A88 | Actions sin ejecuciones automáticas durante la cuota agotada | Workflow remoto desactivado manualmente antes de subir cambios; YAML conserva solo ejecución manual explícita. La validación local se registra aparte y no se presenta como nueva prueba remota en ARM64/macOS |

La tesis entregada conserva SHA-256 `45aaccd3d66da222389b1d153dca5fa23e5eef9cd0ec75c15c3d797ab955cbe1`.
[Detalle de fuentes, formato, límites y verificación](THESIS_UPDATE_20261002.md).
El paso 10 se inicia después de esa entrega. Hernán solicita una nueva revisión
con el modelo institucional y las observaciones del anteproyecto al terminarlo;
se guardará aparte como `tesis_final.docx`.

## Paso 10 — implementación técnica, 2026-10-03 UTC

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A89 | Separar sello técnico de piloto y sello científico final | El primero conserva decisiones/revisiones pendientes; el segundo se bloquea ante cualquier requisito no resuelto. Reauditar fuentes, modelos y alcance antes/después evita ejecutar una configuración incompatible o mantener un informe final si cambian fuentes |
| A90 | Comparación principal sobre O confirmado y R/M/B/H completos | Mantiene denominadores pareados de §3.8. Soporte propio y alertas parciales se publican aparte; F1 se calcula directamente con conteos y valores indefinidos conservan motivos |
| A91 | AP con empates y scores homogéneos; bootstrap de grupos completos | Evita mezclar escalas entre familias/modelos e independencia ficticia entre variantes. Estima métricas agregadas de ejecuciones, fija ordinales ceil sin interpolación y no publica intervalos cuando existen réplicas indefinidas. Parámetros y soporte requieren justificación previa |
| A92 | Inferencia de componente aislado y costes sobre capturas previas | Núcleo 0.9.0 añade API sin puntuar MAD al medir M. Un warmup y cinco pares alternados; CPU de proceso con sampler, RSS absoluto muestreado y medidas fallidas explícitas. No atribuye ETL inicial ni cuota dura de memoria a H3 |
| A93 | Reutilizar O solo tras verificar entrada, implementación y salida revisada | El registro del estudio conserva cada caso, incluso fallido. Una salida nueva diferente no hereda una etiqueta del candidato antiguo. No aprende modelos ni umbrales con test |
| A94 | Bundle portable de bytes originales y tablas regeneradas | Conserva decimales/monedas y hashes de padres; cambia URI solo con vínculo explícito. La reproducción de tablas desde capturas no acredita una nueva ETL ni aprobación humana. La repetición auténtica por otro integrante sigue pendiente |
| A95 | Inventario público separado de publicación y matriz | Licencia, control de nombres y nuevas plataformas requieren evidencia externa. El lector no reserva/publica ni confunde 404 con propiedad; build/instalación temporal solo verifican software. Actions permanece desactivado por A88 |

Precisiones de ingeniería de T09/T11/T15–T18 y OE3/OE4/OE5. No se resuelven por
código la cohorte SERCOP, revisión humana, licencia, soporte científico o H1–H3.
La tesis previa permanece protegida; el documento institucional posterior recogerá
la implementación real y las limitaciones. [Diseño](STEP_10_DESIGN.md),
[métodos](STEP_10_EVALUATION.md), [distribución](STEP_10_DISTRIBUTION.md).

## Adaptación institucional posterior al paso 10 — 2026-10-03 UTC

Fuente: observaciones completas del anteproyecto, modelo institucional y
petición de Hernán de entregar solo capítulos 1–3. El documento anterior se
conserva; la versión posterior tiene un hash propio y no altera el código.

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A96 | Acotar el experimento a Pandas–DuckDB y tres familias: ausencias/tipos, uniones y agregaciones | Responder a viabilidad y problema científico de las observaciones. Polars y cinco familias permanecen capacidades técnicas; objetivos, figura 4, figura 5, texto y tablas distinguen ambos alcances. La evaluación real, selección de variables y composición de manifiestos deben corresponder al nuevo protocolo antes del freeze; no se presentan los ejemplos de cinco familias como el experimento acotado |
| A97 | Entregar solo capítulos 1–3 y referencias, con estructura previa institucional y APA 7 | Instrucción explícita de Hernán prevalece sobre los cinco capítulos y estilos mezclados del modelo. Retirar entradas y remisiones a 4/5; conservar portada, 15 figuras, 17 tablas y 61 referencias. Formularios sin firmas, tutor pendiente y paginación continua; ningún formato acredita aceptación institucional |
| A98 | Exigir inventario de más de 10.000 adjudicaciones originales y dejar cuotas de escenarios por fijar | Observaciones del anteproyecto, sin corpus disponible. Identificar por `ocid` y `award.id`, registrar versiones y exclusiones; registros, perfiles y grupos independientes son unidades distintas. Las antiguas metas 60/300 y reparto 30/10/20 dejan de ser cuotas de la tesis vigente. No fijar tamaños ni calibración por conveniencia antes de observar soporte real |
| A99 | Entrega separada por copia exacta tras cierre estructural y visual completo | 130 páginas; 97 destinos; 62 PNG nuevos inspeccionados y 68 reutilizados solo por bytes idénticos a inspecciones previas. Dos controles estructurales y fuentes originales intactas. Respaldo privado duradero; Word/PDF/datos no se suben a Git ni se usan Actions |

A96/A98 son revisiones metodológicas pendientes de revisión académica y
evidencia real; no confirman hipótesis ni revisiones humanas. A97/A99 registran
la edición y entrega autorizadas. El paso 10 técnico ya está integrado por
PR 20 y la publicación PyPI continúa fuera de esta entrega.

Documento final SHA-256:
`ff638dff604fbe30179fa463b5e3c9440028f23fec0f114c55d4eac8f63246a2`.
[Cambios, fuentes, comprobación y límites](THESIS_FINAL_REVIEW_20261003.md).

## Corrección conforme a instrucciones de Hernán — 2026-10-03 UTC

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A100 | Las tres parejas Pandas–Polars, Pandas–DuckDB y Polars–DuckDB son principales; tres familias y nueve estratos | Instrucción expresa del usuario. Sustituye A96; catálogo y partición global comparten identidades reales, sin sumar reutilizaciones ni mezclar scores incompatibles |
| A101 | El umbral superior a 10.000 corresponde a los registros reales de la matriz efectiva de aprendizaje | Corrige A98 conforme al texto literal del tutor. Adjudicaciones fuente y cantidad de perfiles/grupos son unidades distintas. Informar N por modelo/familia no atribuye al PDF un mínimo literal por familia; requisito empírico pendiente |
| A102 | Word final de 132 páginas, solo 1–3, 15 figuras, 17 tablas, 61 referencias y 97 destinos | Actualiza A99. Gate estructural, contraste de 13 recomendaciones y revisión visual completa; respaldo de la versión anterior y fuentes intactas. Tutor, datos, ajuste y revisiones independientes no se dan por cumplidos |

La [revisión actual](THESIS_TUTOR_REVIEW_20261003.md) sustituye el alcance y la
interpretación del mínimo del informe anterior, conservado como historia. El
Word nuevo tiene SHA-256
`4e2f571ceb16d98b16f1d74e5f66803e0268baa607f9ee589adf6e29d11854c8`.

Antes del paso 11 se registra el [plan del migrador](MIGRATION_DESIGN.md), solicitado
por Hernán. Su implementación no adelanta el cierre científico ni PyPI.

## Migración integrada anterior al paso 11 — 2026-10-03 UTC

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A103 | EquiFrame Migrate pertenece al núcleo 0.10.0; benchmark 0.10.1 fija esa dependencia | Una biblioteca genérica puede declarar ETL, compilarla nativamente y comparar sus resultados sin el DW. IR cerrado y registro explícito permiten extensiones confiables, sin cargar código desde JSON |
| A104 | Captura única aislada para ambos motores y esperado opcional fijado antes de ETL | Comparar salidas no prueba corrección independiente; verificar contra un esperado aportado tampoco autentica su revisión humana. El esperado permanece fuera de perfiles y detectores |
| A105 | R requerida por defecto, alternativa explícita `require_rules=False` | Permite exigir migración/comparación sin ocultar los estados originales de R/H; ejecución y componentes solicitados deben finalizar y las alertas disponibles conservan su efecto |
| A106 | Manifiesto final, inventario cerrado y validación física sin reejecución | Conserva fallos y evidencia parcial; hashes, URI locales, metadatos, eventos y conteos deben concordar. Las URI del migrador no constituyen un bundle portátil ni una firma de autoría |
| A107 | Capacidades iniciales acotadas y presupuestos cooperativos | Rechazo explícito de pérdidas/overflow/índice no representable; límites de captura tras materialización y cota Polars conservadora. Registrar motores no acredita una traducción universal |

[Guía](MIGRATION.md), [plan previo](MIGRATION_DESIGN.md) y
[comprobaciones y límites](MIGRATION_REVIEW.md). Las ampliaciones compatibles
de `DetectorVersions` mantienen formatos 1.0 y productores previos; no modifican
los algoritmos ni el protocolo científico. No se inicia el paso 11 ni PyPI.

## Refuerzo autorizado durante la reorientación documental — 2026-10-03

La nueva instrucción del autor autoriza mejorar la biblioteca y subir el cambio
revisable a Git en paralelo con la entrega de capítulos 1–2. No autoriza PyPI ni
despliegues. El cambio ajeno presente en `HERNAN_ROADMAP.md` permanece intacto.

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A108 | Distinguir en reportes comparación con esperado de EquiFrame Verify (O) | El HTML anterior decía «Independent verification» sin recoger autoría/revisión humana. Se conserva la clave histórica de API y se añade el estado explícito `not_established`, con cada comparación y su evidencia por separado. El lector acepta formatos históricos completos para preservar expedientes; integridad y corrección siguen siendo diferentes. No modifica etiquetas ni algoritmo R/M/B/H. |
| A109 | Contrastar las seis direcciones con semántica de las tres familias y esperados literales | Las pruebas invocan ambos adaptadores reales, conservan NULL/NaN, ocurrencias many-to-many y claves, y separan montos Decimal por moneda. Las seis direcciones son capacidad técnica; el protocolo científico sigue declarando origen y destino de cada ensayo y no hereda validez bidireccional de los tests sintéticos. |
| A110 | Entrega documental actual de capítulos 1–2 y anexos preparatorios | La instrucción actual sustituye el alcance editorial previo de A97/A102 para esta entrega parcial, sin afirmar aceptación del tutor. El requisito superior a 10.000 se refiere a filas reales utilizadas en aprendizaje; interpretación por modelo, corpus, grupos, calibración, etiquetas y revisión humana permanecen pendientes. El plan nuevo distingue soporte H–R del soporte común R/M/B/H y presupone revisión antes de entrenamiento/calibración. |

## Verify reutilizable y ETL local — 2026-10-03

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A111 | Verify operacional en core, O opcional y puente benchmark | Artefactos externos sin rehacer ETL; acuerdo, esperado, R e independencia separados. Los nombres declarados no autentican revisores. APIs oracle históricas se preservan. |
| A112 | Ingestión y grano explícitos, IR nativo acotado y checkpoints | IDs/money/ausencias se conservan o se rechazan con recibos; no inferir esquemas aprobados ni traducir programas arbitrarios. Matriz trazable con rechazos deliberados. |
| A113 | Carga Parquet local con gate releído, staging, versiones y puntero | Utilidad ETL sin DW/OCI; idempotencia y conservación, atomicidad de visibilidad local sin prometer durabilidad eléctrica/transacción distribuida. Resume rechazado. |
| A114 | Evidencia portátil sin reescribir formatos históricos | Inventario/hash/tamaño y resolver limitado a capturas; lectura reconstruye vínculos/estados sin ejecutar motores ni callbacks. Hash no equivale a autenticidad. |
| A115 | Candidato 0.11.0, Python 3.12, CI manual y publicación separada | Twine, builds/instalaciones limpias y manifest; no ampliar plataformas por configuración. Licencia, titularidad, acceso público y publicación son decisiones pendientes. |
| A116 | Validación SERCOP de subconjunto manual identificado | Tres paquetes/dos awards, grano (ocid,award_id), puentes sin monto y monedas separadas; seis direcciones técnicas. No corpus, O humano, DW ni entrenamiento real. |
| A117 | JSON vacío inválido y límites timestamp comprobados por registro | La pasada extra reprodujo éxito ficticio de JSON vacío y overflow fuera de cuarentena. Un `[]` declarado o stream JSONL vacío conserva tabla vacía válida; ticks int64 extremos exactos se aceptan y desbordamientos siguen rechazo/cuarentena. Es corrección de ingeniería sin cambio experimental. |
| A118 | Nombres de publicación inequívocos sin distinguir mayúsculas | Windows podía sobrescribir `Table.parquet` con `table.parquet` y devolver éxito. API/recibo rechazan estas colisiones antes de escribir; la versión previa se conserva. No se normalizan ni fusionan datos y no cambia el protocolo científico. |

Se revisó el cambio preexistente del roadmap y se preservó su planificación
11–20, conciliando descripciones vigentes con evidencia. No modifica el diseño
experimental de tres parejas/tres familias/nueve estratos ni transforma filas
fuente/fixtures/reutilizaciones en registros efectivos de aprendizaje.

## Revisión integral conforme a la última tesis y guía del equipo — 2026-10-03

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A119 | Candidato núcleo/benchmark 0.11.1, con la misma resolución de dependencias | Identifica los fixes y la API descriptiva adicional sin reemplazar artefactos 0.11.0. DetectorVersions conserva productores anteriores; formatos históricos 1.0 no se reescriben. |
| A120 | Aislar operaciones exactas del contexto decimal del consumidor | Traps, rango de exponentes y flags externos podían cambiar ingestión, IR, ejecución y R. Contexto propio y validación de escala/rango preservan valores y no autorizan pérdida de precisión. R conserva precisión 1000; cambia la huella de su implementación y se regenera el catálogo. Estudios congelados con la huella anterior conservan su revisión; usar R corregida requiere nueva evidencia/congelación. |
| A121 | Presupuestos y cancelación durante expansión JSON; exponentes inválidos explícitos | La colección expandida podía crecer antes del control max_records. Se aplica presupuesto restante antes de convertir escalares y se conserva rechazo/cuarentena para exponentes fuera de rango. Parseo sigue materializado, acotado por bytes y controles cooperativos. |
| A122 | Contrastar evidencia física con conteos y clasificación declarada | Reproducción portátil, selección normal y puente Verify rechazan contradicciones de conteos o tipo de candidato. Se usan opciones congeladas y referencia peer, sin modificar etiquetas válidas ni fabricar revisiones. |
| A123 | Reporte pareado aditivo y descriptivo, separado del protocolo histórico | La tesis vigente distingue soportes por contraste de intersección común. evaluate_pairwise conserva el EvaluationReport y seis CSV, añade seis pares R/M/B/H y scientific=false. Su uso principal requiere protocolo nuevo revisado/congelado antes de la prueba; no se reinterpretan resultados ni cambia bootstrap/AP. |
| A124 | Vincular controles a fuente y artefactos del candidato | Huellas antes/después y wheels de dependencias locales evitan aprobar bytes nuevos con recibos antiguos; se exige limpieza del cierre de fuentes al emitir manifest. Listas condicionales de uv.sources se rechazan explícitamente por no estar soportadas. Vinculación no autentica ejecutores ni sustituye aprobación de licencia/publicación. |
| A125 | Preservar las guías y responsabilidades comunicadas, incluida flexibilidad de VM | Tesis y guías se mantienen idénticas en hash. El Word de José permite OCI o alternativas AWS/Azure/Hetzner; se aclara esa flexibilidad sin elegir/desplegar proveedor, construir su gateway o redefinir el DW de Jhair. |
| A126 | Aplicar max_records también al registrar errores de parser | La revisión cruzada confirmó exceso tras una fila válida seguida de CSV mal formado, y casos con presupuesto cero. Se comprueba límite antes de añadir cuarentena; se preservan errores dentro del presupuesto. Se interrumpen y repiten controles finales para vincular evidencia a la corrección. |

## Saneamiento operativo STEP1 — 2026-10-04

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A127 | Poner en cuarentena el auxiliar `equiframe.benchmark` del núcleo | El borrador mezclaba métricas de relleno, conteos como divergencia y ajuste/calibración compartidos. Se retira su ejecución y se conservan siete nombres únicamente como guards que fallan explícitamente; CLI/ejemplo salen 2 salvo ayuda. La distribución separada `equiframe-benchmark` conserva su API, particiones, R/M/B/H/O y gates, sin convertirse en reemplazo directo. No se reinterpreta ninguna salida previa como evidencia científica. [Disposición y pruebas](STEP1_BACKLOG.md). |
| A128 | Aceptar en CLI únicamente equivalencia completa | `invalid_expected` puede tener recorrido completo y debe salir 3, nunca 0. Se preservan los estados del núcleo y los hechos parciales; no se crea un combinador de resultados. [Contrato y tabla ejecutable](STEP1_SEMANTIC_RFC.md). |

Ambas decisiones son correcciones de ingeniería del candidato privado 0.11.1;
no cambian el protocolo experimental, sus etiquetas ni sus resultados. La
[ficha](STEP1_CANDIDATE.md) mantiene separadas fuente, ejecución, artefactos y
decisiones humanas/legales pendientes.

## Entrada breve STEP2 — 2026-10-05

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A129 | Añadir `diff` como fachada del mismo comparador | DataFrames eager pandas/Polars y tablas Arrow se capturan fielmente antes de usar el núcleo vigente. La derecha es esperado por defecto; `compare` mantiene su default peer. Se conservan estados, diagnósticos, matching máximo y fallback de claves. [API](DIFF.md). |
| A130 | Añadir constructores tipados y procedencia separada 1.0 | `DiffContract` contiene el `ComparisonSpec` existente y el origen de cada campo hoja. `read_diff_contract(result)` descubre su compañero y verifica vínculo con comparación/spec/referencia; no cambia el formato anterior ni constituye firma o aprobación humana. |
| A131 | Inferir solo de metadatos de la referencia con defaults visibles | No se leen diferencias del candidato para relajar el contrato. Nulabilidad permanece abierta; exactitud numérica usa escala sin interpretación `unspecified`, sin adivinar unidad de negocio. Tolerancia/unidades y restricciones se declaran explícitamente. Las claves nunca se infieren. |
| A132 | Rechazar materialización lazy y semántica no representable en la fachada inicial | No se ejecuta SQL/relación DuckDB ni plan Polars por pasar un objeto a `diff`. Categorías, metadatos sin política y tipos no fieles fallan explícitamente. Se mantiene la ruta previa de snapshots/ejecuciones materializadas con contrato. Captura y comparación tienen límites cooperativos separados. |
| A133 | Mantener STEP2 independiente de presentaciones y aserciones futuras | El retorno es el `ComparisonResult` vigente. No se introducen HTML, redacción, assertion helpers, publicación, cambios de licencia ni ampliación de versiones. Los ejemplos se verifican mediante consumidores de wheel y los dos paquetes repiten sus gates del candidato. |

Estas decisiones son de API y captura; no cambian el protocolo experimental,
las etiquetas, los detectores ni los requisitos de revisión científica.

## Reporte común STEP3 — 2026-10-05

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A134 | Añadir una vista `ComparisonReport` 1.0 separada | JSON/texto/HTML/notebook consumen un modelo filtrado sin IO de fuentes. El juicio, el comparador y los formatos previos no cambian. [API](REPORTS.md). |
| A135 | Separar divulgación, evaluación y aceptación de evidencia | Valores/nombres/rutas se ocultan por defecto. Límites de ejemplos no reducen el recorrido; evidencia exhaustiva insuficiente tiene requisito insatisfecho independiente del juicio. |
| A136 | Verificar diferencias solo bajo una raíz explícita y presupuestos | Manifiesto, tamaño, hash, estructura y alineación registrada se comprueban sin abrir orígenes. Corrupción falla explícitamente; un hash no autentica al productor. |
| A137 | Limitar reproducción a capturas materializadas con contexto suficiente | Exportación explícita incluye entradas, índices admitidos, spec, opciones y versiones; rechaza comparaciones incompletas y ExecutionResult. No promete reproducir transformaciones o servicios. |
| A138 | Conservar la retención previa y publicar vistas de mínimo acceso | No se borran ni debilitan snapshots/diferencias existentes. Reportes nuevos piden directorios/archivos privados, no cifrado ni ACL remota. Publicación fallida no se considera éxito; HTML mantiene escape/CSP sin scripts. |

Son decisiones operativas de presentación y evidencia, sin cambios del protocolo
experimental, etiquetas, detectores o requisitos de revisión científica.


## Aserciones e integración STEP4 — 2026-10-05

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A139 | Gate explícito sobre `ComparisonResult` | Solo equivalencia completa y consistente; garantía observada del contrato, sin afirmar corrección del negocio o equivalencia universal. Política puede fijar hashes y referencia. |
| A140 | Persistencia exigida de forma explícita y acotada | Política y raíz autorizada se exigen juntas; se reutiliza la inspección del manifiesto/diferencias, sin IO por defecto ni lectura implícita de fuentes. Integridad no autentica origen. |
| A141 | Rechazar truth testing de resultados | Cambio observable deliberado: `__bool__` lanza `TypeError` en todos los estados. Migración a aserción, `.accepted` o comprobación explícita de campos/ausencia. Formatos previos intactos. |
| A142 | Compartir aceptación y separar diagnósticos de máquina | Errores tipados, decisión versionada y CLI con códigos existentes; JSON stdout y mensajes redactados stderr. No se crea otra CLI. |
| A143 | Integración pytest sin plugin, artefactos con lista cerrada | Guardar reporte redactado antes de fallar, capturas privadas aparte y upload `always()`. La demostración local y CI remota se declaran por separado; no se modifican permisos/workflows. |

Son decisiones operativas de API y aceptación de resultados. No modifican
protocolo experimental, detectores, etiquetas ni requisitos científicos.

## Primer uso y recetas STEP5 — 2026-10-05

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A144 | Entregar un kit privado autocontenido de tres recetas sobre wheel exacto | Instalación limpia, pins y hashes del lock, inventario cerrado y ejecución fuera del checkout. Los datos son sintéticos y no se descargan implícitamente; no se publica el nombre en PyPI. |
| A145 | Usar migración nativa existente y conservar esperado separado | El IR acotado ejecuta pandas y DuckDB de forma real con Decimal, NULL y multiplicidad. Un error compartido conserva acuerdo entre motores y falla frente al esperado; no se simula un traductor arbitrario ni se amplía semántica. |
| A146 | Separar consumidor técnico y aceptación humana | Pruebas instaladas y revisión independiente automatizada verifican comportamiento; cinco minutos sigue siendo meta sin validar. Se entrega un protocolo/formulario pendiente para tiempo, ayuda, errores, plataforma y comprensión, sin fabricar observaciones. |

Son decisiones de documentación, consumo y verificación operativa. No alteran
protocolo experimental, etiquetas, detectores, interfaces públicas, soporte
Python, publicación ni responsabilidades del servicio/DW.


## STEP6 — Compatibilidad observada y formatos (2026-10-05)

Decisión de ingeniería, sin cambio metodológico de la tesis: distinguir la
admisión por metadata de soporte observado del candidato y clasificar todas las
superficies públicas. Las API estables requieren aviso durante dos minor releases
y 90 días (ambos) antes de retirada incompatible, salvo rechazo inmediato para
seguridad/integridad/falsa equivalencia. Los formatos no se reinterpretan ni se
actualizan implícitamente; los productores experimentales conservan compromiso
de lectura de versiones históricas según la política.

La matriz de extremos inferiores directos encontró pérdida de cardinalidad en
Arrow → Polars 1.30 para tablas con filas y cero columnas. Se verifican dimensiones
antes del callback y al capturar la salida; una pérdida es CapabilityError, nunca
salida completed. No se inventan filas ni se reconstruyen tipos perdidos.
Un test de ML dependía del umbral interno de splitting de sklearn; se verifica
paridad con el modelo nativo instalado y rechazo de un bosque real sin splits.
Los algoritmos, preprocesamiento, calibración, reglas, H y O no se cambian.

Se evalúa Python 3.13 mediante el mismo wheel, además de 3.12. La matriz STEP6
registra pruebas efectivas y deja Windows/macOS/ARM64 y otras implementaciones
sin verificar cuando no hay ejecutores. Los locks añaden artefactos para 3.13
sin cambiar versiones resueltas. El corpus histórico identifica commits privados,
no releases públicos ficticios. La hoja de ruta reforzada se conserva fuera de Git.


## STEP7 — Captura DuckDB y fidelidad de transporte (2026-10-06)

Decisión de ingeniería: priorizar un bloqueo reproducible de integración, la
captura explícita de una consulta y su consumo una sola vez, en lugar de ampliar
operadores del IR sin demanda ni ocultar pérdidas. La comparación sigue siendo
independiente del motor. `capture_duckdb` crea un `TableArtifact` desprendido por
lotes, con propiedad privada o prestada exclusiva, intervalo de captura, tipos
nativos y lista cerrada de ajustes de sesión. No conserva SQL ni parámetros.
La captura no acredita versión externa de datos ni transacción distribuida.

DuckDB 1.5.6 convierte UHUGEINT máximo en Arrow decimal128 de valor -1, y la
validación Arrow pasa. También UUID pierde su identidad en string. Se adopta
admisión cerrada de tipos antes del transporte tanto en la nueva API como en
`DuckDBAdapter`, con validación exacta de esquema posterior y rechazo de
sentinels temporales. No comparar dos transportes corruptos como esperado.
La revisión independiente detectó además que parámetros Python Decimal como
`1E-38` o `0.01234567890123456789012345678901234567` se inferían como DOUBLE.
Ambas rutas enlazan Decimal mediante `duckdb.Value` y `decimal_type` sobre texto
exacto de valor/escala; no pasan por float ni modifican el SQL del consumidor.
Se rechazan exponentes positivos, cero negativo, precisión/escala >38 y enteros
fuera de 64 bits signed/unsigned antes de ejecutar la consulta del consumidor.
HUGEINT/UHUGEINT quedan fuera aun si un valor individual cabría; recuperación
mediante cast explícito del consumidor con rango/semántica justificados.

La conexión prestada no se reconfigura ni se cierra y debe declarar exclusividad,
sin lectores pendientes ni SQL concurrente. Las extensiones automáticas deben
estar desactivadas antes de entrar. Los controles cooperativos pueden interrumpir
la conexión y un fallo nativo puede abortar su transacción. No existe sandbox
SQL, cuota RSS dura, captura global simultánea o admisión de tipos anidados.

No hay cambios metodológicos, detectores, etiquetas, protocolos experimentales,
servicio/DW de terceros, publicación PyPI ni interpretación de evidencia histórica.

La revisión del candidato encontró un segundo límite: Arrow puede envolver
fallos nativos tardíos como `OSError`, fuera de la jerarquía `duckdb.Error`.
Se normalizan exclusivamente al consumir el lector, comprobando primero
cancelación/deadline, sin exponer SQL/literales en el diagnóstico público.
La causa encadenada se conserva para depuración privada. Un fallo de escritura
o fsync sigue siendo I/O; no se atribuye al motor. El corpus incluye el cast
nativo tardío real, las variantes envueltas y la limpieza atómica.

## STEP8 engineering decision (2026-10-06): bounded costs without semantic weakening

The engineering adoption roadmap's resource step is implemented by extending the
existing benchmark distribution with a separate exact-comparison scale protocol.
The scientific paired `CostProtocol`, R/M/B/H, oracle, frozen studies and thesis
methodology remain unchanged. New synthetic fixtures are engineering evidence.

The optimization selected after a baseline replaces redundant Path/stat work
with same-frequency scandir disk accounting, retaining exceptional filesystem
semantics. Deferred representative decoding was measured diagnostically but not
adopted in this candidate. Exact grouping and every checkpoint remain intact.

Stage boundaries explicitly retain the inclusive public comparison cost. RSS and
directory budgets are sampled reactive termination, not hard quotas; unsupported
child processes and incomplete finalization fail closed. A separate monitoring
quality field prevents successful verdicts from concealing absent measurements.
No unsupported platform, public release, human adoption or external-service load
is implied. [Protocol](SCALING.md); measured candidate results are reported with
exact artifact identities and their known limitations.

## UV-TECH-A11-60-v1 — Índice de avance técnico (2026-10-10)

Motivo: informar las capacidades y la validación parcial del A11 integrado sin
confundirlas con los doce criterios íntegros del cierre histórico A9. Se adopta
una rúbrica propia de doce áreas con cinco comprobaciones binarias cada una,
con definiciones fijadas antes de asignar los resultados del corte. Demostrada
suma uno; pendiente, desconocida o evidencia de otro candidato suma cero.

El [informe y sus definiciones](UNIVERSALITY_TECHNICAL_PROGRESS_20261010.md)
registran 41/60 = 68,3 %. La selección y ponderación son decisiones explícitas
de ingeniería, no un estándar de universalidad ni un indicador científico.
Los recibos privados se conservan fuera de Git; el JSON público reproduce
definiciones, motivos y aritmética, no reemplaza los recibos de ejecución.

Consecuencias: este índice no reemplaza ni recalifica UV01–UV12, no convierte
la autorización de integrar en aceptación independiente y no acredita licencia,
adopción real ni plataformas sin recibos A11. El 25 % histórico usa otra escala:
no existe una comparación longitudinal hasta evaluar el corte anterior con
estas mismas definiciones. Una revisión futura de la rúbrica requiere otra
versión y conservar los resultados de esta. No se cambian los detectores,
el oráculo, los nueve estratos ni los protocolos y resultados de la tesis.

## UV-TECH-A11-60-v1 — Avance comparable a 48/60 (2026-10-10)

Por solicitud del propietario se ejecutó el [plan de cinco pasos](UNIVERSALITY_80_PLAN_20261010.md)
sobre los mismos bytes A11 y la misma rúbrica. Se demuestran 02.1, 02.2,
02.4, 04.4, 07.5, 08.4 y 11.2: **41/60 → 48/60 = 80 %**, incremento de siete
puntos y 11,67 puntos porcentuales. No se alteran definiciones ni pesos, ni
se traslada evidencia A9/A10 a A11. Se conserva el corte 68,3 % original.

El [resultado y JSON](UNIVERSALITY_80_RESULT_20261010.md) ligan tres versiones
Python nuevas, veintiséis perfiles, consumidor independiente de repositorio,
corpus congelado, casos físicos inválidos de tres dominios y consultas de
avisos completas a sus artefactos y recibos privados. La consulta es acotada
a la base pública y fecha, no un dictamen general de seguridad. La integración
a main se realiza bajo la autorización persistente del propietario; no es
publicación PyPI, aprobación de licencia ni revisión humana independiente.

Se mantienen doce comprobaciones pendientes, los cierres UV históricos,
R/M/B/H/O, corpus científico, nueve estratos y protocolo experimental. Las
mediciones de 1000 filas son conformance técnica de los extras y no resultados
científicos de rendimiento. No se usa Actions ni se crean recursos de pago.
