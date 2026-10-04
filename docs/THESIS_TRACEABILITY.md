# Trazabilidad con la tesis en elaboración

La entrega histórica tras el paso 10 técnico fue `tesis_final.docx`, guardada el
2026-10-03 a las 02:41:43 UTC. Incorpora las observaciones del anteproyecto y
el modelo institucional; por instrucción de Hernán contiene solo capítulos
1–3 y referencias, sin capítulos 4/5 ni remisiones. Tiene 130 páginas,
15 figuras, 17 tablas, 61 referencias y 97 destinos de índices comprobados.
Separa R, M y B; H combina R y M, y EquiFrame Verify (O) conserva la validación
independiente. Mantiene formato APA y límites entre verificación del software
y experimento pendiente.
[Entrega y comprobación](THESIS_FINAL_REVIEW_20261003.md).

SHA-256 de esa entrega histórica:

```text
ff638dff604fbe30179fa463b5e3c9440028f23fec0f114c55d4eac8f63246a2
```

En esa entrega histórica, el contraste principal se delimitó a Pandas–DuckDB y tres familias: ausencias
y tipos, uniones y agregaciones. La biblioteca conserva Polars y cinco familias
como cobertura técnica adicional. Los objetivos se reformulan en términos
académicos y las cuotas de escenarios quedan por fijar. El requisito de más
de 10.000 adjudicaciones originales sigue pendiente; no equivale a perfiles
o grupos independientes. Decisiones metodológicas A96/A98 y editoriales A97/A99.

La entrega anterior del 2026-10-02, entre los pasos 9 y 10, permanece intacta:
SHA-256 `45aaccd3d66da222389b1d153dca5fa23e5eef9cd0ec75c15c3d797ab955cbe1`,
125 páginas y 107 destinos. En esa versión sí se conservaron los capítulos
4/5 pendientes. [Registro histórico](THESIS_UPDATE_20261002.md).
El hash `c96f0ed…` identifica el borrador anterior a ambas ediciones.

Revisión del paso 8 contrastada directamente el 2026-10-02 contra el borrador
de SHA-256 `c96f0ed…`, anterior a las dos ediciones del Word.
La corrección de ingeniería 0.8.1 fortalece T09/T11 mediante vínculos entre
capturas, inventarios e intentos de reducción; no modifica el diseño experimental.
Véase [segunda revisión del paso 8](STEP_08_SECOND_REVIEW.md).

El paso 9 aporta código consumidor y conformidad local para T03/T09/T13–T14,
en `equiframe-benchmark 0.9.0` sobre núcleo 0.8.1. Cliente, snapshot y DDL
no están disponibles según confirmó Hernán; las verificaciones reales de T04,
T13–T14 y coordinación del servicio continúan pendientes. El código no amplía
el corpus ni confirma O. [Informe](STEP_09_REVIEW.md).

## Paso 10 técnico — 2026-10-03 UTC

Núcleo 0.9.0 añade inferencia aislada para medir M sin MAD. Benchmark 0.10.0
implementa sello y auditoría de protocolos, ejecución de prueba sin ajuste,
evaluación sobre intersección R/M/B/H y O confirmado, cobertura y soportes
propios, AP homogénea, bootstrap por grupos, costes sobre capturas y CSV
regenerables. Refuerza T09/T11/T15–T18 y OE3/OE4/OE5.

El sello técnico de piloto conserva los bloqueos; el sello final los exige
resueltos. Reutilizar O necesita reproducir la salida revisada con la misma
implementación e inputs. Se conservan fallos, etiquetas pendientes, desacuerdos
y familias no soportadas. Las hipótesis se mantienen: no se generan personas,
etiquetas ni métricas SERCOP para aparentar su confirmación.

El bundle conserva bytes, capturas, fuentes y configuración original; regenera
el contenido completo de tablas/decisiones. Esa comprobación de software no
acredita una ejecución independiente de otro integrante. Corpus, cliente,
DDL/mapeos, decisiones y revisión de resultados siguen pendientes, al igual
que la licencia, control del nombre y publicación PyPI del paso 19. Actions
está desactivado por la cuota; las plataformas de esta versión requieren
evidencia nueva. [Diseño](STEP_10_DESIGN.md), [evaluación](STEP_10_EVALUATION.md),
[distribución](STEP_10_DISTRIBUTION.md) y [revisión](STEP_10_REVIEW.md).

