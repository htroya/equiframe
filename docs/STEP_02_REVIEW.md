# Revisión del paso 2: ejecución genérica y adaptadores nativos

Versión: `equiframe 0.2.0`, 2026-09-28. Base verificada: paso 1 `b77d85e`;
PR #11 continúa abierto al iniciar la entrega. Rama `hernan/step-02-execution`,
PR dependiente hacia `hernan/step-01-foundations`. No se integra automáticamente.

## Alcance entregado

`import equiframe as ef` ofrece ejecución síncrona nativa, modelos frozen de
plan/opciones/resultado/capacidades/artefactos, puertos completos y registro por
instancia. Fuentes Arrow/Pandas/Polars/Arrow IPC file/Parquet locales, almacén con
SHA-256/tamaño y publicación exclusiva, IDs/directorios por corrida. Los callbacks
y SQL confiables se registran fuera del contrato; no hay globals o conexión compartida.

Pandas protege datos e índice. Polars materializa lazy y registra planificación y
materialización. DuckDB recibe conexión propia :memory:, SQL SELECT/WITH parametrizado,
identificadores controlados, memoria/hilos efectivos, ICU, acceso externo/descargas/
spill deshabilitados, monitor unido y recursos cerrados. Los esquemas físicos nativos
se conservan separados del contrato esperado. Una discrepancia capturable no se corrige.

Extras base/arrow/pandas/polars/duckdb/engines, lock y versión 0.2; ejemplos de comercio
y telemetría para cinco familias y esperados explícitos. Arquitectura/API/decisiones/
trazabilidad distinguen los nuevos requisitos de producto del borrador científico.
La distribución pública se incorpora al paso 10 y sigue pendiente.

## Verificaciones locales

Windows x64, CPython 3.12.4. Lock: Pandas 3.0.6, Polars 1.44.2 y runtime-32 1.44.2,
DuckDB 1.5.6, PyArrow 25.0.1, tzdata 2026.4. Solo estas versiones quedan verificadas;
los rangos de metadatos no certifican todas sus combinaciones.

| Control | Evidencia local |
|---|---|
| Suite completa | 321 passed; conserva 198 casos del paso 1 y añade 123 |
| Estilo/formato | Ruff sin incidencias; 33 archivos |
| Tipado | mypy strict sin incidencias en 19 archivos src/tools |
| Assets | Nueve coinciden: cinco contratos y cuatro esquemas; siete assets previos intactos |
| Ejemplos | Cinco familias × tres motores; resultados explícitos de dos dominios |
| Integración | Motores instalados, ninguna omisión sistemática ni backend simulado |
| Recursos | Checkpoints, cancelación durante consulta real, timeout cooperativo, límite real de memoria DuckDB y cierre de conexiones instrumentadas reales |
| Aislamiento | Corridas locales concurrentes e inyección externa/source/store/adaptador; IDs y referencias distintas |
| Distribución | Wheel/sdist 0.2.0 construidos con backend bloqueado; instalación sin editable, base y cada extra fuera del checkout |
| Wheel instalado | Import ligero, API/CLI y errores, perfiles individuales, combinación, ejemplos copiados y mínimo del README ejecutado literalmente |
| Sdist | Wheel reconstruido idéntico byte a byte, batería completa contra site-packages, assets y consumidor mypy externo |

Los comandos reproducibles están en el README del paquete. No se atribuye el
resultado local a Ubuntu ni se declara ARM64 u otras versiones de Python.

## CI verificada

