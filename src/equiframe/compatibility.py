"""Inspectable compatibility commitments, separate from execution admission.

These records describe implemented boundaries; they do not run a probe, register
plugins, import optional engines, or certify a dependency/platform combination.
Use runtime validation and a measured conformity receipt for those questions.
"""

from __future__ import annotations

from typing import Annotated, Literal, cast

from pydantic import BeforeValidator

from equiframe._base import FrozenModel, Text, strict_bool_literal, strict_int_literal
from equiframe._stability_inventory import (
    CLI_INVENTORY,
    EXPERIMENTAL_API,
    SCHEMA_INVENTORY,
    STABLE_API,
    STABLE_FEATURE_SCOPES,
)
from equiframe.adapters import DuckDBAdapter, PandasAdapter, PolarsAdapter
from equiframe.execution_types import EngineCapabilities


class CompatibilityPolicy(FrozenModel):
    """Prospective policy, effective at the STEP6 candidate; not release history."""

    policy_version: Literal["1.0"] = "1.0"
    stable_notice_minor_releases: Annotated[Literal[2], BeforeValidator(strict_int_literal)] = 2
    stable_notice_days: Annotated[Literal[90], BeforeValidator(strict_int_literal)] = 90
    notice_threshold: Literal["both"] = "both"
    applies_during_zero_major: Annotated[Literal[True], BeforeValidator(strict_bool_literal)] = True
    notices: tuple[Text, ...] = (
        "CHANGELOG entry with affected surfaces, replacement and migration example",
        "DeprecationWarning at the deprecated Python entry point, when callable",
        "stderr notice for a deprecated CLI invocation, without changing its exit code",
    )
    stable_breaking_release: Literal["major_or_announced_zero_major_minor"] = (
        "major_or_announced_zero_major_minor"
    )
    experimental_change_notice: Literal["changelog_and_migration_in_same_release"] = (
        "changelog_and_migration_in_same_release"
    )
    fail_closed_exception: Text = (
        "Security, corrupted evidence or false-equivalence fixes may immediately reject "
        "previously accepted inputs. Publish affected scope, reason, replacement/recovery "
        "and a regression test; never reinterpret a failure as success."
    )
    persisted_format_rule: Text = (
        "Do not reinterpret an existing schema version or rewrite old evidence. "
        "Incompatible writes require a new format version and an explicit migration. "
        "Reader withdrawal follows the stable notice window even for experimental producers; "
        "security/correctness rejection remains fail-closed. Unknown versions are rejected."
    )
    dependency_support: Text = (
        "Declared Python and dependency ranges are admission metadata, not tested cells. "
        "Only an exact recorded candidate, environment, dependency set and corpus run "
        "establish observed conformity; no external certification is implied."
    )


class StabilityRecord(FrozenModel):
    """One explicitly classified public name, command or persisted surface."""

    surface: Literal["api", "cli", "format", "evidence", "presentation", "namespace"]
    name: Text
    status: Literal["stable", "experimental", "unsupported"]
    commitment: Text
    parameters: tuple[Text, ...] = ()
    exit_codes: tuple[int, ...] = ()
    schema_sha256: str | None = None


class CapabilityStage(FrozenModel):
    """Conditional capability of one stage, never a Cartesian-product claim."""

    stage: Literal["capture", "comparison", "native_execution", "migration"]
    status: Literal["supported_with_conditions", "rejected", "not_applicable"]
    scope: Text
    conditions: tuple[Text, ...]
    losses: tuple[Text, ...]
    implementation: tuple[Text, ...]
    tests: tuple[Text, ...]


