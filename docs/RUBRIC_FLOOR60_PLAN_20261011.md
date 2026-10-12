# Elevar al menos al 60 % las áreas por debajo del 50 %

La petición conserva los criterios y denominadores originales. El [recibo del
plan](RUBRIC_FLOOR60_PLAN_20261011.json) valida los hashes de las nueve fuentes y
calcula los umbrales con fracciones exactas. No concede puntos por tareas
planificadas, evidencia parcial o repeticiones.

| Área | Medición vigente A13 | Mínimo para alcanzar el 60 % | Cierres completos adicionales |
|---|---:|---:|---:|
| Madurez | 5/16 = 31,25 % | 10/16 = 62,50 % | 5 |
| Cumplimiento de requisitos de tesis | 9/22 = 40,91 % | 14/22 = 63,64 % | 5 |
| Preparación en seguridad | 7/20 = 35 % | 12/20 = 60 % | 5 |

Si esos mínimos se acreditan y las otras seis cifras permanecen iguales, el
promedio condicionado sería **75,2008004915 %**. El promedio medido sigue en
**66,4255479662 %**. Usabilidad A12 y universalidad A11 siguen siendo mediciones
históricas; este escenario no las reevalúa sobre A13. Las metas individuales
anteriores permanecen como objetivos posteriores.

## Trabajo técnico y validación

- **Madurez:** ampliar compatibilidad, instalación y regresiones sobre celdas
  nativas y bandas originales (M04/M05/M07); completar recuperación e integridad
  del kit y el handoff del laboratorio (M11/M12/M13), incluidos los paquetes y
  perfiles comprometidos. Un ensayo adicional Windows o ARM64 no cierra las
  celdas Linux x64/macOS restantes. M08 requiere auditoría/dependencias completas;
  M09 necesita una decisión real de derechos. M15/M16 mantienen gobierno y
  revisión humana pendientes. Véanse [criterios](MATURITY_MATRIX.md) y
  [evaluación vigente](MATURITY_RESOURCE_RESULT_20261011.json).
- **Seguridad:** completar el alcance de lectura (S02), corregir y verificar el
  hallazgo Windows de junctions (S05/S13), ejecutar límites y limpieza aplicables
  (S09), y completar avisos por resolución/perfil (S15). La cobertura sellada
  319/698 no se amplía retroactivamente. Si se modifica el SDK, identificar un
  candidato nuevo y revalidar los controles afectados; conservar las mediciones
  A13 como históricas. La supervisión por muestreo del ensayo SERCOP no acredita
  cuotas duras OS/container. Las decisiones y revisión humana exigidas por otros
  criterios siguen pendientes. [Rúbrica aplicada](SECURITY_READINESS_RESULT_20261011.json).
- **Tesis:** aprovechar el corpus adquirido para perfilado técnico y ensayos
  nativos; preparar reglas y características por familia, grupos transitivos,
  separación ajuste/calibración/prueba y manifest de congelación. T03 necesita
  soporte efectivo de aprendizaje por modelo/familia; las adjudicaciones crudas
  no lo sustituyen. T06/T15/T16/T17/T18 requieren el protocolo científico,
  normalidad revisada, particiones reales y congelación sin decisiones pendientes.
  T04/T13/T14 mantienen el contrato/DW/servicio de sus responsables; T07/T21
  mantienen oráculo y reproducción humanos. [T01–T22 vigentes](THESIS_CURRENT_RESULT_20261011.json).

La revisión IA «mi dot» aporta contrapruebas técnicas y revisión de evidencia.
No representa una persona del equipo, no concede licencias y no satisface las
puertas que requieren revisión humana independiente. La licencia/titulares y
los resultados científicos aprobados continúan pendientes según lo declarado
por el usuario. No se modifica `tesis_corregda_v1.docx`.

## Datos públicos SERCOP

La adquisición y el [piloto de enero](SERCOP_PUBLIC_PILOT_20261011.md) ya existen:
190.619 releases y 183.891 ocurrencias de adjudicación en el export anual;
18 comparaciones nativas del piloto mensual. La ampliación anual debe verificar
el inventario completo/CRC, conservar importes exactos y presencia de campos,
construir esperados independientes antes de ejecutar motores y medir recursos.
Los prefijos comparten observaciones y no forman muestras científicas
independientes. Ninguna prueba adicional de ingeniería cierra por sí sola los
criterios científicos pendientes ni aumenta el numerador de tesis.

## Entrega

Ejecutar pruebas apropiadas de las herramientas, preservar fallos y reintentos,
releer/hash-verificar artefactos, publicar agregados y código revisable en `main`
con la autorización vigente. Mantener exportaciones, capturas y entornos fuera
de Git. Recalcular porcentajes solo tras cierres completos comprobados. No se
publica en PyPI/TestPyPI, no se ejecutan Actions y no se crean recursos de pago.
