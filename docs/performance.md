# Performance and safe resource budgets

[Handbook](index.md) · [Semantics](semantics.md) · [Compatibility](compatibility.md)

EquiFrame favors declared semantics and reviewable evidence over an unconditional
speed claim. Native assertions may be the smaller service when you only need a
verdict. There is no universal row limit, latency guarantee, process-RSS quota,
larger-than-RAM promise or demonstrated advantage over every comparison tool.

## Understand the work you request

`diff` first captures native inputs, then compares. `compare` can read local
captured Arrow IPC/Parquet in batches and uses private SQLite working files for
exact grouping/alignment. It still validates schema, keys, values, multiplicity
and all requested evidence. A displayed sample limit does not skip the remaining
data. Wide strings, many differences and approximate matching can cost more than
an equal narrow table with the same row count.

Common default budgets, as declared by the installed models:

| Options | Defaults and scope |
|---|---|
| `DiffCaptureOptions` | 1,000,000 rows and 256 MiB per eager input |
| `ComparisonOptions.batch_rows` | 4,096 rows per comparison batch |
| `max_batch_bytes`, `max_row_bytes` | 64 MiB per batch; 1 MiB per row |
| `max_rows`, `max_work` | 10,000,000 rows; 100,000,000 accounted work units |
| `max_disk_bytes`, `max_evidence_bytes` | 4 GiB comparison working budget; 512 MiB difference evidence |
| `max_matching_rows`, `max_matching_bytes`, `max_pair_checks` | 2,000 matching rows; 32 MiB; 2,000,000 candidate pair checks |
| `partitions`, `sqlite_cache_kib` | 16 partitions; 4,096 KiB SQLite cache setting |
| `max_examples` | 20 summary examples; does not limit evaluation |
| `timeout_seconds` | None by default; explicit timeouts are cooperative |
| `DuckDBCaptureOptions` | 4,096-row batches; 1,000,000 rows; 64 MiB batch and 256 MiB file budgets |

These are operational checks, not an admission guarantee for every case below
the numbers. Capture/conversion can allocate before a check. File sizes, Arrow
buffers, engine-managed memory, working disk and process RSS are distinct.
`duckdb_memory_mb` constrains engine-managed memory, not all Python/Arrow/native
allocations. Core callback and Polars collection cancellation are cooperative;
a callback that does not check can run until it returns. DuckDB query interruption
does not impose a hard deadline on all Python capture/publication work.

Choose a private output directory on a suitable disk-backed filesystem, leave
space for inputs, temporary files, snapshots and full differences, and avoid
concurrent benchmark workloads. For large inputs prefer captured files and an
explicit contract over eager conversion. Set work/time/evidence budgets based on
a small representative run. Preserve insufficient-budget results instead of
silently loosening exactness or dropping duplicates.

## Reproducible engineering measurements

The separate `equiframe-benchmark` package offers experimental `ScaleSpec`,
`ScaleTrial`, `ScaleRun`, `measure_scale`, `read_scale` and `summarize_scale`.
Install its identified matching wheel with the required dependency profile before
running this complete small example outside the checkout:

```python
from pathlib import Path
import equiframe as ef
import equiframe_benchmark as eb

spec = eb.ScaleSpec(
    case_id="keyed-last-batch-1k",
    rows=1_000,
    width=4,
    alignment="keyed",
    null_every=11,
    difference_last=True,
    repetitions=3,
    comparison_options=ef.ComparisonOptions(batch_rows=256),
    concurrent_loads="Record actual known concurrent work; host load is uncontrolled",
)
result = eb.measure_scale(spec, work_dir=Path("scale-runs"))
verified = eb.read_scale(Path("scale-runs") / result.run_id)
summary = eb.summarize_scale(verified)
print(summary)
if not verified.complete:
    raise SystemExit(3)
```

For meaningful CPU/RSS monitoring install the benchmark's `resources` extra;
missing or failed monitoring remains explicit. The optional `engines` extra
permits applicable native baselines. This script measures a deliberately
**different** case: completion means the expected verdict occurred, not that the
two tables should pass an equivalence assertion.

The generator uses deterministic synthetic integer/text/NULL data with exact keys
or multisets. Width, string length, cardinality, skew, duplicate multiplicity,
NULLs, difference density and final-row differences are controlled explicitly.
It does not establish performance for Decimal, timestamps, approximate matching,
unknown SQL, remote services, data warehouses or larger-than-RAM datasets.

One isolated trusted worker runs 2–10 repetitions sequentially, default 3. The
first uses a fresh Python worker; subsequent trials reuse it. OS caches are
uncontrolled. Raw labels distinguish `fresh_process_os_cache_uncontrolled` and
`warm_process_os_cache_uncontrolled`; summaries retain n/median/min/max, failures
and missing observations. One fresh observation is not a variability estimate.

