# Revisión integral de EquiFrame 0.11.1

Fecha de referencia del usuario: **2026-10-03**, `America/Guayaquil`.
Baseline: `6666d8622911768548287045397e727c58e9ef88`, núcleo y benchmark 0.11.0.
La revisión trabaja sobre esa entrega, la tesis vigente y las actividades ya
comunicadas a José y Jhair. Las fuentes y su preservación están en la
[matriz de alcance](COMPREHENSIVE_REVIEW_SCOPE_20261003.md).

## Resultado de ingeniería y alcance

El candidato 0.11.1 conserva la API operacional, seis direcciones nativas entre
Pandas/Polars/DuckDB, Verify, ETL local, comparación, R/M/B/H, evidencia y
reproducción. Corrige defectos reproducidos y añade análisis descriptivo de
soportes pareados. No reemplaza versiones ni expedientes previos. Los locks
solo cambian las versiones locales del núcleo/benchmark; mantienen las
dependencias resueltas del candidato anterior.

Las tres familias científicas siguen siendo `nulls_types`, `joins` y
`aggregations`, cruzadas con las tres parejas principales: nueve estratos.
Las cinco familias técnicas de perfiles no se convierten en muestra científica.
R/M/B/H/O mantienen su independencia, entradas, autoría y responsabilidades.

José mantiene VM Ubuntu/Python 3.12, acceso, cliente y servicio compartido;
Jhair mantiene datos originales, modelo/mapeos/carga y reconciliación del DW;
Hernán mantiene biblioteca y evaluación. Se conservan todas las catorce
actividades de las guías, incluida la flexibilidad de proveedor que consta
en el Word de José. No se modifican sus carpetas ni se simulan sus entregas.

## Hallazgos corregidos

| ID | Componente y reproducción | Impacto anterior | Tratamiento y regresión |
|---|---|---|---|
| G01 | Ingestión/IR/Pandas/Polars con contexto decimal externo de precisión baja, Emax=9 y traps activos | Dinero exacto válido podía fallar; pérdida de escala podía escapar de cuarentena | Contexto decimal propio para aritmética acotada, sin cambiar contexto/flags del consumidor; `test_review_core_limits.py` |
| G02 | SUM decimal R con totales exactos grandes, correcto y distinto por un centavo | Reglas convertidas en no evaluables por configuración ajena | Contexto independiente conservando precisión R=1000; ambos resultados mantienen su decisión |
| G03 | SUM vacío Polars Decimal(20,20) bajo Emin externo reducido | Resultado cero correcto modificaba flag Clamped del consumidor | Construcción exacta de cero mediante tupla Decimal, sin aritmética ambiental |
| G04 | JSON con arreglo expandido mayor que max_records | La lista completa se creaba antes de comprobar el límite | Presupuesto restante y comprobación cooperativa durante recorrido, antes de convertir registros |
| G05 | Tokens numéricos JSON con exponente fuera de rango de Decimal | InvalidOperation eludía rechazo/cuarentena | Diagnóstico `json_decimal_outside_supported_range`, con documento original conservado |
| G06 | Bundle científico con conteos inventados y hashes recalculados coherentemente | Reproducción podía aceptar metadata incompatible con filas reales | Recomparación con opciones congeladas/reference peer; conteos, estrategia y clave deben concordar |
| G07 | Inventario no vacío de diferencias ligado a O equivalente | Selección normal pública podía admitir evidencia contradictoria | Recuento físico y contraste con ComparisonCounts antes de entrenamiento/calibración |
| G08 | Tipo de Candidate distinto del tipo declarado por OracleResult | Puente Verify aceptaba clasificación incompatible | Rechazo explícito de candidate_kind diferente |
| G09 | Recibos anteriores tras modificar fuente o reemplazar wheel/sdist | Etapas exitosas podían atribuirse a bytes nunca comprobados | Huellas de fuente antes/después, inventario de artefactos y wheel de dependencia local; etapas sin vínculo bloquean candidato |
| G10 | CONTRIBUTING y tablas vigentes con CI automática, pareja única y mínimo de adjudicaciones | Instrucciones incompatibles con configuración y tesis actuales | CI manual explícita; tres parejas; N efectivo de aprendizaje; cuotas históricas retiradas de metas vigentes |

Las regresiones distinguen fallos reproducidos de controles que ya funcionaban.
No se afirma que todos los casos nuevos fallaran en el baseline: DuckDB ya
resolvía la aritmética probada; el test de cancelación establece la comprobación
interna nueva. Un intento inicial de test usó `null_groups=keep` inválido y se
corrigió a `retain`; ese error del test no se presenta como defecto del producto.

