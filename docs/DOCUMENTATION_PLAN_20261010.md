# Plan de documentación profesional: DOC-PRO-20-v1

Corte inicial: `cc6b168a9e6c0fd0c48fe1d4d6e037b0b2b24069`, pareja privada
core/benchmark `0.12.0a13`. Rúbrica propia de ingeniería, fijada antes de los
cambios: 20 controles de igual peso, 5 puntos por control completo; parcial,
ausente o bloqueado vale cero y permanece en el denominador. No es una norma
externa ni una encuesta de satisfacción. El 85 % de la tabla anterior carece
de denominador y evidencias identificables; no se compara numéricamente con
esta medición. La documentación existente sí se aprovecha y reconoce abajo.

## Criterios y diagnóstico inicial

| ID | Condición para PASS | Inicial | Evidencia inicial o carencia |
|---|---|---|---|
| D01 | Entrada única que distingue uso, desarrollo, investigación e informes históricos | GAP | README tiene enlaces dispersos; falta índice de `docs/` |
| D02 | Rutas de lectura para arquitecto y científico | PASS | `packages/equiframe/docs/first-use.md`, `arquitecto.md`, `cientifico.md` |
| D03 | Encabezados actuales de README, arquitectura y API coinciden con metadatos del par | GAP | API anuncia A7 y `__version__` A12; arquitectura mezcla estados actuales A13/A7 |
| D04 | Instalación privada Windows/POSIX, extras y comprobación de identidad | PASS | `installed-private.md`, `quickstart.md`, `dependencies.md` |
| D05 | Primer uso sintético completo con resultados esperados | PASS | `first-use.md`, `quickstart.md`, `recipes.md` |
| D06 | Referencia de API y criterios para elegir servicio | PASS | `api.md`, `choosing-api.md`, README |
| D07 | CLI con códigos de salida y rechazo explícito | PASS | `api.md`, `first-use.md`, README del benchmark |
| D08 | Semántica de tipos, claves, multiplicidad, ausencias y estados | PASS | `semantics.md`, `outcome-gates.md`, `API_CONTRACTS.md` |
| D09 | Interfaces de extensión y ejemplo con límites y propiedad de recursos | PASS | `extending.md`, `sqlite-snapshots.md`, `universal-sources.md` |
| D10 | Separación de benchmark, controles técnicos y evidencia científica | PASS | README del benchmark, `THESIS_TRACEABILITY.md` |
| D11 | Diagnóstico y recuperación de fallos sin ocultar diferencias | PASS | `upgrading.md`, `maintenance.md`, `first-use.md` |
| D12 | Glosario bilingüe con referencias canónicas | GAP | Conceptos repartidos, sin glosario enlazado |
| D13 | Contribución con comandos concretos, revisión y propiedad | PASS | `CONTRIBUTING.md`, `contributing.md`, `TEAM_INTEGRATION.md` |
| D14 | Compatibilidad, cambios y recuperación por artefacto | PASS | `compatibility.md`, `upgrading.md`, `releasing.md`, changelogs |
| D15 | Integración distingue par actual, componentes implementados y entregas pendientes | GAP | `TEAM_INTEGRATION.md` presenta A7 como estado actual |
| D16 | Privacidad, seguridad, límites de confianza y recursos explicados | PASS | `security.md`, `performance.md`, `OFFLINE_WHEEL_AUDIT.md` |
| D17 | Control manual repetible de archivos y anclas Markdown, con inventario y límites | GAP | Auditor del wheel comprueba archivos; excluye anclas y documentación raíz |
| D18 | Ejemplos extraídos del texto actual ejecutados contra wheel identificado, normal y `-O` | GAP | Hay pruebas de scripts/CLI; falta registro que vincule bloques exactos del texto a ejecuciones |
| D19 | Un lector humano distinto del autor completa la guía y registra dificultades | BLOCKED | `adoption.md`: no hay observación humana verificable |
| D20 | Documentación pública de esta distribución accesible con derechos aprobados | BLOCKED | Repositorio privado; licencia y publicación pendientes de titulares |

Inicial bajo esta rúbrica: **12/20 = 60 %**. Esto mide controles completos de
documentación, no el volumen/calidad literaria de los documentos ni una pérdida
respecto de la cifra antigua sin método. Objetivo: **18/20 = 90 %**, conservando
D19/D20 abiertos. No se inventará un lector, una aprobación ni un sitio público.

## Cinco pasos de ejecución

1. Organizar un portal por tareas y separar las fuentes actuales de los recibos
   fechados. Mantener los informes históricos y sus hashes intactos.
2. Conciliar versiones y estado de arquitectura, API e integración con el código
   A13. Conservar las secciones de evolución como historia identificada.
3. Añadir glosario y un recorrido de integración de tres estados, con evidencias
   antes del gate y valores sintéticos. Enlazar las guías existentes.
4. Crear un control manual de navegación y un registro de ejemplos extraídos.
   Probar fallos del control, destinos/anclas y ejemplos normal/optimizado desde
   un wheel identificado fuera del checkout. No ejecutar bloques arbitrarios.
5. Registrar resultados, fuentes y límites; revisar el diff, subir la rama y
   fusionar a `main` dentro de la autorización vigente. Sin Actions, publicación
   en PyPI, servicio nuevo o recurso de pago.

El núcleo, algoritmos, esquemas, dependencias, fixtures históricos y bytes de
los wheels entregados no cambian por esta tarea. Las guías raíz nuevas pertenecen
al repositorio; no se afirmará que ya vienen dentro del wheel A13 anterior.
