# Alcance de la revisión integral y preservación del trabajo del equipo

Fecha de revisión: **2026-10-03**, zona del usuario `America/Guayaquil`.
Este documento registra el contraste de fuentes realizado para revisar,
mejorar y profesionalizar EquiFrame sin modificar lo comunicado a José y
Jhair. Es una revisión documental y de alcance: no es un recibo de pruebas,
CI, despliegue, evaluación científica o publicación.

## Fuentes efectivamente leídas e identidad

Los documentos Word se mantienen fuera del alcance de edición de esta revisión.
El Word de tesis está fuera de Git; las rutas del cuadro son relativas al
workspace que contiene el repositorio `equiframe`.

| Fuente | SHA-256 comprobado | Uso |
|---|---|---|
| `tesis_corregda_v1.docx` | `365af93cdd4bbf7e665145d0e4597eb1391678f5dcb16ce25423b5802c249ac2` | Autoridad académica editable de la última entrega |
| `equiframe/ACTIVIDADES_JOSE_JHAIR.docx` | `fdfa2af9f60729aa178dc88c1098c0036c6124d95dfda5878e59058713a98905` | Trabajo comunicado al equipo, incluidas sus adiciones propias |
| `equiframe/ACTIVIDADES_JOSE_JHAIR.md` | `41d706dae5d7c251bd1aa9e5b479010fc171b95e55c54d8240332e63050aabb1` | Guía técnica de actividades y comandos existentes |
| `word_qa_20261003_revision2/final-audit_text.txt` | `baf2ee3f720d7aa5cba2a2530180f250009b1070143dcd574590fdbeba0016c0` | Extracción de lectura de la entrega final |

La identidad de la tesis coincide con
`word_qa_20261003_revision2/delivery-final.json` y con la sección
«Segunda entrega editorial final» de [trazabilidad](THESIS_TRACEABILITY.md).
También se leyeron directamente los párrafos de `word/document.xml` de ambos
Word para contrastar el mínimo de aprendizaje y la actividad de VM de José.
Los conteos y controles editoriales consignados en el recibo anterior son
antecedentes; esta revisión no repite ni certifica su renderizado.

Referencias de ingeniería leídas: [AGENTS](../AGENTS.md), [README](../README.md),
[arquitectura](ARCHITECTURE.md), [API](API_CONTRACTS.md),
[integración del equipo](TEAM_INTEGRATION.md), [hoja de ruta](HERNAN_ROADMAP.md),
[decisiones](DECISIONS.md), [trazabilidad](THESIS_TRACEABILITY.md),
[Verify](VERIFY.md), [ETL](ETL.md), [soporte semántico](SEMANTIC_SUPPORT.md) y
[revisión técnica anterior](VERIFY_ETL_REVIEW_20261003.md).

## Diferencia entre las dos guías que debe conservarse

El Word y el Markdown de actividades **no son copias idénticas**. En la
actividad 1 de José, el Word añade que, si falta capacidad OCI, puede crear la
VM en **AWS, Azure o Hetzner**. El Markdown conserva únicamente la formulación
OCI. Esta adición mantiene responsable, finalidad, Ubuntu, Python 3.12,
almacenamiento y evidencias; amplía las opciones de proveedor ya comunicadas.

No corresponde regenerar el Word desde el Markdown ni eliminar esa alternativa
para uniformar las fuentes. La revisión del núcleo puede mantener su independencia
del proveedor y las mismas garantías de snapshot, permisos y escritor único.
La elección, creación, costos y configuración de la VM pertenecen a José; este
documento no ejecuta ni acredita ese despliegue.

## Matriz de preservación de la tesis vigente

Las secciones se refieren al Word identificado arriba, con capítulos 1–2 y
anexos preparatorios. Las referencias a capítulos 3–5 en informes anteriores
conservan su sentido histórico; no fijan la estructura de esta entrega.

