# A14: controles nativos del corpus y lectura protegida

EquiFrame sigue en Alpha privada. Este avance conserva el método
[90/10](A14_TECHNICAL_90_METHOD_20261013.md) y los controles pendientes.
No declara siete rubros al 90 % ni evaluación científica terminada.

## Candidato comprobado

Corte `0249285cca2a5f4b26bef990ae496908834717c6`, wheel del núcleo SHA-256
`760c5f98d4684d2e8d16c1ac1e012f5a568f2ffe51b2dc0b96336138bd63ef15`.
Las instalaciones privadas conservaron resolución normal de dependencias,
`pip check` y comprobación de todos los archivos instalados contra el wheel.
Benchmark y cliente conservaron sus artefactos identificados anteriores;
no se presentan como reconstrucciones de ese corte.

| Suite del candidato identificado | Aprobadas | Omitidas | Fallidas |
|---|---:|---:|---:|
| Núcleo Windows, Python 3.12 | 8.253 | 69 | 0 |
| Núcleo Linux ARM64, Python 3.12 | 8.290 | 32 | 0 |
| Benchmark Linux con ese núcleo | 636 | 3 | 0 |
| Cliente y herramientas seleccionadas en Linux | 183 | 0 | 0 |

Los XML conservan cada omisión. Los intentos anteriores y el fallo de `f5c898d`
siguen separados: una ruta ocupada por un archivo ordinario debía mantener su
clase de error del sistema operativo. La corrección pasó ambas suites completas.

La unión concordante de recibos normales y optimizados del mismo wheel acredita
**7.511/9.142 obligaciones**, con **1.631 pendientes**. Los grupos disjuntos
son 6.201 del inventario raíz, 307 contextuales, 33 de artefactos, 89 de fábricas
de contratos, 177 de operaciones nativas y 704 de EDA. Con el bloque manual
sin acreditar, trazabilidad obtiene **73,9433 puntos** y le faltan **16,0567 puntos
técnicos** para 90. No es el promedio de los siete rubros.

## Preparación real del corpus

El [compilador anual](../tools/prepare_sercop_cohort.py) preparó 182.277 unidades
candidatas OCID, conservando 183.891 adjudicaciones y registrando por separado
8.342 unidades sin adjudicaciones. El manifiesto privado tiene SHA-256
`7e76a4233e26aaf08b84835fe9c582b7a9464d6ca03f76ae542a78a36c75825b`.
La fuente anual original permanece fijada por
`80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3`.

El [preparador nativo](../tools/prepare_sercop_native_batch.py) consume fragmentos
JSONL verificados, sin releer el ZIP completo por unidad. Antes de ejecutar
comprueba manifiesto, hashes/tamaños, orden fuente, identidades, ausencia,
precisión/escala y revisión pendiente. Los esperados se calculan desde los
objetos fuente y `Counter`; cada motor ejecuta su implementación propia.

Dos lotes disjuntos ejecutaron **288 controles nativos**: 32 OCID × tres familias
× tres motores. Comprobaron ejecución, equivalencia de valores/multiplicidad/
ausencia, reglas de esquema y valores de los perfiles. El segundo lote utilizó
archivo comprimido por unidad: conservó 31.644.789 bytes de evidencia en unos
6,21 MB de salida y 18 archivos, frente a 3.458 archivos del primer lote.
Las 26 pruebas del preparador final pasaron en Windows y Linux, incluidas
alteración de archivo y conservación del original ante una compresión inválida.

Los lotes admiten hasta 256 unidades, salida de 1 GiB y reserva de disco de
2 GiB. `--compact` verifica todos los bytes archivados antes de retirar sólo
el directorio temporal generado dentro del lote. Conserva inputs, ZIP original,
otros lotes y entrega pública. El inventario registra el prefijo original para
restauración acotada; no ofrece URI archivadas como archivos vivos ni como un
bundle portátil. La salida anterior nunca se sobrescribe.

Se ejecuta con un intérprete privado identificado, `-I` y directorio actual fuera
del checkout. Requiere `--cohort`, `--manifest-sha256`, `--binding`, `--output`,
`--offset` y `--count`. El manifiesto y todos los fragmentos se vuelven a verificar
al terminar. Los datos privados no se incorporan a Git.

`--min-awards` propone explícitamente un mínimo de adjudicaciones por unidad
para controles de ingeniería de multiplicidad; el default 1 conserva todos los
candidatos. Offset/cantidad se aplican a ese subconjunto en orden fuente, sin
selección por resultados. No redefine una cohorte científica. Los preparadores
usan `timezone.utc`, disponible en Python 3.10; esta compatibilidad de fuente
se distingue de las instalaciones y motores realmente ejecutados.