Fuente histórica: `TFM_EquiFrame_ACTUAL.docx`, revisada inicialmente el 2026-09-28
y contrastada de nuevo para el paso 5 el 2026-10-01.

SHA-256 del archivo revisado:

```text
c96f0edfcab839b2ccf357527f4a7937c4b1fd3570f491d702b4f01fde44b38d
```

El archivo está en la carpeta padre del proyecto local y no se publica en Git.
La edición inicial queda registrada en A86 y la entrega institucional posterior
en A96–A99. Ninguna cierra el estudio ni sustituye decisiones experimentales
y revisiones humanas pendientes.

## Matriz de requisitos

La matriz siguiente describe la entrega vigente de capítulos 1–2 y anexos
preparatorios, identificada en «Segunda entrega editorial final». Las referencias
3.x conservan su ubicación histórica como trazabilidad del diseño, sin declarar
un capítulo 3 entregado en el Word vigente. A100/A101/A110 prevalecen sobre
A96/A98: tres parejas principales, N efectivo de aprendizaje y soportes pareados.

| ID | Sección | Requisito vigente / cobertura técnica | Componente / paso de Hernán | Evidencia de aceptación |
|---|---|---|---|---|
| T01 | 1.3, 1.4, 3.3 | Tres familias del contraste; cinco disponibles en software | Contratos/catálogo, 1/4/6; A96 | Casos y reglas de las tres familias; adicionales separados |
| T02 | 1.4; diseño histórico 3.1 | Pandas–Polars, Pandas–DuckDB y Polars–DuckDB principales; tres familias, nueve estratos | Adaptadores/evaluación, 2/10; A100 | Protocolo fijado por pareja, capturas nativas y resultados separados sin contar reutilizaciones como nuevas muestras |
| T03 | 1.4; diseño histórico 3.2 | Snapshot original, SHA-256 e inventario; más de 10.000 registros reales efectivos de aprendizaje, con soporte/grupos y exclusiones | Puertos/manifiestos, 1/2/9; adquisición compartida con Jhair; A101/A110 | Procedencia y hashes del corpus; N_fit real por modelo/familia, sin sustituirlo por adjudicaciones, filas de calibration/test o cuotas heredadas |
| T04 | 3.2, 3.5 | Compilación OCDS y cohorte temporal validada | Dominio de Jhair; consumo en 9 | Contrato de dominio y perfilado real |
| T05 | 3.3 | Contratos independientes del motor; normalización permitida | Contratos/normalización, 1/3 | Pruebas de ausencia, precisión, orden y multiplicidad |
| T06 | 3.3.1 | R fijada antes de mutantes finales | Reglas, 4/6 | Revisión/commit de reglas y catálogo |
| T07 | 3.3.1, 3.3.4 | O independiente, doble revisión ciega | Benchmark, 6 | Esperados, decisiones A/B y resolución |
| T08 | 3.3.3 | Comparación completa de valores y multiplicidades | Comparador, 3 | Diferencias completas, casos que conservan totales |
| T09 | 3.4 | Módulos sustituibles y CLI | Núcleo/API, 1/2/8 | Protocols, pruebas de integración y CLI |
| T10 | 3.4.1 | Perfil de una ejecución, R/M sin otra salida | Reglas/perfiles, 4/5 | Pruebas de dependencia y exclusión de fuga |
| T11 | 3.4.2 | Evidencia, reducción acotada y Hypothesis | Evidencia, 3/8 | Pruebas por propiedades y presupuesto registrado |
| T12 | 3.4.3 | H = R OR M con disponibilidad explícita | Decisiones, 7 | Nueve combinaciones y estado completo/parcial |
| T13 | 3.5 | Grano adjudicación, puente sin monto, monedas separadas | Jhair; contrato/integración 9 | Unicidad, integridad y reconciliación |
| T14 | 3.5 | Preparación antes de publicación, idempotencia | Jhair/José; integración 9 | Carga repetida y fallo sin cambiar versión vigente |
| T15 | 3.6 | Features por familia, imputación solo en ajuste | Perfiles, 5 | Diez fórmulas y preprocesador 0.5.0; pruebas sintéticas y consumidor wheel. Selección científica pendiente |
| T16 | 3.6 | IF y MAD con calibración externa | Modelos, 7 | Scores, umbrales, igualdad estricta y no estimable |
| T17 | 3.7 | Dependencias transitivas dentro de una partición | Benchmark, 6 | Componentes conexos y ausencia de fuga |
| T18 | 3.7, 3.9 | Piloto y congelación; prueba no selecciona parámetros | Benchmark, 6/7/10 | FreezeManifest y auditoría de cambios |
| T19 | 1.4, A.7; diseño histórico 3.8 | Soporte pareado de los métodos comparados, con O confirmado; intersección común R/M/B/H adicional, cobertura y denominadores | Evaluación, 10; A110 | Conteos y métricas regenerables por soporte; el reporte histórico conserva su intersección común y no se renombra como protocolo principal vigente |
| T20 | 3.8 | Incertidumbre por grupos y costos desglosados | Evaluación, 10 | Remuestreo trazable y medición controlada |
| T21 | 3.9 | Reproducción por otro integrante | Entrega, 10 | Registro independiente con contenido y decisiones |
| T22 | 1.4, 3.5 | Ejecución local, sin plataforma distribuida | Arquitectura | Núcleo local y VM como apoyo colaborativo |

