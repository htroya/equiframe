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
