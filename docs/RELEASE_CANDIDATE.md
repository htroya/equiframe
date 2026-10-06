# Candidatos Python 0.11.1

La [ficha STEP5](STEP5_CANDIDATE.md) añade tres recetas y kit instalable
autocontenido; mantiene separada su aceptación técnica de la observación humana.

La [ficha STEP4](STEP4_CANDIDATE.md) identifica aserciones, integración y cambio
observable de truth testing, con evidencia local y límites de CI remota.

La [ficha STEP3](STEP3_CANDIDATE.md) identifica el reporte común, sus controles
y límites de evidencia. Los recibos anteriores siguen siendo históricos.

La [ficha STEP2](STEP2_CANDIDATE.md) registra la entrada directa y las nueve
etapas de ambos paquetes en Linux/Python 3.12.14, con los artefactos exactos.
No amplía la matriz remota ni reemplaza la identidad de recibos anteriores.

La [ficha operativa STEP1](STEP1_CANDIDATE.md) identifica el saneamiento actual
y sus recibos. Las ejecuciones históricas citadas en esta guía conservan su
revisión; no se atribuyen automáticamente al candidato nuevo.

Dos distribuciones: `equiframe==0.11.1` y `equiframe-benchmark==0.11.1`.
El benchmark fija exactamente el núcleo en base/extras; `uv` usa una fuente
local sólo para desarrollo. Los metadatos publicados del wheel contienen la
dependencia por nombre/version y ninguna obligación de ruta local.

Python declarado actual **`>=3.12,<3.14`**. La [matriz STEP6](STEP6_CANDIDATE.md)
identifica evidencia del candidato actual y sus exclusiones. La verificación
Windows x64/Python 3.12.4 de esta sección es histórica; no acredita este candidato. Hatchling 1.28.0, locks por paquete,
Twine 6.2.0 resuelto desde `>=6.2,<7` y `py.typed`. El import base no carga Arrow,
Pandas, Polars, DuckDB, NumPy o sklearn; cada extra se comprueba por separado.
Los rangos anunciados conservan su metadata, pero la prueba ejecuta versiones
resueltas del lock, no cada combinación de todo el rango.

## Construcción y controles

Desde cada paquete, con un ejecutable `uv` realmente disponible:

```bash
uv sync --locked --all-extras --python 3.12
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy
uv run --locked --all-extras python tools/generate_assets.py --check
uv run --locked --all-extras pytest -q
uv run --locked --all-extras python -m build --no-isolation
uv run --locked --all-extras twine check --strict dist/*.whl dist/*.tar.gz
uv run --locked --all-extras python tools/verify_distribution.py --uv /ruta/al/uv
```

El verificador existente se amplía, conserva imports ligeros/consumidor tipado,
API/CLI, extras, instalación runtime-only fuera del checkout, ejemplos nativos,
suite enviada contra site-packages y reconstrucción byte a byte de wheel desde
sdist. Arrow ejecuta el ejemplo Verify; engines ejecuta comercio y OCDS sintético.
El benchmark comprueba puente, piloto y ejemplos de integración/evaluación, sin
contarlos como evidencia científica real.

El wheel incluye módulos/resources runtime; el sdist incluye además tests,
ejemplos, esquemas, herramientas, lock y changelog. Los READMEs del wheel
explican que enlaces del monorepo privado pueden requerir acceso. La licencia
y documentación pública requieren decisión antes de distribuir públicamente.

`tools/check_candidate.py`, situado en el paquete núcleo, guarda comandos,
logs, fechas, duración, directorio de ejecución y exit codes; se detiene al
fallo. Su opción `--package` permite comprobar el benchmark. El helper
`tools/release_manifest.py` identifica versión, wheel/sdist, SHA-256/tamaño,
entorno, herramientas, fuente Git y recibos de ejecución. Desde
`packages/equiframe`, por ejemplo:

```bash
uv run --locked --all-extras python tools/release_manifest.py --checks /ruta/checks-core.json --output /ruta/core-manifest.json
uv run --locked --all-extras python tools/release_manifest.py --package ../equiframe-benchmark --checks /ruta/checks-benchmark.json --output /ruta/benchmark-manifest.json
```

La fuente debe pertenecer a un repositorio Git real: el helper resuelve
`HEAD^{commit}` y exige sus **40 caracteres hexadecimales exactos**. Si se pasa
`--commit`, debe coincidir íntegramente con ese HEAD. `pyproject.toml` debe estar
versionado y el paquete comprobado debe estar limpio, sin cambios tracked ni
archivos untracked no ignorados dentro de su propia carpeta. Esta comprobación
se aplica también a dependencias locales `path` del paquete; las carpetas ajenas
a ese cierre del monorepo no necesitan estar limpias. Un SHA inventado,
otra revisión o una copia sin Git no acredita la fuente y se rechaza.

