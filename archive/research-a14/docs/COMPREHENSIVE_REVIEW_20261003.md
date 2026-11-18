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
| G04 | JSON expandido o fallo CSV/Unicode/JSON tras agotar max_records | La lista se creaba antes del límite; el manejador de error podía excederlo al registrar rechazo | Presupuesto durante expansión y antes de añadir cuarentena por fallo del parser; límite exacto válido conservado |
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

Fuente final comprobada: **`0721b562927dbd99c4d030bdb48c16e5189ffca1`**.
Los commits posteriores de documentación no cambian los bytes de los paquetes.
Entorno ejecutado: **Windows x64 / Python 3.12.4**, `uv 0.11.6`, dependencias
del lock, `PYTHONUTF8=1`. Núcleo y benchmark se comprobaron en paralelo; las
duraciones son tiempos de validación local, no mediciones aisladas de rendimiento.

| Control final ejecutado | Núcleo 0.11.1 | Benchmark 0.11.1 |
|---|---|---|
| Sync locked, Ruff, formato, mypy y assets | Cinco controles, todos exit 0 | Cinco controles, todos exit 0 |
| Suite completa de fuente | **1041 passed, 1 skipped**, 773.80 s | **454 passed, 2 skipped**, 675.47 s |
| Construcción wheel/sdist | Exit 0, 20.83 s | Exit 0, 13.84 s |
| Twine estricto sobre los dos archivos exactos | Exit 0 | Exit 0 |
| Suite instalada fuera del checkout | **1041 passed, 1 skipped**, 722.64 s | **454 passed, 2 skipped**, 687.82 s |
| Verificador completo de distribución | Exit 0, 1052.61 s | Exit 0, 851.92 s |
| Manifiesto ligado a fuente/artefactos | Nueve etapas completas, cero faltantes/no vinculadas/fallidas | Nueve etapas completas; incluye wheel exacto del núcleo |

Hay **1495 pruebas aprobadas** en las dos suites de fuente, repetidas desde
instalaciones externas; no se suman esas repeticiones como casos nuevos.
Las tres omisiones corresponden exclusivamente a creación de enlaces simbólicos
sin privilegios en esta cuenta Windows. El núcleo omite una prueba de bundle;
el benchmark, una de freeze y otra de reproducción. No son fallos del producto
ni acreditan haber ejecutado esas ramas en esta cuenta.

El verificador del núcleo comprueba base y seis extras, import ligero, API/CLI,
consumidor tipado, ejemplos nativos/ETL/Verify y reconstrucción byte a byte desde
sdist. El benchmark comprueba instalación de ambas distribuciones, API pareada,
su ejemplo JSON dentro de la suite instalada, piloto nativo, integración,
evaluación y reproducción de seis CSV, además de wheel idéntico desde sdist.
Los ejemplos negativos mantienen diferencias, alertas o estados parciales
previstos; que el verificador termine 0 no convierte esos datos en correctos.
El piloto conserva 35 revisiones pendientes y ninguna etiqueta confirmada.

Las evidencias detalladas quedan fuera de Git en
`revision_global_equiframe_20261003` del workspace de tesis:
`core-final-complete/checks.json`, `benchmark-final-complete/checks.json`, sus
logs, `software-evidence-final.json`, `core-manifest-final.json` y
`benchmark-manifest-final.json`. Los manifests registran `published=false`;
licencia, nombre/Trusted Publisher, acceso y publicación conservan sus cuatro
bloqueos externos. Los recibos no autentican identidad o ejecución externa.

| Recibo final | SHA-256 |
|---|---|
| Núcleo checks.json | `b56685aca97349b6ccae60d43a77d5325850ea164bd7773bba81dd20e496aeb2` |
| Benchmark checks.json | `ec335a4bf6929730132899277365c35c48834951be9832484abee738f05cc7e7` |

| Artefacto final local | SHA-256 |
|---|---|
| equiframe-0.11.1-py3-none-any.whl | `5f0deb33f200b59e62fee3c3a2dcfb62cf3362eede546f264594c24662a3a1b9` |
| equiframe-0.11.1.tar.gz | `70ed4b1efc1934e27395c2b62a6f7a75d7afc6d866c76b3425b78b20a14b59bf` |
| equiframe_benchmark-0.11.1-py3-none-any.whl | `8e2b06aa6139c9e3d08506fe5f74b78684bd288637f6e6d7f9e3f8b8ef152b7d` |
| equiframe_benchmark-0.11.1.tar.gz | `4065387c2f167ea44bb38ff621339afdab431e7775e9b1a4dcb6d8346503ac48` |

Las versiones 0.11.0 y sus informes siguen conservados. No se activaron jobs de
GitHub Actions, publicación PyPI ni despliegues de infraestructura en esta ronda.

La revisión cruzada reprodujo además el exceso de presupuesto al rechazar un
CSV mal formado. Cinco de siete casos adicionales fallaron antes del arreglo;
los dos restantes verifican la frontera válida. La ronda posterior aprobó
53 pruebas de ingestión/regresiones. Los primeros controles completos fueron
interrumpidos para reiniciarlos sobre los bytes corregidos; sus recibos parciales
se conservan y no se presentan como suites completas aprobadas.

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
