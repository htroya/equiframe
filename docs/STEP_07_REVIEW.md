# Verificación del paso 7

Fecha: 2026-10-01. Núcleo y benchmark 0.7.0. El paso 6 se integró primero
en `main` mediante [PR 15](https://github.com/htroya/equiframe/pull/15), commit
`e9bbda4`, después de verificar sus dos ejecuciones CI aprobadas para
`652a2d30eab147eb814abbcf215e1f41eed554d9`.

## Alcance implementado

Isolation Forest M, MAD B, calibración normal separada e híbrido H = R OR M.
Una matriz común por familia, medianas congeladas, semilla/configuración,
soporte explícito, cuantiles racionales exactos y estados no estimables.
El benchmark incorpora selección normal de calibración y auditoría de grupos.
Se añaden seis esquemas del núcleo y tres del benchmark; los formatos previos
conservan contenido y significado. [Diseño y reorientación](STEP_07_DESIGN.md),
[uso y límites](DETECTORS.md), decisiones A63–A70.

La fuente de tesis conserva el SHA-256 declarado en trazabilidad. Se revisaron
§1.3, §3.4.3 y §3.6–3.7. No se cambió el DOCX ni se atribuyeron al experimento
las pruebas sintéticas de software.

## Comprobaciones locales ejecutadas

Windows x64, Python 3.12.4, uv 0.11.6. Dependencias de núcleo bloqueadas:
scikit-learn 1.9.1, NumPy 2.5.3, SciPy 1.18.1, Pydantic 2.13.5;
Ruff 0.16.9 y pytest 9.1.1. Cada paquete conserva su propio `uv.lock`.

| Control | Resultado observado |
|---|---|
| Ruff y formato, ambos paquetes | Aprobados |
| mypy estricto | Núcleo 31 archivos; benchmark 13 archivos, sin errores |
| Esquemas/fixtures núcleo | 34 archivos verificados |
| Esquemas benchmark | 13 archivos verificados |
| Suite del núcleo instalada desde sdist/wheel final | **649 passed**, 165,52 s |
| Suite del benchmark en checkout | **86 passed**, 35,32 s |
| Suite del benchmark instalada con pip, después de A70 | **86 passed**, 46,15 s |
| Casos específicos finales de detectores | **53 passed**, 15,02 s |
| Particiones con semilla del fallo corregido | **11 passed**, 10,45 s |
| Distribución del núcleo | Base, arrow, pandas, polars, duckdb, engines y ml aprobados fuera del checkout |
| Reproducción del núcleo | Wheel reconstruido desde sdist idéntico en bytes; consumidor tipado aprobado |
| Distribución del benchmark | pip por nombre para ambos 0.7.0; import ligero, piloto nativo y wheel reconstruido idéntico aprobados |

El contraste M compara contra `-IsolationForest.score_samples` con varias
submuestras y filas repetidas (`rtol=1e-14`). Guardar/restaurar el evaluador
declarativo conserva exactamente sus resultados. B se contrasta con mediana,
MAD y scores esperados manualmente. No se usa el umbral de contamination.

Se verifican igualdad estricta, rango decimal que redondearía erróneamente con
float (`alpha=0.7`, n=10), empates, MAD cero e infinito, indicadores, calibración
insuficiente, datos constantes, pérdida de variación float32 y ausencia de
divisiones en los árboles. H cubre nueve combinaciones y alertas parciales,
incluida integración con una evaluación real de reglas sobre una captura
sintética. Perfiles fallidos o incompatibles generan error, nunca no alerta.

Los ejemplos externos entrenan con `ml` y restauran/puntúan en el entorno base
sin sklearn ni NumPy. Se conservan comprobaciones de import ligero, cada motor,
API/CLI, distribución tipada y no sobrescritura. Los bundles son JSON declarativo
acotado, con integridad externa opcional; no se cargan objetos pickle/joblib.

## Incidencia encontrada durante la verificación

La primera instalación externa del benchmark terminó con 76 pruebas aprobadas
y una interrupción de Hypothesis por generación lenta de conjuntos de
dependencias: 3 entradas válidas en 1,04 s. No reportó un contraejemplo de fuga.
Se sustituyó el generador con rechazo de duplicados por máscaras 1–127, que
conservan todos los subconjuntos no vacíos de siete dependencias. La semilla
registrada pasó después del cambio. Se mantienen los health checks y el
algoritmo de partición. A70 registra motivo y consecuencia.

La repetición externa final aprobó sus 86 pruebas. El piloto instalado produjo
5 escenarios, 35 candidatos, 15 perfiles, 4 grupos, 25 comparaciones equivalentes
y 10 diferentes; 35 revisiones pendientes y cero etiquetas confirmadas. Se
conserva `scientific_freeze_ready=false` y acuerdo de revisores no calculable.

## Artefactos locales

Los artefactos se construyen en `dist/`, excluido de Git. Estos hashes son de
los archivos locales de distribución, distintos del hash semántico de bundles.

| Archivo | SHA-256 |
|---|---|
| `equiframe-0.7.0-py3-none-any.whl` | `bfe69aae56d9256b6499884e57980e10356e3c0896345386e164ee743e7fda15` |
| `equiframe-0.7.0.tar.gz` | `25749052c882bd57bc95f8302f42a008adfb61012d1d51c48fd18f7734de02ad` |
| `equiframe_benchmark-0.7.0-py3-none-any.whl` | `b5533cb99f54e48021c2c369045c9e9d1f7453831c8d1ade3548aebe2e816752` |
| `equiframe_benchmark-0.7.0.tar.gz` | `25ae4f435032f8b69552f077db84a8eeebd0ef5c597bf0f1178d703e381895f7` |

## Límites científicos y de publicación

Se entrega ingeniería local y código en Git. El piloto mantiene 5 escenarios,
4 grupos, 15 perfiles, 35 revisiones pendientes y cero etiquetas científicas
confirmadas. No hay modelo científico entrenado ni tasas de detección/FPR
observadas en SERCOP. Los mínimos de software no resuelven suficiencia
estadística, independencia real o justificación de alpha.

El evaluador JSON no promete rendimiento equivalente a sklearn; H3 requiere
medición controlada posterior. La orquestación completa, informes, integración
OCI/DW y congelación/evaluación permanecen en los pasos 8–10.

`pip install equiframe` desde PyPI sigue pendiente de licencia acordada,
control del nombre y publicación verificable. Instalar por nombre desde wheels
del equipo verifica el empaquetado, no la existencia de una publicación PyPI.
La matriz CI de cinco plataformas se verificará sobre el commit publicado;
su configuración por sí sola no acredita el resultado remoto.
