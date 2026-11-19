# Isolation Forest sobre importes públicos: evidencia y límites

Evaluación del 19 de noviembre de 2026, independiente de la entrega de un DW o
portal. La versión publicada en PyPI sigue siendo **0.14.0, Beta pública**.
Las nuevas características 1.2 se midieron en un **candidato local experimental
0.15.0.dev1**. Esa denominación no anuncia una publicación en los índices.

## Para qué sirve

Un informe puede conservar su total y asignar parte del dinero a la entidad
equivocada. Este ejemplo permite estudiar ese problema al migrar una consulta
entre Pandas, Polars y DuckDB. El objetivo es conservar los importes por entidad
y moneda que utiliza un informe de contratación pública. Los fallos se introducen
de forma controlada en las transformaciones; no son hallazgos sobre personas,
proveedores ni decisiones de contratación.

La consulta selecciona adjudicaciones de al menos 100 unidades monetarias
originales y suma sus importes por comprador y moneda. El umbral pertenece al
experimento, sin significado legal. No se convierten monedas ni se rellena un
importe ausente con cero. Se usan enteros en centésimas, obtenidos de decimales.

## Datos y separación de información

La fuente es la exportación pública SERCOP–OCDS de 2025, con publicación y
selección documentadas en el protocolo. De 183.891 adjudicaciones se excluyen
14.363 por fecha de publicación fuera de 2025, tres por comprador o moneda
ausente y una por importe ausente entre los registros restantes. Quedan 169.524
adjudicaciones de 168.796 procedimientos.

La partición asigna procedimientos completos mediante SHA-256 a entrenamiento,
desarrollo, calibración y prueba: 40/10/20/30 por ciento de asignación. No comparte
procedimientos entre particiones. Las entidades pueden repetirse. Cada fragmento
tiene al menos 32 adjudicaciones, dos grupos de salida y una moneda. Los datos
originales no se incluyen en el repositorio; el protocolo identifica los archivos
y el código documenta la descarga y selección. Véase la [ficha de la fuente](../validation/library_detection/README.md).

Se mantienen separados:

- **R**: conservación del total seleccionado y unicidad de comprador/moneda,
  controles globales parciales que no verifican cada importe por entidad.
- **M**: Isolation Forest sobre el perfil de la propia entrada y salida.
- **B**: MAD sobre la misma representación, con disponibilidad explícita.
- **H**: OR de R y M, una política de alertas.
- **O**: esperado independiente en Python, con diccionarios y suma entera.

Cada salida real capturada se coteja por valores completos con O y se compara
también mediante EquiFrame. Etiquetas, nombres de fallos, esperado y salidas de
otros motores quedan fuera de los predictores. Los índices de filas de Pandas
se ignoran con justificación expresa: la identidad de negocio está en las columnas.

## Protocolo congelado y tamaño real

Se ejecutaron 256 casos normales de entrenamiento, 64 de desarrollo y 256 de
calibración en Pandas. La prueba tiene 512 casos correctos, 512 con fallos y
128 correctos de mayor tamaño, ejecutados en los tres motores. En total son
**1.728 casos, 4.032 ejecuciones nativas y 1.152 casos únicos de prueba**.
Tres motores, dos representaciones y tres semillas no multiplican la muestra
independiente. Las 6.912 filas de puntuaciones son registros de esos mismos casos.

Los cuatro fallos tienen 128 casos cada uno: eliminar un grupo, duplicar su
importe, redistribuir una unidad entre dos grupos manteniendo el total y añadir
una centésima. La etiqueta se confirma con el resultado real, no con el nombre.
La prueba principal registra acuerdo de huellas entre motores como control de
identidad; el juicio de cada salida usa comparación de valores con O. No se
presenta ese acuerdo de huellas como comparación directa de valores entre pares.

Se usan 200 árboles y submuestras de 256 perfiles; semilla principal 7, con 23 y
71 para sensibilidad. Entrenamiento y calibración son exclusivamente normales.
El umbral es el cuantil 0,95 de 256 puntuaciones normales de calibración y la
alerta exige puntuación estrictamente superior. No se reajusta tras ver prueba.

La representación 1.1 combina tamaño, razón de filas y cuatro medidas agrupadas.
La 1.2 añade media y varianza poblacional de diferencias relativas por grupo:
`d = abs(salida - entrada) / abs(entrada)`, sobre grupos comunes con base válida
distinta de cero. Bases cero y grupos ausentes conservan categorías separadas.
Se mantiene la aritmética racional hasta convertir a números para el modelo.

## Resultados principales, semilla 7

El denominador es de 512 salidas incorrectas y 512 correctas.

| Método | Detectados | Omitidos | Falsas alertas | Sensibilidad | Falsas alarmas |
| --- | ---: | ---: | ---: | ---: | ---: |
| R global | 384 | 128 | 0 | 75,00 % | 0,00 % |
| M, perfil 1.1 | 153 | 359 | 14 | 29,88 % | 2,73 % |
| H, perfil 1.1 | 400 | 112 | 14 | 78,13 % | 2,73 % |
| M, perfil 1.2 | 146 | 366 | 17 | 28,52 % | 3,32 % |
| H, perfil 1.2 | 396 | 116 | 17 | 77,34 % | 3,32 % |

MAD tuvo umbral de calibración infinito y cobertura cero: se conserva como
**no evaluable**, sin convertir sus ausencias en aciertos. En los 128 casos
correctos de mayor tamaño, M con ambas representaciones alertó 11 veces (8,59 %).

