# Trazabilidad de métodos declarativos A13

La ejecución normal y optimizada de 95 casos nuevos acredita **97 métodos**
pendientes del inventario original. La unión pasa de 5.516 a **5.613 de 8.385
obligaciones: 66,94 %**. Faltan **1.095** para el umbral de 6.708 (80 %).
El [recibo de medición](OPTION_METHOD_RESULT_20261011.json) identifica inputs,
catálogo, herramientas y resultados privados por SHA-256. El
[corte anterior](OPTION_BOUNDARY_RESULT_20261011.json) se conserva sin cambios.

Los esperados son documentos literales completos del catálogo A13 previamente
revisado y tres fixtures adicionales ya publicados. Se congelaron antes de la
ejecución nueva. No se utilizó una salida del SDK para calcular el esperado.

## Qué demuestra cada caso

El ejecutor [option_method_followup.py](../tools/option_method_followup.py)
valida el documento y observa las llamadas de los métodos declarados. Exige:

1. Código Python idéntico por identidad, módulo, nombre y hash de fuente; dueño
   de la clase exacta, asociado a la instancia raíz finalmente devuelta.
2. Entrada al método y retorno en un opcode `RETURN_VALUE` o `RETURN_CONST`.
   El retorno producido al propagar una excepción no constituye finalización.
3. Los 94 validadores `after` devuelven la misma instancia. Los tres
   serializadores `wrap` producen el documento literal completo esperado;
   su retorno se registra inmediatamente para impedir que una mutación posterior
   oculte una salida incorrecta.
4. La serialización completa del modelo coincide con el JSON literal esperado,
   distinguiendo booleanos de números. Cualquier contradicción permanece `FAIL`.

Se restaura el hook previo de trazado en `finally`. No se reemplazan validadores
ni serializadores del SDK. Las pruebas del arnés comprueban llamadas ausentes,
dueños distintos, excepciones, código estructuralmente igual con identidad
distinta, retorno propio incorrecto y mutaciones posteriores. Los 23 casos del
arnés nuevo y de límites pasan normal y con `-O`; estas ejecuciones repetidas
no se suman como casos independientes.

## Reproducción y alcance

Instalar el wheel privado A13 identificado fuera del checkout. El comando
`python tools/option_method_followup.py --help` explica los argumentos `plan`
y `run`. Ambos reciben el wheel, el inventario y catálogo originales, el recibo
base ejecutado y los incrementos de operaciones y límites. Sus hashes están
fijados en el ejecutor. `plan` escribe un catálogo nuevo con apertura exclusiva;
`run` exige su SHA-256 y verifica que coincide con esos inputs literales.
Guardar resultados en carpetas nuevas; para repetir, usar `python -O` y otra
carpeta. No sobrescribir los recibos conservados.

Este corte se ejecutó en Windows AMD64, CPython 3.12.4, contra los 127 archivos
del payload A13 cotejados con el wheel original. No se declara ejecución Linux
de este catálogo nuevo: las repeticiones ARM64 anteriores corresponden al
catálogo de límites de 1.054 casos.

La evidencia demuestra ejecución positiva de métodos declarativos. No acredita
todas sus ramas, parámetros, interacciones, operaciones nativas ni resultados
científicos. «mi_dot» revisó selección y arnés como agente IA; la revisión humana
continúa pendiente. Las herramientas nuevas están fuera del snapshot de
seguridad sellado. El núcleo, benchmark, artefactos A13 y Word no se modificaron.