class AdapterCapability(FrozenModel):
    """Descriptive register entry; EngineCapabilities remains the runtime port."""

    adapter: Literal["arrow", "pandas", "polars", "duckdb"]
    required_extra: Literal["arrow", "pandas", "polars", "duckdb"]
    component: Literal["packages/equiframe"] = "packages/equiframe"
    ownership_reference: Literal["docs/TEAM_INTEGRATION.md#1-propiedad-y-dependencias"] = (
        "docs/TEAM_INTEGRATION.md#1-propiedad-y-dependencias"
    )
    maintainer: Text | None = None
    maintenance_status: Literal["unassigned", "assigned"] = "unassigned"
    evidence_scope: Literal["repository_corpus_only_no_external_certification"] = (
        "repository_corpus_only_no_external_certification"
    )
    runtime: EngineCapabilities | None
    stages: tuple[CapabilityStage, ...]


def get_compatibility_policy() -> CompatibilityPolicy:
    """Return the current prospective deprecation and format-reader commitment."""
    return CompatibilityPolicy()


_STABLE_SCOPE_COMMITMENTS = {
    "datasets": (
        "Local bytes and effective read options identify the source; ambiguous structure "
        "requires an explicit choice. Conversion validates complete values, column order "
        "and admitted types without implicit loss; mutated captures are rejected. "
        "Use close/context management for owned DuckDB resources. Nested GeoJSON transport "
        "does not imply nested comparison support; no filesystem sandbox is promised."
    ),
    "capture": (
        "Only explicit trusted DuckDB SQL/relation capture is admitted, with caller/session "
        "ownership, native type checks and cooperative budgets; connections, callbacks and "
        "SQL strings are not inferred as direct comparison inputs."
    ),
    "migration": (
        "The closed IR, validation diagnostics and per-engine capability checks define "
        "the admitted subset. Built-in engines execute their own compiled plans "
        "on verified inputs; "
        "unsupported plans and semantic loss fail closed. Compilation/execution success "
        "does not establish equivalence or correctness of an independent expected result. "
        "No arbitrary Python/SQL translation or hard process-memory limit is promised."
    ),
    "detection": (
        "Built-in fit/scoring consumes validated profile features, not selection labels or "
        "engine metadata; callers remain responsible for meaningful feature/normal selection. "
        "Fit, normal calibration and inference remain separate; unavailable support is "
        "not no_alert, and H preserves rule alerts. API/format compatibility does not "
        "promise scientific accuracy, cross-version fitted-model parity or speed."
    ),
    "r_review": (
        "Language R independently reviews verified transport under its admitted exact "
        "contract subset; absence, unsupported policy and disagreement cannot establish "
        "acceptance. The execution finalizer verifies artifact/profile/IF bindings. "
        "The low-level finalizer requires caller-associated component decisions. "
        "Rscript is external and process timeout excludes prior Python capture time."
    ),
}


def _stable_api_commitment(name: str) -> str:
    base = "Documented signature, typed values and semantic/error contract; stable notice window"
    for scope, names in STABLE_FEATURE_SCOPES:
        if name in names:
            return base + "; " + _STABLE_SCOPE_COMMITMENTS[scope]
    return base


