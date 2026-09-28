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

La consulta técnica no sustituye la prueba contra las versiones que Sol seleccione y bloquee.