## Decisiones todavía abiertas en la tesis

El paso 5 implementa T10/T15 con las decisiones A48–A54. Los recibos de
conversión son un formato de ingeniería suplementario; no un requisito ya
escrito en el borrador. La declaración `normal_training` y el hash del manifiesto
no sustituyen revisión O ni validación de splits. Los casos sintéticos verifican
fórmulas/API; no acreditan corpus científico ni las metas históricas de 60
escenarios o 300 perfiles, sustituidas por A98.

| Decisión | Qué debe obtenerse antes de cerrarla | Tratamiento en el software |
|---|---|---|
| Cobertura anual 2025 y piloto enero-marzo | Inventario real y restricciones justificadas | Configuración versionada; no codificar año en el núcleo |
| startDate y reserva release.date | Perfilado, significado por modalidad y selección de release | Política explícita de dominio; bloquear freeze si sigue pendiente |
| Fechas sin offset / granularidad día | Evidencia de publicación y criterio acordado | Contrato temporal explícito; no convertir por conjetura |
| Escala/precisión decimal | Perfilado de montos | Esquema configurable y exactitud comprobada |
| Claves incompletas/contradictorias | Criterios de excepciones y procedencia | Política de contrato, no claves inventadas |
| Alpha propuesto 5% | Justificación operativa y soporte de grupos | Sin default oculto en evaluación final |
| Árboles/submuestras IF | Piloto normal | Configuración inicial revisable, bundle registra valor final |
| Soporte de modelos por familia | Variación y cantidad de grupos de ajuste/calibración | `not_estimable` explícito |
| Cantidades de escenarios/perfiles y reparto por partición | Inventario real, tres familias, grupos transitivos y revisiones | Por fijar en la tesis vigente; 60/300 y 30/10/20 son metas históricas sustituidas por A98; no fragmentar grupos |
| Intervalos y tolerancia inferencial | Independencia y suficiencia | Descriptivos si no hay soporte; no atribuir garantías |
| Revisores/arbitraje con tres autores | Asignación y tratamiento de conflictos | Registro ciego y pendientes, sin aprobaciones automáticas |

## Ajustes planteados al borrador inicial

La edición inicial y la adaptación posterior desarrollan estos límites en los
capítulos 2/3. El nuevo alcance acota las migraciones y familias; la resolución
humana de conflictos y los resultados reales siguen pendientes.

1. En 1.4 y 3.5 explicar que el núcleo sigue siendo local y la VM apoya colaboración/publicación de snapshots; distinguir transporte compartido de evaluación distribuida.
2. En 3.4 explicitar API tipada, estados independientes y separación del benchmark respecto de la biblioteca consumible.
3. En 3.3.4 resolver la independencia del arbitraje cuando el tercer integrante es autor de la variante.
4. En 3.6/3.7 dejar alpha, modelos por familia y tamaños como propuestas hasta observar soporte real.
5. En 3.8 establecer que las mediciones comparativas requieren aislamiento de otras cargas de la VM.
6. En 3.4.2 se informa lo construido y probado, junto con componentes no estimables o pendientes. La entrega solo contiene capítulos 1–3; no incorpora resultados de ejemplo como observaciones científicas.

