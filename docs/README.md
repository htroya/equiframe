# Portal de documentación / Documentation portal

Pareja actual **EquiFrame / benchmark 0.12.0a14**, Alpha privada. Este portal
pertenece al repositorio. El [manual del núcleo](../packages/equiframe/docs/index.md)
también viene dentro de su wheel identificado; las páginas raíz nuevas no se
añaden retroactivamente a un wheel entregado. [Cómo mantener y comprobar la
documentación](DOCUMENTATION_MAINTENANCE.md).

## Empezar y resolver una tarea

[Avance A14 del 14 de octubre](A14_CLOSURE_PROGRESS_20261014.md): obligaciones
acreditadas, pruebas instaladas, preparación de tesis y pendientes hasta el 90 %.

| Quiero… | Leer / hacer | Qué obtengo |
|---|---|---|
| Instalar el candidato correcto | [Instalación privada](../packages/equiframe/docs/installed-private.md), [dependencias](../packages/equiframe/docs/dependencies.md) | Entorno y extras identificados; `pip check` y `doctor` no certifican toda la matriz |
| Probarlo por primera vez | [Primer uso](../packages/equiframe/docs/first-use.md), [quick start](../packages/equiframe/docs/quickstart.md) | Datos sintéticos, reporte y gate explícito |
| Integrarlo en un pipeline | [Recorrido de tres estados](DOCUMENTATION_WORKFLOW.md) | Código completo para aceptar, rechazar diferencias y rechazar lo no evaluable |
| Diseñar una integración | [Arquitecto](../packages/equiframe/docs/arquitecto.md), [arquitectura](ARCHITECTURE.md), [propiedad de componentes](TEAM_INTEGRATION.md) | Fronteras, snapshots y contratos; responsabilidades pendientes identificadas |
| Preparar datos de análisis | [Científico](../packages/equiframe/docs/cientifico.md), [ingestión](../packages/equiframe/docs/ingestion.md) | Tipos, ausencias y precisión conservados |
| Explorar calidad y distribuciones | [EDA opcional](../packages/equiframe/docs/eda.md), [implementación y validación A14](EDA_IMPLEMENTATION_20261012.md) | Diagnóstico privado con datos originales y métricas no evaluables explícitas |
| Elegir o consultar una API | [Elegir API](../packages/equiframe/docs/choosing-api.md), [referencia](../packages/equiframe/docs/api.md), [CLI y gates](../packages/equiframe/docs/outcome-gates.md) | Operaciones existentes y estados correctos |
| Entender un resultado | [Semántica](../packages/equiframe/docs/semantics.md), [glosario](DOCUMENTATION_GLOSSARY.md) | Alcance de equivalencia, finalización y revisión |
| Añadir una fuente u operación | [Extensiones](../packages/equiframe/docs/extending.md), [fuentes](../packages/equiframe/docs/universal-sources.md), [IR](../packages/equiframe/docs/migration-ir.md) | Interfaces y subconjuntos nativos; sin ejecutar plugins desde JSON |
| Diagnosticar un fallo | [Recuperación](../packages/equiframe/docs/upgrading.md), [mantenimiento](../packages/equiframe/docs/maintenance.md), [primer uso](../packages/equiframe/docs/first-use.md) | Acción por dependencia, diferencia, no evaluable o fallo de escritura |
| Usarlo con muchos datos | [Rendimiento y presupuestos](../packages/equiframe/docs/performance.md) | Límites cooperativos y necesidad de mediciones reales |

## Desarrollar y mantener

- [Correcciones de la revisión independiente A14](A14_INDEPENDENT_REVIEW_FIXES_20261013.md)
  con [artefactos nuevos revalidados](A14_REVIEW_ARTIFACT_VALIDATION_20261013.md)
  y [222 contextos raíz adicionales verificados](A14_ROOT_CONTEXT_REVALIDATION_20261013.md)
  con [endurecimiento posterior de rutas EDA](A14_EDA_PATH_HARDENING_20261013.md)
  y [errores seguros y lectura de evidencias](A14_SAFE_ERRORS_EVIDENCE_20261013.md)
  con [recuperación de informes y supervisor Windows](A14_REPORT_RECOVERY_VENV_20261013.md)
  y [copia segura de artefactos](A14_ARTIFACT_COPY_20261014.md)
  y [expediente técnico SERCOP](A14_SERCOP_EXPERIMENT_PREPARATION_20261013.md):
  resultados nuevos y límites de su acreditación.
