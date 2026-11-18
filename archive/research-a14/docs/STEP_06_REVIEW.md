# Entrega del paso 6

Fecha: 2026-10-01. Núcleo `equiframe 0.5.0`; distribución nueva
`equiframe-benchmark 0.6.0`. El DOCX conserva el hash registrado en
[trazabilidad](THESIS_TRACEABILITY.md). Diseño, relación con objetivos y
reorientación: [STEP_06_DESIGN.md](STEP_06_DESIGN.md).

## Resultado de ingeniería

Se implementó el catálogo de cinco familias, esperados manuales, candidatos,
paquetes de revisión con entradas y nombres neutros, asignación de revisores,
oráculo independiente, desacuerdos, grupos transitivos, particiones reproducibles
y selección de entrenamiento normal ligada a las capturas del paso 5.
Se publican diez esquemas JSON y un piloto ejecutable desde la distribución.

Se conservó y completó el código inicial sin registrar que ya existía en
`feat/step-6-benchmark`. Se corrigieron la ausencia de entradas en escenarios,
filtración de motor/mutación por nombres de archivos, huella de contrato usada
como si fuera huella de R, falta de revalidación de modelos y vinculación
insuficiente entre perfil y ejecución. No se modificó código operacional de
los pasos 1 a 5 ni carpetas de José/Jhair.

## Comprobaciones ejecutadas localmente

Windows x64, Python 3.12.4. Dependencias reproducibles en el lock de cada paquete.

| Comprobación | Resultado |
|---|---|
| Suite del núcleo existente | 596 aprobadas |
| Suite final del benchmark contra wheel instalado fuera del checkout | 72 aprobadas |
| Total entre ambas suites | 668 aprobadas |
| Ruff y formato del benchmark | Correctos |
| Mypy estricto | Correcto, 12 archivos fuente/herramientas |
| Esquemas generados | 10 comprobados |
| Wheel y sdist | Construidos correctamente |
| Instalación por nombre con pip, índices deshabilitados y wheels locales | `equiframe==0.5.0` y `equiframe-benchmark==0.6.0`, correcta |
| `pip check`, imports ligeros y ubicación de paquetes | Correctos |
| Piloto completo desde wheel instalado | Correcto, tres motores reales |
| Reconstrucción del wheel desde sdist | Mismos bytes y SHA-256 |

Se ejecutó también la suite del benchmark en desarrollo (69 pruebas antes de
añadir tres regresiones de integridad). La primera prueba de consumidor falló
por permisos de una carpeta temporal heredada de pytest, antes de evaluar los
casos. El verificador usa ahora `--basetemp` dentro de su directorio propio;
la repetición completa final aprobó las 72 pruebas. No se confunde ese fallo
de entorno con una divergencia tabular.

Los comandos reproducibles están en el [README del paquete](../packages/equiframe-benchmark/README.md).
`tools/verify_distribution.py` instala dependencias bloqueadas, instala ambos
wheels mediante **pip**, ejecuta pruebas/piloto desde otro directorio y reconstruye
desde sdist. No usa `sys.path` ni imports desde el checkout para el consumidor.

| Artefacto local | SHA-256 |
|---|---|
| `equiframe_benchmark-0.6.0-py3-none-any.whl` | `57b124781b82622496bef92bf8f433bb7828ba4f3978d4175e362eebc2876318` |
| `equiframe_benchmark-0.6.0.tar.gz` | `cfcfc26dd8408841bd65e9e07301f26c7bc3df77812f471781d3680a7a55aba1` |

## Cantidades reales del piloto

| Familia | Entrenamiento | Calibración | Prueba | Candidatos | Perfiles nativos | Revisiones pendientes |
|---|---:|---:|---:|---:|---:|---:|
| Nulos y tipos | 1 | 0 | 0 | 7 | 3 | 7 |
| Uniones | 0 | 0 | 1 | 7 | 3 | 7 |
| Duplicados y orden | 1 | 0 | 0 | 7 | 3 | 7 |
| Agregaciones | 0 | 1 | 0 | 7 | 3 | 7 |
| Fechas | 0 | 0 | 1 | 7 | 3 | 7 |
| Total | 2 | 1 | 2 | 35 | 15 | 35 |

Particiones por **escenario**, semilla 6, pesos 3/1/2. Hay cuatro grupos:
uno de entrenamiento (nulos/tipos y duplicados comparten origen/plantilla),
uno de calibración y dos de prueba. Candidatos/perfiles por partición:
14/6, 7/3 y 14/6 respectivamente. Las variantes no aumentan grupos.

Comparaciones completas: 25 equivalentes y 10 diferentes. Efectos observados
de mutaciones: 10 con cambio y 5 sin efecto. Se ejecutaron tres controles
nativos y un control de permutación por familia. Las mutaciones operan sobre
artefactos y no se presentan como ETL nativos ni perfiles nuevos.

Etiquetas científicas confirmadas: **cero**. Acuerdo entre revisores: **no
calculable**, denominador cero. Las revisiones ficticias de tests prueban el
protocolo, no aprueban casos reales. Ninguna familia tiene soporte repartido
entre ajuste y calibración; este piloto no permite entrenar/calibrar modelos
por familia ni demostrar las hipótesis de la tesis.

## Publicación y límites

La CI se amplió para ejecutar núcleo y benchmark en Windows x64, Linux
x64/ARM64 y macOS x64/ARM64. Su resultado remoto se registra después de
publicar; la configuración por sí sola no demuestra compatibilidad.

La entrega solicitada es publicación del código en Git. No es una publicación
en PyPI ni despliegue OCI. El objetivo público `pip install equiframe` conserva
pendientes licencia, control/disponibilidad del nombre y publicación verificable.
La instalación por nombre comprobada en esta entrega usa wheels locales.

La ingeniería del paso 6 queda implementada. Quedan pendientes el cierre humano
del catálogo, ampliar grupos independientes, escenarios reales SERCOP y el
FreezeManifest experimental final. IF/MAD/H, orquestación, integración y métricas
permanecen en los pasos 7 a 10. A55–A62 documentan los motivos y consecuencias.
