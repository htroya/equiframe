# Admisión explícita de configuración opcional A13

Se acreditaron **40 obligaciones nuevas** sobre diez pares API/parámetro de
los fixtures originales A13. La unión acumulada es **5.942/8.385 =
70,8646392367 %, redondeado 70,86 %**; faltan **1.186 IDs** para alcanzar
7.128 y cumplir al menos el 85 %. El [recibo](OPTION_CONFIGURATION_RESULT_20261012.json)
conserva fuentes, hashes, intentos y relación con el
[corte anterior](OPTION_SEED_BOUNDS_RESULT_20261012.json).

Los 40 casos comprenden diez rechazos de `False`, cada uno con dos obligaciones
pendientes; veinte admisiones de modelos exactos o `None` explícito, con una
obligación por caso; y diez rechazos de un campo desconocido sin crédito.
Un argumento `None` suministrado explícitamente no acredita la omisión de
un argumento ni su valor predeterminado.

El verificador observa la entrada al código Python exacto de la API, desde su
caller previsto, y la identidad del argumento. Las preparaciones se realizan
antes de la región que puede acreditar rechazo. Los errores deben coincidir
con el título, ubicación, tipo e input esperados. `False` no se confunde con
el entero cero. El profiler se restaura tanto al terminar como ante errores.

Las opciones literales de entrada provienen del inventario congelado. En los
reportes se coteja completa la proyección `ReportViewPolicy` de ocho campos;
no se declara que esa salida contenga todo `ReportOptions`. La captura DuckDB
comprueba la salida literal de una consulta de una fila; las capturas sintéticas
de las otras interfaces no se atribuyen a ejecuciones nativas ni a etiquetas
científicas. Este lote tampoco cierra la semántica general de cada API.

El primer protocolo quedó **FAIL**, con seis casos discrepantes. El arnés
esperaba validación directa de `ComparisonPolicy`, mientras A13 la valida dentro
de `ComparisonSpec`, y esperaba todas las opciones en la salida del reporte.
La revisión de la fuente original corrigió esas dos expectativas. El primer
recibo conserva SHA-256 `06250b1e11f8430e7e72d861c7b0665f8d4bf3d14ec5ec45572a5a81fe01b42d`;
sus 34 obligaciones observadas no se vuelven a sumar al segundo intento.

Antes de repetir se congeló el catálogo v2 con SHA-256
`38e89bc9bdb9e712b32e69701c11854721be022f331a7bc99e8cc9ecb0893e2f`.
El lote completo pasó normal y `-O`, con veinte admisiones y veinte rechazos
esperados en cada ejecución:

| Ejecución | SHA-256 de `result.json` |
|---|---|
| Normal | `d22dfc865013ed0cfe50093353e965e3f3967cea82ca2a6ea7f50fbf7570546c` |
| Optimizada | `e4869bc51b597013a0e48b4719e871a09e09fb6eda1eff78b279dd8a5cb4ed22` |

Seis contrapruebas del arnés pasaron en cada modo. La revisión «mi dot» fue IA
y de lectura; no es aceptación humana. El wheel A13 mantiene su identidad;
la ampliación se encuentra en las herramientas del repositorio.
