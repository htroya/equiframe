# Resultado de trazabilidad por opción: 51,25 %

Fecha: 2026-10-10. Meta de 50 % alcanzada para el **inventario del núcleo A12**:
**4.296 / 8.383 = 51,24657 %**. El [JSON agregado](OPTION_TRACEABILITY_RESULT_20261010.json)
publica identidades, denominadores, entornos y límites. El
[plan](OPTION_TRACEABILITY_PLAN_20261010.md) y la
[guía de reproducción](OPTION_TRACEABILITY_20261010.md) acompañan el resultado.

El 5,16 % de la captura no tenía una matriz identificada que pudiera reproducirse
en Git o en los recibos examinados. No se inventa su numerador, ni se presenta una
mejora numéricamente comparable desde ese valor. El nuevo índice conserva todo el
inventario descubierto del wheel, identificado por su commit y SHA-256.

## Qué acredita el porcentaje

Se añadieron **3.443 casos sintéticos distintos** con entradas, expectativas
explícitas y enlaces a las filas exactas que prueban. Cubren construcción,
serialización, conservación de campos, defaults declarados, omisión obligatoria
y rechazos de tipos JSON incorrectos en 191 modelos públicos. La selección de
una semilla o la inspección de una firma nunca se contabiliza como un PASS.

| Estado de la obligación | Filas | Significado |
|---|---:|---|
| PASS | 1.741 | Expectativa explícita satisfecha |
| EXPECTED_REJECTION | 2.555 | Entrada incorrecta rechazada según el contrato |
| NOT_RUN | 4.087 | Falta un recibo que pruebe esa obligación |
| FAIL | 0 | Ningún fallo en el catálogo final |
| Total | 8.383 | Denominador completo y fijo |

Los 3.443 casos tienen 1.666 PASS y 1.777 EXPECTED_REJECTION. Un caso puede
probar obligaciones solapadas, como «entrada inválida» y «clase de tipo incorrecto»;
4.296 filas no son 4.296 pruebas independientes. Los rechazos no significan que
el SDK haya aceptado o procesado datos inválidos.

| Superficie inventariada | Con recibo | Pendiente | Total |
|---|---:|---:|---:|
| Construcción de exports/API de modelos | 191 | 226 | 417 |
| Campos y alternativas de metadatos | 4.105 | 1.551 | 5.656 |
| Parámetros de funciones/constructores/métodos | 0 | 1.754 | 1.754 |
| Métodos públicos | 0 | 152 | 152 |
| Propiedades calculadas | 0 | 102 | 102 |
| Comandos CLI | 0 | 30 | 30 |
| Opciones CLI | 0 | 238 | 238 |
| Perfiles de dependencias y requisitos | 0 | 34 | 34 |

Hay tests previos para varias de esas superficies. Aquí permanecen pendientes
porque no se les atribuye cobertura por opción sin el enlace y recibo que exige
este índice. El benchmark separado no entra en este denominador.

## Desarrollo y validación

`option_trace.py` verifica el wheel instalado, vuelve a descubrir la superficie,
comprueba el denominador y los enlaces y produce recibos con esperado, observado,
caso, hash de entrada, versión y entorno. Rechaza JSON ambiguo, enlaces ajenos,
duplicados, candidatos distintos y reutilización de resultados. Un fallo prevalece
sobre otro PASS de la misma opción. El gate conserva su efecto con Python `-O`.

Se corrigió además un defecto de `option_inventory.py`: las rutas Windows con
`\` provocaban un rechazo de identidad aunque todos los bytes coincidieran con
el wheel. La comparación del inventario de módulos usa ahora rutas POSIX; los
controles de archivos alterados o sobrantes siguen rechazando la instalación.

Validación final:

- **3.485 tests focales PASS**: 3.444 del catálogo/identidad, 21 del ejecutor y
  20 del inventario. No se presenta como ejecución completa de toda la suite.
- **Windows x64, Python 3.12.4**: instalación normal del wheel, `pip check` y
  3.443 casos tanto normal como optimizado; ambas ejecuciones dan 4.296/8.383.
- **VM Linux ARM64, Python 3.10.12**: instalación base normal, `pip check` y
  el mismo catálogo normal y optimizado, con el mismo resultado.
- Tres controles negativos bajo `-O`: esperado deliberadamente falso conserva
  FAIL/salida 1; otro candidato se rechaza; un destino existente se rechaza con
  salida 2 y conserva íntegro su recibo anterior.
- Ruff/formato PASS, mypy sobre 78 archivos fuente PASS y 67 activos/esquemas
  comprobados sin reescribirlos. Wheel/sdist válidos y reconstrucción desde sdist.
- El wheel reconstruido es **byte idéntico** al A12 instalado. El nuevo sdist
  incluye las herramientas y el catálogo sintético. Las fixtures históricas
  y los formatos científicos no se modifican; reglas `-text` específicas conservan
  los bytes identificados del catálogo nuevo también en Windows.

Los intentos preliminares conservaron 38 y 8 fallos de preparación del catálogo:
predicciones de default bajo otro estado de campos y expectativas demasiado
estrechas para validadores declarados. Se corrigieron las entradas/precondiciones
o se dejó la obligación pendiente. Ninguno se convirtió en un PASS ficticio ni
se cambió el SDK para admitir una entrada inválida. La colección preliminar de
semillas no acredita una ejecución del producto.

## Qué quedó desplegado en la VM

En `/home/hernan/equiframe-trazabilidad-a12-20261010` quedan el entorno aislado
`runtime`, el kit manual identificado, inventario, matriz completa y recibos de
las ejecuciones normal y optimizada. Sirve para repetir esta auditoría del SDK
instalado y contrastarla con Windows. No crea servicios, recursos de pago ni
ejecuciones Actions, y no administra el DW de otros integrantes.

## Qué falta

Las **4.087 obligaciones NOT_RUN** necesitan casos y recibos propios: más valores
finitos, límites y clases, defaults con contextos adicionales, miembros de
colecciones, efectos de parámetros de API, métodos, salidas calculadas, CLI y
disponibilidad de dependencias. También faltan matrices de interacciones entre
opciones, más entornos y el inventario separado del benchmark.

Este 51,25 % es trazabilidad del contrato de metadatos dentro del inventario del
núcleo. No significa 51,25 % de líneas ejecutadas, efectos nativos demostrados,
combinaciones posibles ni aprobación científica. No recalcula Universalidad,
Usabilidad, licencia ni preparación de publicación pública.
