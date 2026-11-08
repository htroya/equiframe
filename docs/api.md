# Public API reference

[Handbook](index.md) · [Choose an API](choosing-api.md) · [Semantics](semantics.md) · [Compatibility](compatibility.md)

Use `import equiframe as ef`. This reference describes the 0.12.0 implemented
entry points and their bounded stability contracts. Signatures below use Python notation;
`...` in a signature means the other documented optional arguments, not an
executable example. The exhaustive exported namespace is `ef.__all__` and its
per-name stability classifications are returned by `ef.get_stability_register()`.
A name being exported does not mean every input, platform or use is supported.

## Inspect the installed version, signatures and model fields

These commands work without a checkout and do not load optional engines merely
to inspect EquiFrame:

```python
import inspect
import equiframe as ef

print(ef.__version__)
print(inspect.signature(ef.diff))
print(ef.ComparisonOptions.model_json_schema())
print(ef.get_compatibility_policy().model_dump_json(indent=2))
for entry in ef.get_stability_register():
    print(entry.model_dump_json())
for capability in ef.get_adapter_capabilities():
    print(capability.model_dump_json())
```

Pydantic model fields are available through `Model.model_fields`, schemas through
`Model.model_json_schema()`, and JSON serialization through
`instance.model_dump_json()`. These helpers do not replace public cross-field
validation, artifact verification or declared compatibility rules. Models reject
extra fields and lossy coercions; Python collections are generally explicit
tuples where specified. Use `inspect.signature` for the complete installed
signature and Python `help` for entry-point descriptions.

## Explicit outcome objects

Operational result/check/decision models reject implicit truth testing. Use the
[exact inventory and migration guide](outcome-gates.md) to select each result's
state, completeness and acceptance fields; use `is not None` only for optional
presence. This is an intentional fail-closed Python behavior change. JSON fields,
format versions and fingerprints are unchanged.

## 1. Contracts, policies and serialization

| API | Behavior |
|---|---|
| `validate_contract(document) -> Contract` | Validate JSON text, UTF-8 bytes or a JSON-compatible mapping, including cross-field constraints |
| `read_contract(path) -> Contract` | Read a local file through the same validator |
| `write_contract(contract, path) -> None` | Revalidate and write canonical metadata bytes |
| `canonical_contract_bytes(contract) -> bytes` | Canonical metadata representation |
| `contract_fingerprint(contract) -> str` | SHA-256 of canonical contract metadata |
| `contract_json_schema() -> dict` | Structural Contract JSON Schema |
| `comparison_fingerprint(spec) -> str` | Identity of the complete `ComparisonSpec` |

Core model families:

- Schema: `Contract`, `TableSpec`, `TableSchema`, `ColumnSpec`, `KeySpec`,
  `GlobalKeyScope`, `TableKeyScope`, `ColumnKeyScope`
- Logical types: `BooleanType`, `IntegerType`, `StringType`, `DecimalType`,
  `FloatType`, `DateType`, `TimestampType`
- Policies: `NullPolicy`, `NaNPolicy`, `NumericPolicy`, `Tolerance`, `DatePolicy`,
  `TimestampPolicy`, `IgnoredOrder`, `SignificantOrder`, `SortSpec`
- Declarative checks: `PreconditionSpec`, `RuleSpec`, `SchemaCheck`, `KeyCheck`,
  `CardinalityCheck`, `JoinCheck`, `OrderCheck`, `AggregateCheck`
- Tagged values: `NullValue`, `NaNValue`, `InfinityValue`, `BooleanValue`,
  `IntegerValue`, `StringValue`, `DecimalValue`, `FloatValue`, `DateValue`,
  `TimestampValue`; `ScalarValue` is their declared union
- Artifact identity: `ArtifactRef`, `SchemaRef`, `Sha256`

Package version, `schema_version` and contract `revision` are independent.
Current public documents use their admitted format `1.0`; unknown versions,
duplicate JSON members, invalid UTF-8 and bare JSON NaN/Infinity are rejected.
`equiframe-metadata-json-v1` is EquiFrame's own canonicalization, not JCS/RFC 8785.
It retains defaults/nulls, array order, Unicode text and exact Decimal text.
Metadata fingerprints do not prove tabular equality or artifact authenticity.

