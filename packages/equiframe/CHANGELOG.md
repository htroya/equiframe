# Post-roadmap review: correctness and reusable Python integrations

Private 0.11.1 candidate; identify this revision by commit and exact artifact
hashes. Public release, licensing, platform qualification and adoption remain
separate unresolved gates.

- Preserve workflow indexes and native provenance across captured inputs; isolate
  unrelated source failures and consumer-specific resource budgets
- Reject every out-of-range pandas arithmetic intermediate. DuckDB refuses
  nested arithmetic/predicates whose eager errors SQL optimization can omit;
  corrected compiler identities include `/arithmetic-checks-v1`
- Retain native dtype observations and provider notes through migration detachment
  and child captures. Document direct compiler/execute input preconditions
- Expose generic pinned snapshots from core, with exact historical benchmark
  aliases, manifest format/fingerprint preservation and no new base dependency
- Remove source-owned completed-run bookkeeping; verify per-run manifest reuse
  across contexts with different budgets. Add a core-only installed
  snapshot example and an extension guide for source, adapter and compiler ports
- Use defaults only for `None` configuration arguments; reject invalid falsey
  values before work while retaining valid strict mappings and model instances
- Preserve operational CLI exit statuses and first-line codes; add shared
  fixed-text recovery hints without rendering raw exception payloads
- Regenerate only the current synthetic rule catalog because its fingerprint
  binds the edited rules.py implementation bytes; rule formulas and all historical
  fixtures remain unchanged
- Preserve candidate-check receipts/logs against accidental reuse of an output
  destination; earlier failed attempts remain reviewable

Historical JSON formats, comparison truth-testing rejection, exact value
semantics and independent R/M/B/H/O boundaries remain intact. The workflow and
arithmetic corrections can reject previously accepted defective cases; preserve
old evidence and rerun affected plans before using them for acceptance. This is
ordinary functional/architectural review, not a completed security assessment.

# STEP10 candidate: adoption records and sustainable maintenance

Private 0.11.1 candidate, identified by exact commit and artifact hashes.

- Add a strict local developer-only pilot-record checker and honest empty
  registry. Distinguish synthetic replays, consented human attestations,
  later-change retention, unknown effort and critical incident evidence
- Add a standalone synthetic repeat-use replay for Python refactor,
  SQL/DuckDB and CI-style assertions, with exact contracts and independent
  literal expectations. Technical repetition does not establish human adoption
- Package adoption and maintenance guidance; provide minimal issue templates,
  pending owner/backup roles, proposed priorities and false-equivalence response
- Keep runtime APIs, comparison semantics, historical schemas and dependency
  ranges unchanged. First-use kit v1 retains its closed inventory

No real pilots, human five-minute result, nominal maintenance assignment, SLA,
new engine, completed security assessment or public publication is claimed.
The source-security assessment and retained advisory triage remain unresolved;
public release stays closed pending owner decisions and the global review.

# STEP9 candidate: distribution, English handbook and release controls

Private 0.11.1 candidate, identified by source commit and artifact hashes.

- Package the standalone English handbook in wheel and sdist; translate the
  first-use kit documentation without changing recipe behavior
- Verify byte-identical wheel and sdist rebuilds, outside-checkout consumption,
  separate optional profiles and historical reader tests
- Add artifact-bound CycloneDX dependency inventories, license observations and
  explicit dated vulnerability-query evidence with unavailable states preserved
- Add a tested fail-closed publication-readiness gate; the dormant workflow
  contains no upload step, credential or OIDC permission
- Document threat boundaries, incomplete security assessment, incident response,
  immutable releases, withdrawal and isolated rollback

No project license, public publication, new maintainer/SLA or completed source
security scan is claimed. Existing runtime APIs and protected historic formats
are unchanged by this engineering stage. See `docs/index.md`.

# Changelog

## Candidato STEP8 (2026-10-06)