Las decisiones de empaquetado, Python 3.12, formatos de API y organización del repo son propuestas de ingeniería de esta arquitectura, no afirmaciones de que el borrador ya las exige.

## Evidencia de implementación del paso 1

`packages/equiframe` aporta contratos/fixtures sintéticos para T01/T05, metadatos
de artefacto para la parte declarativa de T03, API/CLI y un Protocol completo
para la parte inicial de T09, y propiedades de serialización para T11.
Esto no acredita validación de datos, un snapshot real, reglas evaluadas,
independencia/revisión del oráculo ni resultados experimentales.
Las decisiones de formato, dependencias y ámbito (A13–A20) son de ingeniería.
La [segunda revisión del paso 1](STEP_01_REVIEW.md) registra correcciones y
regresiones sin modificar el diseño experimental.
Escalas/unidades/fechas de fixtures no se transfieren a SERCOP. No se modificó
la tesis ni se resolvieron por defecto sus decisiones metodológicas pendientes.


## Requisitos adicionales de producto, versión 0.2 (2026-09-28)

Estos requisitos vienen del pedido de Hernán para el paso 2; no son citas ni
contenido ya incorporado a la tesis. No modifican la independencia R/M/B/H/O,
el experimento reproducible, las cinco familias ni el caso DW SERCOP.

| ID | Requisito adicional | Paso/evidencia |
|---|---|---|
| P01 | Biblioteca general para desarrolladores, analistas y arquitectos; contratos configurables | 2: API/ejemplos en comercio y telemetría sin nombres de dominio obligatorios |
| P02 | Instalación base útil y `import equiframe as ef` ligero | 1/2: contratos/store/registro; wheel base fuera del checkout sin motores/ML |
| P03 | Tres motores opcionales con extensibilidad/inyección explícita | 2: puertos completos, registro por instancia, extras instalados individualmente |
| P04 | Ejecutar desde scripts/notebooks de otro proyecto sin VM o sys.path | 2: `ef.execute`, wheel instalado y ejemplos externos |
| P05 | Esquema esperado y salida física separados; no ocultar diferencias | 2: artefactos, máscaras NULL/NaN, tipos nativos, límites decimal/tiempo e índice |
| P06 | Distribución pública verificable por pip/PyPI y accesible a cualquier persona | Después de completar 10 y una nueva ronda de revisión: licencia acordada, control del nombre, metadatos/versiones y publicación; pendiente |

Evidencia del paso 2 para T01/T02/T03/T05/T09/T11/T22: implementaciones nativas,
entradas locales identificadas/verificadas, captura de evidencia, tipos y aislamiento
local, pruebas pequeñas con esperados explícitos y límites reales. T05/T11 continúan
parcialmente pendientes de comparación/normalización/reducción. No se acredita
snapshot real SERCOP, comparador completo, R, perfiles, detectores, benchmark,
aprobación/revisión científica, VM ni mejora experimental de H. Las cantidades de
pruebas y plataformas verificadas se registran en `STEP_02_REVIEW.md` después de
los controles; los ejemplos no cuentan como los 60 escenarios previstos.

A21–A26 registran motivos y consecuencias de ingeniería. El DOCX no se edita;
conserva el hash declarado arriba. Las decisiones experimentales abiertas siguen
pendientes del piloto/equipo; la distribución pública no se adelanta a esta tarea.


## Revisión de ingeniería 0.2.1 — 2026-09-28

La segunda revisión del paso 2 añade 142 regresiones de transporte/ejecución,
coherencia de manifiestos y cierre de recursos. Las decisiones A27–A32 registran
los motivos y consecuencias. Se mantiene el alcance parcial de T01/T02/T03/T05/
T09/T11/T22 y la independencia experimental; no se añaden resultados científicos.

