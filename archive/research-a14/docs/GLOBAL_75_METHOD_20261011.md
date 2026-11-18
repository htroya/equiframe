# Método del promedio global solicitado

El 11 de octubre de 2026 el usuario eligió expresamente **el promedio de las
nueve áreas**, frente a exigir un mínimo del 75 % en cada una. Se fija desde
este corte `GLOBAL-NINE-EQUAL-v1`, como indicador propio de seguimiento.

```text
porcentaje_global = suma(100 × aprobados_i / total_original_i) / 9
```

Cada área pesa exactamente 1/9. El cálculo usa fracciones sin redondear antes
de promediar y presenta dos decimales al final. La meta se evalúa sobre el
valor exacto, no sobre el texto redondeado.

| Área | Denominador conservado |
|---|---:|
| Usabilidad | 12 |
| Universalidad | 60 |
| Preparación PyPI | 20 |
| Documentación | 20 |
| Trazabilidad | 8.385 |
| Calidad propia | 20 |
| Madurez | 16 |
| Requisitos de tesis | 22 |
| Preparación de seguridad | 20 |

Las rúbricas de cada área siguen vigentes. No se reducen sus denominadores,
eliminan áreas bajas, conceden puntos parciales nuevos ni cuentan repeticiones.
Una fuente desconocida, inconsistente o sin identidad impide emitir el índice;
no se sustituye por una cifra favorable.

El [instrumento reproducible](../tools/measure_global_progress.py) recibe una
matriz consolidada revisada y comprueba los nueve IDs únicos, los hashes de
sus fuentes, sus numeradores/denominadores y sus candidatos. Rechaza booleanos
como conteos, identidades ausentes, candidatos trasladados y fuentes ajenas al
repositorio. La matriz de entrada se elige explícitamente: el instrumento no
busca automáticamente el documento más reciente.

```powershell
python tools/measure_global_progress.py --matrix docs/PROJECT_STATUS_MATRIX_20261011_GLOBAL75.json --repo . --output global-result-new.json
```

El resultado requiere un nombre nuevo para conservar recibos anteriores.
El [resultado de este corte](GLOBAL_75_RESULT_20261011.json) identifica la
matriz y herramienta ejecutadas. Las pruebas incluyen intentos de omitir áreas,
duplicarlas, cambiar denominadores, falsificar conteos/identidades y alterar
fuentes conservando su hash anterior.

Este promedio corresponde a **los últimos registros por área**. Usabilidad
conserva A12 y universalidad A11 mientras sus reevaluaciones A13 completas sigan
pendientes. No constituye una evaluación integral del candidato A13 ni una
certificación. Si una nueva evaluación válida reduce una cifra, el promedio
también debe reflejarlo.

Un promedio del 75 % no significa 75 % en cada área, aprobación de la tesis,
seguridad garantizada ni autorización para publicar. Las puertas de derechos,
revisión humana, ciencia, distribución y plataformas mantienen su criterio
propio. Los informes anteriores, que no definían un agregado, se conservan como
históricos; este método no se les atribuye retrospectivamente.
