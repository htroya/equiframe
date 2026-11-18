# Trazabilidad de llamadas públicas con oráculos originales

El núcleo instalado **0.12.0a13** alcanza **6.045/8.385 = 72,09 %** de
obligaciones verificadas. Este lote añade **71 IDs distintos** a los 5.974 del
[corte anterior](OPTION_PROPERTIES_RESULT_20261012.md). Para alcanzar al menos
el 85 % faltan **1.083 IDs**, hasta 7.128/8.385. No se cambia el inventario.
El [resultado JSON](OPTION_TEST_CALLS_RESULT_20261012.json) vincula fuentes,
recibos, pruebas y sus hashes.

| Evidencia | Resultado | Significado |
|---|---:|---|
| Planes de llamadas / nodos originales | 83 / 75 | Selección estática anterior a las ejecuciones calificadas |
| Pruebas parametrizadas seleccionadas | 375 PASS normal; 375 PASS con `-O` | Repetición del mismo conjunto; cero fallos, errores o saltos |
| Recibos de llamadas por ejecución | 399 | 330 PASS; 63 con oráculo excluido; 6 sin llamada observada |
| IDs nuevos | **71** | 10 de API, 40 de valores por defecto, 19 de representantes admitidos, 2 de valores finitos explícitos |
| Guardias del arnés | 10 PASS en cada modo | Comprueban atribución y exclusiones; añaden cero IDs |
| Archivos originales verificados | 294 | Pruebas, auxiliares y ejemplos idénticos al sdist original antes y después |
| Repetición optimizada | 0 IDs adicionales | Misma unión y observaciones semánticas que la ejecución normal |

Las **8.385 obligaciones** son condiciones del inventario, no 8.385 pruebas
nuevas ni registros de aprendizaje. Los 399 recibos tampoco representan
399 casos independientes: una prueba parametrizada puede llamar varias veces
a una API.

## Qué se comprobó

El [verificador](../tools/option_test_calls_followup.py) ejecuta las pruebas
originales seleccionadas contra el wheel instalado e identificado, fuera del
código fuente del checkout. Conserva el SHA-256 del wheel
`c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23` y compara
su contenido instalado antes y después. Los 294 archivos auxiliares se
cotejan con el sdist
`164b70270344343094dc0a688bf8dbfe20a27112f7227e2f7fe318f085b71935`.

El catálogo congela expresiones literales esperadas tomadas de las pruebas
originales. Para vincular un ID se requiere observar la función pública real,
sus argumentos antes de entrar al cuerpo, el objeto retornado por identidad,
un resultado completo, la llegada a la aserción original y el cumplimiento
de los esperados. Además debe aprobarse toda la prueba original. Un fallo
de la suite invalida el incremento completo.

Los valores por defecto requieren que el argumento haya sido omitido y que
su valor observado coincida con el inventario. Los valores finitos requieren
un argumento explícito y coincidencia exacta de valor y tipo. Los
representantes admitidos requieren validación estricta contra la anotación
del parámetro concreto. Una anotación que no pueda resolverse no añade
ningún ID de admisión. Este lote no acredita nuevos rechazos de tipos ni
omisiones de parámetros obligatorios.

Los controles del arnés rechazan resultados parciales, diccionarios sin un
contrato de finalización, oráculos negativos o ambiguos y funciones con código
parecido pero identidad distinta. Comprueban también la resolución de una
anotación sin depender de anotaciones ajenas y la restauración de los
instrumentos de observación cuando una llamada falla.

## Custodia, repetición y límites

El [recibo de custodia](TRACE_SEMANTIC_CALLS_CUSTODY_20261012.json) identifica
un respaldo privado de **42 archivos y 43 miembros ZIP**, verificados por
lectura completa, SHA-256 y CRC. Incluye catálogo, recibos normal/optimizado,
JUnit, logs, herramientas, entradas previas y los intentos no acreditados.
No contiene credenciales, Word, corpus SERCOP, wheels ni entornos. Los datos
de ejecución completos permanecen fuera de Git; se publican código y agregados.

Los intentos v2–v5 se conservan con **cero crédito incremental**. Comprenden
problemas del arnés y una ejecución interrumpida; no se presentan como
aprobaciones del producto. El intento v5 conserva su log, recibo y hash de
herramienta; su fuente completa no se archivó por separado.

La revisión IA «mi dot» comprobó los recibos, sus hashes, los oráculos, la
unión previa de 5.974 IDs y los 71 nuevos sin solapamientos. Es una revisión
de lectura por IA; no acredita revisión humana independiente ni aprobación
científica. Las aserciones de las pruebas y auxiliares seleccionados se
reescriben con pytest en `-O`; no se afirma que las aserciones de cualquier
ejemplo ajeno a pytest se ejecuten en ese modo.

Esta medición cubre llamadas concretas en Windows/Python 3.12.4. No declara
completa la semántica de todas las API ni toda la matriz de plataformas.
No modifica las mediciones de madurez, tesis, publicación o adopción.
La [matriz vigente](PROJECT_STATUS_MATRIX_20261011_EIGHT.md) conserva los otros
siete rubros y sitúa el promedio en **70,74 %**. El Word permanece intacto.