| Requisito de la tesis | Fuente concreta | Mejora de EquiFrame compatible | Condición de preservación |
|---|---|---|---|
| Tres parejas principales: Pandas–Polars, Pandas–DuckDB y Polars–DuckDB | §1.3, §1.4, Anexo A.1; A100 | Fortalecer comparación, diagnóstico y trazabilidad en las seis direcciones técnicas | Conservar los nueve estratos científicos; no sustituir tres parejas por una ni inferir el sentido inverso |
| Tres familias científicas: ausencias/tipos, uniones y agregaciones | §1.3, Anexo A.1 | Mejorar capacidades genéricas de cinco familias | Duplicados/orden y fechas siguen como restricciones transversales y capacidades técnicas; no añaden estratos científicos |
| Cada motor ejecuta su propia transformación sobre las mismas entradas | §1.3, §2.2.8, Anexo B | Compiladores nativos, preflight, contratos y capturas verificadas | No calcular una salida común y convertirla para simular tres ejecuciones |
| R, M, B, H y O tienen información y finalidades diferentes | Resumen, §1.1, §2.2.5–2.2.8, Anexo A | Mejorar disponibilidad, estados, evidencia y utilidad de Verify operacional | H conserva R OR M; perfiles/detectores no reciben esperado, etiquetas, mutación ni salidas de otro motor |
| O requiere esperado independiente y revisión humana elegible | §2.2.8, Anexo A.4; guía Jhair 5 | Validar coherencia de expedientes y procedencia declarada | Acuerdo entre motores, un hash o comparación contra esperado no autentican personas ni establecen por sí solos O |
| Datos pertinentes SERCOP–OCDS de 2025 y exclusiones justificadas | §1.3, §1.4, §2.2.7, Anexo A.2 | Importación genérica exacta, inventarios y consumidores de snapshots | El ejemplo de dos awards y fixtures no representan corpus completo; no fijar cohorte/compilación sin perfilado del dominio |
| Más de 10.000 registros efectivos usados en aprendizaje | §1.3, Anexo A.2; A101 | Exponer unidades, soporte por ajuste, perfiles y grupos independientes | No confundir filas fuente/adjudicaciones con N efectivo; no sumar reutilizaciones, semillas, calibration/test o matrices distintas |
| Organización propuesta: un M y una B por cada familia principal | §1.3, Anexo A.2 | Mantener configuraciones explícitas y compatibilidad de features | Propuesta de tres modelos M, no nueve; interpretación institucional del mínimo por ajuste y suficiencia siguen pendientes |
| Soportes pareados por contraste y una intersección común adicional | §1.4, Anexo A.7 | Mejorar reportes de cobertura, denominadores, no evaluabilidad y comparación incremental | La intersección común no sustituye automáticamente al soporte pareado H–R; registrar resultados negativos y métricas indefinidas |
| Grupos de dependencia indivisibles y prueba reservada | Anexos A.5–A.7 | Auditoría de splits, identidades únicas y freeze trazable | Train/calibration/test disjuntos por grupos; prueba no selecciona reglas, variables ni umbrales |
| Grano de adjudicación y relaciones que no duplican monto | §2.2.7, Anexo A.3; guía Jhair 2–3 y 7 | Verificar claves, multiplicidad y reconciliación por moneda | `(snapshot_id, ocid, award_id)`; puente sin monto; conservar ausencias, decimales y temporalidad |
| Reproducción de contenido y repetición independiente | §1.4, §2.2.8, Anexo A.8; guía José 7 | Bundles, lectura relocatable y reconstrucción de tablas/decisiones | Validar integridad no acredita una repetición por otra persona; tiempos/RSS no tienen que ser idénticos |
| Entrega parcial sin resultados empíricos ni aceptación institucional | Resumen, §1.3, Anexo B | Profesionalizar software y memoria técnica | Tests sintéticos, wheels y reportes no satisfacen hipótesis, revisión científica, DW real ni aprobación del tutor |

## Matriz de las actividades ya comunicadas

La [guía Markdown](../ACTIVIDADES_JOSE_JHAIR.md) conserva numeración y comandos.
Las responsabilidades y carpetas proceden también de
[integración del equipo §1–6](TEAM_INTEGRATION.md).

