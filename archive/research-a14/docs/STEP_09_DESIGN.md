# Integración verificable con snapshots y contratos del DW

Diseño de ingeniería del paso 9, 2026-10-02. Núcleo 0.8.1 y benchmark 0.9.0.
Hernán confirmó que todavía no existen las entregas del cliente, snapshot y DDL
de José/Jhair, y autorizó continuar el desarrollo de EquiFrame en paralelo.
Este incremento completa componentes consumidores y conformidad local; la
aceptación de la conexión real permanece pendiente.

## Responsabilidad del consumidor

`equiframe_benchmark.snapshot` define un recibo estricto `SnapshotManifest` y
un consumidor `SnapshotDataSource` compatible con el puerto del núcleo. El
cliente inyectado ofrece `get_snapshot(id)` y `download_artifact(ref, path)`.
Es una interfaz concreta para adaptar la entrega futura, no una implementación
del transporte, la autenticación ni el servicio de José. Los nombres/campos del
DW y sus revisiones los suministra su responsable; no se escribe ni abre su base.

El recibo registra versión explícita, revisión de dominio y extracción,
procedencia, tablas, filas, referencias SHA-256/tamaño y columnas físicas/lógicas.
Rechaza `latest`, nombres duplicados, recibos sin publicar y versiones distintas
de la solicitada. La selección de tablas permite consumir un subconjunto del
DW conservando el manifiesto completo y su huella.

El constructor fija el recibo una sola vez. Su consulta precede al `RunContext`:
el cliente debe imponer su propio timeout. Cada descarga usa una carpeta privada
nueva bajo la corrida; valida contención, bytes, SHA-256, filas, tipos y ausencias
antes de entregar datos. Conserva el origen y registra la identidad del snapshot
en la configuración efectiva. No reintenta un fallo ni cambia de publicación
entre tablas. Los checkpoints temporales/de cancelación son cooperativos;
no preemptan una descarga bloqueante o decodificación Arrow. Las cuotas del
servicio y la coordinación de cargas siguen fuera del consumidor.

## Ejecuciones y comparaciones

`IntegrationSpec` exige las tres implementaciones registradas Pandas, Polars y
DuckDB con contrato, transformación/revisión, parámetros, reglas y perfil
compatibles. Cada implementación se ejecuta una sola vez con `run_pipeline`.
Se comprueba que las entradas capturadas tienen igual contenido e identidad
del snapshot. Las políticas de índice, tipos, multiplicidad, precisión y tiempo
se toman del contrato; no se añaden normalizaciones para igualar resultados.

Las parejas principales son Pandas–Polars y Pandas–DuckDB. Polars–DuckDB se
conserva como comparación adicional. Un esperado opcional se captura una sola
vez y sus tres comparaciones quedan vinculadas a los mismos bytes, aunque la
fuente original cambie después. La comparación no crea una etiqueta O ni
alimenta R/M/B. Los bundles son previamente ajustados; no hay entrenamiento.

Un fallo de motor o captura no elimina las comparaciones independientes que
pueden completarse. La completitud global exige las tres corridas y las
comparaciones solicitadas evaluables sobre entradas comprobadas; los códigos
0/1/2/3 conservan la prioridad de entrada inválida e incompletitud. Los artefactos
de una integración usan ID nuevo, journal encadenado y publicación exclusiva.
`read_integration` comprueba recibos, inventario, referencias, resultados y
manifiestos hijos sin volver a contactar al servicio ni ejecutar ETL.

## Reconciliación de adjudicaciones

`reconcile_awards` recibe dos tablas explícitas: referencia independiente y
observación del consumidor. `AwardReconciliationSpec` declara la revisión de
dominio y los nombres del grano, importe, moneda y puente opcional. La referencia
debe ser válida y única; una referencia inconsistente deja la evaluación no
evaluable. La función no deduplica, redondea, convierte monedas o reconstruye
claves. Este control suplementario no sustituye el comparador completo ni las
revisiones del oráculo.

La conciliación localiza ausencia de claves, duplicación del grano, importes
ausentes, diferencias por adjudicación y totales por moneda. Por eso detecta
un intercambio de montos aun cuando conserve el total. Requiere decimal Arrow
y acumula coeficientes enteros, preservando precisión incluso con un contexto
Decimal de baja precisión. Un importe NULL conserva el conteo de adjudicaciones
y deja el total monetario `null`/no evaluable; no se presenta como cero.
Una moneda ausente conserva un conteo separado y deja los totales por moneda
no evaluables: el consumidor no puede asignar ese importe a una moneda usando
la referencia ni interpretar subtotales conocidos como sumas completas.

El puente puede vincular varios proveedores a una adjudicación. Se verifican
duplicados del vínculo, claves ausentes, referencias huérfanas y presencia
indebida de la medida monetaria. El importe se cuenta en el hecho, una vez,
sin multiplicarlo por el número de proveedores. La función comprueba las tablas
suministradas; no implementa el DDL, ETL ni publicación que corresponden a Jhair.
El presupuesto cuenta las filas ya materializadas de referencia/observación/
puente; no es una cuota dura de memoria o transporte.

## Criterio de cierre real

La conformidad local ejercita capturas, errores y semántica con fixtures
sintéticos identificados. Para aceptar integración real faltan cliente autorizado,
snapshot utilizable, DDL/diccionario/mapeos, políticas de dominio, expected
revisados y entorno identificado. El servicio debe demostrar lectura estable
durante carga, idempotencia y recuperación bajo sus controles. Las pruebas del
consumidor no certifican esos comportamientos ni el aprovisionamiento OCI.
Los datos y reportes de reconciliación reales permanecen fuera de Git.
