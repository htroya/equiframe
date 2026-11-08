# Revisión de Verify, ETL y candidato 0.11.0 — 2026-10-03

La entrega conserva el runner, comparación, R/M/B/H, migrador de seis direcciones
y herramientas de distribución. Añade contratos y utilidad sin reconstruirlos.
[Diseño Verify](VERIFY_DESIGN.md), [diseño ETL](ETL_DESIGN.md),
[revisión ETL](ETL_REVIEW.md) y [matriz trazable](SEMANTIC_SUPPORT.md).

## Línea base preservada

Raíz Git: `equiframe`; rama inicial
`codex/equiframe-verify-migration-20261003`, HEAD `bb0b3aa`;
`main` local `5c8f0ab`. Ambas revisiones eran posteriores a `origin/main` sin
divergencia. Se capturó `git archive` exacto de `bb0b3aa` y se comprobó separado
de los archivos nuevos. El único cambio preexistente era `HERNAN_ROADMAP.md`:
backup/diff fuera de Git, intención de pasos 11–20 conservada y estado vigente
conciliado; no reset, clean destructivo o force push.

Baseline núcleo: **856 passed, 835.63 s**, además de sync locked, Ruff,
format, mypy y assets aprobados. Es evidencia del commit base, no del candidato.
La extracción y logs viven en `revision_equiframe_20261003/baseline-core` del
workspace. El `uv` encontrado/instalado para esta sesión es 0.11.6 en una
carpeta de tooling local; Python del entorno, 3.12.4 sobre Windows x64.

## Clasificación de hallazgos

| Tipo | Hallazgo / tratamiento |
|---|---|
| Defecto confirmado | Integridad física y referencias de ejecuciones debían preservarse al componer Verify; se reutilizan compare/metadatos físicos y se reconstruyen decisiones al leer |
| Defecto confirmado | Una comparación completa A→A con hashes reconstituidos podía sustituir un peer A→B; lector exige pareja exacta, contrato, política, opciones y ejecución capturada |
| Defecto confirmado | Convertir esperado ExecutionResult en ArtifactRef ocultaba motor conocido; se registra `expected_source_engine` y dependencia, impidiendo O independiente |
| Defecto confirmado | Workflow aceptaba opciones distintas del checkpoint declarado; sólo permite reducir timeout con un deadline global y conserva los demás presupuestos exactos |
| Defecto confirmado | JSON Decimal con exponente extremo podía expandirse antes del rechazo; precisión/escala se validan antes de convertirlo a texto |
| Defecto confirmado | Extractor SERCOP podía omitir relaciones válidas ante arrays parcialmente ausentes y aceptar raíz mixta; ambos casos se rechazan con diagnóstico explícito |
| Defecto confirmado | Recibo de release podía aceptar commit inexistente y un único comando ajeno a los controles; ahora exige Git HEAD real, paquete limpio y nueve etapas completas con cwd exacto |
| Defecto confirmado en pasada extra | JSON vacío aparentaba ingestión completa; ahora se rechaza sin tabla, conservando colecciones/streams vacíos explícitos válidos |
| Defecto confirmado en pasada extra | Timestamp fuera de int64 eludía cuarentena y fallaba al materializar Arrow; ahora el rango físico se comprueba por registro y conserva ambos límites exactos |
| Defecto confirmado en pasada extra | Nombres de tablas `Table`/`table` podían sobrescribir Parquet y aparentar éxito en Windows; API/recibo rechazan colisiones antes de escribir y conservan el previo |
| Restricción deliberada | Timestamp IR, right/full, división/decimal multiply y ramas con aritmética peligrosa se rechazan; no son bugs |
| Mejora de producto | Verify externo, ingestión, workflow, Parquet idempotente, bundles, API/CLI y consumidor real fijado |
| Dependencia externa | DW/OCI, corpus efectivo, doble revisión/arbitraje, licencia/nombre/Trusted Publishing/acceso público |
| Evidencia histórica | Suites e informes antiguos conservados por fecha; no validan código nuevo ni plataforma del candidato |
| Preparación de entorno | Primer intento real usó copia core obsoleta instalada no editable en benchmark y falló sin FieldMapping; reinstalación corrigió entorno, no se atribuye al extractor |

Verify conserva el caso **ambos resultados coinciden y ambos están equivocados**:
acuerdo aprobado y cada salida vs esperado incumplida; carga bloqueada. La
integridad de un expediente no acredita equivalencia, esperado independiente ni
autenticidad de personas. Los tests de sustitución reconstituyen report/HTML/hash
para comprobar validación semántica, no sólo detección de un byte roto.