Se explicita que el DW y su programa de conexión residirán en OCI, con ejecución
de EquiFrame dentro de la VM o acceso externo por snapshots verificados. Es una
decisión de despliegue solicitada por el usuario; la conexión real sigue pendiente.
La matriz CI ampliada no acredita funcionamiento en la VM real. El DOCX no se edita.
Evidencia técnica: [segunda revisión del paso 2](STEP_02_SECOND_REVIEW.md).

## Paso 3 — 0.3.0, 2026-09-30

Se volvió a leer el DOCX, especialmente 1.3, 3.3 y 3.4; conserva el SHA-256
registrado. Sus primeros cuatro objetivos corresponden a OE1–OE4 del encargo;
el archivo contiene además un párrafo específico de documentación y reproducción.
No se modifica ni se presenta la distribución pública como requisito textual de la tesis.

La entrega atiende principalmente **OE1 y OE3**, como fundamento técnico de **OE4**:
T05 (normalización exclusivamente autorizada), T08 (contenido/multiplicidades
completos), la API sustituible de T09 y evidencia/propiedades/presupuestos de T11.
La reducción de casos de T11 y la CLI operacional de T09 quedan para el paso 8.
Pruebas con esperados explícitos cubren las cinco familias, controles que conservan
totales, valores extremos, inválidos, spill y tres motores reales. No son escenarios
humanamente revisados, resultados científicos ni validación del DW.

P02/P04 se extienden a consumidores externos de comparación con wheel base/extras;
P06 conserva la aceptación de publicación pública en el paso 10. El comparador no
recibe ni emite perfiles, etiquetas de entrenamiento o resultados de R/M/B/H.
Dos motores coincidentes pueden compartir un error; O requiere revisión independiente.
Decisiones A33–A40 y [semántica](COMPARISON.md); resultados efectivos en
[informe del paso](STEP_03_REVIEW.md). Permanecen los diez pasos y sus responsables.

## Paso 4 — 0.4.0, 2026-09-30

El borrador exige una línea base R determinista, independiente de otras salidas,
etiquetas y oráculo, fijada antes de las variantes finales (T06 y T10). El
servicio `evaluate_rules` consume una ejecución capturada y sus referencias
verificadas; evalúa las seis formas ya declaradas, precondiciones y
aplicabilidad. Las pruebas distinguen incumplimiento, no aplicabilidad,
imposibilidad de evaluación, controles correctos difíciles y el límite de
esquema/suma global ante intercambio de montos. El catálogo técnico de cinco
familias fija revisiones y huellas de R; no es el benchmark científico revisado.

La corrección heredada del paso 3 refuerza T08/T11: un manifiesto `equivalent`
con filas declaradas 1/2 y solo una emparejada se rechaza estructuralmente.
La integridad de artefactos se comprueba al leerlos por separado. Nuevos modelos
de evidencia R 1.0 no migran ni reinterpretan contratos 1.0.

La semántica exacta de joins, ausencias, `count`, grupos vacíos, orden y
reconciliación elegida es decisión de ingeniería A41–A47, documentada en
[Reglas R](RULES.md). La cantidad de conversiones fallidas no es inferible de
una salida capturada sin recibo adicional. Cohorte y fechas del DW, catálogo
revisado, particiones, alpha y comparación experimental siguen abiertos.
El DOCX permanece sin modificar.

## Paso 6 — benchmark 0.6.0, 2026-10-01

Se contrastaron los objetivos de §1.3 y la revisión/partición de §3.3.4/§3.7;
el SHA-256 del DOCX permanece idéntico. El [diseño del paso](STEP_06_DESIGN.md)
explica la relación con OE1–OE4 y el objetivo adicional de reproducción.

T01/T02 se ejercitan con cinco familias y quince ejecuciones nativas. T06
registra huellas reales de R antes de candidatos, sin modificar el catálogo del
paso 4. T07 incorpora revisión asignada, paquetes ciegos, conflictos, desacuerdos
y estados pendientes; las aprobaciones científicas siguen sin realizarse.
T17 implementa grupos transitivos y auditoría de fuga. T15 conecta la selección
normal revisada con el preprocesador existente, comprobando la captura exacta.
T18 aporta versiones de catálogo/splits y conserva pendientes; **no implementa
el FreezeManifest final** con modelos, alpha, corpus y protocolo de costos.

