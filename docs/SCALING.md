# Exact comparison costs and safe operating limits

STEP8 adds an engineering scale protocol to `equiframe-benchmark`. It extends
its existing cost-measurement infrastructure and reuses its sampled resource
monitor; it does not replace `CostProtocol`, alter the scientific R/M/B/H
experiment, or reactivate the quarantined core benchmark placeholder.

The protocol is experimental. It measures local, deterministic, synthetic
integer, text and NULL workloads, with exact keys or exact multiset comparison.
It does not benchmark external services, a data warehouse, distributed execution,
unknown SQL, approximate matching or datasets larger than RAM. Other supported
semantic types keep their existing correctness tests; no speed claim is inferred
for them from this corpus.

## Reproduce a bounded case

Install the identified candidate wheels with the benchmark's `resources` extra
and the desired `engines` extra in a clean Python 3.12 or 3.13 environment. The
[release guide](RELEASE_CANDIDATE.md) explains private artifact identity and the
still-pending publication decisions. Do not obtain this private candidate by
installing an unrelated project with the same name from an index.

From outside the checkout:

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
    concurrent_loads="Describe known concurrent jobs here; unknown host load remains uncontrolled",
)
result = eb.measure_scale(spec, work_dir=Path("scale-runs"))
verified = eb.read_scale(Path("scale-runs") / result.run_id)
print(eb.summarize_scale(verified))
if not verified.complete:
    raise SystemExit(3)
