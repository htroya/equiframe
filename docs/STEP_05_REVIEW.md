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
La evidencia remota de CI se registra al cerrar esta entrega.

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
