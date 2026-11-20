# Primera verificación ETL con EquiFrame 0.15.2

Usa Python 3.10–3.13 y un entorno virtual vacío. Esta guía usa el extra
`arrow` y el wheel identificado de EquiFrame 0.15.2.

```bash
python -m venv .venv
```

Activa el entorno con `source .venv/bin/activate` en macOS o Linux, o con
`\.venv\Scripts\Activate.ps1` en PowerShell de Windows. Instala el wheel
identificado de 0.15.2 y comprueba las dependencias.

```bash
python -m pip install "./equiframe-0.15.2-py3-none-any.whl[arrow]"
python -m pip check
```

Descarga [verify_accept.py](../examples/integrations/verify_accept.py) usando
el botón **Raw** de GitHub. Guárdalo en el directorio de trabajo y ejecútalo.
`demo-acceptance` debe ser un directorio nuevo.

```bash
python verify_accept.py --work-dir demo-acceptance
```

Puedes ejecutar el ejemplo directamente desde la instalación con
`python -m equiframe.examples.integrations.verify_accept --work-dir demo-acceptance`.

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
esperados. En CI, ejecuta directamente el comando de aceptación y usa su
código de salida para decidir si la carga puede continuar.

```bash
equiframe verify accept demo-acceptance/match.json --reference-binding demo-acceptance/reference/binding.json --output demo-acceptance/ci-runs
```

Cambia `match.json` por `different.json` para observar el código 1. Añade
`--require-execution` a la solicitud correcta para observar el código 3.
El código 2 indica una solicitud o configuración inválida.

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

[Manual de 0.15.2](https://github.com/htroya/equiframe/blob/v0.15.2/docs/index.md) ·
[Formato de la solicitud y la vinculación](https://github.com/htroya/equiframe/blob/v0.15.2/docs/api.md#10-command-line-interface)