```

`equiframe-benchmark scale spec.json --output scale-runs` consumes the strict
`ScaleSpec` JSON schema. `equiframe-benchmark verify-scale scale-runs/scale-ID`
checks the retained receipt and bytes without rerunning the source. Both return
3 for an incomplete/failed measurement; verification failure also returns 3.
Zero means a completed engineering measurement with the expected verdict, not
that candidate and reference are equal: a deliberately different case must
return `different`. Comparison acceptance itself still uses `assert_equivalent`.

The packaged `examples/scale_local.py` runs one small case by default. Its
`--rows` flag explicitly admits 1k, 100k or 1M, with recorded larger budgets for
larger cases; it never starts the largest workload as an import side effect.

## Workload and repetition protocol

The generator independently defines expected rows from their ordinal, writing
both complete sides as bounded Arrow IPC batches. `width` includes the ID.
Payloads alternate exact int64 and variable-length strings; `cardinality`,
`text_max_length`, `skew_percent`, `null_every` and `distinct_rows` expose the
controlled shape. Repeated full rows require multiset alignment. Keyed cases
require actual unique IDs. `difference_every` changes the first payload column
at that interval, and `difference_last` changes the final row even when it was
NULL. Mutations never alter the expected side or relax the contract.

`batch_rows` controls generation. `comparison_options.batch_rows` independently
controls comparison. All comparison budgets remain explicit in the receipt.
The generator caps one case at 1M rows and 32 columns; admission also checks free
disk against the requested disk budget plus a 256 MiB safety reserve. These are
safety admission rules, not scalability promises or accurate size predictions.

A single isolated worker runs 2–10 repetitions (default 3), sequentially. Trial
zero has a fresh Python worker. Later trials reuse that process. Labels are
`fresh_process_os_cache_uncontrolled` and `warm_process_os_cache_uncontrolled`:
the OS page cache is never flushed or claimed cold. Every raw trial is retained.
Summaries separate these two cache groups, give n/median/minimum/maximum, and
retain unsuccessful or missing repetitions rather than discarding them.
One cold observation has no measured cold-run variability.

## Timed stages and service boundaries

| Stage | Actual measured work |
|---|---|
| capture | Synthetic generation and Arrow IPC batch writing |
| snapshot | Complete input hashing and batch row counting |
| transfer | Local file copies, with no network transfer |
| plan | Construct and validate the exact declared contract |
| compare | Public `compare`, including its own snapshots, plan selection, exact SQLite processing, serialization and persistence |
| serialize | Additional standalone serialization of the returned result |
| persist | Additional fsync and exclusive atomic publication of that standalone result |
| render | Privacy-filtered report construction and HTML/text/JSON publication |
| verify | Read the result, iterate every verified difference record and reread the evidence inventory |

The trial end-to-end duration brackets these disjoint stages and their small
orchestration gaps. `compare` is deliberately an inclusive public-API measurement:
the additional serialize/persist stages do not pretend to extract its internal
costs. The supervised-run elapsed time also includes parent preflight/launch, Python
startup/imports, all repetitions, separate native baselines, trial receipt
publication, monitoring, reaping and the final disk walk. Parent-side trial
inventory verification and final-manifest publication are outside that interval.
This is not pure worker CPU time. No component time is subtracted or inferred.

## Resource observations and budgets

- Trial resources reuse the existing process CPU/RSS monitor. RSS is an absolute
  sampled lower bound, not an allocation delta; sample gaps and monitor failures
  stay visible. Trial samples bracket EquiFrame stages, excluding baseline services
- The external supervisor observes the direct worker, including native engine
  threads and its in-worker sampler. The trusted worker starts no subprocesses;
  observed descendants are unsupported and trigger termination. The supervisor's
  own CPU/RSS and unrelated system work are excluded
- Worker CPU and I/O are last available sampled counters, not guaranteed final
  totals. Physical read/write bytes and logical syscall bytes (`read_chars`/`write_chars`
  on Linux) are separate;
  unavailable counters remain null with reasons. Cached reads may show zero
  physical I/O. [Counter units](https://psutil.readthedocs.io/stable/#psutil.Process.io_counters). Engine allocator peak memory is not available
- A Linux child can exit between the live sample and its `/proc/PID/io` read.
  After a confirmed owned-child exit, an access/disappearance error retains
  previously observed complete I/O counters. It does not invent a final sample.
  A live denial, an absent/incomplete earlier sample, or malformed counter data
  remains a measurement failure.
- Temporary/output disk includes the owned worker tree, logs and its private
  TMPDIR. Apparent and allocated peaks are sampled separately and hard links are
  counted once. Directory metadata is included; symlinks are not followed.
  Deleted-between-sample and open-unlinked files may be missed
- RSS and aggregate disk thresholds are reactive sampled termination thresholds.
  They can overshoot. They are not cgroups, containers, hard quotas or a security
  sandbox. No strict maximum memory/disk promise is made
- An independent wall-time watchdog kills the worker's private POSIX process
  group (direct child on other systems). It can stop native work that does not
  reach a Python checkpoint. Scheduling latency remains possible; escaping child
  sessions are unsupported, and no universal preemption/containment claim is made
- Core row/work/batch/evidence/disk/time options stay cooperative. SQLite's page
  limit and current comparison checks do not limit total process RSS or every
  temporary file. Exceeding a budget preserves `not_evaluable`

Do not copy a 1M-row recipe into a smaller machine without reviewing its recorded
work, disk, wall and memory budgets. Default `max_work=100_000_000` is insufficient
for the measured 1M-row/two-column case; increasing that declared budget is a
conscious change in allowed work, never a reduction in exactness. Default
`ScaleSpec.timeout_seconds=300` applies to the entire worker, not each repetition.
Large recipes use a larger explicit wall budget. Run one measurement at a time,
use a disk-backed TMPDIR, and retain failed attempts and known concurrent load.

## Native baselines and exactness

Pandas `assert_frame_equal` is restricted to actual unique keys, sorted by those
keys with exact values, dtypes and names checked. Arrow-backed nullable dtypes
retain this generator's integer/text/NULL distinctions. DuckDB uses bidirectional
`EXCEPT ALL`, retaining multiplicity, on the same restricted integer/text/NULL
captures. Both first require exact Arrow-schema equality, including metadata;
SQL's common-type coercion is not treated as proof of original schema identity.
These are verdict baselines, including input loading/native conversion/query.
They do not produce EquiFrame's complete difference evidence, snapshots, reports
or integrity checks. A timing ratio is therefore a difference in service cost,
not a fair claim that equivalent services are faster or slower.

DataComPy is not a pinned dependency of this candidate. Its observation is
explicitly `not_available`, with no fabricated timing or semantic equivalence
claim. Missing optional pandas/DuckDB engines likewise remain unavailable;
unsupported pandas multiset cases are `not_applicable`. Every requested baseline
retains its status and scope, including failures.

The exact comparator still groups full canonical values and validates contracts,
keys, multiplicity, every row and all required differences. Hashes partition work
or verify artifact bytes; they never substitute a hash match for exact comparison.
The STEP8 optimization changes only how the same per-checkpoint disk files are
counted, preserving checkpoint frequency and filesystem error semantics.

## Completion, interruption and cleanup

The worker exclusively publishes each trial receipt, then its completion marker.
The parent reaps the worker, verifies all completed trial files and referenced
comparison evidence, and publishes `scale.json` followed by `finished.json`
through fsynced files and exclusive atomic links. The last marker binds the
result's hash and actual completeness. Atomic publication is not a guarantee
against every storage/power-loss scenario, and hashes do not authenticate a writer.

Exit zero alone is insufficient. A native kill, timeout, absent/invalid worker
completion, wrong verdict, corrupted inventory or incomplete comparison cannot
be reported as a successful measurement. Failure receipts preserve the observed
exit status, diagnostics, completed prefix and missing repetitions. If the parent
itself dies before finalization, `read_scale` rejects the unfinished directory.

After the child is reaped, only known disposable `work.sqlite` files and their
journal/WAL/shared-memory companions in owned comparison directories are removed.
Removed paths/byte counts are recorded; partial inputs, logs and diagnostics are
retained. A later reader never deletes evidence or executes a workload. The local
receipt is not a portable bundle: artifact paths identify its original retained
run. Reproduction uses the saved specification, generator and identified wheels.

Fault tests use tiny bounded processes and injected errors, rather than filling
the host filesystem or causing a host OOM. They cover genuine native SIGKILL,
exit zero without finalization, watchdog timeout, observed RSS/disk termination,
cooperative memory/batch/work/evidence limits, cancellation, injected ENOSPC,
last-batch discrepancy, skew and duplicate multiplicity. No host-OOM or full-host
storage stress test is claimed.

`complete` and the CLI success code describe the completed workload and its
expected verdict. They do not silently certify complete resource observation.
`summarize_scale` separately reports `resource_measurement_complete`, every
trial's resource quality and all supervisor monitoring errors. For example,
unavailable final I/O counters or lagged samples retain valid earlier lower-bound
observations but make resource measurement completeness false. A receipt reader
uses the existing strict 64 MiB JSON budget before parsing any scale document;
a missing, oversized or malformed final document fails closed.

Producer provenance is recorded by the actual `-I` worker in its completion
receipt, including installed versions and Python source hashes. The parent
compares this environment with its own before/after observations; mismatch makes
the operation unsuccessful even when every expected comparison completed. If
worker completion is absent, the environment is explicitly labeled
`parent_only_worker_unavailable` and actual worker binding is unknown, never
inferred from the parent's imports. These byte bindings are not execution
attestations or cryptographic authentication.
The same 64 MiB limit is checked before publishing each typed scale document,
including the aggregate containing every trial. An oversized aggregate raises
without a successful final marker; individually readable trials never imply
that an unreadable aggregate was successfully delivered.
