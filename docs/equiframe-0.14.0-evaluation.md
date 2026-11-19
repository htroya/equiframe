# Evaluación de Isolation Forest con EquiFrame 0.14.0

La ejecución del 19 de noviembre de 2026 usó el wheel público
`equiframe-0.14.0-py3-none-any.whl` con SHA-256
`c1956d8cfeca3b558fccda9955d1cdba235934041df67ed753cca698ed461219`.
Los 173 archivos del paquete instalado coincidieron byte por byte con el
wheel. La evaluación usa el perfil **1.1** de esa versión.
[Ficha de PyPI](https://pypi.org/project/equiframe/0.14.0/) ·
[Protocolo y recibo de instalación](../validation/library_detection/results/public-spending-0140/protocol.json)

## Diseño y casos

Con los mismos CSV de adjudicaciones públicas de 2025 y las mismas huellas
de selección se ejecutaron **1.728 casos y 4.032 ejecuciones nativas**.
Los conjuntos de entrenamiento, desarrollo, calibración y prueba se
separaron por identificador de procedimiento (OCID). Los 1.152 casos de
prueba incluyen 512 normales, 512 con fallos controlados y 128 normales
bajo desplazamiento. Pandas, Polars y DuckDB coincidieron en el resultado,
la etiqueta derivada del esperado exacto y el perfil 1.1. Los tres motores
ejecutaron los mismos casos de prueba.

La verdad de referencia fue una agregación Python independiente en
centavos, por comprador y moneda, reconciliada con la comparación completa.
Las reglas R validaron conservación total y unicidad de clave. M fue
Isolation Forest con 200 árboles y calibración normal con alfa 0,05.
B fue el detector basado en MAD. H activó una alerta con R o M.
[Informe y registros reproducibles](../validation/library_detection/results/public-spending-0140)

## Resultados con semilla 7

| Método | Fallos detectados (512) | Omisiones evaluadas | Falsas alarmas (512 normales) | No evaluables (1.024) |
| --- | ---: | ---: | ---: | ---: |
| Reglas exactas R | 384 | 128 | 0 | 0 |
| Isolation Forest M | 153 | 359 | 14 | 0 |
| MAD B | — | — | — | 1.024 |
| Híbrido H | 400 | 112 | 14 | 0 |

M detectó 128 de 128 escalados, 3 de 128 eliminaciones de grupo,
16 de 128 redistribuciones y 6 de 128 cambios de un centavo. Con 128
normales bajo desplazamiento, M y H registraron 11 falsas alarmas y R
registró cero. El umbral de M fue 0,631806 y la decisión usó puntuación
estrictamente mayor al umbral.

La calibración de MAD produjo un umbral infinito y el método quedó sin
decisión en los casos de prueba. La tabla preserva esa falta de cobertura.

En la semilla principal, H aumentó la sensibilidad en **3,13 puntos
porcentuales** y la tasa de falsas alarmas en **2,73 puntos** frente a R.
Los objetivos habían fijado un aumento de sensibilidad de al menos cinco
puntos y un aumento de falsas alarmas de hasta dos puntos. Las semillas
23 y 71 también quedaron fuera de ambos objetivos. Las ventanas de
incertidumbre por caso y los resultados por fallo están en el informe.

## Costo en el wheel 0.14.0

El ensayo pareado usó 16 entradas normales capturadas en Pandas, con tres
repeticiones por entrada. La mediana del costo de perfil más inferencia
individual fue **1,914 s**. La comparación exacta de las mismas salidas
materializadas tuvo una mediana de **0,200 s**. Perfil más inferencia fue
más rápido en **0 de 48** pares. Las mediciones excluyeron la ejecución
nativa y la generación del esperado en ambas rutas.

La inferencia sola tuvo una mediana individual de **1,806 s**. La
inferencia en lotes de 16 promedió **0,090 s por perfil** al dividir la
mediana del tiempo por lote entre 16. Cada bloque mide una modalidad
distinta en el mismo equipo. [Mediciones pareadas](../validation/library_detection/results/public-spending-0140/cost.json)

## Alcance

Las mediciones corresponden a un corte de datos públicos, un flujo de filtro y
agregación, cuatro fallos de ETL controlados y un entorno Windows. Los conteos
se reconciliaron sobre 3.456 filas puntuadas correspondientes a tres semillas
sobre los mismos casos. El [estudio del perfil experimental 1.2](public-spending-evaluation.md)
mantiene la identidad del wheel `0.15.0.dev1` y su extensión de severidad.

## Reproducción

Instala el wheel identificado con los extras `engines,ml` en un entorno
fuera del árbol fuente y usa las versiones de dependencias del protocolo.
El directorio de modelos es local y privado.

```sh
python -E validation/library_detection/runtime_receipt.py /private/equiframe-0.14.0-py3-none-any.whl > /private/runtime.json
python -E validation/library_detection/public_spending.py --baseline-only \
  --wheel /private/equiframe-0.14.0-py3-none-any.whl --runtime-receipt /private/runtime.json \
  --csv-dir /original/csv --output /new/primary --cost-model-dir /private/frozen
python -E validation/library_detection/verify_spending.py --primary /new/primary
python -E validation/library_detection/spending_cost.py --csv-dir /original/csv \
  --primary /new/primary --models /private/frozen --output /new/cost
```