Los perfiles continúan **UNREVIEWED** y `N_fit` acreditado es cero. Las
dependencias conservan OCID y plantilla compartida por familia; no se renombran
para crear particiones. Los dos lotes sólo tienen una combinación numérica de
perfil por familia. Una cantidad de unidades o de repeticiones no acredita
normalidad, independencia, calibración/test, etiquetas O ni entrenamiento final.

## Correcciones posteriores a ese artefacto

`read_detector_bundle` y `read_comparison_report` usan apertura protegida de
archivos ordinarios. Rechazan FIFO, enlaces, directorios y puntos de reanálisis
antes de leer, conservando límites y formatos declarativos. La publicación de
reportes comprueba ancestros en Windows y admite padres ordinarios.
Las regresiones de fuente pasaron **148 pruebas**, con 24 omisiones de plataforma.
Estas correcciones necesitan su propio artefacto y recibos de instalación;
las suites anteriores pertenecen exclusivamente al wheel identificado.

[revalidate_literal_runtime.py](../tools/revalidate_literal_runtime.py) amplía
la comprobación de llamadas reales usando pruebas y todos los auxiliares
originales ligados al sdist A13. Sólo acredita IDs si observa las aserciones
literales sobre el retorno real, el resultado completo y la prueba original
entera aprobada. Fija el catálogo antes de ejecutar y conserva el wheel A14
utilizado. No infiere cobertura desde imports, retornos no estimables o fallos.

Los expedientes privados se conservan en `a14_review_fixes_20261013` y en el
directorio de validación de la VM. No se publicaron paquetes, no se ejecutó el
workflow TestPyPI y la entrega de la tutora conserva su función de consulta.

## Revalidación posterior del núcleo corregido

El artefacto del corte `c611a93ea1dc80cb0ffce10ca23b6b38c3f6ef26` incorpora las
correcciones de lectores y publicación descritas arriba. Su wheel tiene
SHA-256 `308bbbe9f647b825ad66aa11d9e2cebeb7f0b045ca449af9dd658ee0ba5fc9a4`.
Pasó 8.259 pruebas del núcleo en Windows (74 omitidas) y 8.298 en Linux ARM64
(35 omitidas), sin fallos. Benchmark en Linux pasó 636, con tres omisiones;
cliente y herramientas seleccionadas pasaron 209. Los ejemplos de documentación
y `twine check --strict` pasaron sobre los artefactos privados identificados.

Los 300 OCID del corpus anual que contienen múltiples adjudicaciones se
ejecutaron en dos lotes acotados: **2.700 controles nativos**. La recomputación
interna verificó 300 archivos ZIP, **64.800 miembros**, 1.914 importes y todos
los outputs/perfiles frente a los objetos fuente, conservando precisión y escala.
Observó 30 vectores numéricos distintos por familia. No es una revisión externa
ni confirma normalidad, independencia estadística o `N_fit`; éste continúa cero.

La reproducción de 395 pruebas originales, tanto normal como con `-O`, acreditó
42 IDs nuevos sobre este wheel. Sus aserciones literales y auxiliares se
conservaron, y los recibos semánticos concordaron entre modos.

Otras **40 obligaciones** corresponden a presencias y ausencias reales de los
once requisitos y nueve grupos de extras. En una copia privada se desinstaló
un requisito por vez, se comprobó su fallo esperado en ambos modos, se restauró
con resolución normal de dependencias y se ejecutó `pip check`. Las operaciones
positivas verificaron filas nativas, ajuste técnico sintético/score MAD y EDA
con/sin gráficos. Un grupo ausente significa que falta un miembro requerido y
su operación no queda disponible; no se infiere que desaparecieron todos sus
miembros. Los entornos previamente acreditados no se modificaron.

El primer instrumento confundió restos de `__pycache__` con un paquete instalado;
se corrigió la preparación de la ausencia retirando únicamente esos cachés
verificados dentro de la copia privada. Otro instrumento esperaba `failed`,
aunque `MissingDependencyError` pertenece a `InvalidExecutionInput`; se corrigió
el esperado a `invalid_input` según el contrato, sin cambiar el SDK. Los intentos
fallidos se conservaron y no se acreditaron.

La unión disjunta del candidato corregido alcanza **7.593/9.142 obligaciones**,
con **1.549 pendientes**. Con el bloque manual todavía sin acreditar son
**74,7506 puntos** de trazabilidad y faltan **15,2494 puntos técnicos** para 90.
No es una evaluación completa de los siete rubros. El expediente consolidado
privado es `root-consolidated-c611a93-literal-dependencies-v1.json`; el recibo de
dependencias y su instrumento están conservados en el ZIP privado
`dependency-runtime-c611a93-receipts-v3.zip`, SHA-256
`73705e6b95bb819462d101b227707edf94b23a167dedb47801138c1e3bcc6fa6`.
