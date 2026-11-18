# Consumidor de un snapshot público SERCOP

La [documentación oficial del portal](https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos/)
y de su [API](https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos/api)
se consultó el 2026-10-03. Se ejecutaron GET explícitos y acotados:
`search_ocds?year=2025&search=agua&page=1`, seguido de `record?ocid=...`
para tres OCID de esa página. No es una muestra representativa del corpus.

Snapshot: **`sercop-e094d8d94ba48b29`**, captura
2026-10-03 19:23:44–48 UTC (14:23:44–48 America/Guayaquil). Los originales,
`snapshot.json`, recibos y `manual_expected.json` se conservan fuera de Git en
`revision_equiframe_20261003/sercop_snapshot` del workspace de esta entrega.
Extractor consumidor: 0.11.0. La captura usa timeout 45 segundos y límite de
10 MiB por respuesta; los importadores tienen además límites declarados.

| Miembro | Tamaño | SHA-256 |
|---|---:|---|
| search.json | 6220 | `d5e0d78e2c874dbf714c3ed306a23e8a26a960dea2c9b9846246824cb20bc61e` |
| record-0.json | 5187 | `6275649a93b34958614d8be61fb92361521cdcc92a9fd011fcb6ed88dc90829f` |
| record-1.json | 7731 | `dbcc6c459da2d3581c8c7e9ca4eecc931f5d5a8f26eebccf2fcfc3c67499ff94` |
| record-2.json | 2604 | `00c2fa22128977f81842823877f9a94d7993b21abd3bb934d9ed359d2dbffb4d` |

Los tres paquetes declaran OCDS `1.1` y el URI de licencia
`https://creativecommons.org/licenses/by/3.0/ec/`. El recibo de búsqueda no trae
licencia propia. Esa observación conserva atribución al Servicio Nacional de
Contratación Pública del Ecuador y no asigna una licencia al software.

## Inspección real y contrato de extracción

Aunque el endpoint se llama `record`, estas respuestas contienen **`releases`**,
exactamente una release por paquete, y no una raíz `records`. El consumidor
rechaza cualquier raíz que contenga `records`, incluso si también contiene
`releases`, y rechaza múltiples releases sin un contrato adicional de selección.
No interpreta el sufijo `compiled` como prueba de historia completa.

| OCID | Award ID observado | Importe esperado manual |
|---|---|---:|
| `ocds-5wno2w-CE-20250002768002-68807` | `CE-20250002768002` | USD 3180.00 |
| `ocds-5wno2w-LCC-GADEP-2025-001-23948` | `7881165-LCC-GADEP-2025-001` | USD 72700.00 |
| `ocds-5wno2w-CDC-GADCN-2025-001-41973` | Sin awards | No se fabrica fila monetaria |

Granos: procedimientos `(ocid, release_id)`; awards `(ocid, award_id)`;
puentes `(ocid, award_id, supplier_id)` y `(ocid, award_id, item_id)`.
Los puentes **no contienen monto**. Se valida unicidad del grano monetario y
ausencia de huérfanos, con dinero Decimal exacto. Se conservan identificadores
como strings; no se elimina un cero inicial ni se deduplica para hacer coincidir.

Si `suppliers` o `items` aparece en unas adjudicaciones y falta en otras del
paquete, la extracción falla antes de migrar o publicar. Esta política exige
resolver la cobertura desconocida y evita perder los vínculos válidos de las
adjudicaciones que sí tienen el array. Un array presente y vacío aporta cero
filas; una relación ausente en todas se registra en `missing_relation_arrays`
y no genera una tabla. Una extracción rechazada puede haber conservado recibos
de ingestión preliminar, sin aprobar el recorrido completo.

La fecha de adjudicación falta en el primer award; no se sustituye por fecha de
publicación. En el segundo es `2025-02-20T13:31:55-05:00`; la release/compilación
y su paquete se publicaron en febrero de 2026. El filtro `year=2025` no equivale
a año de publicación ni a fecha de adjudicación. El consumidor preserva las
fechas originales de release/paquete y un JSON textual con fechas de awards;
no anuncia transformación temporal nativa del IR.

