# EquiFrame

Contratos semánticos tipados, comparación completa y ejecución de transformaciones con
**Pandas, Polars y DuckDB**. Cada motor ejecuta su propia implementación;
EquiFrame conserva los datos, tipos y diagnósticos necesarios para revisar el resultado.

## Funcionalidad

- Contratos estrictos, inmutables y versionados para esquemas, claves, multiplicidad,
  orden, decimales, ausencias y fechas.
- API Python `import equiframe as ef`, registro explícito de transformaciones e
  inyección de fuentes, adaptadores y almacenes.
- Ejecución nativa de callbacks Pandas, DataFrame/LazyFrame Polars y consultas
  DuckDB parametrizadas.
- Entradas Arrow, Pandas, Polars, Arrow IPC y Parquet locales; artefactos verificables
  mediante SHA-256 y un manifiesto por ejecución.
- Estados y diagnósticos de fallo, cancelación, tiempo y recursos; CLI para validar contratos.
- Comparación por clave, multiconjunto o secuencia, normalizaciones autorizadas,
  tolerancias, spill y evidencia verificable; API `ef.compare` con solo el extra Arrow.
- Reglas operativas R sobre una ejecución capturada, precondiciones, cobertura,
  catálogo versionado y evidencia propia; API `ef.evaluate_rules` con solo Arrow.
- Benchmark separado con esperados independientes, revisión ciega, grupos
  transitivos, particiones auditables y selección normal para entrenamiento.
- Perfiles de cinco familias con denominadores y recibos de conversión;
  preprocesamiento con medianas congeladas y matriz común para M/B.
- Isolation Forest y MAD por familia, calibración normal externa con alpha explícito,
  restauración JSON sin pickle e híbrido H que conserva componentes no evaluables.

**Candidato actual: núcleo y benchmark 0.11.1**, con Verify reutilizable, ingestión, workflows, carga local y evidencia portátil. Una ejecución `completed` confirma que la
transformación terminó y se materializó. La [comparación semántica](docs/COMPARISON.md)
evalúa salidas materializadas. [R](docs/RULES.md) evalúa reglas seleccionadas del
contrato sobre una captura. El benchmark técnico conserva revisiones pendientes;
la evaluación científica sigue en la
[hoja de ruta](docs/HERNAN_ROADMAP.md).

La [revisión integral 0.11.1](docs/COMPREHENSIVE_REVIEW_20261003.md) fortalece
decimales exactos, límites de ingestión y coherencia de evidencia. El benchmark
añade [contrastes pareados descriptivos](docs/PAIRWISE_EVALUATION.md) con métricas,
denominadores y exclusiones por pareja de métodos, preservando reportes previos.
La [matriz de preservación](docs/COMPREHENSIVE_REVIEW_SCOPE_20261003.md) vincula
estos cambios con la última tesis y las actividades comunicadas a José y Jhair.

`ef.run_pipeline` integra ejecución/R/perfil/M/B/H y comparación opcional, con
eventos append-only, manifiesto verificable y reportes JSON/HTML. Incluye CLI
operacional, comandos del benchmark y reducción de casos que conserva
precondiciones/fallo bajo presupuesto. [Uso](docs/ORCHESTRATION.md),
[diseño](docs/STEP_08_DESIGN.md) y [verificación](docs/STEP_08_REVIEW.md).

El benchmark añade consumidor de snapshots fijados, integración sobre tres
ejecuciones nativas y reconciliación configurable de adjudicaciones por moneda.
La [conformidad del paso 9](docs/STEP_09_REVIEW.md) usa datos sintéticos; el cliente,
snapshot, DDL y entorno reales de José/Jhair continúan pendientes.

## Instalación

[EquiFrame Migrate](docs/MIGRATION.md) declara un plan relacional, ejecuta sus
implementaciones nativas en origen/destino y compara sus resultados, con un
esperado independiente opcional. Admite las seis direcciones entre Pandas,
Polars y DuckDB; documenta capacidades, presupuestos y evidencia verificable.
La tesis mantiene tres familias principales y las tres parejas, con nueve
estratos; las cinco familias genéricas de perfiles son capacidades del producto.

La [revisión del tutor](docs/THESIS_TUTOR_REVIEW_20261003.md) registra los cambios
del Word histórico y los requisitos empíricos pendientes. La revisión actual y su alcance están en [el informe integral](docs/COMPREHENSIVE_REVIEW_20261003.md); la [revisión 0.11.0](docs/VERIFY_ETL_REVIEW_20261003.md) conserva su evidencia histórica. Ninguna cierra la evaluación científica.

**Objetivo futuro:** publicar EquiFrame en PyPI para que cualquier persona pueda
usar `pip install equiframe`. El candidato 0.11.1 incorpora construcción,
Twine y verificadores de instalaciones limpias; licencia, titularidad del nombre,
acceso público y publicación conservan su decisión propia. Las instrucciones locales siguientes sirven para
desarrollo; no representan el cumplimiento de ese objetivo ni una publicación.

Se requiere **Python 3.12**. El paquete se instala desde este repositorio privado
o desde un wheel del equipo; todavía no se distribuye en PyPI.

```bash
git clone https://github.com/htroya/equiframe.git
cd equiframe/packages/equiframe
python -m pip install ".[duckdb]"
```