## Ampliación útil sin cambiar el experimento anterior

`evaluate_pairwise` devuelve un `PairwiseReport` estricto que conserva el informe
de origen y sus digests. Cada uno de los seis pares R/M/B/H usa O confirmado y
ambos componentes completos; aporta conteos TP/FP/FN/TN, métricas, cobertura,
denominadores por clase, alertas exclusivas por dirección y exclusiones visibles.
Mantiene estratos declarados vacíos y alerta H parcial fuera del soporte completo.

El caso B ausente muestra su utilidad: R–H puede tener soporte válido aunque la
intersección común R/M/B/H esté vacía. La ausencia de B no borra ese contraste ni
se convierte en decisión normal. La intersección histórica sigue disponible.

El reporte es **complementario y descriptivo**, `scientific=false`. No añade
bootstrap, AP ni tests de hipótesis. Se exporta JSON explícitamente; los seis CSV
y el protocol_sha256 anterior permanecen iguales. Adoptarlo como análisis
principal exige revisar y congelar un nuevo protocolo antes de observar prueba.
[API, denominadores y ejemplo](PAIRWISE_EVALUATION.md).

## Validación de la entrega

Las rondas focalizadas acreditan comportamientos concretos, sin sumarse como
cobertura independiente: núcleo 232 pruebas en la revisión amplia inicial;
68 en ingestión/R/regresiones finales con catálogo excluido hasta regenerarlo;
benchmark 56 en selección/calibración/estudio/bundle/puente; reporte pareado y
evaluación/tablas 66. La prueba de catálogo regenerado aprobó por separado.

Las suites completas y controles finales del candidato se registrarán aquí
al concluir su ejecución. Las evidencias detalladas quedan fuera de Git en
`revision_global_equiframe_20261003` del workspace de tesis. Un resultado de
fuente no se atribuye a una instalación limpia hasta ejecutar su verificador.

## Compatibilidad, impacto y límites

Formato original 1.0 conservado; DetectorVersions admite 0.11.1 además de los
productores anteriores. El reporte pareado tiene su esquema propio. No se
amplía el soporte declarado más allá de Python 3.12 ni se afirma que los rangos
de dependencias completos hayan sido probados. La matriz remota sigue manual;
su configuración no prueba otra plataforma.

La huella de R cambia por su corrección real; se regenera el catálogo. Un estudio
congelado con la huella anterior conserva sus bytes y revisión, y no puede
atribuirse a R corregida sin nueva evidencia/congelación. Es una corrección de
ingeniería, sin modificar las seis formas de regla ni ajustar criterios de
aceptación con resultados de prueba.

JSON sigue parseándose completo bajo max_source_bytes; max_records limita la
expansión y los controles de tiempo/cancelación son cooperativos. No se promete
RSS duro, ejecución distribuida, traducción arbitraria de programas ni resume.
La publicación Parquet es local y no reemplaza las garantías del gateway de José.

Los hashes vinculan bytes, sin autenticar personas, independencia de O ni
procedencia de construcción. Corpus efectivo, revisiones humanas, modelos del
experimento, aceptación del tutor, integración real DW/VM y publicación PyPI
conservan sus entregables externos. Esta revisión no crea datos ni aprobaciones.

## Continuidad y alcance máximo defendible

| Frente | Disponible tras esta revisión | Requisito para ampliar alcance |
|---|---|---|
| Reutilización local | Contratos/ejecución/Verify/ETL/bundles y consumidores de paquetes | Nuevos tipos/operaciones necesitan capacidades y casos independientes por motor |
| Evidencia experimental | Catálogo, selección, congelación, evaluación histórica y reporte pareado | Corpus trazable, O revisado, grupos/soporte válidos y protocolo nuevo si cambia el estimando |
| Integración de equipo | Puertos y pruebas consumidoras, guías conservadas | Cliente/gateway real de José y DDL/mapeos/snapshots de Jhair; aceptación compartida |
| Profesionalización | API tipada, esquemas, locks, distribución y recibos ligados a bytes | Consumidor independiente y matriz de plataformas realmente ejecutada |
| Distribución pública | Candidato privado identificable | Licencia, titularidad/nombre, acceso/documentación y encargo expreso de publicación |

La ampliación avanza por capacidades comprobables y conserva decisiones
pendientes con responsable; no aumenta requisitos comunicados a compañeros ni
afirma completar pasos 11–20 por una sola revisión local.
