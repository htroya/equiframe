# Choose the smallest existing API

[Handbook](index.md) · [Inicio en español](inicio.md) · [API reference](api.md) ·
[Eight runnable journeys](journeys.md)

The compatibility facade retains its public models and entry points; the current
name inventory is `ef.__all__`. Most comparison applications start with `diff`,
`assert_equivalent` and `comparison_report`; none require
adopting a new framework. Models, extension ports and advanced services stay
available under their current imports. No facade names are hidden, renamed or
deprecated by this navigation guide.

## Start with the object you already have

| You have | Use | Inspect or accept |
|---|---|---|
| A local JSON, Excel, TXT, XML, CSV, Parquet or GeoJSON file | `load_dataset`, optionally `inspect_dataset` | Original Pandas frame, structure, inferred types and explicit read choices; no semantic approval |
| A `DatasetResult` currently holding Pandas, Polars or DuckDB data | `convert_dataset(..., target=...)` | Select any of those three destinations, consume the current native frame and preserve the captured source identity; no translated program |
| Two eager pandas/Polars DataFrames or Arrow tables | `diff` | `read_diff_contract`, then `assert_equivalent` |
| An explicitly supplied `DuckDBPyRelation` and another admitted native input | `diff` | Authorize bounded consumption of that relation; the caller owns its connection and native plan |
| Materialized Arrow/Parquet or captured `TableArtifact` | `compare` with explicit `Contract` | `comparison_report`, then `assert_equivalent` |
| A trusted DuckDB SELECT/WITH and exclusive connection ownership | `capture_duckdb`, then `compare` | Detached capture and explicit contract |
| A trusted native callback/SQL implementation | `execute` with registry/source | Execution only; compare or Verify separately |
| A supported relational IR for two engines | `check_migration`, then `migrate` | Separate `.state`, `.verification` and `.complete` |
| Outputs plus a reviewed expected and provenance | `verify` | Technical agreement, expected, rules and review dimensions |
| Two admitted eager outputs or explicitly supplied DuckDB relations, with an explicit contract | `review_with_r` | Independent base-R comparison of the captured data; relation submission authorizes bounded native-plan consumption; inspect `.state` and `.complete` |
| Rules/Isolation Forest decisions and the same observed outputs | `finalize_with_r` | Preserve alerts and comparator disagreement; inspect `.accepted` and component availability |
| A captured execution, its rules/profile, one-profile IF detection and a comparison including that output | `finalize_execution_with_r` | Verify identities/artifacts and inspect `.execution_binding`, `.accepted` and component availability |
| CSV/JSON/JSONL with declared source/schema rules | `ingest_file` | Accepted/quarantined records and source/conversion receipts |
| Several bounded migration checkpoints | `run_workflow` | Stage statuses, failure isolation and expected checks |
| A pinned external data-client snapshot | `SnapshotDataSource` | Manifest/bytes/schema validation; client owns transport |
| Finalized migration/Verify/workflow evidence | `export_bundle`, `import_bundle` | Closed-inventory integrity; no ETL reexecution |

`diff` compares captured outputs. Supplying an actual `DuckDBPyRelation`
explicitly authorizes bounded consumption of its native plan; SQL strings,
connections, consumable readers and Polars lazy frames are not inferred as data.
`compare` does not infer an arbitrary file's semantics. Native migration is not arbitrary Python
translation. Prefer the original engine/orchestrator when it already performs the
work, then compare its materialized result. [API](api.md) is the authoritative
signature reference; use `inspect.signature(ef.diff)` in the installed interpreter.

For file loading, [the file guide](lectura-conversion.md) explains conservative
inference, Excel sheets, nested records, text choices, optional dependencies and
DuckDB resource ownership. The [R review guide](r_review.md) lists its exact
admitted policies, input associations and explicit unavailable states. The R
language is separate from the letter R used for operational rules.

## Four dimensions that must stay separate

1. **Execution:** `completed` says registered code finished and was captured
2. **Agreement:** `equivalent` says outputs satisfy the evaluated contract
3. **Expected result:** `correct`/`divergent` concerns a declared reference whose
   business correctness and independence still need justification
4. **Evaluability:** every required incomplete/unavailable component stays visible

Do not use a report, successful process exit from an integrity reader, empty
findings, `bool(result)` or engine agreement as a replacement for the intended
acceptance gate. Anomalies R/M/B/H and independent verification O remain separate.
Pandas is never an oracle by virtue of being the first engine.

## Integrate into an existing orchestrator

Call the Python API from a task that owns a new private output directory, then
persist its result location and apply the explicit gate before its downstream
publication step. Bind supplied files/snapshots to fixed identities. A retry gets
a new run directory; it must not overwrite evidence or silently rerun a callback
with external effects. Let the orchestrator own its process quotas, timeout,
secrets, concurrency and retry policy. EquiFrame's budgets are cooperative.

For a command task, preserve the CLI command's meaning. Comparison/run commands
separate 0 accepted/completed scope, 1 differences/alerts, 2 input/preflight errors,
and 3 failed/partial/unavailable evaluation as documented for that command.
Integrity readers can return zero for valid evidence describing a failed run;
apply the stored semantic gate separately. [API CLI reference](api.md) and
[fast CI](fast-ci.md) show the boundary without requiring a deployed service.

## Discover advanced types without importing engines

`ef.get_stability_register()` classifies every public name and supported surface;
`ef.get_adapter_capabilities()` separates capture, comparison, native execution
and migration. These descriptions are not admission checks or platform test
results. `Model.model_fields` and `Model.model_json_schema()` support typed editing
and inspection. Use the [tested compatibility scope](compatibility.md) and each
actual preflight/result, rather than treating export count as capability count.
