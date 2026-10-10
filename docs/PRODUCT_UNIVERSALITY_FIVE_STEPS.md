# Product universality in five implementation steps

This work implements the user's product plan. It does not replace the historical
UV01–UV12 score, alter scientific methods or claim unexecuted platform support.
Work remains manual; no Actions, public release or paid resources are requested.

1. **Sources and domain-independent contracts:** expose bounded SQLite query and
   caller-owned response inputs alongside CSV/JSON/Parquet; preserve ingestion
   receipts, typed mappings, NULLs, textual identifiers and row multiplicity.
2. **Native operations:** extend the existing relational IR with deterministic
   partitioned windows, implemented independently in pandas, Polars and DuckDB.
3. **Semantic preservation:** validate window types, units, NULLs, tie policies
   and overflow with independent expected results and explicit diagnostics.
4. **Extensions and bounded processing:** compose independently implemented
   data sources and enforce cumulative budgets, cancellation and cleanup.
5. **Installation and first use:** ship a complete CSV-to-SQL example, documented
   interfaces and an installed wheel/sdist validation outside the checkout.

Each step has its own reviewable commit and relevant behavior checks. Existing
native joins, filters, aggregates, sorts and conservative casts are reused.
Unavailable native hosts remain untested; license and release gates remain
separate. New sources/extensions neither implement José's infrastructure nor
redefine Jhair's domain warehouse.

Step 1 validation (Windows, CPython 3.12, manual): source, ingestion, ingestion
batch and compatibility checks: 194 passed, 3 existing symlink-capability skips.
Ruff and strict mypy passed for the new source implementation. Private JUnit
receipts stay outside version control.

Step 2 validation (same manual environment): 291 native window/backend/product
checks passed, including all six directed migrations with a literal independent
expected. Migration code passed Ruff and strict mypy. The seven experimental
IR-containing schemas and their registered digests were regenerated together;
historical fixtures were not rewritten.

Step 3 validation: 12 semantic boundary checks and 22 compatibility-register
checks passed. The historical compatibility run passed its 386 corpus checks;
its one new-schema register failure was corrected using the existing canonical
JSON hash algorithm and the complete 22-check register was rerun successfully.
Extreme integers, Decimal(38,2), NULL/NaN, dates, UTC microseconds, special names,
global ordering/offsets, incompatible units and error-pruning boundaries are
covered with independent expectations. Capability records now include windows.

Step 4 validation: 40 source, extension and compatibility-register checks passed.
External providers are captured once for genuine native migration. Batch schema
drift, illegal NULLs, cumulative budgets, upstream errors, cleanup and SQLite
interruption before the first result are exercised. New source code passes
Ruff and strict mypy. Final materialization and cooperative (not hard RSS) limits
remain documented.

Step 5 is implemented in the private A11 core/benchmark pair. The installed
`universal_first_use` example executes six inputs and three native engines under
one contract, with literal independent expectations and correct/different/corrupt
cases. The Spanish guide is shipped in the wheel. New APIs remain experimental.

Final manual validation:

| Check | Observed result |
|---|---|
| Core full Windows run, CPython 3.12.4 | 4527 passed, 25 existing capability skips, 3 obsolete compiler-revision assertions failed |
| Complete affected arithmetic/build/source checks after correction | 51 passed; all three stale expectations corrected to actual v3/v5 identities |
| Benchmark full Windows run | 620 passed, 7 existing Windows/POSIX capability skips |
| Final installed Linux ARM64 candidate, CPython 3.12.15 | 122 passed, 0 failures/skips |
| Installed examples, Windows and Linux | Correct 0; discrepant 1; corrupt response 3; 18 real native runs per case |
| Optimized installed Windows corrupt example (`-O`) | Rejected with exit 3 |
| Dependency and installed payload checks | Both final wheels match installed bytes; dependency checks pass |
| Core/benchmark Ruff and strict mypy | Passed; 94 core and 37 benchmark source/tool files checked |
| Generated assets | 67 core assets and 45 benchmark schemas verified |
| Wheel/sdist metadata | Four final distributions pass strict twine checks |
| Native reconstruction from final sdists | Both wheels reproduce exact Windows SHA-256 on Linux |

The full Windows receipt retains its initial three failures; it is not described
as a single all-green full run. The corrected modules were rerun successfully
and exercised again from the final installed Linux artifact. Platform skips
were not removed or converted to successes. Private receipts and intermediate
attempts remain outside Git.

The build fix changes only ZIP creator metadata to the Unix convention used by
already-normalized modes. It preserves payload, RECORD, entry order and modes.
The sdist ships the hook; core never imports it at runtime. Working text follows
the repository LF policy; immutable historical byte fixtures are untouched.
SQLite also accepts Python builds without the optional extension-loading API;
the real connection remains read-only with extensions disabled by default.

Final artifact SHA-256:

| Distribution | SHA-256 |
|---|---|
| Core wheel | `11cbae825f3b2ac4f6e9a6378d589bbb6f74be37587a3c40a591b64a7496a15e` |
| Core sdist | `82527d8c9e9f33fe6d3d8b5df43d65f531c355a577f900a5257ee9a04a8fe5ca` |
| Benchmark wheel | `f77d06012e92ea3bc72a1ada4d02938827880622d7560501ba0a251e132fc2b3` |
| Benchmark sdist | `b775f5909c3122bb5313800ff49a22ab822b8bb922e55496289ae279ff903241` |

Final VM directory: `/home/hernan/equiframe-product-a11-20261009-final` on the
existing `157.137.227.1` host. It contains uploaded hash-checked distributions,
source unpacking, an isolated offline dependency environment, JUnit, reports,
example outputs and exact rebuilt wheels. Earlier A11 directories retain the
pre-correction packaging observations. The A10 labs remain historical.

Mac native hosts and the full twenty-cell A11 matrix remain unexecuted. These five
product steps do not close the UV01–UV12 score, licensing, independent human
review, public release or real-domain adoption. No Actions were executed and no
paid resources were created. Code is delivered on the review branch; main
integration remains subject to the existing owner-review rule.
