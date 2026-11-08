# Entrega de la tesis tras el paso 10 — 2026-10-03 UTC

El documento `tesis_final.docx` se guardó en la carpeta de tesis a las
02:41:43 UTC del 2026-10-03 (21:41:43 del 2026-10-02 en Ecuador). Contiene
únicamente los capítulos 1, 2 y 3 y las referencias. Se retiraron los capítulos
4 y 5, sus entradas del índice y las remisiones a ellos, por instrucción de Hernán.
La entrega conserva 15 figuras, 17 tablas y 61 referencias; tiene 130 páginas.

La adaptación se realizó después de integrar el paso 10 en
[`d8b84ef`](https://github.com/htroya/equiframe/pull/20). El Word anterior,
entregado antes de ese paso, permanece intacto. Los archivos privados de tesis,
adjuntos, datos y comprobantes no se incorporan al repositorio remoto.

## Fuentes de la revisión

Se leyeron íntegramente las dos páginas de *Observaciones anteproyecto - Grupo 5
Paralelo B.pdf* y las 14 páginas del *ModeloTFM Ciencias de la Computación.docx*.
Ambos originales se conservaron. Las observaciones orientan el contenido
académico y el modelo aporta la estructura institucional; los ejemplos de
autores, tutores, fechas y firmas del modelo no se trasladan como hechos.
La instrucción de conservar solo tres capítulos y aplicar APA prevalece sobre
el esquema de cinco capítulos y los formatos mezclados de la plantilla.

| Archivo fuente | SHA-256 |
|---|---|
| Tesis entregada antes del paso 10 | `45aaccd3d66da222389b1d153dca5fa23e5eef9cd0ec75c15c3d797ab955cbe1` |
| Observaciones del anteproyecto | `9b2ca6d66a710474f9fd58487f87d2bb57e53b4aabf5e84a5cf823a43be74cba` |
| Modelo institucional | `6d29b3ef68ed102ac44f34a9253d54d84380a08e39d9ae0cb60981fbe4a02dd3` |

La comprobación de entrega confirma que esos tres hashes permanecen iguales.

## Delimitación académica

Título de quince palabras: **Evaluación híbrida de divergencias semánticas en
migraciones ETL con reglas e Isolation Forest mediante EquiFrame**.

El experimento principal se limita a **Pandas–DuckDB** y tres familias:
**ausencias y tipos, uniones y agregaciones**. Polars y las otras familias
siguen siendo capacidades del software; no amplían la población del estudio.
La pregunta investiga detecciones adicionales, falsas alarmas, cobertura,
costo y límites de combinar reglas con Isolation Forest. No presupone que
el híbrido aventaje a las reglas.

Los objetivos específicos usan caracterizar, analizar, examinar, comparar y
evaluar. La Figura 4 y la Tabla 5 corresponden a esos objetivos. La Figura 5,
el texto del método y las tablas distinguen la migración principal de las
comprobaciones adicionales del software. R, M y B conservan sus funciones;
H combina R y M. **EquiFrame Verify (O)** mantiene la validación independiente.

El cierre del capítulo 2 presenta el vacío dentro de los trabajos revisados,
sin afirmar la inexistencia universal de antecedentes. Se conserva el
desarrollo teórico previamente contrastado y las 61 referencias, cuyos
registros bibliográficos son idénticos a los de la entrega anterior.
La existencia de esas publicaciones se verificó en fuentes responsables;
la ampliación se sustentó en 24 fuentes con alcance de lectura registrado.
Eso no equivale a haber leído íntegramente todos los libros citados.
[Registro de la ampliación](THESIS_UPDATE_20261002.md).

## Respuesta a las observaciones

| Punto y página del PDF | Tratamiento en la entrega | Condición pendiente |
|---|---|---|
| 1, p. 1: título | Quince palabras y método explícito | Aceptación institucional |
| 2, p. 1: problema científico | Una migración, tres familias y pregunta contrastable | Evaluación real |
| 3, p. 1: impacto académico | Conocimiento sobre condiciones y límites del híbrido | Observaciones del experimento |
| 4, p. 1: alcance estadístico | Observabilidad, dependencias y exclusiones explícitas | Suficiencia e independencia justificadas |
| 5, p. 1: objetivos | Cinco objetivos académicos; figura y tabla sincronizadas | Cumplimiento experimental |
| 6, p. 1: vacío al cerrar la revisión | Cierre acotado al conjunto de trabajos revisados | Revisión de tutoría |
| 7, p. 1: aporte más allá del software | Se separan instrumento y conocimiento; una ganancia nula es válida | Contraste de hipótesis |
| 8, pp. 1–2: más de 10.000 registros reales | Adjudicaciones originales identificables por `ocid` y `award.id`, sin inflar versiones | Adquisición e inventario verificable |
| 9, p. 2: intercambio de montos | Un perfil idéntico no permite a M/B recuperar la asociación perdida | Corpus y casos revisados |
| 10, p. 2: publicación de 2025 | Procedencia, cohorte y exclusiones previstas | Snapshot real y cobertura efectiva |
| 11, p. 2: viabilidad y cronograma | Una migración, tres familias; doce semanas por fases | Disponibilidad efectiva de datos y responsables |
| 12, p. 2: capítulos y tutor | Solo 1–3; tutor indicado como pendiente | Designación o confirmación del tutor |
| 13, p. 2: independencia | Esperados, doble revisión, conflictos y grupos de procedencia | Revisiones y reproducción por otra persona |

El requisito de más de 10.000 adjudicaciones no se confunde con perfiles,
mutantes ni muestras independientes. Las cantidades de escenarios por
partición y familia quedan **por fijar** antes del sello experimental.
Los datos no se corrigen manualmente según la respuesta del detector:
transformaciones, exclusiones y problemas de origen deben conservarse con
procedencia. Tampoco se atribuye a la publicación OCDS acceso directo a bases
operativas sin preparación previa.

Si dos salidas tienen el mismo vector, M y B no distinguen un intercambio de
montos que conserva sus estadísticas. La comparación independiente del
contenido conserva ese caso como límite observable. Cualquier cambio de
variables exige selección y comprobación antes de abrir la prueba.

## Formato y estructura

Se incorporan las cuatro secciones institucionales de certificación, derechos,
confidencialidad y aprobación, sin firmas ni aceptación atribuida. No se
inventan tutor, agradecimientos o dedicatorias. Resumen y abstract ocupan
una página cada uno. El índice de tablas precede al de figuras, como en el modelo.

Se mantienen Times New Roman 12, doble espacio, márgenes de una pulgada,
jerarquía de títulos, números de página, títulos y notas de tablas/figuras,
atribuciones y bibliografía con sangría francesa, cursivas y DOI/enlaces según
APA 7. A4, portada institucional, numeración de capítulos y paginación continua
son adaptaciones del formato de la tesis; no se atribuyen a una regla general
de APA.

| Parte | Página física comprobada |
|---|---|
| Resumen / abstract | 6 / 7 |
| Índice general | 8–10 |
| Índice de tablas / figuras | 11 / 12 |
| Capítulo 1 / 2 / 3 | 13 / 26 / 72 |
| Referencias | 124–130 |

Los índices contienen **97 destinos enlazados**: 65 generales, 17 tablas y
15 figuras. Todos los números impresos coinciden con el mapa de páginas de Word.

## Verificación y entrega

Word 16 abrió la candidata en lectura y generó un PDF de 130 páginas sin
cambiar el DOCX. Las cuatro revisiones cubren las 130 imágenes de
2234 × 3158 píxeles: 62 inspecciones nuevas a resolución original y 68
reutilizaciones exclusivamente por identidad de bytes con PNG previamente
inspeccionados personalmente. La comprobación agrega hashes, cobertura sin
omisiones ni duplicados y recibos anteriores; no usa una muestra de páginas.
La revisión visual terminó sin problemas materiales.

Dos controles estructurales verifican capítulos, índices, referencias,
objetivos, tablas y figuras. Frente al Word anterior solo cambian
`word/document.xml` y las imágenes 4 y 5; los demás miembros del paquete,
incluidos relaciones, estilos, encabezados, pies y otros medios, permanecen
idénticos. Se comprobó específicamente el PNG realmente embebido en la Figura 5.
La copia entregada conserva exactamente los bytes del candidato revisado.

SHA-256 de la entrega:

```text
ff638dff604fbe30179fa463b5e3c9440028f23fec0f114c55d4eac8f63246a2
```

Comprobante agregado de calidad, SHA-256:

```text
125c56ef3ca53f4ff2a3f723d8d758b0198746b633416f6c1235981a5d698b71
```

Destino: `C:\HT\maestria datos\tesis\tesis_final.docx`.
Respaldo de fuentes, entrega, PDF, imágenes, planes y recibos:
`C:\HT\maestria datos\tesis\revision_tesis_final_20261003`.

El capítulo 3 recoge evidencia técnica del paso 10: núcleo 0.9.0 con 726 pruebas
aprobadas y benchmark 0.10.0 con 437 aprobadas y dos omisiones por enlaces
simbólicos en Windows. El ejemplo sintético conserva seis casos y seis CSV
regenerados, con cero etiquetas confirmadas. Es verificación del software,
sin confirmación de H1–H3, integración real del DW ni aprobación humana.
[Informe técnico](STEP_10_REVIEW.md).

Corpus, cliente, DDL/mapeos, inventario científico, revisores, calibración,
grupos suficientes y reproducción independiente siguen pendientes. Los
formularios requieren tramitación real. PyPI no se ha publicado; licencia,
control del nombre y evidencia nueva de plataformas permanecen abiertos.
Actions continúa desactivado por la cuota; esta entrega no consume ejecuciones
remotas ni atribuye a CI los controles locales.
