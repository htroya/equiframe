# Contratos sintéticos del paso 1

Los cinco JSON son ejemplos de contratos y fixtures de pruebas, uno por familia.
Los produce `tools/generate_assets.py`. Sus valores, unidades, escalas, límites y
reglas son elecciones sintéticas para comprobar la API. No son escenarios
científicos revisados, resultados de comparación ni políticas de SERCOP.

`allowed_values` es una restricción declarativa, no una tabla de datos de prueba.
Las reglas y precondiciones del contrato 1.0 se evalúan desde el paso 4 con
`ef.evaluate_rules` sobre una captura de una ejecución. Véase [R](../../../docs/RULES.md).

Desde `packages/equiframe`:

```powershell
uv run --locked equiframe contract validate examples/nulls_types.json
uv run --locked python tools/generate_assets.py --check
```


`execute_native.py` ejecuta las cinco familias con código propio de cada motor y esperados explícitos, en comercio y telemetría. Con wheel + [engines]: `python execute_native.py --work-dir my-runs`; con un extra individual añada `--engine pandas|polars|duckdb`. Estos casos prueban ejecución, transporte y comparación; no son el benchmark científico.

## Comparación del paso 3

`compare_local.py` es un consumidor autocontenido del extra Arrow: compara montos
con un esperado independiente, detecta intercambio que conserva la suma y lee
toda la evidencia aunque el resumen contenga un solo ejemplo. No necesita motores.

`execute_native.py` conserva las implementaciones nativas independientes; además
compara sus salidas contra esperados explícitos y entre parejas con entradas
verificadas idénticas. Usa permisos justificados para índices sin significado y
anchos físicos que conservan valores. Ambos ejemplos se copian y ejecutan con
el wheel instalado fuera del checkout por `tools/verify_distribution.py`.

## Reglas R del paso 4

`rules/catalog-1.0.json` fija las cinco entradas técnicas y sus huellas de R.
`rules_catalog.py` crea capturas sintéticas de una fila, verifica esas huellas y
evalúa con solo el extra `arrow`:

```powershell
python rules_catalog.py --work-dir my-rule-runs
```

Las capturas de demostración no son corridas ETL de los tres motores, el oráculo
ni casos del benchmark revisado. Para una ejecución real, lea su `run.json` como
`ef.ExecutionResult`, luego llame `ef.evaluate_rules(execution)`; la API verifica
los artefactos referenciados sin importar los motores.
`rules_from_run.py ruta/al/run.json` es el consumidor mínimo de esa captura;
no necesita instalar Pandas, Polars ni DuckDB.