The recorded stages are capture, snapshot hashing/counting, local transfer,
contract planning, public comparison, additional standalone serialization,
persistence, rendering and verification. Public `compare` includes its own
capture/snapshot/planning/evidence work; the additional serialization/persistence
stages do not isolate its internals. End-to-end trial time brackets these stages.
Supervisor elapsed time additionally includes startup, repetitions, baselines,
monitoring and reaping. Parent final inventory verification/publication is outside
that measured interval. Do not subtract unlike scopes to invent a component cost.

## What the resource figures mean

- RSS is an absolute sampled **lower bound on peak**, not an allocation delta or
  hard maximum. Sample gaps and monitoring failures remain visible
- Worker CPU/I/O counters are last available observations; physical storage bytes
  and logical syscall bytes are different. Missing final totals stay unknown
- Disk apparent/allocated peaks are sampled within the owned worker tree and
  temporary directory. Hard links count once; deleted-between-sample or
  open-unlinked files may be missed
- Engine allocator peak is not supplied by this protocol. Supervisor resources
  and unrelated host work are not included in worker RSS
- Observed RSS/disk thresholds reactively terminate work and may overshoot; they
  are not cgroups, containers or a sandbox
- A watchdog can terminate the trusted worker's private process group on POSIX
  or direct child elsewhere. Scheduling delays and unsupported escaping children
  prevent a universal hard-time/containment claim
- `complete` describes operation/verdict completion;
  `resource_measurement_complete` separately states observation quality

Native pandas assertions and DuckDB bidirectional `EXCEPT ALL` baselines are
restricted to the generator's exact integer/text/NULL policies and original
Arrow-schema check. They provide less evidence: no complete EquiFrame difference
files, snapshots, reports and integrity inspection. Ratios are service-cost
comparisons, not proof one equivalent service is faster. DataComPy is not pinned
in this candidate and no measurement is invented for it.

## Historical baseline, not a new-artifact speed claim

The STEP8 identified Linux x86_64/CPython 3.12.14 artifacts recorded nine synthetic
cases with three sequential trials each. The narrow 1M-row/two-column last-batch
case had an all-trial median end-to-end pipeline time of **207.985 seconds**,
range **206.989–211.278 seconds** and sampled worker peak RSS about **396.8 MiB**.
The corresponding restricted DuckDB verdict baseline was about **0.493 seconds**
median, providing substantially less evidence. There is no raw verdict-speed
advantage for EquiFrame in that example.

Those results belong to core wheel SHA-256
`61030f6755d943954920ef989939fae845bb8b77c69886a347b4fc00e05de1be`
and benchmark wheel SHA-256
`e7a227e13c0ea2db926d24e5e6625025bdf4a052e7eac8a0406cb48d6a5a3d96`.
They are **not measurements of a later rebuilt STEP9 wheel**. All nine runs
retained `resource_measurement_complete=False` due to incomplete final I/O
monitoring; some RSS sampling was partial. Host load and OS caches were not
controlled. These numbers are orientation with explicit limits, not a sizing SLA.

The measured narrow 1M recipe used a 1 GiB sampled RSS threshold, 2 GiB sampled
disk threshold, 1 billion comparison work units, 540 seconds per-comparison
cooperative timeout and 1,800 seconds supervised allowance for three trials.
Admission additionally reserves at least disk budget + 256 MiB free space. These
are fixture-specific budgets, not recommendations for every 1M-row workload.
The default 100 million work units was insufficient for that fixture.

## Failure, finalization and cleanup

`equiframe-benchmark scale spec.json --output scale-runs` and
`verify-scale scale-runs/scale-ID` return 3 for incomplete/failed measurement or
invalid finalization. Exit zero by itself is insufficient. The worker's completion
receipt, finalized aggregate and `finished.json` inventory binding must all
validate. A native kill, incorrect verdict, corrupted inventory or incomplete
comparison is not successful measurement.

After reaping the worker, only known disposable SQLite files in owned comparison
directories are removed; partial captures, diagnostics and logs remain. A reader
does not execute workloads or delete evidence. Receipts retain original local
paths and are not portable bundles; reproduce from the specification and exact
artifacts. If the parent dies before publication, `read_scale` fails closed.

Tests use bounded subprocesses, genuine SIGKILL and injected ENOSPC rather than
filling a host disk or causing host OOM. No destructive whole-host stress result
is claimed. The consumer must treat missing finalization, abnormal exit and
insufficient evidence as failure or unavailable evaluation, never equivalence.

## Bounded consolidation suite

