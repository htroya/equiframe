# STEP8 measured costs and resource boundaries

The private candidate adds reproducible engineering measurements and a narrowly
measured exact-comparison optimization. It preserves semantic contracts, every
budget checkpoint and the scientific benchmark protocol. Main remains held for
steps 8–10 and the final whole-project review; no public package is released.

## Identified artifacts

Python admission remains `>=3.12,<3.14`; measured performance below is Linux
x86_64, Python 3.12.14. Compatibility validation is separate from timing.

| Artifact | SHA 256 |
|---|---|
| Core wheel | `61030f6755d943954920ef989939fae845bb8b77c69886a347b4fc00e05de1be` |
| Core sdist | `12abbc5169515d0e2dbddc4bc7d10c101afe581efdeba91e4fb14f8e6e6cbe11` |
| Benchmark wheel | `e7a227e13c0ea2db926d24e5e6625025bdf4a052e7eac8a0406cb48d6a5a3d96` |
| Benchmark sdist | `3f5d2599b4740351618568b84456467109b8c265e6710344dcd6067387054c5b` |

The private version remains 0.11.1 and therefore is not sufficient to identify
these bytes. Install exact files and verify hashes. Licenses, public publishing,
external adoption and real DW acceptance retain their separate unresolved gates.

## Baseline and justified optimization

`_Work.check` now uses context-managed `os.scandir` instead of repeated Path
construction and filesystem metadata calls. Exceptional file-type checks fall
back to `Path.is_file`, preserving supported Python/platform behavior including
symlink loops. Cancellation, timeout, work accounting and disk measurement still
happen at every original checkpoint. Full values, normalization, grouping,
matching, multiplicity and difference evidence are unchanged.

Three alternating baseline/candidate pairs were executed at each size:

| Rows per side | Baseline median seconds | Optimized median seconds | Lower median time |
|---|---:|---:|---:|
| 1,000 | 0.284108 | 0.212545 | 25.2% |
| 100,000 | 25.362796 | 19.377525 | 23.6% |
| 1,000,000 | 251.382538 | 191.436394 | 23.85% |

All 18 observations completed with identical exact verdicts, row/match/difference
counts, work units, input identities, difference hashes and working-disk peaks
within each size. The 1M case used 260,002,019 work units and peaked at
1,357,082,852 comparison-working bytes. No external timeout or resource stop
occurred in those paired runs.

These are controlled-method diagnostics on a two-column integer/text multiset
fixture, not a general throughput claim. The same installed environment executes
both variants, substituting only the measured check method. The comparator and
its comparison dependency closure match STEP7; one unused DuckDB capture module
in that diagnostic environment differs. Candidate method bytes match the final
core wheel. Method substitution can influence the small RSS difference; it is not
attributed solely to the library change. OS caches and host load were not
controlled. This experiment is separate from final installed-distribution tests.
A second lazy-decoding idea was investigated and not included in the candidate.

## Complete stage pipeline on the final installed wheels

Nine synthetic cases, three sequential trials each, cover width, variable string
length, cardinality, extreme skew, duplicate multiplicity, NULLs, difference
density, single-partition/small batches and the last batch at 1k/100k/1M rows.
All 27 trials completed with the independently expected verdict and counts.
Every retained run was reread through `read_scale` and audited independently.

| Case | Rows per side | Width | Median pipeline seconds | Sampled worker RSS MiB |
|---|---:|---:|---:|---:|
| Keyed equal with NULLs | 1,000 | 4 | 0.360 | 200.7 |
| Keyed last-row difference | 1,000 | 4 | 0.432 | 200.4 |
| Wide variable text | 1,000 | 24 | 1.398 | 224.8 |
| Dense differences | 1,000 | 8 | 0.678 | 200.1 |
| Extreme skew and duplicates | 1,000 | 8 | 0.274 | 196.8 |
| Single partition and small batches | 1,000 | 4 | 0.295 | 196.8 |
| Last-batch difference | 100,000 | 2 | 20.462 | 219.1 |
| Duplicate-heavy skew | 100,000 | 4 | 20.535 | 242.6 |
| Last-batch difference | 1,000,000 | 2 | 207.985 | 396.8 |

The table's median combines the three raw trials for compact orientation; raw
summaries separately retain one fresh-process observation and two warm-process
observations. For 1M, fresh was 207.984682s, warm median 209.133101s, and all-trial
range 206.988514–211.277689s. No OS-cold claim is made.

The 1M worker sampled RSS peak was 416,051,200 bytes; apparent disk peak was
1,326,180,994 bytes and allocated disk peak 1,326,292,992 bytes. Evidence retained
per trial was approximately 96,352,726 bytes. Worker observations include native
baselines and all repetitions; trial observations bracket the nine EquiFrame
stages. They have different scopes and cannot be directly subtracted.

