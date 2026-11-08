# Ingest CSV and JSONL in bounded value batches

[Handbook](index.md) · [API](api.md) · [Extension ports](extending.md)

Use `ingest_file` when converting a local text source under an explicit schema.
It preserves the original bytes and SHA-256, exact conversion receipts, rejected
record locations, duplicates and declared Decimal/time precision. It does not
infer a schema, repair values or establish business correctness.

## A complete small example

After installing an identified artifact with the `arrow` extra, run
this in a fresh directory. The input is deliberately synthetic.

```python
from decimal import Decimal
from pathlib import Path
import equiframe as ef
import pyarrow as pa

path = Path("example.csv")
path.write_text("id,money\n001,1.10\n001,1.10\n002,NULL\n", encoding="utf-8")
spec = ef.IngestionSpec(
    format="csv",
    fields=(
        ef.FieldMapping(
            column=ef.ColumnSpec(
                name="id",
                logical_type=ef.StringType(),
                nullable=False,
                null_policy=ef.NullPolicy(representations=("null",)),
            ),
            path=("id",),
        ),
        ef.FieldMapping(
            column=ef.ColumnSpec(
                name="money",
                logical_type=ef.DecimalType(precision=10, scale=2),
                nullable=True,
                null_policy=ef.NullPolicy(representations=("null",)),
                numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD"),
            ),
            path=("money",),
            null_tokens=("NULL",),
        ),
    ),
)
result = ef.ingest_file(path, spec=spec, work_dir=Path("ingestion"), batch_rows=2)
if result.state != "completed" or result.output is None:
    raise RuntimeError("Review the ingestion receipt before accepting these data")
expected = pa.table(
    {
        "id": ["001", "001", "002"],
        "money": pa.array([Decimal("1.10"), Decimal("1.10"), None], type=pa.decimal128(10, 2)),
    }
)
comparison = ef.diff(ef.read_table(result.output), expected, work_dir=Path("comparison"))
report = ef.write_comparison_report(comparison, Path("report"))
print(report.to_text())
ef.assert_equivalent(comparison)
```

`batch_rows` is an execution knob, default **4096**, accepted by `ingest_file`
and `FileInput(path, spec, batch_rows=4096)`. It must be a positive Python integer;
booleans, floats, strings, zero and negative values fail before creating files.
There is no artificial upper bound: a large batch requests a correspondingly
large allocation. Record and source budgets still apply. The CLI uses the
default. The `IngestionSpec`/`IngestionResult` JSON format remains **1.0** and gains
no field: record the chosen batch size in your application's run configuration.
Existing calls and historical receipts need no migration.

## What is bounded, and what is not

- CSV and JSONL use incremental text decoding and at most one batch of converted
  accepted values before an Arrow IPC write. They no longer retain the full
  decoded file or a list of all JSONL documents
- An initial bounded decode-validation pass retains the historical behavior for
  invalid encoding: the entire source is rejected before accepting any row.
  The preserved raw file is then read again; this costs an extra sequential pass
- CSV record positions remain `$[index]`. JSONL keeps its historical `line:N`
  plus nested JSON path; array expansion and root/ancestor scopes are unchanged.
  These are logical record/line positions, not byte offsets. CSV quoted newlines
  retain the prior universal-newline decoding behavior, while original bytes do
  not change
- Full JSON documents still materialize. A single large JSONL document and its
  explicit nested expansion can also materialize. `max_source_bytes` bounds the
  copied source; `max_records` bounds expanded/inspected records, not parser RSS
- The public result still retains **all** conversion and quarantine receipt
  objects. Result JSON is now serialized in chunks with exactly the historical
  canonical bytes, avoiding a second complete receipt dictionary/string copy.
  Receipt objects and a single large string/value are not bounded by batch size
- Context row and Arrow-buffer budgets are cumulative across batches. Arrow
  buffer accounting includes each batch's buffers (including validity bitmaps).
  Physical IPC bytes and hashes can differ with chunk boundaries; semantic
  values, multiplicity, order and receipts must not. These are cooperative
  checks, not hard memory, CPU or disk quotas
- `FileInput.load`, `read_table` and native execution still return/materialize a
  complete `LoadedTable`. Batching ingestion does not make a whole workflow
  streaming. Existing file-based comparison readers have their own batch/spill
  support; see the [extension boundary](extending.md#arrowparquet-partitions-and-external-source-boundaries)

## CSV headers and surplus cells

Any unique, nonempty declared CSV header is legitimate, including names such as
`<surplus_fields>` or `null`. Diagnostic labels never replace named source cells.
Rows with additional cells follow `extra_fields`: `ignore` discards only the
undeclared surplus cells before scalar conversion; `reject` records
`new_or_extra_field` and follows the declared `invalid_records` policy.

Scalar conversion and diagnostics use separate records. For non-colliding names,
overflow diagnostics retain their historical `original_text` bytes, including
the existing `null` and `<surplus_fields>` labels. If either label is an actual
header or declared field path, the diagnostic instead uses the unambiguous
`{"fields": {named source cells}, "surplus_fields": [extra cells]}` shape inside
`original_text`. This wrapper is a narrow diagnostic difference for collision
cases, not a new ingestion schema version; historical 1.0 receipts stay readable.
No diagnostic labels can become the value of a declared missing field.

Original source bytes, SHA-256, source size, logical record positions and
conversion receipts for named fields are retained. Missing cells still follow
their declared `missing` policy and never become surplus values.

## Rejection, quarantine and interruption

`rejected` has no output reference, even if valid rows had already been flushed
to private staging. `quarantined` publishes accepted rows but retains the rejected
records and incomplete coverage. `FileInput.load` accepts only `completed`.
A successful parse alone does not imply equivalence; use an independent expected
output or the other requested verification checks.

Staged Arrow files are removed on parse rejection, budget exhaustion,
cancellation, timeout or write failure before publication. Resource and I/O
errors raise rather than become a successful result. Cancellation or a failure
while writing the final receipt leaves no `ingestion.json`; its unique operation
folder may still contain original bytes or already completed artifact files.
Their existence is not a finalized result. Existing operations are never
replaced. Original sources and unredacted receipts can contain private values;
keep evidence in an authorized private directory.

The focused tests exercise varying batch sizes, independent exact expected
values, duplicates, nulls, Unicode, encodings/separators, nested paths, empty
inputs, cumulative budgets and interruptions. Platform and installed-artifact
claims require the separate receipt for the exact candidate; source tests and
historical results are not that receipt. No constant-memory or universal speedup
claim is made.
