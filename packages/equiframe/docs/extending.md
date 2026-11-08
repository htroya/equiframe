# Integrating your own data and implementations

[Handbook](index.md) · [API](api.md) · [Semantics](semantics.md)

Start with the smallest boundary you need. `diff` compares already-materialized
results without adopting the execution runner. Use an explicit source/adapter or
compiler only when you need EquiFrame to capture or execute your integration.
The core does not import the benchmark, a cloud provider or a domain warehouse.

## Reuse a pinned snapshot with core alone

`SnapshotClient`, `SnapshotDataSource`, `SnapshotColumn`, `SnapshotTable`,
`SnapshotManifest` and `snapshot_fingerprint` are available through `equiframe`
and `equiframe.snapshot`. These core exports are experimental. The existing
`equiframe_benchmark` and `equiframe_benchmark.snapshot` imports remain exact
aliases; no migration of historical manifest format 1.0 is required.

The base installation can construct/validate manifests without Arrow, a native
engine or the benchmark. Resolving data needs the `arrow` extra. Executing a
native transformation additionally needs its corresponding engine extra. No
new base dependency, remote transport or implicit plugin discovery was added.

A client implements two methods:

- `get_snapshot(snapshot_id: str) -> SnapshotManifest`
- `download_artifact(ref: ArtifactRef, destination: Path) -> None`

The client owns authentication, transport timeouts and service coordination.
The source fetches the manifest once at construction, refuses `latest`, pins its
identity/revisions and optionally selects a declared subset of tables. Each
resolve downloads to a fresh private run directory and verifies bytes, SHA-256,
row count, names/order and declared physical/logical types before returning a
`LoadedTable`. It records the complete manifest identity even for a selection.
A failed client is not retried silently. The provider must supply genuine
immutable snapshots; the consumer cannot make a mutable service immutable.

The source-distribution example `examples/snapshot_source.py` is self-contained.
After installing the identified core wheel with the `duckdb` extra and copying
the example outside the checkout, run:

```bash
python snapshot_source.py --output fresh-snapshot-example
```

It uses an injected in-memory client and synthetic Arrow IPC bytes, executes a
native DuckDB identity transformation, then checks exact Decimal, NULL and
multiplicity against a literal synthetic table. It needs no benchmark, credentials
or network service. This is a technical integration example, not acceptance of a
real service or independent human verification.

The snapshot manifest retains its historical ASCII-escaped canonical JSON and
fingerprint algorithm. Do not substitute contract canonicalization, rename fields,
normalize strings or rewrite older evidence to make an integration fit.

## A complete external SQLite producer

The [SQLite snapshot integration](sqlite-snapshots.md) implements this same port
outside core with a native owned read transaction, explicit Arrow schemas and
immutable detached bytes. Its executable examples and tests demonstrate a fixed
multi-table snapshot during a committed WAL update, exact Decimal/NULL, explicit
differences and failed byte/schema validation. It is a local reference adapter,
not a claim of portable isolation semantics across arbitrary DB-API drivers.

## Choose an extension port

For CSV/JSON/Parquet, read-only SQLite, API responses, typed Arrow batches and
composition of multiple explicit providers, see [universal inputs](universal-sources.md).
External inputs can implement `load(context) -> LoadedTable` and be passed to
`LocalDataSource`. Existing `DataSource` providers can be bound through
`CompositeDataSource` without changing core or discovering plugins at import.

| Boundary | Implement or register | Responsibility |
|---|---|---|
| Captured input | `DataSource` (`table_names`, `resolve`) | Fixed table identity, faithful `LoadedTable`, explicit failure |
| Artifact storage | `ArtifactStore` (`put`, `get`) | Declared bytes/format and verified hash/size |
| Native execution | `EngineAdapter` plus `TransformationRegistry` | Your native implementation, declared capabilities and actual output metadata |
| Bounded relational migration | `PlanCompiler` plus `CompilerRegistry` | Validate/support the declared IR and compile a genuine native transformation |
| Additional rules | `RuleRegistry` | Evaluate one execution within its declared applicability and budgets |
| Local publication | `Destination` | Honor verification, idempotency and publication semantics |