Capture, snapshot, local transfer, contract planning, comparison, extra standalone
serialization/persistence, rendering, verification and end-to-end times are all
recorded. Public `compare` includes its own snapshots, planning and evidence I/O;
its internal work is not falsely split into independent substage estimates.
[Exact timing boundaries and reproduction](SCALING.md).

## Resource quality and adverse observations

Every case has `resource_measurement_complete=False`: last-available I/O counters
were recorded, but the probe also reported `AccessDenied`; final totals are not
verified. The error list has no per-error timestamps, so no precise failure time
is inferred. The 1M trial sampler states are partial/complete/partial because of
sampling lag. Missing/partial measurements are retained without zero imputation
or removal. RSS and disk values are sampled lower bounds, not hard maxima.

For example, the 1M worker retained observed cumulative physical writes
5,803,618,304 bytes and logical writes 6,258,351,594 bytes (`write_chars`). Physical reads
were observed as zero, compatible with cache residency rather than absence of
logical reads (23,925,460,462 bytes in `read_chars`). These are last-available counters,
not a complete process I/O accounting or disk-cap claim. Linux `read_chars` and
`write_chars` count syscall bytes, as documented by [psutil](https://psutil.readthedocs.io/stable/#psutil.Process.io_counters).

The measured narrow 1M recipe explicitly used a 1 GiB sampled RSS termination
threshold, 2 GiB sampled disk threshold, 1B comparison work budget, 540s
cooperative per-comparison timeout and 1800s supervised allowance for all three
trials. Reproduction admission reserves at least the disk budget plus 256 MiB
free space, in addition to dependencies and other runs. These are conservative
settings for this recipe, not universal recommended capacities. Default 100M
work is insufficient for the paired 1M fixture; no default was silently raised.

Neither sampled threshold is a hard quota. No general RSS containment, strict
latency, larger-than-RAM operation, real host OOM, or full-host disk stress result
is claimed. Tests instead safely exercise observed RSS/disk termination,
cooperative limits, watchdog timeout, cancellation, genuine SIGKILL, injected
ENOSPC and incomplete/oversized/corrupt completion. Known SQLite temporaries are
removed only after the worker is reaped; partial inputs and diagnostics remain.

## Comparison with native services

Restricted native pandas assertions and DuckDB bidirectional `EXCEPT ALL` share
this generator's exact integer/text/NULL policies and original Arrow-schema
check. Every applicable native verdict matched. They return a verdict without
EquiFrame's complete stored difference evidence, snapshots, reports and integrity
verification, so elapsed time is not an equivalent-service league table.

The restricted 1M DuckDB verdict took median 0.492983s (range
0.466040–0.558969s), including loading/native conversion/query. The complete
EquiFrame pipeline took roughly 208s. EquiFrame therefore has no raw verdict-speed
advantage in this example; its justification here is reusable contracts and
reviewable evidence. Choose the smaller native service when those additional
services are unnecessary. Pandas multiset measurements were not applicable.
DataComPy was unpinned/unavailable and has no invented measurement.

## Review and validation status

Independent installed v2 consumer: 50 assertions passed, including a native kill
after every worker receipt existed, hostile rehashed external references,
parent/isolated-child producer mismatch and oversized aggregate publication.
The final candidate uses actual worker producer identities; missing worker
provenance remains explicitly unknown. All 18 paired and 27 pipeline measurements
were independently audited against raw records.

All 18 final gates passed, nine per package: locked sync, lint, formatting,
strict typing, generated assets, full source tests, build, strict Twine and
installed distribution verification. Every before/after source snapshot and
wheel/sdist/dependency hash is bound to the identified final bytes.

- Core: 2,574 source and 2,574 installed tests
- Benchmark: 524 source and 524 installed tests
- Compatibility: eight core cells (Arrow/all × minimum/latest × Python
  3.12.14/3.13.5), including four full suites of 2,574 tests
- Benchmark compatibility: four full suites of 524 tests, independently resolved
  minimum/latest direct dependencies under the matching core runtime pins
- No skips/xfails in the full suites; all 2,559 prior core and 456 prior benchmark
  testcase identities retained. All 175 prior core test/fixture files and 23 prior
  benchmark test files are byte-identical to STEP7
- Independent installed consumer: 50 assertions; all paired and stage records
  independently audited. This is technical review, not human adoption

Only these executed Linux x86_64 combinations are evidenced. Installed consumers
are outside the checkout and use the exact frozen artifacts. Configured workflows
are not remote CI results. A preliminary sdist/source audit needed an explicit
mapping for the repository-root `.gitignore` included by Hatch; the failed
preflight is retained as a corrected tooling assumption, not a product-test failure.
Scientific review, public distribution and real DW acceptance remain separate.

## Preserved boundaries

No change to `THESIS_TRACEABILITY.md`, scientific methodology, detector protocol,
old evidence readers, adapter capabilities or public core signatures. The
quarantined placeholder stays unsupported. The Spanish reinforced roadmap is
outside Git. Only the candidate branch may move at STEP8 completion; main,
remote CI activation, PR creation and public distribution remain withheld.