## 2. Direct comparison

```text
diff(candidate, expected, *, contract=None, keys=None, policy=None,
     reference=None, options=None, capture_options=None, work_dir=None,
     cancellation=None) -> ComparisonResult

compare(left, right, *, contract, policy=None, options=None,
        reference="peer", work_dir=None, cancellation=None) -> ComparisonResult
```

`diff` directly admits eager pandas/Polars DataFrames, Arrow tables and actual
`DuckDBPyRelation` objects. Passing a relation authorizes consuming that native
plan once per supplied input. Capture fetches at most `max_rows + 1`, rejects
excess rows instead of truncating, checks each Arrow batch against byte limits,
and detaches the result. The caller retains connection/session ownership; no SQL
string or live connection is inferred as a table. Cancellation is cooperative
before execution and between batches, including native first-fetch limitations.
Without a contract it infers conservatively from the right-hand schema and defaults to
`reference="expected"`. With a contract it also supports the materialized
`compare` input routes. Inference without a contract is limited to these admitted
native inputs and `ArrowInput`.

`compare` requires a `Contract`; inputs are `ArrowInput`, local `ArtifactRef`,
local Arrow IPC **file**/Parquet `Path`, `TableArtifact` or completed
`ExecutionResult`. It never runs transformations. Two ExecutionResults must have
compatible verified input identities/parameters; comparing their explicit
TableArtifacts instead makes no same-input execution claim.

Typed reusable declarations:

```text
bag_contract(columns, *, policy=None, multiplicity="preserve",
             reference="expected", contract_id="diff", revision=1)
keyed_contract(columns, *, keys, incomplete="reject", policy=None,
               multiplicity="preserve", reference="expected",
               contract_id="diff", revision=1)
sequence_contract(columns, *, by, ties="preserve", policy=None,
                  multiplicity="preserve", reference="expected",
                  contract_id="diff", revision=1)
infer_diff_contract(reference_schema, *, keys=None, column_overrides=(),
                    policy=None, reference="expected")
read_diff_contract(result) -> DiffContract
```

These constructors return `DiffContract`, holding `.spec`, `.reference` and
field-level `.provenance`; `provenance_for(path)` uses a JSON Pointer.
`DiffContract.from_contract(contract, ...)` adapts an existing contract. Reuse
with `diff(..., contract=declaration)`; do not simultaneously override its keys,
policy or reference. `read_diff_contract` verifies the supplementary declaration's
format and links but does not rerun comparison or authenticate provenance labels.

`ComparisonResult` retains state, completeness, final/partial counts, captured
sources, applied policies, examples, diagnostics, contract/spec fingerprints and
the differences artifact. `read_comparison(path)` validates its manifest;
`iter_differences(result.differences)` verifies and iterates persisted records.
Differences expose code, key/position, column, typed values and multiplicities.
See [semantics](semantics.md) for key, bag and sequence guarantees.

`ComparisonOptions` controls batches, rows, work, SQLite/disk, approximate
matching, time and evidence. `DiffCaptureOptions` controls native capture
separately. They are cooperative budgets; [defaults and costs](performance.md)
are not hard resource quotas.

## 3. Explicit acceptance in tests and pipelines

```text
assert_equivalent(result, *, policy=None, evidence_root=None,
                  report_path=None) -> None
equivalence_decision(result, *, policy=None,
                     evidence_root=None) -> EquivalenceDecision
```

`assert_equivalent` returns only for accepted complete/final `observed_contract`
equivalence. `EquivalencePolicy` can require the reference role and reviewed
contract/spec hashes. Obtain those hashes from previously approved inputs;
copying them from an untrusted result is not a meaningful approval check.

Persistence is optional and requires **both**
`EquivalencePolicy(require_persisted_evidence=True)` and an explicit `Path`
`evidence_root`. It verifies the finalized manifest and difference evidence
within bounded permitted paths. Supplying only one is invalid. It does not
reexecute sources or certify full transformation reproducibility.

