# Evidencia ETL del candidato 0.11.0

Fecha local del encargo: 2026-10-03. Entorno observado: Windows, Python 3.12.4,
`.venv` del núcleo y dependencias de `uv.lock` con `--locked --all-extras`. El
gestor uv del entorno de revisión se localizó fuera de PATH. Los controles se
ejecutaron desde `packages/equiframe`; resultados científicos y OCI/DW siguen
fuera de esta aceptación técnica.

## Contratos y defectos

El diseño previo está en [ETL_DESIGN.md](ETL_DESIGN.md). El incremento añade
lectores, composición de checkpoints y un destino local sobre el migrador
existente, sin ejecutar un motor y atribuir su resultado a los otros.

La primera batería nueva dio 29 aprobadas y cuatro fallos: las cuatro direcciones
con Pandas frente al esperado mantenían el índice predeterminado significativo
del comparador. El fixture declara ahora `index="ignore"` con justificación de
que RangeIndex generado no es clave lógica. No se alteró la salida para ocultar
el diagnóstico ni se denominó defecto del comparador a una política deliberada.
El caso actualizado dio 33 aprobadas, incluyendo las seis direcciones reales.

La revisión adicional confirmó que un workflow podía conservar expedientes hijos
válidos sin ligar su entrada a la dependencia declarada. `WorkflowResult` ahora
revalida plan/contrato/opciones, identidad de la captura externa o checkpoint y
estado real de la migración. La regresión sustituye una fuente y un contrato y
exige rechazo. No consulta benchmark ni cambia R/M/B/H/O.

La carga exige expediente de Verify íntegro y aprobado ligado al hash publicado.
Los recibos nuevos vinculan tamaño/formato de fuente y hash de Verify; identidad,
rutas y conteos se revalidan. La prueba de fallo en la segunda tabla conserva el
previo y limpia staging. La prueba de fallo del puntero deja la versión anterior
visible y permite completar la versión huérfana mediante retry coherente.

La revisión independiente de Verify reprodujo una sustitución de comparación
entre dos salidas por una comparación de la misma salida consigo misma. El
modelo podía aceptar ese expediente y marcarlo publicable. El responsable de
Verify vinculó cada pareja a sus referencias exactas y a su evidencia de
ejecución; el mismo intento ahora produce `ValidationError`.

La revisión final de ingestión confirmó que un Decimal JSON con exponente extremo
se expandía a texto plano antes de comprobar su precisión. La conversión verifica
límites y escala con Decimal antes de cualquier expansión. La regresión rechaza
`1e-999999999` y `1e999999999` y conserva exactamente `2e3` como `2000.00`.

La revisión del consumidor SERCOP confirmó que una relación presente en algunas
adjudicaciones y ausente en otras podía omitir también los vínculos válidos del
paquete. El consumidor congelado rechaza esas ausencias parciales antes de las
migraciones y de la publicación. Puede conservar evidencia de ingestión previa,
pero no declara un recorrido completo. También rechaza cualquier raíz `records`,
incluida una raíz mixta con `releases`; la selección admitida sigue siendo una
sola release explícita.

El consumidor conserva los bytes leídos de `snapshot.json` y comprueba el
tamaño/SHA-256 de cada miembro de sus recibos, incluido el archivo de búsqueda.
Escribe esos mismos bytes verificados en `snapshot-capture` antes de extraer
cada paquete desde la copia. Esto fija la entrada ante cambios posteriores del
original. El manifiesto aporta las identidades esperadas y no constituye una
autenticación externa de su origen.

Los bytes del esperado manual quedan en `expected-source.json`; su recibo
conserva hash, tamaño, método y autores declarados. Autores desconocidos no se
completan por inferencia y Verify mantiene `provenance=None` en ese caso. Con
autores explícitos se registra procedencia con independencia declarada falsa.
El consumidor mantiene O científico sin establecer. Su bundle exportado es el
expediente de la última migración de totales, no un paquete completo del snapshot,
del esperado original y de la publicación de todas las tablas.

## Ejecuciones

1. `uv run --locked --all-extras pytest -q` sobre
   `test_ingestion.py`, `test_migration_etl_ir.py`, `test_workflow.py`,
   `test_destinations.py`, `test_migration_ir.py`, `test_migration_backends.py` y
   `test_migration_semantic_directions.py`: **109 passed en 300.62 s** antes de las
   últimas regresiones de lineage/puntero.
2. Revalidación de workflow/destinos/IR tras restricciones de errores anticipados:
   **28 passed en 126.52 s**. Las regresiones posteriores tienen su comprobación
   adicional en el manifiesto final de validación. Tras las últimas correcciones,
   ingestión/workflows/destinos dieron **28 passed en 70.22 s**; el control dirigido
   de comparación/tiempo/categorías/dependencias/timestamp IR dio **23 passed en
   54.94 s**.
3. Mypy estricto sobre los 14 archivos ETL/migración revisados: **sin errores**.
   Ruff check y format sobre módulos/pruebas/consumidor nuevos: controles locales
   ejecutados; la revisión global final debe permanecer verde.
