# A13: fuentes reconstruidas y suites adicionales

El [recibo PEP517](ALPHA_SDIST_REBUILD_RESULT_20261012.json) conserva
construcción de los tres paquetes, wheel/sdist idénticos, instalación directa
de fuentes originales, locks y ejemplos nativos en Windows Python 3.11/3.13.
El backend se aísla mediante PEP517 y recibe sólo su wheelhouse público
fijado por hashes. Los anteriores ensayos sin aislamiento o con ruta Windows
mal interpretada se conservan; no se presentan como equivalentes al final.

El [recibo de suites](ALPHA_FULL_SUITES_RESULT_20261012.json) enumera los
resultados y omisiones reales de núcleo, benchmark y consumidor por Python.
Complementa M13 ARM3.10/3.12, sin inferir otros sistemas o todos los perfiles.
La [regresión del productor](ALPHA_PRODUCER_REGRESSION_RESULT_20261012.json)
conserva FAIL A12 y PASS A13 normales/optimizados por identidad real instalada.
Ninguno de estos recorridos añade IDs al catálogo de trazabilidad ni observación
humana. Los artefactos originales A13 siguen intactos.
