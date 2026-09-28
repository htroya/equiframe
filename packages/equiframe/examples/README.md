# Contratos sintéticos del paso 1

Los cinco JSON son ejemplos de contratos y fixtures de pruebas, uno por familia.
Los produce `tools/generate_assets.py`. Sus valores, unidades, escalas, límites y
reglas son elecciones sintéticas para comprobar la API. No son escenarios
científicos revisados, resultados de comparación ni políticas de SERCOP.

`allowed_values` es una restricción declarativa, no una tabla de datos de prueba.
Las reglas y precondiciones se validan estructuralmente; no se ejecutan en este paso.

Desde `packages/equiframe`:

```powershell
uv run --locked equiframe contract validate examples/nulls_types.json
uv run --locked python tools/generate_assets.py --check
```
