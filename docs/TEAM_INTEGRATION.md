# Integración entre Hernán, José y Jhair

Este documento define entregas técnicas propuestas. Las tareas ya asignadas por el equipo son: José crea la VM y el acceso Python compartido; Jhair construye el DW; Hernán desarrolla y evalúa EquiFrame. Los detalles de sus componentes se acuerdan con sus responsables.

Estado actual: candidatos `equiframe 0.11.1` y `equiframe-benchmark 0.11.1`,
con Verify, ETL, migración y destino local. Las herramientas locales y las interfaces consumidoras están
implementadas; el servicio/DW real, el corpus y la aceptación científica siguen
pendientes. Las propuestas de despliegue de este documento no acreditan entregas
de José o Jhair. Los controles de distribución y sus pendientes se registran en
la [revisión del migrador](MIGRATION_REVIEW.md).

## 1. Propiedad y dependencias

| Responsable | Carpetas | Entrega que consumen los demás |
|---|---|---|
| Hernán | `packages/equiframe`, `packages/equiframe-benchmark`, documentación de API y experimento | Biblioteca, compiladores nativos, esquemas/Protocols, herramientas de comparación y evidencia, benchmark |
| José | `packages/equiframe-data`, `services/data-gateway`, `infra` | Cliente autenticado, snapshots inmutables, envío/estado de trabajos, límites, backups y recuperación |
| Jhair | `packages/equiframe-sercop` | Modelo/DDL SQL del DW, mapeos, preparación/carga, excepciones, contratos de dominio y reconciliación |

El desarrollo técnico de los pasos 1–10 y del migrador puede usar fixtures
sintéticos explícitos, almacén local y bases temporales. Esto amplía la
independencia de desarrollo prevista inicialmente para los pasos 1–8. La
integración real del paso 9 requiere snapshots y contratos del DW. La evaluación
científica y las mediciones finales del paso 10 requieren corpus/etiquetas
válidos, entorno fijado y ausencia de interferencia de otras cargas.

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

El consumidor implementado `SnapshotDataSource`, disponible en el núcleo con
aliases compatibles desde el benchmark, usa sólo `get_snapshot` y
`download_artifact` del `SnapshotClient` inyectado. Fija un ID explícito y consulta
su manifiesto una vez al construir; puede seleccionar un subconjunto de tablas
sin cambiar la huella del manifiesto completo. Comprueba formato, SHA/tamaño,
filas y expectativas de esquema antes de devolver una tabla. No usa `latest` ni
cambia de versión entre resoluciones. La consulta inicial precede al presupuesto
`RunContext`; el cliente controla sus timeouts/autenticación. Las otras cuatro
operaciones de la tabla son requisitos propuestos del servicio, no un gateway
implementado por este consumidor.

Publicación y autorización para cargar son responsabilidades del servicio/Jhair;
`equiframe` no ofrece una puerta trasera para ejecutar escrituras administrativas.
El cliente se adapta al puerto `DataSource` sin importar transporte/autenticación
desde el núcleo. Formatos JSON/Arrow/Parquet, decimales exactos, zona temporal y
errores compatibles con [API](API_CONTRACTS.md).

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
- Hernán convierte los requisitos acordados en contratos y escenarios
  ejecutables. El alcance científico principal es `nulls_types`, `joins` y
  `aggregations`, en Pandas–Polars, Pandas–DuckDB y Polars–DuckDB: nueve estratos.
  `duplicates_order` y `dates` permanecen como capacidades genéricas del software,
  sin ampliar automáticamente la muestra científica.
- Las transformaciones específicas de dominio y variantes experimentales viven
  fuera del núcleo. El núcleo 0.10.0 incorpora un migrador de IR genérico para
  compilar operaciones comunes a los tres motores; no incorpora nombres, reglas
  o DDL SERCOP obligatorios ni sustituye la definición de dominio de Jhair.
- Si Jhair ya entrega una implementación compatible, Hernán la registra y prueba en lugar de duplicarla. Se conserva autoría y versión.
- Las tres implementaciones reciben exactamente la misma entrada de la etapa. No se compara una versión que recibe JSON crudo con otra que recibe datos previamente depurados sin contabilizar y controlar esa diferencia.
- `run_integration` captura los tres motores una vez y compara las tres parejas.
  El esperado independiente es común y se captura aparte; Pandas no se convierte
  en O por ser origen de dos parejas. Una captura reutilizada en varias
  comparaciones no se cuenta como nueva muestra independiente.