| Exception | Meaning |
|---|---|
| `EquivalenceDifferentError` | Complete differences |
| `EquivalenceNotEvaluableError` | Required judgment unavailable |
| `EquivalenceGuaranteeError` | Consumer's required hashes/reference not satisfied |
| `EquivalenceEvidenceError` | Required persisted evidence fails its checks |
| `EquivalenceInputError` | Invalid argument/model/policy configuration |

The first four derive from `EquivalenceAssertionError` (`AssertionError` and
`EquiFrameError`). Input errors derive from `ValueError` and `EquiFrameError`.
Use stable error codes, not prose message parsing. Decision `.accepted` is the
explicit machine-readable gate. `report_path` is only a caller-selected diagnostic
path; it is not opened or verified by the assertion.

## 4. Redacted comparison reports

```text
comparison_report(result, *, options=None, evidence_root=None,
                  declaration=None) -> ComparisonReport
write_comparison_report(result, directory, *, options=None,
                        evidence_root=None, declaration=None) -> ComparisonReport
read_comparison_report(path, *, max_bytes=2097152) -> ComparisonReport
```

`report.to_text()`, `report.to_html()` and notebook `_repr_html_()` share the same
filtered content. The public `render_comparison_text`, `render_comparison_html`
and `render_comparison_notebook` functions render that model. Default report
construction reads no files and hides values, names and paths.

`ReportOptions` selects `diagnostic`, `detail` or `reproduction`, explicit
`include_values`/`include_metadata`, `redact_columns`, examples and read/write
budgets. `evidence_root` explicitly permits bounded evidence inspection.
`require_exhaustive` requires both completed evaluation and verified complete
difference evidence, regardless of example limit. Required evidence can be
`not_satisfied` without changing the comparison's original verdict.

Writing requires a new directory and produces `report.json`, `report.txt`,
`report.html`, then `evidence-manifest.json`. Partial files without successful
publication are not a delivered report. `read_comparison_report` reads the view;
it does not verify a whole export's inventory. Reproduction requires explicit
value/metadata disclosure and supported complete materialized input captures;
it cannot reproduce arbitrary original SQL, ETL or services.

## 5. Explicit DuckDB capture

```text
capture_duckdb(sql, *, work_dir, name="result", connection=None,
               exclusive_connection=False, parameters=None, options=None,
               cancellation=None) -> TableArtifact
```

This stable, explicitly bounded entry point runs one trusted SELECT/WITH, checks native
types before Arrow and publishes detached Arrow IPC batches. `parameters` is a
mapping of bound values. It rejects unsupported native types rather than
silently losing distinctions. `DuckDBCaptureOptions` controls batch, row, byte
and cooperative time limits.

Without a supplied connection, it owns and closes a private connection. A borrowed
connection requires `exclusive_connection=True` and owner-disabled extension
autoload/autoinstall. It is not closed, configured, registered or committed by
this API; its result slot is consumed and an SQL error may require caller rollback.
The snapshot is reusable after the connection closes. Capture does not establish
a shared transaction across external systems and is not a SQL sandbox.

## 6. Registered native execution

```text
execute(plan, *, source, registry, adapter=None, artifact_store=None,
        work_dir=None, cancellation=None) -> ExecutionResult
```

`ExecutionPlan` holds a contract, engine, registered transformation ID/revision,
tagged parameters and `ExecutionOptions`. `TransformationRegistry` is explicit
and per-instance; `.register(...)` does not replace an existing identical key.

- `PandasTransformation(id, callback, code_version)` receives named DataFrames
  and `RunContext`, and returns a DataFrame
- `PolarsTransformation(id, callback, code_version)` receives native DataFrames
  and can return a DataFrame or LazyFrame; collection is explicit in execution
- `DuckDBTransformation(id, sql, code_version)` registers trusted SELECT/WITH;
  named `$parameter` values are bound from the plan

`code_version` is the caller's declaration, not an automatically computed hash
of callback behavior. Callbacks/plugins and dependencies may have external effects.

