# Ensayo local de mantenimiento

Incidente técnico observado: el consumidor tipado instalado en Python 3.12 invocaba mypy con el objetivo 3.10 heredado del archivo de configuración y fallaba al leer stubs de NumPy que usan sintaxis 3.12.

1. Reporte conservado: checks-core-312-001-08.log, error real de sintaxis en numpy/__init__.pyi y código de salida 2 del subproceso mypy
2. Impacto: el gate de distribución fallaba. Las 4.474 pruebas fuente y 4.474 instaladas habían pasado, pero el control integral no podía declararse aprobado
3. Reproducción: ejecución integral real con CPython 3.12.14 y las dependencias fijadas; no hace falta un ticket externo para conservar el defecto
4. Cambio revisable: commit 8c524d29df0007d743d6f95c0bf3e0b8c81de05a consulta la versión del intérprete del consumidor, conserva --strict y el archivo de configuración, y rechaza versiones fuera de la matriz
5. Regresión precisa: cuatro minors, rechazo del minor no comprometido y fallo del probe, seis casos aprobados antes del nuevo recorrido integral
6. Verificación final: pendiente de los controles del candidato actualizado; un pase focalizado no borra el fallo anterior
7. Reversión: el commit es independiente; volver al último artefacto bueno exige usar sus hashes y dependencias, no renombrar un wheel
8. Gobierno: autor técnico registrado como trabajador de la tarea. Responsable de mantenimiento, revisor independiente y aceptación del titular siguen sin asignarse/aceptarse

La prioridad de ingeniería es impedir que un arnés confunda las dependencias del intérprete real con otro objetivo de tipos. No se ha prometido SLA ni comunicado un incidente a terceros.