El piloto tiene 5 escenarios, 35 candidatos y 15 perfiles, en 4 grupos, con
35 revisiones pendientes y cero etiquetas científicas confirmadas. No se
cuentan como la meta 60/300. Sus mutaciones de artefactos no son implementaciones
ETL mutadas. R mínima y features del piloto son configuración técnica y deben
revisarse antes de congelar el experimento. No se acredita snapshot/DW SERCOP,
modelo entrenado, métricas ni mejora del híbrido.

P02/P04 se verifican con imports y consumo externo de distribuciones; P06 mantiene
como aceptación pública final `pip install equiframe` desde PyPI. La prueba
local con pip y wheels no acredita publicación en ese índice. A55–A62 registran
motivos, versión y consecuencias. Resultados efectivos: [informe](STEP_06_REVIEW.md).

## Paso 7 — núcleo y benchmark 0.7.0, 2026-10-01

Se releen el objetivo general, los cinco párrafos de objetivos específicos en
§1.3, la tabla H de §3.4.3 y las fórmulas/condiciones de §3.6–3.7. El DOCX conserva
el hash declarado y no se modifica. [Diseño y reorientación](STEP_07_DESIGN.md).

T12 implementa H con nueve combinaciones y alerta parcial; T16 implementa
Isolation Forest, MAD, score con signo definido, alpha explícito, rango exacto,
igualdad estricta y no estimable. T15 reutiliza las medianas e indicadores de
ajuste para ambos métodos. T17 incorpora selección normal de calibración y
auditoría de grupos disjuntos. T18 conserva versiones/hashes/configuración,
pero el FreezeManifest experimental completo permanece pendiente.

El aporte principal es OE3 y la infraestructura de OE4; mantiene OE1 por
familia y respeta la responsabilidad compartida de OE2. El quinto objetivo de
documentación/reproducción se apoya en persistencia, dependencias bloqueadas y
consumidores externos. P02/P04 se verifican con import ligero, extra `ml` y
restauración/inferencia del bundle en instalación base. P06 sigue sin publicación
pública PyPI; no se atribuye esa distribución al texto de la tesis.

Las pruebas sintéticas de software y sus modelos temporales no cuentan como
perfiles normales científicos, escenarios revisados, ni resultados de H1–H3.
El piloto anterior conserva cero etiquetas confirmadas y carece de soporte
por familia para ajuste/calibración. A63–A69 registran decisiones y consecuencias;
[verificación efectiva](STEP_07_REVIEW.md).

## Paso 8 — núcleo y benchmark 0.8.0, 2026-10-01

La integración de R/perfil/M/B/H utiliza los formatos y fórmulas existentes;
el oráculo permanece en benchmark y no alimenta la inferencia. El runner aporta
trazabilidad de captura, versiones, etapas, evidencia y reportes a OE3/OE4/OE5.
El reductor facilita diagnóstico técnico con un fallo preservado; no genera
etiquetas científicas ni transforma candidatos reducidos en nuevos escenarios
revisados automáticamente.

A72–A78 precisan ingeniería, estados y límites. No hay modificación metodológica
ni del documento de tesis. Los datos, modelos y autores de tests son sintéticos;
no aportan revisión humana, resultados SERCOP, FPR ni confirmación H1–H3. El piloto
conserva 5 escenarios/4 grupos/15 perfiles y 35 revisiones pendientes. P06 continúa
pendiente de publicación pública en la etapa indicada por Hernán. La instalación
temporal de wheels solo verifica ingeniería. [Diseño](STEP_08_DESIGN.md),
[uso](ORCHESTRATION.md) y [verificación](STEP_08_REVIEW.md).

## Alcance vigente del documento tras las observaciones del tutor

El [contraste de las 13 recomendaciones](THESIS_TUTOR_REVIEW_20261003.md)
corresponde al Word entregado con hash
`4e2f571ceb16d98b16f1d74e5f66803e0268baa607f9ee589adf6e29d11854c8`.
Hernán mantiene las tres parejas principales y tres familias; A100 sustituye
la reducción a una pareja de A96. A101 corrige A98: el mínimo mayor que 10.000
corresponde a los registros del conjunto efectivo de ajuste, no a adjudicaciones
fuente ni sumas de matrices. Se informan N por modelo/familia, ejecuciones únicas
y grupos independientes. Las reutilizaciones entre parejas no aumentan N.