`SnapshotDataSource` consumes an explicitly pinned `SnapshotManifest` through
an injected `SnapshotClient`; both are now available from core alone. The
historical benchmark imports remain exact aliases. Metadata needs only base;
resolving data needs Arrow. See [extension ports](extending.md) for the complete
boundary, preservation rules and a runnable core-only example.

`DataSource` exposes `table_names` and `resolve(name, *, context) -> LoadedTable`.
`LocalDataSource` uses named `ArrowInput`, `PandasInput`, `PolarsInput` or local
artifact inputs. `EngineAdapter` exposes `engine`, `capabilities()` and native
`execute(transformation, inputs, context)`. `ArtifactStore` exposes
`put(path, *, media_type)` and `get(ref, destination)`; `LocalArtifactStore` verifies
local copies. `read_table(ref)` verifies size/hash before reading Arrow/Parquet.

`ExecutionResult.state` is `completed`, `invalid_input`, `failed`, `timeout`,
`resource_exhausted` or `cancelled`. **Completed only means execution and
materialization finished**. `execute` does not run preconditions, R, comparison
or anomaly detection. Operational failures inside a run preserve a typed problem;
invalid plans and evidence-creation/publication failures can raise directly.
`CancellationToken` and callback checkpoints are cooperative.

## 7. Rules, profiles, models and orchestration

| Family | Entry points and result types |
|---|---|
| Rules R | `evaluate_rules(execution, *, registry=None, options=None, work_dir=None, cancellation=None) -> RuleEvaluation`; `RuleRegistry`, `RuleOptions`, `read_rule_evaluation`, `iter_rule_findings` |
| Profiles | `profile_execution(execution, *, spec, options=None, work_dir=None, cancellation=None, conversions=()) -> ProfileResult`; `ProfileSpec`, `ProfileFeature`, `ProfileVector`, `read_profile` |
| Preprocessing | `fit_preprocessor(training, *, spec, empty_policy="drop")`; `transform_profiles(bundle, profiles) -> FeatureMatrix`; `read_preprocessor`, `write_preprocessor` |
| Fit | `fit_detectors(training, *, spec, config, support, empty_policy="drop") -> DetectorFit` |
| Score | `score_detectors(fit, profiles) -> DetectorScoreResult` |
| Calibrate | `calibrate_detectors(fit, calibration, *, alpha) -> DetectorBundle` |
| Infer | `detect(bundle, profiles) -> DetectionResult`; `detect_component(bundle, profiles, *, method)` for `isolation_forest` or `mad` |
| Hybrid | `combine_decisions(r, m) -> HybridDecision`; H is R OR M, without B |
| Persistence | `read_detector_bundle`, `write_detector_bundle`, `detector_fingerprint` |
| Pipeline | `run_pipeline(spec, *, source, registry, ...) -> PipelineResult`; `read_pipeline`, `inspect_evidence`, `verify_events`, `pipeline_summary` |
| Pipeline report | `render_report`, `write_report`; distinct from comparison reports |
| Reduction | `reduce_case(inputs, *, predicate, predicate_version, failure_signature, options=None, work_dir=None, cancellation=None)`; `read_reduction` |

Profiles, preprocessing and detector interfaces are stable within their declared
feature/version/support contracts. This does not promise statistical accuracy or
cross-version fitted-model parity. Standalone pipeline orchestration and
reduction remain experimental; shared pipeline models embedded in migration
retain their versioned format commitments.
Training/calibration wrappers (`NormalTrainingProfiles`,
`NormalCalibrationProfiles`) keep labels outside detector inputs; the benchmark
handles reviewed selection. An empty/unsupported component remains not evaluable.
Reduction invokes a **trusted** predicate with bounded row subsets, preserves
preconditions/signature and does not claim a global minimum.

## 8. Native migration, Verify and ETL

