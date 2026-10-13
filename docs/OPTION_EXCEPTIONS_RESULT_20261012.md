# Contratos locales de excepciones: 43 IDs nuevos

La trazabilidad alcanza **6.309/8.385 = 75,24 %**. El lote acredita una vez
20 APIs de excepción y 23 parámetros: trece admisiones, cinco defaults omitidos
y cinco `None` explícitos. Sus [recibos y custodia](OPTION_EXCEPTIONS_RESULT_20261012.json)
conservan los esperados previos y las dos ejecuciones concordantes.

| Familia | Casos por modo | IDs únicos nuevos |
|---|---:|---:|
| Tres excepciones `Contract*` con `ValidationIssue` | 3 | 6 |
| Cinco excepciones de equivalencia, con puntero omitido/nulo/explícito | 15 | 25 |
| Doce excepciones con inicializador C heredado | 12 | 12 |

Los treinta casos verifican tipo exacto, export, `args`, mensaje completo,
código, todos los atributos y jerarquía MRO. Una captura al levantar la misma
instancia comprueba identidad bajo la clase y sus bases declaradas. Las tres
excepciones de contrato almacenan la misma tupla de issues; sus rutas y
mensajes literales se fijaron antes del SDK. Las decisiones de equivalencia
son cuatro fixtures sintéticas coherentes y completas, con verificación JSON.

Los dieciocho casos con inicializador Python observan código, tipo exacto
de `self`, llamador y enlace/default de argumentos. En los doce casos heredados
de C el cuerpo **no es observable**: se registra la invocación directa desde un
helper controlado y se comprueba todo el estado. No se inventan eventos C ni
IDs de `args` ausentes del inventario. Los 63 enlaces se reducen a 43 IDs.

El código de instancia de `EquivalenceEvidenceError` proviene de su decisión
sintética (`evidence_missing` en este lote). `report_path` se presenta en el
mensaje y no se almacena ni se abre; los atributos completos son `decision`
y `code`. Los tres modos de puntero no se cuentan como datasets independientes.

Normal y `-O` pasan los treinta casos con recibos semánticos iguales. El primer
instrumento y sus resultados se conservan; la fuente final sólo añade una
línea en blanco para ordenar importaciones. Se acredita la versión final una
vez. «mi dot» revisó fuentes, oráculos y uniones como IA de solo lectura.

La custodia privada `trace85_excepciones_20261012.zip` contiene trece archivos,
1.756.132 bytes y lectura completa verificada, SHA-256
`a9348fb34c2488ed8178bd363f66a9dd6fa0955f097029ea564ae006eb84cd7d`.
Conserva la custodia anterior de defaults. Quedan **2.076 `NOT_RUN`**, 1.238 IDs
para ≥90 % y 819 para el umbral anterior de ≥85 %.

Construir y levantar estas excepciones prueba su contrato local. No demuestra
fallos operativos reales de IO, motor o comparación, ni aprobación científica
o humana. El SDK y el Word permanecen intactos.
