"""Generate versioned schemas and synthetic contract fixtures; --check never writes."""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from equiframe import (
    AggregateCheck,
    ArtifactRef,
    BooleanType,
    BooleanValue,
    CardinalityCheck,
    CheckResult,
    ColumnSpec,
    ComparisonDifference,
    ComparisonOptions,
    ComparisonReport,
    ComparisonResult,
    ComparisonSpec,
    ComponentDetectionResult,
    Contract,
    DatePolicy,
    DateType,
    DateValue,
    DecimalType,
    DecimalValue,
    DetectionResult,
    DetectorBundle,
    DetectorFit,
    DetectorScoreResult,
    DiffCaptureOptions,
    DiffContract,
    EquivalenceDecision,
    EquivalencePolicy,
    EvidenceBundle,
    EvidenceEvent,
    ExecutionPlan,
    ExecutionResult,
    ExpectedProvenance,
    Family,
    FeatureMatrix,
    FloatType,
    FloatValue,
    HybridDecision,
    IgnoredOrder,
    IndependentReviewEvidence,
    IngestionResult,
    IngestionSpec,
    IntegerType,
    IntegerValue,
    JoinCheck,
    KeyCheck,
    KeySpec,
    LoadReceipt,
    MigrationOptions,
    MigrationRequest,
    MigrationResult,
    MigrationSpec,
    NaNPolicy,
    NaNValue,
    NormalCalibrationProfiles,
    NormalTrainingProfiles,
    NullPolicy,
    NullValue,
    NumericPolicy,
    OrderCheck,
    OrderPolicy,
    PipelineRequest,
    PipelineResult,
    PipelineSpec,
    PreconditionSpec,
    PreprocessorBundle,
    ProfileFeature,
    ProfileResult,
    ProfileSpec,
    ReductionObservation,
    ReductionOptions,
    ReductionResult,
    RelationalPlan,
    ReportEvidenceManifest,
    ReportOptions,
    ReportPublicationManifest,
    ReviewedDecision,
    RExecutionBinding,
    RReviewBinding,
    RReviewOptions,
    RReviewResult,
    RuleDefinition,
    RuleEvaluation,
    RuleFinding,
    RuleOptions,
    RuleSpec,
    SchemaCheck,
    SignificantOrder,
    SnapshotManifest,
    SortSpec,
    StringType,
    StringValue,
    TableKeyScope,
    TableSchema,
    TableSpec,
    TimestampPolicy,
    TimestampType,
    TimestampValue,
    Tolerance,
    VerificationRequest,
    VerificationResult,
    WorkflowRequest,
    WorkflowResult,
    WorkflowSpec,
    canonical_contract_bytes,
    contract_fingerprint,
    contract_json_schema,
    default_rule_registry,
    rule_set_fingerprint,
)
from equiframe.eda import EdaConfig, EdaManifest, EdaResult
from equiframe.eda import Source as EdaSource

ROOT = Path(__file__).resolve().parents[1]

NULLS = NullPolicy(representations=("null",))


def string(name: str, *, samples: tuple[StringValue, ...] = ()) -> ColumnSpec:
    return ColumnSpec(
        name=name,
        logical_type=StringType(),
        nullable=False,
        null_policy=NULLS,
        allowed_values=samples,
    )


def integer(name: str) -> ColumnSpec:
    return ColumnSpec(
        name=name,
        logical_type=IntegerType(bits=64, signed=True),
        nullable=False,
        null_policy=NULLS,
        numeric_policy=NumericPolicy(comparison="exact", unit="rows"),
        allowed_values=(IntegerValue(value=0),),
    )


def money(name: str) -> ColumnSpec:
    return ColumnSpec(
        name=name,
        logical_type=DecimalType(precision=38, scale=18),
        nullable=False,
        null_policy=NULLS,
        numeric_policy=NumericPolicy(comparison="exact", unit="synthetic_currency"),
        allowed_values=(
            DecimalValue(value=Decimal("12345678901234567890.123456789012345678")),
            DecimalValue(value=Decimal("-0.000000000000000000")),
        ),
    )


def table(
    name: str,
    columns: tuple[ColumnSpec, ...],
    *,
    keys: tuple[KeySpec, ...] = (),
    order: OrderPolicy | None = None,
) -> TableSpec:
    return TableSpec(
        name=name,
        schema_spec=TableSchema(
            columns=columns,
            keys=keys,
            multiplicity="preserve",
            order=order if order is not None else IgnoredOrder(),
        ),
    )


def key(column: str) -> KeySpec:
    return KeySpec(
        name="primary", columns=(column,), unique=True, incomplete="reject", scope=TableKeyScope()
    )