- Reduce llamadas redundantes al sistema de archivos en cada control de disco
  del comparador mediante scandir. Conserva frecuencia, errores, cancelación,
  trabajo, tiempos y umbrales; no cambia normalización, alineamiento, contenido
  exacto ni evidencia. Casos medidos y límites en docs/SCALING.md.
- Añade regresiones de contabilidad, enlaces, cierres y fallos de recursos.
  No cambia API pública, formatos históricos ni límites declarados por defecto.

## Candidato STEP7 (2026-10-06)

- Nueva captura explícita `capture_duckdb` y `DuckDBCaptureOptions`: consulta
  confiable, consumo único por lotes, snapshot Arrow desacoplado, presupuestos
  cooperativos y propiedad/conservación de sesión documentadas
- Rechazo fail-closed antes de Arrow de HUGEINT/UHUGEINT, UUID y tipos nativos
  sin transporte fiel declarado, también en `DuckDBAdapter`. Antes podía
  ocultarse una pérdida (UHUGEINT máximo pasa a -1 en DuckDB 1.5.6).
  Use un cast SQL explícito solo si el rango y la semántica del caso lo permiten
- Los parámetros Decimal se enlazan con tipo nativo y texto exacto en ambas
  rutas: la inferencia DuckDB de `Decimal("1E-38")` podía degradar a DOUBLE.
  Parámetros Decimal no representables o enteros fuera de 64 bits se rechazan;
  para una conversión deliberada, pase texto y un cast SQL explícito
- La nueva API es experimental. Formatos anteriores, comparación, política de
  esquema, IR de migración y lectores históricos conservan sus contratos
- Fallos nativos tardíos envueltos por Arrow como `OSError` conservan cancelación
  o timeout, omiten SQL/valores del diagnóstico público y limpian staging.
  Los errores de escritura/fsync siguen identificándose como I/O


## Sin publicar — revisión del candidato 0.11.1

- STEP6: clasificación pública de estabilidad, política de deprecación y registro
  de capacidades por etapa. Lectura de fixtures históricas inmutables; rechaza
  versiones futuras en los expedientes, incluido environment.json rehasheado.
  Nuevas guardas Polars rechazan pérdida de dimensiones en captura/conversión.
- Metadatos Python ampliados a 3.12/3.13 tras evaluación, con locks revisados y
  matriz ejecutable de extras/dependencias mínimas directas y recientes permitidas.
  Cada resultado identifica el mismo wheel y su entorno; no acredita SO/arquitecturas
  no ejecutados, compatibilidad de todo el rango, ni CI remota. Ver STEP6_CANDIDATE.
- Regresiones de transporte comprueban float16 con un escalar representable en
  Arrow20, sin admitir ese tipo. El test ML compara los splits con sklearn nativo
  y mantiene una prueba determinista de rechazo de bosque sin splits; no fija
  umbrales que difieren entre versiones nativas ni cambia el método del detector.

- STEP5: kit de primer uso con tres recetas autocontenidas, wheel identificado,
  dependencias bloqueadas con hashes, guía de interpretación y formulario de
  observación humana sin completar. Refactor pandas con clave/bolsa, migración
  nativa acotada pandas → DuckDB y receta pytest/CI existente con evidencia
  previa al fallo. El verificador instala el kit fuera del checkout y comprueba
  códigos, reportes y políticas; no se anuncia una prueba humana de cinco minutos,
  nueva compatibilidad, nueva semántica, CI remota ni publicación.

- El verificador del candidato actualiza dependencias locales `path` y vincula
  sus bytes runtime importados al cierre de fuente, para impedir que una copia
  antigua del mismo candidato valide accidentalmente el benchmark nuevo.
- STEP4: `assert_equivalent`, `equivalence_decision`, `EquivalencePolicy` y
  `EquivalenceDecision` exigen equivalencia completa bajo contrato, con hashes
  y referencia fijables y evidencia persistida verificable de forma opcional.
  Errores tipados distinguen diferencia, no evaluabilidad, garantía, evidencia
  y configuración; diagnóstico seguro y esquema de aceptación propio 1.0.