El commit `ac92cac433306fd2343279baed7d69d1336ddf9a` contiene toda la implementación
y documentación de alcance. Los workflows de
[PR](https://github.com/htroya/equiframe/actions/runs/36489628830) y
[push](https://github.com/htroya/equiframe/actions/runs/36489623851) terminaron
con success en las dos plataformas el 2026-09-28.

| Plataforma x64 | Python efectivo | Suite | Suite contra wheel del sdist | Evidencia del PR |
|---|---|---|---|---|
| Ubuntu 24.04 | CPython 3.12.14 | 321 passed | 321 passed | [Job Ubuntu](https://github.com/htroya/equiframe/actions/runs/36489628830/job/109154847878) |
| Windows Server 2022 | CPython 3.12.10 | 321 passed | 321 passed | [Job Windows](https://github.com/htroya/equiframe/actions/runs/36489628830/job/109154847644) |

Ambos jobs también verificaron Ruff/formato, mypy strict, nueve assets, build,
base y cada extra runtime-only, import/API/CLI, ejemplos externos y mínimo del
README, consumidor tipado y reconstrucción del wheel idéntica byte a byte.

El [PR #12](https://github.com/htroya/equiframe/pull/12) está vinculado al issue #2 y
su base sigue siendo `hernan/step-01-foundations`, dependiente del PR #11 abierto.
El commit que añade esta evidencia solo modifica este informe; los
[checks del HEAD](https://github.com/htroya/equiframe/pull/12/checks) se comprueban
nuevamente antes de entregar. No se integra el PR automáticamente.

## Regresiones y decisiones relevantes

- Arrow IPC leído desde una ruta mantenía el archivo mapeado y bloqueaba limpieza
  en Windows: lectura desde archivo propio cerrado, antes de borrar temporales.
- Pandas copy(deep=True) podía compartir almacenamiento del índice: copia explícita
  del índice/columnas protege el consumidor; índice se registra en artefacto separado.
- NumPy NaN sin máscara NULL, None/NaN ya conflados y objetos Decimal con signed zero
  o exponente por celda: conservar la evidencia existente o rechazar pérdida; no recuperar
  distinciones inexistentes ni convertir decimal en float.
- DuckDB TimeZone no se configura antes de tener ICU disponible: conexión propia sin
  acceso externo, zona parametrizada después de abrir, autoinstall deshabilitado y
  autoload deshabilitado después del ICU incluido. Sin descarga ni writer compartido.
- Arrow date64 se convierte implícitamente en timestamp al ingresar a Polars: rechazo
  explícito. date32 funciona. date64 no canónico viola invariantes Arrow y se informa
  invalid_input; Pandas/DuckDB aceptan días enteros. No se hace cast para esconderlo.
- Decimal >38 y timestamp zoned ns incompatibles con motores concretos: rechazos
  previos sin cambiar contratos. NaN/NULL/cero/ceros de identificador/duplicados y ns
  compatibles se conservan. Joins con claves nulas exponen diferencias nativas.
- DuckDB renombra columnas que solo difieren por mayúsculas/minúsculas: rechazo
  explícito antes de registrar la entrada; Pandas/Polars preservan esos nombres.
- Escritura Arrow que falla tras crear el archivo: limpia el temporal parcial y
  conserva el manifiesto de fallo, los artefactos previos y la entrada del consumidor.
- Pruebas de interrupción esperan una consulta activa; no suponen el mismo tiempo de
  inicio por plataforma ni sustituyen el ejecutor por un mock.

## Límites y pendientes

completed solo acredita ejecución/captura. No hay comparador general, normalización,
R, perfiles, MAD/IF/H, benchmark, cliente remoto, VM o modificaciones del DW. El
servicio de José y los contratos/cargas de Jhair siguen bajo su responsabilidad.

Timeout/cancelación de callbacks/Polars collect son cooperativos; no hay sandbox,
preempción de callbacks o límite RSS. DuckDB limita memoria propia e interrumpe la
consulta; cargas/captura Python siguen teniendo checkpoints. Presupuestos tabulares
se comprueban tras materializar; no son cuotas agregadas ni evitan asignaciones.

Arrow conserva época/unidad/zona por columna, no texto ISO/offset original por fila;
se requieren columnas explícitas si interesa retenerlos. Motores tienen proveedores
IANA independientes y las versiones no expuestas se informan. No se admiten tablas
nested/categóricas/binarias, objetos arbitrarios o Arrow stream. Polars rechaza date64,
DuckDB zoned ns y zonas distintas de su configuración de sesión, y transporte decimal
no admite signed zero/NaN/Infinity/exponentes variables todavía presentes en objetos.

Sin publicación en PyPI; licencia/nombre bajo control del equipo, metadatos/versiones
y publicación verificable se resuelven en paso 10. Ninguna aprobación científica,
cantidad de escenarios o mejora experimental se fabrica con estos ejemplos.

El DOCX conserva SHA-256
`c96f0edfcab839b2ccf357527f4a7937c4b1fd3570f491d702b4f01fde44b38d`.
La implementación se detiene antes del paso 3.
