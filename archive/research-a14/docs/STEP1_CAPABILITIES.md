# STEP1: capacidades declaradas y verificación del candidato

Fecha: 2026-10-04. Este inventario complementa
[SEMANTIC_SUPPORT.md](SEMANTIC_SUPPORT.md) y su
[matriz JSON](SEMANTIC_SUPPORT.json), que conserva operaciones, políticas,
direcciones, estados y nodos pytest. No se duplica esa matriz ni se amplía
soporte por producto cartesiano entre sus filas.

## Cómo leer la evidencia

- **D — declarado:** contrato, metadata o documentación; no prueba ejecución
- **S — fuente contrastada:** implementación y prueba localizadas; todavía no
  demuestra ejecución de esos bytes
- **V — ejecutado en candidato:** exige recibo con SHA/huella de fuente,
  versiones, entorno, comando, resultado y límites enlazado desde la
  [ficha del candidato](STEP1_CANDIDATE.md)
- **H — histórico:** ejecución atribuida a otra revisión/entorno. Se conserva
  como antecedente, sin promoverla a V
- **P — pendiente/no implementado:** no se anuncia como capacidad disponible

**Verificación local cerrada:** las suites de los dos paquetes y sus instalaciones
externas aprobaron en Linux x86_64 / Python 3.12.14, con nueve etapas por paquete.
Los hashes de fuente, artefactos y recibos están en la [ficha](STEP1_CANDIDATE.md).
V en esta tabla se limita a los casos de prueba referenciados y a ese entorno;
no verifica automáticamente todos los tipos/valores de la columna declarada.
Los resultados históricos conservan su fecha y alcance. Los roles siguen siendo
responsabilidades a asignar, no aprobación de personas concretas.

## Subconjunto inicial elegido

Los pilotos usan tablas finitas sintéticas y tipos escritos expresamente:

| Tipo inicial | Política / uso previsto | Exclusiones del subconjunto |
|---|---|---|
| Boolean | Valor exacto; NULL solo en columnas nullable declaradas | Sin coerción string/integer→boolean |
| Signed int64 | Identificadores/medidas exactos; claves completas únicas cuando se declaren | Sin asumir representación exacta en float ni overflow permitido |
| String | Texto exacto, incluidos `001`, vacío y Unicode | Sin trim, collation, casefold o normalización Unicode implícitos |
| Float64 | Medida separada; exacta o tolerancia fijada de antemano; NULL y NaN explícitos | No claves aproximadas, sumas IR float ni dinero en float |
| Decimal(10,2) | Importe exacto; agregación de piloto a Decimal(12,2), moneda en columna separada | Sin división, multiplicación/redondeo Decimal IR, escala variable o paso por float |

