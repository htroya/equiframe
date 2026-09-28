# EquiFrame

Biblioteca Python para comprobar requisitos semánticos y estudiar divergencias al migrar transformaciones ETL entre Pandas, Polars y DuckDB.

Repositorio privado del equipo: <https://github.com/htroya/equiframe>.

Tablero privado de trabajo: <https://github.com/users/htroya/projects/1>. Los diez pasos de Hernán están registrados como issues; el primero es [Paso 01/10](https://github.com/htroya/equiframe/issues/1).

## Estado real

El **paso 1** implementa `equiframe 0.1.0`: contratos semánticos estrictos e inmutables, tipos públicos, validación cruzada, JSON canónico, SHA-256 de metadatos, esquemas JSON y CLI funcional. Hay cinco contratos sintéticos y pruebas de comportamiento/propiedades, tipado, empaquetado e instalación limpia. Adaptadores, comparador, reglas ejecutables, modelos y benchmark siguen pendientes. El paquete no está publicado en PyPI.

Instalación, API y comandos de verificación: [README del paquete](packages/equiframe/README.md). Python inicial: 3.12; matriz CI x64 Windows/Ubuntu. ARM64 no está verificado.

La [segunda revisión completa del paso 1](docs/STEP_01_REVIEW.md) registra fallos
reproducidos, correcciones, 51 regresiones nuevas y evidencia de distribución.

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
| [Segunda revisión del paso 1](docs/STEP_01_REVIEW.md) | Hallazgos, matriz del alcance y comprobaciones ejecutadas |
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

`packages/equiframe` contiene `src/`, `pyproject.toml`, `uv.lock`, pruebas, fixtures y esquemas generados. Los otros paquetes y servicios conservan sus especificaciones de responsabilidad.

## Inicio de la implementación

Sol ha implementado únicamente el paso 1 de [la hoja de ruta](docs/HERNAN_ROADMAP.md). La CI ejecuta controles reales con permisos `contents: read`, acciones fijadas por commit y dependencias bloqueadas. Los siguientes nueve pasos siguen pendientes.

## Datos y permisos

Código, especificaciones y pequeños casos sintéticos se versionan en Git. Datos SERCOP, archivos DuckDB, modelos y resultados de corridas van al almacén de artefactos con hashes y manifiestos. Ningún integrante comparte sus tokens con los demás.

`htroya` es propietario. Las invitaciones de José y Jhair están pendientes de conocer sus usuarios. En un repositorio personal GitHub permite colaboradores con escritura, pero reserva al propietario la administración completa. Si se necesitan tres administradores se debe acordar el traslado a una organización.

La licencia de distribución del software está pendiente de decisión de los autores. Este repositorio privado no implica autorización para publicar un paquete en PyPI.
