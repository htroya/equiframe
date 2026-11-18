# STEP1: tres pilotos sintéticos acotados

Fecha: 2026-10-04. **Definiciones de aceptación, todavía no pilotos humanos
ejecutados.** Reutilizan APIs, ejemplos y pruebas del repositorio. No son nuevas
recetas implementadas ni evidencia de adopción, rendimiento o resultados
científicos. La instalación y sus resultados deben pertenecer al
[candidato identificado](STEP1_CANDIDATE.md).

## Condiciones comunes

- Datos pequeños, sintéticos y enumerados aquí; sin descarga externa, credenciales,
  DW, modelos entrenados ni datos SERCOP
- Python 3.12 y artefactos privados identificados con SHA-256; extras `engines`
  para P1/P2 y `arrow` para P3. Usar la [instalación del wheel del equipo](RELEASE_CANDIDATE.md),
  nunca resolver este candidato con un `pip install equiframe` público
- Contrato fijado antes de comparar, tipo físico y lógico explícitos; sin cast,
  redondeo, deduplicación ni inferencia de clave para hacer pasar resultados
- Población completa del fixture, no muestreo. Tiempo y tamaño son observaciones
  del entorno, sin meta de rendimiento acreditada
- Conservar contrato, capturas, versiones, estado/completitud, diferencias y
  recibos. Los resultados y logs quedan fuera de Git; solo fixtures sintéticos
  pequeños y código revisado pueden versionarse
- La persona que haga primer uso registra tiempo, ayuda, errores, diagnóstico e
  interpretación de los tres estados. La meta de cinco minutos es **por validar**
- Gate técnico: `state == "equivalent" and complete`; errores o falta de
  finalización fallan. La integridad del expediente es una comprobación adicional

## P1. Refactor pandas ↔ Polars: asignaciones por clave

**Responsables:** experiencia de desarrollo, adaptadores pandas/Polars y QA.
**Decisión:** comprobar si un refactor conserva valores por registro, aunque
coincidan conteos y totales. No se traduce Python arbitrario.

### Entrada y esperado independientes

Esquema de salida fijo: `id: int64 no nulo`, `account: string no nulo`,
`amount: Decimal(10,2) nullable`, `active: boolean no nulo`.
Clave única completa `id`, orden de filas ignorado, multiplicidad preservada,
valores exactos y NULL distinto de cero/vacío. `amount` tiene unidad declarada;
el fixture usa una sola moneda y no interpreta el texto como conversión monetaria.

| id | account | amount | active |
|---:|---|---|---|
| 1 | `001` | `10.20` | true |
| 2 | `002` | `20.30` | false |
| 3 | `003` | NULL | true |
| 4 | `004` | `0.00` | true |

El esperado es esta tabla escrita manualmente, no la salida de pandas. Los dos
callbacks propios reciben el mismo snapshot y proyectan las mismas columnas.
Capturar salidas con `execute` y comparar las salidas materializadas con
`compare`. El índice RangeIndex generado se ignora solo mediante política y
justificación expresa, como en los ejemplos existentes; no es una clave oculta.

### Casos que delimitan la aceptación

1. Permutar filas del candidato conserva `equivalent`, completo
2. Intercambiar `10.20` y `20.30` entre id 1/2 conserva el total y debe producir
   `different`, completo, con las dos asignaciones localizables
3. Duplicar id 4 solo en candidato incumple clave/multiplicidad; no se deduplica
4. Esperado con id duplicado produce `not_evaluable / invalid_expected` tras
   recorrido completo; la persona debe explicar por qué no es éxito
5. Extensión de frontera separada: columna float64 `[NULL, NaN, 0.0, 2.5]`
   con máscara preservada y `NaNPolicy(handling="distinct")`. No derivarla de una columna
   pandas NumPy que ya haya perdido la distinción NULL/NaN

**Reutilización:** [execute_native.py](../packages/equiframe/examples/execute_native.py),
[compare_local.py](../packages/equiframe/examples/compare_local.py),
[test_swapped_money_conserves_total_and_localizes_key](../packages/equiframe/tests/test_comparison.py),
[test_null_nan_zero_and_signed_zero](../packages/equiframe/tests/test_execution.py).
Estos ejemplos usan sus propios contratos/precisiones; adaptarlos a la tabla
anterior requiere una receta nueva revisada, no afirmar que ya ejecutan P1.

**No cubre:** categorías, MultiIndex como dato, objetos arbitrarios, timestamps
object, tablas mayores que memoria o fachada DataFrame directa. No se necesita
`ef.diff`, `summary()`, `assert_equivalent()` ni `to_html()` de comparación.

## P2. Migración acotada a SQL/DuckDB: suma por moneda

**Responsables:** migración, adaptador DuckDB y QA.
**Decisión:** comprobar una agregación declarativa en pandas→DuckDB y
DuckDB→pandas, preservando Decimal, multiplicidad y grupos totalmente NULL.
Las otras cuatro direcciones ya existen en el corpus, pero no se atribuyen a
este piloto de dos direcciones sin ejecutarlas.

### Entrada y esperado independientes

Entrada: `currency: string no nulo`, `amount: Decimal(10,2) nullable`:

| currency | amount |
|---|---|
| USD | `10.20` |
| USD | `10.20` |
| USD | NULL |
| EUR | `0.00` |
| GBP | NULL |