def get_stability_register() -> tuple[StabilityRecord, ...]:
    """Return the exhaustive, explicit core API/CLI/schema classification.

    Export names and CLI options are deliberately not discovered at runtime:
    adding a surface must also classify it, and drift tests enforce this rule.
    Experimental does not weaken format integrity or safe failure semantics.
    """
    records = [
        StabilityRecord(
            surface="api",
            name="equiframe." + name,
            status=cast('Literal["stable", "experimental"]', status),
            commitment=(
                _stable_api_commitment(name)
                if status == "stable"
                else "Producer/algorithm or extension surface may evolve; "
                "explicit release migration"
            ),
        )
        for names, status in ((STABLE_API, "stable"), (EXPERIMENTAL_API, "experimental"))
        for name in names
    ]
    records.extend(
        StabilityRecord(
            surface="cli",
            name="equiframe " + name,
            status=cast('Literal["stable", "experimental"]', status),
            commitment=(
                "Command, listed parameters and exit meanings; help/error prose is not byte-stable"
            ),
            parameters=parameters,
            exit_codes=codes,
        )
        for name, status, parameters, codes in CLI_INVENTORY
    )
    records.extend(
        StabilityRecord(
            surface="format",
            name=name,
            status=cast('Literal["stable", "experimental"]', status),
            commitment=(
                "Versioned JSON shape and semantics; reader withdrawal uses the stable notice "
                "window independently of producer maturity; no automatic historical rewrite"
            ),
            schema_sha256=digest,
        )
        for name, status, digest in SCHEMA_INVENTORY
    )
    records.extend(
        (
            StabilityRecord(
                surface="format",
                name="equiframe-metadata-json-v1",
                status="stable",
                commitment="Contract canonicalization bytes and fingerprint algorithm; not JCS",
            ),
            StabilityRecord(
                surface="evidence",
                name="comparison.json/differences.jsonl/diff-contract.json",
                status="stable",
                commitment=(
                    "Versioned comparison/difference/declaration semantics; existing readers "
                    "validate recorded evidence without executing a source; raw URI portability "
                    "is not guaranteed"
                ),
            ),
            StabilityRecord(
                surface="evidence",
                name="comparison-report/evidence-manifest.json",
                status="stable",
                commitment=(
                    "Closed report inventory, verified hashes, disclosure policy and completion; "
                    "reader verification preserves historical bytes and never authenticates authors"
                ),
            ),
            StabilityRecord(
                surface="evidence",
                name="pipeline/migration/workflow-local-layout",
                status="experimental",
                commitment=(
                    "Producer layout may evolve; recorded versions retain the reader notice "
                    "window; integrity, completion and semantic decisions remain separate"
                ),
            ),
            StabilityRecord(
                surface="presentation",
                name="HTML/text/notebook/error-prose",
                status="experimental",
                commitment=(
                    "Visual layout, wording, CSS and bytes may change; schema-tagged JSON "
                    "and recorded hashes are the interchange surfaces; no HTML scraping contract"
                ),
            ),
            StabilityRecord(
                surface="namespace",
                name="equiframe_benchmark",
                status="experimental",
                commitment=(
                    "Separate distribution and experimental protocol; this core register "
                    "does not enumerate or certify its API or scientific results"
                ),
            ),
            StabilityRecord(
                surface="namespace",
                name="equiframe.eda",
                status="experimental",
                commitment=(
                    "Optional standalone diagnostics; exact nested API names/signatures/shapes "
                    "are explicitly inventoried in equiframe.eda._inventory. No change to "
                    "migration/Verify or detectors; unavailable metrics are not zero alerts."
                ),
            ),
            StabilityRecord(
                surface="namespace",
                name="equiframe.benchmark",
                status="unsupported",
                commitment=(
                    "Quarantined helpers raise UnsupportedBenchmarkError; CLI exits 2 "
                    "except help. No evaluation, migration or replacement compatibility promised"
                ),
            ),
        )
    )
    return tuple(sorted(records, key=lambda record: (record.surface, record.name)))


_ENGINE_CLASS = {"pandas": "Pandas", "polars": "Polars", "duckdb": "DuckDB"}

