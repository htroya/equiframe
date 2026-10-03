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