4. `uv run --locked --all-extras python examples/etl_local.py --output ...`:
   workflow de comercio completo, dos checkpoints nativos, Verify `passed`,
   Parquet publicado, USD `Decimal('10.30')`, EUR `Decimal('8.00')`, O
   `not_requested`. El expediente de esa ejecución previa a ampliar los campos
   de recibo queda preservado en la carpeta externa de revisión; los artefactos
   finales se regeneran con el candidato terminado. El consumidor final volvió
   a completar el recorrido con recibos reforzados en `retail-etl-final`.
5. `uv run --locked --all-extras pytest -q tests/test_etl_cli.py`: **5 passed en
   31.32 s**. Comprueba CLI de ingestión complete/quarantine, metadatos inválidos,
   I/O, validación/run/inspect de workflow, corrupción y divergencia con dependiente
   saltado. Ruff check/format del archivo nuevo completados.
6. Revalidación final de `tests/test_ingestion.py`: **18 passed en 15.56 s**,
   incluida la regresión de exponentes extremos. Ruff check/format del módulo y
   de sus pruebas completados.

Las rutas de caches, temporales y resultados se mantienen fuera del Git. El
aislamiento Windows negó escrituras temporales de Ruff/mypy bajo ejecución
normal; los mismos controles se repitieron con la elevación revisada de la
herramienta. Ese fallo del entorno no se atribuye al código.

### Vinculación final de opciones de workflow

La revisión final encontró que el lector normalizaba todas las opciones de
migración al compararlas con la etapa declarada. Se corrigió para exigir igualdad
exacta de los campos de captura. Solo un plazo global declarado permite reducir
`timeout_seconds`, con valor positivo, presente y acotado por el plazo global y
por el timeout de la etapa cuando existe. Sin plazo global, las opciones completas
deben coincidir. El tiempo restante exacto no se autentica al releer un expediente;
se comprueba esta condición acotada.

`tests/test_workflow.py` dio **8 passed en 60.54 s**. La regresión final ampliada
`test_checkpoint_options_only_allow_timeout_reduction_with_global_deadline` dio
**2 passed en 17.95 s**, con plazos nulo/presente, sustitución de filas/bytes de
captura y violaciones de ambos límites de timeout. Ruff check/format y mypy sobre
el módulo corregido terminaron sin errores.

## Alcance y pendientes

La pasada adicional tras reanudar reprodujo dos defectos de ingestión del
commit `617e59b`: JSON vacío se etiquetaba `completed` con salida vacía, y un
timestamp UTC/ns fuera de int64 provocaba `OverflowError` al escribir Arrow,
ignorando la política de cuarentena. El fix `0421486` rechaza el documento
vacío y comprueba los ticks antes de aceptar el registro. Las **24 pruebas de
ingestión aprobaron en 4.79 s**, incluidas seis regresiones sobre documentos
vacíos, colecciones/streams vacíos válidos, rechazo/cuarentena y los dos límites
int64 exactos. Ruff y mypy del módulo aprobaron. Son casos técnicos sintéticos;
no añaden resultados científicos ni revisores.

La misma pasada reprodujo una colisión física de nombres `Table`/`table` en
Windows: `publish` devolvía éxito y `current()` detectaba después un hash
incorrecto, porque una tabla sobrescribía la otra. El fix `09c3dfb` exige
nombres inequívocos en filesystems que no distinguen mayúsculas, tanto en la
API como en `LoadReceipt`. Las **ocho pruebas de destinos aprobaron en 12.75 s**,
incluidas tres regresiones nuevas: rechazo antes de I/O, conservación del
puntero/datos anteriores y rechazo del recibo con rutas equivalentes. Ruff y
mypy aprobaron. El paquete se reconstruyó y revalidó tras esa corrección.

El consumidor se probó instalado fuera del checkout mediante el verificador de
distribución del núcleo: suite final de fuente **1000 passed, 1 skipped** y suite
instalada desde sdist **1000 passed, 1 skipped**, con consumidor tipado y rebuild
del wheel idéntico. El skip corresponde al privilegio symlink ausente en Windows.
Benchmark conservó **440 passed, 2 skipped** en fuente y repitió ese resultado
instalado contra el núcleo final; ambos verificados por sus nueve etapas
completas. Los consumidores SERCOP/comercio/Verify de los dos wheels aprobaron
sus seis comandos en un entorno externo. Commit, comandos, tiempos, hashes y
límites están en [la revisión final](VERIFY_ETL_REVIEW_20261003.md); no se infieren
estos resultados de la ejecución editable ni se suman rondas repetidas.

La matriz incluye casos particulares verificables, no una garantía cartesiana.
Timestamps IR, right/full, selección dedup first/last, división y multiplicación
Decimal y resume siguen fuera de soporte. Materialización, presupuesto de disco
y cancelación son controles cooperativos; no hay cuota RSS dura ni interrupción
universal. JSON completo y recibos se materializan. Parquet garantiza cambio de
visibilidad por puntero en filesystem local con un escritor cooperante, sin
afirmar transacción remota/durabilidad frente a caída eléctrica.