- Cambio de compatibilidad deliberado: truth testing de `ComparisonResult` y
  `EquivalenceDecision` lanza `TypeError`; use la aserción o campos explícitos.
  No cambia el formato serializado previo. No se convierte `not_evaluable` en
  `False`, diferencia ni éxito.
- CLI compare conserva códigos 0/1/2/3 y JSON stdout, añade diagnósticos seguros
  stderr y valida el resultado antes de emitir éxito. Recetas pytest/CI guardan
  una vista redactada antes del fallo, con cuatro archivos permitidos. Pruebas
  instaladas comprueban éxito/fallo y privacidad; no se añade plugin, dependencia,
  workflow remoto ni publicación.

- STEP3: `comparison_report` produce un `ComparisonReport` 1.0 común para JSON,
  consola, HTML y notebooks; redacción conservadora por defecto, tipos escalares
  fieles, posiciones por lado y recuentos exactos/cotas/desconocidos. No vuelve
  a ejecutar fuentes ni cambia `ComparisonResult` o el comparador.
- `write_comparison_report` y `read_comparison_report` publican/leen vistas
  independientes. Inspección de evidencia con raíz autorizada, límites, hashes
  y defensas frente a archivos corruptos/rutas/symlinks. Reproducción opcional
  de capturas materializadas con contexto y manifiesto; ejecución original,
  cifrado, borrado de originales y assertion helpers quedan fuera del alcance.
- HTML escapado sin scripts/recursos remotos y CSP; texto con controles visibles;
  pruebas de redacción, claves con ámbito, límites y fallos de publicación. El
  ejemplo de reporte corre también desde wheel, y la lectura/render usa la base
  instalada sin dependencias tabulares ni notebook.

- STEP2: `diff` acepta tablas eager pandas/Polars/Arrow, construye contratos a
  partir del esquema derecho y delega al mismo núcleo de comparación.
  `DiffContract`, constructores de clave/bolsa/secuencia y `read_diff_contract`
  hacen visibles todas las políticas y su procedencia sin cambiar los formatos
  anteriores. Claves explícitas, valores estrictos y fallback existente.
- Captura nativa con límites de filas/bytes, snapshots aislados, conservación de
  índices significativos y rechazos explícitos para categorías, metadatos sin
  política, tipos no fieles, planes lazy y relaciones DuckDB. No ejecuta SQL.
  Las opciones de comparación, diagnósticos y estados conservan su significado.
- Pruebas de paridad pública, captura, procedencia y claves globales; ejemplo
  directo ejecutado por el verificador del wheel fuera del checkout. No añade
  HTML/aserciones en STEP2, amplía versiones/plataformas ni publica paquetes.
- Cuarentena explícita del auxiliar incompleto `equiframe.benchmark`: sus siete
  funciones conservan los argumentos anteriores pero lanzan
  `UnsupportedBenchmarkError` antes de leer entradas, entrenar o escribir.
  Se retiran las métricas ficticias, la calibración con datos de entrenamiento
  y el proxy de conteo presentado como R; no hay resultados sustitutos.
- El módulo y `examples/benchmark_local.py` terminan con código 2 y una guía al
  paquete separado `equiframe_benchmark`; `--help` sigue disponible. Ese paquete
  no es un reemplazo directo: conserva sus requisitos de revisión y protocolo.
  Las API soportadas del núcleo, sus formatos y el import ligero no cambian.
- `equiframe compare` devuelve 0 solo para una comparación completa y
  `equivalent`, 1 para una completa y `different`, y 3 para todo `not_evaluable`,
  incluida una referencia esperada inválida con `complete=True`.

## 0.11.1 — 2026-10-03

- Decimales exactos de ingestión, IR, ejecución nativa y sumas R aislados del
  contexto decimal del consumidor, conservando sus flags y sin autorizar redondeo.