Esperado enumerado: `currency: string no nulo`,
`total: Decimal(12,2) nullable`, `rows: int64 no nulo`:

| currency | total | rows |
|---|---|---:|
| USD | `20.40` | 3 |
| EUR | `0.00` | 1 |
| GBP | NULL | 1 |

IR cerrado: `Scan` y `Aggregate`, `group_by=(currency,)`, `sum(amount)` exacto,
`count_rows`, `null_groups="retain"`, `empty_sum="null"`. Clave de salida
`currency`, orden ignorado, multiplicidad preservada. Conservar la regla
operacional de esquema cuando `require_rules=True`; no interpretar una colección
de reglas vacía como R evaluada. No ajustar tolerancia para una suma Decimal.

`check_migration` comprueba capacidades antes de ejecución; `migrate` captura
las entradas una vez y ejecuta dos rutas nativas, incluido SQL compilado para
DuckDB. El esperado se proporciona aparte. Comparar ambos con el esperado y
mantener separado acuerdo, corrección declarada e independencia humana de Verify.

### Casos que delimitan la aceptación

1. Ambas direcciones producen el esperado y el acuerdo completos
2. Un resultado materializado con USD=`10.20`, filas=2 detecta pérdida de una
   ocurrencia; no basta comprobar número de grupos ni total agregado global
3. Sustituir el NULL de GBP por cero produce diferencia bajo el contrato exacto
4. Variante de IR con división Decimal o timestamp: debe rechazarse por
   capacidad, sin inventar SQL equivalente ni normalización con pérdida
5. Corrida terminada conserva evidencia legible después del cierre de la
   conexión privada; renderizar/leer no vuelve a ejecutar la consulta

**Reutilización:** [migrate_native.py](../packages/equiframe/examples/migrate_native.py),
[test_semantic_native_directions_and_independent_validation_scope](../packages/equiframe/tests/test_migration_semantic_directions.py),
[SEMANTIC_SUPPORT.json](SEMANTIC_SUPPORT.json), [MIGRATION.md](MIGRATION.md).
El ejemplo existente usa Decimal(18,2)→(20,2); esta definición adopta
(10,2)→(12,2), como el fixture de la matriz, sin modificar aquel ejemplo.

**No cubre:** SQL arbitrario, relaciones DuckDB externas/lazy como input directo
de `compare`, timestamps en IR, joins adicionales, uso concurrente del DW,
sesiones globales, extensiones o permisos de infraestructura. Una comparación de
este fixture no prueba corrección de la traducción para todas las entradas.

## P3. Regresión en CI: tres estados y artefacto antes de fallar

**Responsables:** CLI, releases y QA.
**Decisión:** aceptar únicamente equivalencia completa desde una instalación
del wheel; conservar un diagnóstico revisable cuando el proceso falla.

Fixture mínimo `id: int64 no nulo`, exacto, orden ignorado, multiplicidad
preservada. `reference="expected"` identifica la derecha. El contrato y las
tablas Parquet se crean en un directorio temporal con los tipos explícitos.

| Candidato | Esperado | Decisión esperada | Exit de `equiframe compare --expected` |
|---|---|---|---:|
| `[1,2]` | `[2,1]` | `equivalent`, completo | 0 |
| `[1,2]` | `[1,3]` | `different`, completo | 1 |
| `[1]` | `[NULL]` | `not_evaluable / invalid_expected`, completo | 3 |
| `[1]` | Archivo ausente | `not_evaluable`, incompleto | 3 |

El JSON stdout conserva `comparison_id`, `state` y `complete`; el consumidor
localiza `comparison.json` y las diferencias antes de fallar su job. El reporte
es un artefacto del test, no un permiso para publicar datos. Un comando que
verifica integridad no se usa como sustituto del gate semántico.

Por API, añadir `max_rows=2` al candidato `[NULL,NULL,NULL]` frente a `[1,2,3]`:
debe conservar dos diagnósticos observados y devolver `not_evaluable`,
`complete=False`, `counts.final=False`. No inventar un flag CLI de presupuesto
que no existe. La aserción del consumidor comprueba estado y completitud con
Python normal; no invoca un método de aserción inexistente.

**Reutilización ejecutable:**
[test_comparison_decisions.py](../packages/equiframe/tests/test_comparison_decisions.py),
[test_cli_compare_outcomes](../packages/equiframe/tests/test_pipeline.py),
[verificador de distribución](../packages/equiframe/tools/verify_distribution.py).
Los tests existentes proporcionan reproductores; su presencia no acredita una
ejecución remota ni la observación de un consumidor independiente.

### Cierre del piloto

Una persona ajena a la implementación instala el artefacto identificado fuera
del checkout y provoca los cuatro resultados de la tabla. Explica por qué un
esperado inválido completo no aprueba, dónde ver la evidencia y cómo cambiar
deliberadamente el baseline tras revisión. Registrar SHA de wheel, plataforma,
versiones, comando, exit, estado, ayuda y resultado humano. No actualizar el
baseline automáticamente para hacer verde una prueba.

## Estado de adopción

Los tres pilotos están **definidos**. Faltan recetas ajustadas donde se indica,
ejecución contra el artefacto final y observación independiente. No se presenta
una ejecución sintética del desarrollador como tres proyectos externos ni como
una muestra estadística de adopción. Los bloqueos se convierten en hallazgos del
[backlog](STEP1_BACKLOG.md) con fixture mínimo y esperado separado.