def contract(
    family: Family, inputs: tuple[TableSpec, ...], output: TableSpec, definition: RuleDefinition
) -> Contract:
    return Contract(
        schema_version="1.0",
        contract_id="synthetic." + family,
        revision=1,
        family=family,
        inputs=inputs,
        output=output,
        preconditions=(
            PreconditionSpec(
                precondition_id="input_schema", requirement=SchemaCheck(table=inputs[0].name)
            ),
        ),
        rules=(
            RuleSpec(
                rule_id="output_schema",
                revision=1,
                specification=SchemaCheck(table=output.name),
                severity="error",
                required=True,
            ),
            RuleSpec(
                rule_id="family_declaration",
                revision=1,
                specification=definition,
                severity="warning",
                required=True,
                applicability=("input_schema",),
            ),
        ),
    )


def examples() -> dict[str, Contract]:
    identifiers = string("id", samples=(StringValue(value="0007"),))
    null_columns = (
        identifiers,
        ColumnSpec(
            name="text",
            logical_type=StringType(),
            nullable=True,
            null_policy=NULLS,
            allowed_values=(StringValue(value=""), StringValue(value="0"), NullValue()),
        ),
        ColumnSpec(
            name="signal",
            logical_type=FloatType(bits=64),
            nullable=True,
            null_policy=NULLS,
            nan_policy=NaNPolicy(handling="distinct"),
            numeric_policy=NumericPolicy(
                comparison="approximate",
                unit="synthetic_sensor",
                tolerance=Tolerance(
                    absolute=Decimal("0.0001"),
                    relative=Decimal("0.001"),
                    unit="synthetic_sensor",
                    justification="Synthetic sensor example, not benchmark policy",
                ),
            ),
            allowed_values=(FloatValue(value=0.0), NaNValue(), NullValue()),
        ),
        ColumnSpec(
            name="active",
            logical_type=BooleanType(),
            nullable=False,
            null_policy=NULLS,
            allowed_values=(BooleanValue(value=False), BooleanValue(value=True)),
        ),
        integer("count"),
        money("amount"),
    )
    supplier = string("supplier_id")
    date_column = ColumnSpec(
        name="day",
        logical_type=DateType(),
        nullable=False,
        null_policy=NULLS,
        temporal_policy=DatePolicy(
            lower=DateValue(value="2000-02-01"), upper=DateValue(value="2000-03-01"), closed="left"
        ),
        allowed_values=(DateValue(value="2000-02-29"),),
    )
    time_column = ColumnSpec(
        name="instant",
        logical_type=TimestampType(unit="ns", timezone="America/Guayaquil"),
        nullable=False,
        null_policy=NULLS,
        temporal_policy=TimestampPolicy(
            granularity="ns",
            timezone="America/Guayaquil",
            naive="reject",
            comparison="instant",
            ambiguous="reject",
            closed="both",
            lower=TimestampValue(
                value="2000-02-29T00:00:00.000000001-05:00", zone="America/Guayaquil"
            ),
            upper=TimestampValue(
                value="2000-02-29T23:59:59.999999999-05:00", zone="America/Guayaquil"
            ),
        ),
        allowed_values=(
            TimestampValue(value="2000-02-29T12:00:00.123456789-05:00", zone="America/Guayaquil"),
        ),
    )
    return {
        "nulls_types": contract(
            "nulls_types",
            (table("source", null_columns, keys=(key("id"),)),),
            table("result", null_columns, keys=(key("id"),)),
            KeyCheck(table="result", key="primary"),
        ),
        "joins": contract(
            "joins",
            (
                table("orders", (identifiers, supplier), keys=(key("id"),)),
                table("suppliers", (supplier, string("name")), keys=(key("supplier_id"),)),
            ),
            table("result", (identifiers, supplier, string("name"))),
            JoinCheck(
                left_table="orders",
                right_table="suppliers",
                left_columns=("supplier_id",),
                right_columns=("supplier_id",),
                relationship="many_to_one",
                unmatched="reject",
            ),
        ),
        "duplicates_order": contract(
            "duplicates_order",
            (table("source", (identifiers, integer("position"))),),
            table(
                "result",
                (identifiers, integer("position")),
                order=SignificantOrder(
                    by=(SortSpec(column="position", direction="ascending", nulls="last"),),
                    ties="preserve",
                ),
            ),
            OrderCheck(table="result", columns=("position",)),
        ),
        "aggregations": contract(
            "aggregations",
            (table("source", (string("currency"), money("amount"))),),
            table("result", (string("currency"), money("total")), keys=(key("currency"),)),
            AggregateCheck(
                table="source",
                group_by=("currency",),
                measure="amount",
                function="sum",
                output_table="result",
                output_column="total",
            ),
        ),
        "dates": contract(
            "dates",
            (table("source", (identifiers, date_column, time_column)),),
            table("result", (identifiers, date_column, time_column)),
            CardinalityCheck(table="result", minimum=0),
        ),
    }