## 6. Acuerdos compartidos

Hernán publica primero los esquemas y ejemplos de intercambio, y añade pruebas de conformidad ejecutables. José y Jhair implementan contra ellos y pueden proponer ajustes antes de congelar la API. Las tres áreas usan PR, no cambios coordinados por copias de carpetas.

Revisión de EquiFrame Verify (O): dos revisores no autores de la variante,
decisiones ciegas y registro independiente; el tercero resuelve desacuerdos
conforme a la tesis. Si el tercero es autor de la variante, registrar ese conflicto
y resolver el procedimiento metodológico antes de declarar una adjudicación
independiente. No fabricar firmas ni aprobaciones. El nombre comercial no cambia
los módulos/APIs existentes `oracle`, `OracleResult`, `OracleState` o
`evaluate_oracle`.

Invitaciones GitHub pendientes de los nombres de usuario de José y Jhair. `htroya` conserva administración del repositorio personal; colaboradores tendrán lectura/escritura y gestión de PR/issues. Administración equivalente para los tres requiere organización y roles apropiados.


## 7. Puertos del paso 2 y consumidor implementado en el paso 9

Hernán entrega `ef.DataSource`, `ef.EngineAdapter`, `ef.ArtifactStore`,
`LoadedTable` y `TableArtifact` con tipos completos. Un consumidor externo puede
adaptar el cliente de José: fijar un snapshot una vez, materializar sus
referencias verificadas y devolver tablas Arrow preservando procedencia. Las URI
remotas no se resuelven desde `LocalDataSource`; su autenticación/transporte debe
ser explícito y permanece bajo el componente de José. El paso 9 implementa el
consumidor `SnapshotDataSource`, no la entrega ni aceptación de ese cliente real.

`DuckDBAdapter` es ejecución analítica local de SELECT/WITH con conexión propia
`:memory:` por corrida, no un cliente remoto ni escritor del DW compartido.
`PandasInput` conserva índice separado; otros motores requieren la decisión
explícita de convertirlo en columnas/descartarlo. `completed` no aprueba una carga.
Jhair aportará contratos de esquema/negocio y tablas identificadas a este puerto;
Hernán no agrega nombres/monedas/fechas SERCOP obligatorios al núcleo. Los ejemplos
genéricos de comercio y sensores no son entregas del DW ni evidencia de VM.


## 8. Ubicación del DW y del programa de conexión

La guía Word `ACTIVIDADES_JOSE_JHAIR.docx` conserva la opción comunicada de
usar AWS, Azure o Hetzner cuando no haya capacidad OCI. José mantiene la elección
y preparación de la VM Ubuntu/Python 3.12; las garantías del cliente, snapshots,
concurrencia y recuperación son las mismas. Las referencias OCI describen el
entorno inicialmente previsto y no retiran esas alternativas de la guía Word.

El DW, DuckDB real y su programa/biblioteca de conexión estarán en la VM elegida
por José, con OCI como opción inicialmente prevista.
`packages/equiframe-data` versiona el código de acceso a desplegar allí; un cliente
ligero externo es opcional si se acuerda un servicio remoto. EquiFrame podrá
instalarse y ejecutarse dentro de la VM, o consumir snapshots verificados mediante
un proveedor externo. Abrir el archivo desde tres equipos no es la integración.

Las garantías y las entregas técnicas están en [integración OCI](OCI_INTEGRATION.md).
Este documento define interfaces; no implica que el servicio, la VM o el DW hayan
sido implementados ni probados por la CI del núcleo.

## 9. Congelación y coordinación de las tres parejas

El paso 10 técnico implementa auditoría/sello del experimento, ejecución de
estudios, evaluación, seis CSV, costes y reproducción desde registros. Un estudio
piloto conserva bloqueos científicos; un experimento final exige resolverlos.
El corpus 2025 requiere inventario/procedencia. El criterio `N_fit > 10_000`
se refiere a registros reales de la matriz efectiva de aprendizaje, no a las
adjudicaciones fuente, sumas de capturas reutilizadas o registros de calibration/test. Se informa N por
modelo/familia, soporte y grupos; no se atribuye al PDF del anteproyecto un mínimo
literal por familia. Esta condición sigue pendiente.
Tampoco hay etiquetas, entrenamiento/calibración o revisión externa acreditados
por el mero uso de las herramientas.

