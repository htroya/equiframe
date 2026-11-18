# Paso 10: inventario de distribución y reproducción

El inventario comprueba la fuente y, si se aporta, el wheel. No publica en PyPI,
no reserva el nombre y no elige una licencia. Las versiones de este paso son
núcleo `0.9.0` y benchmark `0.10.0`; la publicación permanece en el paso 19 de
la hoja de ruta de veinte pasos, sujeta a sus requisitos y autorización explícita.

## API de lectura

```python
from pathlib import Path
from equiframe_benchmark.distribution import inspect_distribution

inventory = inspect_distribution(
    Path("packages/equiframe-benchmark"),
    wheel_path=Path("dist/equiframe_benchmark-0.10.0-py3-none-any.whl"),
)
print(inventory.pending_conditions)
```

`DistributionReadiness` conserva nombre normalizado, versión, `Requires-Python`,
dependencias y extras, clasificadores, URLs, README, metadatos/archivos de licencia
y marcadores `py.typed`. Guarda SHA-256 y tamaño de los archivos de `src`,
`pyproject.toml`, `uv.lock`, README y licencias presentes; el hash del inventario
fija ese conjunto. No incluye ni declara verificado todo el contenido posible de
un sdist: pruebas, ejemplos y esquemas externos a `src` requieren la comprobación
separada de la distribución construida.

El lector utiliza `packaging` para interpretar nombres, versiones y requisitos.
Compara las dependencias de extras con sus marcadores y no evalúa esos marcadores
como prueba de instalación. Estas representaciones siguen las
[especificaciones de metadatos de PyPA](https://packaging.python.org/en/latest/specifications/core-metadata/)
y los [metadatos de pyproject.toml](https://packaging.python.org/en/latest/specifications/pyproject-toml/).

Cuando se aporta un wheel, se contrastan su nombre, versión, requisitos de Python,
dependencias, extras, clasificadores, URLs, licencias y tipado con la fuente. Se
leen `METADATA` y `WHEEL` en su formato de cabeceras, y se comprueban directorio,
nombre del archivo y etiquetas. La
[especificación de wheels](https://packaging.python.org/en/latest/specifications/binary-distribution-format/)
describe esos componentes; una etiqueta `py3-none-any` es metadata declarada y no
demuestra que los extras funcionen en todas las arquitecturas.

## Estados y evidencia separada

| Campo o condición | Qué representa |
|---|---|
| `source_available` | Se pudo leer e inventariar la fuente local. |
| `technical_inventory_complete` | Hay README, lock, requisito de Python y marcador de tipado. |
| `wheel_metadata_verified` | Se aportó un wheel y su metadata coincidió con la fuente. |
| `pending_license` | Faltan metadata de licencia o archivos regulares no vacíos. Su presencia no autentica una aprobación legal. |
| `pending_pypi_name_control` | No se aportó evidencia declarada de control del nombre. |
| `pending_wheel_metadata` | No se aportó un wheel para esta lectura. |
| `pending_build_install_verification` | Este lector no construye ni instala el paquete; los resultados de esas pruebas se adjuntan aparte. |
| `pending_current_release_platform_matrix` | El lector no acredita la matriz de sistemas y arquitecturas de esta versión. |
| `publication_ready` | Siempre `false` en el alcance de este inventario. |

Los resultados locales de build, instalación, extras y pruebas deben identificar
versiones, hashes y entorno en evidencia separada. Una matriz CI antigua no prueba
esta versión, y Windows/Python 3.12 no acredita Linux o ARM64. El cierre técnico
del paso 10 tampoco equivale a completar integración externa, evaluación científica,
reproducción independiente por un compañero ni publicación pública.

`NameCheck` se inyecta mediante `name_check=` o un JSON estricto. El helper no hace
peticiones de red. Un `404` registrado significa que esa consulta no encontró el
proyecto; no reserva el nombre. Un `200` significa existencia observada, no control
de la cuenta. Un fallo de consulta permanece `unknown`. Afirmar `controlled=true`
requiere existencia observada y evidencia aparte, y sigue siendo una declaración
del productor que este lector no autentica.

## Comandos y códigos

Los comandos se conectan a la aplicación mediante `equiframe_benchmark.commands.register(app)`.

```text
equiframe-benchmark distribution-readiness packages/equiframe-benchmark --wheel dist/equiframe_benchmark-0.10.0-py3-none-any.whl --output readiness.json
equiframe-benchmark verify-bundle bundle-directory --expected-sha256 DIGEST_DEL_BUNDLE_JSON
equiframe-benchmark reproduce-bundle bundle-directory --regenerator trusted_module:factory --output reproduction.json
equiframe-benchmark bundle-study study-directory --output portable-study
equiframe-benchmark reproduce-study portable-study --expected-sha256 DIGEST_DEL_BUNDLE_JSON
```

El resultado de `distribution-readiness` se imprime íntegro; `--output` guarda un
archivo exclusivo y no sobrescribe uno existente. Código `0` significa que se
completó la operación pedida, aunque queden condiciones de publicación pendientes.
Los comandos de reproducción devuelven `1` ante diferencias conservadas; entrada
inválida produce `2`, y evidencia persistida corrupta o fallo operacional produce `3`.

`verify-bundle` verifica bytes y el inventario completo sin ejecutar código. La
ancla `--expected-sha256` corresponde al SHA-256 de los bytes de `bundle.json`, no
al hash de una representación distinta del documento. `reproduce-bundle` exige
un `module:factory` explícito de confianza; la factory devuelve un callable que
recibe y devuelve `ReproductionRecord`. Ningún nombre de módulo viene del JSON.
Se verifica el bundle antes de invocar incluso esa factory.

La reproducción genérica compara el contenido completo declarado de configuración,
particiones, etiquetas, decisiones y tablas. El recibo no verifica por sí solo
contenido que el productor haya omitido. `bundle-study` incluye el estudio y sus
capturas; `reproduce-study` regenera métricas/tablas desde decisiones capturadas y
verifica bytes, conservando las referencias originales. No vuelve a ejecutar ETL,
no conecta con OCI y no certifica una repetición independiente por una persona.

## Límites del lector

No se extrae el ZIP ni se importan módulos del wheel. Se rechazan rutas que salen
del contenedor, barras inversas brutas —incluidas las que Windows normaliza—,
miembros duplicados, enlaces y cifrado. El lector impone límites a número de
miembros, tamaños de metadata, bytes de fuente y tamaño expandido del archivo.
No acredita las firmas del publicador ni la validez de todo `RECORD`; las pruebas
de instalación y la comprobación del artefacto construido son independientes.

La fuente debe tener metadata estática para nombre, versión, dependencias y
compatibilidad de Python. Una propiedad calculada mediante un backend no se
presenta como verificada: el lector no ejecuta ese backend. Los datos y consultas
de nombre utilizados por las pruebas unitarias son ficticios y no cuentan como
aprobaciones o decisiones sobre EquiFrame.