| Responsable y actividad | Entrega preservada | Apoyo permitido desde la biblioteca de Hernán |
|---|---|---|
| Jhair 1 | Originales 2025 e inventario fuente/fecha/SHA-256, fuera de Git | Lectura estricta, recibos y metadatos de procedencia |
| Jhair 2 | `packages/equiframe-sercop/schema.sql`, diagrama y grano sin monto duplicado | Contratos genéricos y pruebas de conformidad sobre fixtures |
| Jhair 3 | `packages/equiframe-sercop/mapeo_ocds.md`, tipos, moneda, fechas y ausencias | Conversión exacta o rechazo explícito; sin inventar políticas de dominio |
| Jhair 4 | Recorrido ETL nativo y seis migraciones de práctica, luego adaptación a originales | Mantener el comando y formato de resumen del ejemplo; ampliar diagnóstico |
| Jhair 5 | Esperados desde JSON, dos revisiones independientes y resolución | Formatos/validadores que conservan pendientes y conflictos |
| Jhair 6 | Repetición de carga y fallo controlado con conservación del previo | Destino Parquet local de práctica; no atribuirle carga del almacén real |
| Jhair 7 | Reconciliación por clave/moneda y entrega de snapshots a José | Herramientas de verificación que consumen la entrega acordada |
| José 1 | VM Ubuntu/Python 3.12 y recursos; OCI o alternativa AWS/Azure/Hetzner comunicada en Word | Compatibilidad y límites documentados; sin crear ni administrar la VM |
| José 2 | Instalación, ejemplos y pasos equivalentes Ubuntu en `infra/README.md` | Conservar rutas/comandos; paquetes instalables desde repositorio/wheel |
| José 3 | Identidades, permisos, claves y conexiones; secretos fuera de Git | Diagnósticos de acceso y consumidores inyectables sin credenciales incorporadas |
| José 4 | Cliente `packages/equiframe-data`, `get_snapshot` y `download_artifact` | `SnapshotDataSource` consume interfaces existentes y fija una versión |
| José 5 | Servicio `services/data-gateway`, estados, idempotencia y publicación | Tipos/Protocols y validación de conformidad; sin implementar su servicio |
| José 6 | Límites, tres lectores, carga interrumpida, backup y recuperación | Conservar errores y evidencia; controles locales no certifican el servicio |
| José 7 | Reproducción desde entorno nuevo y aceptación final con datos reales/VM | Portabilidad y documentación ejecutable; no inventar aceptación personal |

Permanecen bajo sus responsables `packages/equiframe-data`,
`services/data-gateway`, `infra` y `packages/equiframe-sercop`.
Las mejoras del núcleo, benchmark, ejemplos y documentación de Hernán no
transfieren esas entregas, no sustituyen DDL/mapeos y no cambian la API lógica
de snapshot/trabajo acordada.

## Capacidad técnica y evidencia que aún falta

| Área | Estado documental comprobado | Cierre que no se puede inferir |
|---|---|---|
| Núcleo/benchmark 0.11.0 | API, contratos, comparación, R/perfiles/M/B/H, migración, Verify, ETL local y bundles documentados | Ausencia universal de defectos; modelo científico entrenado o utilidad de H |
| Semántica | Matriz explícita de soporte/rechazo/pendiente; el validador conserva rechazo de right/full y timestamp IR | Producto cartesiano de todos los operadores, tipos, motores, versiones y plataformas |
| Datos de práctica | Ejemplos sintéticos y consumidor público SERCOP acotado documentados | Corpus 2025 completo, cohorte aceptada o N efectivo suficiente |
| Servicio/DW | Puertos y entregas de José/Jhair especificados | VM operativa, acceso autenticado, DDL real y consistencia durante cargas |
| Revisión científica | Instrumentos de asignación, revisión y arbitraje documentados | Personas autenticadas, decisiones externas y etiquetas confirmadas |
| Distribución | Candidato, artefactos y controles históricos documentados | Publicación PyPI/TestPyPI, licencia acordada y aceptación externa |
| Compatibilidad | Controles previos identificados por commit/plataforma | Ejecución remota actual o soporte nuevo por configurar una matriz CI |

Los resultados numéricos de pruebas anteriores permanecen en sus informes,
fechas y commits. Este contraste no ejecutó tests ni CI y no los acredita para
cambios posteriores.

## Hallazgos documentales y prioridades de mejora

Las referencias siguientes identifican el estado inspeccionado; una corrección
posterior debe mantener los informes y decisiones históricos con su contexto.

