# Admisión de constructores públicos de Alpha A13

El lote v2 ejecutado acredita **51 obligaciones únicas nuevas**: 27
representantes admitidos, 13 argumentos por defecto realmente omitidos y
11 valores finitos explícitos. La unión es **6.188/8.385 = 73,7984496124 %**.
Faltan **940** IDs para ≥85 %, **1.359** para ≥90 % y **2.197** para 100 %.

Los oráculos completos de atributos se congelaron antes de ejecutar sobre
el wheel A13 instalado fuera de fuente. Las clases cubiertas son `ArrowInput`,
`PandasInput`, `PolarsInput`, `ArtifactInput`, `LoadedTable`, las tres
`Transformation`, `ValidationIssue`, `LocalArtifactStore` y `ParquetDestination`.
Pydantic permanece fuera de los IDs de parámetros de constructor del inventario.

Cada objeto conserva todos sus atributos esperados. Las referencias a tablas,
frames, callbacks y metadatos se verifican por identidad. Las rutas se comprueban
por su resolución absoluta y tipo concreto. Los valores y tuplas conservan
tipos recursivos exactos; `2.0` no satisface el esperado entero `2`.
Los valores `None` explícitos no acreditan una clase representativa no nula.
No se infiere ejecución de callbacks, transporte, persistencia, APIs completas,
métodos ni rechazo de tipos a partir de estas construcciones.

Los 25 recorridos por modalidad contienen **19 configuraciones distintas** y
seis repeticiones internas. Sus 75 enlaces se reducen a **51 IDs**, contados una
sola vez entre ejecución normal y optimizada. Tres guardias por modalidad
comprueban atributos ausentes/adicionales, identidad y tipos exteriores e
interiores. Los intentos v1 se conservan sin crédito porque su instrumento no
comprobaba tipos dentro de tuplas; la corrección tiene fuente y recibos propios.

La revisión de «mi dot» es IA de solo lectura. Los
[resultados y fuentes](OPTION_CONSTRUCTORS_RESULT_20261012.json) conservan
sus hashes. El archivo privado sellado contiene 20 archivos, lectura completa
verificada y SHA-256
`8c0de8bbd6726fa8d8cd3b405d892b876dd729faba69e6352962a2b6996d99a6`.
Madurez y requisitos científicos de tesis conservan sus puntuaciones.
