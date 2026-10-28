# Compatibility and stability

[Handbook](index.md) · [Upgrading](upgrading.md) · [Dependencies](dependencies.md)

## Admission is not a measured support matrix

The 0.12.3 release contract declares **Python `>=3.10,<3.14`**, meaning 3.10, 3.11, 3.12 and
3.13. Dependency ranges describe installable admission, not every tested
combination. A lock captures one resolution; it does not prove every operating
system, architecture, Python patch or cross-product of package versions works.

The recorded STEP6 matrix tested the then-identified wheel on **Debian 13/Linux
x86_64, CPython 3.12.14 and 3.13.5**, with base, arrow, pandas, polars, duckdb,
engines, ml and all profiles at minimum-direct and recent-permitted resolutions.
Later STEP8 revalidation covered Arrow/all on those two interpreters at both
resolution ends, plus matching benchmark consumers. These are historical receipts
for their exact artifact hashes, not a blanket validation of every later wheel
that retains version `0.11.1`.

The following implementation checks actually ran from installed A14 artifacts
on 27 October 2026. They establish the listed workloads, rather than every input
or dependency combination. The final 0.12.3 artifact must still pass its own
[release gates](releasing.md); a version change does not inherit an artifact hash.

| OS / architecture | CPython actually exercised | Observed functional scope |
|---|---|---|
| Windows / x86_64 | 3.10.22 | Files, six native directions, semantic differences, complex ETL, IF/MAD/H and base R |
| Windows / x86_64 | 3.11.17 | Same functional scope |
| Windows / x86_64 | 3.12.4 | Same functional scope; the separate elevated symlink checks used 3.12.5 |
| Windows / x86_64 | 3.13.15 | Same scope, plus final MIT wheel/sdist, clean base/extras consumers and literal README checks |
| Linux / aarch64 | 3.10.12 | Files, six native directions, semantic differences, complex ETL, IF/MAD/H and base R |
| Linux / aarch64 | 3.11.17 | Same functional scope |
| Linux / aarch64 | 3.12.15 | Same functional scope |
| Linux / aarch64 | 3.13.16 | Same scope, plus final wheel/sdist rebuild and clean installation |

The functional scope used eight invented file formats (CSV, TXT, JSON, JSONL,
XML, Excel XLSX, Parquet and GeoJSON), three native targets and all six directed
conversions, with at least 30,000 rows per input. Thirty semantic cases combined
the six directions with equality, exact Decimal changes, NaN/NULL distinction,
an extra duplicate and declared-order changes. The complex ETL used two inputs
of 30,000 rows, six native directions, independent expected values and two
negative cases. ML/R checks kept eight training origins and four calibration
origins separate, checked IF against scikit-learn and MAD against NumPy, and
reviewed twelve native equal/different pairs with real R. These counts do not
establish statistical accuracy or a minimum useful scientific sample size.

Base R was 4.3.3 on Windows and 4.1.2 on Linux. The Python 3.13 runs used
Pandas 3.1.0, Polars 1.44.2, DuckDB 1.5.6, Arrow 25.0.1 and scikit-learn 1.9.1;
NumPy was 2.4.6 on Windows and 2.5.4 on Linux. Those pins are not asserted for
the other minors: each interpreter used a compatible resolved closure. This
matrix does not establish every legacy XLS, JSON nesting or XML dialect variant.
Windows' two symlink cases subsequently passed with real elevated permissions
on all four minors (eight passes, no skips); POSIX permission cases ran on Linux.
Platform-specific skips retain their meaning and are not successful checks.

No macOS, PyPy, other architecture, every Python patch or full minimum-to-maximum
dependency cross-product is established by this table. Earlier STEP6 x86_64
results above retain their own artifact identities; none is silently relabelled
as a 0.12.3 final-artifact result.

The first-use builder selects an explicit Python minor and its own hash-pinned
dependency closure. The legacy `requirements.lock` is the 3.12 closure;
`requirements-py310.lock`, `requirements-py311.lock` and
`requirements-py313.lock` identify the other minors. Do not treat one closure as
universal. A generated kit records its selected Python and still needs testing.

## Declared runtime dependencies

The installed wheel metadata is authoritative. Current direct ranges are:

| Profile | Dependencies |
|---|---|
| Base | typing-extensions `>=4.14,<5`; pydantic `>=2.12,<3`; typer `>=0.20,<1`; tzdata `>=2025.2,<2027` |
| `arrow` | pyarrow `>=23.0.1,<26` |
| `pandas` | pandas `>=2.2,<4`, excluding `3.0.3`, `3.0.4`, `3.0.5`, `3.0.6`; pyarrow `>=23.0.1,<26` |
| `polars` | polars `>=1.30,<2`; pyarrow `>=23.0.1,<26` |
| `duckdb` | duckdb `>=1.5.6,<2`; pyarrow `>=23.0.1,<26` |
| `engines` | All three engines and the same Arrow range |
| `files` | The `pandas` and `arrow` dependencies above; openpyxl `>=3.1,<4`; xlrd `>=2,<3`; defusedxml `>=0.7,<1` |
| `ml` | scikit-learn `>=1.7,<1.10`; numpy `>=2,<3` |
| `eda` | duckdb `>=1.5.6,<2`; pyarrow `>=23.0.1,<26` |
| `eda-charts` | The `eda` dependencies plus plotly `>=6.3,<8` |

