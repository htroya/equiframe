# Validación nativa tras autorizar la transferencia a la VM

El usuario autorizó expresamente el contenido, destino y pruebas del envío
antes rechazado. Se ejecutaron en `157.137.227.1`, usuario `hernan`, únicamente
en el laboratorio propio `/home/hernan/equiframe-targets-20261011-dFXg80`.
El [recibo estructurado](VM_TARGET_FOLLOWUP_20261011.json) identifica los inputs,
comandos, archivos devueltos, hashes y límites. La [matriz vigente](PROJECT_STATUS_MATRIX_20261011_VM.md)
incorpora este resultado y conserva el corte anterior como histórico.

## Lo ejecutado y verificado

El archivo autorizado se actualizó con las herramientas finales publicadas en
`47941c9`; el original preparado se conservó. La transferencia SCP terminó
correctamente y la VM verificó SHA-256
`0c798b543169e3c9129302dc200c06e58119f78c6c4a0bc7e47071875449e839`.
Se comprobaron rutas y miembros regulares antes de extraer; el manifiesto
verificó todos los archivos. Los cuatro artefactos A13 originales no cambiaron.

Se crearon dos venvs aislados, sin alterar Python global ni laboratorios previos.
Los **14 comandos finalizaron con código 0**, incluyendo instalación con
dependencias fijadas, `pip check`, inventario del entorno y ejecuciones.

| Prueba | Entorno real | Resultado |
|---|---|---|
| Catálogo de límites/omisiones normal | ARM64, CPython 3.10.12 | 1.054 casos: 333 PASS, 721 rechazos esperados |
| Mismo catálogo con `-O` | ARM64, CPython 3.10.12 | Mismos 1.054 casos y resultados |
| Catálogo de límites/omisiones normal | ARM64, CPython 3.12.15 | 1.054 casos: 333 PASS, 721 rechazos esperados |
| Mismo catálogo con `-O` | ARM64, CPython 3.12.15 | Mismos 1.054 casos y resultados |
| Omisiones POSIX del núcleo | ARM64, CPython 3.12.15 | **25 PASS, 0 FAIL/ERROR/SKIP** |
| Omisiones POSIX del benchmark | ARM64, CPython 3.12.15 | **7 PASS, 0 FAIL/ERROR/SKIP** |

Los conjuntos `(classname, name)` de ambos XML coinciden exactamente con las
omisiones originales de Windows. Los cuatro recibos del catálogo reproducen
los mismos casos, IDs, oráculos, salidas y estados del recibo Windows final.
La herramienta tiene el hash `56822972540c405a1a5c05315575d4b87b21e5919ee0910747c9680564ed1bff`,
igual al código publicado. Las repeticiones no añaden obligaciones.

Después se ejecutaron las suites fuente completas desde los sdists A13:

| Suite / control adicional | Resultado nativo Linux ARM64, CPython 3.12.15 |
|---|---|
| Núcleo completo | **8.077 PASS, 0 FAIL/ERROR/SKIP**; mismos IDs de la suite Windows |
| Benchmark completo, primer recorrido | **622 PASS, 0 FAIL/ERROR y 5 SKIP** |
| Tres inventarios fuente antes omitidos | **3 PASS** tras indicar la pareja original mediante `EQUIFRAME_TEST_SOURCE_PACKAGES`; 616 miembros fuente cotejados, expectativas intactas |
| Unión aplicable del benchmark en Linux | **625 PASS**; quedan dos casos que requieren Windows y ya tienen evidencia Windows |

El [recibo de la ampliación](VM_FULL_VALIDATION_20261011.json) conserva el primer
resultado de cinco omisiones y las tres comprobaciones posteriores separadas.
Los 32 casos POSIX iniciales son parte de las suites completas y no se suman
como otros 32 casos distintos.

Se actualizó únicamente el tooling de los venvs propios: pip 22.0.2/25.0.1 de
VM y pip 24.0 de Windows pasaron a 26.2.1; setuptools 59.6.0 de VM/3.10 pasó
a 84.0.0. `pip check` y el catálogo posterior vuelven a pasar. Los congelados
anteriores se conservan; no se modificó Python global. No se repitió la consulta
de avisos ni se declara limpieza de todo el entorno o cierre de S15.

El archivo devuelto, de 2.129.283 bytes, conserva SHA-256
`7859c5793742f89d6566fcb5f4c8830f4d0718abeffebe07630495b9c2a15ff0`.
Se verificaron 24 recibos regulares. Los enlaces y FIFO creados deliberadamente
por pruebas negativas permanecen como datos dentro del tar original, sin
extraerse localmente. El primer extractor conservador rechazó uno de esos
fixtures; su salida parcial se conserva separada y no sustenta la evaluación.

## Efecto en las mediciones

Con las suites A13 anteriores y los 72 casos del consumidor, estas pruebas
completan las omisiones funcionales identificadas del conjunto de paquetes.
La revisión independiente del agente IA `mi_dot` cotejó archivos, comandos,
IDs y recibos y recomendó cerrar **M02**. La [madurez actual](MATURITY_VM_RESULT_20261011.json)
queda en **4/16 = 25 %**, con M01/M02/M03/M06 completos. No es una revisión humana
ni una ejecución de todas las celdas de la matriz. La posterior suite completa
Linux fortalece la evidencia del mismo criterio, sin conceder nuevos criterios.

M04/M07/M13 y los demás criterios integrales conservan sus brechas. No se
ejecutaron los trece perfiles aislados en ARM64, todos los extremos de dependencias,
las restantes plataformas/Python, ni el handoff completo. Los recibos prueban
el alcance de la tabla, sin ampliarlo.

La trazabilidad permanece en **5.516/8.385 = 65,78 %**, con **1.192 obligaciones
adicionales necesarias** para el 80 %. Seguridad conserva **7/20 = 35 %**: estos
casos POSIX no corrigen el hallazgo Windows, completan la lectura del repositorio
ni asignan responsables. Tesis sigue en **9/22 = 40,91 %**; las pruebas no son
corpus efectivo, O ciego o aceptación científica. Las otras cifras mantienen
las versiones y rúbricas de su última medición respaldada.

## Custodia y entrega

El archivo privado `metas_90_80_85_50_20261011_VM_evidencia.zip` tiene 6.568.731
bytes y **32 miembros con CRC/hash verificados**. SHA-256:
`c21d0ae2773c3760660ca4fc30a22e8f0f9b0ec10e9953bebf848961afbe06f4`.
Incluye input autorizado, respuesta raw, recibos regulares y scripts; excluye
credenciales y Word. Las evidencias anteriores permanecen intactas. Los dos
venvs propios de la VM se conservan para futuras pruebas.

La ampliación completa y el tooling se conservan en
`metas_90_80_85_50_20261011_VM_full_evidencia.zip`, de 2.019.213 bytes y
44 miembros verificados. SHA-256:
`166375ba05dc6e154ccff8f4457ad0228cf6c43766648bf7fa778a26bb8f9e58`.

La entrega Git contiene resúmenes y referencias; no contiene los binarios,
logs/corpus completos ni credenciales. El Word mantiene SHA-256
`883b187f08221b9b4abab775430d9a2c87b6d92f503494317f3e1fec214d0f3c`.
No se ejecutaron Actions, se crearon recursos de pago ni se publicó en PyPI/TestPyPI.
