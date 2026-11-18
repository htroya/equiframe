# Entrega del paso 5: perfiles y preprocesamiento

Fecha: 2026-10-01. Versión: `equiframe 0.5.0`. Repositorio privado:
`htroya/equiframe`. Fuente: `TFM_EquiFrame_ACTUAL.docx`, hash
`c96f0edfcab839b2ccf357527f4a7937c4b1fd3570f491d702b4f01fde44b38d`.
El DOCX sigue siendo borrador y permanece intacto.

## Revisión del plan 1–10

| Paso | Situación y relación con esta entrega |
|---|---|
| 1 | Contratos, tipos, serialización, paquete y CI existentes |
| 2 | Ejecución nativa y capturas verificables existentes |
| 3 | Comparador completo existente; no constituye por sí solo O |
| 4 | R y catálogo técnico 0.4.0 existentes; punto de partida |
| 5 | Implementado: perfiles por familia y preprocesamiento congelado |
| 6 | Pendiente: benchmark, O revisado, grupos y particiones |
| 7 | Pendiente: M, B, calibración e híbrido H |
| 8 | Pendiente: orquestación integral, CLI y reportes completos |
| 9 | Pendiente: entregas reales de José/Jhair e integración OCI/DW |
| 10 | Pendiente: congelación científica, evaluación, publicación pública y reproducción independiente |

## Alcance implementado

- Diez fórmulas de §3.6/Tabla 13, con denominadores por columna/etapa.
- Cinco familias, orden fijo, huella de definición y versiones explícitas.
- Ausencia, NaN, cadena vacía, cero, claves incompletas y denominadores vacíos
  separados; expansiones/razones duplicadas rechazadas.
- Tasas de conversión basadas en recibos de intentos/fallos de la misma ejecución.
  Ausencia del recibo, integridad alterada y fallos técnicos quedan no evaluables.
- Medianas de entrenamiento normal, indicadores, retiro documentado o estado
  no estimable; inferencia sin reajuste y matriz común para los futuros M/B.
- JSON estricto, persistencia sin sobrescritura, esquemas y ejemplos instalables.

Detalles de uso y límites en [PROFILES.md](PROFILES.md). Decisiones A48–A54 y
requisitos T10/T15 registrados en decisiones/trazabilidad. El contrato 1.0 y
el catálogo de R conservan sus bytes y huellas.

## Validación local ejecutada

Windows x64, Python 3.12.4, dependencias fijadas en `uv.lock` (solo cambia la
versión propia del paquete). En la suite completa: **596 pruebas aprobadas**.
Incluye **35 pruebas nuevas** de perfiles/preprocesamiento, con propiedades de
permutación, fórmulas esperadas independientemente, límites, fallos y persistencia.
Ruff, formato, mypy estricto y generación de 28 fixtures/esquemas pasan.

Comandos desde `packages/equiframe` con el entorno bloqueado:

```bash
uv sync --locked --all-extras
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy
uv run --locked --all-extras python tools/generate_assets.py --check
uv run --locked --all-extras pytest -q
uv run --locked --all-extras python -m build --no-isolation
uv run --locked --all-extras python tools/verify_distribution.py
```

El script de distribución verifica base sin motores/ML, los cinco extras, ejemplos
de perfiles con Arrow, preprocesador restaurado, ejecuciones nativas de cinco
familias, consumidor tipado y reconstrucción byte a byte del wheel desde sdist.
La verificación local de distribución pasó, incluyendo las 596 pruebas repetidas
contra el wheel instalado desde el sdist y la reconstrucción idéntica byte a byte.

## Publicación y evidencia remota

El cambio se integró en `main` mediante el
[PR #14](https://github.com/htroya/equiframe/pull/14), commit de implementación
`ce933a8bbe10b592a40191ce48639fcde4b85343` y merge
`994947a4d0c100a843d5269e5220a02b3ca88e85`.
La [CI del merge](https://github.com/htroya/equiframe/actions/runs/36894666957)
terminó correctamente en las cinco plataformas: Windows x64, Linux x64/ARM64
y macOS x64/ARM64, con Python 3.12. También pasaron la CI de la rama y del PR.

La [prepublicación privada v0.5.0](https://github.com/htroya/equiframe/releases/tag/v0.5.0)
contiene los artefactos instalables verificados. Sus SHA-256, confirmados contra
los digest de GitHub, son:

| Artefacto | SHA-256 |
|---|---|
| `equiframe-0.5.0-py3-none-any.whl` | `a47a0e519f460cf3d166f9644aa85e73ea67132132895d2a906bb89f69442943` |
| `equiframe-0.5.0.tar.gz` | `37544e8fad3293978fa416d2a2972c308e5e3e27541a42d836118937eb4acc98` |

Después de publicar se completaron nueve intentos OCI: 1 OCPU y 12, 8, 4 GB,
en ese orden, recorriendo AD-1, AD-2 y AD-3 para cada RAM. Por instrucción
adicional se hicieron otros seis: primero 3 GB en los tres AD y después 2 GB.
Los **15 intentos** recibieron `Out of host capacity`; no se creó una VM.
El registro está en
[OCI_INTEGRATION.md](OCI_INTEGRATION.md#reintentos-del-2026-10-01).

## Límites y tareas que siguen pendientes

Estas pruebas son de ingeniería. No acreditan los 60 escenarios/300 perfiles,
normalidad revisada, grupos independientes, suficiencia de soporte, detector
entrenado, alpha calibrado, métricas ni resultados SERCOP. Un hash de selección
no certifica su validez científica. El perfilado actual materializa las tablas
con presupuestos cooperativos; no promete streaming, spill ni cuota RSS.

La entrega desplegable del paso es wheel/sdist privado, con Python 3.12. No existe
un servicio nuevo que desplegar en OCI. La publicación en PyPI y la licencia final
siguen en el paso 10. La VM se intenta por instrucción expresa adicional del usuario,
después de entregar este paso, y su resultado se documenta por separado.
