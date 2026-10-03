# Trazabilidad con la tesis en elaboración

El Word se amplió y guardó el 2026-10-02 después del paso 9 y antes del paso 10.
La revisión académica desarrolla los capítulos 2/3, conserva independientes
R/M/B/H y EquiFrame Verify (O), y corrige APA e índices sin añadir resultados
experimentales. Contiene 125 páginas, 15 figuras, 17 tablas y 61 referencias.
Las 107 entradas de los tres índices se comprobaron contra la paginación de Word.
[Alcance y verificación](THESIS_UPDATE_20261002.md).

SHA-256 del Word actualizado:

```text
45aaccd3d66da222389b1d153dca5fa23e5eef9cd0ec75c15c3d797ab955cbe1
```

El hash `c96f0ed…` que aparece en las revisiones históricas siguientes identifica
el borrador previo. Sus capítulos 4/5 pendientes se conservaron íntegros.
Hernán solicitó después una entrega `tesis_final.docx`, basada en observaciones
del anteproyecto y el modelo institucional, una vez terminado el paso 10.
Esa entrega posterior todavía no queda acreditada por este registro.

Revisión del paso 8 contrastada directamente el 2026-10-02 contra el mismo DOCX.
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
La edición autorizada del 2026-10-02 queda registrada en A86; no cierra el estudio
ni elimina las decisiones experimentales pendientes.

## Matriz de requisitos

| ID | Sección | Requisito del borrador | Componente / paso de Hernán | Evidencia de aceptación |
|---|---|---|---|---|
| T01 | 1.3, 1.4, 3.3 | Cinco familias de divergencias | Contratos/catálogo, 1/4/6 | Casos y reglas por familia |
| T02 | 1.4, 3.1 | Pandas-Polars y Pandas-DuckDB principales; tercera pareja adicional | Adaptadores/evaluación, 2/10 | Resultados separados por migración |
| T03 | 3.2 | Snapshot original, SHA-256, inventario, cobertura/exclusiones | Puertos/manifiestos, 1/2/9; adquisición compartida con Jhair | Hashes y procedencia verificables |
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
| T19 | 3.8 | Métricas sobre intersección evaluable, cobertura y denominadores | Evaluación, 10 | Conteos y métricas regenerables |
| T20 | 3.8 | Incertidumbre por grupos y costos desglosados | Evaluación, 10 | Remuestreo trazable y medición controlada |
| T21 | 3.9 | Reproducción por otro integrante | Entrega, 10 | Registro independiente con contenido y decisiones |
| T22 | 1.4, 3.5 | Ejecución local, sin plataforma distribuida | Arquitectura | Núcleo local y VM como apoyo colaborativo |

## Decisiones todavía abiertas en la tesis

El paso 5 implementa T10/T15 con las decisiones A48–A54. Los recibos de
conversión son un formato de ingeniería suplementario; no un requisito ya
escrito en el borrador. La declaración `normal_training` y el hash del manifiesto
no sustituyen revisión O ni validación de splits. Los casos sintéticos verifican
fórmulas/API; no se cuentan como los 60 escenarios o 300 perfiles propuestos.

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
| 60 escenarios y reparto 30/10/20 | Catálogo, grupos transitivos y revisiones reales | Metas frente a cantidades realizadas; no fragmentar grupos |
| Intervalos y tolerancia inferencial | Independencia y suficiencia | Descriptivos si no hay soporte; no atribuir garantías |
| Revisores/arbitraje con tres autores | Asignación y tratamiento de conflictos | Registro ciego y pendientes, sin aprobaciones automáticas |

## Ajustes planteados al borrador inicial

La edición del 2026-10-02 desarrolla estos límites en los capítulos 2/3.
La resolución humana de conflictos y los resultados reales siguen pendientes.

1. En 1.4 y 3.5 explicar que el núcleo sigue siendo local y la VM apoya colaboración/publicación de snapshots; distinguir transporte compartido de evaluación distribuida.
2. En 3.4 explicitar API tipada, estados independientes y separación del benchmark respecto de la biblioteca consumible.
3. En 3.3.4 resolver la independencia del arbitraje cuando el tercer integrante es autor de la variante.
4. En 3.6/3.7 dejar alpha, modelos por familia y tamaños como propuestas hasta observar soporte real.
5. En 3.8 establecer que las mediciones comparativas requieren aislamiento de otras cargas de la VM.
6. En el capítulo 4 informar lo construido y probado, junto con los componentes no estimables o pendientes. No incorporar resultados de ejemplo como observaciones.

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
