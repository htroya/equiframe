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

These adapters are library inputs. Untrusted SQL/callbacks are not sandboxed.
Register external inputs explicitly; document their type, consistency and size
guarantees before using them as interchangeable sources.