`tools/measure_bounded.py` adds a repeatable developer suite. It reuses
`ScaleSpec`, `measure_scale`, `read_scale`, `summarize_scale` and their existing
isolated-worker supervisor for final-row differences, dense differences,
duplicate multiplicity, wide strings and ordinary disk/evidence costs. A separate
small Decimal supplement measures exact cents through Arrow and pandas, including
an explicitly timed Arrow-to-pandas conversion. It does not change historical
scale schemas or introduce a core dependency on the benchmark.

Use a benchmark environment containing the **matching installed** core and
benchmark builds, including pandas, Arrow and the benchmark `resources` extra.
From the checkout, after the identified artifacts have been installed:

```bash
packages/equiframe-benchmark/.venv/bin/python -I \
  tools/measure_bounded.py \
  --output /new/private/bounded-costs --rows 512 --repetitions 3
```

The scale supervisor deliberately ignores `PYTHONPATH`; pointing the parent at
changed source while its isolated worker has an older installed wheel fails the
producer-identity check. Install the matching artifacts instead of weakening the
check. `suite.json` retains imported-source fingerprints, tool hash, versions,
individual stage boundaries, raw supervision records and explicit completion.
An older version string alone is not a matching artifact. Failed attempts remain
separate; each run requires a new output directory.

Defaults run sequentially at 512 rows/side (1,024 for the disk/evidence fixture),
three repetitions, 128-row batches, a 512 MiB sampled RSS threshold, 64 MiB sampled
disk threshold and 120 seconds per supervised case. Comparison budgets are 32 MiB
disk, 8 MiB differences and 30 cooperative seconds. The suite admits only
8–2,048 rows and 2–5 repetitions and requires at least 384 MiB initially free.
These are conservative test boundaries, not hard quotas or workload sizing advice.
The disk fixture writes complete snapshots and dense differences without trying
to fill the host disk. The small tests simulate interruption and ENOSPC; they do
not exhaust memory or storage.

The Decimal supplement has its own developer-receipt format rather than claiming
the historical `ScaleSpec` supports Decimal. It retains the independently expected
one-cent final-record difference, all comparison records and a redacted report.
`diff` includes its own conversion/capture, inference, complete comparison and
publication. Additional conversion, capture, hashing, serialization and durable
write timings describe additional work; they are not disjoint pieces extracted
from the internal `diff` timing. A completed comparison followed by failed receipt
publication is an incomplete measurement. Pre-contract cancellation can raise
`ExecutionCancelled` before a final comparison exists.

### Measured reference at the consolidation base

On 2026-10-06, the installed core and benchmark Python sources were independently
matched to commit `c4be1c5a29d9f58b2628882bd986de2bb5ca4184`. This **base reference**,
not a final rebuilt-consolidation measurement, ran all six families with three
repetitions and complete expected outcomes. Linux x86_64, CPython 3.12.14,
PyArrow 25.0.1, pandas 3.0.6 and psutil 7.2.2; shared cloud host, uncontrolled OS
caches and concurrent development work. Each case has one fresh worker trial and
two warm-worker trials; medians below combine those three explicitly identified
observations and do not imply cold-cache repeatability.

| Case | Rows/side | Pipeline median (range), seconds | Sampled worker RSS, MiB | Sampled apparent disk, MiB |
|---|---:|---:|---:|---:|
| Final-row difference | 512 | 0.221 (0.207–0.485) | 147.8 | 1.74 |
| Every-row difference | 512 | 0.243 (0.228–0.497) | 148.8 | 2.47 |
| Eight distinct rows, duplicates | 512 | 0.131 (0.130–0.365) | 148.0 | 1.21 |
| Eight columns, wider strings | 512 | 0.275 (0.271–0.530) | 158.8 | 15.90 |
| Dense differences plus disk evidence | 1,024 | 0.755 (0.650–0.967) | 160.0 | 24.98 |
| Exact Decimal final cent | 512 | 0.184 (0.181–0.186) | 149.2 | 1.31 |

The public comparison stage dominates these small cases. For example, the
Decimal median stages were 0.00051 s construction, 0.00087 s additional conversion,
0.00027 s additional IPC capture, 0.00007 s hashing, 0.17618 s full `diff`,
0.00007 s extra serialization, 0.00005 s extra durable write, 0.00314 s report and
0.00146 s readback. Very short stages are below useful stable sizing resolution.
No algorithm was optimized from these observations and no percentage improvement
or comparison against a lower-guarantee service is claimed.

All six resource receipts remain incomplete because the final I/O sampling
reported `AccessDenied`. Missing final I/O totals are unknown, not zero. RSS and
disk columns remain observed lower bounds over the supervised worker and retained
evidence tree; disk is for the case's three repetitions, not one input file.
Raw receipts also retain allocated-disk observations and sampling gaps. No new
macOS/Windows/ARM64, large-volume, storage-saturation or human usability result is
implied. Preserve the supplied private raw receipts when using this reference;
source/tool fingerprints and actual environment take precedence over these
rounded display values.