def render_schema(schema: dict[str, object]) -> bytes:
    return (json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def profile_examples(contracts: dict[str, Contract]) -> dict[str, ProfileSpec]:
    result = {}
    for family, contract in contracts.items():
        features = [ProfileFeature(name="rows", metric="log_filas", table="result")]
        if family in ("joins", "duplicates_order", "aggregations"):
            features.append(
                ProfileFeature(
                    name="row_ratio",
                    metric="razon_salida_entrada",
                    table="result",
                    denominator_table=contract.inputs[0].name,
                )
            )
        if family == "nulls_types":
            features.extend(
                (
                    ProfileFeature(
                        name="text_nulls", metric="tasa_nulos", table="result", columns=("text",)
                    ),
                    ProfileFeature(
                        name="signal_nulls",
                        metric="tasa_nulos",
                        table="result",
                        columns=("signal",),
                    ),
                    ProfileFeature(
                        name="signal_nan", metric="tasa_nan", table="result", columns=("signal",)
                    ),
                )
            )
        if family == "joins":
            features.extend(
                (
                    ProfileFeature(
                        name="unmatched",
                        metric="claves_sin_pareja",
                        table="orders",
                        columns=("supplier_id",),
                        right_table="suppliers",
                        right_columns=("supplier_id",),
                        null_matches="never",
                    ),
                    ProfileFeature(
                        name="name_nulls", metric="tasa_nulos", table="result", columns=("name",)
                    ),
                )
            )
        if family == "duplicates_order":
            features.append(
                ProfileFeature(
                    name="duplicate_ids", metric="prop_duplicados", table="result", columns=("id",)
                )
            )
        if family == "aggregations":
            features.extend(
                (
                    ProfileFeature(
                        name="currency_cardinality",
                        metric="cardinalidad_rel",
                        table="result",
                        columns=("currency",),
                    ),
                    ProfileFeature(
                        name="total_nulls", metric="tasa_nulos", table="result", columns=("total",)
                    ),
                )
            )
        if family == "dates":
            for column in contract.output.schema_spec.columns:
                if column.logical_type.kind in ("date", "timestamp"):
                    features.append(
                        ProfileFeature(
                            name=column.name + "_invalid",
                            metric="fechas_invalidas",
                            table="result",
                            columns=(column.name,),
                            target=column,
                        )
                    )
        result[family] = ProfileSpec(family=contract.family, features=tuple(features))
    return result


def render_catalog(contracts: dict[str, Contract]) -> bytes:
    """Technical R freeze; intentionally separate from the scientific benchmark."""
    registry = default_rule_registry()
    implementation_ids = dict(registry.identities())
    options = RuleOptions()
    limitations = {
        "nulls_types": (
            "Key and schema checks cannot reconstruct failed source-to-output conversions."
        ),
        "joins": (
            "Join checks validate captured input relationships, not the full output projection."
        ),
        "duplicates_order": "Order check does not prove full multiplicity preservation.",
        "aggregations": (
            "Only declared sum by currency is reconciled; entity allocation is not checked."
        ),
        "dates": "Schema and row count do not prove every temporal value retains its entity.",
    }
    entries = []
    for family, contract in contracts.items():
        definitions = (
            *[p.requirement for p in contract.preconditions],
            *[r.specification for r in contract.rules],
        )
        entries.append(
            {
                "family": family,
                "contract_file": "../" + family + ".json",
                "contract_id": contract.contract_id,
                "contract_revision": contract.revision,
                "contract_sha256": contract_fingerprint(contract),
                "rule_set_sha256": rule_set_fingerprint(contract, registry, options),
                "preconditions": [p.model_dump(mode="json") for p in contract.preconditions],
                "rules": [r.model_dump(mode="json") for r in contract.rules],
                "implementations": {
                    definition.kind: implementation_ids[definition.kind]
                    for definition in definitions
                },
                "coverage": {
                    "declared_rule_count": len(contract.rules),
                    "declared_kinds": sorted({r.specification.kind for r in contract.rules}),
                    "required_rule_ids": [r.rule_id for r in contract.rules if r.required],
                },
                "limitations": limitations[family],
            }
        )
    document = {
        "schema_version": "1.0",
        "catalog_id": "equiframe.synthetic.rules",
        "catalog_revision": 1,
        "options": options.model_dump(mode="json"),
        "entries": entries,
        "status": "technical synthetic examples; not a reviewed benchmark or DW validation",
    }
    payload = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf8")
    document["catalog_sha256"] = hashlib.sha256(payload).hexdigest()
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    contracts = examples()
    assets = {
        ROOT / "examples" / (name + ".json"): canonical_contract_bytes(value)
        for name, value in contracts.items()
    }
    assets[ROOT / "examples" / "rules" / "catalog-1.0.json"] = render_catalog(contracts)
    for name, spec in profile_examples(contracts).items():
        assets[ROOT / "examples" / "profiles" / (name + ".json")] = render_schema(
            spec.model_dump(mode="json")
        )
    assets[ROOT / "schemas" / "contract-1.0.schema.json"] = render_schema(contract_json_schema())
    assets[ROOT / "schemas" / "artifact-ref-1.0.schema.json"] = render_schema(
        ArtifactRef.model_json_schema()
    )
    assets[ROOT / "schemas" / "execution-plan-1.0.schema.json"] = render_schema(
        ExecutionPlan.model_json_schema()
    )
    assets[ROOT / "schemas" / "execution-result-1.0.schema.json"] = render_schema(
        ExecutionResult.model_json_schema()
    )
    for name, model in (
        ("snapshot-manifest", SnapshotManifest),
        ("comparison-spec", ComparisonSpec),
        ("comparison-options", ComparisonOptions),
        ("comparison-result", ComparisonResult),
        ("equivalence-policy", EquivalencePolicy),
        ("equivalence-decision", EquivalenceDecision),
        ("comparison-report", ComparisonReport),
        ("report-options", ReportOptions),
        ("report-publication-manifest", ReportPublicationManifest),
        ("report-evidence-manifest", ReportEvidenceManifest),
        ("comparison-difference", ComparisonDifference),
        ("diff-contract", DiffContract),
        ("diff-capture-options", DiffCaptureOptions),
        ("rule-options", RuleOptions),
        ("rule-finding", RuleFinding),
        ("rule-check-result", CheckResult),
        ("rule-evaluation", RuleEvaluation),
        ("profile-spec", ProfileSpec),
        ("profile-result", ProfileResult),
        ("detector-fit", DetectorFit),
        ("detector-bundle", DetectorBundle),
        ("detector-score-result", DetectorScoreResult),
        ("detection-result", DetectionResult),
        ("component-detection-result", ComponentDetectionResult),
        ("hybrid-decision", HybridDecision),
        ("r-review-options", RReviewOptions),
        ("r-review-binding", RReviewBinding),
        ("r-execution-binding", RExecutionBinding),
        ("r-review-result", RReviewResult),
        ("reviewed-decision", ReviewedDecision),
        ("normal-calibration-profiles", NormalCalibrationProfiles),
        ("normal-training-profiles", NormalTrainingProfiles),
        ("preprocessor-bundle", PreprocessorBundle),
        ("feature-matrix", FeatureMatrix),
        ("evidence-event", EvidenceEvent),
        ("pipeline-spec", PipelineSpec),
        ("pipeline-request", PipelineRequest),
        ("pipeline-result", PipelineResult),
        ("reduction-options", ReductionOptions),
        ("reduction-observation", ReductionObservation),
        ("reduction-result", ReductionResult),
        ("relational-plan", RelationalPlan),
        ("migration-options", MigrationOptions),
        ("migration-spec", MigrationSpec),
        ("migration-request", MigrationRequest),
        ("migration-result", MigrationResult),
        ("verification-request", VerificationRequest),
        ("verification-result", VerificationResult),
        ("expected-provenance", ExpectedProvenance),
        ("independent-review-evidence", IndependentReviewEvidence),
        ("evidence-bundle", EvidenceBundle),
        ("ingestion-spec", IngestionSpec),
        ("ingestion-result", IngestionResult),
        ("workflow-spec", WorkflowSpec),
        ("workflow-request", WorkflowRequest),
        ("workflow-result", WorkflowResult),
        ("load-receipt", LoadReceipt),
        ("eda-config", EdaConfig),
        ("eda-manifest", EdaManifest),
        ("eda-result", EdaResult),
        ("eda-source", EdaSource),
    ):
        assets[ROOT / "schemas" / (name + "-1.0.schema.json")] = render_schema(
            model.model_json_schema()
        )
    failures = []
    for path, data in assets.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                failures.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if failures:
        parser.exit(1, "Assets differ: " + ", ".join(failures) + "\n")
    if args.check:
        # Current experimental schemas can change with a reviewed producer
        # release. Their explicit inventory must change in the same patch;
        # never automatically bless a new shape or rewrite historical evidence.
        from equiframe._stability_inventory import SCHEMA_INVENTORY

        generated = {
            path.name: hashlib.sha256(
                json.dumps(
                    json.loads(data), ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            for path, data in assets.items()
            if path.parent == ROOT / "schemas"
        }
        declared = {name: digest for name, _, digest in SCHEMA_INVENTORY}
        changed = sorted(
            name
            for name in generated.keys() | declared.keys()
            if generated.get(name) != declared.get(name)
        )
        if changed:
            parser.exit(1, "Schema inventory differs: " + ", ".join(changed) + "\n")
    print("Checked" if args.check else "Generated", len(assets), "synthetic fixtures/schemas")


if __name__ == "__main__":
    main()
