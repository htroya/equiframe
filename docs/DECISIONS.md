# Registro de decisiones

Fecha inicial: 2026-09-28. Estado de arquitectura: propuesta concreta para implementación; cambios se registran con ID, motivo, impacto, autor y fecha. La aprobación metodológica requiere evidencia del equipo, no se presume a partir de este documento.

| ID | Decisión | Motivo / consecuencia | Estado |
|---|---|---|---|
| A01 | Monorepo privado `htroya/equiframe` | Colaboración y cambios de contratos revisables; datos/tesis fuera de Git | Repositorio creado |
| A02 | Dos distribuciones de Hernán: `equiframe` y `equiframe-benchmark` | Evitar dependencias experimentales y etiquetas dentro de biblioteca operacional | Diseño propuesto |
| A03 | Paquetes/servicio propios para José y dominio propio para Jhair | Dependencias dirigidas, propiedad explícita e integración por formatos | Diseño propuesto para acordar |
| A04 | Python 3.12, `src/`, tipado, pyproject y extras | Instalación profesional y versiones comprobables; ARM64 requiere prueba | A implementar en paso 1 |
| A05 | Contratos estrictos y versionados | Borrador evoluciona sin reglas implícitas ni coerción con pérdida | Diseño propuesto |
| A06 | R/M/B/H separados de O | Evitar circularidad y fuga de etiquetas | Requisito de tesis |
| A07 | H con tres estados y disponibilidad | Fallo o falta de modelo no equivalen a corrección | Requisito de tesis |
| A08 | Snapshots inmutables y coordinación central de escrituras | Lectura estable y escritores controlados; puede haber espera de cola | Propuesta a José |
| A09 | Comparaciones por contenido completo; hashes para integridad/particionado | No probar igualdad por muestras o hashes exclusivamente | Diseño derivado de tesis |
| A10 | Configuración piloto vs congelación final | No fijar prematuramente alpha/cohorte/precisión/grupos | Requisito de tesis |
| A11 | Implementación íntegra a cargo de Sol en diez pasos | Preparación actual contiene solo diseño y gestión del repositorio | Instrucción expresa de Hernán |
| A12 | `htroya` propietario; invitaciones pendientes de logins | GitHub personal no permite tres propietarios/admin equivalentes | Limitación verificada |

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