Cada recibo `--checks` debe contener comandos y exit codes válidos, y su `cwd`
debe ser absoluto y resolver exactamente a la carpeta del paquete comprobado.
Se pueden aportar varios recibos, conservando sus hashes. Para completar el
candidato se necesitan resultados exitosos de estas **nueve etapas**:
`locked_sync`, `ruff_check`, `ruff_format`, `mypy`, `assets`, `pytest`, `build`,
`twine` y `distribution`. Se reconocen los comandos completos correspondientes:
sync locked con todos los extras, Ruff sobre el paquete completo, mypy, assets
con `--check`, suite completa `pytest -q`, build sin aislamiento, Twine estricto
sobre el wheel y sdist identificados y el verificador de distribución propio.
Una prueba dirigida, nodo pytest, filtro `-k`/`-m` o colección sin ejecutar
**no cumple la etapa pytest**, aunque termine con código 0.

`check_completion` registra etapas requeridas, exitosas, ausentes y comandos
fallidos. Recibos con cwd inválido se rechazan; etapas ausentes o cualquier
comando fallido añaden bloqueos de publicación al manifiesto generado. No se
convierte una ejecución parcial en distribución final aprobada. Los dos
manifiestos locales finales de `09c3dfb` contienen nueve etapas exitosas, cero
faltantes y cero comandos fallidos, con las suites instaladas aprobadas.
Los cuatro bloqueos de licencia/nombre/acceso/publicación permanecen.
[Resultados, hashes y alcance ejecutado](VERIFY_ETL_REVIEW_20261003.md).

La comprobación Git acredita el HEAD y la limpieza del paquete al generar el
manifiesto. Los recibos suministrados no autentican su ejecución ni la identidad
del ejecutor (`receipts_authenticated=false`); los hashes identifican los bytes
actuales de los artefactos, sin autenticar su origen de construcción. El
manifiesto no es una firma ni concede licencia, titularidad o autorización de
publicación. Las evidencias y los manifests locales están fuera de Git; los
artefactos están en `dist` de cada paquete.

Instalación identificada, sin resolver proyectos ajenos en un índice:

```bash
python -m pip install --no-index --find-links /ruta/wheels equiframe==0.11.1 equiframe-benchmark==0.11.1
```

Esa carpeta debe contener también las dependencias runtime necesarias; los
verificadores crean entornos con versiones del lock antes de instalar los wheels.

## Controles vinculados a los bytes actuales

Desde 0.11.1 cada control registra huellas `source_before`/`source_after` de los
archivos versionados y nuevos no ignorados del paquete y de sus dependencias
locales declaradas en `tool.uv.sources`. El benchmark incorpora así los bytes
del núcleo usados por sus pruebas. El driver aborta si cambian durante o entre
controles; los locks y las versiones runtime se mantienen separados de esta
huella de fuente. Construcción, Twine e instalación se vinculan además al
wheel/sdist exactos, y los últimos dos exigen bytes constantes antes y después.
La instalación del benchmark registra también el wheel exacto del núcleo en
`dependency_artifacts_before`/`dependency_artifacts`. Un wheel ausente o
sustituido invalida esa etapa aunque la fuente no cambie. Se soportan fuentes
locales `path` simples dentro del repositorio; listas condicionales de fuentes
se rechazan explícitamente para impedir omisiones silenciosas.

`check_completion.source_bound_stages` contiene las etapas vinculadas a los
bytes actuales. Las etapas sin ese vínculo aparecen en `unbound_stages` y
bloquean publicación. Los recibos históricos siguen siendo legibles: conservar
su comando exitoso no acredita validación del candidato nuevo. El driver usa
una carpeta pytest propia junto al recibo para evitar colisiones entre rondas.
Esta vinculación detecta evidencia desactualizada; conserva
`receipts_authenticated=false` y no es una firma ni acredita ejecución externa.
Use un recibo fuera del árbol de fuente o dentro de `dist/`, ignorado por Git;
un recibo no ignorado escrito dentro del paquete cambia su propia huella.

La [revisión integral final](COMPREHENSIVE_REVIEW_20261003.md) registra las nueve
etapas aprobadas de ambos candidatos 0.11.1, las suites instaladas, sus tres
omisiones Windows y los SHA-256 exactos. La evidencia 0.11.0 de `09c3dfb` citada
arriba permanece histórica y no es la validación de estos artefactos.

## CI y publicación separadas

`.github/workflows/equiframe.yml` es manual y exige activar la matriz opcional.
`.github/workflows/release-candidate.yml` construye ambos paquetes y conserva
artefactos `equiframe-candidate-SHA`; exige `run_build=true`, desactivado por
defecto. Sus acciones oficiales están fijadas a SHA. No se activó ningún job,
amplió cuota ni cambió facturación; configuración no acredita ejecución.

`.github/publish-prepared.yml.example` está deliberadamente fuera de `workflows`.
Prepara un trabajo separado con environment, descarga del run identificado,
verificación de commit, fuente limpia, nueve controles, inventario exacto de
ambas distribuciones/hashes y OIDC `id-token: write`, siguiendo
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/).
No recompila durante publicación y rechaza manifiestos con decisiones pendientes.
Su activación requiere una tarea expresa posterior y adecuar las decisiones
del manifiesto; actualmente no puede publicar.

## Decisiones externas pendientes

