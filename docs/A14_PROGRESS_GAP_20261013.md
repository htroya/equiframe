# Brecha para el objetivo del 90 %

Corte del 13 de octubre de 2026. EquiFrame continúa en Alpha privada A14.
Esta tabla calcula la distancia desde las últimas mediciones acreditadas;
no atribuye esas mediciones a A14 ni declara obtenida la nueva meta.

| Indicador solicitado | Última medición | Versión evaluada | Brecha hasta 90 % |
|---|---:|---|---:|
| Universalidad | 80,00 % | A11 | 10,00 puntos |
| Preparación PyPI | 80,00 % | A13 | 10,00 puntos |
| Documentación | 90,00 % | A13 | 0,00 puntos; revalidar A14 |
| Trazabilidad | 75,24 % | A13 | 14,76 puntos |
| Calidad del paquete, rúbrica propia | 80,00 % | A13 | 10,00 puntos |
| Madurez | 68,75 % | A13 | 21,25 puntos |
| Requisitos de tesis | 40,91 % | A13 | 49,09 puntos |

Promedio simple de estos siete porcentajes: **73,56 %**. Brecha media:
**16,44 puntos porcentuales**. Se calcula con los valores publicados
redondeados; alcanzar un promedio no satisface la meta individual por área.

El promedio histórico de ocho indicadores es **75,82 %** porque incluye
usabilidad, 91,67 % A13. Su brecha media frente a 90 % es 14,18 puntos.
Si los siete solicitados llegaran exactamente a 90 % y usabilidad conservara
su medición histórica, el promedio de ocho sería 90,21 %; ese cálculo tampoco
constituye una acreditación A14.

## Trabajo cuantificable con las rúbricas originales

| Área | Acreditado | Mínimo entero para al menos 90 % | Adiciones necesarias |
|---|---:|---:|---:|
| Trazabilidad | 6.309 / 8.385 obligaciones | 7.547 / 8.385 = 90,01 % | 1.238 obligaciones |
| Madurez | 11 / 16 criterios | 15 / 16 = 93,75 % | 4 criterios |
| Tesis | 9 / 22 requisitos | 20 / 22 = 90,91 % | 11 requisitos |

Se conserva el denominador original. Una prueba ejecutada, una repetición,
un motor o una plataforma adicional no equivalen automáticamente a una nueva
obligación de trazabilidad. No se dispone todavía de una velocidad de cierre
validada para estimar horas o días hasta completar todas las áreas.

## Reparto nuevo por instrucción del propietario

El [método prospectivo A14](A14_TECHNICAL_90_METHOD_20261013.md) usa
`90 × fracción técnica acreditada + 10 × fracción humana acreditada` por área.
Las [entregas humanas](HUMAN_REQUIREMENTS_20261012.md) pesan en conjunto el
10 % de su área; la [configuración de TestPyPI](TESTPYPI_PUBLISHER_PREPARATION_20261013.md)
se prepara sin ejecutar construcción, publicación o instalación.

Con el bloque humano pendiente, obtener 90 % exige completar el 100 % del
bloque técnico. La tabla histórica no se convierte multiplicando por 0,9
porque usa otra rúbrica. La puntuación A14 permanece pendiente de la evaluación
completa, incluido el expediente científico que depende de datos aprobados.

Para trazabilidad, si se conserva el inventario de 8.385 obligaciones como
bloque técnico, completar ese bloque desde las 6.309 históricas exige **2.076
obligaciones** más y su validación sobre A14. Las 1.238 de la tabla anterior
son la distancia al umbral del 90 % de la rúbrica original. La asignación del
10 % a revisión humana no convierte casos técnicos sin ejecutar en completados.

Fuentes de partida: [matriz de ocho indicadores](PROJECT_STATUS_MATRIX_20261011_EIGHT.md),
[trazabilidad más reciente](OPTION_EXCEPTIONS_RESULT_20261012.md),
[madurez](MATURITY_SCOPE_REASSESSMENT_20261012.md) y
[requisitos de tesis](THESIS_CURRENT_RESULT_20261011.json).
