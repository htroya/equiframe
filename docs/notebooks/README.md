# Cuadernos públicos de EquiFrame

Estos dos cuadernos pueden abrirse en Google Colab o en Jupyter. Cada uno
descarga 10.000 registros reales desde Kaggle y contiene instrucciones, tipos
explícitos, controles de aceptación y resultados de una ejecución comprobada.
No requieren claves API, GPU ni acceso a la VM del proyecto.

| Cuaderno | Contenido | Abrir en Colab |
| --- | --- | --- |
| [Instalación y uso](01_instalacion_y_uso.ipynb) | Instalación identificada, lectura de 10.000 registros, CSV/JSONL/Parquet, comparación y rechazo de una modificación controlada | [Abrir](https://colab.research.google.com/github/htroya/equiframe/blob/main/docs/notebooks/01_instalacion_y_uso.ipynb) |
| [Tres motores con 10.000 registros](02_kaggle_10000_tres_motores.ipynb) | Agregaciones nativas en Pandas, Polars y DuckDB, esperado construido por separado, tres parejas, perfiles agrupados 1.1 y redistribución controlada | [Abrir](https://colab.research.google.com/github/htroya/equiframe/blob/main/docs/notebooks/02_kaggle_10000_tres_motores.ipynb) |

## Ejecución

1. Abre un cuaderno y selecciona un entorno CPU con Python 3.10, 3.11, 3.12 o 3.13.
2. Ejecuta las celdas en orden. La primera usa `%pip install --upgrade "equiframe[engines]"`
   desde PyPI, sin fijar una versión, y muestra la versión que se instaló. Después
   puedes usar `import equiframe as ef`.
3. Examina los estados y la completitud antes de aceptar una comparación.
   Los controles modificados deben producir `different` y rechazar la aceptación.
4. La última celda elimina los archivos temporales de esa ejecución. Al repetir,
   vuelve a ejecutar desde el principio para crear un espacio nuevo.

La lectura pública en GitHub y Colab no requiere pertenecer al proyecto.
Google puede solicitar una cuenta propia para asignar un entorno de ejecución;
esa cuenta no se utiliza para descargar los datos ni para instalar EquiFrame.

## Datos y atribución

La descarga procede de [E-Commerce Data, versión 1, en Kaggle](https://www.kaggle.com/datasets/carrie1/ecommerce-data).
La fuente original es **Online Retail**, publicada por Daqing Chen en UCI:
https://doi.org/10.24432/C5BW33. UCI declara **CC BY 4.0**. Los cuadernos conservan
esta atribución y verifican el SHA-256 del CSV original. No se atribuye CC0 a la
copia de Kaggle, cuyos metadatos no identifican una licencia específica.

Se seleccionan las primeras 10.000 de las 541.909 líneas originales. No se
replican registros ni se eliminan devoluciones. Se mantienen 2.291 clientes
ausentes, 42 descripciones ausentes y 130 cantidades negativas. La selección
es didáctica y determinista; no constituye una muestra estadística del corpus.
Los datos y las capturas se descargan al ejecutar y quedan fuera de Git.

## Verificación realizada

La revisión actual se ejecutó completa el 19 de noviembre de 2026 en un entorno
nuevo de Linux ARM64 con CPython 3.12.15 y kernels Jupyter reales, incluida la
celda `%pip` de instalación sin versión. PyPI resolvió EquiFrame 0.14.0. Se
ejecutaron las cinco celdas de código del primer cuaderno y las ocho del segundo,
con cero salidas de error. Cada uno procesó 10.000 registros, comprobó los tres
formatos y rechazó su control negativo. El segundo ejecutó los tres motores,
sus tres contrastes con un esperado separado, las tres parejas y tres perfiles.
El [recibo de ejecución](execution-20261119.json) registra sus huellas y entorno.

Las versiones anteriores de los cuerpos de cálculo también se verificaron en
Windows; la instalación simplificada de esta revisión se ejecutó en Linux.
Las salidas incorporadas proceden de la ejecución Linux; no se afirma una
ejecución en el servicio alojado de Colab. Los ejemplos comprueban software y
no estiman eficacia de detectores ni resultados científicos sobre SERCOP.