Pandas 3.0.3–3.0.6 are excluded because their `ZoneInfo.from_file` regression
can replace the supplied timezone rules with a named-key lookup. This can
silently change historical ETL timestamps even when the locked `tzdata` bytes
are correct. Pandas documents the correction in
[3.1.0 (GH 66828)](https://pandas.pydata.org/pandas-docs/version/3.1.0/whatsnew/v3.1.0.html).
The controlled ARM312 case preserves its original inputs and SDK: 3.0.6 shifts
three `EET` results by one hour; 3.1.0 passes the same complete native outputs
and readbacks. That diagnostic does not certify the complete environment matrix.

Minimum-direct testing means a mutually resolvable minimum direct set with
available binary wheels and compatible transitive dependencies. It does not mean
all historical transitive minima. Binary availability may raise a practical
minimum on a Python/platform. A recent-permitted resolution is time-bound and
must be identified by its pins and hashes.

Base imports remain light even when extras are installed: importing EquiFrame
or its compatibility registers does not import Arrow, pandas, Polars, DuckDB,
NumPy or scikit-learn. The selected operation loads its required dependencies.
Missing extras fail explicitly with a diagnostic identifying the dependency.

`files` supplies local file readers and the initial Pandas DataFrame. Select the
`polars` or `duckdb` extra as well when that engine is the conversion target.
`equiframe doctor --extra files` checks installed dependency metadata without
loading a dataset. The optional language-R reviewer requires a user-installed
`Rscript` executable and base R; it has no Python installation extra and does not
install R packages. Its result records the R version actually used.

File loading and language-R review were introduced on 26 October and exercised
in the implementation runs above. Their stabilization commits to the admitted
interfaces and failure semantics; it does not expand the admitted type/policy
subsets or reinterpret historical results.

Dependency changes require fresh artifact, semantic and environment checks.
Native engine/Arrow transport and timezone behavior must be rechecked, not just
`pip check`. ML parity is against the installed scikit-learn version; fitted
forests, thresholds and decisions are not promised identical across versions.
See [dependency/SBOM policy](dependencies.md) before upgrading transitives.

## Public-surface classification

`get_stability_register()` is exhaustive **for the core**. It separately
classifies API, CLI, format, evidence, presentation and namespace surfaces.
`get_adapter_capabilities()` distinguishes capture, comparison, native execution
and migration; each entry gives conditions, known losses and implementation/test
references. This descriptive register does not execute a probe or admit a case.
The four returned capability records name Hernán Troya (`htroya`) as maintainer
of the internal EquiFrame adapter implementations, with best-effort support as
described in [maintenance](maintenance.md). This does not assign him maintenance
of Arrow, Pandas, Polars or DuckDB themselves. Unassigned defaults remain available
when callers construct their own capability records.

| Status | Main surfaces |
|---|---|
| Stable | Existing contracts/comparison/native execution/rules/assertions/Verify/bundles; local file reading and conversion; explicit DuckDB capture; closed IR and native pairwise migration, including admitted windows; profiles/preprocessing/IF/MAD/H; optional language-R review and finalization; their explicitly inventoried models/formats |
| Experimental | Standalone pipeline orchestration, ingestion/destinations/workflows, snapshot providers, pipeline reporting/reduction, first-use demo/doctor and the `equiframe.eda` namespace |
| Unsupported | Quarantined historical `equiframe.benchmark` helper |
| Outside this inventory | Private `_...` internals, dependency APIs and the separate benchmark package's experimental API |

Stable protects the documented signature and semantic/error contract within
admitted capabilities. It is not a certification, maturity claim for every
workflow, service-level guarantee or promise of speed. Experimental code still
must reject unsafe/unsupported input, preserve historical meaning and report
failures honestly. Adding an export requires an explicit reviewed classification.

Stable CLI includes contract validation, comparison, operational Verify, bundles,
`dataset load`, `dataset inspect` and migration validate/run/verify. Workflows,
ingestion, standalone pipeline execution/reporting, evidence inspection,
reduction and first-use commands retain their experimental classification. Inspect
the registry for exact command/parameter classifications and exit-code contracts.
Do not parse help formatting, diagnostic prose, HTML or console colors as a
machine interface.

The stable commitments are deliberately bounded:

- File conversion validates complete values, columns/order and admitted types;
  ambiguous sheets, records and delimiters require a choice. Source bytes and
  effective options identify the load; changing a captured frame requires a new
  capture. GeoJSON structures can be transported without making nested geometry
  a supported semantic-comparison type. Local loading is not a path sandbox.
- IR validation and both native compiler checks define the supported plan.
  Each built-in engine executes independently; no arbitrary program translation, fallback
  engine, implicit rounding or pruning of a failed guard is promised. Successful
  compilation is not equivalence or proof of an expected result's independence.
- ML interface stability protects fit/calibration/inference separation, feature
  admission and explicit unavailable states. Callers remain responsible for the
  meaning of selected features and normal-training/calibration origins; validating
  a vector is not automatic detection of every possible label encoding or leak.
  Stability does not promise detection power,
  identical trained forests across dependency versions or a throughput target.
  Operational rules R and the external language R remain different components.
- The R reviewer admits its documented exact policy/type subset and external
  Rscript. The bound finalizer verifies execution/profile/IF/artifact association;
  the low-level finalizer requires the caller to associate component decisions.
  A missing reviewer, unsupported contract or disagreement cannot produce an
  accepted result. Its process timeout excludes earlier Python capture time.

`PipelineInput`, `EvidenceFile`, `StageRecord`, `PipelineSpec` and `PipelineResult`, and the
versioned spec/result formats, are protected shared models because migration
embeds them. This does not stabilize `run_pipeline`, its standalone request,
workflow APIs or the private local directory layout. Persisted semantic formats
and producer layout are separate commitments. The per-name register is decisive.

## Deprecation and persisted-format commitments

This prospective policy began with the private STEP6 candidate. It does not
invent prior public releases or assert a deprecation has already happened.

1. Incompatible stable changes require a changelog notice naming affected
   surfaces, reason, replacement, migration example and earliest removal date/version
2. Callable Python entry points emit `DeprecationWarning`; CLI invocations warn
   on stderr without changing exit status merely because of the warning
3. Removal waits for **both at least two subsequent minor releases and 90 days**.
   A notice in 0.12 cannot be removed before 0.14 or day 90; time alone is insufficient
4. During 0.x, a stable removal occurs in an announced minor; from 1.x it requires
   a major, with the same notice window. Patch releases normally preserve it
5. Experimental changes can occur in a minor with changelog and migration in that
   release. Downgrading a stable label cannot evade the stable notice window
6. Withdrawing a persisted-format reader follows the stable window even if its
   producer is experimental. Historical evidence is not rewritten or reinterpreted

**Fail-closed exception:** security flaws, corrupted evidence, semantic loss or
false equivalence may be rejected immediately, including in a patch. Record
scope, reason, safe recovery/migration and a regression. Compatibility never
requires preserving a false success. An unrelated capability expansion is not
permission to change a valid old meaning silently.

Package version, format version and contract revision remain independent.
Incompatible writes need a new format and explicit migration; unknown versions
are rejected. Historical fixtures identify private commits and formats rather
than invented public releases. Their readers verify those admitted artifacts;
they do not promise arbitrary old data will be accepted.

HTML/text/notebook presentation may evolve while JSON semantic contracts remain.
Historical report verification uses the admitted frozen format behavior, not the
current renderer's bytes. Rehashing modified/corrupt evidence does not make it
valid. Preserve originals and create new, traceable migrated artifacts when an
explicit conversion exists. No automatic universal converter is promised.

## Filesystems, concurrency and external integrations

Local evidence publication uses exclusive creation and, where specified, atomic
hard links. Verify your filesystem and permissions; network/object stores are not
implicitly supported. Do not make independent processes write a shared DuckDB
file. A production service owns snapshot publication, writer coordination,
security, concurrency and aggregate resource limits.

The core has no requirement for OCI, SERCOP, a data warehouse or the benchmark
package. Explicit DataSource/adapter integrations can provide external services;
that integration's authentication, network policy, snapshot consistency and
acceptance must be verified separately. A local synthetic test does not certify
a real service or another team's implementation.

## Python 3.10 legacy-runtime boundary

EquiFrame compatibility with Python 3.10 does not provide upstream security
maintenance or vendor extended maintenance. Deployment owners must check their
runtime's [current lifecycle](https://devguide.python.org/versions/) and their
own maintenance policy; this does not remove 3.10 from the compatibility matrix.

The a8 compatibility changes preserve named type aliases through
`typing_extensions.TypeAliasType`, retain strict typing, use local Decimal
contexts without 3.11-only keyword arguments, and validate supported timestamp
literals consistently while retaining their original nanoseconds/text.
Windows junction checks use lstat reparse tags available since 3.8; simulated
branch tests alone are not actual Windows execution. The measured platform
scope is the table above; preserved roadmap cells do not add unexecuted support.

The benchmark declares `tomli` only below Python 3.11. Source-development tools
use the same fallback from the explicitly declared development dependency.
Normal pip resolution chooses compatible branches within unchanged native
dependency ranges; the recorded locks identify those branches per Python.
