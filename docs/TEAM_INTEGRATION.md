# Integración entre Hernán, José y Jhair

Este documento define entregas técnicas propuestas. Las tareas ya asignadas por el equipo son: José crea la VM y el acceso Python compartido; Jhair construye el DW; Hernán desarrolla y evalúa EquiFrame. Los detalles de sus componentes se acuerdan con sus responsables.

## 1. Propiedad y dependencias

| Responsable | Carpetas | Entrega que consumen los demás |
|---|---|---|
| Hernán | `packages/equiframe`, `packages/equiframe-benchmark`, documentación de API y experimento | Biblioteca, esquemas/Protocols, herramientas de comparación y evidencia, benchmark |
| José | `packages/equiframe-data`, `services/data-gateway`, `infra` | Cliente autenticado, snapshots inmutables, envío/estado de trabajos, límites, backups y recuperación |
| Jhair | `packages/equiframe-sercop` | Modelo/DDL SQL del DW, mapeos, preparación/carga, excepciones, contratos de dominio y reconciliación |

Hernán no necesita VM, datos completos ni un DW terminado para los pasos 1 a 8: usa fixtures sintéticos explícitos, almacén local y bases temporales. La integración real del paso 9 requiere snapshots y contratos del DW. Las mediciones finales del paso 10 requieren entorno fijado y sin interferencia de otras cargas.

Los casos sintéticos prueban la biblioteca pero no sustituyen los datos SERCOP ni cuentan automáticamente como escenarios revisados del benchmark.

## 2. Contrato del cliente de José

La API de transporte puede cambiar internamente, pero debe ofrecer estas operaciones lógicas:

| Operación | Entrada | Salida y garantía |
|---|---|---|
| `get_snapshot` | `snapshot_id` explícito | Manifiesto inmutable con tablas, formatos, tamaños, esquemas y SHA-256 |
| `download_artifact` | Referencia del manifiesto y destino | Copia verificada; un hash incorrecto produce fallo |
| `submit_job` | Operación registrada, parámetros, artefactos, versión base esperada y `idempotency_key` | Recibo con `job_id`; no equivale a publicación exitosa |
| `get_job` | `job_id` | Estado, etapa, errores y referencia al resultado cuando termina |
| `cancel_job` | `job_id` | Resultado de cancelación; distingue petición aceptada de trabajo ya confirmado |
| `publish_snapshot` | Resultado validado y versión base esperada | Nueva versión inmutable; actualización atómica del catálogo o conflicto explícito |

Publicación y autorización para cargar son responsabilidades del servicio/Jhair; `equiframe` no ofrece una puerta trasera para ejecutar escrituras administrativas. El cliente se adapta al puerto `DataSource` desde una integración externa. Formatos JSON/Arrow/Parquet, decimales exactos, zona temporal y errores compatibles con [API](API_CONTRACTS.md).

Cada persona usa su identidad y permisos, con sesiones de corta duración o credenciales protegidas. SSH/túnel o TLS y autenticación según el despliegue elegido por José; no exponer DuckDB ni un endpoint de SQL administrativo sin control.

## 3. Concurrencia y consistencia exigidas

La propuesta inicial usa un único proceso propietario de la base mutable y una cola de escrituras. El proceso puede coordinar lecturas internas según DuckDB; los otros procesos leen snapshots publicados en archivos diferentes. Las cargas preparan una versión nueva mientras los lectores conservan la anterior.

Pruebas que José deberá demostrar para la integración:

1. Tres clientes leyendo un snapshot durante una carga observan la misma versión y contenido.
2. Dos escrituras recibidas a la vez tienen orden/aislamiento definido; no abren dos escritores externos sobre el mismo archivo.
3. Repetir una petición con la misma clave y contenido devuelve el mismo trabajo, sin duplicar la carga. Misma clave con otro contenido devuelve conflicto.
4. Caída antes de publicar conserva la versión vigente. Reinicio recupera o marca trabajos interrumpidos sin anunciar éxito falso.
5. Un cliente que pierde la respuesta puede consultar el trabajo. La publicación valida versión base para evitar sobrescrituras perdidas.
6. Los lectores fijan snapshot; no cambian de versión entre tablas de una corrida. Retención y leases/referencias impiden borrar versiones en uso.
7. El servicio limita memoria, hilos, disco y número de trabajos; informa cola y timeouts. No promete escrituras simultáneas ilimitadas ni espera cero.

