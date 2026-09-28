# Changelog

## 0.2.1 — 2026-09-28

- Conservación de anchos/signo NumPy y nullable Pandas, UInt64 extremo y máscaras Float32/64.
- Rechazo previo de categorías e inferencia ambigua de objetos numéricos heterogéneos.
- Límites explícitos de decimal256/escala negativa, segundos Polars y microsegundos zoned DuckDB.
- Rechazo de infinito/sentinels temporales DuckDB en entradas y salidas, sin ocultarlos como fechas finitas.
- Captura parcial referenciada si falla el índice; presupuesto de buffers del índice y limpieza de descargas.
- Copia aislada de índices/columnas en fuentes inyectadas y cierre DuckDB durante setup cancelado.
- Diagnóstico de pánicos nativos Polars; etapas anidadas y puertos runtime validados.
- Coherencia estructural de manifiestos: huella, entradas, salida, formatos y conteos de ausencias.
- DuckDB mínimo 1.5.6, versión comprobada con la API usada; formato JSON 1.0 conservado.
- 142 regresiones adicionales de motores reales; documentación de producto e integración OCI.
- CI extendida a macOS Intel/Apple Silicon y Ubuntu ARM64, con triggers para ramas de cualquier colaborador.

La captura fiel puede rechazar entradas antes aceptadas mediante conversiones que
perdían información. No incorpora comparador ni conexión remota al DW.

## 0.2.0 — 2026-09-28

- Paso 2: `ef.execute`, planes/resultados estrictos, contexto, capacidades y registro por instancia.
- Adaptadores nativos Pandas, Polars lazy materializado y SQL DuckDB local parametrizado.
- Fuentes Arrow/Pandas/Polars/locales y almacén con integridad y publicación exclusiva.
- Evidencia separada del esquema esperado, índices Pandas y diferencias conservadas.
- Cancelación/timeout cooperativos, interrupción DuckDB y presupuestos documentados.
- Extras arrow/pandas/polars/duckdb/engines; importación base ligera y versión/lock actualizados.
- Ejemplos de comercio/telemetría, cinco familias, integración real y distribución fuera del checkout.
- CI Windows/Ubuntu para ramas de pasos y PR dependientes, base y cada extra instalado.

Contratos y ArtifactRef siguen en formato 1.0; el nuevo manifiesto de ejecución usa
su propio formato 1.0. Actualizar desde 0.1 requiere instalar extras para procesar
tablas; la API declarativa se conserva. Sin comparación general, R, ML o benchmark;
sin publicación PyPI ni cambios de tesis/DW/servicio remoto.

## 0.1.0 — 2026-09-28

- Primera API pública del paso 1: contratos semánticos estrictos, inmutables y versionados.
- Validación cruzada de esquemas, claves, tipos, políticas, intervalos y reglas declarativas.
- JSON canónico, SHA-256 de metadatos y esquemas JSON generados.
- CLI `equiframe contract validate`, con errores localizables y salidas documentadas.
- Fixtures sintéticos para cinco familias, pruebas por propiedades y distribución tipada.
- Bloqueo reproducible de desarrollo/ejecución y controles Windows/Ubuntu, Python 3.12 x64.
- Segunda revisión: hash independiente del contexto decimal, base IANA bloqueada,
  unidades/tipos coherentes en reglas y literales float32 exactos sin pérdida.
- Diagnósticos temporales y JSON duplicado específicos/localizables/imprimibles;
  errores de rutas inválidas y validación estricta de sintaxis de URI.
- Verificación ampliada de distribución: API/errores CLI instalada, consumidor
  mypy y batería completa contra wheel reconstruido desde sdist.

No incluye ejecución de reglas, adaptadores, comparador, modelos ni benchmark.
Los formatos del paso 1 usan `schema_version="1.0"`; cambios incompatibles requieren
nueva versión de esquema y migración expresa. No se hace migración automática.
