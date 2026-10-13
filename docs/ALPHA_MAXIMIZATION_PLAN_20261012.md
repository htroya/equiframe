# Maximizar Alpha antes de una Beta privada

La versión activa es **0.12.0a14**, tras la [extensión EDA validada](EDA_IMPLEMENTATION_20261012.md).
El corte evaluado de este plan conserva **A13** y sus recibos. El propietario pidió ejecutar todo lo
posible para alcanzar 100 % en Alpha antes de que exista una Beta. La entrega
conserva los artefactos originales A13 y sus seis identidades; no cambia su
versión, sus contratos ni los resultados históricos A11/A12.

## Implementación y validación

| Trabajo | Acción concreta | Criterio para acreditarlo |
|---|---|---|
| Trazabilidad | Inventario A13 congelado de 8.385 obligaciones; nuevos lotes de parser, llamadas, campos y parámetros con esperados previos | Ejecución real sobre wheel A13 instalado fuera de fuente; ID conocido, nuevo y observado; resultados normales/optimizados concordantes; rechazos atribuibles a su causa |
| Madurez M04/M05/M07 | Completar perfiles de dependencias, versiones Python y plataformas del alcance original | Instalación, regresión y reproducción nativas por celda; una prueba Windows no cierra Linux/macOS |
| Madurez M11/M12/M14 | Verificar actualización, interrupción, recuperación, integridad y consumidor | Artefactos/payload originales, fallo conservado, restauración comprobada y todas las interfaces/celdas comprometidas |
| Madurez M13 | Recuperar el expediente original de la VM y ejecutar por separado su corrección r2 | Logs, recibos y resultados completos devueltos y cotejados; la preparación local del kit no es su ejecución |
| SERCOP 2025 | Preservar exportaciones anual y mensuales en JSON/CSV/XLSX, metadatos y todas las colecciones del JSON | Originales con SHA/CRC, posiciones y duplicados conservados, números exactos, lectura completa de tablas y catálogo de procedencia |
| Requisitos de tesis | Preparar datos, particiones, características y protocolo reproducible; ejecutar sólo ensayos cuyo criterio pueda comprobarse | Separar preparación técnica de cohorte aprobada, normalidad, etiquetas humanas, resultados científicos y servicio/DW real |
| Documentación | Explicar cada limitación, evidencia, criterio y pendiente humano | Enlaces/hashes comprobados; revisión IA identificada como IA; Word sin cambios en este encargo |
| Distribución privada | Mantener fuente y artefactos A13 verificables; preparar instrucciones y recuperación | Ninguna sustitución de originales, ningún artefacto Beta ni publicación pública en esta fase |
| Entrega Git | Revisar diff, ejecutar controles aplicables, recalcular y publicar agregados/código/documentación en `main` | Commit remoto coincidente; datos, entornos, respaldos privados y Word fuera de Git; Actions no ejecutado |

Los lotes congelan primero el catálogo y los esperados. Un intento fallido
permanece en su carpeta; corregir el instrumento genera otro intento. Repetir
un ID en otra versión Python, plataforma o modo no aumenta el numerador.
Contar filas, construir un plan o cambiar una versión tampoco cierra un criterio.

## Límites actuales y trabajo externo

Madurez acredita **11/16** y tesis **9/22** mientras no se complete cada criterio
original. Sus umbrales de ≥90 % son **15/16** y **20/22**. La trazabilidad exige
**7.547/8.385** para ≥90 % y las **8.385** para 100 %. Los porcentajes efectivos
se publican en la matriz vinculada a los recibos; estas cifras son umbrales,
no promesas ni resultados nuevos.

La [reevaluación de alcance original](MATURITY_SCOPE_REASSESSMENT_20261012.md)
cierra M05/M07/M11/M12/M13/M14 con evidencias A13 y sustenta M06 por cuatro
Python reales. M04 conserva compatibilidad pendiente en plataformas/perfiles
comprometidos. M09 requiere derechos/licencia, M15 roles aceptados y M16
revisión humana y cierre. El criterio cancelado por el propietario se conserva
con cero crédito. La fase Alpha sigue abierta: quedan comprobaciones técnicas
de trazabilidad/compatibilidad y cierres externos; no se declara agotada.

En tesis, los pendientes técnicos comprenden
**T03/T06/T15/T16/T17/T18/T20**. Los cierres dependen de condiciones reales:
más de 10.000 filas de ajuste por familia/modelo no equivale a disponer de
muchas filas brutas; hay que aprobar la normalidad, características y partición.
**T04/T07/T13/T14/T19/T21** requieren validación de dominio, etiquetas humanas,
DW/servicio del equipo, evaluación científica y reproducción independiente.
Completar sólo los siete primeros llevaría a **16/22 = 72,73 %**, siempre que
cumplieran íntegramente su definición. No se fabrica evidencia para el resto.

Las decisiones humanas, entregables y roles de PyPI están en
[HUMAN_REQUIREMENTS_20261012.md](HUMAN_REQUIREMENTS_20261012.md).
La VM concluyó M13 y devolvió su evidencia completa. Posteriormente, el
propietario autorizó y se comprobó la entrega pública SERCOP de lectura. El
[EDA posterior](EDA_NEXT_TASK_20261012.md) se ejecutó tras esta entrega y sus
controles/subida a main, en salidas independientes sin alterar la fuente.

## Paso posterior a Beta

La fase Alpha debe quedar agotada de forma comprobable antes de retomar el
[plan Beta](PRIVATE_BETA_PLAN_20261012.md). Cada pendiente debe identificar su
causa, evidencia faltante y responsable; una dificultad o una prueba preparada
no constituye agotamiento. Los cambios de identidad Beta están apartados y
la fuente activa es ahora A14, también Alpha. Una futura Beta necesitará sus propios
artefactos, instalación, consumidor compatible, inventario y mediciones.
