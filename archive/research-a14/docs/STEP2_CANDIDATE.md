# STEP2: candidato de entrada directa y contratos tipados

Fecha: 2026-10-05. **Verificación técnica local completada**. Esta ficha registra
la API y los bytes comprobados; no atribuye aceptación humana, resultados
científicos ni una matriz remota que no se haya ejecutado.

## Identidad y alcance

- Base: [`618ba7fac28160cc0d7540970652beec96f064a8`](https://github.com/htroya/equiframe/commit/618ba7fac28160cc0d7540970652beec96f064a8)
- Distribuciones privadas: `equiframe==0.11.1` y `equiframe-benchmark==0.11.1`
- El SHA final y la comprobación de `main` se registran en los manifiestos
  externos después del commit, evitando una referencia circular en esta ficha
- [API y límites](DIFF.md), [decisiones A129–A133](DECISIONS.md#entrada-breve-step2--2026-10-05)
- `diff` reutiliza el mismo comparador. `ComparisonResult`, `Contract` y
  `ComparisonSpec` conservan el esquema anterior. Los constructores y la
  procedencia usan un compañero separado; no hay un segundo motor

## Comportamiento entregado

1. Una llamada con tablas eager pandas/Polars/Arrow, referencia derecha esperada
   y claves solo explícitas; también las entradas materializadas anteriores con
   contrato explícito
2. Constructores tipados de bolsa, clave y secuencia; inferencia conservadora
   del esquema derecho; procedencia completa por campo, serialización y consulta
3. Captura separada y acotada, snapshots aislados, índices significativos y
   versiones de bibliotecas visibles; rechazos explícitos de pérdida de significado
4. Mismos estados, diagnósticos, infracciones, claves globales, fallback y
   matching máximo que el núcleo bajo el mismo contrato

En la revisión se reprodujeron pérdidas de metadatos en subclases de DataFrame,
subclases de escalares object y dtype NumPy. La entrada directa ahora las
rechaza antes de la conversión; sus regresiones forman parte de los tests.
También se probó fallo de publicación del compañero: se elimina su temporal y
se conserva el reporte válido del núcleo, propagando el error.

## Controles ejecutados sobre el mismo candidato

Entorno: Linux x86_64, glibc 2.41, Python 3.12.14. Dependencias efectivas:
pandas 3.0.6, Polars/runtime 1.44.2, PyArrow 25.0.1, DuckDB 1.5.6,
Pydantic 2.13.5, NumPy 2.5.3, scikit-learn 1.9.1 y tzdata 2026.4.
Hatchling 1.28.0 y Twine 6.2.0. No se modificaron los locks ni los rangos.

| Control | Núcleo | Benchmark |
|---|---:|---:|
| Sync bloqueado con todos los extras | Aprobado | Aprobado |
| Ruff check / format | Aprobados | Aprobados |
| mypy estricto | Aprobado | Aprobado |
| Assets generados, modo check | Aprobado | Aprobado |
| Suite completa sobre fuente | 1.380 passed | 456 passed |
| Build sin aislamiento | Aprobado | Aprobado |
| Twine check estricto wheel/sdist | Aprobado | Aprobado |
| Verificación de distribución | Aprobada | Aprobada |
| Suite completa instalada desde distribución | 1.380 passed | 456 passed |

Son **nueve etapas del candidato por paquete**, con cero fallos y cero
omisiones/xfail en ambas suites, tanto fuente como instaladas. Las pruebas
nuevas son 294: 136 de API pública/paridad, 79 de captura y 79 de constructores.
Las repeticiones instaladas y la revisión adicional no se suman como tests
únicos nuevos.

Los verificadores ejecutaron consumidores externos al checkout, import ligero,
API/CLI, extras por separado, ejemplos nativos y un consumidor tipado. El nuevo
ejemplo directo corre en Arrow/pandas/Polars; el consumidor tipado usa DataFrames
concretos e inferencia de esquema, además de las declaraciones públicas.
Ambos wheels se reconstruyeron **idénticos byte a byte** desde sus sdists.
El benchmark conserva su metodología y fuente, comprobado contra este núcleo.

### Huellas de fuente

Algoritmo `sha256-git-worktree-v1`, inventario completo de archivos de paquete:

- Núcleo, 189 archivos: `435271ab95472373cfa353feb483a3b6383062b9c07cd71f2036ea37d574d82e`
- Cierre benchmark + núcleo, 289 archivos: `e37a43ddf055d223a909ee53691869c67bcf636ceb1d2af8a93c748208e9adaf`

### Artefactos comprobados

| Artefacto | Bytes | SHA-256 |
|---|---:|---|
| equiframe-0.11.1-py3-none-any.whl | 201547 | `4598164791807a9db64b619a022acadacffdd6727c8b2b5e2120cadb522a922b` |
| equiframe-0.11.1.tar.gz | 519406 | `f6b2d36441e7807f0ffab2bf17df11fd111f17edafb09e5cd4d701861a84991e` |
| equiframe_benchmark-0.11.1-py3-none-any.whl | 103882 | `a774443387edba9f20ea0078ef83d8e6e17f17cb228171b8d51c856ebbabe9c1` |
| equiframe_benchmark-0.11.1.tar.gz | 309324 | `ca6919b1aad00b7870bced26bb5f3d0ffd28665e7854903756ff8bba4ced610d` |

Los recibos externos `core-checks.json` y `benchmark-checks.json` conservan
comandos, cwd, fechas, duración, logs, exit codes y huellas antes/después de
cada etapa. Los manifiestos finales vinculan esos recibos al commit limpio y
a estos artefactos. Son evidencia local no autenticada; no una firma ni CI remota.

## Límites y siguiente frontera

- Entradas directas eager admitidas, no todas las versiones/tipos de cada motor
- Relaciones DuckDB, planes lazy y lectores consumibles requieren materializar
  explícitamente; no se ejecutan por pasar un objeto a `diff`
- Políticas por unidad, categorías, índices o metadatos no se adivinan. `exact`
  sigue la firma lógica vigente; no promete identidad de dtype nativo
- Presupuestos cooperativos, no cuotas duras de RAM/tiempo ni benchmark de escala
- Procedencia suplementaria en el directorio original; no extensión de bundles
  anteriores ni autenticación criptográfica del productor
- Sin HTML, redacción, nuevos assertion helpers, cambios científicos, licencia,
  publicación en PyPI o despliegues
- Python 3.12/Linux local verificado; los workflows manuales y la ausencia de
  ejecuciones remotas se comprueban aparte, sin anunciar CI verde por inferencia

La presentación unificada y las aserciones futuras tienen alcance separado.