## Evidencia del candidato

Fuente final comprobada:
`09c3dfb22f904e8c74f7eb3c61214236cb09d768`, tras los fixes de ingestión
`0421486` y publicación `09c3dfb`. Los paquetes permanecían limpios al emitir
sus manifiestos; los cambios posteriores de documentación/configuración quedan
en un commit separado y no cambian los bytes de los paquetes. Las rondas
`617e59b` y `b2e3555` se conservan como históricas: no son la distribución final.

| Control final | Núcleo | Benchmark |
|---|---|---|
| Suite de fuente completa | 1000 passed, 1 skipped; 667.44 s | 440 passed, 2 skipped; 713.43 s |
| Sync locked, Ruff check/format, mypy, assets | Cinco controles, todos 0 | Cinco controles, todos 0 |
| Construcción wheel/sdist | 19.75 s; 0 | 12.55 s; 0 |
| Twine estricto de ambos archivos | 1.47 s; 0 | 2.70 s; 0 |
| Suite instalada desde sdist | 1000 passed, 1 skipped; 740.13 s | 440 passed, 2 skipped; 714.57 s |
| Verificador completo de distribución | 1167.62 s; 0 | 908.75 s; 0 |

Los skips corresponden exclusivamente a creación de symlinks sin privilegio en
esta cuenta Windows. El benchmark no cambió entre `b2e3555` y `09c3dfb`; se
conserva su ronda fuente válida y se revalidó su distribución contra el wheel
final del núcleo. Los verificadores comprueban imports ligeros, API/CLI, extras,
consumidores fuera del checkout y reconstrucción del wheel desde sdist idéntica
byte a byte. El núcleo comprueba además consumidor tipado; el benchmark ejecuta
piloto, integración y reproducción de seis CSV, sin aceptación científica.

Recibos finales externos, dentro del workspace: `candidate-core-final-extra-source`,
`candidate-core-final-extra-artifacts`, `candidate-core-final-extra-distribution`,
`candidate-benchmark-extra-source`, `candidate-benchmark-extra-artifacts` y
`candidate-benchmark-final-extra-distribution`. Cada carpeta de
`revision_equiframe_20261003` conserva `checks.json` y los logs completos.
`software-evidence-final.json` coteja sus etapas, resúmenes, consumidores y hashes;
`core-manifest-final.json` y `benchmark-manifest-final.json` registran nueve etapas
completas, cero comandos fallidos y cuatro bloqueos externos, `published=false`.
Los intentos interrumpidos quedan preservados como tales. No se suman rondas
repetidas como cobertura nueva ni se autentican personas/origen mediante hashes.

| Artefacto 0.11.0 | SHA-256 |
|---|---|
| `equiframe-0.11.0-py3-none-any.whl` | `4aba553a7fb942c8306adf61fea0027af2f0eb11b473ed01b37a6d8b5eba5699` |
| `equiframe-0.11.0.tar.gz` | `0e5350f239f1391c916fa7d23aa399489a256b4a8a1b15f86257448a71c7be4e` |
| `equiframe_benchmark-0.11.0-py3-none-any.whl` | `1ff7f563e0e2b3e7da92754a9f18c4cab2e4b1d81c6f2c9d7996a49a80bb54e2` |
| `equiframe_benchmark-0.11.0.tar.gz` | `e5cf7a9fa7de17f14077454d5250334c33df70e68939090c97873a2b0cc6ce5a` |

Rondas focalizadas ya ejecutadas: ETL/migración **109 passed**; ingestión/workflow/
destino final **28 passed**; casos de soporte **23 passed**; CLI ETL **5 passed**;
Verify/bundle/CLI previo al último refuerzo **38 passed, 1 skipped** (privilegio
symlink ausente en Windows); puente+oracle **45 passed**. Son rondas distintas
y parcialmente solapadas. La matriz final tiene **131 filas**: 123 nodos de prueba
encontrados y ocho pendientes sin test, cotejados con una colección de 1001 nodos;
cero referencias faltantes. No afirma
haber ejecutado un producto cartesiano de casos.

Se preserva una ronda consumidor con un fallo de configuración del esperado:
`ExpectedProvenance` rechazó correctamente autores vacíos. Se corrigió el
consumidor para conservar método/bytes en el recibo y omitir provenance cuando
no hay autores conocidos; no se atribuyen nombres ni independencia. La ronda
posterior consumidor/workflow aprobó 13 casos; las regresiones de estructura y
captura se ejecutaron además antes de la suite final congelada.

