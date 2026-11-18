# Ampliación comprobada de trazabilidad declarativa

La unión del inventario A13 llega a **5.786/8.385 = 69,00 %**. Este seguimiento
añade **270 obligaciones**: 97 métodos y 173 variaciones de campos. Faltan
**922** para el 80 % solicitado. El numerador no incluye repeticiones, pruebas
sin ejecutar ni superficies inferidas. El
[resultado estructurado de campos](OPTION_LITERAL_FIELD_RESULT_20261011.json)
conserva referencias y hashes de entradas, catálogo, fuentes y recibos.

| Lote | Casos de aserción nuevos | Obligaciones nuevas | Resultado normal y `-O` |
|---|---:|---:|---|
| [Métodos propios](OPTION_METHOD_FOLLOWUP_20261011.md) | 95 | 97 | 95 PASS por ejecución |
| Variaciones de campos | 173 | 173 | 168 PASS y 5 rechazos esperados por ejecución |
| Unión de esta entrega | 268 | 270 | Sin FAIL; repeticiones separadas |

Los casos de método reutilizan 95 fixtures literales previas e incorporan
aserciones nuevas sobre llamada, dueño y retorno. Los IDs de catálogo distinguen
esas aserciones; no representan 95 nuevos inputs ni muestras científicas.
La unión completa contiene 4.906 IDs de casos de aserción del catálogo,
incluidos los históricos. Los dos casos de regresión se mantienen separados.

## Selección y comprobación de campos

«mi_dot» revisó 102 límites declarados y 71 valores finitos o nulos pendientes.
La selección privada identifica modelo, campo, ID, declaración, fuente/hash y
los campos que leen sus validadores, propiedades y helpers resueltos.
Excluye serializers de modelo, acceso dinámico al objeto completo y campos
afectados por invariantes de otros campos. Los callbacks admitidos tienen nombre
calificado y hash de su fuente: no se aceptan solo por llamarse `_text`.

El [ejecutor de campos](../tools/option_literal_field_followup.py) construye cada
input a partir del fixture literal revisado, modificando solo el campo elegido.
Hace lo mismo sobre el esperado JSON completo anterior, con el valor declarado
normalizado y fijado antes de ejecutar. No calcula el esperado validando el
modelo ni consultando una salida del SDK. El catálogo se revisó y congeló por
SHA-256 antes de correrlo.

Las admisiones deben conservar todo el documento esperado, distinguiendo
booleanos y números. Los cinco rechazos previstos son `string_too_short` para
`SnapshotColumn.name`, `SnapshotColumn.physical_type`,
`SnapshotManifest.domain_schema_revision`,
`SnapshotManifest.extraction_revision` y `SnapshotTable.name`.
Todos los errores deben corresponder al campo seleccionado y al código previsto;
un error de otro campo o código permanece `FAIL`.

Los dos ejecutores exigen el wheel A13 original, sus 127 archivos instalados,
el inventario y recibos originales, y rechazan IDs desconocidos, ya verificados
o repetidos. `plan` y `run` reciben rutas explícitas; `--help` documenta los
argumentos. Para `run` se requiere el catálogo congelado y su SHA-256. Las
carpetas de resultados deben ser nuevas. Los catálogos/recibos anteriores
permanecen intactos.

## Validación y límites

La validación se ejecutó en Windows AMD64, CPython 3.12.4, con el wheel privado
`0.12.0a13` identificado. Ambos catálogos nuevos coinciden normal y con `-O`.
Las 26 pruebas de los arneses de métodos, campos y límites pasan en ambos modos;
15 de esas pruebas pertenecen a los dos arneses nuevos de esta entrega. Ruff y
la comprobación de formato pasan. No se afirma que pytest bajo `-O` verifique
aserciones de módulos ajenos a sus tests: los ejecutores usan comprobaciones
explícitas que no dependen de `assert`.

Este incremento acredita metadatos de construcción y métodos declarativos.
Parámetros, propiedades, API/CLI semántica, interacciones y motores restantes
necesitan casos propios. Las repeticiones ARM64 previas corresponden al catálogo
de límites anterior: estos dos lotes nuevos no se ejecutaron en la VM.
No amplían retrospectivamente el snapshot de seguridad sellado.

La [matriz recalculada](PROJECT_STATUS_MATRIX_20261011_RECALCULATED.md) presenta
las nueve cifras con sus versiones. Este incremento no cierra obligaciones
adicionales de madurez, tesis, seguridad, PyPI, calidad, usabilidad o universalidad.
Licencia/titulares, revisiones humanas, aceptación de otros responsables y
evidencia científica conservan sus pendientes. La revisión IA no los sustituye.
No se modificaron SDK, benchmark ni Word, ni se publicaron paquetes o ejecutó
GitHub Actions. No se crearon recursos de pago.
