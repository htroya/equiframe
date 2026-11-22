# Primera verificación ETL con EquiFrame 0.15.8

Esta guía web amplía las instrucciones de CI para 0.15.8.
La [guía incluida en el wheel](https://github.com/htroya/equiframe/blob/v0.15.8/docs/first-acceptance-0.15.8.md) sigue disponible en la etiqueta de la versión.

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
esperados. En CI, ejecuta directamente el comando de aceptación y aplica el
control de publicación descrito abajo.

```bash
equiframe verify accept demo-acceptance/match.json --reference-binding demo-acceptance/reference/binding.json --output demo-acceptance/ci-runs
```

Cambia `match.json` por `different.json` para observar el código 1. Añade
`--require-execution` a la solicitud correcta para observar el código 3.
El código 2 indica una solicitud o configuración inválida.

## Decisión de publicación en CI

`accept_in_ci` ejecuta el comando de aceptación con el mismo intérprete y
comprueba el código de salida y el JSON leído de su salida estándar
(`stdout`). Devuelve 0 solo cuando el comando devuelve 0 y ese JSON contiene
el booleano `publishable: true` en el nivel superior. Bloquea la carga si falta
esa salida, si el JSON es ilegible o si la decisión integral queda pendiente.
La comprobación se limita a esos criterios y a la salida directa del comando.

```bash
python -I -m equiframe.examples.integrations.accept_in_ci verify demo-acceptance/match.json --reference-binding demo-acceptance/reference/binding.json --output demo-acceptance/guarded-runs
```

Para SERCOP, usa `sercop` en lugar de `verify` y pasa los argumentos de
`equiframe sercop accept-execution`. El campo `contract.publishable` describe
la decisión contractual. Puede indicar `true` mientras la decisión integral
está pendiente. La cobertura `complete` indica que el examen se completó.

### Cuando CI recibe un informe guardado

Conserva el código de salida y el `stdout` de la llamada de aceptación, junto
con los recibos y la vinculación a la referencia, en un registro controlado por
la etapa que ejecutó el comando. Cuando otra etapa reciba el informe como
archivo, aplica estas comprobaciones.

1. Valida el esquema del informe que espera tu integración. Comprueba su
   identidad y su correspondencia con el lote, la ejecución y la referencia
   autorizados.
2. Contrasta el JSON guardado con la salida retenida del comando. Para la
   verificación genérica, ejecuta `equiframe verify inspect` sobre el
   directorio de verificación para comprobar la integridad de la evidencia.

   ```bash
   equiframe verify inspect directorio-de-verificacion
   ```

   El código 0 de `verify inspect` indica que la evidencia está íntegra. La
   decisión de publicación proviene del comando de aceptación original. En
   SERCOP, coteja el informe integral guardado con el `stdout` de
   `sercop accept-execution` y comprueba su `publishable` superior.
3. Autoriza la publicación solo si esa ejecución devolvió 0, su
   `publishable` superior es el booleano `true` y la evidencia comprobada
   corresponde al lote. Bloquea el lote si falta la evidencia, está truncada
   o su identidad discrepa.

Prueba en tu CI un lote aprobado, otro divergente, un informe ausente o
truncado y un informe de otra ejecución. Para SERCOP, incluye el caso de
`contract.publishable: true` con decisión integral pendiente.

## Adaptarlo a tu carga

- Declara las claves, tipos, reglas y precisión que necesita tu ETL.
- Genera el resultado esperado con una implementación de referencia. Conserva
  su archivo, las entradas del lote y `binding.json` en un canal que el
  proceso candidato no pueda modificar.
- Construye la solicitud con la salida candidata y la referencia autorizada.
  Para certificar el plan ejecutado, aporta los recibos de ejecución y usa
  `--require-execution`.

[Manual de 0.15.8](https://github.com/htroya/equiframe/blob/v0.15.8/docs/index.md) ·
[Formato de la solicitud y la vinculación](https://github.com/htroya/equiframe/blob/v0.15.8/docs/api.md#10-command-line-interface)
