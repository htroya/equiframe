# Orquestación y automatización en 0.8.0

## Python y notebooks

Se reutilizan contratos, fuentes y registros de los pasos anteriores:

```python
import equiframe as ef
from pathlib import Path

spec = ef.PipelineSpec(
    execution=plan,             # ExecutionPlan del consumidor
    profile=profile_spec,       # ProfileSpec compatible con el bundle
    comparison_reference="expected",
)
result = ef.run_pipeline(
    spec, source=source, registry=registry,
    detector_bundle=bundle,     # ya ajustado/calibrado, opcional
    comparison=expected,        # ArrowInput/ArtifactRef/Path/captura, opcional
    work_dir=Path("equiframe-runs"),
)
print(result.complete, result.exit_code)
print(ef.pipeline_summary(result))
verified = ef.read_pipeline(Path("equiframe-runs") / result.pipeline_id)
```

El fragmento ilustra integración con objetos del consumidor, no crea datos ni
modelos ficticios. El [ejemplo completo](../packages/equiframe/examples/pipeline_local.py)
crea datos sintéticos, ejecuta DuckDB, verifica evidencia y reduce un caso. Usa
`import equiframe` desde la distribución instalada; el verificador del wheel lo
copia y ejecuta fuera del checkout. El extra `duckdb` es suficiente para ese
ejemplo. Inferencia de un bundle compatible no requiere instalar scikit-learn;
su entrenamiento sí requiere el extra `ml`.

`adapter`, `rule_registry`, `cancellation` y `conversion_provider` permiten
extensión por inyección. Este último recibe la captura y devuelve recibos reales
de conversiones instrumentadas; no se infieren fallos de conversión desde nulos.
No se ejecuta una transformación otra vez para generar perfiles o comparar.

## CLI operacional

Una petición JSON `PipelineRequest` contiene `spec`, bindings `name/artifact` y
referencia opcional `comparison`. Arrow/Parquet se identifican por URI local,
tamaño y SHA-256. Los formatos se generan en `schemas/`. El JSON no admite SQL,
callbacks, plugins, etiquetas o credenciales de autenticación.

El consumidor proporciona un módulo Python confiable accesible en su entorno:

```python
# mi_etl.py
import equiframe as ef

def registry():
    result = ef.TransformationRegistry()
    result.register(ef.DuckDBTransformation(
        "identity", "SELECT * FROM source", "mi-etl.1",
    ))
    return result
```

```bash
equiframe run request.json --registry mi_etl:registry --output runs
equiframe run request.json --registry mi_etl:registry --bundle model.json --output runs
equiframe compare comparison-spec.json left.arrow right.arrow --expected --output runs
equiframe evidence verify runs/pipeline_ID
equiframe report runs/pipeline_ID --output nuevo-reporte
```

El módulo es código del consumidor expresamente seleccionado. No es un sandbox;
no se importan registros encontrados automáticamente ni nombres desde JSON.

| Código run/compare | Significado |
|---|---|
| 0 | Evaluaciones solicitadas completas, sin alertas/diferencias observadas |
| 1 | Evaluación completa con alerta R/M/B/H o diferencia |
| 2 | Configuración/JSON/argumentos inválidos, o ejecución `invalid_input` |
| 3 | Fallo técnico, componente solicitado no evaluable, cancelación o recursos |

La incompletitud tiene prioridad sobre una alerta; esta se conserva en el JSON.
Código 0 no confirma corrección científica. `evidence verify` devuelve 0 cuando
la evidencia final es íntegra, aunque describa un fallo o alerta; devuelve 3 ante
integridad fallida o carpeta interrumpida. `report` devuelve 0 si creó un informe
nuevo desde evidencia verificada. Ninguno reescribe la corrida original.

## Archivos de una corrida

```text
pipeline_UUID/
  pipeline.json       # configuración estricta
  environment.json    # versiones/plataforma, sin variables del entorno
  events.jsonl        # cadena append-only, una escritura sincronizada por evento
  execution.json      # captura y procedencia del motor, si disponible
  rules.json          # evaluación R, si disponible
  profile.json        # observaciones/denominadores, si solicitados y disponibles
  detector-bundle.json / detection.json  # solo si corresponden
  comparison.json     # comparación opcional
  hybrid.json         # R OR M y completitud
  report.json / report.html
  run_.../ rules_.../ profile_.../ comparison-.../  # artefactos de componentes
  manifest.json       # publicado al final, inventario y resultados enlazados
```

Una publicación fallida deja archivos parciales y eleva una excepción: no hay
manifiesto final válido. No se admite reanudar ni reemplazar la misma carpeta;
una nueva llamada crea otra. Las URI de las capturas siguen siendo absolutas;
mover carpetas no relocaliza automáticamente los artefactos para reejecutar.
Los reportes omiten datos tabulares; los artefactos completos requieren manejo
privado. Los límites de confianza están en el [diseño](STEP_08_DESIGN.md).

## Reductor

```python
reduced = ef.reduce_case(
    inputs,                              # mapping nombre -> ArrowInput
    predicate=reproduce_target_failure,  # verifica precondiciones y el fallo exacto
    predicate_version="my-check.1",
    failure_signature="duplicate.customer-id",
    options=ef.ReductionOptions(max_evaluations=100, timeout_seconds=60.0, confirmations=2),
    work_dir=Path("equiframe-runs"),
)
print(reduced.status, reduced.minimality, reduced.evaluations)
```

El predicado devuelve `ReductionObservation(preconditions="satisfied",
failure_signature="duplicate.customer-id")` solo si reproduce el fallo objetivo.
Si no lo reproduce, devuelve `failure_signature=None`. Si las precondiciones
fallan o no pueden comprobarse, usa `violated` o `not_evaluable`, sin firma.

```bash
equiframe reduce request.json --predicate mi_etl:reproduce_target_failure \
  --predicate-version my-check.1 --failure-signature duplicate.customer-id \
  --max-evaluations 100 --timeout-seconds 60 --confirmations 2 --output runs
equiframe evidence verify runs/reduction_ID
```

La CLI devuelve 0 si termina la búsqueda con `reduced/unchanged`, 3 si el caso
inicial no confirma el fallo, se agota un presupuesto, se cancela o falla el
predicado; 2 para configuración inválida. Las tablas reducidas son referencias
verificables y `retained_positions` conserva las posiciones de origen.
No hay afirmación de mínimo global. Cada ejecución crea una carpeta nueva.

## Benchmark separado

```bash
equiframe-benchmark validate catalog.json --splits splits.json
equiframe-benchmark split catalog.json --output nuevos-splits.json --seed 8 \
  --training 3 --calibration 1 --test 2
equiframe-benchmark pilot --output benchmark-runs
```

`pilot` crea `pilot_UUID` y permite relanzar sin sobreescribir. El comando previo
`equiframe-benchmark-pilot --output directorio-nuevo` conserva su semántica.
Validar catálogo/splits no confirma revisiones ni congela un experimento. Las
quince ejecuciones nativas del piloto ya pasan por `run_pipeline`; no se entrena
un detector científico con los perfiles de este piloto sin soporte revisado.
