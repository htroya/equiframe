# SERCOP 2025 en Windows para usar con Alpha

El depósito local está en **`local-data/sercop/2025`**, dentro del repositorio
y excluido de Git. Después, el propietario autorizó la
[entrega pública de la captura actual](SERCOP_PUBLIC_DELIVERY_20261012.md) a la VM;
el depósito ampliado y sus evidencias privadas permanecen en Windows. Se conservan todos los métodos
ofrecidos por el selector oficial de 2025, tanto el año completo como sus doce
meses, sin seleccionar una muestra de filas.

## Contenido comprobado

| Contenido | Alcance |
|---|---|
| Nuevas descargas | 39 respuestas completas: anual + 12 meses × JSON/CSV/XLSX; hashes, cabeceras HTTP y CRC de los ZIP comprobados |
| Formatos originales organizados | 13 JSON completos, 104 CSV originales y 13 XLSX con bytes originales; cada formato conserva su captura |
| CSV utilizables | 104 tablas Parquet completas, 1.924.544 filas de exportación con lectura completa contra el hash construido desde el CSV antes de escribir |
| Captura JSON anterior conservada | 28 colecciones, 6.081.374 ocurrencias: 190.619 packages/releases y 183.891 adjudicaciones; lectura completa verificada |
| Captura JSON actual proyectada | 28 colecciones, 6.081.376 ocurrencias y 35.369.723 escalares; lectura completa contra las filas construidas desde la fuente |
| Referencias | 21 documentos/esquemas/extensiones públicos guardados con procedencia y SHA-256 |
| Consumidor nativo completo | 312 lecturas completas: 104 tablas y 1.924.544 filas por cada motor pandas, Polars y DuckDB |
| Comparación SDK de resúmenes | Nueve comparaciones completas sobre resúmenes de 104 tablas; seis equivalentes y tres diferencias deliberadas |
| Ejemplo anual ejecutado | Las 183.891 adjudicaciones agrupadas por moneda en tres motores; siete comparaciones completas contra el oráculo CSV y entre motores |
| Custodia local | 531 archivos y 9.506.267.980 bytes comprobados; 350 hashes de fuentes, formatos organizados, referencias y tablas cotejados con sus recibos |

El [resultado consolidado](SERCOP_LOCAL_REPOSITORY_RESULT_20261012.json)
conserva los hashes de los índices y recibos. Los datos y el inventario detallado
siguen excluidos de Git; el informe contiene sólo metadatos de preparación.
El censo de 531 archivos precede a la creación del índice, informe local y
README. Esos tres archivos adicionales tienen hashes publicados por separado;
el depósito al cierre contiene 534 archivos. No se cuentan recursivamente los
índices como si fueran nuevos datos de contratación.

**1.924.544 no es un número de casos únicos:** suma tablas diferentes y los
solapamientos entre la exportación anual y las mensuales. **6.081.374 tampoco
son procesos únicos:** incluye cada aparición de arrays, participantes, roles,
items y demás colecciones, con posición y vínculo al padre. No se deduplican.

La captura nueva anual JSON tiene SHA-256
`80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3`.
La captura anterior usada en las pruebas tiene SHA-256
`9ee4e5f94f44e42c89ade804d00ed69cd24604d246ad6450a4a43b2bd42e3632`.
No son el mismo archivo y se mantienen separadas. Las 28 colecciones actuales
tienen su propia ejecución y catálogo; no reutilizan la acreditación anterior.
La comparación completa emparejada por posición encontró 190.614 arrays de
releases distintos y cinco iguales. No es una comparación semántica por OCID
ni acredita que cambiaron 190.614 procesos únicos. Ambos contenidos completos
y las observaciones de diferencias se conservan.

## Organización y uso

- `01_fuentes_originales`: respuestas originales y recibos; capturas separadas.
- `02_tablas/<SHA16>`: todas las colecciones anidadas del JSON por captura,
  con catálogo, tipos, rutas, posiciones, payload completo y hashes de filas.
- `03_metadatos`: adquisiciones, catálogos, procedencia y comprobaciones.
- `04_evidencias`: ensayos anteriores y nuevos recibos de consumidor.
- `05_exports/consulta_20261012/mesNN`: JSON/CSV/XLSX organizados;
  los ocho CSV por período también tienen tablas Parquet.
- `06_referencias`: política de publicación, licencia declarada y esquemas
  OCDS/extensiones con URLs y hashes del momento de captura.
- `07_ejemplos`: agrupación anual ejecutada, diferencias deliberadas y recibos.

La exportación anual CSV contiene 190.619 releases, 37.821 registros de
planning, 185.536 de tender, 183.891 awards, 183.888 suppliers y 180.465
contracts, además de metadata y extensions. El catálogo guarda columnas,
filas y hashes de cada tabla mensual y anual; no es necesario reconstruirlo
manualmente ni cargar el JSON de 1,72 GB entero en memoria.

Los CSV se conservan como **texto UTF-8**, sin inferir monedas, fechas o números.
Las celdas vacías permanecen texto vacío. La fuente CSV original distingue su
representación de quoting y líneas; la tabla refleja sus registros lógicos.
En las tablas JSON los números tienen texto Decimal exacto y columna `@type:`:
no se convierten a float. Los campos ausentes se distinguen de `null`, cada
array mantiene su posición y `__payload_json` conserva todo su contenido.
No se debe convertir un identificador a número ni sumar importes entre monedas.

`tools/sercop_local_repository.py` preserva, adquiere y proyecta JSON completo.
`tools/sercop_local_exports.py` organiza todos los formatos y proyecta CSV con
oráculo de lectura completa. `tools/sercop_local_consumer.py` verifica cada tabla
CSV en tres motores nativos y usa A13 para comparar resúmenes de sus recibos.
Sus comparaciones de resúmenes no se anuncian como comparaciones SDK de todas
las filas brutas. Los resultados ejecutados se registran por separado.

`tools/sercop_awards_example.py` ofrece el ejemplo anual comprobado.
`tools/sercop_local_index.py` verifica el depósito y genera un README,
esquemas/índice portable y recibo consolidado. El generador JSON actual conserva
el codificador Decimal original para payloads; usa lotes de 4.096 filas y un
codificador canónico equivalente para filas planas. La equivalencia de bytes,
tipos, colecciones y hashes respecto de la herramienta anterior fue probada
antes de la extracción actual; la versión anterior permanece archivada.

La carpeta incluye un README y ejemplos locales de consulta; el Word permanece
intacto. Estos datos son un depósito de consumidor, no el DW del equipo ni
una cohorte normal aprobada. No acreditan `N_fit > 10.000`, etiquetas humanas,
hipótesis de tesis o puntos automáticos de madurez/trazabilidad.

Fuentes: [portal oficial SERCOP](https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos/)
y [esquema oficial OCDS 1.1.5](https://standard.open-contracting.org/schema/1__1__5/release-schema.json).
El formato declara OCDS 1.1; guardar el esquema publicado no equivale a validar
el conjunto contra todas sus extensiones ni a aprobar su semántica de dominio.
