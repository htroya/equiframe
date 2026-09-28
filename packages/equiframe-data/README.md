# Cliente de datos — José

Espacio de integración propuesto para el cliente Python de José. No está implementado en este incremento y no pertenece al plan de desarrollo de Hernán/Sol.

Debe cumplir las garantías de snapshots, trabajos, idempotencia y errores descritas en [integración del equipo](../../docs/TEAM_INTEGRATION.md). El cliente no convierte varios `duckdb.connect()` independientes en un servicio de escritura concurrente.