El Word contiene capítulos 1–3 y referencias, 132 páginas, 15 figuras, 17 tablas
y 97 destinos paginados. Los controles editoriales están cerrados; corpus SERCOP
real, soporte de aprendizaje, revisión doble, designación del tutor y aceptación
institucional permanecen pendientes. Los pasos 9/10 técnicos no acreditan esos
requisitos. El [migrador integrado](MIGRATION.md), cuyo [plan previo](MIGRATION_DESIGN.md)
se documentó antes de programar, es una extensión de
ingeniería autorizada antes del paso 11; no cambia R/M/B/H ni incorpora esperados
o etiquetas a las variables de los detectores.

El núcleo 0.10.0 implementa las seis direcciones entre los tres motores y
conserva comparación observada/esperado, requisitos de componentes y evidencia.
El benchmark 0.10.1 fija esa dependencia sin cambiar algoritmos ni protocolos.
[Validación y límites](MIGRATION_REVIEW.md). Sus pruebas sintéticas verifican
ingeniería; no constituyen registros reales de aprendizaje ni revisión humana.

## Reorientación documental y refuerzo autorizado — 2026-10-03

El encargo actual mantiene tres parejas y tres familias principales, pero entrega
solo los capítulos 1–2 y anexos preparatorios. Los documentos históricos no son
instrucciones para sustituir `tesis_final.docx` ni acreditan autorización del tutor
para retirar definitivamente el futuro desarrollo. A108–A110 registran alcance
y consecuencias, sin convertir el plan en ejecución científica.

El refuerzo de la biblioteca conserva núcleo 0.10.0/benchmark 0.10.1 como versiones
de partida; los cambios aún no publicados están en `Unreleased`. Corrige el
informe de migración para distinguir comparación automática con esperado
aportado de EquiFrame Verify (O); no crea etiquetas ni revisores. Se conservan
las tres comparaciones y la lectura íntegra de formatos históricos. Las pruebas
integradas nuevas cubren las tres familias en seis direcciones con motores
reales y esperados literales sintéticos. Sus cantidades no aumentan N_fit ni
prueban hipótesis, integración SERCOP o aceptación institucional.

## Primera entrega de formato y candidato 0.11.0 — 2026-10-03

La autoridad de contenido es `tesis_reorientada_capitulos_1_2.docx`; la referencia
visual exacta es `tesis_final.docx` de la raíz. `tesis_corregda_v1.docx` aplica
formato sin añadir resultados académicos. La evidencia editorial de esa entrega está
fuera del repositorio; la descripción inicial de 130 páginas pertenece a otra
entrega y no fija el número de páginas del documento actual.

La primera entrega quedó en 133 páginas editables, conservando las 20 tablas,
15 figuras corregidas, 74 referencias y 26 grupos de expresiones de la autoridad
de contenido. Los originales conservaron sus hashes. Word actualizó realmente
campos e índices; se renderizaron y revisaron todas las páginas finales a tamaño
legible. La evidencia estructural/visual está en `word_qa_20261003` del workspace,
incluido el reemplazo documentado del runtime ausente por Word nativo. Esto
acredita conservación y revisión de formato, sin afirmar identidad de píxeles
entre documentos de contenido distinto ni aceptación académica.

La reanudación solicitó una revisión bibliográfica/editorial adicional fuera
del alcance del código. Este registro conserva la primera entrega como historia;
no atribuye sus 133 páginas o hashes a la segunda entrega final descrita abajo.

El candidato técnico 0.11.0 añade Verify operacional, workflow, ingestión, carga
local y bundles. Mantiene el protocolo científico: Pandas–Polars,
Pandas–DuckDB, Polars–DuckDB × ausencias/tipos, uniones y agregaciones, nueve
estratos. La [validación SERCOP](SERCOP_EXAMPLE.md) es un subconjunto público
de dos awards; no satisface el corpus efectivo de aprendizaje, independencia
humana/doble revisión, ni prueba hipótesis. R/M/B/H y sus entradas se conservan.