_SCALAR_TYPES = (
    "Scalar NULL, bool, signed/unsigned integers, float32/64, text, fixed-scale decimal, "
    "date32/date64 and timestamps only as admitted by each capture path; nested, binary, "
    "dictionary/category and extension semantics are not silently decoded"
)
_LOST_BEFORE_CAPTURE = (
    "NULL/NaN, original per-cell timezone offset/provider, decimal signed zero or exponent "
    "distinctions already erased by the input representation cannot be reconstructed"
)
_COMPARISON = CapabilityStage(
    stage="comparison",
    status="supported_with_conditions",
    scope="Materialized captures compared by the complete comparison kernel; no native query",
    conditions=(
        "Contract output schema, explicit keys or bag/sequence policy; incomplete/duplicate keys "
        "and invalid expected references never establish equivalence",
        "Exact physical types by default; authorized lossless mapping, index ignore or column "
        "order relaxation needs an explicit policy/justification",
        "Numeric/absence/temporal policy is applied only where declared; budgets can produce "
        "not_evaluable; no all-types/all-policies Cartesian-product support claim",
    ),
    losses=(_LOST_BEFORE_CAPTURE,),
    implementation=("equiframe.comparison.compare", "equiframe.diff.diff"),
    tests=(
        "tests/test_comparison.py::test_absence_nan_empty_zero_are_distinct",
        "tests/test_comparison.py::test_permutation_and_multiplicity_property",
        "tests/test_comparison.py::test_budget_exhaustion_never_equivalent",
    ),
)
_COMMON_MIGRATION = (
    "Closed IR: Scan, Project, Filter, widening Cast, inner/left/right/full/semi/anti EquiJoin "
    "with matchable-key cardinality, Aggregate, Sort, Concatenate, deterministic Deduplicate "
    "and deterministic Window (row_number, exact-type lag/lead)",
    "Signed/unsigned 8/16/32/64-bit integer add/subtract/multiply reject overflow; "
    "Decimal precision <=38; exact multiply declares summed scales; DecimalRound declares "
    "precision/scale and rounding; division/localization have per-engine capability boundaries",
    "Timestamp transport preserves declared unit/zone; float join/group/sort/dedup/window keys and "
    "floating sum/min/max remain rejected; count_valid may consume float",
    "Fallible expressions inside Coalesce, Conditional or boolean short-circuit forms "
    "require preceding Project checkpoints; integer division is rejected",
    "No arbitrary Python/SQL translation, remote execution, implicit casts or cross-engine "
    "fallback; validate_ir and both compiler checks remain authoritative",
)
_MIGRATION_TESTS = (
    "tests/test_native_integer_arithmetic.py::test_native_integer_results_preserve_exact_width_and_bag",
    "tests/test_migration_backends.py::test_each_native_adapter_is_invoked_once_without_other_backend_fallback",
    "tests/test_migration_backends.py::test_native_decimal_sum_currency_groups_and_all_null",
    "tests/test_migration_semantic_directions.py::test_semantic_native_directions_and_independent_validation_scope",
    "tests/test_migration_product_semantics.py::test_join_cardinality_composite_key_option_matrix",
    "tests/test_migration_product_semantics.py::test_timestamp_ir_exact_unit_zone_transport",
    "tests/test_migration_product_semantics.py::test_decimal_multiply_exact_scale_and_round",
    "tests/test_migration_windows.py::test_six_migration_directions_verify_windows_against_literal_expected",
    "tests/test_window_semantics.py::test_native_lag_preserves_values_and_literal_column_names",
)


def _native_stage(engine: str) -> CapabilityStage:
    details = {
        "pandas": (
            "Trusted PandasTransformation callback on isolated DataFrames; no lazy return",
            "Arrow-backed decimal up to precision 76; meaningful index retained separately; "
            "zero-column tables with rows are rejected",
        ),
        "polars": (
            "Trusted PolarsTransformation callback; DataFrame/LazyFrame output is collected",
            "decimal128 precision <=38 with nonnegative scale; date64 rejected; timestamp "
            "seconds transported as milliseconds only after int64 overflow guard",
        ),
        "duckdb": (
            "Trusted SELECT/WITH or compiler-generated native checkpoints in a fresh "
            ":memory: connection; no external SQL access",
            "decimal128 precision <=38 with nonnegative scale; zoned ns, mismatched session "
            "zone, temporal infinity sentinels, casefold column collisions and zero columns "
            "are rejected; zoned s/ms must fit finite int64 microseconds; native output "
            "HUGEINT/UHUGEINT and unknown/extended types are rejected before Arrow export",
        ),
    }
    scope, restrictions = details[engine]
    return CapabilityStage(
        stage="native_execution",
        status="supported_with_conditions",
        scope=scope,
        conditions=(
            restrictions,
            "Pandas meaningful index requires an explicit columns/discard decision before "
            "transport to other engines; DuckDB input table identifiers are ASCII names",
            "Every input conversion must preserve row/column counts; a zero-column input "
            "cannot silently become a zero-row table on an installed native version",
            "Callbacks/SQL are trusted code, not a sandbox; budgets/checkpoints are cooperative "
            "and DuckDB memory_limit is not a whole-process RSS cap",
        ),
        losses=(
            _LOST_BEFORE_CAPTURE,
            "Observed output order is captured but SQL without ORDER BY does not guarantee it",
        ),
        implementation=(
            f"equiframe.adapters.{_ENGINE_CLASS[engine]}Adapter",
            "equiframe.adapters._input_capabilities",
        ),
        tests=(
            "tests/test_execution.py::test_five_families_native",
            "tests/test_execution_regressions.py::test_decimal_storage_width_and_negative_scale_capabilities",
            "tests/test_execution.py::test_index_requires_explicit_transport_policy",
            "tests/test_execution_regressions.py::test_zero_column_tables_keep_cardinality_or_reject_explicitly",
        ),
    )


