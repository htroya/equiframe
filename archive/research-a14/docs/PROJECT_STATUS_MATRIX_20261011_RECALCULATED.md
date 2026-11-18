# Porcentajes recalculados tras la ampliación declarativa

Corte: 11 de octubre de 2026. **Núcleo y benchmark 0.12.0a13, Alpha privada**.
El [resultado estructurado](PROJECT_STATUS_MATRIX_20261011_RECALCULATED.json)
coteja cada fuente por SHA-256 y recalcula `100 × aprobados / total` con las
rúbricas conservadas. El [plan de metas](IMPLEMENTATION_PLAN_TARGETS_20261011.md)
y la [matriz VM anterior](PROJECT_STATUS_MATRIX_20261011_VM.md) permanecen
identificados. Este corte no declara alcanzadas las metas pendientes.

| Aspecto | Meta vigente | Porcentaje respaldado | Base de la medición |
|---|---:|---:|---|
| Usabilidad técnica | Sin cambio | **91,67 %** | 11/12, A12 histórica |
| Universalidad técnica | 90 % | **80 %** | 48/60, A11 histórica; reevaluación completa A13 pendiente |
| Preparación para PyPI | 90 % | **80 %** | 16/20, A13 |
| Documentación profesional | Sin cambio | **90 %** | 18/20, repositorio sobre A13 |
| Trazabilidad por opción | 80 % | **69,00 %** | 5.786/8.385, núcleo A13 |
| Calidad del paquete, rúbrica propia | 85 % | **80 %** | 16/20, A13 |
| Madurez: cierre estricto M01–M16 | 90 % | **25 %** | 4/16, A13 |
| Cumplimiento de requisitos de tesis | 90 % | **40,91 %** | 9/22, A13 |
| Preparación técnica en seguridad | 50 % | **35 %** | 7/20, A13 |

La [ampliación declarativa](OPTION_DECLARATIVE_FOLLOWUP_20261011.md) acredita
270 obligaciones adicionales mediante 268 casos de aserción, conservando
los esperados literales y todos los IDs del denominador. Ambos catálogos pasan
normal y con `-O` en Windows. El numerador pasa de 5.516 a 5.786; faltan
**922 obligaciones adicionales** para 6.708 (80 %). Repetir las ejecuciones
no suma cobertura ni crea muestras científicas.

Se conserva la [validación nativa VM](VM_TARGET_FOLLOWUP_20261011.md):
8.077 pruebas del núcleo y 625 aplicables del benchmark pasan en Linux ARM64;
los dos casos propios de Windows están separados. Eso ya cerró M02 y elevó
madurez a 4/16. Los métodos y campos nuevos no cierran otro criterio integral.

Universalidad necesita reevaluar los 60 controles sobre A13 y completar las
plataformas, perfiles/extremos y condiciones pendientes. Para PyPI faltan dos
cierres reales entre derechos, cuentas/roles, documentación pública y ensayo
de distribución. Calidad requiere un cierre real entre distribución,
dependientes, comunidad y derechos; más pruebas técnicas no acreditan esos hechos.

Madurez requiere al menos 15/16 = 93,75 % para superar la meta del 90 %.
Tesis requiere 20/22 = 90,91 %, incluyendo evidencia científica y revisiones
pendientes; **40,91 % no mide la calidad editorial del Word**. Seguridad
requiere 10/20 para el 50 %; conserva auditoría parcial, un hallazgo bajo Windows
abierto y decisiones de responsables/revisión humana pendientes.

No se calcula una media general entre rúbricas de alcance y versión distintos.
Recalcular una cifra histórica no la convierte en una evaluación de A13.
La revisión de «mi_dot» es por IA y no sustituye una revisión humana independiente.

El Word conserva su hash. Esta entrega modifica herramientas, pruebas y
documentación del repositorio. No se modificó la VM en este seguimiento,
publicó en PyPI/TestPyPI, ejecutó Actions ni creó recursos de pago.