| Prioridad | Hallazgo concreto | Fuente inspeccionada | Corrección compatible |
|---|---|---|---|
| P1 | La matriz llamada «Requisito vigente» aún usa Pandas–DuckDB principal y Polars adicional | `THESIS_TRACEABILITY.md`, tabla T02; A96 frente a A100 | Conciliar la matriz actual con tres parejas; conservar A96 como historia supersedida |
| P1 | T03 aún aplica el mínimo a adjudicaciones fuente | `THESIS_TRACEABILITY.md`, tabla T03; A98 frente a A101 | Separar inventario/recuentos fuente de N efectivo por ajuste; referir al Word vigente y A101 |
| P1 | T19 y aceptación del paso 10 solo nombran la intersección común | `THESIS_TRACEABILITY.md`, tabla T19; `HERNAN_ROADMAP.md`, paso 10 | Declarar soportes por contraste y común adicional; auditar implementación/métricas sin cambiar resultados históricos |
| P1 | La hoja de ruta llama «Meta» a 60 escenarios/300 perfiles | `HERNAN_ROADMAP.md`, paso 6; Word §1.3 | Etiquetar cuotas históricas; cierre basado en inventario, diversidad, grupos y revisión real |
| P1 | El Word de actividades acepta proveedores alternativos, mientras los textos técnicos usan OCI de forma exclusiva | Guía Word, José 1; `TEAM_INTEGRATION.md` §8; `OCI_INTEGRATION.md` apertura | Mantener OCI como propuesta histórica y reconocer la alternativa ya comunicada; misma responsabilidad y garantías |
| P2 | Referencias históricas §3.x pueden leerse como estructura vigente de una entrega 1–2 + anexos | `THESIS_TRACEABILITY.md`, matriz y ajustes al borrador inicial | Señalar versión histórica y añadir correspondencia con §1.3/1.4 y anexos actuales |
| P2 | Algunas descripciones del IR inicial omiten operaciones aditivas presentes | `TEAM_INTEGRATION.md` §10; `migration/types.py`, `Concatenate` y `Deduplicate` | Referir al IR/API y matriz vigentes; no sugerir soporte de right/full o timestamp por existir tipos declarativos |

La ampliación más útil dentro de este encargo es fortalecer casos límite
reproducibles, exactitud decimal/ausencias/multiplicidad, estados no evaluables,
verificación de evidencia, mensajes de CLI y uso desde paquetes instalados.
Un defecto debe llevar entrada mínima, esperado independiente, comportamiento
observado y regresión significativa antes de declararse corregido.

Las capacidades nuevas requieren definir políticas y límites antes de
implementarlas. Right/full, timestamp IR, aritmética Decimal adicional, resume,
streaming, cuotas duras, PROV normativo, plugins adicionales o ejecución
distribuida son fronteras de ingeniería; no se anuncian por escribir una interfaz
ni amplían automáticamente la tesis o las tareas del equipo.

## Criterios de cierre de la intervención

1. Conservar los tres hashes de tesis y guías y las carpetas de José/Jhair.
2. Mantener comandos, rutas y formatos que las actividades requieren; si aparece
   una incompatibilidad, resolverla en el consumidor genérico o documentar una
   migración explícita antes de modificar contratos.
3. Vincular cada mejora a su alcance, prueba apropiada y limitación; distinguir
   defecto confirmado de rechazo deliberado o dependencia externa.
4. Repetir controles del paquete realmente afectado, conservar sus logs/commit y
   registrar los resultados observados en el informe de implementación.
5. Mantener datos, Word de tesis, credenciales, bases, modelos y resultados
   privados fuera de Git. Versionar código, documentación y fixtures sintéticos
   pequeños permitidos.
6. La subida solicitada corresponde a `htroya/equiframe`; verificar commit y
   SHA remoto después del push. Publicación en índices, despliegue e invitaciones
   a terceros siguen siendo acciones distintas de actualizar este repositorio.

Este documento define alcance y preservación. El informe final de la revisión
debe registrar por separado qué cambios se hicieron, qué controles se ejecutaron
y qué requisitos empíricos o entregas externas continúan pendientes.
