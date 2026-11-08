# Lectura de archivos y conversión de DataFrames

La API `load_dataset`, incluida en el alcance estable de 0.12.0, lee un archivo local, descubre su estructura
y crea un **DataFrame real de Pandas**. Si se selecciona Polars o DuckDB,
convierte ese mismo DataFrame y entrega el objeto nativo correspondiente.
Esta ruta convierte datos; no traduce un programa ni ejecuta transformaciones
independientes en tres motores. Tampoco entrena detectores ni ejecuta R.

La implementación se añadió el 26 de octubre de 2026. Su estabilización protege
la interfaz, las conversiones admitidas y sus errores; no promete todas las
variantes de cada formato o combinación de dependencias. La
[compatibilidad](compatibility.md) identifica las verificaciones ejecutadas y
sus límites, sin atribuirlas a otros artefactos.

## Uso desde Python

```python
import equiframe as ef

datos = ef.load_dataset("ventas.json")
pandas_df = datos.pandas
print(datos.info.to_dict())  # columnas, tipos observados, nulos, NaN y número de filas

polars_datos = ef.convert_dataset(datos, target="polars")
polars_df = polars_datos.frame

# Las conversiones encadenadas consumen el objeto nativo actual.
with ef.convert_dataset(polars_datos, target="duckdb") as duckdb_datos:
    pandas_de_vuelta = ef.convert_dataset(duckdb_datos, target="pandas")

# También puede seleccionarse el destino en la misma llamada.
with ef.load_dataset("ventas.parquet", target="duckdb") as datos_sql:
    relacion = datos_sql.frame
    resultado = relacion.limit(10).df()
# La relación DuckDB depende de la conexión privada, cerrada al salir del with.
```

`DatasetResult.pandas` conserva el DataFrame de origen y `frame` contiene el
objeto del destino seleccionado: DataFrame de Pandas, DataFrame de Polars o
DuckDBPyRelation. `close()` libera la conexión DuckDB que pertenece al resultado;
no abre archivos DuckDB compartidos. El usuario puede trabajar con esos objetos
mediante las APIs de sus motores. `inspect_dataset(path)` devuelve solamente
`DatasetInfo`, pero realiza la lectura completa dentro de los límites declarados.

## Identidad de la fuente y de la conversión

Cada lectura utiliza una única captura de los bytes del archivo y devuelve
`DatasetResult.provenance`, también accesible desde `info.provenance`.
`DatasetSource` identifica URI, formato, SHA-256 y tamaño de esos bytes; conserva
las opciones efectivas en `read_options_json`, consultables como un objeto con
la propiedad `read_options`. Esto incluye la hoja, el delimitador o el modo de
texto resueltos durante la lectura, no solamente las opciones iniciales.

`DatasetProvenance` vincula esa fuente con `pandas_sha256`, el destino `target`
y `target_sha256`. Las conversiones admiten las seis direcciones entre Pandas,
Polars y DuckDB; leen el objeto nativo seleccionado, sin releer el archivo ni
sustituirlo por una copia anterior. La conversión rechaza una modificación del
objeto nativo o del Pandas original posterior a la captura. El esquema nativo
de Polars o DuckDB se verifica antes de convertir a Arrow; una exportación Arrow
coincidente no sustituye esa comprobación de tipos. La exportación del origen
también rechaza una modificación del Pandas original. Para trabajar sobre datos modificados,
el consumidor debe establecer una nueva entrada y su identidad, sin reutilizar
la procedencia original como si describiera esos cambios.

```python
print(datos.provenance.source.sha256)
print(datos.provenance.source.read_options)
print(datos.info.to_dict(include_provenance=True))
```

`info.to_dict()` omite esa procedencia por defecto, porque su URI puede contener
una ruta privada. `include_provenance=True` la añade explícitamente;
`include_metadata=True` controla por separado los metadatos originales.
Estas huellas identifican los datos y opciones observados; no autentican al
productor del archivo ni aprueban una migración de programas.

## Formatos y decisiones que puede requerir el lector

