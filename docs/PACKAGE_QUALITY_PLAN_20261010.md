# Calidad de paquete: plan de evaluación 2026-10-10

## Alcance y medida congelada antes del desarrollo

Fuente: [How to Evaluate the Quality of Python Packages, Real Python](https://realpython.com/python-package-quality/), consultada el 2026-10-10.
El artículo propone señales de compatibilidad, documentación, mantenimiento,
distribución, confianza, comunidad y licencia. No define un porcentaje ni una
certificación. Esta evaluación es una **rúbrica propia** para el par privado
EquiFrame núcleo/benchmark A12. No mide Universalidad, madurez científica,
seguridad certificada, cobertura de líneas ni trazabilidad por opción.

El 45 % de la captura no tiene aquí un denominador o recibo identificado.
No se reutiliza como baseline medido. La nueva rúbrica tiene veinte controles
binarios de igual peso (5 puntos cada uno); se conserva íntegra para siguientes
evaluaciones. Sólo PASS recibe puntos; BLOCKED, FAIL y NOT_RUN reciben cero.
El objetivo es 16/20 = 80 %, conservando los cuatro pendientes externos.

| ID | Control y evidencia mínima | Relación con la fuente |
|---|---|---|
| Q01 | README de ambos paquetes: propósito, límites y estado privado | Project description |
| Q02 | Primer uso ejecutado: equivalente, diferente y no evaluable | Getting started / code examples |
| Q03 | Requires-Python/classifiers coherentes; instalación A12 en Windows y Linux ARM64, con versiones observadas | Supported Python versions |
| Q04 | Alpha explícito, sin afirmar Production/Stable | Development Status |
| Q05 | Changelog vigente y diferencias frente al candidato anterior | Release history |
| Q06 | Autor y URL del repositorio identificados en ambos METADATA | Author / source links |
| Q07 | Documentación local del wheel con destinos Markdown resolubles, sin depender de abrir el checkout | Documentation |
| Q08 | Distribuciones públicas verificadas en PyPI con identidad controlada | PyPI availability |
| Q09 | Dependencias declaradas iguales a METADATA; resolución normal y pip check satisfactorios | Package compatibility |
| Q10 | Consumidor técnico separado: pruebas independientes contra el wheel suministrado | Dependent packages, prueba técnica acotada |
| Q11 | Dependientes externos reales, ajenos a los laboratorios del equipo | Dependent packages, adopción |
| Q12 | Interés externo observado: comunidad/usuarios; no crear estrellas, forks o descargas artificiales | GitHub social proof / Libraries.io |
| Q13 | Actividad Git real: historial y PR integrados recientes | Active maintenance |
| Q14 | Instrucciones para contribuir, reportar fallos y revisar cambios; límites de respuesta explícitos | Pull requests / issues |
| Q15 | Suites completas núcleo y benchmark sin fallos: fuente y wheel fuera del checkout | Source inspection / maintenance, operacionalización propia |
| Q16 | Ruff, formato, mypy y activos generados de ambos paquetes satisfactorios | Source inspection, operacionalización propia |
| Q17 | Wheel/sdist y payload identificados; reconstrucción desde sdist y rechazos de alteración | Trustworthy source |
| Q18 | Actualización/reversión aisladas A11–A12 con versiones y bytes comprobados; notas de migración | Update precautions |
| Q19 | Comandos privados exactos, verificación SHA-256 por canal separado antes de instalar; import base ligero | Exact installation / trust precautions |
| Q20 | Titularidad y licencia aprobadas; permisos, condiciones y restricciones adecuados | License suitability |

Q03 verifica los entornos indicados, no todas las combinaciones de Python y OS.
Q06 no certifica la reputación del autor. Q10 no cierra Q11. Q14 no inventa
responsables, revisores humanos ni SLA. El score nunca habilita publicación:
Q08 y Q20 son gates independientes incluso con 80 %. Los cuatro controles
externos siguen en el denominador, no se omiten para aumentar la nota.

## Cinco pasos

1. Congelar esta rúbrica y auditar el estado real de Git y del candidato A12.
2. Comprobar coherencia de metadatos, instrucciones, changelog y documentación;
   corregir errores actuales sin reescribir informes históricos.
3. Incorporar un auditor de wheel **previo a instalación**, local y sin ejecución
   del contenido, para comprobar identidad, RECORD, payload y enlaces locales.
   El SHA esperado debe llegar por un canal confiable separado del archivo.
4. Ejecutar controles completos y pruebas instaladas, casos negativos del
   auditor, consumidor independiente, primer uso y actualización/reversión;
   conservar recibos privados identificados por hashes. Validar manualmente
   en la VM existente sin Actions, servicios nuevos ni recursos de pago.
5. Publicar en Git los controles, instrucciones y resultado agregado; integrar
   en main y comprobar el commit remoto. Respaldar evidencia y eliminar sólo
   temporales de esta tarea. No publicar en PyPI ni elegir una licencia.

La evidencia ausente se registra como pendiente. Un fallo no se reclasifica
como éxito por mantener la meta del 80 %.

## Ampliación de candidato tras el control completo

La ejecución completa detectó un defecto real en A12: `fit_detectors` emitía
`versions.equiframe=0.12.0a11`, aunque el paquete observado era A12. La prueba
de identidad también tenía una referencia literal antigua. Se prepara A13
para corregir el emisor y conservar todos los productores históricos. No se
cambia el algoritmo `equiframe-if-mad-1.0`, las reglas, etiquetas o métodos de
la tesis. Se regeneran sólo esquemas actuales; fixtures y recibos fechados
conservan sus bytes originales.

La meta y los veinte controles permanecen. La evaluación final se aplica a
A13; Q03 incluye además su instalación en ambos entornos y Q18 añade el ciclo
A12–A13–A12–A13. Los controles ya ejecutados de A12 se mantienen como evidencia
histórica y de diagnóstico, sin acreditarlos como pruebas del nuevo artefacto.