```text
check_migration(spec, *, compilers=None) -> tuple[CompilationCheck, CompilationCheck]
migrate(spec, *, source, work_dir=None, expected=None, compilers=None,
        adapters=None, rule_registry=None, detector_bundle=None,
        cancellation=None) -> MigrationResult
read_migration(path, *, verify=True) -> MigrationResult

verify(outputs, *, contract, expected=None, provenance=None, reviews=(),
       request_review=False, require_expected=False, require_rules=False,
       snapshots=None, plan_sha256=None, policy=None, options=None,
       work_dir=None) -> VerificationResult
verify_migration(path, *, work_dir=None, provenance=None, reviews=(),
                 request_review=False) -> VerificationResult

ingest_file(path, *, spec, work_dir, context=None, batch_rows=4096) -> IngestionResult
run_workflow(spec, *, source, work_dir, expected=None,
             cancellation=None) -> WorkflowResult
```

Migration models include `RelationalPlan`, `MigrationSpec`, `MigrationOptions`,
`MigrationRequest`, `MigrationResult`, `CompilerRegistry`, `PlanCompiler` and
`CompiledPlan`. `validate_ir`, `ir_fingerprint` and `native_compiler_registry`
cover the typed IR/compilers. The [semantics chapter](semantics.md) lists its
bounded operations and native limitations.

Migration `.state` is peer equivalence; `.verification` is `correct`, `divergent`,
`not_evaluable` or `not_requested` against the supplied expected output. `.complete`
and `.exit_code` reflect requested stages. Comparison with a declared expected
output alone does not prove its authorship, independence or correctness.

Verify keeps input validity, technical completion, integrity, agreement,
expected-output checks, rules, coverage and independent review separate.
`ExpectedProvenance` and `IndependentReviewEvidence` declare reviewed evidence;
JSON reviewer names are not authenticated identities. `read_verification` and
`verification_summary` inspect finalized records without rerunning ETL.

ETL models include `FileInput`, `IngestionSpec`, `IngestionResult`,
`IngestionConversionReceipt`, `WorkflowSpec`, `WorkflowStage`,
`WorkflowInputBinding`, `WorkflowRequest`, `WorkflowResult`, `Destination`,
`ParquetDestination` and `LoadReceipt`. Ingestion uses explicit CSV/JSON/JSONL
schema/grain/path rules and retains original sources/quarantine receipts.
[CSV/JSONL batching](ingestion.md) limits accepted-value arrays, with complete
receipt tuples retained; full JSON and execution inputs still materialize.
`FileInput(path, spec, batch_rows=4096)` accepts the same positive integer knob.
Workflows fix inputs and native checkpoints, retain failed/skipped stages and
have no resume guarantee. Local Parquet publication is a separate verified
workflow; it does not implement a shared production data gateway.

## 9. Portable evidence

```text
export_bundle(source, destination) -> EvidenceBundle
import_bundle(source, destination, *, expected_sha256=None) -> EvidenceBundle
read_bundle(path, *, expected_sha256=None) -> EvidenceBundle
```

`inspect_bundle` provides a summary of the verified inventory. Supported sources
are finalized migration, verification and workflow evidence. The bundle retains
historical bytes and resolves old references only to captured members with
matching size/hash; it does not execute callbacks. An independently trusted
`expected_sha256` pins the bundle manifest. Absolute local paths elsewhere do
not become portable automatically. Benchmark study bundles are a separate API.

## 10. Command-line interface

Use `python -m equiframe --help` or the installed `equiframe` command. Subcommand
`--help` is the authority for exact installed parameters. Examples below show
request **shapes**; supply your own validated JSON and local artifacts:

```text
equiframe contract validate contract.json
equiframe compare comparison-spec.json candidate.arrow expected.arrow --expected --output comparisons
equiframe migration validate migration-spec.json
equiframe migration run migration-request.json --output migrations
equiframe migration verify migrations/migration_ID
equiframe verify validate verification-request.json
equiframe verify run verification-request.json --output verifications
equiframe verify migration migrations/migration_ID --output verifications
equiframe verify inspect verifications/verification_ID
equiframe ingestion run ingestion-spec.json input.csv --output ingestion
equiframe dataset inspect ventas.json
equiframe dataset load ventas.json --target polars
equiframe dataset load libro.xlsx --sheet Ventas --target duckdb
equiframe workflow validate workflow-request.json
equiframe workflow run workflow-request.json --output workflows
equiframe workflow inspect workflows/workflow_ID
equiframe bundle export migrations/migration_ID portable-bundle
equiframe bundle verify portable-bundle
equiframe bundle import portable-bundle imported-bundle
```