## Recorrido reproducible sin red

Con el wheel de `equiframe[engines]` instalado y el sdist extraído/copias de los
ejemplos, use una carpeta de salida nueva. No hace falta el checkout ni `sys.path`:

```bash
python -I examples/sercop_etl.py --snapshot /ruta/snapshot-fijado --expected /ruta/snapshot-fijado/manual_expected.json --output /ruta/nueva-evidencia
```

El consumidor copia los bytes de `snapshot.json` a `snapshot-capture` y verifica
tamaño/SHA-256 de cada archivo listado en sus recibos, incluida `search.json`.
Conserva exactamente los bytes verificados en esa carpeta y extrae los paquetes
`record-*` desde las copias. El manifiesto sirve como referencia de esas
identidades; el consumidor no autentica por sí mismo su procedencia externa.
Conserva originales y recibos de conversiones; para este snapshot crea cinco
tablas; compara íntegramente awards por clave
frente al esperado enumerado manualmente; ejecuta la agregación Decimal por moneda
en las seis direcciones Pandas/Polars/DuckDB; verifica los expedientes, publica
Parquet de cinco tablas, repite idempotentemente y exporta/importa un bundle.
El esperado agregado es **USD 75880.00, dos awards**. La suma global no sustituye
la comparación de asignaciones por clave.

El esperado se conserva íntegro como `expected-source.json`. Su recibo en
`summary.json` registra SHA-256, tamaño, método y autores declarados. Cuando los
autores se desconocen, se conserva esa ausencia y el método disponible, y
`provenance` de Verify queda sin declarar. Si el documento aporta autores, el
consumidor puede registrarlos con `independence_declared=False`. Esta procedencia
no establece independencia ni revisión científica O.

El bundle del ejemplo corresponde al expediente de la última migración de
totales, con sus entradas, salidas y evidencia capturada. La exportación/importación
verifica ese expediente. El snapshot original, el esperado fuente y la carga de
las cinco tablas se conservan en la carpeta del recorrido y no forman, en
conjunto, un bundle de esta demostración.

Si está instalado `equiframe-benchmark`, ejecuta adicionalmente `reconcile_awards`
con claves explícitas y el puente de proveedores. La ausencia de ese paquete
queda como `null` en el resumen; no obliga a instalarlo para usar el núcleo.
Los proveedores/ítems/procedimientos tienen inspección de esquema y relaciones;
no se presentan como cotejados con un esperado humano independiente completo.

`summary.json` registra fuentes, inspección, granos, conteos, seis migraciones,
reconciliación, carga, idempotencia y bundle. Los tiempos por fases especifican
qué incluyen; las migraciones incluyen comparación/evidencia y no son costos
aislados de motores. RSS se mide externamente por árbol de procesos a intervalos
de 200 ms, con posible doble conteo de páginas compartidas. No acredita cuota
dura ni rendimiento a gran escala. [Resultados de ejecución](VERIFY_ETL_REVIEW_20261003.md).

## Modo sintético y generalidad

```bash
python -I examples/sercop_etl.py --snapshot examples/sercop_offline --expected examples/sercop_offline/expected.json --output sercop-offline
python -I examples/retail_etl.py --output retail-example
python -I examples/verify_generic.py --output verify-example
```

La fixture offline se identifica explícitamente como **sintética**: dos awards,
USD 13.00 y puentes con tres suppliers/tres items, para demostrar que expansión
no multiplica dinero. `retail_etl.py` ingiere CSV de comercio, calcula descuentos
y agrega dos monedas en dos checkpoints con carga local. `verify_generic.py`
muestra el caso de dos resultados coincidentes pero erróneos.

El caso real confirma este subconjunto fijado. `scientific_O=not_established`:
no se inventan autores, revisiones ni independencia autenticada. No acredita
corrección del corpus completo, registros efectivos de aprendizaje, hipótesis,
cliente/DW del equipo, OCI o aceptación de dominio por Jhair.
