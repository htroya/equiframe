# Registro de decisiones

Fecha inicial: 2026-09-28. Estado de arquitectura: propuesta concreta para implementación; cambios se registran con ID, motivo, impacto, autor y fecha. La aprobación metodológica requiere evidencia del equipo, no se presume a partir de este documento.

| ID | Decisión | Motivo / consecuencia | Estado |
|---|---|---|---|
| A01 | Monorepo privado `htroya/equiframe` | Colaboración y cambios de contratos revisables; datos/tesis fuera de Git | Repositorio creado |
| A02 | Dos distribuciones de Hernán: `equiframe` y `equiframe-benchmark` | Evitar dependencias experimentales y etiquetas dentro de biblioteca operacional | Diseño propuesto |
| A03 | Paquetes/servicio propios para José y dominio propio para Jhair | Dependencias dirigidas, propiedad explícita e integración por formatos | Diseño propuesto para acordar |
| A04 | Python 3.12, `src/`, tipado, pyproject y extras | Instalación profesional y versiones comprobables; ARM64 requiere prueba | Base implementada; extras se difieren a sus pasos |
| A05 | Contratos estrictos y versionados | Borrador evoluciona sin reglas implícitas ni coerción con pérdida | Implementado en paso 1, esquema 1.0 |
| A06 | R/M/B/H separados de O | Evitar circularidad y fuga de etiquetas | Requisito de tesis |
| A07 | H con tres estados y disponibilidad | Fallo o falta de modelo no equivalen a corrección | Requisito de tesis |
| A08 | Snapshots inmutables y coordinación central de escrituras | Lectura estable y escritores controlados; puede haber espera de cola | Propuesta a José |
| A09 | Comparaciones por contenido completo; hashes para integridad/particionado | No probar igualdad por muestras o hashes exclusivamente | Diseño derivado de tesis |
| A10 | Configuración piloto vs congelación final | No fijar prematuramente alpha/cohorte/precisión/grupos | Requisito de tesis |
| A11 | Implementación íntegra a cargo de Sol en diez pasos | Preparación actual contiene solo diseño y gestión del repositorio | Instrucción expresa de Hernán |
| A12 | `htroya` propietario; invitaciones pendientes de logins | GitHub personal no permite tres propietarios/admin equivalentes | Limitación verificada |
| A13 | Runtime del paso 1: Pydantic, Typer y tzdata; uv 0.11.6 con lock universal | Arrow/motores/ML no se usan todavía; evitar dependencias y extras sin implementación. Runtime/dev/backend separados y fijados por hashes | Ingeniería, Sol, 2026-09-28; implementado |
| A14 | Formato 1.0 y canónico `equiframe-metadata-json-v1` | Defaults/nulls incluidos, objetos ordenados, arrays preservados, UTF-8 sin normalización; Decimal textual y timestamps hasta ns con offset/zona. SHA-256 identifica metadatos, no equivalencia tabular | Ingeniería, Sol, 2026-09-28; implementado |
| A15 | Un único Protocol `ArtifactStore` en paso 1 | `ArtifactRef` está completo; snapshots/observaciones/resultados/features aún no. No introducir `Any`, tipos incompletos ni implementaciones ficticias | Ingeniería, Sol, 2026-09-28; implementado |
| A16 | Seis especificaciones cerradas de reglas y precondiciones | Validar parámetros, referencias y compatibilidad sin ejecutar expresiones ni crear registro operativo. Nuevas formas incompatibles requieren versión de esquema | Ingeniería, Sol, 2026-09-28; implementado |
| A17 | Decimal con precisión 1–76, escala no negativa y comparación exacta; unidad explícita | Capacidad genérica, no escala SERCOP ni garantía por motores. Tolerancias justificadas en integer/float; nunca en decimal exacto | Ingeniería, Sol, 2026-09-28; dominio/escala real pendientes |
| A18 | Coherencia de reglas declarativas sin conversiones implícitas | Joins/grupos preservan unidades; sum/min/max preservan unidad; sum admite ampliación dentro de familia sin reducir dominio y min/max mantienen tipo. OrderCheck usa la política significant completa. Float32 exacto requiere literal representable | Ingeniería, Sol, 2026-09-28; segunda revisión del paso 1 |
| A19 | Zonas IANA exclusivamente desde tzdata bloqueado | La base del sistema puede diferir entre Windows/Ubuntu; cargar recursos del paquete evita que TZPATH cambie la validación. Actualizaciones de tzdata exigen revalidación | Ingeniería, Sol, 2026-09-28; segunda revisión del paso 1 |
| A20 | Decimal canónico independiente del contexto y entrega probada fuera del checkout | Fijar capitals=1 localmente conserva bytes del formato inicial; ejecutar toda la batería contra el wheel instalado desde el sdist, además de API/CLI runtime-only y consumidor tipado | Ingeniería, Sol, 2026-09-28; segunda revisión del paso 1 |

Estas decisiones del paso 1 no cambian requisitos metodológicos del borrador ni cierran cohorte, alpha, revisión humana o cantidades experimentales. La tesis conserva el hash registrado.

## Decisiones que impiden cerrar evaluación, pero no empezar a programar