La técnica concreta y su versión deben registrarse en una decisión de José. [DuckDB documenta](https://duckdb.org/docs/current/connect/concurrency) restricciones del modo embebido y opciones remotas. Una librería que solamente envuelva `duckdb.connect()` en tres computadoras no satisface estas garantías.

## 4. Contrato del DW de Jhair

- Versión del esquema, DDL, diccionario y diagrama de tablas.
- Grano de `fact_adjudicacion`: `(snapshot_id, ocid, award_id)`; monto una vez; tabla puente sin monto.
- Ámbito de identificadores de entidades/proveedores, claves naturales/sustitutas reproducibles y tratamiento de incompletas.
- Tipos y escala decimal demostrados por perfilado; monedas y estados conservados.
- Fecha de cohorte, `fuente_fecha` y fecha analítica de adjudicación como conceptos diferentes.
- Snapshot original inmutable y tablas de preparación derivadas con manifiestos; reglas de compilación de releases y procedencia.
- Entradas y salidas por etapa ETL, reglas de transformación, muestras sintéticas y un extracto real utilizable con licencia/procedencia.
- Reconciliación independiente desde JSON: adjudicaciones, procedimientos, proveedores, vínculos, excepciones y sumas por moneda/estado.
- Carga idempotente, tablas de preparación y publicación solo cuando pasan los controles. Ante fallo, la versión consultable permanece vigente.

## 5. Quién implementa las tres versiones ETL

Para evitar un hueco entre DW y evaluación:

- Jhair define la semántica del dominio y construye la ruta de preparación/carga del DW que le corresponde.
- Hernán convierte los requisitos acordados en contratos y escenarios ejecutables del benchmark, e implementa las variantes comparables Pandas/Polars/DuckDB necesarias para evaluar las cinco familias. Esas transformaciones viven en el paquete experimental, no en el núcleo genérico.
- Si Jhair ya entrega una implementación compatible, Hernán la registra y prueba en lugar de duplicarla. Se conserva autoría y versión.
- Las tres implementaciones reciben exactamente la misma entrada de la etapa. No se compara una versión que recibe JSON crudo con otra que recibe datos previamente depurados sin contabilizar y controlar esa diferencia.

## 6. Acuerdos compartidos

Hernán publica primero los esquemas y ejemplos de intercambio, y añade pruebas de conformidad ejecutables. José y Jhair implementan contra ellos y pueden proponer ajustes antes de congelar la API. Las tres áreas usan PR, no cambios coordinados por copias de carpetas.

Revisión del oráculo: dos revisores no autores de la variante, decisiones ciegas y registro independiente; el tercero resuelve desacuerdos conforme a la tesis. Si el tercero es autor de la variante, registrar ese conflicto y resolver el procedimiento metodológico antes de declarar una adjudicación independiente. No fabricar firmas ni aprobaciones.

Invitaciones GitHub pendientes de los nombres de usuario de José y Jhair. `htroya` conserva administración del repositorio personal; colaboradores tendrán lectura/escritura y gestión de PR/issues. Administración equivalente para los tres requiere organización y roles apropiados.


## 7. Integración concreta tras el paso 2

Hernán entrega `ef.DataSource`, `ef.EngineAdapter`, `ef.ArtifactStore`,
`LoadedTable` y `TableArtifact` con tipos completos. Un consumidor externo puede
adaptar después el cliente de José: fijar un snapshot una vez, materializar sus
referencias verificadas y devolver tablas Arrow preservando procedencia. Las URI
remotas no se resuelven desde `LocalDataSource`; su autenticación/transporte debe
ser explícito y permanece bajo el componente de José, a integrar en el paso 9.

`DuckDBAdapter` es ejecución analítica local de SELECT/WITH con conexión propia
`:memory:` por corrida, no un cliente remoto ni escritor del DW compartido.
`PandasInput` conserva índice separado; otros motores requieren la decisión
explícita de convertirlo en columnas/descartarlo. `completed` no aprueba una carga.
Jhair aportará contratos de esquema/negocio y tablas identificadas a este puerto;
Hernán no agrega nombres/monedas/fechas SERCOP obligatorios al núcleo. Los ejemplos
genéricos de comercio y sensores no son entregas del DW ni evidencia de VM.
