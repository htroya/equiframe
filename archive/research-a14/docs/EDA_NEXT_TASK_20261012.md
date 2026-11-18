# Orden del encargo EDA y ejecución posterior

**Actualización:** la fase previa fue publicada y comprobada en `main`, commit
`cfd65b90e749053f68aaf7d1c2b1d1f508e2db8e`. Después se implementó la
[extensión A14 y se validó en Windows/ARM64](EDA_IMPLEMENTATION_20261012.md).
El texto siguiente conserva el orden original; sus expresiones de futuro
describen ese encargo anterior, no una tarea técnica todavía sin implementar.

El propietario indicó implementar el prompt adjunto **después de concluir el
trabajo actual, sus verificaciones/pruebas Alpha y subirlo a `main`**. Esta página
registra el orden y no acredita implementación ni reportes EDA ya existentes.

El alcance futuro es subpaquete opcional de la distribución existente, backend
DuckDB y Plotly opcional, API/CLI comunes, contratos versionados, calidad,
estadísticas, IQR/MAD y reportes JSON/HTML con manifiestos. Mantendrá fuentes
inmutables, tipos originales, conversiones explícitas y decimales/monedas,
presupuestos y estados no evaluables. No crea otro migrador, verificador,
servicio, DW ni detectores entrenados; R/M/B/H/O conservan sus funciones.

La fuente real será la copia local de la [entrega SERCOP](SERCOP_PUBLIC_DELIVERY_20261012.md),
identificada por manifiesto SHA-256
`712022f8470428f25fa12b307e301ad6ef6fb0f9c59634ab8b90569380ac279c`.
Los runs irán fuera de la carpeta de la tutora, fuera de Git y sin publicación
automática. No se cambia Word, permisos, túnel, URL o servicio de esa entrega.
Se prueban datos sintéticos y un ejemplo real con reglas documentadas; los
pendientes de dominio pertenecen a Jhair y los de servicio a José.

Migración, comparación y Verify deben seguir operando sin instalar ni ejecutar
EDA. Se verificará integridad antes/después, diferencia pese a estadísticas
iguales, límites, fallos/cancelación y evidencia histórica. QA usa Opera Neon
con perfil dedicado y zoom inicial 75 %. No hay publicación PyPI ni despliegue
de servicios dentro de este nuevo encargo. Una extensión futura necesitará
su propio candidato Alpha y evaluación; no hereda automáticamente las cifras A13.