Tipos de frontera incluidos para preservar pruebas existentes, **sin ampliar el
piloto SQL/IR**: date32 como día; timestamp ns/UTC o naive con política explícita
en captura/comparación; signed/unsigned de otros anchos y Decimal128/256 según
capacidad de cada ruta. La tabla siguiente distingue esas etapas. [Tipos
públicos](API_CONTRACTS.md#2-modelos-materializados), [transporte](../packages/equiframe/src/equiframe/tables.py).

## Matriz operacional por etapa y adaptador

Cada fuente/test es relativo a esta revisión. Los nombres de pruebas enlazan
al archivo que los define; la matriz JSON conserva nodos parametrizados cuando
ya existen. «Condicionado» nunca significa todos los valores o combinaciones.

| ID | Etapa / adaptador | Tipo o capacidad | Declarado / fuente contrastada | Evidencia de referencia | Límite | Rol responsable |
|---|---|---|---|---|---|---|
| C01 | Captura Arrow / IPC file / Parquet | boolean, integer, string, float32/64, Decimal128/256, date32/64, timestamp; null con política | S + V de casos referenciados, condicionado | [check_arrow](../packages/equiframe/src/equiframe/tables.py), [test_local_file_integrity_and_exchange](../packages/equiframe/tests/test_execution.py), [test_physical_mapping_is_lossless_and_explicit](../packages/equiframe/tests/test_comparison.py) | No structs/lists/maps/binarios/dictionary ni Arrow stream; captura no equivale a soporte de todos los motores | Núcleo / captura |
| C02 | Captura pandas | boolean/int64/string/float64 y máscaras nullable | S + V de casos referenciados, condicionado | [pandas_capture](../packages/equiframe/src/equiframe/tables.py), [test_scalar_types_boundaries_and_masks](../packages/equiframe/tests/test_execution.py) | NULL/NaN ya confluidos al construir el frame no se recuperan | Adaptador pandas |
| C03 | Captura pandas | Decimal homogéneo de escala fija; índices separados | S + V de casos referenciados, condicionado | [pandas_capture](../packages/equiframe/src/equiframe/tables.py), [test_decimal_exact_beyond_float53 / test_index_requires_explicit_transport_policy](../packages/equiframe/tests/test_execution.py) | Rechazo de Decimal no finito/cero negativo/exponentes distintos; índice no se convierte en clave | Adaptador pandas |
| C04 | Captura pandas | category, object heterogéneo, timestamp object | S + V del rechazo deliberado | [pandas_capture](../packages/equiframe/src/equiframe/tables.py), [test_pandas_uncapturable_object_values_fail_before_callback](../packages/equiframe/tests/test_execution.py) | No convertir silenciosamente a etiquetas/string/float | Adaptador pandas |
| C05 | Captura/ejecución Polars | Tipos escalares iniciales y DataFrame/LazyFrame | S + V de casos referenciados, condicionado | [PolarsAdapter](../packages/equiframe/src/equiframe/adapters.py), [test_polars_lazy_input_and_consumer_protected](../packages/equiframe/tests/test_execution.py) | LazyFrame materializa con collect; no promesa out-of-core universal, categorías/nested fuera del transporte | Adaptador Polars |
| C06 | Ejecución/captura DuckDB | SQL SELECT/WITH registrado; escalares admitidos, Decimal≤38 | S + V de casos referenciados, condicionado | [DuckDBAdapter](../packages/equiframe/src/equiframe/adapters.py), [test_duckdb_values_are_bound_and_identifiers_are_controlled](../packages/equiframe/tests/test_execution.py) | Conexión privada; resultado Arrow materializado; no consumo directo de relación externa por `compare` | Adaptador DuckDB |
| C07 | Captura temporal nativa | Date y timestamps por motor/unidad/zona | S + V de casos referenciados, condicionado | [capacidades adaptadores](../packages/equiframe/src/equiframe/adapters.py), [test_nanoseconds_zone_and_mask / test_zoned_us_offset_around_dst / test_naive_time_units_are_preserved_without_truncation](../packages/equiframe/tests/test_execution.py) | DuckDB zoned ns fuera de capacidad fiel; controles de rango/unidad. No implica timestamp en IR | Adaptadores / QA |
| C08 | Comparación independiente de motor | Boolean, enteros, string, Decimal exactos | S + V de casos referenciados, condicionado | [comparison / normalization](../packages/equiframe/src/equiframe/normalization.py), [test_integer_extremes / test_decimal_no_rounding_and_currency_preserved](../packages/equiframe/tests/test_comparison.py) | Contrato obligatorio; sin casts inter-familia automáticos; moneda/unidad no convertida | Núcleo / semántica |
| C09 | Comparación independiente de motor | Float, NULL, NaN, vacío, cero, infinitos | S + V de casos referenciados, condicionado | [normalization](../packages/equiframe/src/equiframe/normalization.py), [test_absence_nan_empty_zero_are_distinct / test_tolerance_boundary_zero_infinity_nan](../packages/equiframe/tests/test_comparison.py) | Tolerancia fija integer/float; valores especiales separados; no transitividad | Núcleo / semántica |
| C10 | Comparación independiente de motor | Date y timestamp ns/unidad/zona/DST | S + V de casos referenciados, condicionado | [COMPARISON](COMPARISON.md#tiempo-y-aproximaciones), [test_nanosecond_precision_and_time_units / test_dst_naive_policy](../packages/equiframe/tests/test_comparison.py) | Instant/wall-time y naive explícitos; calendario de zona 1..9999; no recuperación de offset textual por fila | Núcleo / semántica |
| C11 | Comparación por clave/secuencia/bolsa | Tipos admitidos, multiplicidad y tolerancia | S + V de casos referenciados | [comparison](../packages/equiframe/src/equiframe/comparison.py), [test_compound_scoped_and_incomplete_keys / test_sequence_ties_and_invalid_shared_order / test_maximum_matching_is_not_greedy_or_transitive](../packages/equiframe/tests/test_comparison.py) | Unicidad global comprobada; fallback de clave; matching máximo con presupuesto; `distinct` no deduplica | Núcleo / QA |
| C12 | Comparación / SQLite spill | Lotes, colisiones, límites e interrupciones | S + V de casos referenciados, con límites | [comparison](../packages/equiframe/src/equiframe/comparison.py), [test_spill_hash_collisions_batches_partitions_and_summary / test_partial_differences_retained_on_resource_limit](../packages/equiframe/tests/test_comparison.py) | Hash particiona, valores completos deciden; presupuesto cooperativo, no RSS duro | Núcleo / rendimiento |
| C13 | Migración, seis direcciones nativas | Scan int64/float64, left join int64/string N:M, sum/count Decimal(10,2)→(12,2), Project int32→64/boolean/string | S + V de casos acotados; H conservado | [runner](../packages/equiframe/src/equiframe/migration/runner.py), [test_semantic_native_directions_and_independent_validation_scope](../packages/equiframe/tests/test_migration_semantic_directions.py), [filas por dirección](SEMANTIC_SUPPORT.json) | pandas→Polars, pandas→DuckDB, Polars→pandas, Polars→DuckDB, DuckDB→pandas, DuckDB→Polars; no todos los operadores/tipos por dirección | Migración / QA |
| C14 | Migración IR en pandas/Polars/DuckDB | Inner/left/semi/anti; suma/resta Decimal; agregados exactos | S + V de casos referenciados, condicionado | [validation](../packages/equiframe/src/equiframe/migration/validation.py), [SEMANTIC_SUPPORT.json](SEMANTIC_SUPPORT.json), [tests ampliación](../packages/equiframe/tests/test_migration_etl_ir.py) | Escala/unidades y guard digit; claves float y right/full rechazados; límites conservadores por motor | Migración / adaptadores |
| C15 | Migración IR | Timestamp, Decimal multiply/divide/round, dedup first/last por clave | S + V de rechazos probados; P en ampliaciones | [validation](../packages/equiframe/src/equiframe/migration/validation.py), [filas rechazadas/pendientes](SEMANTIC_SUPPORT.json) | Fuera del IR actual; captura/comparación temporal no habilitan ejecución IR | Arquitectura / migración |
| C16 | Verify / salidas externas o migración | Acuerdo, esperado, integridad, R, cobertura y O separados | S + V de casos referenciados | [verify](../packages/equiframe/src/equiframe/verify.py), [test_equal_wrong_outputs_remain_agreed_but_failed_expected / test_expected_derived_from_test_engine_cannot_establish_O](../packages/equiframe/tests/test_verify.py) | Coincidencia no prueba corrección ni revisión; nombres declarados no autentican personas | Verify / QA |
| C17 | Ingestión | CSV/JSON/JSONL con boolean/integer/string/Decimal/date/timestamp declarados | S + V de casos referenciados, condicionado | [ingestion](../packages/equiframe/src/equiframe/ingestion.py), [tests](../packages/equiframe/tests/test_ingestion.py), [ETL](ETL.md) | Esquema/grano explícitos; rechazo o cuarentena; lectura materializada con límites; no inferencia aprobada automática | Ingestión |
| C18 | Workflow / destino / bundle | Checkpoints, publicación Parquet local, evidencia portátil | S + V de casos referenciados, condicionado | [workflow](../packages/equiframe/src/equiframe/workflow.py), [destinations](../packages/equiframe/src/equiframe/destinations.py), [bundle](../packages/equiframe/src/equiframe/bundle.py), [tests](../packages/equiframe/tests/test_workflow.py) | Sin resume ni DW/OCI; puntero local no garantiza durabilidad eléctrica/transacción distribuida | Operación / integraciones |
| C19 | CLI compare | Tres estados y códigos seguros | S + V de tabla y errores CLI | [CLI](../packages/equiframe/src/equiframe/cli.py), [tabla y regresiones CLI](../packages/equiframe/tests/test_comparison_decisions.py), [RFC](STEP1_SEMANTIC_RFC.md#contrato-del-gate-cli) | `not_evaluable` completo sale 3; configuración/persistencia no aprueban; recibo final en ficha | CLI / QA |
| C20 | Experimento auxiliar del núcleo | `equiframe.benchmark` | S + V de cuarentena explícita | [módulo](../packages/equiframe/src/equiframe/benchmark.py), [test_benchmark_quarantine](../packages/equiframe/tests/test_benchmark_quarantine.py) | Siete helpers fallan con `UnsupportedBenchmarkError`; CLI sale 2 salvo ayuda; no lectura, escritura, fit ni métricas. No es reemplazo del paquete científico | Núcleo / benchmark |
| C21 | Benchmark separado | Catálogo, splits, freeze, métricas/reproducción | S + V de APIs/casos técnicos; resultado científico no acreditado | [paquete](../packages/equiframe-benchmark/README.md), [evaluación](STEP_10_EVALUATION.md) | R/M/B/H/O independientes; requiere corpus, soporte y revisiones; fixtures no son evidencia empírica | Benchmark / metodología |
| C22 | Experiencia API | DataFrame directo, `ef.diff`, `summary()`, `assert_equivalent()`, `to_html()` de comparación | P, no API anunciada | [firma compare](../packages/equiframe/src/equiframe/comparison.py), [ComparisonResult](../packages/equiframe/src/equiframe/comparison_types.py) | Reutilizar primitivas; HTML/JSON de pipeline existente tiene otro alcance | Experiencia de desarrollo |
| C23 | Distribución / compatibilidad | Python 3.12, extras y cinco plataformas configuradas | D + H; V solo Linux x86_64 / Python 3.12.14 | [metadata](../packages/equiframe/pyproject.toml), [workflow](../.github/workflows/equiframe.yml), [release](RELEASE_CANDIDATE.md) | Rangos no son combinaciones ensayadas; CI manual no acredita jobs; licencia/nombre pendientes | Releases / QA |

## Cómo promover una afirmación a verificada

1. Elegir fila y nodo parametrizado exacto del inventario existente; declarar las
   versiones y política usadas, incluyendo los casos negativos
2. Ejecutar sobre el candidato fijado, conservar comando, resultados/skips,
   fuente antes/después y artefactos relacionados
3. Registrar V solo para ese alcance y entorno en la ficha o un recibo vinculado;
   no sustituir los estados semánticos de la matriz por un «todo soportado»
4. Ante un falso `equivalent`, retirar la afirmación afectada, guardar reproductor
   y corregir con regresión antes de ampliar el alcance

Una prueba de rechazo exitosa verifica una frontera segura, no que el operador
rechazado haya sido implementado. Una pasada de las suites tampoco acredita
todos los límites de rendimiento, versiones de dependencias o aceptación humana.
