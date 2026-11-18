# Resultado del seguimiento de las metas revisadas

El seguimiento amplía la validación y mide las áreas que carecían de una
evaluación vigente. **No acredita todas las metas solicitadas.** La pareja
núcleo/benchmark sigue en `0.12.0a13`, Alpha privada. El Word permanece intacto.
El [plan de implementación](IMPLEMENTATION_PLAN_TARGETS_20261011.md) conserva
las rúbricas y sus umbrales; la [matriz vigente](PROJECT_STATUS_MATRIX_20261011_FOLLOWUP.md)
identifica cada candidato y requisito pendiente.

## Cambios y comprobaciones

Se amplió `tools/universality/validate_profiles.py` con una versión de candidato
explícita. Comprueba los nombres y versiones de ambos wheels antes de instalar;
rechaza parejas mezcladas. Mantiene el valor histórico A11 como default. El
probe del benchmark compara la versión del manifiesto, sin asumir A11.
Los **trece perfiles A13 de Windows AMD64 / CPython 3.12.4** pasaron:
ocho del núcleo y cinco del benchmark, con entornos separados, dependencias
fijadas, identidad instalada y `pip check`. Incluyen operaciones/migraciones
nativas, un recorrido ML sintético y mediciones reales de recursos cuando el
perfil las admite. No son toda la matriz de plataformas/Python/extremos.

`tools/option_boundary_followup.py` congela un catálogo de **1.054 casos nuevos**
y **1.072 obligaciones antes no ejecutadas**. Comprueba el wheel A13 y sus 127
archivos instalados fuera del checkout, los hashes de baseline y catálogos y el
conjunto original de 8.385 IDs. Excluye campos que requieren fixtures coordinadas
o validadores no revisados. Los tres modelos nuevos tienen fixtures sintéticas
completas y esperados literales. No son una carga real ni un ajuste de detectores.

Las omisiones de argumentos llaman realmente a Python, con placeholders inertes
para los demás argumentos y una guardia que prohíbe entrar al cuerpo operativo.
Ese resultado acredita solamente el rechazo de la omisión. La guardia no es un
sandbox para código arbitrario; su alcance es el catálogo de funciones Python
propias revisadas, sin wrappers ni allocators personalizados.

Normal y `-O` obtuvieron **333 PASS y 721 rechazos esperados** cada uno. La unión
es **5.516/8.385 = 65,78 %**: 2.107 PASS, 3.409 rechazos esperados y 2.869 pendientes.
Faltan **1.192 obligaciones adicionales** para llegar al 80 %. Son 4.638 casos
distintos en la unión de catálogos; las repeticiones no suman. El seguimiento
incremental acumulado tiene 1.195 intentos: 1.193 nuevos y dos regresiones.
Los recibos iniciales v3 con una etiqueta ambigua se preservan y se aclaran;
no se modifican sus hashes. [Resultado estructurado](OPTION_BOUNDARY_RESULT_20261011.json).

Pasaron **trece pruebas del arnés** en normal y `-O`, además de Ruff/formato.
Rechazan crédito por IDs ajenos, duplicados, ya comprobados, fallos de programación,
entrada al cuerpo de una operación, mezcla de versiones, confusión `False`/`0`
y fixtures con errores en otros campos. Se reforzaron esos dos últimos controles
tras la revisión IA; el catálogo volvió a pasar con los bytes finales.

## Mediciones nuevas y límites

La [madurez actual](MATURITY_CURRENT_RESULT_20261011.json) aplica M01–M16 con su
alcance original: **3/16 = 18,75 % de cierre estricto**. M01/M03/M06 están completos;
los demás conservan sus brechas. No es una estimación universal de madurez ni un
retroceso frente a un porcentaje informal sin rúbrica. El corte histórico A8
de 1/16 permanece separado. Suites A13 Windows y consumidor están preservadas;
las 25 omisiones POSIX del núcleo y siete del benchmark siguen sin ejecutarse
en este seguimiento, por lo que M02 conserva estado parcial.

