# Changelog

## 0.9.0 — 2026-10-03

- API aditiva `detect_component` y resultado `ComponentDetectionResult` para
  inferir M o MAD con el preprocesador y la calibración congelados, sin puntuar
  el otro detector. Conserva los scores, umbrales y decisiones de `detect`.
- Huellas del bundle, ajuste, perfiles y matriz enlazan el resultado aislado a
  sus entradas. Los modelos/calibraciones no estimables conservan sus motivos
  y scores ausentes; las mediciones fallidas o incompatibles se rechazan.
- Paridad de inferencia, restauración declarativa y regresiones de independencia;
  formatos anteriores y algoritmo conjunto conservados. El benchmark separado
  incorpora evaluación y costes operacionales del paso 10.
- `DetectorVersions` admite el emisor 0.9.0 y conserva productores explícitos
  0.7.0/0.8.0/0.8.1. Sin ajuste implícito, nuevas etiquetas ni publicación PyPI.

## 0.8.1 — 2026-10-02

- Revisión del paso 8 frente al TFM: conserva objetivos, fórmulas, separación de
  detectores/oráculo y pendientes científicos; corrige referencias de estado.
- Verificación de evidencia vinculada a las capturas y referencias inventariadas;
  rechaza artefactos omitidos y reducciones inconsistentes con sus observaciones
  y posiciones originales.
- CLI de evidencia/reportes distingue corrupción de una petición inválida.
- Formatos 1.0 y bundles explícitos 0.7.0/0.8.0 conservados; la versión emisora
  admite 0.8.1. Distribución privada; publicación pública sigue en el paso 19.

## 0.8.0 — 2026-10-01

- Paso 8: API `run_pipeline`, configuración/resultados estrictos, R/perfil/M/B/H
  y comparación opcional sobre una captura nativa; sin entrenamiento implícito.
- Eventos encadenados SHA-256, manifiestos exclusivos, inspección de interrupciones
  y verificación de archivos, procedencia y consistencia de reportes JSON/HTML.
- CLI run/compare/report/evidence/reduce y CLI separada del benchmark; códigos
  0/1/2/3 que conservan la prioridad de fallos y componentes no evaluables.
- Reducción determinista por filas entre tablas, firma de fallo y precondiciones
  verificadas por predicado confiable, presupuestos y confirmaciones explícitos.
  Minimalidad local únicamente; nunca se afirma mínimo global.
- Siete esquemas nuevos 1.0. DetectorVersions acepta también 0.8.0 y conserva
  bundles 0.7.0 explícitos sin cambiar el algoritmo declarativo.
- Ejemplo instalado, pruebas nativas y distribución reproducible; PyPI, integración
  OCI/DW y cierre científico permanecen pendientes según el plan vigente.

## 0.7.0 — 2026-10-01

- Paso 7: Isolation Forest y MAD por familia sobre el mismo preprocesamiento,
  soporte explícito, calibración normal independiente y alpha decimal obligatorio.
- Cuantil empírico exacto sin interpolación, desigualdad estricta, MAD cero e
  infinito y estados no estimables; ninguna excepción se convierte en no alerta.
- H = R OR M con tres estados y conservación de alertas parciales.
- Árboles declarativos y bundles JSON verificables, sin cargar pickle/joblib;
  inferencia base sin ML y ajuste opcional mediante `equiframe[ml]`.
- Benchmark 0.7.0 incorpora selección normal de calibración y auditoría de grupos.
  Conserva contratos, perfiles y reglas 1.0. La API añade formatos independientes.
- Wheel/sdist, consumidor externo, tipado y pruebas. No publica en PyPI ni
  entrena modelos científicos con el piloto pendiente de revisión humana.

## 0.5.0 — 2026-10-01

- Perfiles de una captura para las cinco familias y diez métricas de la Tabla 13.
- Conteos y denominadores explícitos; NULL/NaN/vacío/cero, no aplicabilidad y
  fallos técnicos separados. Recibos para conversiones instrumentadas.
- Preprocesamiento normal de entrenamiento: medianas congeladas, indicadores,
  retiro documentado, incompatibilidades de versión/orden y matriz común M/B.
- Persistencia JSON sin sobrescritura; esquemas, cinco ejemplos y verificación
  del wheel fuera del checkout. M/B/H y el benchmark siguen pendientes.

## 0.4.0 — 2026-09-30

- Paso 4: `ef.evaluate_rules` verifica entradas y salida capturadas de una sola
  ejecución, con registro explícito de las seis formas de regla y precondiciones.
- Hallazgos JSONL completos, resumen acotado, cobertura, presupuesto y cancelación
  cooperativa; alerta observada conserva su estado ante evaluación incompleta.
- Catálogo técnico versionado para cinco familias y huella de contrato, código de
  reglas y configuración; consumidor Arrow sin tres motores.
- `ComparisonResult` rechaza manifiestos `equivalent` con conteos contradictorios
  y valida la coherencia de la estrategia/clave seleccionada.
- Nuevos documentos/esquemas de R 1.0, contratos/ejecuciones 1.0 conservados.
- Segunda revisión: la relectura de R rechaza decisión/completitud contradictorias,
  la aplicabilidad prioriza una precondición verificablemente falsa y `SchemaCheck`
  localiza tipos Arrow transportables incompatibles con el contrato.

No incorpora perfiles, M/B/H, oráculo, benchmark final, DW ni publicación PyPI.
Las estadísticas de conversiones anteriores a la captura requieren evidencia
adicional; no se reconstruyen de una salida final.

## 0.3.0 — 2026-09-30

- Paso 3: `ef.compare`, modelos completos, lectura de manifiestos y diferencias verificables.
- Esquema observado separado; validación de valores, claves/ámbitos, multiplicidad y orden.
- Normalización autorizada de ausencias, NaN y tiempo; decimales/enteros/ns sin pérdida.
- Alineación exacta por clave comprobada, secuencias, multiconjuntos y matching máximo aproximado.
- Lotes y SQLite privado con spill; presupuestos, cancelación y completitud explícita.
- Evidencia JSONL completa, ejemplos acotados, snapshots y corridas exclusivas.
- `ComparisonSpec` y documentos propios 1.0; contratos/artefactos/ejecuciones 1.0 intactos.
- Timeout de callback determinista mediante reloj controlado; caso previo al callback separado.
- Esperados independientes, propiedades, tres motores y consumidores instalados base/extras.

Instalar el nuevo wheel; ningún contrato antiguo se migra automáticamente. Los
permisos adicionales se expresan mediante `ComparisonPolicy` con justificación.
Soporte Python 3.12; sin publicación PyPI, despliegue OCI, R/ML/DW ni resultados
científicos añadidos. El comparador evalúa `output_schema`, no certifica el oráculo.

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
