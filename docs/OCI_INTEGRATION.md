# Integración de EquiFrame con el DW en OCI

## Estado y alcance

El DW, el archivo DuckDB real y la biblioteca o programa que abre sus conexiones
residirán en una VM de OCI. Este documento fija la integración prevista; no
representa un despliegue, un servicio remoto ya disponible ni una conexión probada.
El núcleo EquiFrame 0.4.0 sigue siendo local e independiente de OCI y del esquema de dominio.

El adaptador DuckDB del núcleo abre una conexión propia `:memory:` para ejecutar
transformaciones sobre entradas registradas. No abre el archivo del DW ni acepta
una URL SSH como conexión DuckDB. El acceso real corresponde al componente de datos.

## Dos formas de ejecutar

| Modalidad | Ubicación y acceso | Entrega necesaria |
|---|---|---|
| Ejecución dentro de OCI | EquiFrame y el programa de conexión se instalan en la VM. Un proceso autorizado materializa un snapshot y ejecuta EquiFrame allí. El operador accede por SSH o por un servicio de trabajos | Entorno Python fijado, acceso individual, coordinación del DW, snapshot y destino de resultados |
| Ejecución desde otro equipo | Un proveedor explícito consulta el servicio de OCI y descarga Arrow IPC file/Parquet verificables; después entrega `LoadedTable` o referencias locales al núcleo | Servicio autenticado, protocolo versionado, cliente opcional, hashes y snapshot fijo |

Las dos modalidades conservan el mismo contrato y la API `DataSource`.
La conexión que abre el archivo DuckDB real permanece en OCI. Una modalidad API
puede incorporar un cliente ligero en el equipo consumidor; ese cliente no abre
el archivo de la base ni necesita una copia de su biblioteca de conexión interna.

Los archivos de una corrida deben proceder de **un mismo snapshot inmutable**.
Una ruta local mutable o resolver `latest` por cada tabla no ofrece esa garantía.
El transporte HTTP/SSH, los permisos y las cuotas pertenecen al proveedor externo:
`LocalDataSource`, `LocalArtifactStore` y `read_table` no hacen descargas implícitas.

## Coordinación de DuckDB

Un proceso propietario administra la base mutable, las conexiones y las cargas.
La alternativa para lectores independientes es un snapshot inmutable publicado,
sin un escritor concurrente sobre el mismo archivo. Los lectores nunca abren un
archivo de producción mientras otro proceso independiente lo modifica.

La publicación propuesta construye una versión nueva, ejecuta sus controles y
publica el catálogo/recibo después de completarla. Los lectores fijan el ID de
versión; la carga siguiente no sustituye sus archivos abiertos. El servicio
conserva snapshots aún utilizados y define su retención y recuperación.

