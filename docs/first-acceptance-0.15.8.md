# Primera verificación ETL con EquiFrame 0.15.8

Usa Python 3.10–3.13 y un entorno virtual vacío. La instalación de EquiFrame 0.15.8 incluye Arrow.

```bash
python -m venv .venv
```

Activa el entorno con `source .venv/bin/activate` en macOS o Linux, o con
`./.venv/Scripts/Activate.ps1` en PowerShell de Windows.

```bash
python -m pip install "equiframe==0.15.8"
python -m pip check
python -m equiframe.examples.integrations.verify_accept --work-dir demo-acceptance
```

Usa un directorio de salida nuevo para cada ejecución.

El script genera un CSV de pedidos, una captura Arrow y una referencia de
totales exactos en centavos por comprador y moneda. Una agregación Arrow
separada produce las salidas candidatas. El contrato conserva los grupos con
total cero y exige que cuadren los importes del lote. El script ejecuta la CLI
y muestra la ruta de cada informe.

| Caso | Código de la CLI | Resultado |
| --- | ---: | --- |
| Salida equivalente y regla de suma satisfecha | 0 | `passed` |
| Diferencia de un centavo | 1 | `failed` |
| Ejecución requerida sin evidencia capturada | 3 | `not_evaluable` |

El script de demostración sale con 0 cuando observa los tres resultados
esperados. En CI, ejecuta directamente el comando de aceptación y aplica el control de publicación descrito abajo.

```bash
equiframe verify accept demo-acceptance/match.json --reference-binding demo-acceptance/reference/binding.json --output demo-acceptance/ci-runs
```

Cambia `match.json` por `different.json` para observar el código 1. Añade
`--require-execution` a la solicitud correcta para observar el código 3.
El código 2 indica una solicitud o configuración inválida.

## Decisión de publicación en CI

El ejemplo instalado solo devuelve código 0 cuando EquiFrame devuelve 0 y el
informe JSON contiene el booleano `publishable` en `true` en el nivel superior.
Si el informe falta, es ilegible o indica revisión pendiente, bloquea la carga.

```bash
python -I -m equiframe.examples.integrations.accept_in_ci verify demo-acceptance/match.json --reference-binding demo-acceptance/reference/binding.json --output demo-acceptance/guarded-runs
```

Para SERCOP, usa `sercop` en lugar de `verify` y pasa los argumentos de
`equiframe sercop accept-execution`. El campo `contract.publishable` describe
la decisión contractual. Puede indicar `true` mientras la decisión integral
está pendiente. La cobertura `complete` indica que el examen se completó.

## Adaptarlo a tu carga

- Declara las claves, tipos, reglas y precisión que necesita tu ETL.
- Genera el resultado esperado con una implementación de referencia. Conserva
  su archivo, las entradas del lote y `binding.json` en un canal que el
  proceso candidato no pueda modificar.
- Construye la solicitud con la salida candidata y la referencia autorizada.
  Para certificar el plan ejecutado, aporta los recibos de ejecución y usa
  `--require-execution`.
- Conserva el informe de cada ejecución. `equiframe verify inspect` comprueba
  la integridad de un informe guardado. El comando `verify accept` decide la
  aceptación de una carga.

[Manual de 0.15.8](https://github.com/htroya/equiframe/blob/v0.15.8/docs/index.md) ·
[Formato de la solicitud y la vinculación](https://github.com/htroya/equiframe/blob/v0.15.8/docs/api.md#10-command-line-interface)