El [cumplimiento actual de requisitos de tesis](THESIS_CURRENT_RESULT_20261011.json)
es **9/22 = 40,91 %** bajo una regla binaria explícita. Mide requisitos mixtos de
ingeniería y estudio; no calidad editorial, aprobación del tutor ni confirmación
de hipótesis. Las pruebas sintéticas y el piloto SERCOP no reemplazan N_fit
efectivo, cohorte validada, O humano ciego, freeze, particiones/costos científicos,
soportes pareados y reproducción por otro integrante. El Word no se editó.

La [preparación en seguridad](SECURITY_READINESS_RESULT_20261011.json) aplica
SEC-PREP-20-v1 congelada: **7/20 = 35 %**. Son criterios de preparación, no una
probabilidad de estar seguro. S01/S04/S06/S07/S10/S11/S14 están comprobados en su
alcance declarado. S11 se apoya en revisión de refs/gates y un ensayo manual
real `prepare-scan → scan → verify`, ejecutado por CLI/Python separado: no se
ejecutó Actions ni el bloque Bash/job íntegro.

Los inventarios ligados a los cuatro artefactos A13 verifican hashes, metadatos,
locks y cuatro CycloneDX 1.6. El núcleo contiene 68 componentes (67 públicos) y
el benchmark 64 (62 públicos, núcleo privado y paquete raíz). Las listas
revisadas producen 134/124 consultas PyPI/OSV sobre nombre/versión públicos;
ambos resultados tienen cero avisos conocidos y cero desconocidos. La verificación
offline posterior exige identidad, limpieza y antigüedad menor de 24 horas.
Los componentes build/dev no instalados se identifican expresamente; no se
declara que todo el lock esté instalado ni que el inventario incluya bibliotecas
nativas del SO. El pip 24.0 del entorno de pruebas nuevo queda fuera del lock:
este control no acredita ausencia de avisos en todo el entorno.

El análisis sellado conserva **319 de 698 archivos revisados**, 379 sin revisión
completa y **un hallazgo bajo abierto** de contención de rutas/junctions Windows.
No se aplicó una corrección al payload A13 ni se ejecutó PoC. La evaluación de
preparación referencia el almacenamiento MCP; no sustituye ni reescribe el
informe/findings/coverage canónicos. Falta cobertura, remediación/aceptación,
responsables/canal y revisión humana. S15 permanece parcial.

## Bloqueos y entrega

Licencia/titulares, revisión humana independiente, gobierno y resultados
científicos siguen pendientes según la respuesta del usuario. PyPI conserva
16/20 y calidad propia 16/20: sus condiciones pendientes requieren decisiones,
distribución o adopción reales. No se conceden puntos por redactar propuestas.
Universalidad conserva el último porcentaje respaldado de A11; los nuevos
trece perfiles A13 no acreditan por sí solos una reevaluación de sus 60 criterios.

La revisión automática rechazó la transferencia del paquete privado preparado
de 3,33 MB a la VM `157.137.227.1`, porque consideró insuficiente la autorización
del contenido/destino concretos. Se pidió aprobación específica y el envío
permanece pendiente. El archivo preparado no prueba ejecución Linux. Los
recibos ARM64 anteriores conservan su alcance; no se esquiva el rechazo.

Los recibos completos, listas públicas, planes, logs y catálogos permanecen en
el expediente privado `metas_90_80_85_50_20261011`, fuera de Git. Sus referencias
y hashes se publican para revisión con las herramientas y pruebas. No se publica
el Word, corpus ni credenciales. No se ejecutan Actions, no se crean recursos
de pago y no se publica el paquete en PyPI/TestPyPI.

El [recibo técnico](TARGET_FOLLOWUP_TECHNICAL_20261011.json) identifica el archivo
privado de 12.215.603 bytes: 2.623 miembros con CRC/hash comprobados y sin rutas
ilegibles. SHA-256: `111189b9f620c1e8ca10c6f0bcd01cfc9d4105c0f57cf477eedae1aa029f7613`.
Los entornos propios de este seguimiento se conservan para continuar las pruebas;
el payload VM preparado requiere actualizar sus herramientas antes de un envío
futuro autorizado. Ese archivo conserva sus bytes anteriores y no se presenta
como una ejecución de las herramientas finales.

SHA-256 conservado del Word: `883b187f08221b9b4abab775430d9a2c87b6d92f503494317f3e1fec214d0f3c`.