H añadió 3,13 y 2,34 puntos porcentuales de sensibilidad frente a R global,
con 2,73 y 3,32 puntos adicionales de falsas alarmas. No alcanzó los criterios
planteados de al menos cinco puntos de detección adicional y como máximo dos
de falsas alarmas adicionales. La ampliación 1.2 no mejoró el resultado agregado.
Los intervalos y las tres semillas permanecen en los informes, incluidos los
resultados desfavorables. Sus intervalos son condicionales al modelo y al corte;
no representan independencia entre todas las entidades de contratación pública.

## Extensión de severidad y control más fuerte

Antes de puntuar la prueba principal se registró una extensión con 64 fragmentos
fuente nuevos. Cada uno recibe cinco variantes emparejadas: correcta y
redistribuciones de una centésima, 1 %, 10 % y 50 % del menor importe afectado.
Son **64 fuentes, 320 variantes y 960 ejecuciones nativas de prueba**. Otras
512 ejecuciones reconstruyen entrenamiento/calibración y no son nuevos casos.
Los modelos reconstruidos coinciden con las huellas de los modelos principales.

Esta extensión coteja directamente las filas completas y los objetos de perfil
entre los tres motores antes de reunir resultados. No utiliza solo huellas.
La regla más fuerte aplica el filtro declarado a la entrada y compara exactamente
las sumas de cada entidad y moneda.

| Condición, 64 casos por fila | M 1.1 detectados | M 1.2 detectados | Regla por grupo detectados |
| --- | ---: | ---: | ---: |
| Redistribución de una centésima | 12 | 8 | 64 |
| Redistribución del 1 % | 13 | 11 | 64 |
| Redistribución del 10 % | 33 | 44 | 64 |
| Redistribución del 50 % | 64 | 64 | 64 |

M emitió dos y tres falsas alertas sobre los 64 casos correctos. La regla por
grupo detectó los 256 errores sin falsas alertas en esos 64 casos. **El aumento
frente a reglas parciales no acredita superioridad frente al control exacto**.
El remuestreo conserva juntas las variantes de cada fragmento; no se usan
intervalos binomiales agrupados como si fueran 256 fuentes independientes.

El registro de recorridos reconstruye puntuaciones desde los 200 árboles del
primer fragmento fijado, sin seleccionarlo por sus alertas. Con perfil 1.1 se
obtuvieron 0,407713; 0,591946; 0,606734; 0,641344 y 0,752677 para las cinco
condiciones, frente al umbral 0,631806. Los recorridos reproducen las puntuaciones
de la API con tolerancia 1e-12. Demuestran uso real del bosque, sin interpretar
su puntuación como probabilidad o explicación causal.

## Costo observado

La medición repetida posterior usó 16 entradas correctas y tres repeticiones,
alternando el orden de operaciones. Reutilizó los modelos, sin refit. Excluyó
por igual ejecución nativa y construcción del esperado. Las 48 observaciones
son 16 entradas repetidas, no 48 entradas independientes.

| Perfil | Perfil + inferencia individual, mediana | Comparación completa, mediana | Pares donde el conjunto fue más rápido |
| --- | ---: | ---: | ---: |
| 1.1 | 662,91 ms | 134,60 ms | 0/48 |
| 1.2 | 631,34 ms | 134,60 ms | 0/48 |

La API individual incluye validación del modelo, preprocesamiento y procedencia;
no mide solo recorridos de árboles. Lotes de 16 perfiles amortizan la inferencia
a 36,06 y 44,72 ms por caso. Esa amortización no es latencia individual ni prueba
superioridad de throughput frente a una comparación completa por lotes no medida.
No se acredita H3 en la modalidad individual, ni se afirma una ventaja universal
de tiempo o memoria. El informe conserva cada par medido.

## Identidad, reproducción y límites

El wheel experimental medido tiene SHA-256
`1bdcdfaec39f1a5508e2b0064ad88804b0af703dab2854ff83bcd578b20b7fbe`.
El protocolo enumera las huellas de sus 177 archivos de paquete y de los scripts.
El campo de productor del modelo conserva el valor base 0.14.0 de esa rama; no
identifica por sí solo este candidato. La versión de distribución, las huellas
del código y el wheel identifican la ejecución experimental. Una corrección
posterior del registro de compatibilidad revisa únicamente los mismos enums
ampliados y no cambia bosques, puntuaciones, fórmulas o artefactos históricos.

Código: [consulta principal](../validation/library_detection/public_spending.py),
[severidad y recorridos](../validation/library_detection/spending_severity.py),
[costo](../validation/library_detection/spending_cost.py),
[reconciliación independiente](../validation/library_detection/verify_spending.py).
Los protocolos, decisiones y registros numéricos se distribuyen comprimidos en
`validation/library_detection/results/public-spending-20261119`; el manifiesto
registra huellas de archivos comprimidos y originales. No se publican datos fuente
ni modelos ajustados. Las instrucciones de reproducción figuran en el README de
esa carpeta.

Este es un corte anual y una consulta con fallos dirigidos, sobre fragmentos
pequeños. No acredita producción, ausencia universal de defectos, revisión humana,
ni eficacia sobre todas las familias de ETL. La [revisión de antecedentes](research-related-work.md)
delimita la contribución sin afirmar haber inventado Isolation Forest o que no
existan herramientas semejantes. La [guía de fiabilidad](reliability.md) distingue
el veredicto exacto de las señales y políticas estadísticas.