| Decisión | Resultado observado y siguiente requisito |
|---|---|
| Licencia | No hay licencia de distribución asignada; autores deben aprobar términos y archivos/metadata correspondientes |
| Nombre | GET oficiales de PyPI para ambos nombres devolvieron HTTP 404 el 2026-10-03 20:16:32 UTC; no reserva ni acredita titularidad |
| Cuenta/Trusted Publisher | No se configuró proyecto/editor en PyPI/TestPyPI ni autorización de environments |
| Acceso público | Repo privado; decidir documentación accesible y permisos de redistribución sin cambiar visibilidad aquí |
| Publicación | No autorizada por este encargo; wheels/sdist preparados, no publicados |
| Aceptación externa | No se inventa ejecución por compañero ni matriz de plataformas remota |

La [guía oficial de empaquetado](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
y [Twine](https://twine.readthedocs.io/en/stable/) orientan metadatos/construcción.
`twine check --strict` aprobado valida artefactos; no elimina decisiones de
licencia, titularidad o publicación. La etiqueta científica O mantiene gates
humanos separados del release.

## Dependencias locales realmente cargadas en STEP4

La huella del cierre de fuente por sí sola no garantiza qué instalación ha
importado Python. Durante STEP4 la verificación del wheel detectó una fixture
adversarial rechazada antes por el nuevo validador; el entorno de fuente del
benchmark todavía tenía una copia en caché del núcleo anterior. Ese intento se
conserva como fallido/superado y no valida el candidato final.

El driver ahora reinstala explícitamente las dependencias `path` del cierre
local, y comprueba las rutas de import y hashes de archivos runtime frente a sus
fuentes antes de aceptar los controles. La verificación de distribución sigue
instalando los wheels identificados fuera del checkout. Los recibos nuevos
separan esa vinculación runtime (`local_dependency_runtime_bound_stages`) de
la huella de archivos fuente. Las etapas sin prueba cargada aparecen en
`local_dependency_runtime_unbound_stages` y bloquean el candidato. Los antiguos
no se interpretan como prueba de qué bytes se cargaron. No se cambian locks,
versiones o dependencias para evitar el problema de caché.

La fixture conserva dos defensas: contradicciones de conteos/metadatos se
rechazan al validar el modelo; una observación de alineación falsificada pero
estructuralmente válida atraviesa el expediente rehasheado y debe ser rechazada
al volver a comprobar las filas portátiles reales. No se elimina ese control
profundo para hacer pasar la suite.

Los candidatos privados conservan por ahora el número 0.11.1 y se identifican
por commit y hash de artefacto. En un entorno existente no asuma que la igualdad
de versión implica los mismos bytes. Tras preparar sus dependencias bloqueadas,
reinstale explícitamente los wheels exactos elegidos, por ejemplo con
`python -m pip install --force-reinstall --no-deps /ruta/equiframe-0.11.1-py3-none-any.whl /ruta/equiframe_benchmark-0.11.1-py3-none-any.whl`.
Los verificadores del candidato utilizan entornos limpios e identifican los
artefactos; este comando no resuelve los pendientes de publicación/licencia.

## Consumo de primer uso STEP5

El verificador de distribución del núcleo construye un kit con el wheel exacto,
los scripts, guías y pins/hashes de dependencias del lock sin modificarlo. Lo
copia fuera del checkout, crea un entorno limpio, verifica el import instalado y
los códigos/reporte de las tres recetas y pytest. `build_first_use_kit.py` rechaza
un inventario inesperado, pins desactualizados y archivos no regulares; el kit
incluye su verificador y manifiesto. Los hashes verifican consistencia, no origen.
No se distribuyen entornos ni dependencias binarias dentro de ese kit.

Esta verificación y la revisión técnica independiente del consumidor no son una
observación de una persona nueva. El formulario de primer uso sigue pendiente y
registra tiempo total, instalación, ayuda, errores, plataforma y comprensión.
No se amplía soporte Python/plataformas ni se activa un workflow remoto.

## Estabilidad y matriz STEP6

La [política](COMPATIBILITY.md) clasifica API, CLI y formatos; el
[registro de adaptadores](ADAPTER_CAPABILITIES.md) declara condiciones, pérdidas
y mantenimiento individual no asignado. Los formatos permanecen independientes
del número privado 0.11.1; el corpus histórico se conserva en el sdist y no se
regenera durante tests. No es aceptación externa ni certificación de terceros.

`tools/verify_compatibility.py` consume un único wheel/sdist ya construido,
identifica sus bytes y crea consumidores fuera del checkout. Por perfil e
intérprete, conserva resolución, versiones reales, comandos, logs y corpus;
las dependencias de test se constriñen para no alterar silenciosamente las de
runtime. Una celda fallida, omitida o bloqueada no da soporte. La resolución
mínima de dependencias directas no es una prueba de toda dependencia transitiva
histórica ni de cada combinación permitida por el metadata.

No se reconstruye un wheel diferente para aparentar la misma matriz. Los recibos
de cada celda se enlazan al commit final mediante inventarios de fuente y del
payload instalado. Hashes e informes locales no autentican un ejecutor ni son
CI remota. La guía de primer uso sigue enfocada en Python 3.12 y su meta humana
de cinco minutos continúa pendiente.
