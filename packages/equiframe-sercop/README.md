# DW y dominio SERCOP — Jhair

Este directorio contiene prototipos de esquema, carga y reconciliación de Jhair.
No forma parte de las distribuciones `equiframe` ni `equiframe-benchmark`, y sus
scripts no acreditan una entrega aceptada del DW o del servicio de datos.

La corrección posterior a la [revisión independiente A14](../../docs/A14_INDEPENDENT_REVIEW_FIXES_20261013.md)
endurece `etl_load_ocds.py` conservando el DDL v1. La carga valida el lote antes
de escribir, utiliza parámetros SQL y una transacción para snapshot, dimensiones
y hechos. Si falla una inserción, revierte el lote. Un snapshot ya publicado no
se reemplaza: el reenvío requiere una identidad nueva acordada por el operador.
Esta negativa evita sobrescrituras; no ofrece una reconciliación idempotente.
También se rechazan cambios de atributos de una dimensión existente: el DDL v1
no puede conservar versiones y sobrescribirlos alteraría snapshots anteriores.

El JSON se abre como archivo local regular con un límite de 64 MiB. No se admiten
claves repetidas, NaN/Infinity, dinero float, booleano o textual. El dinero debe
caber exactamente en `DECIMAL(18,2)`; se rechaza en lugar de redondearlo. Monto,
moneda, fecha y asociaciones ausentes permanecen NULL. La fecha del procedimiento
se obtiene sólo de `procedure_date`; nunca de la fecha de adjudicación o de hoy.

El DDL no representa puentes ni timestamps precisos. Por eso la carga rechaza
múltiples proveedores/items y fechas distintas de `YYYY-MM-DD` antes de escribir.
La extracción de `equiframe-data` sí conserva todos los proveedores en su columna
anidada. No ejecutar el cargador sobre una entrega anual sin acordar primero la
proyección temporal, el grano, los puentes y la preservación de ausencias explícitas
frente a campos omitidos. NULL no conserva por sí solo esa última distinción.

Las comprobaciones del cargador fueron sintéticas y privadas. No hubo conexión
al DW real ni aceptación del modelo de dominio. La CLI usa el `--db-path` indicado
y no ejecuta `etl_init.py` ni carga datos de demostración.

Antes de uso productivo, el responsable debe acordar/verificar como mínimo:

- Identidad por `(snapshot_id, ocid, award_id)` en reconciliación y detección de
  registros presentes solo en destino; el script actual busca por `award_id`
- Múltiples proveedores/items, grano y puente sin duplicar montos; la carga v1
  los rechaza hasta disponer de un esquema aprobado
- Decimales exactos también en `etl_reconcile.py`, que aún usa float
- Ausencias omitidas frente a NULL explícito y proyección de timestamps originales
- Idempotencia del protocolo completo, publicación, backups y concurrencia bajo
  el propietario único de la base; una transacción local no acredita esos controles
- Inicialización y reconciliación completas usando la misma ruta y snapshot

`README_SCRIPTS.md` conserva las instrucciones históricas y descripciones del
prototipo; no prevalece sobre estas limitaciones verificadas. No ejecutar sus
recetas sobre una base productiva sin la revisión/aceptación de su responsable.
Las entregas y la propiedad de componentes siguen en
[integración del equipo](../../docs/TEAM_INTEGRATION.md).
