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

## Corte posterior `8f8138c`: lectores instalados y recuperación

El núcleo corregido se construyó desde
`8f8138c23992b9df6f531036f001f699bfd0743e`. Su wheel tiene SHA-256
`42e636ae3ca38633cd6bc3a19ac24d5f8a39e36fd610427dd34603e6e131edd5`;
su sdist, `3e4435866f5b0f0efe863fb8dbaf4c658afb1c741dae4f03277e97b769628fe3`.
Benchmark y cliente de datos retienen sus artefactos anteriores identificados.

La revalidación normal/optimizada de ese wheel volvió a acreditar **7.334 / 9.142**,
con los mismos 1.808 pendientes. En Linux ARM64 pasó su batería propia: **8.205
aprobadas/16 omitidas** del núcleo, **636/3** del benchmark y **175/0** de datos y
herramientas. La tanda focalizada registró 175 aprobadas/14 omitidas. Cero fallos
y errores en las cuatro tandas. La suite completa Windows sigue en ejecución;
sus comprobaciones de instalación, identidad, documentación, metadatos y
trazabilidad terminaron sin fallos.

`upgrade-rollback-a13-8f8138c-v1` completó cinco etapas privadas: A13 inicial,
actualización A14, reversión A13, nueva actualización A14 y recuperación A14
en otro entorno limpio. Cada etapa resolvió dependencias sin `--no-deps`, pasó
`pip check`, vinculó todos los bytes instalados y comprobó recorridos con salidas
esperadas 0/1/3/2, recuperación del consumidor y CLI benchmark. Todos los
inventarios de evidencia anterior y wheels originales quedaron idénticos. Los
entornos nuevos se conservan; no se modificaron los originales compartidos.

El expediente SERCOP también se regeneró para las nuevas huellas de reglas.
Recalculó 216 perfiles/reglas/comparaciones y pasó de nuevo las seis barreras de
selección. El recibo del verificador tiene SHA-256
`1989b18e281c694068feaead66811ee066c7196460d9132402a54fb3f948dd4c`.
Conserva un componente transitivo, etiquetas pendientes y N_fit acreditado cero.

La auditoría ordinaria `ordinary-audit-8f8138c-v1` consultó las 103 dependencias
públicas exactas: cero vulnerabilidades públicas conocidas en esa consulta.
Bandit conservó **40 advertencias B608** de construcción SQL del núcleo y cuatro
de PRNG/subprocesos del benchmark. `review-dispositions.json` registra las 44
ubicaciones, hashes, razones y límites: identificadores/literales escapados,
valores vinculados, IR validada, PRNG experimental reproducible y ejecución local
de comandos de confianza. No se suprimieron reglas. El cliente y gateway no
registraron advertencias en código de producción; sus pruebas conservaron las
anotaciones de expectativas y casos negativos. El primer escaneo del cliente
usó un directorio `src` inexistente; se conserva como intento no válido y se
repitió sobre su estructura real. No constituye certificación integral ni
acredita ejecución segura de código hostil proporcionado por un usuario.

La revisión detectó una prueba histórica de recuperación del cliente que
capturaba cualquier excepción. La corrección exige `FileNotFoundError`, utiliza
la ruta inexistente de su propio directorio temporal y falla si la entrada se
acepta. Su comprobación focalizada pasó; no modifica el wheel del cliente.

El enlace de la tutora respondió HTTP 200 el 14 de octubre de 2026 a las
07:13:28 UTC. El índice conserva SHA-256
`2bbc4db94ea3ea34ae090f02553438588c37c52414b681bb2a54881c99a2a625`.
No se cambió el servicio ni la entrega pública.
