# EquiFrame: matriz de porcentajes y alcance

Fecha local: 2026-10-10, America/Guayaquil. Base de esta consolidación:
`3cc7c72fc7c0f76e810289f0e09514b1b0aad6ab`, verificada también en GitHub.
Versión actual: `equiframe 0.12.0a13` y `equiframe-benchmark 0.12.0a13`.
El [resumen estructurado](PROJECT_STATUS_MATRIX_20261010.json) conserva
numeradores, denominadores, candidatos, hashes de fuentes y límites.

Hay **seis áreas con mediciones identificadas** y **tres sin porcentaje vigente
acreditado**. La tabla reúne el último resultado medido de cada área. Los
recibos A11/A12 conservan sus cortes: no se atribuyen automáticamente al A13.
Los valores de la captura son estimaciones antiguas sin método reproducible;
restarlos de estas cifras no demostraría un avance comparable.

## Matriz contrastada con Git

| Aspecto | Captura anterior | Última medición respaldada | Alcance / fuente |
|---|---:|---|---|
| Usabilidad para arquitecto/científico de datos | 80 % | **91,67 % — 11/12** | Técnica, A12; [recibo](USABILITY_CURRENT_RESULT_20261010.md) |
| Madurez | 80 % | **Sin medición vigente de A13** | [Plan y matriz históricos A8](MATURITY_MATRIX.md); ver precisión abajo |
| Universalidad | 55 % | **80 % — 48/60** | Avance técnico A11; [recibo](UNIVERSALITY_80_RESULT_20261010.md) |
| Preparación para publicar en PyPI | 60 % | **80 % — 16/20** | Par privado A13; [recibo](PYPI_PREPARATION_RESULT_20261010.md) |
| Cumplimiento de la tesis | 40 % | **Sin porcentaje acreditado** | [Requisitos y pendientes científicos](THESIS_TRACEABILITY.md) |
| Documentación profesional | 85 % | **90 % — 18/20** | Repo sobre A13; [verificación](DOCUMENTATION_RECHECK_20261010.md) |
| Preparación en seguridad | 50 % | **Sin porcentaje acreditado** | [Estado de seguridad](../SECURITY.md) y [límites](../packages/equiframe/docs/security.md) |
| Pruebas con trazabilidad por opción | 5,16 % | **51,26 % — 4.298/8.385** | Inventario del núcleo A13; [recibo actual](PACKAGE_QUALITY_RESULT_20261010.md) |
| Calidad según criterios de Real Python | 45 % | **80 % — 16/20** | Par A13, rúbrica propia; [recibo](PACKAGE_QUALITY_RESULT_20261010.md) |

## Qué se puede afirmar de esas cifras

**Usabilidad:** once criterios técnicos completos; el criterio humano U12
continúa pendiente. Las 64 subcomprobaciones técnicas no cambian el peso de los
doce criterios. No mide satisfacción ni adopción real. Es la evaluación A12,
no una nueva revisión completa U01–U12 del A13.

**Universalidad:** 48 comprobaciones completas de 60 en UV-TECH-A11-60-v1.
Se conserva el progreso comparable **41/60 → 48/60**, de 68,33 % a 80 %, sobre
los mismos bytes A11. Faltan doce comprobaciones de plataformas, extremos de
dependencias, operaciones/tipos, adopción, derechos y reproducción independiente.
El 25 % del cierre estricto histórico A9 usa otra escala. Ni ese dato ni una
versión posterior se mezclan para fabricar una medición nueva del A13.

**PyPI:** dieciséis controles completos del par A13. Faltan licencia/titulares,
acceso/nombres, documentación pública y ensayo real en TestPyPI. Preparar y
auditar archivos no es publicarlos; la política de publicación sigue cerrada.

**Documentación:** dieciocho controles completos. Siguen pendientes un lector
humano independiente y un manual público con derechos aprobados. La revisión
conserva ejemplos vinculados a ejecuciones y navegación verificada; el recibo
documental anterior no se reescribe cuando se añade esta matriz.

**Trazabilidad:** 1.743 obligaciones PASS y 2.555 EXPECTED_REJECTION suman 4.298;
4.087 siguen NOT_RUN. Total fijo: 8.385; **51,258199… %, redondeado a 51,26 %**.
Los 3.445 casos distintos y sus repeticiones normal/optimizada no se suman como
obligaciones nuevas. Construcción/serialización/rechazo de metadatos no prueban
por sí solos sus efectos nativos ni las combinaciones entre opciones. No es
cobertura de líneas ni porcentaje de toda la suite.

**Calidad:** dieciséis controles de PACKAGE-QUALITY-RP-20-v1; quedan publicación,
usuarios/dependientes externos reales, comunidad observada y derechos/licencia.
Es una rúbrica propia inspirada en el [artículo de Real Python](https://realpython.com/python-package-quality/),
que revisa señales de distribución, documentación, actividad y licencia; no
asigna una nota oficial a EquiFrame. Este 80 % no sustituye la revisión de seguridad.

## Tres porcentajes que no se deben inventar

**Madurez:** el último dictamen específico localizado es del 2026-10-08 para
A8: **1/16 = 6,25 % de cierre estricto de aquel plan**, con nueve criterios
parciales y seis bloqueados. No es el porcentaje de funcionalidad de la librería
ni una valoración vigente del A13. Las pruebas A13 y la VM posteriores aportan
evidencia, pero no se ha consolidado una reevaluación M01–M16 del mismo candidato.
Conservar el 80 % de la captura como hecho nuevo sería injustificado; afirmar
que A13 tiene 6,25 % también lo sería. [Dictamen histórico](MATURITY_REVIEW.md).

**Tesis:** la matriz T01–T22 describe requisitos y evidencia de aceptación, no
veintidós criterios formalmente aprobados. Desarrollo técnico y edición del
Word no acreditan corpus real suficiente, revisión ciega/etiquetas, congelación
y resultados experimentales, reproducción humana o aceptación académica.
El 40 % de la captura no tiene aquí numerador, denominador ni dictamen vigente.
No se infiere un porcentaje del número de páginas, tests o pasos implementados.

**Seguridad:** SECURITY.md declara incompleta la revisión de fuente; inventarios
de dependencias y checks de archivos son acotados. Faltan revisión completa del
candidato, evidencia actual de dependencias y responsables/canal aceptados.
No existe una rúbrica aplicada que acredite el 50 % de la captura. Esta tarea
no reanuda el escaneo ni convierte pruebas funcionales en un dictamen de seguridad.

## Identidad y entrega de esta consolidación

La pareja A13 de preparación, calidad y trazabilidad identifica el wheel núcleo
por SHA-256 `c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23`
y el benchmark por `fb843318d044a36a7ba4efab7d7d997d45798e12d16df7a9aa1b472b2c6359d8`.
Las fuentes estructuradas identifican separadamente los originales A11/A12.

Se contrastan fuentes/aritmética y se comprueba la navegación de esta página,
sus versiones y las regresiones documentales. No se ejecuta una nueva evaluación
de nueve áreas ni se traslada una medición entre artefactos. No hay promedio
global: los denominadores, pesos, versiones y gates difieren; promediar seis
cifras omitiendo tres pendientes produciría otra métrica no definida.

El resultado se entrega en `main` mediante el repo privado. SDK, artefactos,
criterios y recibos anteriores conservan sus bytes; no hay Actions, publicación
pública, recursos nuevos de pago ni cambios en la VM `157.137.227.1`. Solo se
archivan y retiran los temporales propios de esta consolidación.