`PlanCompiler.compile` is a lower-level extension operation: a compiled
transformation assumes its actual inputs match the validated IR contract.
`migrate` enforces the physical/value admission before running either engine.
Calling the compiled transformation through `execute` alone does not reproduce
that preflight. Native casts can change mismatched input data; `completed` only
records execution/materialization and establishes no equivalence or correctness.

Use explicit instance-owned registries. Registration does not prove support;
preflight validation and execution still enforce the contract. Do not place
callback/module names into JSON and expect them to be imported. This library is
not a sandbox for untrusted extensions.

## Preserve the complete loaded-table boundary

A `LoadedTable` can carry an Arrow table, native column types, an index,
`meaningful_index`, source reference and notes. Preserve those fields when
wrapping an existing source. Keeping only `.table` or a data-file reference can
lose the distinction between native and transport types or silently discard an
index. Meaningful indexes remain unsupported for the current migration IR and
must be rejected; do not drop one to make migration pass.

Generic workflows capture each external source once. Independent stages can
continue after another source fails under `skip_dependents`; their declared
resource limits remain enforced separately. A shared-source capture uses the
permitted consumer envelope, followed by each stage's own limits. Missing or
invalid inputs never become empty successful tables.

## Bounds you still own

Source resolution, callbacks and Arrow decoding can allocate memory before a
cooperative checkpoint. `RunContext` cancellation, time and byte budgets do not
preempt a blocked network call or impose a hard process-memory quota. Snapshot
manifest fetching precedes run budgets. Use bounded clients and an appropriately
isolated execution service when you need aggregate quotas or hard timeouts.

Data-service publication, writer coordination, retention, backups and domain
mapping remain external responsibilities. The separate SERCOP/DW scripts in the
repository are owner-maintained prototypes, excluded from the two distributable
packages. Neither this port nor those scripts establish production readiness,
accepted real DW integration or support for every Python platform/data type.

## Arrow/Parquet partitions and external-source boundaries

The current `DataSource.resolve` and `TableInput.load` ports return an eager
`LoadedTable`; `ArtifactInput` verifies one local Arrow IPC or Parquet file and
then materializes its table. A directory of Hive partitions or a remote object
prefix is not an accepted `ArtifactRef`. Do not present those interfaces as a
streaming dataset scanner.

The existing comparison reader already iterates Arrow record batches and Parquet
batches under `ComparisonOptions.batch_rows`, and spills comparison partitions
to private SQLite. New [CSV/JSONL ingestion batches](ingestion.md) emit a normal
multi-batch Arrow IPC artifact that this reader can consume without a new file
format. An IPC record batch or Parquet decode may allocate before a checkpoint;
these are cooperative bounds. `read_table` and execution remain eager.

An application can use the existing explicit source port to capture its own
partitioned dataset, but must pin the complete fragment inventory, versions,
schemas, multiplicity and order policy, verify every fragment, and return the
complete declared table. Comparing partitions separately can miss cross-partition
keys, duplicates or moves. No new partition-directory connector, implicit
partition-column coercion, concatenation protocol or distributed executor is
implemented or needed for the bounded local ingestion change.

SQLite remains the implemented external-producer reference described above:
a single owned native read transaction, explicit schemas, detached immutable
Arrow bytes and the existing `SnapshotClient` contract. Its supported schema,
size limits and consistency tests are specific to that producer. They do not
establish PostgreSQL isolation or a generic DB-API connector.

No requested source, schema or credentials demonstrate a need for new Excel,
PostgreSQL or object-storage connectors in this change. Those remain external
extensions, not installed capabilities. An Excel producer must declare formula
versus cached values, cell types and textual identifiers; PostgreSQL needs an
owned consistent multi-query snapshot and exact type mappings; object storage
needs a fixed inventory/version identity, bounded transport and verified bytes.
Use existing `DataSource`/`SnapshotClient` ports if such a concrete consumer is
provided. None of this changes the data-service or domain-warehouse ownership.
