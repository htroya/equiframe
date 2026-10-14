# Avance comprobado hacia el cierre A14

EquiFrame continúa en Alpha privada A14. Este registro acredita sólo los
recibos indicados; el 90 % de los siete rubros y su promedio siguen pendientes.
Se conserva el [reparto de 90 puntos técnicos y diez manuales](A14_TECHNICAL_90_METHOD_20261013.md).

## Trazabilidad del candidato identificado

Fuente del núcleo: `486a0be91d4dd75bb258c6afa6ca2c8d768e6cbf`.
Wheel privado: `equiframe-0.12.0a14-py3-none-any.whl`, SHA-256
`1c37dec3906099a182a877b8d7b5f6a7850706b5ad2c4992bececd30984004b0`.

La consolidación `root-consolidated-486a0be-v1.json` comprueba normal y `-O`,
identidad del wheel, catálogos congelados y ausencia de IDs superpuestos:

| Bloque | Obligaciones acreditadas |
|---|---:|
| Inventario raíz reejecutado | 6.201 / 8.438 |
| Contextos de campos acoplados | 307 adicionales |
| Almacén local de artefactos | 33 adicionales, once casos por modo |
| Constructores de contratos | 89 adicionales, 67 casos por modo |
| Namespace EDA separado | 704 / 704 |
| Total consolidado | **7.334 / 9.142** |

Quedan **1.808 obligaciones**: 1.242 de parámetros, 123 de API, 51 de métodos,
73 de campos, 70 de propiedades, 34 de CLI, 175 de opciones CLI, 18 de extras
y 22 de dependencias. Son **72,200831 puntos** con el bloque manual pendiente;
faltan **17,799169 puntos** para 90 en trazabilidad. Las 8.438 originales y las
704 EDA se conservan explícitamente; no se reduce el denominador ni se cuentan
repeticiones como nuevas obligaciones.

Los [casos del almacén](../tools/revalidate_artifact_runtime.py) comprobaron
conservación de bytes/hash/formato, publicación exclusiva y tipos inválidos.
Los [constructores](../tools/revalidate_contract_runtime.py) comprobaron esquema,
claves, orden, políticas, procedencia, defaults y rechazo de tipos o alternativas
inválidas. Sus expectativas se congelaron antes de ejecutar el SDK.

## Pruebas instaladas y consumidor

En Linux ARM64/Python 3.12.15, el wheel `486a0be` registró:

| Suite | Aprobadas | Omitidas | Fallidas/errores |
|---|---:|---:|---:|
| Núcleo completo | 8.193 | 13 | 0 |
| Benchmark completo | 636 | 3 | 0 |
| Datos y herramientas de tesis/DW | 175 | 0 | 0 |
| Copia/ejecución local/lecturas protegidas | 163 | 11 | 0 |

La instalación privada resolvió dependencias normalmente desde el repositorio
local congelado y pasó `pip check` y la vinculación del contenido instalado.
El primer intento con Python del sistema/pip antiguo se conserva como fallo de
preparación; los resultados anteriores pertenecen al segundo intento con 3.12.

En Windows, `486a0be` pasó 154 pruebas focalizadas con 20 omisiones, doce
regresiones conocidas, los ocho ejemplos documentales y los seis artefactos en
`twine check --strict`. Su suite completa aún requiere un recibo propio.

El candidato anterior `fc7a676` terminó su suite completa de Windows con 8.152
aprobadas/40 omitidas del núcleo y 632 aprobadas/siete omitidas del benchmark.
El consumidor privado 0.1.16, ligado a ese wheel y al benchmark exacto, pasó
72 casos normales y 72 optimizados: por modo, 24 aceptaciones, 48 rechazos
esperados y 144 ejecuciones nativas registradas. También pasaron las pruebas de
fallos y dominios. El consumidor original 0.1.15 y sus oráculos permanecen intactos.
Estos recibos no se trasladan a un wheel posterior.

## Controles técnicos de tesis

`sercop-preparation-486a0be-v1` se regeneró con el wheel identificado y el
snapshot público SHA-256
`80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3`.
El verificador volvió a calcular 216 perfiles, reglas y comparaciones: 108
equivalentes y 108 diferentes. El snapshot original no cambió. El recibo
`sercop-verification-486a0be-v1/verification.json` tiene SHA-256
`7f7abde7ed70a9ce5282ab27a83b57bfe470f5ac4f7ad4b53eccd4a21499b1cf`.

La [auditoría de selección](../tools/audit_thesis_selection.py) ejecutó las seis
barreras de entrenamiento/calibración sobre evidencia real preparada. Rechazó
la selección sin O confirmado y la entrada desde otra partición. No asignó
etiquetas ni ajustó modelos. Cada familia contiene 36 ejecuciones de control,
doce por motor, pero sólo un vector numérico distinto. El catálogo conserva un
único componente transitivo y doce escenarios de entrenamiento por familia,
sin soporte de calibración/prueba. **N_fit acreditado: cero**, por familia.

Estos resultados acreditan preparación y barreras técnicas. Faltan un corpus
efectivo confirmado suficiente, particiones viables, entrenamiento/calibración,
soportes pareados y evaluación final. No se convierten automáticamente en los
diez puntos manuales ni acreditan una conclusión científica.

## Lectores públicos en corrección posterior

La revisión de código identificó lecturas directas sin presupuesto en
`read_comparison`, `read_rule_evaluation` y `read_diff_contract`. La corrección
actual usa lectura de archivos regulares, inspección de ancestros antes de
normalizar navegación local y límite de 64 MiB, manteniendo validación JSON
estricta. Se añadieron regresiones de FIFO, directorios, enlaces/junctions y
manifiestos sobredimensionados. La validación de fuente registró **203 aprobadas,
21 omitidas y cero fallos**, junto con tipado, Ruff, arquitectura y 71 activos
aprobados. Su candidato instalado propio continúa pendiente; no se suman al
recibo de `486a0be`. El primer chequeo detectó el catálogo derivado desactualizado;
se conserva el fallo y la repetición después de actualizarlo.

El catálogo actual de reglas incorpora las nuevas huellas de implementación
derivadas del cambio en `rules.py`. Los algoritmos de reglas, esquemas históricos,
catálogos de oráculos congelados y evidencias anteriores se conservan.

No se usó Codex Security ni se crearon agentes. No se publicó en PyPI/TestPyPI
ni se ejecutaron Actions. El Word, los datos compartidos y el servicio de la
tutora no se modificaron. La solicitud a Robot continúa condicionada a acreditar
los siete rubros al 90 % y subir el corte correspondiente.