| Archivo | Representación y opciones |
|---|---|
| JSON | Un objeto de registro o una lista de registros. Los escalares y listas de valores se conservan en una columna `value`, sin aplanar sus objetos o arrays. Los números fraccionarios se leen como `Decimal`. Para un contenedor de registros se exige `records_path`, sin expandir otras colecciones. |
| JSONL / NDJSON | Un registro o valor por línea no vacía. Se rechazan miembros JSON duplicados, NaN e Infinity no estándar. |
| CSV | Detecta delimitadores consistentes entre coma, punto y coma, tabulación y barra vertical. Si más de uno encaja, solicita elección. Por defecto la primera fila es el encabezado. |
| TXT / TSV | Texto libre: una columna `text`, una fila por línea. Si también puede interpretarse como tabla, pregunta `lines` o `delimited`. Se puede fijar `delimiter`, `header` y `text_mode`. No se inventa un esquema para texto libre. |
| Excel | `.xlsx` y `.xlsm` mediante openpyxl; `.xls` mediante xlrd. Selecciona automáticamente solo cuando hay una hoja. Con varias hojas exige `sheet`. Lee las filas/celdas observadas sin truncarlas según dimensiones declaradas por el productor. No ejecuta macros; XLSX/XLSM con fórmulas o errores exige un archivo con valores. |
| XML | Usa defusedxml y rechaza DTD, entidades y referencias externas. Conserva atributos, campos y elementos repetidos; `records_path` permite seleccionar registros. El XML de contenido mixto que no pueda representarse fielmente se rechaza. |
| Parquet | Conserva tipos Arrow, unidades, zonas y máscaras de ausencia al construir Pandas con ArrowDtype. |
| GeoJSON | FeatureCollection, Feature y geometrías. Conserva `geometry` y `properties` originales; expone además `properties.nombre` y los otros miembros como `feature.nombre`. Los metadatos de la colección quedan en `info.metadata`. No requiere GIS ni cambia el sistema de coordenadas. |

Ejemplos de desambiguación:

```python
opciones = ef.DatasetReadOptions(sheet="Ventas")
datos = ef.load_dataset("libro.xlsx", options=opciones, target="polars")

opciones = ef.DatasetReadOptions(records_path="/respuesta/ventas")
datos = ef.load_dataset("respuesta.json", options=opciones)

opciones = ef.DatasetReadOptions(delimiter="\t", header=False)
datos = ef.load_dataset("mediciones.txt", options=opciones)
```

En JSON `records_path` es un JSON Pointer RFC 6901. En XML es una ruta de
elementos de ElementTree, por ejemplo `./ventas/venta` o `.//venta`.
No se descargan esquemas, no se ejecuta XPath arbitrario ni se evalúa código.

## Tipos y preservación

La inferencia textual es conservadora: enteros canónicos se convierten en
enteros y números decimales inequívocos se convierten en `Decimal`, sin pasar
por float. Los ceros iniciales, espacios, representaciones mezcladas y fechas
permanecen como texto. Un campo vacío sigue siendo una cadena vacía; no se
interpreta automáticamente como nulo ni se adivinan tokens como `NA`.
Los números ya almacenados por Excel tienen la precisión que conserva el
libro; no se recuperan dígitos perdidos antes de llegar a EquiFrame. Los formatos
Excel de enteros con ceros de relleno, como `000000`, se conservan como texto y
se informa esa decisión. Las fechas tipadas de Excel conservan su tipo.
XLS expone valores almacenados o cacheados; su lector no identifica
independientemente todas las fórmulas del archivo heredado.

`DatasetInfo.notes` informa las inferencias. Para conservar todo texto o
declarar unas pocas columnas:

```python
opciones = ef.DatasetReadOptions(
    infer_text_types=False,
    column_types={"importe": "decimal", "cantidad": "integer", "codigo": "string"},
)
datos = ef.load_dataset("ventas.csv", options=opciones)
```

Tipos explícitos admitidos: `string`, `integer`, `decimal`, `boolean` y `json`.
`json` conserva un objeto o array como texto JSON sin convertir sus Decimal a
float. Es una representación explícita útil para geometrías heterogéneas o
propiedades anidadas que no admitan una única estructura Arrow:

