# Ejecutar pruebas con trazabilidad por opción

El kit manual se compone de `option_inventory.py`, `option_trace.py`,
`catalog-a12.json` y el wheel privado identificado A12. Las herramientas están
en `packages/equiframe/tools`; el catálogo sintético versionado está en
`packages/equiframe/tests/fixtures/option_trace`. No activa Actions.

Instale normalmente el wheel privado en un entorno aislado **fuera del checkout**.
Para este catálogo basta la instalación base. Use el intérprete de ese entorno
y rutas explícitas; `-I` impide depender accidentalmente del directorio fuente.

```text
python -I option_inventory.py --wheel equiframe-0.12.0a12-py3-none-any.whl --commit 8df0173b98398e2a4f3ef3c5e8216f079a541922 --output inventory.json --matrix obligations.json
python -I option_trace.py --inventory inventory.json --matrix obligations.json --catalog catalog-a12.json --wheel equiframe-0.12.0a12-py3-none-any.whl --output run-new --minimum-percent 50
```

Wheel SHA-256:
`1d769926f3003686a0b728cebc6163c939e5b33f7278b86182877b816b8a3c88`.
El commit de arriba identifica la fuente del SDK de ese wheel. Las herramientas
de auditoría nuevas se identifican separadamente mediante sus hashes en el recibo
y los commits de esta entrega. No se reemplazan los artefactos A12 anteriores ni
se declara una publicación en PyPI.

El primer comando verifica cada archivo instalado contra el wheel y descubre
las obligaciones. El segundo vuelve a verificar la identidad, el inventario y
los enlaces; después ejecuta todos los casos y guarda `receipts.json` y
`result.json` en un directorio nuevo. No acepta nombres duplicados, JSON NaN,
inventarios recortados, recibos duplicados o enlaces a opciones ajenas. Conservar
un directorio anterior es obligatorio: otra ejecución necesita un nombre nuevo.

El código de salida es 0 cuando no hay filas FAIL y se alcanza la meta; 1 si
hay fallos o falta cobertura. Un catálogo/artefacto inválido o un destino ya
existente se rechaza antes de contabilizar casos. Las comprobaciones del ejecutor
usan condiciones explícitas y conservan su efecto con `python -O`.

La fórmula es `(PASS + EXPECTED_REJECTION) / todas_las_obligaciones_del_núcleo`.
Los rechazos esperados acreditan una validación correcta, no la aceptación de
datos inválidos. Los casos repetidos por plataforma no se suman. Una fila FAIL
prevalece sobre otro recibo PASS de la misma fila.

La lectura del porcentaje exige su alcance: este catálogo cubre construcción,
serialización y rechazo de metadatos. Los efectos en motores nativos, cruces de
opciones, fronteras adicionales, API/CLI sin enlaces y el benchmark permanecen
pendientes. La totalidad de esos pendientes se conserva en `result.json`.
Consulte el resultado fechado y su desglose; esto no modifica Universalidad,
Usabilidad ni el cumplimiento científico de la tesis.

Para extender el catálogo, añada un caso con entrada y esperado independiente,
declare sus precondiciones y enlace únicamente los IDs que ejecuta. Conserve el
denominador original del candidato. Si cambia la API del candidato, genere y
publique una nueva matriz identificada y compare explícitamente ambos alcances.