Para articular estudios por las tres parejas se conserva un catálogo común y las
mismas particiones/componentes de dependencia. El cierre de grupos precede a
train/calibration/test; reglas y variables se fijan antes de variantes/test, y
test no interviene en el ajuste. Se conserva la identidad de ejecuciones
reutilizadas y se evita duplicar muestras. No se mezclan scores de modelos de
parejas distintas como si compartieran escala. El software no consolida
automáticamente tres estudios ni resuelve la dependencia científica entre ellos.

El freeze genérico conserva cinco slots de modelos, con motivos explícitos para
familias sin bundle. El protocolo final declara las cinco; las dos fuera del
alcance principal pueden quedar sin casos/soporte y deben distinguirse de los
nueve estratos principales. Las métricas conservan cobertura y motivos de no
evaluabilidad, sin ceros ficticios.

Los bundles del benchmark verifican archivos y regeneran contenido lógico de
configuración, splits, etiquetas, decisiones y métricas/CSV desde registros,
sin reejecutar ETL ni exigir tiempos idénticos. No generan una aprobación personal
ni acreditan que un compañero haya realizado la reproducción. La revisión
independiente real requiere su propio recibo y evidencia.

## 10. Integración operacional del migrador

`check_migration` comprueba el IR/contrato y ambos compiladores sin leer entradas
ni ejecutar ETL. `migrate` recibe un `DataSource`, comprueba dependencias y
capacidades, fija/captura las mismas tablas una vez, verifica restricciones
físicas para ambos motores y ejecuta dos pipelines nativos. Compara sus salidas y,
si se aporta esperado, ejecuta las dos verificaciones contra esa captura aparte.
El esperado no alimenta perfiles ni detectores. R/perfil/M/B/H se reutilizan sin
entrenamiento; el bundle de detectores es opcional.

El IR cerrado admite Scan/Project/Filter/Cast exacto/EquiJoin/Aggregate/Sort con
políticas explícitas para ausencias, grupos, precisión, multiplicidad y orden.
Los límites nativos se declaran como capacidad no soportada; no se calcula una
salida común y se atribuye a otros motores. Es una interfaz extensible mediante
compiladores/adaptadores confiables registrados explícitamente, no traducción de
cualquier Python ni ejecución de plugins desde JSON. Véanse el
[diseño](MIGRATION_DESIGN.md) y la [API vigente](API_CONTRACTS.md#17-migrador-declarativo-en-núcleo-0100).

`MigrationSpec.require_rules=True` es el default. Con
`require_rules=False` explícito se exige ETL y los perfiles/detectores solicitados;
R/H pueden seguir no evaluables y las alertas parciales se conservan. El migrador
no cambia el `complete` o `exit_code` de los pipelines hijos ni interpreta R no
evaluable como ausencia de alerta. `state` expresa equivalencia entre motores;
`verification` expresa resultado contra esperado o `not_requested`. `completed`
no autoriza publicar en el DW ni confirma independencia del esperado.

`read_migration` y `migration verify` comprueban evidencia física, inventario,
referencias, snapshots y reportes locales sin ETL. Esa integridad no certifica
revisores, autenticidad humana o corrección del esperado. Las referencias del
migrador inicial mantienen rutas locales absolutas; no constituyen el bundle
portátil de estudio. En 0.11.0, `export_bundle`/`import_bundle` conserva esos bytes
y resuelve sólo capturas verificadas dentro de un inventario cerrado; no cambia
el bundle de estudio. Los presupuestos son cooperativos y no cuotas duras de memoria. El
servicio mantiene sus propios límites agregados, permisos y controles de carga.

## Consumidor público acotado actual

El [ejemplo SERCOP](SERCOP_EXAMPLE.md) usa la API oficial pública y un snapshot
fijado fuera de Git. Su carga Parquet local y reconciliación manual de dos awards
prueban el consumidor de Hernán; no acreditan conexión al servicio de José,
esquema DW de Jhair, escritores compartidos ni aceptación en OCI. El contrato de
entrega de esos responsables continúa vigente, sin modificar sus carpetas.
