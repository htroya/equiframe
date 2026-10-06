# DW y dominio SERCOP — Jhair

Este directorio contiene prototipos de esquema, carga y reconciliación de Jhair.
No forma parte de las distribuciones `equiframe` ni `equiframe-benchmark`, y sus
scripts no acreditan una entrega aceptada del DW o del servicio de datos.

La revisión global corrigió únicamente dos errores mecánicos de SQL en la carga
(lista de columnas y número de parámetros) y el código de salida 0 ante cargas
parciales fallidas. Las comprobaciones fueron sintéticas y locales. No hubo
conexión al DW real, cambios de modelo de dominio ni procesamiento de datos reales.

Antes de uso productivo, el responsable debe acordar/verificar como mínimo:

- Identidad por `(snapshot_id, ocid, award_id)` en reconciliación y detección de
  registros presentes solo en destino; el script actual busca por `award_id`
- Múltiples proveedores/items, grano y puente sin duplicar montos; los prototipos
  conservan actualmente solo el primer proveedor/item
- Decimales exactos desde JSON hasta reconciliación; los prototipos usan float
- Ausencias y fechas inválidas sin inventar moneda, monto o la fecha actual
- Transacciones, idempotencia, carga parcial, publicación y concurrencia bajo el
  propietario único de la base; los scripts actuales no ofrecen esas garantías
- Rutas de inicialización/lectura coherentes con `--db-path`, sin presuponer cwd

`README_SCRIPTS.md` conserva las instrucciones históricas y descripciones del
prototipo; no prevalece sobre estas limitaciones verificadas. No ejecutar sus
recetas sobre una base productiva sin la revisión/aceptación de su responsable.
Las entregas y la propiedad de componentes siguen en
[integración del equipo](../../docs/TEAM_INTEGRATION.md).
