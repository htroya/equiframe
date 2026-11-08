# Incremento ETL: contratos antes de implementación

Este incremento reutiliza los compiladores y el runner de migración. No modifica
el diseño experimental, entrena detectores ni integra OCI/DW.

| Problema | Contrato propuesto | Compatibilidad y aceptación |
|---|---|---|
| CSV/JSON/JSONL no tienen ingestión contractual | `IngestionSpec`, `FieldMapping`, `ingest_file` y `FileInput.load`; tipos Arrow explícitos, originales conservados por hash, rechazo/cuarentena y recibos | Nuevos módulos; probar identificadores, decimal exacto, ausencias, cambios de esquema, fechas inválidas y JSON anidado con rutas/arrays declarados |
| IR carece de operaciones ETL comunes | `Arithmetic`, `Coalesce`, `Conditional`, `Concatenate`, `Deduplicate`; existencia semi/anti | IR 1.0 recibe variantes nuevas aditivas. Toda operación anunciada se ejecuta nativamente en tres motores. NULL propaga en aritmética; CASE desconocido elige else; coalesce solo sustituye NULL; concat conserva multiplicidad; dedup elimina solo filas idénticas y exige todas las columnas |
| Una transformación no es un workflow | `WorkflowSpec`/`WorkflowStage` con enlaces externos/checkpoints previos y `run_workflow`; un `MigrationSpec` por salida/etapa | Runner existente fija las entradas por etapa para ambos motores; las etapas fallidas bloquean dependientes. Varias etapas permiten varias salidas. Se rechaza resume; no se reutilizan capturas sin validar |
| Salida completed no autoriza publicación | Puerto `Destination`, implementación `ParquetDestination`, gate de Verify ligado a hashes de todas las tablas | Publicación de directorio de versión inmutable y sustitución atómica de un único puntero JSON local. No transacción DW ni garantía frente a caída eléctrica. Conserva versiones; identidad repetida solo admite exactamente los mismos bytes |

Aritmética prioritaria: enteros con promoción exacta antes de operar y control de
rango de salida; decimal suma/resta con precisión suficiente comprobada antes de
compilar. División/redondeo, timestamp IR y right/full siguen rechazados: ampliar
esas semánticas exige pruebas adicionales. Los timestamps de ingestión exigen
offset cuando tienen zona y unidad exacta; no se adivinan horas DST.

Evidencia: especificaciones serializadas, hashes fuente y salida, recibos de
conversión/cuarentena, expedientes de migración por etapa, primer checkpoint
divergente y manifiesto/puntero de carga. Los límites son cooperativos/materializados;
JSON completo se materializa y JSONL/CSV se leen por registros, sin cuota RSS dura.