Pipeline `run`, `report`, `evidence verify` and `reduce` are also available;
explicit factory references load **trusted code** and are not safe for arbitrary
untrusted modules. `report` is the pipeline reporter, not a comparison report CLI.

| Command category | Exit meaning |
|---|---|
| `compare` | 0 accepted complete equivalence; 1 complete difference; 2 invalid input/configuration; 3 not evaluable/failure |
| Operational `run`, migration/workflow run, Verify run/migration | 0/1/2/3 distinguish successful requested checks, alert/difference/failure of checks, invalid input and unavailable/incomplete work as documented by that command |
| Integrity `inspect`/`verify` | 0 intact evidence, including a historically failed/partial run; 3 invalid evidence; argument errors may be 2 |
| `contract validate` | 0 valid metadata; 2 invalid arguments/JSON/contract/version; 3 I/O failure |
| `ingestion run` | 0 complete; 1 quarantined/rejected records; 2 invalid input; 3 technical failure |
| `dataset load` / `dataset inspect` | 0 complete bounded reading and requested conversion; 2 invalid arguments/configuration; 3 unavailable dependency or technical failure. Zero is not semantic equivalence |
| `reduce` | 0 reduced/unchanged; 2 invalid input; 3 failure/limit, not a global-minimum claim |

Operational failures write the original machine-readable code on the first
stderr line, followed by one fixed-text `hint[category]: ...` line. Categories
distinguish missing paths, existing outputs, permissions, invalid documents,
optional dependencies, unsupported capabilities and resource limits. Scripts
should use the exit code and first line, rather than match the whole message.
Hints do not include exception text, input values or local paths. The existing
`contract validate` command retains its structured validation locations and
codes; completed commands retain their existing stdout format.
Dataset reading/configuration errors may add explanatory text and, for an
unresolved choice, a JSON object with `required_option` and `choices` after the
stable code and hint. Scripts should not treat those later lines as a new
success/error protocol or parse their human-readable prose.

Never treat every command's zero as data equivalence. Never suppress nonzero exit
codes in CI without preserving the underlying failure. `--help` normally exits 0.
The historical `equiframe.benchmark` helper is **unsupported and quarantined**:
its helpers raise `UnsupportedBenchmarkError`; CLI exits 2 except help. Use the
separate experimental package only within its documented scope.

## 11. File discovery, Pandas loading and data conversion

```text
load_dataset(source, *, target="pandas", options=None) -> DatasetResult
inspect_dataset(source, *, options=None) -> DatasetInfo
convert_dataset(dataset, *, target) -> DatasetResult
```

These stable, capability-bounded APIs read local JSON/JSONL, Excel, TXT, XML, CSV, Parquet and
GeoJSON files into a real Pandas DataFrame. `target="polars"` or `"duckdb"`
converts that same DataFrame to the requested native engine. This is data
conversion; it does not translate transformation code or simulate independent
native executions. Full conversion readback rejects representation loss.

`DatasetReadOptions` exposes optional format/encoding, sheet, record path,
delimiter/header, text mode, conservative type inference, per-column explicit
types and admission budgets. `DatasetChoiceRequired.option` and `.choices`
identify an ambiguity the caller must resolve. No arbitrary file reader,
callback or dependency installation is executed from configuration.

`DatasetResult.pandas` is the original loaded frame; `.frame` is the native
destination; `.target` identifies it; `.info` describes rows, columns and
inference. `DatasetInfo.to_dict()` omits original metadata unless
`include_metadata=True` is requested. DuckDB uses a private in-memory connection
owned by the result: keep it open while using the relation and release it with
`close()` or `with`. `to_parquet(path)` exports the loaded Pandas data to a new
file; it does not export later operations on the destination frame. Publication
uses a synced sibling temporary file and an exclusive same-filesystem hard link;
an unsupported filesystem fails without falling back to a partial copy. See the
file guide for cleanup and recovery if an error occurs after publication.

