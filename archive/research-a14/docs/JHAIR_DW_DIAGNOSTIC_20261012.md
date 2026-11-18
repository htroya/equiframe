# Diagnóstico técnico del aporte DW

El repositorio confirmado es `htroya/equiframe`. En `main` existe
[`packages/equiframe-sercop`](../packages/equiframe-sercop/README.md): DDL,
diccionario, inicialización DuckDB, carga JSON, reconciliadores, consulta y dos
ejemplos sintéticos. Es una base útil de **prototipo DW**, todavía sin aceptación
del almacén real SERCOP 2025. Inicializar el ejemplo produce una sola fila de
hechos de 2023; no demuestra carga o reconciliación del corpus anual.

## Dónde y cuándo se subió

El [commit de introducción](https://github.com/htroya/equiframe/commit/ce016180979b341e9cfb40adbfa761b8e2d25f47)
es del 4 de octubre; declara `Claude Code` como autor Git y se vincula a la cuenta
`Karim13014`. La [corrección mecánica](https://github.com/htroya/equiframe/commit/c4be1c5a29d9f58b2628882bd986de2bb5ca4184)
del 6 de octubre corrigió SQL y documentó límites. El corte remoto consultado es
`ac2434841d562599f4bcdd8e30d15ff3000ee7d4`. No se encontró una actualización DW
posterior en `main`, ni un PR asociado al commit inicial. Estos metadatos no
demuestran por sí solos quién escribió físicamente cada aporte.

La captura muestra `git push origin main` con `Everything up-to-date`: ese
comando concreto no transfirió cambios nuevos. La rama `feature/datawarehouse-etl`
tiene un gateway en el [commit c1d1863](https://github.com/htroya/equiframe/commit/c1d1863c5c49f3953fd40f2f66fd8fb6a5094b53),
asociado a `gaonauide-create`; se analiza por separado y no se atribuye a Jhair.
No se fusionó ni cambió de rama para revisar estos componentes.

## Comprobaciones ejecutadas

Se copiaron los archivos identificados y se usaron bases sintéticas exclusivas
en Windows, Python 3.12.4 y DuckDB 1.5.6. El código revisado quedó intacto.
Los [resultados y hashes](JHAIR_DW_DIAGNOSTIC_RESULT_20261012.json) distinguen
ejecución observada de interpretación; no son un ensayo científico ni un EDA.

| Caso | Resultado observado |
|---|---|
| D01 | La inicialización del demo funciona: una adjudicación de muestra |
| D02 | Desde otro directorio falla: no encuentra `dw_schema.sql` |
| D03 | Una ruta nueva indicada con `--db-path` queda sin tabla `snapshot` |
| D04 | Un objeto de paquete OCDS con `releases` se rechaza |
| D05 | La lista de paquetes puede terminar con éxito guardando `UNKNOWN`, `0.00`, `USD` y la fecha actual |
| D06 | Dos proveedores y dos ítems se reducen a uno de cada clase |
| D07 | Ausencias monetarias/de fecha se sustituyen por valores no presentes en la fuente |
| D08 | Un lote falla con salida no cero, pero conserva una fila cargada parcialmente |
| D09 | Un registro adicional en destino no se detecta en la reconciliación |

El diccionario enumera 37 de las 46 columnas del esquema. Dos filas con
`DECIMAL(18,2)` carecen de comillas CSV y se desalinean. Faltan nueve columnas,
entre ellas claves sustitutas y procedencia/versionado de `snapshot`.

En el gateway de la otra rama se reprodujeron además dos incumplimientos:
dos gestores obtienen simultáneamente el supuesto lock; un fallo controlado
al renombrar elimina la publicación anterior. Ese gestor copia archivos CSV/
Parquet; no ejecuta por sí mismo la carga del DDL DW. No se cambió infraestructura
del equipo ni se desplegó este prototipo en la VM.

## Qué falta para un DW aceptable

1. Aprobar el grano y claves compuestas con identidad del proceso y adjudicación;
   interpretar historial OCDS y registrar la versión exacta de cada publicación.
2. Leer el formato real con identidad del padre, conservar todas las asociaciones
   y usar puentes sin repetir montos por proveedor/ítem.
3. Conservar decimales y monedas; declarar ausencias, fechas, cuarentenas y reglas
   de dominio, evitando completar datos por suposición.
4. Completar/corregir el diccionario y resolver rutas de esquema/base con independencia
   del directorio del usuario; separar inicialización productiva de datos de demo.
5. Preparar cargas completas con staging/transacción, repetición idempotente y
   publicación recuperable; comprobar interrupciones y coordinación de escritores.
6. Reconciliar en ambos sentidos usando claves completas, multiplicidad, importes
   exactos por moneda y estados; conservar diferencias y devolver salida no cero.
7. Ejecutar el corpus real identificado con oráculos independientes, recibos,
   hashes, recursos y reglas aprobadas; entregar commit/rama y dictamen de dominio.
8. Integrar con José la lectura de snapshots inmutables y la continuidad del servicio;
   demostrar las garantías en sus componentes reales.

## Porcentaje de aporte y problema de VM

No existe una rúbrica acordada para convertir commits o líneas en porcentaje de
autoría de tesis. Por eso **no se acredita un porcentaje personal**. El criterio
T13 de integración DW permanece parcial. Cerrarlo íntegramente añadiría **1/22 =
4,55 puntos porcentuales** al índice de requisitos, no a la autoría de Jhair.
T04 y T14 necesitan además decisiones y evidencia compartidas del equipo.

Los scripts DW no contienen conexión SSH. No se puede deducir el error concreto
de su VM sin comando y traceback. D02/D03 son fallos reproducibles que podrían
afectarle; no demuestran que sean su incidente. Nuestro acceso SSH autorizado
sí permitió completar el laboratorio A13 y entregar el dataset, acciones distintas
de desplegar/aceptar su DW.

## Mensaje propuesto para Jhair

> Revisé `packages/equiframe-sercop` en `main`: existe el prototipo y el demo
> funciona. El último cambio DW que encuentro es del 6 de octubre. Pásanos la
> rama/commit de tu actualización y el comando completo con el error de la VM,
> junto con Python/DuckDB, directorio de ejecución y ruta de la base. Reproduje
> problemas con la ruta del esquema y con `--db-path`. Para aceptar el DW anual
> faltan lectura del OCDS real con OCID padre, conservación de proveedores/ítems,
> decimales y ausencias, carga recuperable y reconciliación bidireccional. Podemos
> ayudarte a reproducir el error con esos datos; no necesitamos claves ni contraseñas.

Este texto es un borrador para el propietario; no se envió a otras personas.