- Exponentes JSON fuera de rango siguen rechazo/cuarentena; expansión de registros
  comprueba presupuesto y cancelación antes de materializar la colección completa.
- Recibos de calidad vinculados a bytes de fuente, dependencias locales y
  wheel/sdist; evidencia histórica legible pero insuficiente para un candidato nuevo.
- Productores 0.11.1 añadidos a DetectorVersions conservando los anteriores y
  esquemas 1.0. Python 3.12, motores y dependencias bloqueadas sin ampliar soporte.

## 0.11.0 — 2026-10-03

- Verify reutilizable para artefactos, ejecuciones y migraciones; dimensiones
  separadas y puente opcional de O, sin cambiar los algoritmos R/M/B/H.
- CSV/JSON/JSONL con esquema explícito, copias originales, conversiones exactas,
  rutas/grano y cuarentena; workflow de checkpoints y destino Parquet con staging,
  gate de Verify, versiones, visibilidad local atómica e idempotencia.
- JSON vacío rechazado sin salida; desbordamiento timestamp rechazado o puesto
  en cuarentena antes de materializar Arrow, conservando límites int64 exactos.
- Carga Parquet rechaza colisiones de nombres sin distinguir mayúsculas antes
  de escribir; recibos y versiones conservan una identidad física inequívoca.
- IR nativo ampliado con aritmética acotada, coalesce, condiciones, concatenación,
  deduplicación explícita y semi/anti join. Capacidades/rechazos trazables por prueba.
- Bundles cerrados para Verify/migración/workflow, lectura relocalizada sin ETL,
  protección de rutas y comprobación de decisiones/refencias a evidencia.
- API/CLI, once esquemas nuevos, productores previos de detectores preservados,
  ejemplos genéricos y OCDS sintético/consumidor real sin descarga implícita.
- Twine reproducible, verificadores de wheel/sdist ampliados, manifiesto de
  candidato y automatización separada de publicación. Python 3.12 sin ampliar
  plataformas; licencia, publicación e integración DW/OCI pendientes.


- Informes de migración distinguen la comparación con el esperado aportado de
  EquiFrame Verify (O), cuya independencia/revisión humana no establece el runner.
  Resúmenes conservan estados y evidencia de las tres comparaciones por separado,
  mantienen la clave histórica y permiten leer reportes previos completos.
- Pruebas integradas de las seis direcciones para NULL/NaN, uniones many-to-many
  sin coincidencia NULL, claves/multiplicidad y sumas Decimal por moneda con
  esperados literales. Son verificaciones sintéticas de software.

## 0.10.0 — 2026-10-03

- EquiFrame Migrate: IR relacional estricto, compiladores nativos Pandas/Polars/
  DuckDB y registro explícito extensible; seis direcciones entre los tres motores.
- `migrate`, `check_migration`, `read_migration` y `migration_summary`; captura
  única aislada, comprobación de ambos motores antes de ETL, esperado separado,
  perfiles/detectores congelados y presupuestos cooperativos de extremo a extremo.
- Diferencias observadas y comprobación contra esperado se conservan separadas.
  R es requerida por defecto; `require_rules=False` permite exigir solo los
  componentes declarados sin convertir estados ausentes de R/H en «sin alerta».
- CLI migration validate/run/verify, reportes, journal e inventario cerrado;
  lectura verifica archivos, referencias y metadatos físicos sin ejecutar ETL.
  Manifiesto publicado al final; operaciones interrumpidas permanecen visibles.
- Cinco JSON Schema nuevos 1.0. `DetectorVersions` añade el emisor 0.10.0 y
  conserva productores anteriores; sus esquemas reciben la ampliación compatible
  de enum/default. No cambia el algoritmo de inferencia ni entrena durante migración.
- Ejemplo con Decimal, monedas, grupos nulos y esperado literal independiente.
  Timestamps/operaciones float declaradas fuera del IR inicial; plugins confiables,
  límites de buffers tras materialización y evidencia local sin portabilidad automática.

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
