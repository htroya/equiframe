# STEP7: captura explícita y fidelidad DuckDB

Candidato privado `0.11.1`; cambios sobre STEP6 en la rama secuencial de trabajo.
No constituye publicación PyPI, aceptación humana, integración al DW ni soporte
universal de plataformas. La implementación y sus pruebas amplían la captura;
no modifican el protocolo experimental ni la trazabilidad de la tesis.

## Resultado y fronteras

- `capture_duckdb` y `DuckDBCaptureOptions` añaden una API experimental explícita:
  SELECT/WITH confiable, consumo único por lotes, snapshot Arrow IPC desacoplado,
  tipos nativos/Arrow, versión, ajustes seleccionados e intervalo de captura
- Conexión privada restringida o préstamo exclusivo declarado. El préstamo no
  cambia configuración, registros o transacción ni cierra la conexión. Consume
  su result slot y puede interrumpirla; la recuperación de transacciones abortadas
  corresponde al dueño. No se aceptan lectores/resultados previos o planes lazy
- La admisión cerrada **antes de Arrow** se comparte con `DuckDBAdapter`. Evita
  publicar UHUGEINT máximo como Decimal(-1), corrupción observada con DuckDB
  1.5.6 pese a pasar la validación Arrow. Rechaza además UUID y otros tipos que
  perderían identidad o no tienen semántica admitida
- La revisión independiente detectó que DuckDB infería como DOUBLE parámetros
  `Decimal("1E-38")` y otros con ceros fraccionales iniciales. Ambas rutas ahora
  enlazan un valor decimal nativo tipado desde texto exacto, conservando coeficiente
  y exponente. No hay intermediario float ni reescritura de SQL
- Decimal hasta 38, enteros 8–64, NULL/NaN, texto, DATE y timestamps finitos
  tienen pruebas de valor independiente, tipo, límites y rechazo. La división
  Decimal de SQL conserva su tipo DOUBLE; no se maquilla como resultado exacto
- El núcleo comparador conserva su independencia, estados, políticas y lectores.
  Los formatos históricos no se reescriben. No hay ampliación de IR de migración,
  schema approval, deduplicación correctiva, categorías/nested o SQL sandbox

## Recorrido y paquete de conformidad

[Uso y propiedad](DUCKDB_CAPTURE.md),
[ejemplo instalable sin red ni pandas](../packages/equiframe/examples/capture_duckdb.py),
[matriz semántica](SEMANTIC_SUPPORT.md),
[registro de capacidades](ADAPTER_CAPABILITIES.md).

Desde el sdist extraído o checkout, con el candidato y dependencias de pruebas
instalados en el intérprete seleccionado:

```bash
python -m pytest -q tests/test_duckdb_capture.py tests/test_duckdb_native_fidelity.py
python examples/capture_duckdb.py --output nuevo-reporte-duckdb
```

La suite de conformidad tiene 198 casos sobre conexión prestada/privada,
concurrencia entre capturas, consumo único con y sin parámetros, fuente mutable,
cierre, errores después de lotes previos, cancelación, límites y timeout,
valores esperados independientes, Unicode/colación, Decimal y parámetros,
instantes/unidades, promoción DATE por sesión, multiplicidad N:M, invariancia de
lotes, tipos rechazados, datos/manifiesto adulterados y HTML redactado.
El corpus incluye un error nativo real de conversión tras lotes previos y
fallos inyectados del lector. Los errores nativos envueltos por Arrow se
redactan y conservan cancelación/timeout; los de fsync no se reclasifican.
Los índices/categorías/metadata ya
rechazados por las otras rutas conservan sus corpus previos.

El ejemplo cambia/elimina la tabla y cierra la conexión antes de comparar contra
cinco filas literales independientes; el reporte se lee y renderiza después de
borrar capturas privadas. Con `--output` sólo retiene cuatro archivos redactados.
`verify_distribution.py` y `verify_compatibility.py` ejecutan el ejemplo en los
perfiles DuckDB apropiados y vinculan la prueba al wheel/sdist exactos.

## Límites operativos y semánticos

Los límites son cooperativos sobre filas, tamaño de cada lote, archivo final y
tiempo. Un fetch, binding parametrizado o estado interno de consulta puede
materializar/consumir recursos antes del siguiente checkpoint. No se afirma
memoria constante, zero-copy, cuota RSS, latencia dura o soporte mayor que RAM.
El registro de intervalo/sesión no autentica una versión externa ni coordina dos
sistemas. El llamante debe excluir lectores pendientes, SQL concurrente y cambios
externos durante captura. SQL confiable puede tener efectos: no es una sandbox.
No se descargan extensiones automáticamente ni se usa conexión global.

