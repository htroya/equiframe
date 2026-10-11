# Portal de documentación / Documentation portal

Pareja actual **EquiFrame / benchmark 0.12.0a13**, Alpha privada. Este portal
pertenece al repositorio. El [manual del núcleo](../packages/equiframe/docs/index.md)
también viene dentro de su wheel identificado; las páginas raíz nuevas no se
añaden retroactivamente a un wheel entregado. [Cómo mantener y comprobar la
documentación](DOCUMENTATION_MAINTENANCE.md).

## Empezar y resolver una tarea

| Quiero… | Leer / hacer | Qué obtengo |
|---|---|---|
| Instalar el candidato correcto | [Instalación privada](../packages/equiframe/docs/installed-private.md), [dependencias](../packages/equiframe/docs/dependencies.md) | Entorno y extras identificados; `pip check` y `doctor` no certifican toda la matriz |
| Probarlo por primera vez | [Primer uso](../packages/equiframe/docs/first-use.md), [quick start](../packages/equiframe/docs/quickstart.md) | Datos sintéticos, reporte y gate explícito |
| Integrarlo en un pipeline | [Recorrido de tres estados](DOCUMENTATION_WORKFLOW.md) | Código completo para aceptar, rechazar diferencias y rechazar lo no evaluable |
| Diseñar una integración | [Arquitecto](../packages/equiframe/docs/arquitecto.md), [arquitectura](ARCHITECTURE.md), [propiedad de componentes](TEAM_INTEGRATION.md) | Fronteras, snapshots y contratos; responsabilidades pendientes identificadas |
| Preparar datos de análisis | [Científico](../packages/equiframe/docs/cientifico.md), [ingestión](../packages/equiframe/docs/ingestion.md) | Tipos, ausencias y precisión conservados |
| Elegir o consultar una API | [Elegir API](../packages/equiframe/docs/choosing-api.md), [referencia](../packages/equiframe/docs/api.md), [CLI y gates](../packages/equiframe/docs/outcome-gates.md) | Operaciones existentes y estados correctos |
| Entender un resultado | [Semántica](../packages/equiframe/docs/semantics.md), [glosario](DOCUMENTATION_GLOSSARY.md) | Alcance de equivalencia, finalización y revisión |
| Añadir una fuente u operación | [Extensiones](../packages/equiframe/docs/extending.md), [fuentes](../packages/equiframe/docs/universal-sources.md), [IR](../packages/equiframe/docs/migration-ir.md) | Interfaces y subconjuntos nativos; sin ejecutar plugins desde JSON |
| Diagnosticar un fallo | [Recuperación](../packages/equiframe/docs/upgrading.md), [mantenimiento](../packages/equiframe/docs/maintenance.md), [primer uso](../packages/equiframe/docs/first-use.md) | Acción por dependencia, diferencia, no evaluable o fallo de escritura |
| Usarlo con muchos datos | [Rendimiento y presupuestos](../packages/equiframe/docs/performance.md) | Límites cooperativos y necesidad de mediciones reales |

## Desarrollar y mantener

- [Contribuir](../CONTRIBUTING.md): entornos, controles manuales y revisión.
- [Compatibilidad](../packages/equiframe/docs/compatibility.md), [cambios del núcleo](../packages/equiframe/CHANGELOG.md)
  y [cambios del benchmark](../packages/equiframe-benchmark/CHANGELOG.md).
- [Seguridad](../packages/equiframe/docs/security.md), [auditoría offline del wheel](OFFLINE_WHEEL_AUDIT.md)
  y [releases/recuperación](../packages/equiframe/docs/releasing.md).
- [Política documental](DOCUMENTATION_MAINTENANCE.md#manual-checks): alcance,
  controles repetibles y ejemplos seleccionados. No se ejecutan Actions.
- [Preparación manual de PyPI](PYPI_MANUAL_RELEASE.md): auditoría del par,
  entrega propuesta y pendientes reales de licencia, cuentas y publicación.

## Investigar e integrar con el equipo

El [benchmark](../packages/equiframe-benchmark/README.md) es otra distribución;
requiere exactamente el núcleo A13. Sus APIs no convierten una comparación
técnica en un resultado científico. [Diseño experimental](EXPERIMENT_DESIGN.md),
[trazabilidad de tesis](THESIS_TRACEABILITY.md) y [hoja de ruta](HERNAN_ROADMAP.md#paso-13-profesionalismo-de-api-cli-y-documentación)
identifican las decisiones y revisiones pendientes. R, M, B, H y O conservan
independencia. El gateway y el DW pertenecen a sus responsables; la validación
en VM no equivale a su despliegue o aceptación.

## Informes y alcance de los porcentajes

| Aspecto | Recibo y artefacto al que se aplica | Medición |
|---|---|---|
| Documentación de este repositorio | [Plan DOC-PRO-20-v1](DOCUMENTATION_PLAN_20261010.md), [resultado](DOCUMENTATION_RESULT_20261010.md) | Controles documentales; independiente de los siguientes índices |
| Preparación de PyPI | [Plan PYPI-PREP-20-v1](PYPI_PREPARATION_PLAN_20261010.md), [resultado](PYPI_PREPARATION_RESULT_20261010.md) | 16/20 = 80 %; preparación manual, cuatro requisitos externos pendientes |
| Calidad de paquete | [A13, PACKAGE-QUALITY-RP-20-v1](PACKAGE_QUALITY_RESULT_20261010.md) | 16/20 = 80 %; inspiración cualitativa de Real Python |
| Pruebas por opción | [A13 en recibo de calidad](PACKAGE_QUALITY_RESULT_20261010.md), [recibo histórico A12](OPTION_TRACEABILITY_RESULT_20261010.md) | A13: 4.298/8.385 = 51,26 % de obligaciones, no cobertura de líneas |
| Usabilidad técnica | [A12, U01–U12](USABILITY_CURRENT_RESULT_20261010.md) | 11/12 = 91,67 %; observación humana pendiente |
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