Los tests, receipts y wheels son evidencia de ingeniería. El esperado literal
manual del consumidor se declara con su procedencia, sin autores/revisores
inventados. DW/OCI, corpus/modelado, aceptación del tutor y publicación externa
mantienen requisitos propios. A111–A116 registran motivo y consecuencias.

## Segunda entrega editorial final — 2026-10-03

El archivo editable final, fuera de Git, es `tesis_corregda_v1.docx` en la raíz
del workspace tesis. Su identidad comprobada es:

```text
365af93cdd4bbf7e665145d0e4597eb1391678f5dcb16ce25423b5802c249ac2
```

La nueva instrucción editorial autoriza verificar las 74 referencias mediante
fuentes primarias, corregir su metadata, registrarlas en la lista actual nativa
de Administrar fuentes de Word y aplicar APA 7 al texto y a la bibliografía.
El cuerpo queda alineado a la izquierda; la bibliografía APA 7 es manual y
editable, con DOI/URL verificables, no un campo automático de bibliografía.
No se crean obras, autores, fechas, revisores o resultados científicos.

La entrega tiene **134 páginas**, **74 fuentes nativas**, **74 referencias**,
**17 figuras** y **20 tablas**. Añade dos gráficos técnicos de proceso ETL y
verificación independiente, figuras 14/15 en páginas 81/82; la bibliografía
comienza ahora en página 83. Las 17 figuras aparecen en el selector nativo
de referencias cruzadas bajo **Ilustración**, y las 20 tablas bajo **Tabla**.
Los rótulos visibles conservan «Figura». Los campos y relaciones del documento
se validaron sin errores; el rótulo de la tabla 2 permanece unido a su tabla.

Se comprobaron las **134 páginas**: 112 imágenes de página de la última revisión
y 22 idénticas en SHA-256 a páginas ya aprobadas. La entrega es idéntica a la
revisión congelada. Conserva exactamente los textos de las 20 tablas, los bytes
y orden relativo de las 15 imágenes originales, los 530 nombres de marcadores
originales y los 26 textos analíticos identificados en la autoridad de contenido.
Ambos originales de contenido y formato conservan sus hashes.

Los recibos editoriales están en `word_qa_20261003_revision2/delivery-final.json`,
`delivery-final.md` y `delivery-structure-final.json` del workspace; la comprobación
independiente de preservación está en
`revision_equiframe_20261003/word-preservation-final.json`. Estos artefactos
locales no se incorporan al repositorio de código. La revisión editorial y los
controles del candidato 0.11.0 no acreditan aceptación del tutor, corpus efectivo,
etiquetas/revisiones humanas, entrenamiento científico, DW/OCI ni publicación PyPI.

## Revisión integral del software 0.11.1 — 2026-10-03

La [matriz de preservación](COMPREHENSIVE_REVIEW_SCOPE_20261003.md) fija la última
tesis y ambas guías por SHA-256; permanecen intactas. No se editan las catorce
actividades ni las carpetas de José/Jhair. Las aclaraciones del repositorio
incorporan los proveedores alternativos de VM que constan en el Word de José,
sin retirar opciones ni añadir entregables obligatorios.

Las decisiones A119–A126 registran correcciones de decimales/presupuestos y
evidencia, vinculación de controles y el reporte pareado descriptivo. El código
conserva R/M/B/H/O, tres parejas × tres familias, nueve estratos y N efectivo de
aprendizaje. La huella de R corregida exige evidencia nueva cuando se use en un
estudio, sin reescribir freezes previos.

El reporte aditivo expone soporte por contraste conforme al plan vigente, pero
no reemplaza el protocolo común histórico ni acredita análisis científico
principal. Esa adopción requiere revisión y congelación antes de la prueba.
No se entrenan modelos del estudio, inventan etiquetas o recalibran parámetros.

La [revisión final](COMPREHENSIVE_REVIEW_20261003.md) acredita nueve controles por
distribución y 1041/454 pruebas de fuente repetidas desde instalaciones externas.
Tres casos de symlinks se omiten por privilegios Windows; no se extrapola a
otras plataformas ni al corpus/servicio/DW reales. Los pendientes empíricos,
humanos y de publicación conservan su responsable y aceptación propia.