Extras disponibles: `arrow`, `pandas`, `polars`, `duckdb`, `engines` y `ml`.
La instalación base incluye contratos, CLI y metadatos; los motores son opcionales
y no se cargan al importar el paquete.

Para desarrollo reproducible se usa `uv.lock`. Los comandos de instalación y
verificación están en el [README del paquete](packages/equiframe/README.md).

## Uso

Una ejecución combina un contrato, una transformación registrada y una fuente de datos:

```text
ExecutionPlan + DataSource + TransformationRegistry
                    ↓ ef.execute(...)
ExecutionResult + artefactos Arrow + run.json
```

El [ejemplo mínimo](packages/equiframe/README.md#ejecución-mínima-funcional) muestra
una consulta parametrizada y la lectura de su salida. Los
[ejemplos ejecutables](packages/equiframe/examples/execute_native.py) cubren cinco
familias de transformaciones en comercio y telemetría con los tres motores.

La salida observada se conserva separada del esquema esperado: EquiFrame no
redondea, rellena ausencias, deduplica ni cambia tipos para ajustarla al contrato.
Las capacidades incompatibles se informan explícitamente. Consulte la
[matriz de transporte](packages/equiframe/README.md#transporte-fiel-y-capacidades-comprobadas).

## Compatibilidad e integración

La CI actual se inicia manualmente (`workflow_dispatch`) y exige activar
explícitamente la matriz Windows x64, Linux x64/ARM64 y macOS Intel/Apple Silicon.
Esos jobs están configurados para comprobar tipos, pruebas, construcción e
instalación limpia; esta entrega ejecuta controles locales en Windows x64/Python
3.12.4. No se han ejecutado los jobs remotos del candidato.
[Evidencia de compatibilidad y revisión](docs/STEP_03_REVIEW.md).

Los runners de GitHub son entornos temporales de prueba. El workflow no despliega
servicios ni conecta con una VM de OCI.

El núcleo funciona con datos locales y admite proveedores externos mediante
`DataSource`. El DW, la base DuckDB real y su programa de conexión podrán residir
en OCI: EquiFrame puede ejecutarse en esa VM o consumir snapshots publicados por
un proveedor explícito. El [contrato de integración OCI](docs/OCI_INTEGRATION.md)
describe los límites y las entregas necesarias; la conexión real sigue pendiente.

## Documentación

| Documento | Contenido |
|---|---|
| [API y ejemplos](packages/equiframe/README.md) | Instalación, ejecución, contratos, CLI y límites |
| [Referencia de formatos](docs/API_CONTRACTS.md) | Tipos públicos, estados y serialización |
| [Verify reutilizable](docs/VERIFY.md) | Dimensiones, esperados, O y bundles portátiles |
| [ETL completo](docs/ETL.md) | CSV/JSON/JSONL, etapas y publicación Parquet |
| [SERCOP fijado](docs/SERCOP_EXAMPLE.md) | Granos, API oficial y reconciliación acotada |
| [Matriz de soporte](docs/SEMANTIC_SUPPORT.md) | Operación, tipo, motor, política y pruebas |
| [Candidato de release](docs/RELEASE_CANDIDATE.md) | Artefactos, controles y decisiones pendientes |
| [Comparación](docs/COMPARISON.md) | API, autorizaciones, evidencia y presupuestos |
| [Reglas R](docs/RULES.md) | Semántica, cobertura, catálogo y límites |
| [Perfiles y preprocesamiento](docs/PROFILES.md) | Fórmulas, soporte, recibos y medianas congeladas |
| [Detectores y calibración](docs/DETECTORS.md) | Uso de M/B/H, persistencia y estados no estimables |
| [Diseño del paso 7](docs/STEP_07_DESIGN.md) | Reorientación después de 1–6 y relación con los objetivos de tesis |
| [Arquitectura](docs/ARCHITECTURE.md) | Componentes, dependencias y flujo de ejecución |
| [Diseño del paso 6](docs/STEP_06_DESIGN.md) | Reorientación después de 1–5, objetivos de tesis y arquitectura experimental |
| [Uso del benchmark](packages/equiframe-benchmark/README.md) | Piloto, revisión, particiones, selección y distribución |
| [Integración OCI](docs/OCI_INTEGRATION.md) | Acceso al DW, snapshots y coordinación de DuckDB |
| [Calidad](docs/QUALITY.md) | Pruebas, recursos y distribución |
| [Changelog](packages/equiframe/CHANGELOG.md) | Cambios por versión |
| [Contribución](CONTRIBUTING.md) | Desarrollo, ramas y revisión de cambios |

## Estructura del repositorio

```text
packages/equiframe/            biblioteca y pruebas
packages/equiframe-benchmark/  puente O científico, evaluación, reproducción y pruebas
packages/equiframe-data/       especificación de acceso a datos
packages/equiframe-sercop/     especificación de integración de dominio
services/data-gateway/         especificación del servicio de datos
infra/                        especificación de infraestructura
docs/                         documentación técnica
.github/                      CI y plantillas de colaboración
```

Actualmente `packages/equiframe` y `packages/equiframe-benchmark` contienen
implementaciones Python. Los componentes de acceso a datos, dominio e infraestructura
conservan sus especificaciones hasta que sus responsables los implementen.
Código, esquemas y casos sintéticos pequeños se versionan en Git; las bases reales,
credenciales, snapshots y resultados privados se almacenan fuera del repositorio.

La licencia de distribución está pendiente de decisión de los autores.
