# Inputs from files, SQL and API responses

`LocalDataSource` accepts existing `FileInput` (CSV/JSON/JSONL), `ArtifactInput`
(hashed Parquet/Arrow), `ArrowInput` and the new experimental `SQLiteInput` and
`StreamInput`. Every input exposes `load(context)` and produces a `LoadedTable`.
Use the same declared columns, null, Decimal and timestamp policies regardless
of where the data came from. Ingestion retains original bytes and conversion
receipts; a rejected or quarantined input fails execution.

`SQLiteInput(path, query, spec, parameters=(), batch_rows=4096)` reads one trusted
parameterized SELECT/WITH in an owned read-only transaction. Its `IngestionSpec`
uses JSONL with direct record mappings. Decimal fields require SQLite TEXT;
REAL cannot recover exact monetary values. Textual identifiers, duplicate rows
and NULLs remain visible. BLOB and ambiguous column names are rejected. It does
not manage a remote warehouse or claim another database provider's isolation.

`StreamInput(open_stream, spec, expected_sha256=None, batch_rows=4096)` consumes
an explicitly injected binary response context manager. The caller implements
API authentication, transport and timeouts. EquiFrame never opens an implicit
URL. It closes the response on success or failure, checks byte budgets and an
optional separately supplied digest, then uses the existing typed ingestion.
Blocking transport calls remain the caller's responsibility. JSON documents
still materialize; CSV/JSONL parsing is incremental. Final tables and public
conversion receipts materialize within cooperative budgets, not a hard RSS cap.

`RecordBatchInput(open_batches, schema)` accepts an explicit Arrow batch reader
context manager. Every batch must match the exact schema, including metadata;
nonnullable fields cannot contain NULL. Row and Arrow-byte budgets accumulate
across all batches before constructing the final chunked table. The reader is
closed after success, schema failure, cancellation or budget exhaustion. The
final table still materializes; this is not a disk-spilling execution engine.

`CompositeDataSource({"logical_name": (provider, "provider_table")})` binds
independent `DataSource` implementations to the names of one contract. Bindings
are copied, tables are checked and failures propagate. No plugin is discovered
or imported implicitly. Providers own their immutable snapshots, authentication
and type fidelity. Composition does not create an atomic snapshot across
databases or APIs. `LocalDataSource` also accepts external objects with
`load(context) -> LoadedTable`, so a new input need not modify core.

SQLite additionally checks cancellation/timeouts through its native progress
handler every 1000 VM instructions, including before the first row is produced.
Its busy lock wait uses a 5-second SQLite timeout; interruption remains
cooperative. Stream reads and external batch retrieval remain caller-controlled
blocking operations and require transport timeouts supplied by that caller.

These adapters are library inputs. Untrusted SQL/callbacks are not sandboxed.
Register external inputs explicitly; document their type, consistency and size
guarantees before using them as interchangeable sources.