Los tipos HUGEINT/UHUGEINT, UUID, ENUM, JSON, BLOB/BIT, TIME/TIMETZ, INTERVAL,
arrays/listas/struct/maps/unions y extensiones desconocidas no se admiten como
resultados. Parámetros Decimal no finitos, cero negativo, exponente positivo o
precisión/escala >38 y enteros fuera de signed/unsigned 64 bits se rechazan.
Un cast deliberado del consumidor necesita rango y significado justificables.
No se recuperan ns, labels de zona por fila, nullability o colaciones de origen
que DuckDB ya haya perdido. TIMESTAMPTZ conserva microsegundos y zona de sesión.

## Validación final del candidato

Validación local de los bytes v2 en Linux x86_64, Python **3.12.14 y 3.13.5**.
El commit que contiene esta ficha conserva los mismos bytes de paquete; el
expediente externo vincula su SHA Git, fuentes, comandos y artefactos.

| Control | Resultado observado |
|---|---|
| Núcleo, nueve gates finales | Todos aprobados; **2 559** tests de fuente y **2 559** instalados desde sdist |
| Benchmark, nueve gates finales | Todos aprobados; **456** tests de fuente y **456** instalados con el núcleo actual |
| Matriz núcleo | **8/8 celdas**: ambos Python × extremos mínimos/recientes × perfiles `duckdb`/`all` |
| Suite completa en matriz | **2 559** tests en cada una de las cuatro celdas `all`, sin skips/xfails |
| Matriz benchmark instalada | **4/4 celdas**, ambos Python × extremos; **456** tests cada una, sin skips/xfails |
| Consumidor técnico independiente | **18** tests en cada una de cuatro instalaciones; 200 tuplas Decimal con semilla por celda y contexto de precisión 2 |
| Auditoría adicional de frontera | **16** ensayos instalados reales de error/interrupción/propiedad y valores escalares |
| Matriz semántica | **155** filas: 147 con nodo encontrado y ocho pendientes explícitos; cero nodos ausentes |

Las celdas `duckdb` ejecutan consumidores API/CLI y ejemplos, no la suite completa.
Los mínimos directos resueltos incluyen Arrow 20.0.0, Pydantic 2.12.0, Typer 0.20.0
y tzdata 2025.2; los recientes, Arrow 25.0.1, Pydantic 2.13.5, Typer 0.27.2 y
tzdata 2026.5. DuckDB observado es 1.5.6 en ambos extremos. Los locks/recibos
conservan todas las dependencias reales, incluida la diferencia con el lock de
desarrollo. Estos puntos no acreditan cada versión o combinación intermedia.

Los nueve gates por distribución son sync bloqueado, Ruff, formato, mypy,
assets, pytest completo, build, Twine estricto y verificación de distribución.
Se verificaron imports ligeros, consumidores tipados, perfiles aislados, ejemplos,
kit previo, origen en site-packages y reconstrucción byte a byte del wheel desde
sdist. Las repeticiones del corpus no se suman como observaciones independientes.

Artefactos privados exactos, SHA-256:

- Núcleo wheel: `bc97a9cf3ba6b7a950235f18450bbfbd9307b7703b2a4235b047325691034a1b`
- Núcleo sdist: `51f7d1081a9ecc18d08c6816d6cacce6f651526d6a954b2e5826e8037f2d365f`
- Benchmark wheel: `9a51e7cea5dc39df83ecb6d601af3a4e368a4c2e2a9bf1b3d4b1487bc74f12b5`
- Benchmark sdist: `345ac1a0a0714ee35f3eaeded00774049cf5f629974fe9ea661eacea026f1c18`

La huella de fuente del núcleo es
`326eed6a931bdaeda58eda6fb35b0e2fa93590dbfdb1d1043f88f654f981a5a9`
(`sha256-git-worktree-v1`, 353 archivos del paquete). El consumidor independiente
cotejó 70 archivos de paquete y dos de metadata en cada instalación con el wheel;
el sdist conserva esos mismos 70 archivos de paquete.

### Hallazgos, reintentos y límites de aceptación

El primer artefacto fue reemplazado después de detectar que Arrow envuelve errores
nativos tardíos como `OSError`: podían exponer SQL/literales o perder la clasificación
de cancelación/timeout. La versión final verifica errores reales tardíos y limpieza,
comprueba interrupción antes de clasificar y mantiene separados los fallos de I/O.
Las causas encadenadas pueden contener datos y se reservan a depuración privada.

Un intento de distribución v2 agotó el tmpfs de `/tmp` al instalar mypy. Sin cambiar
fuente ni artefactos, se repitieron los nueve gates del núcleo usando disco de la
nube. El fallo y los intentos interrumpidos se conservan como tales; los recibos
finales identifican únicamente ejecuciones terminadas. No se cuentan colecciones,
pruebas preliminares o comandos interrumpidos como validación final.

Los hashes identifican integridad/identidad, no autentican ejecutores o revisores.
No hay aceptación humana ni de DW, publicación PyPI, ampliación de metodología,
medición de escala, CI remota ejecutada o verificación nueva en Windows/macOS/ARM64.
La hoja de ruta externa no se versiona y `THESIS_TRACEABILITY.md` conserva sus bytes.
El paso 8 debe medir recursos y rendimiento sobre esta base antes de prometer escala.