def get_adapter_capabilities() -> tuple[AdapterCapability, ...]:
    """Return four immutable stage-separated capability descriptions.

    Entries are declarations tied to implementation and repository test nodes,
    not claims that those nodes ran in the caller's environment. The named
    maintainer is responsible for EquiFrame's adapter implementations, not the
    third-party engines. Native runtime capabilities are derived from the real
    adapters without importing optional dependencies.
    """
    captures = {
        "arrow": (
            "Eager pyarrow.Table direct diff capture; IPC/Parquet through explicit artifact inputs",
            "Direct diff rejects semantic schema/field metadata; only actual base Tables; "
            "physical full validation and detached IPC snapshots; row/byte budgets",
            "test_arrow_retains_schema_null_nan_decimal_and_timezone",
        ),
        "pandas": (
            "Eager pandas.DataFrame direct diff capture; native index captured separately",
            "Plain scalar columns and recognized extension dtypes only; attrs, named column "
            "axis, category/order metadata, object timestamps, heterogeneous numeric objects, "
            "signed-zero/nonfinite or mixed-exponent Decimal and subclasses are rejected",
            "test_pandas_decimal_and_zoned_timestamp_capture_is_exact",
        ),
        "polars": (
            "Eager polars.DataFrame direct diff capture; independently detached Arrow buffers",
            "LazyFrame direct diff is rejected without collect; categories, nested/object/int128 "
            "and unknown extension semantics rejected; explicit execution can collect lazy output",
            "test_polars_eager_preserves_null_nan_decimal_and_zones",
        ),
        "duckdb": (
            "Direct diff consumes an explicitly supplied DuckDBPyRelation with bounded "
            "Arrow IPC capture; capture_duckdb executes one trusted SELECT/WITH",
            "Direct relation submission authorizes execution under the caller-owned "
            "plan/session, with native type admission, row/byte budgets and cooperative "
            "cancellation. SQL strings/connections/readers are not inferred as inputs. "
            "Explicit SQL capture additionally requires exclusive borrowed ownership or a "
            "private session and disables "
            "extension autoload/install; finite temporal values are required",
            "test_explicit_duckdb_relation_capture_is_bounded_and_consumed_once",
        ),
    }
    native = {
        "pandas": PandasAdapter().capabilities(),
        "polars": PolarsAdapter().capabilities(),
        "duckdb": DuckDBAdapter().capabilities(),
    }
    records = []
    for engine in ("arrow", "pandas", "polars", "duckdb"):
        scope, restrictions, test = captures[engine]
        capture = CapabilityStage(
            stage="capture",
            status="supported_with_conditions",
            scope=scope,
            conditions=(
                _SCALAR_TYPES,
                restrictions,
                "Every accepted conversion must preserve row/column counts. In particular, "
                "a zero-column table with rows is accepted only if the installed conversion "
                "preserves cardinality; otherwise fail closed rather than compare zero rows",
            ),
            losses=(_LOST_BEFORE_CAPTURE,),
            implementation=(
                "equiframe._diff_capture.capture_native",
                "equiframe.tables.check_arrow",
            )
            + (("equiframe.duckdb_capture.capture_duckdb",) if engine == "duckdb" else ()),
            tests=("tests/test_diff_capture.py::" + test,)
            + (
                ("tests/test_diff_capture.py::test_polars_direct_capture_rejects_lost_cardinality",)
                if engine == "polars"
                else (
                    "tests/test_duckdb_capture.py::test_capture_survives_source_change_and_connection_close",
                )
                if engine == "duckdb"
                else ()
            ),
        )
        if engine == "arrow":
            execution = CapabilityStage(
                stage="native_execution",
                status="not_applicable",
                scope="Arrow is a capture/transport input; no built-in Arrow execution adapter",
                conditions=("Supply an explicit trusted EngineAdapter for a new engine",),
                losses=(),
                implementation=("equiframe.adapters.native_adapter",),
                tests=(
                    "tests/test_compatibility_register.py::test_arrow_has_no_builtin_execution_or_compiler",
                ),
            )
            migration = CapabilityStage(
                stage="migration",
                status="not_applicable",
                scope="Arrow feeds captured inputs; it is not a built-in migration target",
                conditions=("Only pandas, polars and duckdb compilers are registered by default",),
                losses=(),
                implementation=("equiframe.migration.ports.native_compiler_registry",),
                tests=(
                    "tests/test_compatibility_register.py::test_arrow_has_no_builtin_execution_or_compiler",
                ),
            )
        else:
            execution = _native_stage(engine)
            specific = {
                "pandas": "Pandas retains Arrow dtypes/null masks, exact or explicitly rounded "
                "Decimal division, timestamp s/ms/us/ns and explicit DST localization",
                "polars": "Polars IR transports unchanged timestamp int64 ticks in s/ms/us/ns "
                "and declared zones through an explicit codec; native transition-table/POSIX-rule "
                "localization from pinned installed tzdata resources; "
                "exact/rounded native coefficient "
                "Decimal division through precision 38; "
                "Decimal multiply uses checked native coefficients with summed output scales; "
                "native sums "
                "retain a conservative bound and localization declares DST policies",
                "duckdb": "DuckDB IR transports unchanged timestamp int64 ticks in s/ms/us/ns "
                "and declared zones through an explicit codec; native ICU localization with "
                "explicit fold/gap policies; "
                "exact/rounded native HUGEINT Decimal division through precision 38; "
                "explicit DecimalRound supports half_even and "
                "half_away_from_zero; native eager checkpoints materialize relational nodes "
                "and nested arithmetic/rounding/localization before later pruning; "
                "compiled programs require a compatible native checkpoint adapter",
            }
            migration = CapabilityStage(
                stage="migration",
                status="supported_with_conditions",
                scope="Closed-IR native compilation and pairwise execution on identical captures",
                conditions=(*_COMMON_MIGRATION, specific[engine]),
                losses=("No declared loss is silently accepted; unsupported plans fail closed",),
                implementation=(
                    "equiframe.migration.validation.validate_ir",
                    "equiframe.migration.runner.check_migration",
                    f"equiframe.migration.backends.{engine}.{_ENGINE_CLASS[engine]}Compiler",
                ),
                tests=_MIGRATION_TESTS
                + (
                    (
                        "tests/test_duckdb_checkpoints.py::test_native_guards_survive_later_empty_filter",
                        "tests/test_duckdb_checkpoints.py::test_non_native_adapter_is_rejected_before_provider_even_without_timestamps",
                        "tests/test_duckdb_checkpoints.py::test_transport_budget_checks_materialized_intermediate_before_empty_output",
                    )
                    if engine == "duckdb"
                    else ()
                ),
            )
        records.append(
            AdapterCapability(
                adapter=engine,
                required_extra=engine,
                maintainer="Hernán Troya (htroya); EquiFrame adapter implementation only",
                maintenance_status="assigned",
                runtime=native.get(engine),
                stages=(capture, _COMPARISON, execution, migration),
            )
        )
    return tuple(records)
