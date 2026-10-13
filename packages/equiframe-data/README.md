# Cliente de datos — José

Componente **privado 0.1.0a14**: transporte local de snapshots, coordinación de
trabajos y puente opcional al núcleo A14. La revisión del 13 de octubre corrige
validación de rutas/manifiestos, bloqueo entre procesos y publicación inmutable.

Instale el wheel identificado por SHA-256 desde el wheelhouse privado:

```bash
python -m pip install --find-links /ruta/wheelhouse-privado equiframe-data==0.1.0a14
```

No está publicado en PyPI/TestPyPI. El código consumidor usa el paquete
`equiframe_data`; no necesita modificar `sys.path` ni usar rutas del autor.

```python
from pathlib import Path
from equiframe_data import JobManager, SnapshotClient

manager = JobManager(Path("private-state"), input_dir=Path("trusted-input"))
job = manager.submit_job("load", "v1", "project-specific-idempotency-key")
manager.run_job(job.job_id, {"items": "items.parquet"})
client = SnapshotClient(manager.snaps_dir)
manifest = client.get_snapshot("v1")
ref = manifest.get_artifact("items")
local = client.download_artifact(ref, Path("private-downloads"))
```

`trusted-input` debe existir y ser una carpeta controlada por el operador.
La API de servicio admite nombres relativos a esa carpeta. IDs y nombres de
tabla usan letras ASCII, números, guion y guion bajo, hasta 128 caracteres.
Las rutas no admiten `..`, rutas absolutas, enlaces, junctions, ADS ni dispositivos.
Los manifiestos exigen ID/versiones coherentes, tablas y archivos únicos,
SHA-256 hexadecimal, tamaños enteros y timestamp con zona. Se rechazan JSON
duplicado/no finito y manifiestos mayores de 4 MiB; máximo 256 artefactos.

La referencia y el manifiesto obtenidos son inmutables y quedan fijados por
cliente. Una descarga nueva se publica sólo después de verificar todos sus bytes;
el fallo conserva cualquier archivo anterior. Un snapshot publicado no se borra
ni sustituye. Use un ID nuevo para una nueva versión.

`JobManager` admite sólo `load`, limita bytes/trabajos y coordina submit/cancel/run
con `flock` en POSIX o un bloqueo de archivo Windows. Los recibos se reemplazan
atómicamente. Al reiniciar con exclusividad, un trabajo interrumpido falla o
recupera una publicación completa del mismo `producer_job_id`, comprobando
hashes. No se garantiza recuperación ante pérdida eléctrica del almacenamiento.

El extra `core` habilita `equiframe_data.core_adapter.CoreSnapshotClient`.
Recibe un `equiframe.SnapshotManifest` declarado por el operador con columnas,
tipos lógicos, filas y revisiones independientes. Comprueba su inventario contra
el transporte y se inyecta en `equiframe.SnapshotDataSource`. Arrow/Parquet son
los formatos admitidos; no se infiere una aprobación de dominio ni se convierte
CSV silenciosamente. El núcleo no importa este componente.

El extra `etl` conserva un extractor OCDS **prototipo**. Valida estructura y
presupuestos, conserva Decimal, proveedores y descripciones, y no inventa USD
cuando falta moneda. Los nombres históricos `monto_usd` no significan conversión
a USD: consulte siempre la moneda. No sustituye el DW ni una cohorte aprobada.
El presupuesto por defecto es 64 MiB / 250.000 releases / 2.000.000 filas
aplanadas; cambiarlo es explícito dentro de los límites admitidos. Valores y
colecciones malformados se rechazan sin repetir su contenido en el error.
También conserva la moneda del tender; el CLI informa conteos y tamaños sin
imprimir muestras de registros. Fechas y campos de dominio siguen sujetos al
contrato aprobado del equipo.

La [API autenticada](../../services/data-gateway/README.md) ofrece lectura y
operación con credenciales separadas. Los directorios, fuentes y procesos del
servicio deben ser controlados por su propietario. Un usuario del sistema con
permiso para modificarlos no queda aislado por esta biblioteca.

Las garantías y pendientes reales se conservan en [integración del equipo](../../docs/TEAM_INTEGRATION.md).
La publicación del DW real, aceptación humana, backup operativo y configuración
de producción siguen bajo José/Jhair. Este componente no abre una base DuckDB
mutable con varios escritores independientes.
