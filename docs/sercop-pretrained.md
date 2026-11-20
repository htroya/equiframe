# Modelo SERCOP preentrenado y revisión ETL

Una instalación normal incluye el modelo SERCOP ya entrenado y calibrado. El
comando `model` muestra su contrato, la huella, los años, el tamaño de las
particiones y el umbral. `score` recibe el JSON de un `ProfileVector` generado
con las características del modelo y devuelve la puntuación y la decisión.

```sh
python -m pip install equiframe
equiframe sercop model
equiframe sercop score perfil.json
```

La revisión de una ejecución materializada usa el extra `arrow` y un `Rscript`
de base R instalado en el sistema. Si necesitas ejecutar el ETL para generar el
recibo, instala además el extra del motor que utilice tu plan.

```sh
python -m pip install 'equiframe[arrow]'
Rscript --version
equiframe sercop accept solicitud.json --reference-binding referencia.json --output evidencia
```

Usa el contrato incluido, los recibos completos de la ejecución y una referencia
independiente del mismo lote. El contrato agrega las adjudicaciones en centavos
por comprador y moneda después del filtro de importe mínimo. La revisión R vuelve
a comparar los artefactos observados contra esa referencia con una implementación
independiente. El informe conserva el veredicto contractual, la puntuación y el
umbral del bosque, el dictamen de R y si hace falta revisar la corrida.

| Resultado | Código |
| --- | ---: |
| Contrato aprobado, R equivalente y evaluación del bosque sin alerta | `0` |
| Diferencia detectada por el contrato | `1` |
| Solicitud o configuración inválida | `2` |
| Alerta del bosque, desacuerdo o evidencia insuficiente para aprobar | `3` |

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

[Revisión con R](r_review.md) · [Prueba ETL con recibos](first-acceptance-0.15.3.md) ·
[Fuente pública SERCOP](https://data.open-contracting.org/es/publication/110)
