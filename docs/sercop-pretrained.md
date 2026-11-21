# Modelo SERCOP preentrenado y revisión ETL

Una instalación normal incluye el modelo SERCOP ya entrenado y calibrado. El
comando `model` muestra su contrato, la huella, los años, el tamaño de las
particiones y el umbral. `score` recibe el JSON de un `ProfileVector` generado
con las características del modelo y devuelve la puntuación y la decisión.
Los comandos SERCOP se clasifican como experimentales en esta versión Beta.

```sh
python -m pip install equiframe
equiframe sercop model
equiframe sercop score perfil.json
```

La instalación normal también incorpora Arrow y el intérprete R para Windows x64
y Linux x64 con glibc. Después de instalar, la primera revisión puede ejecutarse
sin conexión. Si vas a generar la ejecución con EquiFrame, elige el extra del
motor que utilice tu plan.

```sh
python -m pip install equiframe
equiframe sercop accept solicitud.json --reference-binding referencia.json --output evidencia
```

A partir de EquiFrame 0.15.7, puedes usar el `run.json` generado por
`equiframe.execute` con el archivo Arrow IPC de la referencia independiente.
El comando toma del recibo el plan, las entradas y la salida, y comprueba sus
huellas junto con el archivo de vinculación preparado para esa referencia.
Mantén accesibles las rutas a los artefactos indicadas en el recibo.

```sh
equiframe sercop accept-execution ruta/run.json referencia.arrow --reference-binding referencia.json --output evidencia
```

Usa el contrato incluido, los recibos completos de la ejecución y una referencia
independiente del mismo lote. El contrato agrega las adjudicaciones en centavos
por comprador y moneda después del filtro de importe mínimo. La revisión R vuelve
a comparar los artefactos observados contra esa referencia con una implementación
independiente cuando el bosque y la comparación exacta discrepan o falta una
evaluación. El informe conserva el veredicto contractual, la puntuación y el
umbral del bosque, el dictamen de R y el caso aplicado a la corrida.

En 0.15.8, el perfil agrupado de SERCOP excluye las filas de entrada con importe
nulo de las sumas de referencia del modelo. La captura original, el recuento de
filas y la distinción entre cero y NULL se conservan. El informe identifica la
política `sercop-grouped-reference-present-amounts-1`. El bosque y su umbral
provienen del entrenamiento original con importes presentes.

Para autorizar una carga usa el código 0 y el `publishable` del nivel superior.
Consulta el [ejemplo de CI](first-acceptance-0.15.8.md) para distinguirlo de la
decisión contractual `contract.publishable`.

El contrato revisa las claves, la multiplicidad y los totales exactos en
centavos. Si el bosque guarda silencio ante una diferencia contractual, esa
diferencia bloquea la corrida. Si el bosque alerta y R confirma la equivalencia
de la comparación exacta, la corrida puede aprobarse y la alerta queda
registrada. Un desacuerdo entre comparadores o evidencia incompleta deja
la decisión pendiente.

Si falla una restricción de entrada o de salida, el caso indica
`contract_constraints_failed`. `constraint_failures` identifica la tabla y la
comparación que documenta la infracción. `comparison_case` conserva el resultado
de contrastar la salida con la referencia, Isolation Forest y R.

| Resultado | Código |
| --- | ---: |
| Contrato aprobado y bosque sin alerta, o alerta confirmada como falsa por R | `0` |
| Diferencia detectada por el contrato | `1` |
| Solicitud o configuración inválida | `2` |
| Alerta sin confirmación, desacuerdo o evidencia insuficiente para aprobar | `3` |

El modelo describe perfiles de agregación SERCOP. Los lotes de entrenamiento,
calibración y evaluación se identifican por huella y ventana temporal. La
evaluación usa datos públicos con fallos de ETL controlados. Consulta los
resultados por escenario y el umbral junto a la ficha del modelo.

El ajuste examinó ocho instantáneas públicas de 2019 a 2026, con 1.077.934
publicaciones compiladas en total. Se entrenó con 768 lotes normales, se calibró
con 144 lotes separados y se evaluó con 120 lotes reservados de septiembre a
noviembre de 2026. Los tres motores coincidieron en la evaluación.

| Método | Fallos detectados (60) | Omisiones (60) | Falsas alarmas (60 correctos) |
| --- | ---: | ---: | ---: |
| Isolation Forest | 32 | 28 | 5 |
| Comparación exacta contra la referencia | 60 | 0 | 0 |

El recurso instalado `equiframe/_sercop_assets/provenance.json` contiene las
huellas de los archivos de origen, el artefacto de entrenamiento, las particiones
y los resultados por escenario. Los valores se refieren al contrato, universo
y lotes evaluados.

[Revisión con R](r_review.md) · [Prueba ETL con recibos](first-acceptance-0.15.8.md) ·
[Fuente pública SERCOP](https://data.open-contracting.org/es/publication/110)
