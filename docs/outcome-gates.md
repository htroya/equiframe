# Explicit outcome gates

## Aceptación de cargas ETL

El [ejemplo de primer uso de 0.15.3](https://github.com/htroya/equiframe/blob/v0.15.3/docs/first-acceptance-0.15.3.md) genera
el lote, la referencia y solicitudes ejecutables para CI.

Ejecuta `equiframe verify accept request.json --reference-binding binding.json`
con el resultado esperado y el vínculo del generador de referencia.
Declara claves de negocio,
conservación de multiplicidad y comparación numérica exacta en el contrato.
El proceso acepta con código 0, rechaza una diferencia con 1 y devuelve 3
cuando falta la referencia o la comparación queda incompleta.

El informe guarda el alcance y el vínculo autorizado. Usa
`--require-execution` si también necesitas comprobar las ejecuciones
capturadas y el plan de cada salida. La aprobación se refiere al contrato y al
lote identificado en el informe.

Desde 0.14.5, la salida y la referencia deben estar en archivos distintos.
Si la misma ruta o un enlace duro apunta al mismo archivo, el código es 3.
Usa `--reference-binding binding.json` para exigir además las huellas
de la referencia, de las entradas del lote, del contrato y del plan.
El generador de referencia debe entregar este archivo por un canal que el
proceso que produjo la salida no pueda modificar. Consulta el
[formato de la vinculación](api.md#10-command-line-interface).

En la prueba temporal de 0.14.5, Isolation Forest detectó 9 de 24 fallos y
alertó en 3 de 36 lotes correctos. La comparación exacta detectó los 24 fallos y
aceptó los 36 lotes correctos. La prueba reservó los datos de octubre a diciembre
de 2025 para medir el resultado después de entrenar y calibrar con meses
anteriores. Consulta el [informe por mes y tipo de fallo](../validation/library_detection/results/temporal-0145/README.md).

Si la transformación conserva sumas, declara un `AggregateCheck` por las
claves de negocio sobre las filas que el filtro admite. Por ejemplo, un
control de suma por comprador y moneda detecta una redistribución aunque el
total general coincida. Conserva la comparación completa para exigir también
campos y multiplicidad. Consulta [reglas y comparación](api.md).

Para una salida agrupada aplica primero el filtro declarado a las entradas.
Después compara el conjunto de claves y la suma exacta en centavos. El ejemplo
instalado acepta los grupos válidos, rechaza un grupo omitido y señala un
centavo incorrecto. [Ejemplo de comparación agrupada](../examples/grouped_compare.py)

Puedes usar Isolation Forest para priorizar qué casos inspeccionar. La
comparación exacta establece la aceptación bajo el contrato. Una alerta
sobre una salida equivalente sigue disponible como diagnóstico; una
diferencia se rechaza incluso cuando el detector devuelve `no_alert`.
Puedes producir la referencia con SQL, Python o R. Identifica la fuente y
valida que la referencia cubra el mismo alcance que la carga.

En una repetición con el wheel 0.14.4 se probaron 144 casos del corpus
público de adjudicaciones, con 432 ejecuciones en Pandas, Polars y DuckDB.
Se seleccionaron 80 casos normales y 64 fallos controlados por cuotas
fijadas antes de puntuar. El esperado se calculó en Python desde las
entradas. Las tres rutas de ejecución coincidieron.

| Método | Fallos detectados (64) | Omisiones | Falsas alarmas (80 normales) |
| --- | ---: | ---: | ---: |
| Isolation Forest, modelo congelado del estudio 1.1 | 22 | 42 | 3 |
| Comparación exacta de sumas por comprador y moneda | 64 | 0 | 0 |
| Aceptación mediante comparación exacta completa | 64 | 0 | 0 |

Se probaron eliminaciones de grupo, escalados, redistribuciones y cambios de un
centavo. El resultado se refiere a ese conjunto y contrato. Las pruebas de CLI
cubren también duplicados, claves inesperadas, reordenamiento válido y ausencia
del esperado.
[Recibo del wheel y resultados por caso](../validation/library_detection/results/operational-0144/replay.json) ·
[Código de la repetición](../validation/library_detection/operational_replay.py)

Object presence, completed execution, observed equivalence, agreement with an
expected output and authorization to publish are different claims. A returned
object, empty output, empty alert list or generated report cannot supply the
missing claim.

## Python migration

The original private consolidation changed Python truth testing for the
operational types inventoried below; 0.12.0 retains that boundary. Previously
these objects inherited Python's
ordinary object truthiness: even a failed or unavailable result was truthy. They
now raise `TypeError` for `bool(result)`, `if result`, `assert result`, `not result`,
truth-tested `and`/`or` operands and `any`/`all` over result objects, in every state.
The exception names the type and points to explicit fields or the assertion API.
`ComparisonResult` and `EquivalenceDecision` already rejected truth testing;
their existing behavior and messages are preserved.

Review callers that used object truthiness for a gate. Replace it with the actual
required verdict; do not mechanically change an approval predicate into a
presence check. Existing evidence accepted solely because an object existed
must be reevaluated from its states, coverage and required dimensions.

Only a real optional-presence check should become `result is not None`:

```python
if pipeline.execution is not None:
    print(pipeline.execution.state)  # This merely displays available evidence.
```

For comparisons, keep the result and use the established gate:

```python
result = ef.diff(candidate, expected, keys=["id"], work_dir=work_dir)
report = ef.write_comparison_report(result, report_dir)
print(report.to_text())  # Reports can be generated for failed/incomplete results.
ef.assert_equivalent(result)  # Raises for different and not_evaluable.
```

A consumer of an `EquivalenceDecision` uses `.accepted` explicitly. A workflow
or migration consumer checks the dimensions its policy requires in addition to
technical completeness. The existing exit codes, defaults and semantic meanings
are unchanged; the guard introduces no implicit acceptance policy.

## Exact guarded inventory

These public classes reject truth testing. No new public base class is exported.

| Types | Explicit interpretation |
|---|---|
| `ComparisonResult` | `assert_equivalent(result)`, or the explicit state/completeness and guarantee policy |
| `EquivalenceDecision` | `.accepted`, with guarantee and evidence diagnostics |
| `ComparisonReport` | Presentation only; gate the original comparison |
| `GroupedComparisonResult` | `.complete`, modified/zero-reference metrics and explicit coverage; grouped sums do not establish row equivalence |
| `ExecutionResult` | `.state`; `completed` only establishes execution completion |
| `PipelineResult` | `.complete`, `.exit_code`, requested R/M/B/H and comparison outcomes |
| `MigrationResult` | `.state`, `.verification`, `.complete`, `.exit_code`; peer agreement alone is not expected-output correctness |
| `CompilationCheck` | `.supported`; support is preflight admission, not execution or equivalence |
| `VerificationResult` | `.operational_state`, `.publishable`, and explicitly required dimensions; `.publishable` is the existing operational result, not external authorization or scientific review |
| `VerificationCheck` | `.state`; `not_requested` and `pending_review` are not passed checks |
| `WorkflowResult` | `.complete`, `.exit_code` and required checkpoints |
| `WorkflowCheckpoint` | `.state` and the migration's explicit dimensions |
| `IngestionResult` | `.state`, accepted/quarantined counts and the declared ingestion policy |
| `RuleEvaluation` | `.decision`, `.complete`, `.coverage`; `no_alert` is not equivalence |
| `CheckResult` | `.state`, `.complete`, required/applicable coverage |
| `ProfileResult` | `.complete` and feature availability; a profile makes no approval decision |
| `DetectorScores` | `.state` and score values; scoring is not classification |
| `DetectorScoreResult` | `.m.state`, `.b.state`, `.rows`; M and B remain separate |
| `DetectionResult` | Individual `.m`/`.b` decisions and evaluated coverage |
| `ComponentDetectionResult` | `.decisions`, `.complete`, `.rows`; an empty batch cannot establish evidence about absent rows |
| `ComponentDecision` | `.decision`, `.complete`; `not_evaluable` is not `no_alert` |
| `DetectorDecision` | `.result.decision`, `.result.complete` and score/threshold |
| `HybridDecision` | `.result.decision`, `.result.complete`; H retains R OR M, not correctness |
| `RReviewResult` | `.state`, `.complete`, `.reason`; the language-R reviewer is independent of operational rules R, and unavailable R does not establish equivalence |
| `ReviewedDecision` | `.accepted`, `.result`, `.hybrid`, `.r_review`, optional `.comparison` and `.execution_binding`; existing alerts and comparator disagreement stay visible |
| `ReductionResult` | `.status`, `.baseline_verified`, `.minimality`; a reduction result is not validation of a transformation |

The scope is intentionally explicit. Contracts, options, schemas, artifact
references, table/profile data, compiled plans, fitted preprocessors/models,
calibration bundles, provenance declarations and stage bookkeeping keep their
existing behavior. They are not approval APIs. This change does not make
`FrozenModel` or every class with a `state` field reject truth testing. Fitted
bundles still require inspecting model/preprocessor/calibration availability
before their established inference APIs can be used.

`DatasetResult` holds loaded data and an optional owned DuckDB connection; it is
not an approval result and does not adopt these truth-value guards. Use its
`pandas`, `frame`, `target` and `info` fields for data access and `close()` or a
context manager for resource ownership. Successful file loading/conversion does
not establish equivalence of two independently written transformations.

## Empty and incomplete evidence

- Two empty tables can legitimately be equivalent under a contract that permits
  emptiness. This does not prove that the business expected any rows. Require an
  independently expected output or an explicit cardinality rule when appropriate.
- Ingestion can produce zero accepted records, including an empty completed
  input. Inspect counts and policy; an existing output artifact is not approval.
- Empty detector batches preserve their existing coverage semantics. They do not
  demonstrate that a required population was evaluated. Check required row coverage
  and each component's availability before interpreting absence of alerts.
- A comparison report preserves `different` or `not_evaluable`. Successful report
  publication does not change the comparison's verdict.
- Missing rules, unavailable features, cancelled work and partial detector
  availability retain their explicit states and diagnostics.

## Compatibility and verification

The guard is a field-free private Python mixin. Public names, import paths,
model fields, JSON schema, serialization, versions, canonical bytes and
fingerprint algorithms are unchanged. Existing persisted documents load into
the same public models and acquire the safer Python behavior. No historical
fixture is regenerated to make this change pass.

`tests/test_operational_truthiness.py` exercises real positive, discrepant,
failed, unavailable, empty and cancelled routes, serialization round-trips,
explicit inventory and unchanged configuration behavior. Existing native,
verification, evidence, schema/digest and immutable historical-reader tests
exercise the migrated internal presence checks. The installed executable example
`equiframe/examples/integrations/outcome_gates.py` demonstrates the gate outside
the source checkout with the identified wheel and its `arrow` extra.

After installing that wheel and its reviewed dependencies, extract and run the
example in a fresh working directory:

```bash
python -c "from importlib.resources import files; from pathlib import Path; Path('outcome_gates.py').write_bytes(files('equiframe').joinpath('examples/integrations/outcome_gates.py').read_bytes())"
python -I -O outcome_gates.py --work-dir outcome-evidence
```

The script exits zero only after observing the expected assertion verdict for
all four synthetic cases and verifying that implicit approval is rejected. Its
checks also run with Python assertions disabled (`-O`). Business correctness
requires a contract and a reference for the intended operation.
