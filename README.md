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

**Versión de desarrollo: 0.3.0.** Una ejecución `completed` confirma que la
transformación terminó y se materializó. La [comparación semántica](docs/COMPARISON.md)
evalúa salidas materializadas. Las reglas operativas, detectores y benchmark siguen en la
[hoja de ruta](docs/HERNAN_ROADMAP.md).

## Instalación

Se requiere **Python 3.12**. El paquete se instala desde este repositorio privado
o desde un wheel del equipo; todavía no se distribuye en PyPI.

```bash
git clone https://github.com/htroya/equiframe.git
cd equiframe/packages/equiframe
python -m pip install ".[duckdb]"
```

Extras disponibles: `arrow`, `pandas`, `polars`, `duckdb` y `engines`.
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

La configuración de CI ejecuta el mismo paquete en Windows x64, Linux x64/ARM64
y macOS Intel/Apple Silicon. Cada job comprueba tipos, pruebas con motores reales,
construcción e instalación limpia del wheel.
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
| [Comparación](docs/COMPARISON.md) | API, autorizaciones, evidencia y presupuestos |
| [Arquitectura](docs/ARCHITECTURE.md) | Componentes, dependencias y flujo de ejecución |
| [Integración OCI](docs/OCI_INTEGRATION.md) | Acceso al DW, snapshots y coordinación de DuckDB |
| [Calidad](docs/QUALITY.md) | Pruebas, recursos y distribución |
| [Changelog](packages/equiframe/CHANGELOG.md) | Cambios por versión |
| [Contribución](CONTRIBUTING.md) | Desarrollo, ramas y revisión de cambios |

## Estructura del repositorio

```text
packages/equiframe/            biblioteca y pruebas
packages/equiframe-benchmark/  especificación de evaluación
packages/equiframe-data/       especificación de acceso a datos
packages/equiframe-sercop/     especificación de integración de dominio
services/data-gateway/         especificación del servicio de datos
infra/                        especificación de infraestructura
docs/                         documentación técnica
.github/                      CI y plantillas de colaboración
```

Actualmente `packages/equiframe` contiene la implementación Python. Los otros
componentes conservan sus especificaciones hasta que sus responsables los implementen.
Código, esquemas y casos sintéticos pequeños se versionan en Git; las bases reales,
credenciales, snapshots y resultados privados se almacenan fuera del repositorio.

La licencia de distribución está pendiente de decisión de los autores.
