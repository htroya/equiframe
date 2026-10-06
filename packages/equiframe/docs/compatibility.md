# Compatibility and stability

[Handbook](index.md) · [Upgrading](upgrading.md) · [Dependencies](dependencies.md)

## Admission is not a measured support matrix

The private Alpha candidate declares **Python `>=3.12,<3.14`**, meaning 3.12 and
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

For this STEP9 artifact, use the supplied [release receipt](releasing.md) to see
which checks actually ran against its exact bytes. A configured workflow, test
source, historical receipt or unexecuted platform job is not a current pass.
No new Windows, macOS, ARM64, PyPy or other unrecorded platform support is claimed.
Older Windows results do not validate the current candidate. Skips, xfails,
blocked cells and missing receipts are not successful conformity checks.

The first-use kit has a narrower **Python 3.12-only** pinned dependency closure.
Using its commands on another interpreter does not extend that tested contract.

## Declared runtime dependencies

The installed wheel metadata is authoritative. Current direct ranges are:

| Profile | Dependencies |
|---|---|
| Base | pydantic `>=2.12,<3`; typer `>=0.20,<1`; tzdata `>=2025.2` |
| `arrow` | pyarrow `>=20,<26` |
| `pandas` | pandas `>=2.2,<4`; pyarrow `>=20,<26` |
| `polars` | polars `>=1.30,<2`; pyarrow `>=20,<26` |
| `duckdb` | duckdb `>=1.5.6,<2`; pyarrow `>=20,<26` |
| `engines` | All three engines and the same Arrow range |
| `ml` | scikit-learn `>=1.7,<1.10`; numpy `>=2,<3` |

Minimum-direct testing means a mutually resolvable minimum direct set with
available binary wheels and compatible transitive dependencies. It does not mean
all historical transitive minima. Binary availability may raise a practical
minimum on a Python/platform. A recent-permitted resolution is time-bound and
must be identified by its pins and hashes.

Base imports remain light even when extras are installed: importing EquiFrame
or its compatibility registers does not import Arrow, pandas, Polars, DuckDB,
NumPy or scikit-learn. The selected operation loads its required dependencies.
Missing extras fail explicitly with a diagnostic identifying the dependency.

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

| Status | Main surfaces |
|---|---|
| Stable | Contract/value/policy/error models and serialization; capture inputs/ports/native execution; comparison/diff/declarations/readers; R; assertions; common comparison reports; operational Verify; supported evidence bundles; compatibility inspectors |
| Experimental | Explicit `capture_duckdb`; profiles/preprocessing/IF/MAD/H; relational IR/compilers/migration; ingestion/destinations/workflows; pipeline/reporting/reduction |
| Unsupported | Quarantined historical `equiframe.benchmark` helper |
| Outside this inventory | Private `_...` internals, dependency APIs and the separate benchmark package's experimental API |

Stable protects the documented signature and semantic/error contract within
admitted capabilities. It is not a certification, maturity claim for every
workflow, service-level guarantee or promise of speed. Experimental code still
must reject unsafe/unsupported input, preserve historical meaning and report
failures honestly. Adding an export requires an explicit reviewed classification.

Stable CLI includes contract validation, comparison, operational Verify and
bundles. Migration, workflows, ingestion, pipeline execution/reporting, evidence
inspection and reduction retain their classified experimental commands. Inspect
the registry for exact command/parameter classifications and exit-code contracts.
Do not parse help formatting, diagnostic prose, HTML or console colors as a
machine interface.

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
