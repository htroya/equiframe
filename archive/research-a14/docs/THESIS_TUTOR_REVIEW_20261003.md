# Revisión de las observaciones del tutor y alcance autorizado

La versión entregada de `tesis_final.docx` incorpora las observaciones del
anteproyecto y mantiene las tres migraciones exigidas por Hernán: Pandas–Polars,
Pandas–DuckDB y Polars–DuckDB. Solo contiene capítulos 1–3 y referencias.
La entrega ocurrió el 3 de octubre de 2026 UTC, todavía 2 de octubre en Ecuador.
Este informe sustituye el alcance de una pareja descrito en
[la revisión anterior](THESIS_FINAL_REVIEW_20261003.md), que se conserva como
registro histórico.

## Fuentes y versión

Se leyó completo `Observaciones anteproyecto - Grupo 5 Paralelo B.pdf` y se
contrastó con `ModeloTFM Ciencias de la Computación.docx`. Las recomendaciones
del tutor se aplican como requisitos del trabajo; la petición posterior de
Hernán prevalece sobre la sugerencia de reducirlo a una sola migración y sobre
los capítulos 4/5 de la plantilla. La designación del tutor permanece pendiente
por instrucción expresa del usuario. No se inventaron firmas ni aprobaciones.

| Artefacto | SHA-256 |
|---|---|
| Word entregado | `4e2f571ceb16d98b16f1d74e5f66803e0268baa607f9ee589adf6e29d11854c8` |
| Word final anterior, respaldado | `ff638dff604fbe30179fa463b5e3c9440028f23fec0f114c55d4eac8f63246a2` |
| TFM anterior, conservado | `45aaccd3d66da222389b1d153dca5fa23e5eef9cd0ec75c15c3d797ab955cbe1` |
| Observaciones del tutor | `9b2ca6d66a710474f9fd58487f87d2bb57e53b4aabf5e84a5cf823a43be74cba` |
| Modelo institucional | `6d29b3ef68ed102ac44f34a9253d54d84380a08e39d9ae0cb60981fbe4a02dd3` |

## Comprobación de cada recomendación

| Recomendación | Cambio comprobado en el Word | Estado |
|---|---|---|
| Título de exactamente 15 palabras | «Evaluación híbrida de divergencias semánticas en migraciones ETL con reglas e Isolation Forest mediante EquiFrame» | Incorporada |
| Problema científico acotado | Pregunta, objetivo y alcance delimitan tres parejas y tres familias: ausencias/tipos, uniones y agregaciones | Incorporada |
| Impacto académico | Se estudia la capacidad y los límites del perfil híbrido frente a divergencias semánticas; el aporte no se reduce a entregar código | Incorporada; resultados pendientes |
| Límites estadísticos | Se distinguen métricas no definidas, soporte insuficiente, incertidumbre, dependencia y exclusiones | Incorporada |
| Verbos académicos en objetivos | Objetivos orientados a caracterizar, analizar, diseñar y evaluar con productos verificables | Incorporada |
| Brecha al final de la literatura | Síntesis y brecha delimitadas al perfil, reglas, referencia robusta y evaluación independiente | Incorporada |
| Conocimiento independiente del software e hipótesis | H1–H3 son contrastables; no se presume superioridad del híbrido | Incorporada; contraste pendiente |
| Aprendizaje sobre más de 10.000 registros reales no curados | El mínimo se aplica a las filas de la matriz efectiva de ajuste de M; se registran N por modelo/familia, ejecuciones únicas y grupos | Requisito incorporado; cumplimiento empírico pendiente |
| Montos intercambiados con perfil global idéntico | Caso dentro del alcance como control del límite informativo; no se promete detección si las variables permanecen iguales | Incorporada; evaluación real pendiente |
| Descarga y perfilado del corpus SERCOP 2025 | Inventario propuesto con procedencia, versiones, archivos, releases, ocid y adjudicaciones | Protocolo incorporado; datos reales pendientes |
| Viabilidad y cronograma | Cinco fases y 12 semanas previstas con responsables, insumos, controles de soporte y replanificación | Incorporada; viabilidad efectiva condicionada a insumos |
| Alcance documental y tutor | Solo 1–3, formularios institucionales sin firmas y tutor pendiente | Incorporada según instrucciones del usuario |
| Validación independiente y fuga | EquiFrame Verify, dos revisiones independientes, arbitraje elegible o estado pendiente, dependencias transitivas y partición global compartida | Protocolo incorporado; revisiones reales pendientes |

El PDF contiene una evaluación histórica del anteproyecto. Corregir el texto
no equivale a obtener una nueva aceptación del tutor. Tampoco se puede afirmar
que todos los requisitos empíricos estén satisfechos sin corpus, ajuste y
revisiones reales.

El mínimo de aprendizaje **no** se acredita contando adjudicaciones fuente,
sumando matrices distintas, reutilizando una ejecución en varias parejas ni
contando árboles o remuestreos. El PDF no impone literalmente 10.000 registros
por familia; la tesis exige informar el tamaño efectivo de cada modelo y
explicitar cualquier insuficiencia. Las antiguas cuotas 60/300 y 30/10/20 no
se presentan como tamaños científicos ya justificados.

Las tres parejas forman nueve estratos con las tres familias. Comparten catálogo,
dependencias y partición antes del ajuste; una ejecución reutilizada conserva su
identidad. Las métricas se presentan por pareja y por modelo/familia, sin mezclar
scores incompatibles ni inflar denominadores. La coordinación científica final
requiere manifiestos y evidencia reales; los tests técnicos no la sustituyen.

## Edición, presentación y verificación

Se modificaron 27 párrafos y 12 celdas, además de las figuras 4 y 5 para reflejar
el alcance de tres migraciones. Se conservaron exactamente las 61 entradas
bibliográficas de la versión anterior. La ampliación previa de capítulos 2/3
y sus fuentes verificadas permanece en el documento.

El Word tiene **132 páginas, 15 figuras y 17 tablas**. Contenidos, índice de tablas
e índice de figuras suman **97 destinos**, contrastados con la paginación de Word.
Se verificaron estilos APA 7, márgenes, referencias, notas, fórmulas y estructura;
A4, portada, formularios y paginación continua son adaptaciones institucionales
declaradas. No hay capítulos 4/5 ni sus entradas en el índice.

Todas las páginas fueron verificadas visualmente a resolución original:
123 inspecciones directas y 9 reutilizaciones exclusivamente por identidad de
bytes de PNG con inspecciones previas. No quedaron defectos materiales.
Los controles estructural, de contenido y visual están vinculados al hash del
Word entregado. La sustitución conserva copia anterior, fuentes y evidencia
privada en `revision_tesis_final_20261003_tutor_tres_migraciones`.

No se suben Word, PDFs, imágenes de revisión ni datos privados a Git. Esta tarea
no habilita GitHub Actions, no publica en PyPI y no inicia el paso 11.