1. Perfilado y regla de cohorte/fecha de reserva con Jhair.
2. Precisión decimal, claves incompletas, estados y alcance de identificadores.
3. Catálogo y grupos independientes suficientes; revisión del reparto nominal 30/10/20.
4. Alpha tolerable y suficiencia de calibración por familia.
5. Variables/modelos estimables y tratamiento de MAD con soporte degenerado.
6. Revisores asignados, arbitraje y conflicto de autoría con tres integrantes.
7. Protocolo de costos aislado frente a uso concurrente de VM.
8. Licencia de software y condiciones de redistribución del corpus.

## Fuentes técnicas consultadas

- [Concurrencia DuckDB](https://duckdb.org/docs/current/connect/concurrency): modo embebido y alternativas remotas; comprobar versión elegida por José.
- [Permisos de repositorio personal GitHub](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository): propietario y colaboradores.
- [IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html): puntuación y parámetros.
- [Guía pyproject](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/): declaración de distribuciones y dependencias.
- [Contexto Decimal de Python 3.12](https://docs.python.org/3.12/library/decimal.html): capitalización de exponentes y contexto local, comprobados por propiedades.
- [ZoneInfo de Python 3.12](https://docs.python.org/3.12/library/zoneinfo.html): precedencia de TZPATH y carga desde archivo; prueba aislada con base del host alterada.

La consulta técnica no sustituye la prueba contra las versiones que Sol seleccione y bloquee.


## Decisiones del paso 2 — producto 0.2, Sol, 2026-09-28

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A21 | Biblioteca de propósito general, API ef y distribución pública en paso 10 | Pedido nuevo de Hernán, separado del texto científico; base útil, extras y contratos sin SERCOP/OCI/VM. Mantiene diez pasos e independencia experimental |
| A22 | `execute` limita orquestación a ejecución/captura | Tipos completos y DI ahora; reglas/precondiciones operativas, comparación/perfiles/modelos esperan sus pasos. completed no acredita semántica |
| A23 | Arrow IPC file como captura y Arrow/Parquet locales de entrada | Máscaras/NaN/decimal/épocas temporales, esquema físico separado; rechazo previo de objetos/exponentes/signed decimal zero/zoned ns DuckDB no representables. No reconstruye pérdidas anteriores |
| A24 | Registro explícito por instancia y SQL confiable parametrizado | No evalúa contrato JSON, no globals; callbacks propios por motor. DuckDB solo conexión :memory: local con acceso externo/descargas/spill deshabilitados y cierre verificable |
| A25 | Controles cooperativos; interrupción nativa de consulta DuckDB | Sin sandbox ni promesa de timeout duro para callbacks/collect; checkpoint de filas/buffers y memoria/hilos propios del motor no equivalen a RSS o cuotas remotas. Monitores se unen antes de cerrar |
| A26 | Extras y wheel fuera del checkout, CI para PR dependientes | arrow/pandas/polars/duckdb/engines instalados y probados; import ligero; base del PR es step-01 mientras #11 siga abierto. Formato contrato/ArtifactRef 1.0 intacto; API 0.2 con changelog/lock |

El paso 2 no publica en PyPI, no integra PR ni cambia carpetas de José/Jhair.
Los proveedores temporales reales se registran: contrato tzdata Python, entrada
Pandas tzinfo, Polars chrono-tz del runtime, DuckDB ICU del wheel. No se atribuye una
versión IANA común o expuesta sin evidencia. Los enlaces técnicos del README apoyan
las limitaciones; pruebas contra el lock fijan el comportamiento de esta entrega.


## Decisiones de revisión 0.2.1 — 2026-09-28

| ID | Decisión | Motivo y consecuencias |
|---|---|---|
| A27 | Preservar anchos/máscaras y rechazar inferencia ambigua Pandas | NumPy uint64 extremo/nullable y categorías revelaron pérdida o rechazo incorrecto; tipos mezclados se rechazan antes de inferir |
| A28 | Rechazar capacidades temporales/decimales no fieles | Decimal256 de baja precisión provoca pánico Polars; segundos pueden desbordar; DuckDB usa sentinels de infinito y microsegundos zoned. Diagnóstico explícito conserva la entrada |
| A29 | Retener evidencia parcialmente publicada en estado fallido | El índice puede fallar tras publicar datos; se conserva la referencia y la incompletitud, sin anunciar completed. Presupuesto incluye índice y descarga limpia temporales |
| A30 | Validar puertos runtime y coherencia estructural del manifiesto | Fuentes/adaptadores externos deben respetar tipos; huella, entradas/conteos/formato/salida incoherentes se rechazan sin ajustar observaciones al contrato |
| A31 | DuckDB mínimo 1.5.6 y CI en cinco plataformas | El rango anterior incluía API no disponible; lock comprobado. Matriz añade macOS x64/ARM64 y Ubuntu ARM64, para todas las ramas. Los checks prueban código, no despliegan OCI |
| A32 | Conexión al DW alojada en OCI, integración externa al núcleo | Pedido del usuario: programa de conexión y base en la VM. EquiFrame puede ejecutarse allí o consumir snapshots; servicio real y contratos de dominio siguen siendo dependencias del paso 9 |

A27–A31 corrigen ingeniería y pruebas; A32 explicita la ubicación de la integración.
No cambian el experimento, R/M/B/H/O ni el documento DOCX.
