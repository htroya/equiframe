# Segunda revisión del paso 1

Fecha: 2026-09-28. Revisión de `equiframe 0.1.0`, esquema `1.0`, sobre la base
`cc847276de628318abf70e6d78cec2b87c49fcbc`, en la rama
`hernan/step-01-foundations`. Entrega: [PR #11](https://github.com/htroya/equiframe/pull/11),
vinculado al [issue #1](https://github.com/htroya/equiframe/issues/1).

La segunda lectura completa encontró defectos que las 147 pruebas iniciales
no detectaban. Se añadieron 51 casos: antes de corregir, 39 fallaban y 12 pasaban;
después, pasan los 198 casos de la batería completa. Los 39 fallos son casos
de reproducción, no 39 defectos independientes. Las correcciones permanecen
en fundaciones, contratos, tipos, diagnóstico y distribución.

## Hallazgos y correcciones

| ID | Prioridad | Reproducción en la base revisada | Corrección y regresión |
|---|---|---|---|
| R01 | Alta | `decimal.localcontext(capitals=0)` cambia `-0E-18` a `-0e-18` y cambia SHA-256 para el mismo contrato | Serializador decimal con `capitals=1` local; propiedad sobre precisión, capitalización, clamp y límites, sin alterar flags/contexto del consumidor |
| R02 | Alta | Un TZPATH sintético que asigna +09:00 a UTC hace inválido un timestamp UTC válido | Carga privada de reglas IANA desde `tzdata` bloqueado; subprocess aislado verifica literal, política y asignación de zona con el host alterado |
| R03 | Alta | Suma decimal aceptada con salida float, menor precisión/escala o unidad diferente; también estrechamiento de enteros/floats | Misma familia numérica, ampliación sin reducir el dominio fuente y unidad preservada; casos negativos y positivos independientes |
| R04 | Media | Joins y grupos numéricos aceptados con unidades diferentes | Unidades iguales en parejas de join y grupos preservados; errores en la regla/precondición y columna correspondiente |
| R05 | Media | `OrderCheck` aceptado sobre tabla con orden ignorado o distintas columnas de orden | Exige política significant completa y columnas en la misma secuencia; la política aporta dirección, ausencias y empates |
| R06 | Alta | Literales float32 exactos `0.1` y `1e-50` aceptados pese a redondeo/subdesbordamiento al representarlos | Comprobar representabilidad exacta; aceptar `-0.0`, `0.5` y `2**24` sin transformar el literal |
| R07 | Media | Literal temporal inválido devuelve `timestamp_literal` genérico y oculta la causa | Conservar código temporal específico y ubicación bajo `allowed_values[index].value` |
| R08 | Media | Clave JSON duplicada anidada solo señala raíz; surrogate en el mensaje no se puede codificar como UTF-8; constructores imprimen entradas rechazadas | Ruta completa de objeto/array, escape de claves y mensajes directos sin valores de entrada; probar API y CLI. Las causas/Pydantic `.errors()` pueden conservar entradas |
| R09 | Media | Ruta con NUL produce `ValueError` fuera de la jerarquía pública | Lectura/escritura traducen rutas inválidas a `ContractIOError`, con ruta escapada |
| R10 | Media | URI acepta puerto textual/fuera de rango, backslash o escape porcentual inválido | Validar puerto/separadores/escapes; puertos solo HTTPS; casos válidos IPv6, espacios codificados, file/s3/gs |
| R11 | Evidencia | El verificador inicial no ejecutaba toda la batería contra el wheel instalado desde el sdist ni comprobaba negativos de CLI instalada | Verificador ampliado: API runtime-only, CLI 0/2/3, consumidor mypy, tests/assets desde sdist e identidad byte a byte del wheel reconstruido |

Regresiones: [serialización, errores y base IANA](../packages/equiframe/tests/test_review_serialization.py)
y [coherencia declarativa, números y URI](../packages/equiframe/tests/test_review_semantics.py).
Las pruebas anteriores siguen en la batería. El formato y los bytes de los cinco
fixtures y dos esquemas generados se conservan. No hubo cambios de dependencias
ni del lock. Es una corrección de la primera entrega todavía abierta, sin una
versión ya publicada que migrar. Decisiones de ingeniería: A18–A20 en
[DECISIONS.md](DECISIONS.md).

## Revisión de todo el alcance

| Área del paso 1 | Evidencia revisada/comprobada | Resultado |
|---|---|---|
| Rama y entrega | Rama requerida, PR hacia main, vínculo `Closes #1`, sin auto-merge | Conforme |
| Distribución | pyproject, src, versión explícita, API `__all__`, py.typed, runtime/dev/backend separados, uv.lock universal | Conforme; Python 3.12 x64 |
| Tipos y modelos | Tipos lógicos, columnas/esquemas, claves/ámbitos, multiplicidad/orden, ausencia/NaN, precisión/tolerancias, fechas/instantes | Estrictos, frozen, extras rechazados; coherencia reforzada |
| Contrato y reglas | ID/revisión/versión, inputs/output, referencias de seis formas declarativas y precondiciones/aplicabilidad | Conforme; no ejecuta Python/SQL ni reglas |
| Estados y artefactos | Estados independientes de ejecución/decisión/oráculo, referencias versionadas, hash/formato/tamaño/URI, SchemaRef | Conforme; metadatos, sin descarga/integridad de contenido real |
| Integración | ArtifactStore con put/get y tipos completos; búsqueda en src sin Any ni dependencias de motores/ML | Conforme; sin puertos incompletos/implementaciones ficticias |
| JSON y hash | Duplicados, syntax/UTF-8, versión, roundtrip, revalidación de copias, referencia independiente stdlib, propiedades y hash seed | Conforme; SHA-256 de metadatos, no de equivalencia tabular |
| Precisión y tiempo | Decimal >53 bits y ceros firmados/escala; rango entero/float32; ns/offset/zone, calendario, intervalos, DST/gaps/ambigüedad/extremos | Conforme; base IANA y contexto decimal controlados |
| CLI | API compartida, entry point/módulo, stdout/stderr, JSON/versión/argumentos inválidos e I/O | Conforme; códigos 0/2/3, sin éxito ante fallo |
| Cinco familias | nulls_types, joins, duplicates_order, aggregations, dates; validación semántica y estructural | Conforme; fixtures sintéticos, sin aval científico |
| Pruebas y calidad | Casos válidos/negativos, propiedades, strict mypy, Ruff y assets actuales | Conforme; 198 casos |
| Distribución aislada | Runtime-only sin motores/ML/dev; API/CLI; sdist íntegro; batería contra instalación no editable; consumidor tipado | Conforme; wheel reconstruido idéntico |
| CI | Matriz Windows Server 2022/Ubuntu 24.04 x64, Python 3.12, contents: read, acciones fijadas, lock y backend reproducible | Controles reales; resultados del nuevo commit en checks del PR |
| Documentación y límites | README/API/decisiones/changelog; ejemplo Python ejecutado literalmente; carpetas de compañeros y tesis fuera del cambio | Conforme; solo paso 1 |

## Verificación ejecutada

Local: Windows x64, CPython 3.12.4, entorno virtual del paquete y dependencias de
`uv.lock`. Comandos desde `packages/equiframe`; en Ubuntu la CI usa los equivalentes
`uv run --locked` documentados en el [README](../packages/equiframe/README.md).

| Comprobación | Resultado local |
|---|---|
| pytest completo | 198 passed |
| Nuevas regresiones antes de corregir | 39 failed / 12 passed; confirma reproducciones |
| Nuevas regresiones después de corregir | 51 passed |
| Ruff check y format --check | Sin incidencias; 24 archivos con formato correcto |
| mypy strict de src/tools | Sin incidencias en 13 archivos |
| generate_assets.py --check | 7 assets coinciden byte a byte |
| Ejemplo Python del README | Ejecutado literalmente; roundtrip/escritura/schema/error de versión correctos |
| build --no-isolation | Wheel y sdist construidos con backend bloqueado |
| verify_distribution.py | API/CLI instalada y códigos negativos correctos; dependencias compatibles; py.typed presente; import sin motores/ML/dev |
| Pruebas desde sdist contra wheel instalado | 198 passed; comprobación explícita de import desde site-packages |
| Consumidor externo mypy --strict | Sin incidencias en 1 archivo |
| Reconstrucción wheel desde sdist | Igualdad de todos los bytes |
| Hash del borrador de tesis | Sin cambio: `c96f0edfcab839b2ccf357527f4a7937c4b1fd3570f491d702b4f01fde44b38d` |

La evidencia CI de esta revisión se consulta en
[checks del PR #11](https://github.com/htroya/equiframe/pull/11/checks).
Los resultados iniciales de 147 casos pertenecen a la base revisada y no se
usan como prueba del nuevo código.

## Límites y decisiones pendientes

No se encontraron impedimentos locales pendientes dentro del alcance revisado.
Esta revisión no acredita procesamiento de tablas, reglas evaluadas, comparación,
adaptadores, modelos, benchmark, snapshots reales, independencia/revisión del
oráculo ni resultados científicos. Las sumas declaradas no prueban ausencia de
overflow de datos reales. JSON Schema cubre estructura; la API sigue siendo
necesaria para referencias/coherencia/zona/DST.

El soporte se limita a la matriz comprobada: Python 3.12 x64 Windows/Ubuntu;
ARM64 y otras versiones no se certifican. Siguen pendientes cohorte, escala
monetaria real, alpha, tamaños experimentales, catálogo/revisión humana y licencia.
La tesis permanece intacta. Actualizar tzdata puede cambiar validaciones temporales
y exige revalidar; actualizar otras dependencias exige resolver lock y repetir CI.
El PR continúa abierto sin integración automática ni publicación en PyPI.
