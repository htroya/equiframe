# EquiFrame

Biblioteca Python para comprobar requisitos semánticos y estudiar divergencias al migrar transformaciones ETL entre Pandas, Polars y DuckDB.

Repositorio privado del equipo: <https://github.com/htroya/equiframe>.

Tablero privado de trabajo: <https://github.com/users/htroya/projects/1>. Los diez pasos de Hernán están registrados como issues; el primero es [Paso 01/10](https://github.com/htroya/equiframe/issues/1).

## Estado real

Este primer incremento contiene la arquitectura, los contratos de integración, el plan de implementación y las normas del proyecto. **La biblioteca todavía no está implementada ni publicada.** Las interfaces documentadas son la especificación de desarrollo, no funciones ya disponibles. No hay resultados experimentales ni modelos entrenados.

La fuente metodológica es `TFM_EquiFrame_ACTUAL.docx`, revisada el 2026-09-28. Su identidad, requisitos y decisiones pendientes están en [trazabilidad](docs/THESIS_TRACEABILITY.md). El documento de tesis y los datos originales no se copian a este repositorio.

## Documentos de trabajo

| Documento | Uso |
|---|---|
| [Arquitectura](docs/ARCHITECTURE.md) | Componentes, dependencias, ejecución y decisiones técnicas |
| [API y formatos](docs/API_CONTRACTS.md) | Interfaces Python, tipos, estados, errores y serialización |
| [Integración del equipo](docs/TEAM_INTEGRATION.md) | Límites y entregas entre Hernán, José y Jhair |
| [Diseño experimental](docs/EXPERIMENT_DESIGN.md) | Oráculo, independencia, perfiles, modelos, particiones y métricas |
| [Plan de Hernán](docs/HERNAN_ROADMAP.md) | Diez pasos con entregables y criterios de aceptación |
| [Calidad y operación](docs/QUALITY.md) | Pruebas, recursos, compatibilidad, seguridad y releases |
| [Decisiones](docs/DECISIONS.md) | Decisiones de arquitectura y asuntos abiertos |
| [Colaboración](CONTRIBUTING.md) | Ramas, revisiones y permisos |

## Responsabilidades

- **Hernán:** `equiframe`, `equiframe-benchmark`, contratos genéricos, adaptadores de ejecución, comparación, reglas, perfiles, modelos, evidencia, CLI y evaluación.
- **José:** VM, servicio de acceso a datos y cliente Python `equiframe-data`; controla concurrencia, autenticación, trabajos y publicación de versiones.
- **Jhair:** modelo y construcción del DW, mapeos OCDS, preparación/carga del dominio, controles y reconciliación en `equiframe-sercop`.

Los nombres de los paquetes de José y Jhair son convenciones propuestas para integrar el trabajo; cada responsable implementa su componente. Las interfaces compartidas se acuerdan por PR. Hernán implementa las transformaciones comparables del benchmark en los tres motores a partir de los contratos de negocio entregados por Jhair; no administra la carga productiva del DW.

## Organización inicial

```text
docs/                          arquitectura y requisitos versionados
packages/equiframe/            biblioteca de Hernán
packages/equiframe-benchmark/  evaluación de Hernán
packages/equiframe-data/       cliente de José
packages/equiframe-sercop/     integración de dominio de Jhair
services/data-gateway/         servicio de José
infra/                        infraestructura de José
.github/                      plantillas de colaboración
```

En este incremento las carpetas de paquetes contienen su especificación de responsabilidad. Los directorios `src/`, las distribuciones Python, los bloqueos de dependencias y sus pruebas se crean en el paso 1 de implementación de Hernán o por el responsable correspondiente.

## Inicio de la implementación

Sol realizará toda la implementación, comenzando por el paso 1 de [la hoja de ruta](docs/HERNAN_ROADMAP.md). Esta preparación no incorpora código de biblioteca, modelos, tests ni pipelines CI ficticios. El paso 1 incorporará empaquetado, tipos, validación y las primeras pruebas y comprobaciones CI reales.

## Datos y permisos

Código, especificaciones y pequeños casos sintéticos se versionan en Git. Datos SERCOP, archivos DuckDB, modelos y resultados de corridas van al almacén de artefactos con hashes y manifiestos. Ningún integrante comparte sus tokens con los demás.

`htroya` es propietario. Las invitaciones de José y Jhair están pendientes de conocer sus usuarios. En un repositorio personal GitHub permite colaboradores con escritura, pero reserva al propietario la administración completa. Si se necesitan tres administradores se debe acordar el traslado a una organización.

La licencia de distribución del software está pendiente de decisión de los autores. Este repositorio privado no implica autorización para publicar un paquete en PyPI.