`DatasetSource(uri, format, sha256, size_bytes, read_options_json)` records the
single byte snapshot actually consumed and the effective reading options;
`.read_options` exposes the decoded options. `DatasetProvenance` combines that
source, `pandas_sha256`, `target` and `target_sha256`. The result and its `info`
expose `.provenance`; `info.to_dict()` includes it only with
`include_provenance=True`, separately from original metadata. Conversion/export
reject a modified original Pandas frame instead of reusing an outdated source
identity. Hashes identify observed content and options, not trusted authorship.

`equiframe dataset load file` asks for the target in the same interactive
invocation. Noninteractive callers pass `--target pandas|polars|duckdb`; reading
choices can also be supplied explicitly. `dataset inspect` only describes the
loaded data. Without `--output` the CLI object exists only for the duration of
that command; Python callers receive the objects directly.

See [file loading and conversion](lectura-conversion.md) for exact supported
layouts, Decimal/identifier preservation, explicit `json` representation,
XML/Excel boundaries, resources and dependency extras.

## 12. Optional independent review in the R language

```text
review_with_r(left, right, *, contract, comparison=None, options=None,
              cancellation=None) -> RReviewResult
finalize_with_r(rules, model, *, left, right, contract, comparison=None,
                options=None, cancellation=None) -> ReviewedDecision
finalize_execution_with_r(execution, rules, profile, detection, *, comparison,
                          options=None, cancellation=None) -> ReviewedDecision
```

The optional reviewer implements exact comparison a second time in base R
over the complete observed tables and admitted contract. It does not consume
Python's verdict as its expected answer, retrain Isolation Forest, replace
operational rules R or establish an independent business oracle O.
Its interface and explicit unavailable/error states belong to the stable
[compatibility contract](compatibility.md); its admitted type/policy subset
remains narrower than arbitrary comparison contracts.

`RReviewOptions` configures a local, user-installed `Rscript`, cooperative
timeout and capture/transport budgets. `RReviewResult` exposes `.state`,
`.complete`, `.reason`, row accounting, source/specification/transport hashes
and the observed R version. Missing R, unsupported policy, cancellation, timeout
and technical failure produce `not_evaluable`; invalid API options/contracts
raise their validation errors. There is no automatic R/package installation.

`finalize_with_r` preserves H = rules OR Isolation Forest and all alerts from
the optional previous Python comparison. Its `ReviewedDecision` keeps the
components, comparator disagreement and explicit final `.result`/`.accepted`.
An unavailable required component cannot become acceptance, and equivalent R
outputs cannot erase an existing rule/model/comparison alert. Both result
models reject implicit truth testing.

Use `finalize_execution_with_r` for the execution-bound route: pass the actual
`ExecutionResult`, its `RuleEvaluation` and `ProfileResult`, and a
`ComponentDetectionResult` obtained with
`detect_component(bundle, (profile.vector,), method="isolation_forest")`.
It checks execution/contract/artifact/profile identities and IF association,
then reads the comparison's verified artifacts directly. Invalid associations
raise validation errors before R starts. `.execution_binding` records the
`RExecutionBinding` identities of the execution, profile, detection and output.

When `comparison` is supplied to `review_with_r` or the low-level finalizer,
its actual artifacts are verified and its full observed inputs must match the
transport sent to R. `RReviewResult.binding` records `RReviewBinding` with the
comparison ID and both artifact hashes. A standalone review without a Python
comparison does not invent that binding. `finalize_with_r` remains low-level:
the caller owns the association of isolated `ComponentDecision` inputs.

See [independent R review](r_review.md) for input binding, policy restrictions,
resource ownership and interpretation of final acceptance. This is a Python
API; there is no separate R-review CLI command.


## Native IR additions in 0.12.0a6

See the [executable contract reference](migration-ir.md) for `EquiJoin.cardinality`,
right/full joins, `Deduplicate.keep="first"` and its deterministic `by`,
`DecimalRound`, Decimal `Arithmetic` multiply/divide, and `LocalizeTimestamp`.
These expression models are stable public exports in 0.12.0. Engine-specific
rejections remain part of the capability contract, not fallback behavior.