```python
opciones = ef.DatasetReadOptions(column_types={"geometry": "json", "properties": "json"})
datos = ef.load_dataset("mapa.geojson", options=opciones, target="polars")
```

No se cambia automáticamente a texto cuando un motor no admite un tipo.
La ruta de conversión comprueba la representación Arrow inicial y recorre por
completo el resultado nativo para rechazar cambios de contenido, nulos/NaN,
orden, precisión, escala o zona temporal. Permite cambios de transporte como
`string` a `large_string` que conservan los valores. Un tipo incompatible genera
`CapabilityError`; el resultado no se declara equivalente ni se normaliza.

Los campos JSON ausentes se materializan como nulos en las columnas unificadas;
sus posiciones originales quedan en `info.metadata["absent_json_members_by_row"]`.
`info.to_dict()` omite metadatos originales por defecto; use
`info.to_dict(include_metadata=True)` cuando quiera incluirlos explícitamente.
Los metadatos de una colección GeoJSON pueden contener información del usuario.

## Un comando para leer y elegir destino

```console
equiframe dataset load ventas.json
```

La misma invocación muestra la estructura, pregunta las ambigüedades del archivo
y pregunta: «¿A qué motor quiere migrar desde Pandas? pandas / polars / duckdb».
Para scripts y entradas no interactivas se pasa el destino:

```console
equiframe dataset load ventas.json --target polars
equiframe dataset load libro.xlsx --sheet Ventas --target duckdb
equiframe dataset load ventas.csv --target polars --output copia.parquet
equiframe dataset inspect mapa.geojson
```

Opciones de lectura: `--format`, `--sheet`, `--records-path`, `--delimiter`
(`tab` significa tabulación), `--header/--no-header`, `--text-mode`,
`--infer-types/--keep-text`, `--encoding`, `--max-bytes` y `--max-rows`.
Sin `--output`, el objeto convertido existe durante el comando; en Python
la API devuelve el objeto para continuar trabajando. `--output` y
`DatasetResult.to_parquet()` exportan el **Pandas original cargado** a un Parquet
nuevo; no exportan transformaciones que el usuario aplique después a `frame`.
La exportación escribe y sincroniza primero un temporal hermano, y publica
exclusivamente el archivo completo mediante un enlace duro en el mismo sistema
de archivos. El destino no se sobrescribe. Si el sistema no admite esa operación,
la exportación falla; no usa una copia parcial como alternativa. El temporal
propio se retira al terminar. No se promete durabilidad ante corte de energía.
Un error posterior a la publicación puede dejar el Parquet completo visible;
inspeccione y compruebe su contenido antes de decidir una recuperación, sin
suponer que cualquier archivo existente pertenece al intento fallido.
La conversión no equivale a una comparación
semántica de dos implementaciones; para esa tarea siguen disponibles `diff`
y los contratos de equivalencia.

Los fallos CLI conservan el código estable en la primera línea de stderr y la
guía fija `hint[...]` después. Un `DatasetChoiceRequired` puede añadir entonces
un objeto JSON con `required_option` y `choices` para resolver una ambigüedad.
Un error de lectura/configuración termina con código 2; dependencias no
disponibles y fallos técnicos terminan con código 3. El código 0 sólo indica que
se completó la lectura y conversión solicitadas, sin aprobar equivalencia.

## Dependencias y límites

El extra `files` añade Pandas, Arrow, openpyxl, xlrd y defusedxml. Polars y DuckDB
se seleccionan mediante sus extras existentes. Los lectores y motores se importan
solo al usarlos; un extra faltante produce `MissingDependencyError` con la
dependencia necesaria. No hay instalaciones automáticas.

Por defecto se admiten hasta 128 MiB de archivo, un millón de filas y dos
millones de celdas. Son límites de admisión; no son cuotas duras de RAM ni de
descompresión. La lectura es local y completa, no distribuida ni en streaming.
Las rutas locales pueden seguir enlaces simbólicos; el llamante debe elegir
archivos y directorios de confianza. Se rechazan nombres de columnas duplicados,
filas CSV irregulares y conversiones sin representación fiel. No se infieren
claves de negocio, monedas, fechas, CRS ni reglas de aceptación del proyecto.
