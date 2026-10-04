# Matriz de soporte comprobable

[SEMANTIC_SUPPORT.json](SEMANTIC_SUPPORT.json) es la matriz legible por máquina.
Cada fila declara operación, tipo/fixture, motor, dirección, política, resultado
esperado, estado y nodo pytest concreto. No expande combinaciones sin pruebas.
La versión actual contiene **131 filas**. Las tres filas añadidas de categoría I
registran las dos ausencias parciales de relaciones SERCOP y la captura de bytes
verificados: pruebas dirigidas de fuente ejecutadas el 2026-10-03,
**3 passed en 6.46 s**. No atribuyen a esos tests una migración o publicación
que no ejecutaron. Los enlaces se cotejaron con una colección de **961 tests**,
anterior a las últimas regresiones del manifiesto; ese número identifica la
auditoría de nodos, no el resultado de la suite final. El resultado por fila queda
en la evidencia externa de revisión.
La pasada adicional añade cuatro filas de ingestión: JSON vacío inválido,
colección/stream vacíos explícitos y timestamp ns UTC fuera de int64 con rechazo
o cuarentena. Las seis regresiones aprobaron dentro de los **24 tests de
ingestión**. La nueva colección contiene **998 nodos**: **120 filas** tienen
su nodo localizado, **ocho** permanecen pendientes sin test y no hay referencias
ausentes. Esta colección acredita existencia de nodos; el resultado completo
de las suites se registra separadamente. La corrección adicional de publicación
añade tres filas sobre colisión física de nombres, conservación del previo y
validación del recibo. Sus ocho pruebas de destinos aprobaron; la colección
final contiene **1001 nodos**, **123 filas** ligadas a pruebas y **ocho**
pendientes, sin nodos ausentes. No se suman las colecciones históricas.
`native_single` significa ejecución independiente en cada motor con esperado;
no afirma una migración en seis direcciones de ese caso. `preflight` acredita
rechazo comprobado antes de ejecutar, no una implementación nativa del operador.

Los estados son `supported`, `supported_with_conditions`, `rejected` y `pending`.
La fecha de ejecución y alcance están en [ETL_REVIEW.md](ETL_REVIEW.md). La
ejecución final global/distribución complementa esa evidencia; esta matriz no
acredita todas las versiones de dependencias, plataformas ni volúmenes posibles.

Las seis direcciones Pandas→Polars, Pandas→DuckDB, Polars→Pandas,
Polars→DuckDB, DuckDB→Pandas y DuckDB→Polars tienen filas separadas para:

- Scan con signed64/float64 y distinción NULL/NaN.
- Left join con duplicados N:M, huérfanos y claves NULL never.
- Sum/count_rows Decimal por moneda con grupo enteramente NULL.
- Fixture Project/renombrado/multiplicación signed32→64/coalesce/conditional.

Cada caso conserva su propio esperado, política y pruebas. La concordancia entre
motores no prueba independencia del esperado ni revisión científica O. Las
pruebas técnicas no amplían los nueve estratos principales de la tesis.

| Categoría pedida | Casos ejecutables en matriz | Límites expresos |
|---|---|---|
| A. Esquema/tipos | Proyección/renombrado, widening exacto, ausencias/adicionales JSON, esquema vacío, overflow entero, categorías rechazadas | No aprobación automática de evolución/inferencia; categorías no se convierten a etiquetas |
| B. Ausencias | NULL/NaN nativos, lógica de tres estados, CSV token NULL frente a vacío/cero, campo inexistente, agregación totalmente NULL | Distinciones ya perdidas al construir un input externo no se pueden recuperar |
| C. Identificadores/texto | IDs `001`, claves compuestas, rutas de padre, literales NUL/comillas y contratos explícitos | Ningún trim/casefold/Unicode normalizado automático; claves por consumidor |
| D. Dinero/números | Decimal exacto, overflow, suma/resta con guard digit, asignaciones erróneas con suma global igual, matching aproximado no transitivo | Unidades iguales; monedas separadas por clave; división/redondeo/multiplicación Decimal IR pendientes |
| E. Joins | Inner/left NULL equal/never y N:M; semi/anti mantienen multiplicidad izquierda; extracción padre/hijo | Right/full rechazados; una cardinalidad comercial inválida necesita su propia regla/contrato |
| F. Agregaciones | Count_rows/count_valid/min/max, Decimal por moneda, grupos NULL/vacíos | Sumas exactas enteras/Decimal; float agregado común rechazado; límites nativos/conservadores |
| G. Orden/multiplicidad | Concatenate conserva ocurrencias, dedup todas columnas explícita, rechazo de empates, comparación por políticas | Dedup first/last por clave arbitraria pendiente; no se deduplica para corregir diferencias |
| H. Fechas | Ingestión días/ns/offset, comparación unidades/ns, validación DST gap/fold | Timestamp IR rechazado; no asunción de zona ni truncamiento temporal implícitos |
| I. Operación | Cancelación/timeout, dependencia ausente, expediente corrupto, fallo a mitad de carga/puntero, idempotencia, dependencia workflow | Controles cooperativos; sin cuota RSS dura, DW/OCI ni resume; bundles tienen sus pruebas en Verify |

Los casos `pending` registran capacidades fuera de implementación y no incluyen
nodo de prueba ficticio. Un rechazo deliberado de formato o semántica tampoco es
un defecto confirmado. Las garantías de staging/puntero, recursos y lectura
portátil están detalladas en [ETL.md](ETL.md) y la documentación de Verify.
