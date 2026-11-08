# Desarrollo seguro de Alpha A14

Trabajo de programación y pruebas del 13 de octubre de 2026, realizado sin
Codex Security ni agentes delegados. El
[recibo identificado](A14_SECURE_DEVELOPMENT_RESULT_20261013.json) conserva
hashes de 127 archivos de código, resultados, omisiones y límites. No acredita
una auditoría formal ni una matriz completa al 90 %.

## Cambios implementados

- Cliente de datos: manifiestos acotados, campos/tipos/rangos comprobados,
  JSON sin claves repetidas ni valores no finitos, rutas confinadas y rechazo
  de enlaces/archivos especiales. Descarga con tamaño/SHA-256 comprobados,
  referencias fijadas e inventario inmutable; los fallos conservan el destino
  íntegro anterior.
- Trabajos: bloqueo del sistema operativo entre procesos, escrituras atómicas,
  claves de idempotencia resumidas, límites de archivos/bytes/trabajos y
  snapshots que nunca se sustituyen. Recuperación distingue cargas parciales
  de snapshots ya publicados y conserva la versión vigente ante fallos.
- Integración opcional: puente con el contrato genérico del núcleo, comprobando
  nombres, hashes, tamaños, formato y conteos declarados. La aceptación del DW
  y del servicio del equipo conserva su validación propia.
- Gateway: configuración externa obligatoria, tokens de alta entropía con
  resúmenes y comparación en tiempo constante, roles de lectura/operación,
  HTTPS obligatorio para negocio, cuotas y límites de cuerpo/concurrencia.
  Errores genéricos, trazas internas con nombres/líneas sin valores sensibles,
  redacción de errores antiguos y cabeceras de protección.
- Núcleo/benchmark: 63 `assert` de ejecución convertidos en comprobaciones
  explícitas que siguen activas con `-O`. Catálogo actual de reglas y cuatro
  esquemas del benchmark sincronizados con su código A14; expedientes
  históricos conservados. Mínimo Arrow elevado a 23.0.1.
- ETL opcional: lectura JSON acotada y montos decimales exactos; no se inventa
  USD ante moneda ausente ni se corta la descripción. Se preserva la moneda
  del tender y se acota el total de filas aplanadas; importes/colecciones
  malformados se rechazan y el CLI deja de imprimir muestras. Sigue siendo un
  prototipo sujeto a contrato y aceptación de dominio.

## Comprobaciones observadas

| Control | Resultado |
|---|---|
| Núcleo, suite completa normal | 8.104 aprobadas, 25 omitidas y 3 fallos del catálogo/fixture recogidos antes de sus correcciones |
| Seguimientos de esos fallos | 48 aprobadas de reglas/activos y 15 de límites/inyección; ambos sin fallos |
| Benchmark, suite completa normal | 620 aprobadas y 7 omitidas |
| Cliente y gateway contra el código actual | 97 aprobadas y 1 omitida en Windows |
| Selección de invariantes/detectores/workflow con `-O` | 204 aprobadas y 4 omitidas en Windows |
| Supervisión de procesos Windows | 35 aprobadas |
| Freeze/study tras sincronizar esquemas | 63 aprobadas y 1 omitida |
| Límites POSIX y muerte del escritor, ARM64/Python 3.10 | 4 aprobadas, sin omisiones |
| Contratos de repositorio | 83 ejecutadas, incluidas 9 omisiones; sin fallos |
| Ruff y formato | Aprobados en núcleo, benchmark, cliente, gateway y preparación del publicador |
| Mypy | 106 archivos del núcleo y 37 del benchmark aprobados |
| Activos generados y arquitectura | 71 activos del núcleo y 45 esquemas del benchmark actuales; sin violaciones de arquitectura |
| SCA, versiones públicas exactas y transitivas del entorno | 101 versiones, cero avisos conocidos |
| SCA, mínimos directos admitidos tras corregir Arrow | 13 versiones, cero avisos conocidos; no representa una resolución transitiva de mínimos |

La suite completa del núcleo no se repitió después de corregir el catálogo y
las pruebas nuevas que pretendían comprobar un valor no reflejado por el
reporte. Los seguimientos prueban los fallos concretos con una etiqueta de
columna realmente reflejada y escapada; no se debilita la comprobación de HTML.
Las omisiones Windows/POSIX y los intentos anteriores se conservan por separado.
El primer ensayo POSIX esperaba otra excepción para un snapshot ausente;
corregido el instrumento, los mismos hashes de los módulos aprobaron las cuatro
pruebas. Un proceso v5 quedó abierto tras escribir su recibo y se cerró de forma
acotada; el ensayo v6 contra el código actual terminó normalmente sin caché.

Bandit analizó el código de ejecución sin errores de análisis y emitió **44
avisos**: 40 B608 por composición SQL, dos B311 por aleatoriedad científica
reproducible y B404/B603 por supervisión de un proceso solicitado por el
aplicador. Los avisos SQL requieren revisar el contexto: identificadores con
comillas escapadas, literales escapados, valores vinculados y números validados.
Se comprobaron entradas hostiles en CSV/Parquet y codificación HTML/Plotly.
Los generadores aleatorios señalados no generan credenciales; el supervisor
recibe comandos de una aplicación confiable y no habilita un sandbox de código
externo. La lista de avisos no se oculta ni equivale a 44 vulnerabilidades
confirmadas o a una garantía de ausencia de vulnerabilidades.

El aviso [CVE-2026-25087 de Apache Arrow](https://arrow.apache.org/blog/2026/02/16/23.0.1-release/)
afecta una API C++ de prelectura que Python no expone. El mínimo se eleva de
forma conservadora; los locks conservan Arrow 25.0.1. La auditoría anterior de
los mínimos contenía dos registros duplicados de ese mismo aviso.

## Alcance que queda pendiente

Las fuentes Python del núcleo y benchmark coinciden byte por byte con los
wheels privados usados para las suites. Los metadatos de dependencias y activos
generados corregidos son posteriores a sus sdists. El cliente/gateway actuales
se comprobaron con una copia de importación identificada por hash; no se
construyó ni instaló otro paquete en la fase nueva de TestPyPI. Una entrega
binaria futura debe incorporar y comprobar esos cambios.

El gateway autenticado no se desplegó. TLS 1.3, volúmenes/backups cifrados,
protecciones del proxy y cuentas/roles reales requieren comprobación del
entorno. Esta API no almacena contraseñas ni usa cookies de sesión: si se
incorporan, requieren Argon2/bcrypt y HttpOnly/Secure/SameSite. Un resumen SHA
de un token aleatorio no sustituye el hash de una contraseña humana.

La [entrega de la tutora](SERCOP_SHARED_ACCESS_20261013.md) continúa con el
mismo enlace, verificado nuevamente en Opera Neon con perfil QA y zoom 75 %:
manifiesto HTTP 200, SHA-256 idéntico y página legible. Sus datos están en la
ruta compartida de `/var/tmp`; el directorio antiguo se eliminó tras verificar
la copia. Ese servidor de datos públicos es distinto del gateway privado.

La [brecha hasta 90 %](A14_PROGRESS_GAP_20261013.md) conserva las mediciones
anteriores. El [reparto 90/10](A14_TECHNICAL_90_METHOD_20261013.md) no inventa
corpus, etiquetas humanas, normalidad, N_fit, aprobaciones ni ciencia. Alpha
sigue abierta. [TestPyPI](TESTPYPI_PUBLISHER_PREPARATION_20261013.md) queda en
configuración: no se ejecutaron Actions ni se subió o instaló un paquete.