## SERCOP y recursos

Snapshot real `sercop-e094d8d94ba48b29`: tres paquetes, dos awards,
USD **75880.00**; puentes de proveedores/items sin monto. La primera corrida
fuente válida aprobó seis migraciones, cinco tablas cargadas, idempotencia y
bundle relocalizado: 95.59 s, RSS muestreada del árbol 243523584 bytes y
2876499 bytes de archivos de salida/evidencia. Incluye comparación y evidencia;
no es un benchmark de rendimiento aislado, cuota dura o demostración de escala.
Los costos internos sumados de expedientes copiados no son fases aditivas.

La corrida final desde ambos wheels instalados en entorno externo aprobó
`reconcile_awards`: diez controles conformes, dos claves y USD75880.00 exactos;
incluyó cinco cargas, retry idempotente y bundle relocalizado. El esperado
manual inspecciona sólo las dos asignaciones de awards y su suma por moneda.
Relaciones tienen esquema/huérfanos comprobados; no un esperado humano completo.
`scientific_O=not_established`; `DW_OCI_integration=not_requested`.
[Fuentes, hashes, fechas y reproducción](SERCOP_EXAMPLE.md).

Medición final SERCOP, tras el fix `09c3dfb`, desde los dos wheels instalados:
**44.22 s** de proceso, RSS máxima muestreada del árbol **247803904 bytes**
(201 muestras) y **2923270 bytes** de salida/evidencia antes de escribir el
recibo de recursos. La descarga previa no está incluida. La ronda anterior de
144.00 s se conserva como histórica; estas mediciones concurrentes no permiten
atribuir su diferencia a una mejora de rendimiento del código.

| Fase secuencial del consumidor SERCOP | Segundos |
|---|---:|
| Ingestión y extracción | 6.69 |
| Preparación del esperado y comparación del subconjunto | 0.14 |
| Relaciones y preparación del plan | 0.03 |
| Seis migraciones nativas, con comparación y evidencia | 15.99 |
| Verify y lectura de evidencia | 4.22 |
| Staging, carga, lectura posterior y retry idempotente | 3.33 |
| Exportación, importación y lectura del bundle | 8.79 |
| Reconciliación adicional del benchmark | 0.74 |

Las fases abarcan 40.65 s hasta preparar el resumen; wall total también incluye
inicio/importación y terminación. Se ejecutaron junto con otras suites locales:
no es una medición aislada. RSS suma procesos y puede contar páginas compartidas
más de una vez; muestrear cada 200 ms no garantiza observar el pico absoluto.

Comercio: CSV sintético, dos checkpoints nativos, USD14.00/EUR9.00, esperados
literales, Parquet idempotente y workflow portátil. También se conserva el
ejemplo genérico `etl_local.py` USD10.30/EUR8.00. Ninguno es dato SERCOP real.
El comercio final desde wheel aprobó ambos checkpoints/Verify, dos tablas
cargadas, idempotencia y workflow portátil: **56.09 s**, RSS muestreada
**226177024 bytes** y **3197607 bytes** de archivos de salida/evidencia. La ronda
anterior de 125.20 s se conserva como histórica, sin inferir una aceleración. El Verify
genérico instalado confirmó acuerdo aprobado, ambos esperados incumplidos y
publicación bloqueada. Los seis comandos del consumidor externo terminaron 0.

## Límites y siguiente frontera

Python 3.12/Windows x64 ejecutado; CI manual configurada, sin jobs remotos del
candidato. Importadores materializados, presupuestos cooperativos, sin RSS duro,
resume de workflow, procesamiento distribuido ni integración DW. El IR común
es un subconjunto con capacidades/rechazos por prueba. Lectores no ejecutan ETL.
Puntero Parquet ofrece visibilidad atómica local con escritor cooperante, sin
afirmar durabilidad de corte eléctrico o transacción distribuida.

No cambia el protocolo científico: tres parejas × tres familias = nueve estratos.
No entrena/recalibra modelos ni convierte fuentes/duplicados/reutilizaciones en
N efectivo de aprendizaje. [Candidato de distribución](RELEASE_CANDIDATE.md)
identifica los pendientes de licencia/nombre/acceso/Trusted Publishing antes de
publicar. La subida a Git `main` sí está autorizada y se verifica por SHA remoto.
