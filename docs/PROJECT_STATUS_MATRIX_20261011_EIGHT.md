# Estado consolidado de las ocho áreas vigentes

Núcleo y benchmark **0.12.0a13, Alpha privada**. Los ocho denominadores
originales y cada candidato evaluado se conservan. El área retirada por el
propietario conserva sus registros históricos; el cambio de tablero no suma
avance técnico. La última meta es maximizar cada área hacia 100 % salvo cierres
externos; no se declara 100 % con criterios parciales.

| Área | Medición respaldada | Candidato | Recibo |
|---|---:|---|---|
| Usabilidad técnica | **91,67 % — 11/12** | 0.12.0a13 | [USABILITY_A13_REASSESSMENT_RESULT_20261012](USABILITY_A13_REASSESSMENT_RESULT_20261012.json) |
| Universalidad | **80,00 % — 48/60** | 0.12.0a11 | [UNIVERSALITY_80_RESULT_20261010](UNIVERSALITY_80_RESULT_20261010.json) |
| Preparación PyPI | **80,00 % — 16/20** | 0.12.0a13 | [PYPI_PREPARATION_RESULT_20261010](PYPI_PREPARATION_RESULT_20261010.json) |
| Documentación | **90,00 % — 18/20** | 0.12.0a13 | [DOCUMENTATION_RECHECK_20261010](DOCUMENTATION_RECHECK_20261010.json) |
| Trazabilidad | **75,24 % — 6309/8385** | 0.12.0a13 | [OPTION_EXCEPTIONS_RESULT_20261012](OPTION_EXCEPTIONS_RESULT_20261012.json) |
| Calidad del paquete, rúbrica propia | **80,00 % — 16/20** | 0.12.0a13 | [PACKAGE_QUALITY_RESULT_20261010](PACKAGE_QUALITY_RESULT_20261010.json) |
| Madurez | **68,75 % — 11/16** | 0.12.0a13 | [MATURITY_SCOPE_REASSESSMENT_RESULT_20261012](MATURITY_SCOPE_REASSESSMENT_RESULT_20261012.json) |
| Cumplimiento de requisitos de tesis | **40,91 % — 9/22** | 0.12.0a13 | [THESIS_CURRENT_RESULT_20261011](THESIS_CURRENT_RESULT_20261011.json) |

El promedio con igual peso es **75,82 %**, calculado con fracciones
exactas por el [instrumento](../tools/measure_global_progress.py) y vinculado al
[recibo JSON](GLOBAL_EIGHT_RESULT_20261011.json). Alcanza la meta global del 75 %.
No significa que todas las áreas alcancen ese valor ni que haya aceptación
científica o humana. Universalidad conserva A11 hasta reevaluar su rúbrica completa.

La [evaluación nueva de madurez](MATURITY_SCOPE_REASSESSMENT_20261012.md)
relee el alcance original y usa recibos A13 reales. Conserva la evaluación
tras M13 y corrige la extensión improcedente de M04 a evidencia/consumidor/
recuperación; no omite los cuatro Python requeridos en artefactos y suites.
La [usabilidad A13](USABILITY_A13_REASSESSMENT_20261012.md) verifica sus 64
subcomprobaciones técnicas; U12 humano permanece pendiente.

Trazabilidad acredita **6.309/8.385 = 75,24 %**, 264 IDs adicionales de esta
entrega. Restan 2.076 para 100 %, 1.238 para ≥90 % y 819 para ≥85 %.
Repeticiones, suites y plataformas no crean nuevos IDs.

[Plan Alpha](ALPHA_MAXIMIZATION_PLAN_20261012.md), [pendientes humanos/PyPI](HUMAN_REQUIREMENTS_20261012.md),
[estado VM](VM_PENDING_WORK_20261012.md), [dataset público](SERCOP_PUBLIC_DELIVERY_20261012.md)
y [diagnóstico DW](JHAIR_DW_DIAGNOSTIC_20261012.md) detallan alcances y causas.
Alpha sigue abierta; Beta está aplazada. El [encargo EDA posterior](EDA_NEXT_TASK_20261012.md)
se ejecuta después de los controles y subida de esta fase a main.

El Word conserva SHA-256 `883b187f08221b9b4abab775430d9a2c87b6d92f503494317f3e1fec214d0f3c`.
No se publica en PyPI/TestPyPI, no se ejecutan Actions ni se crean recursos pagos.