- [Contribuir](../CONTRIBUTING.md): entornos, controles manuales y revisión.
- [Compatibilidad](../packages/equiframe/docs/compatibility.md), [cambios del núcleo](../packages/equiframe/CHANGELOG.md)
  y [cambios del benchmark](../packages/equiframe-benchmark/CHANGELOG.md).
- [Seguridad](../packages/equiframe/docs/security.md), [auditoría offline del wheel](OFFLINE_WHEEL_AUDIT.md)
  y [releases/recuperación](../packages/equiframe/docs/releasing.md).
- [Política documental](DOCUMENTATION_MAINTENANCE.md#manual-checks): alcance,
  controles repetibles y ejemplos seleccionados. No se ejecutan Actions.
- [Preparación manual de PyPI](PYPI_MANUAL_RELEASE.md): auditoría del par,
  entrega propuesta y pendientes reales de licencia, cuentas y publicación.
- [Preparación de TestPyPI](TESTPYPI_PUBLISHER_PREPARATION_20261013.md): valores
  exactos del publicador y workflow de configuración, sin ejecutar publicación.
- [Brecha hasta 90 %](A14_PROGRESS_GAP_20261013.md) y
  [reparto técnico/humano](A14_TECHNICAL_90_METHOD_20261013.md): cortes históricos
  separados de la evaluación pendiente de A14.
- [Cliente de datos](../packages/equiframe-data/README.md),
  [gateway privado](../services/data-gateway/README.md) y
  [acceso compartido SERCOP](SERCOP_SHARED_ACCESS_20261013.md).
- [Desarrollo seguro A14](A14_SECURE_DEVELOPMENT_20261013.md): código corregido,
  pruebas, análisis automatizados y limitaciones identificadas.
- [Revalidación actual A14](A14_REVALIDATION_CHECKPOINT_20261013.md): suites
  completas, identidad de los candidatos privados y obligaciones pendientes.

## Investigar e integrar con el equipo

El [benchmark](../packages/equiframe-benchmark/README.md) es otra distribución;
requiere exactamente el núcleo A14. Sus APIs no convierten una comparación
técnica en un resultado científico. [Diseño experimental](EXPERIMENT_DESIGN.md),
[trazabilidad de tesis](THESIS_TRACEABILITY.md) y [hoja de ruta](HERNAN_ROADMAP.md#paso-13-profesionalismo-de-api-cli-y-documentación)
identifican las decisiones y revisiones pendientes. R, M, B, H y O conservan
independencia. El gateway y el DW pertenecen a sus responsables; la validación
en VM no equivale a su despliegue o aceptación.

## Informes y alcance de los porcentajes

La [matriz vigente de ocho áreas](PROJECT_STATUS_MATRIX_20261011_EIGHT.md) reúne
las mediciones y el candidato de cada porcentaje. El propietario retiró un área
del tablero; el promedio actual es **75,82 %**, sin reescribir el
[resultado histórico de nueve áreas](GLOBAL_75_RESULT_20261011.json).
El cambio de alcance no constituye un incremento técnico. El agregado conserva
los criterios individuales y los candidatos históricos.

El [plan vigente de Alpha](ALPHA_MAXIMIZATION_PLAN_20261012.md) prioriza agotar
el trabajo comprobable hacia 100 % antes de que exista una Beta. Las últimas
metas mínimas son 90 % en los siete rubros solicitados; conserva
los criterios, pendientes externos y Word intacto. El
[plan Beta pendiente](PRIVATE_BETA_PLAN_20261012.md) no activa otra versión.
Las [entregas humanas y de PyPI](HUMAN_REQUIREMENTS_20261012.md) y las
[tareas pendientes de la VM](VM_PENDING_WORK_20261012.md) permiten revisar
responsables, evidencia y orden. El
[plan del 60 %](RUBRIC_FLOOR60_PLAN_20261011.md) queda como historia.

Las [llamadas con oráculos originales](OPTION_TEST_CALLS_RESULT_20261012.md)
acreditan 71 obligaciones nuevas. La
[lectura de propiedades públicas](OPTION_PROPERTIES_RESULT_20261012.md)
acreditó 32, además de las
[40 de configuración opcional](OPTION_CONFIGURATION_RESULT_20261012.md), las
[42 fronteras sobre fixtures originales](OPTION_SEED_BOUNDS_RESULT_20261012.md) y las
[74 obligaciones de tipos públicos](OPTION_PUBLIC_TYPES_RESULT_20261011.md).
El [parser CLI](OPTION_CLI_PARSER_RESULT_20261012.md) suma 92 IDs y los
[constructores públicos](OPTION_CONSTRUCTORS_RESULT_20261012.md) suman 51,
los [contextos](OPTION_CONTEXT_CONSTRUCTORS_RESULT_20261012.md) suman 66 y
los [defaults de campos](OPTION_MODEL_DEFAULTS_RESULT_20261012.md) suman doce,
y las [excepciones locales](OPTION_EXCEPTIONS_RESULT_20261012.md) suman 43.
La medición actual es **6.309/8.385 = 75,24 %**; faltan 1.238 IDs para el 90 %.
Las repeticiones y las guardias sin ID no incrementan la cobertura.

El [laboratorio M13 concluido](M13_VM_COMPLETED_20261012.md) terminó
115 comandos y 52 perfiles y devolvió íntegramente su expediente. La
[evaluación nueva de madurez](MATURITY_SCOPE_REASSESSMENT_20261012.md)
conserva su alcance original y usa además [sdists/suites nuevos](ALPHA_SDIST_AND_SUITES_20261012.md).
La [usabilidad reevaluada A13](USABILITY_A13_REASSESSMENT_20261012.md)
conserva 11/12 y distingue el pendiente humano.

El [depósito SERCOP local](SERCOP_LOCAL_REPOSITORY_20261012.md) permanece fuera
de Git. La [captura actual entregada](SERCOP_PUBLIC_DELIVERY_20261012.md)
ya está en la VM en una carpeta pública de lectura y tiene HTTPS temporal.
No contiene EDA/reflexión. El [diagnóstico del DW](JHAIR_DW_DIAGNOSTIC_20261012.md)
distingue el prototipo de una carga anual aceptada. El [EDA autorizado después](EDA_NEXT_TASK_20261012.md)
se ejecuta en salidas separadas tras esta entrega.

La [comparación anual completa en la VM](SERCOP_ANNUAL_VM_20261011.md) aprueba
81 comprobaciones SDK, incluidas 27 del corpus completo, y conserva ambas
repeticiones ARM64. La [verificación anual anterior](SERCOP_ANNUAL_ENGINEERING_20261011.md) conserva
54 comparaciones SDK completas hasta 10.000 filas, el límite de disco del
conjunto anual y 18 comprobaciones nativas complementarias sobre todas sus
adjudicaciones. Registra recursos y distingue resultados científicos pendientes.

En el corte anterior, la [ampliación declarativa](OPTION_DECLARATIVE_FOLLOWUP_20261011.md) añadió 270
obligaciones con esperados completos y ejecución normal/optimizada: trazabilidad
69,00 %, con 922 obligaciones pendientes para el 80 %. Las mediciones previas
y las versiones históricas permanecen identificadas.

El [plan de las metas revisadas](IMPLEMENTATION_PLAN_TARGETS_20261011.md) conserva
las rúbricas y sus dependencias; el [plan inicial del 95 %](IMPLEMENTATION_95_PLAN_20261011.md)
permanece histórico. El [nuevo seguimiento](TARGET_FOLLOWUP_RESULT_20261011.md)
documenta implementación, pruebas y límites. La [revisión de tesis](THESIS_CONTRIBUTIONS_REVIEW_20261011.md)
documenta los aportes incorporados y la actualización preparatoria del Word.
El [seguimiento de seguridad](SECURITY_FOLLOWUP_20261011.md) identifica la
auditoría de snapshot y sus límites; el [diagnóstico anterior](SECURITY_SCAN_BLOCKER_20261011.md)
conserva el fallo histórico del launcher.
El [resultado de implementación y validación](IMPLEMENTATION_95_RESULT_20261011.md)
conserva los controles nuevos y las condiciones todavía abiertas.
El [seguimiento técnico posterior](FOLLOWUP_95_RESULT_20261011.md) añade
validación ARM64 3.10/3.12, [corpus y piloto SERCOP](SERCOP_PUBLIC_PILOT_20261011.md),
[revisión IA «mi dot»](AUTOMATED_REVIEW_20261011.md) y
[propuesta de licencia pendiente](LICENSE_PROPOSAL_20261011.md), sin cambiar el Word.
La [validación VM autorizada](VM_TARGET_FOLLOWUP_20261011.md) resuelve el bloqueo
de transferencia y comprueba 32 pruebas POSIX y cuatro recorridos ARM64 del
catálogo; M02 pasa y la madurez estricta queda en 25 %.
La [ampliación completa](VM_FULL_VALIDATION_20261011.json) verifica las 8.077
pruebas del núcleo y las 625 aplicables del benchmark en Linux; conserva dos
casos específicos de Windows y los primeros recorridos como evidencia separada.

| Aspecto | Recibo y artefacto al que se aplica | Medición |
|---|---|---|
| Documentación de este repositorio | [Plan DOC-PRO-20-v1](DOCUMENTATION_PLAN_20261010.md), [resultado inicial](DOCUMENTATION_RESULT_20261010.md), [verificación vigente](DOCUMENTATION_RECHECK_20261010.md) | 18/20 = 90 %; lectura humana independiente y documentación pública pendientes |
| Preparación de PyPI | [Plan PYPI-PREP-20-v1](PYPI_PREPARATION_PLAN_20261010.md), [resultado](PYPI_PREPARATION_RESULT_20261010.md) | 16/20 = 80 %; preparación manual, cuatro requisitos externos pendientes |
| Calidad de paquete | [A13, PACKAGE-QUALITY-RP-20-v1](PACKAGE_QUALITY_RESULT_20261010.md) | 16/20 = 80 %; inspiración cualitativa de Real Python |
| Pruebas por opción | [Recibo actual A13](OPTION_EXCEPTIONS_RESULT_20261012.json) | 6.309/8.385 = 75,24 % de obligaciones únicas |
| Madurez | [Evaluación nueva](MATURITY_SCOPE_REASSESSMENT_RESULT_20261012.json) | 11/16 = 68.75 % de cierre original |
| Cumplimiento de requisitos de tesis | [T01–T22 actuales](THESIS_CURRENT_RESULT_20261011.json) | 9/22 = 40,91 %; no calidad editorial ni aprobación científica |
| Usabilidad técnica | [Reevaluación A13](USABILITY_A13_REASSESSMENT_RESULT_20261012.json) | 11/12 = 91,67 %; observación humana pendiente |
| Universalidad técnica | [A11, UV-TECH-A11-60-v1](UNIVERSALITY_80_RESULT_20261010.md) | 48/60 = 80 %; no se traslada automáticamente a otro wheel |

Los informes con fecha/versión son registros históricos: sus hashes, matrices,
fallos y pendientes se conservan. La versión del paquete, `schema_version`,
revisión de contrato y algoritmo tienen significados distintos; consulta el
[glosario](DOCUMENTATION_GLOSSARY.md). Este portal no sustituye un recibo de
artefacto ni declara una licencia, PyPI, aprobación científica o adopción real.

## English readers

Start with the [distribution-carried handbook](../packages/equiframe/docs/index.md)
and [choosing an API](../packages/equiframe/docs/choosing-api.md). For repository
maintenance use the [English documentation policy](DOCUMENTATION_MAINTENANCE.md).
The bilingual [glossary](DOCUMENTATION_GLOSSARY.md) explains the shared terms;
the Spanish historical design records keep their original context.