Esta estrategia debe comprobarse con la versión elegida para el servicio. Las
alternativas remotas descritas por DuckDB no se presuponen instaladas ni disponibles
por instalar el extra `equiframe[duckdb]`.
[Concurrencia oficial de DuckDB](https://duckdb.org/docs/current/connect/concurrency).

## Entregas e interfaces

El componente de datos aporta configuración no secreta, entorno de ejecución,
autenticación, coordinación de trabajos, acceso a snapshots, respaldos y operación.
Sus ubicaciones son `packages/equiframe-data`, `services/data-gateway` e `infra`.
El programa de conexión y sus dependencias se despliegan en OCI conforme al
procedimiento que implemente su responsable.

El componente de dominio aporta el modelo/DDL, diccionario, mapeos, preparación y
carga del DW, reconciliación y contratos de negocio en `packages/equiframe-sercop`.
Las bases y datos reales permanecen fuera de Git.

Para integrar ambos con EquiFrame se acuerda un recibo versionado que incluya:

- ID de snapshot y revisión del esquema de dominio; la misma versión para todas las tablas.
- Referencias, formato, tamaño, SHA-256, nombres de tablas y conteos de filas.
- Tipos físicos y lógicos, precisión/escala decimal, unidades/monedas y políticas de claves.
- Distinción NULL/NaN, fechas frente a instantes, unidad temporal y zona cuando exista.
- Procedencia y revisión del código de extracción; política de orden si resulta relevante.
- Estados de publicación/trabajo, errores, cancelación y presupuestos efectivos.

`SnapshotManifest` es una especificación futura; no existe todavía un modelo de ese
nombre en la API del núcleo. Un proveedor implementa el puerto actual:

```python
@property
def table_names(self) -> tuple[str, ...]: ...

def resolve(self, name: str, *, context: RunContext) -> LoadedTable: ...
```

La implementación debe resolver el snapshot antes de cargar tablas y registrar su
identidad en la evidencia. Debe preservar tipos/máscaras y verificar hashes antes
de devolver datos. Los controles de EquiFrame son por tabla y tras materializar;
el servicio debe imponer además límites agregados de RAM, trabajos y disco.

## Acceso y validación pendientes

Cada persona usa credenciales y claves propias para GitHub y OCI. El acceso SSH a
OCI depende de la imagen, el usuario y la clave pública autorizada; estos valores
los entrega el administrador de la VM.
[Acceso oficial a instancias OCI](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/accessinginstance.htm).

Clonar o actualizar Git no despliega automáticamente servicios ni carga el DW.
Las dependencias se instalan en un entorno de ejecución separado; los secretos se
configuran en la VM y no en archivos versionados.

Antes de declarar integración real se comprobarán lectura autorizada del DW,
snapshot consistente, integridad alterada, fallos de transporte, cancelación,
concurrencia de carga/lectura y conservación de decimal/ausencias/tiempo. También se
registrarán sistema, arquitectura, versiones y recursos de la VM real.

La CI de GitHub usa runners temporales de Windows, Linux y macOS. Probar Linux
ARM64 ayuda a detectar problemas de arquitectura; no certifica la imagen OCI,
su red, el acceso al DW ni la capacidad de RAM. Ningún job actual despliega en OCI.

## Dimensionamiento preliminar de la VM

El DW, el archivo DuckDB y la API Python aún no existen; por tanto, faltan
tamaño del archivo, cardinalidades, consultas, número de workers y simultaneidad
de carga/lectura para medir memoria y disco. Para alojar juntos estos servicios,
**4 GB no se consideran capacidad suficiente para el objetivo completo**.
Solo podrían servir para un prototipo pequeño y secuencial con límites estrictos.
DuckDB usa por defecto hasta el 80 % de RAM en su buffer manager, y ese límite
no cubre todas sus asignaciones; en 4 GB dejaría una reserva nominal de solo
0,8 GB para Ubuntu, Python, Arrow y el servicio. DuckDB recomienda 1–4 GB por
hilo para buen rendimiento y reducir memoria/hilos ante OOM.

La referencia inicial razonable es Ampere A1 con **2 OCPU y 12 GB**, sujeta a
disponibilidad en la región principal, espacio de disco y pruebas ARM64. La
asignación Always Free publicada por Oracle para A1 equivale actualmente a
2 OCPU y 12 GB; el almacenamiento gratuito combinado de volúmenes de arranque
y bloques es 200 GB en la región principal. Esto no certifica que 12 GB basten
para cualquier DW o benchmark: José y Jhair deben medir volumen, picos de RSS,
consultas, spill, snapshots y respaldos antes de fijar cuotas de servicio.

En la cuenta Free Tier de OCI, región US East (Ashburn), se verificó un volumen
de arranque Always Free de 47 GB y ningún volumen de bloques en el compartimento
raíz. Una segunda VM con volumen predeterminado de 47 GB habría usado unos
94 GB del total gratuito de 200 GB. El estimador del formulario mostró un costo
nominal de USD 2/mes para el volumen de arranque, pero Oracle indica que ese
estimador no aplica los tramos gratuitos. Se seleccionó Ubuntu 24.04, A1 Flex
de 2 OCPU/12 GB, volumen predeterminado, red pública existente y clave SSH
propia; solo quedó activo el agente de métricas de instancia. **No se creó la VM**:
OCI respondió `Out of capacity` para A1 Flex en AD-2, AD-1 y AD-3 el
2026-09-30. Hay que reintentar en Ashburn cuando exista capacidad, sin cambiar
de plan ni activar recursos pagados.

Cuando la VM exista, el administrador agregará usuarios Linux individuales para
Jhair y José con sus claves públicas propias y comprobará SSH por el puerto 22.
No se deben compartir la clave privada inicial ni las cuentas. El DW, el archivo
DuckDB y la API Python se construirán después; no forman parte de este paso.

Fuentes: [Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm),
[estimación de costos de OCI](https://docs.oracle.com/en-us/iaas/Content/Billing/Tasks/signingup_topic-Estimating_Costs.htm),
[DuckDB: memoria y OOM](https://duckdb.org/docs/current/guides/performance/oom),
[DuckDB: rendimiento y memoria por hilo](https://duckdb.org/docs/current/guides/performance/my_workload_is_slow).
