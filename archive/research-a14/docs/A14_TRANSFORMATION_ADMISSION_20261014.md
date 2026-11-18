# A14: admisión de transformaciones y presupuestos explícitos

El núcleo valida al construir las implementaciones nativas la identidad,
revisión positiva estricta y versión textual. Cada clase conserva su motor fijo;
Pandas/Polars requieren callbacks invocables y DuckDB SQL Unicode no vacío,
sin NUL ni surrogates inválidos. La construcción no llama código ni importa
motores. El SQL válido permanece intacto: no se recorta ni se normaliza.

`RunContext.check_table` exige booleanos en `output` y `enforce_rows`. Una cadena
como `"false"` o un número como `0` no pueden cambiar o desactivar el presupuesto
de filas por su valor de verdad. El `False` explícito mantiene su significado
documentado y no desactiva el límite de bytes. Las etapas de medición se validan
antes de entrar en el trabajo o modificar su contexto.

La primera prueba de fuente detectó una incompatibilidad evitable: la nueva
validación de revisión envolvía `ValidationError` como `InvalidExecutionInput`.
Se conservó la clase histórica y se ocultó el valor de entrada en su mensaje.
Ese intento fallido se mantiene separado. La fuente final pasó **189 pruebas**,
incluyendo controles de admisión, presupuestos y operaciones nativas válidas.
Mypy comprobó 89 archivos sin errores y Ruff pasó sobre los cambios.

[revalidate_transformation_runtime.py](../tools/revalidate_transformation_runtime.py)
fija los inputs y esperados antes de ejecutar, requiere un intérprete aislado
ligado al wheel completo y acredita únicamente IDs nuevos. Los positivos
registran y ejecutan la transformación real, conservando tres filas, incluida
una duplicada; los negativos exigen el error declarado antes de llamar código
o crear salida. Importar el tipo no acredita su API operacional.

Estos cambios posteriores al corte `c611a93` necesitan un artefacto y recibos
propios. No se transfieren automáticamente las pruebas ni los 7.593/9.142 IDs
del [candidato anterior](A14_NATIVE_CORPUS_PROGRESS_20261014.md). El objetivo
[90/10](A14_TECHNICAL_90_METHOD_20261013.md) sigue vigente y todavía no acredita
los siete rubros al 90 %. Corpus, etiquetas, `N_fit`, freeze científico y
revisión externa mantienen sus controles separados. No se publicó en PyPI ni
TestPyPI y no se modificó la entrega de la tutora.
