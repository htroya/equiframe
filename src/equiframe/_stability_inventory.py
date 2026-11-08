"""Explicit reviewed inventory. New public surfaces require an explicit classification."""

STABLE_DATASETS_API = (
    "DatasetChoiceRequired",
    "DatasetColumn",
    "DatasetFormat",
    "DatasetInfo",
    "DatasetProvenance",
    "DatasetReadError",
    "DatasetReadOptions",
    "DatasetResult",
    "DatasetSource",
    "DatasetTarget",
    "convert_dataset",
    "inspect_dataset",
    "load_dataset",
)

STABLE_CAPTURE_API = (
    "DuckDBCaptureOptions",
    "capture_duckdb",
)

STABLE_MIGRATION_API = (
    "Aggregate",
    "Arithmetic",
    "Boolean",
    "Cast",
    "CastColumn",
    "Coalesce",
    "Column",
    "Compare",
    "CompilationCheck",
    "CompilationDiagnostic",
    "CompiledPlan",
    "CompilerRecord",
    "CompilerRegistry",
    "Concatenate",
    "Conditional",
    "DecimalRound",
    "Deduplicate",
    "EquiJoin",
    "EvidenceFile",
    "Filter",
    "IRColumn",
    "IsNaN",
    "IsNull",
    "JoinKey",
    "LiteralExpression",
    "LocalizeTimestamp",
    "Measure",
    "MigrationOptions",
    "MigrationRequest",
    "MigrationResult",
    "MigrationSpec",
    "MigrationStage",
    "NamedExpression",
    "NodeSchema",
    "Not",
    "PlanCompiler",
    "PipelineInput",
    "PipelineResult",
    "PipelineSpec",
    "Project",
    "RelationalPlan",
    "Scan",
    "Sort",
    "SortKey",
    "StageRecord",
    "ValidatedIR",
    "Window",
    "WindowMeasure",
    "check_migration",
    "ir_fingerprint",
    "migrate",
    "migration_summary",
    "native_compiler_registry",
    "read_migration",
    "render_migration_report",
    "validate_ir",
)

STABLE_DETECTION_API = (
    "ComponentDecision",
    "ComponentDetectionResult",
    "DetectionResult",
    "DetectorBundle",
    "DetectorCalibration",
    "DetectorDecision",
    "DetectorFit",
    "DetectorModel",
    "DetectorScoreResult",
    "DetectorScores",
    "DetectorSupport",
    "DetectorVersions",
    "FeatureFit",
    "FeatureMatrix",
    "FeatureObservation",
    "FeatureState",
    "FeatureSupport",
    "HybridDecision",
    "IsolationForestConfig",
    "NormalCalibrationProfiles",
    "NormalTrainingProfiles",
    "PreprocessorBundle",
    "ProfileFeature",
    "ProfileMetadata",
    "ProfileMetric",
    "ProfileOptions",
    "ProfileResult",
    "ProfileSpec",
    "ProfileVector",
    "calibrate_detectors",
    "combine_decisions",
    "detect",
    "detect_component",
    "detector_fingerprint",
    "fit_detectors",
    "fit_preprocessor",
    "profile_execution",
    "profile_spec_fingerprint",
    "read_detector_bundle",
    "read_preprocessor",
    "read_profile",
    "score_detectors",
    "transform_profiles",
    "write_detector_bundle",
    "write_preprocessor",
)

STABLE_R_REVIEW_API = (
    "RExecutionBinding",
    "RReviewBinding",
    "RReviewOptions",
    "RReviewResult",
    "ReviewedDecision",
    "finalize_execution_with_r",
    "finalize_with_r",
    "review_with_r",
)

STABLE_FEATURE_SCOPES = (
    ("datasets", STABLE_DATASETS_API),
    ("capture", STABLE_CAPTURE_API),
    ("migration", STABLE_MIGRATION_API),
    ("detection", STABLE_DETECTION_API),
    ("r_review", STABLE_R_REVIEW_API),
)

STABLE_API = (
    "AdapterCapability",
    "AggregateCheck",
    "AppliedPolicy",
    "ArrowInput",
    "ArtifactIOError",
    "ArtifactInput",
    "ArtifactIntegrityError",
    "ArtifactRef",
    "ArtifactStore",
    "BooleanType",
    "BooleanValue",
    "BundleReference",
    "CANONICALIZATION",
    "CancellationToken",
    "CapabilityError",
    "CapabilityStage",
    "CardinalityCheck",
    "CheckResult",
    "CheckState",
    "ColumnKeyScope",
    "ColumnSpec",
    "ComparisonCounts",
    "ComparisonDiagnostic",
    "ComparisonDifference",
    "ComparisonInput",
    "ComparisonOptions",
    "ComparisonPolicy",
    "ComparisonReport",
    "ComparisonResult",
    "ComparisonSource",
    "ComparisonSpec",
    "ComparisonState",
    "ComparisonValue",
    "CompatibilityPolicy",
    "Contract",
    "ContractIOError",
    "ContractParseError",
    "ContractValidationError",
    "DataSource",
    "DatePolicy",
    "DateType",
    "DateValue",
    "DecimalType",
    "DecimalValue",
    "DecisionState",
    "DiffCaptureOptions",
    "DiffContract",
    "DiffInput",
    "DuckDBAdapter",
    "DuckDBTransformation",
    "EngineAdapter",
    "EngineCapabilities",
    "EquiFrameError",
    "EquivalenceAssertionError",
    "EquivalenceDecision",
    "EquivalenceDifferentError",
    "EquivalenceEvidenceError",
    "EquivalenceGuaranteeError",
    "EquivalenceInputError",
    "EquivalenceNotEvaluableError",
    "EquivalencePolicy",
    "EvidenceBundle",
    "EvidenceEvent",
    "ExactDecimal",
    "ExecutionCancelled",
    "ExecutionOptions",
    "ExecutionPlan",
    "ExecutionProblem",
    "ExecutionResult",
    "ExecutionState",
    "ExecutionTimeout",
    "ExpectedProvenance",
    "Family",
    "FitState",
    "FloatType",
    "FloatValue",
    "GlobalKeyScope",
    "IgnoredOrder",
    "IndependentReviewEvidence",
    "InfinityValue",
    "IntegerType",
    "IntegerValue",
    "InvalidExecutionInput",
    "JobState",
    "JoinCheck",
    "KeyCheck",
    "KeyScope",
    "KeySpec",
    "LoadedTable",
    "LocalArtifactStore",
    "LocalDataSource",
    "LogicalType",
    "MissingDependencyError",
    "Multiplicity",
    "NaNPolicy",
    "NaNValue",
    "NativeEngineError",
    "NullPolicy",
    "NullValue",
    "NumericPolicy",
    "OracleState",
    "OrderCheck",
    "OrderPolicy",
    "PandasAdapter",
    "PandasInput",
    "PandasTransformation",
    "Parameter",
    "PhysicalColumn",
    "PolarsAdapter",
    "PolarsInput",
    "PolarsTransformation",
    "PolicyProvenance",
    "PreconditionSpec",
    "ReportCount",
    "ReportEvidenceManifest",
    "ReportOptions",
    "ReportPolicy",
    "ReportPublicationManifest",
    "ReportValue",
    "ReportViewPolicy",
    "ReportWitness",
    "ResourceLimitError",
    "RuleContext",
    "RuleCoverage",
    "RuleDefinition",
    "RuleEvaluation",
    "RuleFinding",
    "RuleImplementation",
    "RuleOptions",
    "RuleRegistry",
    "RuleSpec",
    "RunContext",
    "SCHEMA_VERSION",
    "ScalarValue",
    "SchemaCheck",
    "SchemaRef",
    "SchemaVersionError",
    "Sha256",
    "SignificantOrder",
    "SortSpec",
    "StabilityRecord",
    "StageTiming",
    "StringType",
    "StringValue",
    "TableArtifact",
    "TableKeyScope",
    "TableSchema",
    "TableSpec",
    "TemporalPolicy",
    "TimeUnit",
    "TimeZone",
    "TimestampPolicy",
    "TimestampType",
    "TimestampValue",
    "Tolerance",
    "Transformation",
    "TransformationRegistry",
    "ValidationIssue",
    "VerificationBinding",
    "VerificationCheck",
    "VerificationCoverage",
    "VerificationInput",
    "VerificationRequest",
    "VerificationResult",
    "VerificationReview",
    "VerificationState",
    "VersionInfo",
    "__version__",
    "assert_equivalent",
    "bag_contract",
    "canonical_contract_bytes",
    "compare",
    "comparison_fingerprint",
    "comparison_report",
    "contract_fingerprint",
    "contract_json_schema",
    "default_rule_registry",
    "diff",
    "equivalence_decision",
    "evaluate_rules",
    "execute",
    "export_bundle",
    "get_adapter_capabilities",
    "get_compatibility_policy",
    "get_stability_register",
    "import_bundle",
    "infer_diff_contract",
    "inspect_bundle",
    "iter_differences",
    "iter_rule_findings",
    "keyed_contract",
    "read_bundle",
    "read_comparison",
    "read_comparison_report",
    "read_contract",
    "read_diff_contract",
    "read_rule_evaluation",
    "read_table",
    "read_verification",
    "render_comparison_html",
    "render_comparison_notebook",
    "render_comparison_text",
    "rule_set_fingerprint",
    "sequence_contract",
    "validate_contract",
    "verification_summary",
    "verify",
    "verify_events",
    "verify_migration",
    "write_comparison_report",
    "write_contract",
    *STABLE_DATASETS_API,
    *STABLE_CAPTURE_API,
    *STABLE_MIGRATION_API,
    *STABLE_DETECTION_API,
    *STABLE_R_REVIEW_API,
)

EXPERIMENTAL_API = (
    "CompositeDataSource",
    "RecordBatchInput",
    "SQLiteInput",
    "StreamInput",
    "SnapshotClient",
    "SnapshotColumn",
    "SnapshotDataSource",
    "SnapshotManifest",
    "SnapshotTable",
    "snapshot_fingerprint",
    "ConversionReceipt",
    "Destination",
    "FieldMapping",
    "FileInput",
    "IngestionConversionReceipt",
    "IngestionResult",
    "IngestionSpec",
    "LoadReceipt",
    "ParquetDestination",
    "PipelineRequest",
    "PublishedTable",
    "QuarantinedRecord",
    "ReducedTable",
    "ReductionObservation",
    "ReductionOptions",
    "ReductionResult",
    "SourceReceipt",
    "WorkflowCheckpoint",
    "WorkflowExpected",
    "WorkflowInputBinding",
    "WorkflowRequest",
    "WorkflowResult",
    "WorkflowSpec",
    "WorkflowStage",
    "ingest_file",
    "inspect_evidence",
    "pipeline_summary",
    "read_pipeline",
    "read_reduction",
    "read_workflow",
    "reduce_case",
    "render_report",
    "run_pipeline",
    "run_workflow",
    "write_report",
)

# Every shipped core schema, including experimental producer formats.
# Tuple: file name, classification, canonical schema SHA-256.
SCHEMA_INVENTORY = (
    (
        "artifact-ref-1.0.schema.json",
        "stable",
        "a07bfab18772f05d5eb78a9a2ea5967808320d306b162553a7ea93c96e6a7b70",
    ),
    (
        "comparison-difference-1.0.schema.json",
        "stable",
        "efd5fa548b99ea6bf78530a8ce88c313d85af51576ed603ccd4f4572d3643801",
    ),
    (
        "comparison-options-1.0.schema.json",
        "stable",
        "3b71a66755842f9d1a6485f9782f3b2c05a8d5078bd3a314c06f14bc262a2e3f",
    ),
    (
        "comparison-report-1.0.schema.json",
        "stable",
        "df2a15514915af4f8f24f6481ea984bd43fbab6801c8892eeae1f4c7a9d2f2a7",
    ),
    (
        "comparison-result-1.0.schema.json",
        "stable",
        "a52e69258dbef0011b7321ef8a674d979891b7eb283471b2f7f1e29207ba3fba",
    ),
    (
        "comparison-spec-1.0.schema.json",
        "stable",
        "6d3ffdbb73d04cb52414684364fb7a5c1d0a467d5306c1e88f4f229fbd0e97e4",
    ),
    (
        "component-detection-result-1.0.schema.json",
        "stable",
        "3b34398f8cabc5e6b9a691f57b8e9a7c9a1e4997efe6efca389c5ce2810fe231",
    ),
    (
        "contract-1.0.schema.json",
        "stable",
        "faebdcc7adcb20b6f5b89eb2b355dbb7c110cd38d101e60a162c510c0bdcc24e",
    ),
    (
        "detection-result-1.0.schema.json",
        "stable",
        "dabd0f1de4a7437b89572330096c38375e081618f032e3d9cdde05fa45a56b87",
    ),
    (
        "detector-bundle-1.0.schema.json",
        "stable",
        "adea73af8d4ca17c1a0e40c82ea40d3c9ce7ac841bd7d2b001f5eb94d529d720",
    ),
    (
        "detector-fit-1.0.schema.json",
        "stable",
        "3e5a0cacede941489b5e2121f387dad8233e61fb75cbfba16921551842f3fca8",
    ),
    (
        "detector-score-result-1.0.schema.json",
        "stable",
        "d2ba844388cabad55c1cf29428e86611b69b66572dc7f47d3eab2584eec83cf1",
    ),
    (
        "diff-capture-options-1.0.schema.json",
        "stable",
        "5d0fb5dd3c9017edc6d47510c8956a067ac72565b62a9f9beec7f78da25823d5",
    ),
    (
        "diff-contract-1.0.schema.json",
        "stable",
        "1607b342fe4c928632d31526290275451ad4d97d9a992060ff3b39c9542f84b3",
    ),
    (
        "eda-config-1.0.schema.json",
        "experimental",
        "65ea2de1dd1d43bd0f1bb8942dd5b28ff7a95f346c24edc01418ec5a04083fe1",
    ),
    (
        "eda-manifest-1.0.schema.json",
        "experimental",
        "f9d3b6ccb63249f7bd796f8154135a04c844578231666a988e400c857d0b3e2d",
    ),
    (
        "eda-result-1.0.schema.json",
        "experimental",
        "5bce9ab1457ab99b5ed818ecaac7695caef205c12eff29dd0fe6507e8c8a0cad",
    ),
    (
        "eda-source-1.0.schema.json",
        "experimental",
        "182d1cc45e149e0251acdae721dd78b4f73721d69cd52f630140c805b96265fb",
    ),
    (
        "equivalence-decision-1.0.schema.json",
        "stable",
        "ca095206e8439a2699d81dd81c3d9ee25876de11d44214db93aa2222e987802e",
    ),
    (
        "equivalence-policy-1.0.schema.json",
        "stable",
        "5533bdeb44f34f1aa93847865a09aa8c187f12284e93f057fe05044cc1f70dac",
    ),
    (
        "evidence-bundle-1.0.schema.json",
        "stable",
        "3261937386cceafa7fb5850554b50891d7133a3365c168b01bf3f3f6e4c54e9c",
    ),
    (
        "evidence-event-1.0.schema.json",
        "stable",
        "bf436cc9e1c29b4d1376a184830494d59cacd0e74f48153ee3b18d1b47389fcc",
    ),
    (
        "execution-plan-1.0.schema.json",
        "stable",
        "522eba37e95ed9b0b149a380620d5180830185fbdb98a3b04093e82fd3715316",
    ),
    (
        "execution-result-1.0.schema.json",
        "stable",
        "32f65fb045bbccb6671bce8108c4082a55065ec7c2400b80e45f6bd3e0b79e5f",
    ),
    (
        "expected-provenance-1.0.schema.json",
        "stable",
        "69f12205af11fa159dfb862b7b6d2480482515515eb89b586f85f0c8477217d7",
    ),
    (
        "feature-matrix-1.0.schema.json",
        "stable",
        "d4021f00e8eea912bd7f77bd408c174b2b725d2c892b555163cf68d1b775520d",
    ),
    (
        "hybrid-decision-1.0.schema.json",
        "stable",
        "94b65efb9988bf9a922f0e35b082eef38e667e7b4292fe97badd3662e554b429",
    ),
    (
        "independent-review-evidence-1.0.schema.json",
        "stable",
        "b5ac2c988b44ce2d743750300f9f3f218f9c1d14c9880aba5d58e59133d728c7",
    ),
    (
        "ingestion-result-1.0.schema.json",
        "experimental",
        "89b76c25848f12c0a861bf8997ecaad56816f3e955b0ae80a0467b4c2a7daae7",
    ),
    (
        "ingestion-spec-1.0.schema.json",
        "experimental",
        "7e536091fdb920ce87b8ff106ad43cfd3e434bc2154b4966e49c40902584fdbf",
    ),
    (
        "load-receipt-1.0.schema.json",
        "experimental",
        "f73434f6a3113006e7c4661a536f2a1ffbe19c24dfba7a09d98dc9c8a02e470e",
    ),
    (
        "migration-options-1.0.schema.json",
        "stable",
        "7469d5d6dc2af4f5ceffce37ffe1263e6d1360bfc959530ab42244abcab33bfa",
    ),
    (
        "migration-request-1.0.schema.json",
        "stable",
        "fe42af3c7eff94ab06ec3b358ffbe3049715656690f9cf44f10c51a11d42d1fb",
    ),
    (
        "migration-result-1.0.schema.json",
        "stable",
        "e8fab4f562f45cdd52b6d3d07fea6315cb3c332b1fde301a352efdaa9b269fa3",
    ),
    (
        "migration-spec-1.0.schema.json",
        "stable",
        "537797da0c99c27c441fa70931bbfc12bcb24d672da52ebac9fa48105d32fc28",
    ),
    (
        "normal-calibration-profiles-1.0.schema.json",
        "stable",
        "b00f3a5d32bc802b73a2ec4bda83737df4d7f3c81c23b85babcceaecbd55210e",
    ),
    (
        "normal-training-profiles-1.0.schema.json",
        "stable",
        "532661b6dd668f5aade9e3ba463898ac49ca7bbd8c1c8ae30de269b9bfe52bf4",
    ),
    (
        "pipeline-request-1.0.schema.json",
        "experimental",
        "b6b489bcfca89397c8173d5e25766ffe5b36b3b5fd840ff554edec999e385b32",
    ),
    (
        "pipeline-result-1.0.schema.json",
        "stable",
        "81f8b621857e700a1f8b07c28fc708ba6581a559c9a852fe82efea2dc1324267",
    ),
    (
        "pipeline-spec-1.0.schema.json",
        "stable",
        "153e88c89867a6ab890b3af1648e6f8a063a8d86dbcaa9c7844e23dfac434633",
    ),
    (
        "preprocessor-bundle-1.0.schema.json",
        "stable",
        "6af7f07c9ee4478fcf030ece1de07ae988ee8e9e2cf4a1bb36083668e11646a0",
    ),
    (
        "profile-result-1.0.schema.json",
        "stable",
        "5c95b094421f9efe4ac367e4729ea9ce5d5a440a4fffdda5c8ec429c02678544",
    ),
    (
        "profile-spec-1.0.schema.json",
        "stable",
        "77c5af8f8a222edd515131392f2d684fc7db6aabd010de8b90d229d5051c6c49",
    ),
    (
        "r-execution-binding-1.0.schema.json",
        "stable",
        "46d7b30a2ebe8a7eeff8e3f484b04b5e509412c638d1e0467eaad86adce4401d",
    ),
    (
        "r-review-binding-1.0.schema.json",
        "stable",
        "b246dab63a6b38a03fb65f6c646ab895940f8c5b6d4d88ea55a75a3442ac2f45",
    ),
    (
        "r-review-options-1.0.schema.json",
        "stable",
        "e58898a62bfd4e521b5f449b0759791469d918b78e95ab08cba6a765f0070c02",
    ),
    (
        "r-review-result-1.0.schema.json",
        "stable",
        "fe90eef205d50fb00da1de0b4643430da52570fd262599234d5373a68c338848",
    ),
    (
        "reduction-observation-1.0.schema.json",
        "experimental",
        "f75c4e7c00a6e4c05c6c951da70b7f0478ad22c0a228f5f30cb3288a1c7719e6",
    ),
    (
        "reduction-options-1.0.schema.json",
        "experimental",
        "5dddd2b04008a2688553aa5fcd96220bc96cd2b368fb79302599021b8542a2fd",
    ),
    (
        "reduction-result-1.0.schema.json",
        "experimental",
        "d9dca890c370228f3765bbb959ca7616824be23eef01a9edaf37bbb4cee0a43c",
    ),
    (
        "relational-plan-1.0.schema.json",
        "stable",
        "3746a0d31fa221fd94b0fe8dfcd4ac53b74797993d95365493c47f7b5d1c1bca",
    ),
    (
        "report-evidence-manifest-1.0.schema.json",
        "stable",
        "7ad21c1530bcf585020d692c1b675fed84f3569c92fd1f572c9f873fbec96734",
    ),
    (
        "report-options-1.0.schema.json",
        "stable",
        "505c5bbc2bc5d5ad067fceec2902f19a3b2149180ff87016e4daf5b1b6550160",
    ),
    (
        "report-publication-manifest-1.0.schema.json",
        "stable",
        "deda976bd5a29430e58139730abc389ce28e5f458877918f9f62d59dd51652e3",
    ),
    (
        "reviewed-decision-1.0.schema.json",
        "stable",
        "5f4402ffe22318ec66b30f7d1060bfda63844d075148b2a8d8f3fbf1bc0b66e8",
    ),
    (
        "rule-check-result-1.0.schema.json",
        "stable",
        "d6bd5c828859fdb751f1c4c063047c3f49e0e3cab007458ee4a637059606cc64",
    ),
    (
        "rule-evaluation-1.0.schema.json",
        "stable",
        "98f38f596cc9fa5e49ca17929fe26c4c016d3cd6e9d616ba955f52a8e6f77435",
    ),
    (
        "rule-finding-1.0.schema.json",
        "stable",
        "23aa44c8ceabae2a471862bdcf440673b69483ec018bdb80a513e1d736ae9c1b",
    ),
    (
        "rule-options-1.0.schema.json",
        "stable",
        "e6546b88c0848b160407eec63aaf8e6b6122ff8edc38b40fb4c98ae4cb049c7a",
    ),
    (
        "snapshot-manifest-1.0.schema.json",
        "experimental",
        "ed83a8b275f5357b75731da1f34a30f98a61fa3342adcfcdc72adaf8f740778c",
    ),
    (
        "verification-request-1.0.schema.json",
        "stable",
        "eb0fa1998062944180db55db805c993340736923ceaba5bbb630d2595e047180",
    ),
    (
        "verification-result-1.0.schema.json",
        "stable",
        "65b5457c5feea88190016e843b780f2382edef7af1f3c8d100fb84de5f01d4b6",
    ),
    (
        "workflow-request-1.0.schema.json",
        "experimental",
        "0766059752d5973a52fd828dd72bb316c328576bff0ef4e3794a2d0f51f2a89c",
    ),
    (
        "workflow-result-1.0.schema.json",
        "experimental",
        "54c871a59c7b16a85e54db4101aa2a6171070f90b1bbdf9853290a7b46e22410",
    ),
    (
        "workflow-spec-1.0.schema.json",
        "experimental",
        "af3c0ab51b5c598d54a6fce43c4a4368e8dcc4efba4a254e96003a42a1575096",
    ),
)
# command, classification, CLI parameters, possible process exits (including parser errors).
CLI_INVENTORY = (
    (
        "dataset inspect",
        "stable",
        (
            "argument|source|source|required=True|default=None",
            "option|file_format|--format|required=False|default=None",
            "option|sheet|--sheet|required=False|default=None",
            "option|records_path|--records-path|required=False|default=None",
            "option|delimiter|--delimiter|required=False|default=None",
            "option|header|--header,--no-header|required=False|default=True",
            "option|encoding|--encoding|required=False|default=utf-8-sig",
        ),
        (0, 2, 3),
    ),
    (
        "dataset load",
        "stable",
        (
            "argument|source|source|required=True|default=None",
            "option|target|--target|required=False|default=None",
            "option|output|--output|required=False|default=None",
            "option|file_format|--format|required=False|default=None",
            "option|sheet|--sheet|required=False|default=None",
            "option|records_path|--records-path|required=False|default=None",
            "option|delimiter|--delimiter|required=False|default=None",
            "option|header|--header,--no-header|required=False|default=True",
            "option|text_mode|--text-mode|required=False|default=auto",
            "option|infer_types|--infer-types,--keep-text|required=False|default=True",
            "option|encoding|--encoding|required=False|default=utf-8-sig",
            "option|max_bytes|--max-bytes|required=False|default=134217728",
            "option|max_rows|--max-rows|required=False|default=1000000",
        ),
        (0, 2, 3),
    ),
    (
        "bundle export",
        "stable",
        (
            "argument|source|source|required=True|default=None",
            "argument|destination|destination|required=True|default=None",
        ),
        (0, 2, 3),
    ),
    (
        "bundle import",
        "stable",
        (
            "argument|source|source|required=True|default=None",
            "argument|destination|destination|required=True|default=None",
            "option|sha256|--sha256|required=False|default=None",
        ),
        (0, 2, 3),
    ),
    (
        "bundle verify",
        "stable",
        (
            "argument|directory|directory|required=True|default=None",
            "option|sha256|--sha256|required=False|default=None",
        ),
        (0, 2, 3),
    ),
    (
        "compare",
        "stable",
        (
            "argument|spec|spec|required=True|default=None",
            "argument|left|left|required=True|default=None",
            "argument|right|right|required=True|default=None",
            "option|expected|--expected,--no-expected|required=False|default=False",
            "option|output|--output|required=False|default=equiframe-runs",
        ),
        (0, 1, 2, 3),
    ),
    ("contract validate", "stable", ("argument|path|path|required=True|default=None",), (0, 2, 3)),
    (
        "doctor",
        "experimental",
        (
            "option|extra|--extra|required=False|default=Extra.base",
            "option|json_output|--json|required=False|default=False",
        ),
        (0, 2, 3),
    ),
    (
        "demo",
        "experimental",
        (
            "option|role|--role|required=True|default=None",
            "option|case|--case|required=False|default=Case.good",
            "option|output|--output|required=True|default=None",
        ),
        (0, 1, 2, 3),
    ),
    (
        "evidence verify",
        "experimental",
        ("argument|directory|directory|required=True|default=None",),
        (0, 2, 3),
    ),
    (
        "ingestion run",
        "experimental",
        (
            "argument|spec|spec|required=True|default=None",
            "argument|source|source|required=True|default=None",
            "option|output|--output|required=False|default=equiframe-runs",
        ),
        (0, 1, 2, 3),
    ),
    (
        "migration run",
        "stable",
        (
            "argument|request|request|required=True|default=None",
            "option|output|--output|required=False|default=equiframe-runs",
            "option|bundle|--bundle|required=False|default=None",
        ),
        (0, 1, 2, 3),
    ),
    (
        "migration validate",
        "stable",
        ("argument|spec|spec|required=True|default=None",),
        (0, 2, 3),
    ),
    (
        "migration verify",
        "stable",
        ("argument|directory|directory|required=True|default=None",),
        (0, 2, 3),
    ),
    (
        "reduce",
        "experimental",
        (
            "argument|request|request|required=True|default=None",
            "option|predicate|--predicate|required=True|default=None",
            "option|predicate_version|--predicate-version|required=True|default=None",
            "option|failure_signature|--failure-signature|required=True|default=None",
            "option|output|--output|required=False|default=equiframe-runs",
            "option|max_evaluations|--max-evaluations|required=False|default=100",
            "option|timeout_seconds|--timeout-seconds|required=False|default=60.0",
            "option|confirmations|--confirmations|required=False|default=2",
        ),
        (0, 2, 3),
    ),
    (
        "report",
        "experimental",
        (
            "argument|manifest|manifest|required=True|default=None",
            "option|output|--output|required=True|default=None",
        ),
        (0, 2, 3),
    ),
    (
        "run",
        "experimental",
        (
            "argument|request|request|required=True|default=None",
            "option|registry|--registry|required=True|default=None",
            "option|output|--output|required=False|default=equiframe-runs",
            "option|bundle|--bundle|required=False|default=None",
        ),
        (0, 1, 2, 3),
    ),
    (
        "verify inspect",
        "stable",
        ("argument|directory|directory|required=True|default=None",),
        (0, 2, 3),
    ),
    (
        "verify migration",
        "stable",
        (
            "argument|directory|directory|required=True|default=None",
            "option|output|--output|required=False|default=equiframe-runs",
        ),
        (0, 1, 2, 3),
    ),
    (
        "verify run",
        "stable",
        (
            "argument|request|request|required=True|default=None",
            "option|output|--output|required=False|default=equiframe-runs",
        ),
        (0, 1, 2, 3),
    ),
    (
        "verify validate",
        "stable",
        ("argument|request|request|required=True|default=None",),
        (0, 2, 3),
    ),
    (
        "workflow inspect",
        "experimental",
        ("argument|directory|directory|required=True|default=None",),
        (0, 2, 3),
    ),
    (
        "workflow run",
        "experimental",
        (
            "argument|request|request|required=True|default=None",
            "option|output|--output|required=False|default=equiframe-runs",
        ),
        (0, 1, 2, 3),
    ),
    (
        "workflow validate",
        "experimental",
        ("argument|request|request|required=True|default=None",),
        (0, 2, 3),
    ),
    (
        "eda run",
        "experimental",
        (
            "argument|source|source|required=True|default=None",
            "option|output|--output|required=True|default=None",
            "option|config|--config|required=False|default=None",
            "option|format|--format|required=False|default=parquet",
            "option|snapshot_id|--snapshot-id|required=False|default=local",
            "option|expected_sha256|--expected-sha256|required=False|default=None",
            "option|manifest|--manifest|required=False|default=None",
            "option|manifest_sha256|--manifest-sha256|required=False|default=None",
        ),
        (0, 2, 3),
    ),
    (
        "eda migration",
        "experimental",
        (
            "argument|path|path|required=True|default=None",
            "option|output|--output|required=True|default=None",
            "option|side|--side|required=False|default=source",
            "option|config|--config|required=False|default=None",
        ),
        (0, 2, 3),
    ),
    ("eda inspect", "experimental", ("argument|path|path|required=True|default=None",), (0, 3)),
)

# Exact stable function signatures and stable model shapes; review changes explicitly.
API_SIGNATURES = {
    "calibrate_detectors": (
        "(fit: equiframe.detector_types.DetectorFit, calibration: equiframe.det"
        "ector_types.NormalCalibrationProfiles, *, alpha: str) -> equiframe.det"
        "ector_types.DetectorBundle"
    ),
    "capture_duckdb": (
        "(sql: 'str', *, work_dir: 'Path', name: 'str' = 'result', connection: "
        "'duckdb.DuckDBPyConnection | None' = None, exclusive_connection: 'bool"
        "' = False, parameters: 'Mapping[str, object] | None' = None, options: "
        "'DuckDBCaptureOptions | None' = None, cancellation: 'CancellationToken"
        " | None' = None) -> 'TableArtifact'"
    ),
    "check_migration": (
        "(spec: 'MigrationSpec', *, compilers: 'CompilerRegistry | None' = None"
        ") -> 'tuple[CompilationCheck, CompilationCheck]'"
    ),
    "combine_decisions": (
        "(r: equiframe.detector_types.ComponentDecision | equiframe.rule_types."
        "RuleEvaluation, m: equiframe.detector_types.ComponentDecision) -> equi"
        "frame.detector_types.HybridDecision"
    ),
    "convert_dataset": "(dataset: 'DatasetResult', *, target: 'DatasetTarget') -> 'DatasetResult'",
    "detect": (
        "(bundle: equiframe.detector_types.DetectorBundle, profiles: tuple[equi"
        "frame.profile_types.ProfileVector, ...]) -> equiframe.detector_types.D"
        "etectionResult"
    ),
    "detect_component": (
        "(bundle: equiframe.detector_types.DetectorBundle, profiles: tuple[equi"
        "frame.profile_types.ProfileVector, ...], *, method: Literal['isolation"
        "_forest', 'mad']) -> equiframe.detector_types.ComponentDetectionResult"
    ),
    "detector_fingerprint": (
        "(value: equiframe.detector_types.DetectorFit | equiframe.detector_type"
        "s.DetectorBundle) -> str"
    ),
    "finalize_execution_with_r": (
        "(execution: 'ExecutionResult', rules: 'RuleEvaluation', profile: 'Prof"
        "ileResult', detection: 'ComponentDetectionResult', *, comparison: 'Com"
        "parisonResult', options: 'RReviewOptions | None' = None, cancellation:"
        " 'CancellationToken | None' = None) -> 'ReviewedDecision'"
    ),
    "finalize_with_r": (
        "(rules: 'ComponentDecision | RuleEvaluation', model: 'ComponentDecisio"
        "n', *, left: 'object', right: 'object', contract: 'Contract | DiffCont"
        "ract | ComparisonSpec', comparison: 'ComparisonResult | None' = None, "
        "options: 'RReviewOptions | None' = None, cancellation: 'CancellationTo"
        "ken | None' = None) -> 'ReviewedDecision'"
    ),
    "fit_detectors": (
        "(training: equiframe.profile_types.NormalTrainingProfiles, *, spec: eq"
        "uiframe.profile_types.ProfileSpec, config: equiframe.detector_types.Is"
        "olationForestConfig, support: equiframe.detector_types.DetectorSupport"
        ", empty_policy: Literal['drop', 'not_estimable'] = 'drop') -> equifram"
        "e.detector_types.DetectorFit"
    ),
    "fit_preprocessor": (
        "(training: equiframe.profile_types.NormalTrainingProfiles, *, spec: eq"
        "uiframe.profile_types.ProfileSpec, empty_policy: Literal['drop', 'not_"
        "estimable'] = 'drop') -> equiframe.profile_types.PreprocessorBundle"
    ),
    "inspect_dataset": (
        "(source: 'str | Path', *, options: 'DatasetReadOptions | None' = None) -> 'DatasetInfo'"
    ),
    "ir_fingerprint": "(plan: 'RelationalPlan') -> 'str'",
    "load_dataset": (
        "(source: 'str | Path', *, target: 'DatasetTarget' = 'pandas', options:"
        " 'DatasetReadOptions | None' = None) -> 'DatasetResult'"
    ),
    "migrate": (
        "(spec: 'MigrationSpec', *, source: 'DataSource', work_dir: 'Path | Non"
        "e' = None, expected: 'ExpectedInput | None' = None, compilers: 'Compil"
        "erRegistry | None' = None, adapters: 'Mapping[str, EngineAdapter] | No"
        "ne' = None, rule_registry: 'RuleRegistry | None' = None, detector_bund"
        "le: 'DetectorBundle | None' = None, cancellation: 'CancellationToken |"
        " None' = None) -> 'MigrationResult'"
    ),
    "migration_summary": "(result: 'MigrationResult') -> 'dict[str, object]'",
    "native_compiler_registry": "() -> 'CompilerRegistry'",
    "profile_execution": (
        "(execution: 'ExecutionResult', *, spec: 'ProfileSpec', options: 'Profi"
        "leOptions | None' = None, work_dir: 'Path | None' = None, cancellation"
        ": 'CancellationToken | None' = None, conversions: 'tuple[ConversionRec"
        "eipt, ...]' = ()) -> 'ProfileResult'"
    ),
    "profile_spec_fingerprint": "(spec: equiframe.profile_types.ProfileSpec) -> str",
    "read_detector_bundle": (
        "(path: pathlib.Path, *, expected_sha256: str | None = None) -> equifra"
        "me.detector_types.DetectorBundle"
    ),
    "read_migration": "(path: 'Path', *, verify: 'bool' = True) -> 'MigrationResult'",
    "read_preprocessor": "(path: pathlib.Path) -> equiframe.profile_types.PreprocessorBundle",
    "read_profile": "(path: 'Path') -> 'ProfileResult'",
    "render_migration_report": "(result: 'MigrationResult') -> 'str'",
    "review_with_r": (
        "(left: 'object', right: 'object', *, contract: 'Contract | DiffContrac"
        "t | ComparisonSpec', comparison: 'ComparisonResult | None' = None, opt"
        "ions: 'RReviewOptions | None' = None, cancellation: 'CancellationToken"
        " | None' = None) -> 'RReviewResult'"
    ),
    "score_detectors": (
        "(fit: equiframe.detector_types.DetectorFit, profiles: tuple[equiframe."
        "profile_types.ProfileVector, ...]) -> equiframe.detector_types.Detecto"
        "rScoreResult"
    ),
    "transform_profiles": (
        "(bundle: equiframe.profile_types.PreprocessorBundle, profiles: tuple[e"
        "quiframe.profile_types.ProfileVector, ...]) -> equiframe.profile_types"
        ".FeatureMatrix"
    ),
    "validate_ir": "(plan: 'RelationalPlan', contract: 'Contract') -> 'ValidatedIR'",
    "write_detector_bundle": (
        "(bundle: equiframe.detector_types.DetectorBundle, path: pathlib.Path) -> str"
    ),
    "write_preprocessor": (
        "(bundle: equiframe.profile_types.PreprocessorBundle, path: pathlib.Path) -> None"
    ),
    "assert_equivalent": (
        "(result: 'ComparisonResult', *, policy: 'EquivalencePolicy | None' = Non"
        "e, evidence_root: 'Path | None' = None, report_path: 'Path | None' = Non"
        "e) -> 'None'"
    ),
    "bag_contract": (
        "(columns: 'Sequence[ColumnSpec]', *, policy: 'ComparisonPolicy | None' ="
        " None, multiplicity: 'Multiplicity' = 'preserve', reference: 'Reference'"
        " = 'expected', contract_id: 'str' = 'diff', revision: 'int' = 1) -> 'Dif"
        "fContract'"
    ),
    "canonical_contract_bytes": ("(contract: equiframe.contracts.Contract) -> bytes"),
    "compare": (
        "(left: 'ComparisonInput', right: 'ComparisonInput', *, contract: 'Contra"
        "ct', policy: 'ComparisonPolicy | None' = None, options: 'ComparisonOptio"
        "ns | None' = None, reference: \"Literal['peer', 'expected']\" = 'peer', wo"
        "rk_dir: 'Path | None' = None, cancellation: 'CancellationToken | None' ="
        " None) -> 'ComparisonResult'"
    ),
    "comparison_fingerprint": ("(spec: 'ComparisonSpec') -> 'str'"),
    "comparison_report": (
        "(result: 'ComparisonResult', *, options: 'ReportOptions | None' = None, "
        "evidence_root: 'Path | None' = None, declaration: 'DiffContract | None' "
        "= None) -> 'ComparisonReport'"
    ),
    "contract_fingerprint": ("(contract: equiframe.contracts.Contract) -> str"),
    "contract_json_schema": ("() -> dict[str, object]"),
    "default_rule_registry": ("() -> 'RuleRegistry'"),
    "diff": (
        "(candidate: 'DiffInput', expected: 'DiffInput', *, contract: 'Contract |"
        " DiffContract | None' = None, keys: 'Sequence[str] | None' = None, polic"
        "y: 'ComparisonPolicy | None' = None, reference: \"Literal['peer', 'expect"
        "ed'] | None\" = None, options: 'ComparisonOptions | None' = None, capture"
        "_options: 'DiffCaptureOptions | None' = None, work_dir: 'Path | None' = "
        "None, cancellation: 'CancellationToken | None' = None) -> 'ComparisonRes"
        "ult'"
    ),
    "equivalence_decision": (
        "(result: 'ComparisonResult', *, policy: 'EquivalencePolicy | None' = Non"
        "e, evidence_root: 'Path | None' = None) -> 'EquivalenceDecision'"
    ),
    "evaluate_rules": (
        "(execution: 'ExecutionResult', *, registry: 'RuleRegistry | None' = None"
        ", options: 'RuleOptions | None' = None, work_dir: 'Path | None' = None, "
        "cancellation: 'CancellationToken | None' = None) -> 'RuleEvaluation'"
    ),
    "execute": (
        "(plan: 'ExecutionPlan', *, source: 'DataSource', registry: 'Transformati"
        "onRegistry', adapter: 'EngineAdapter | None' = None, artifact_store: 'Ar"
        "tifactStore | None' = None, work_dir: 'Path | None' = None, cancellation"
        ": 'CancellationToken | None' = None) -> 'ExecutionResult'"
    ),
    "export_bundle": ("(source: 'Path', destination: 'Path') -> 'EvidenceBundle'"),
    "get_adapter_capabilities": ("() -> 'tuple[AdapterCapability, ...]'"),
    "get_compatibility_policy": ("() -> 'CompatibilityPolicy'"),
    "get_stability_register": ("() -> 'tuple[StabilityRecord, ...]'"),
    "import_bundle": (
        "(source: 'Path', destination: 'Path', *, expected_sha256: 'str | None' ="
        " None) -> 'EvidenceBundle'"
    ),
    "infer_diff_contract": (
        "(reference_schema: 'pa.Schema', *, keys: 'Sequence[str] | None' = None, "
        "column_overrides: 'Sequence[ColumnSpec]' = (), policy: 'ComparisonPolicy"
        " | None' = None, reference: 'Reference' = 'expected') -> 'DiffContract'"
    ),
    "inspect_bundle": (
        "(path: 'Path', *, expected_sha256: 'str | None' = None) -> 'dict[str, object]'"
    ),
    "iter_differences": ("(ref: 'ArtifactRef') -> 'Iterator[ComparisonDifference]'"),
    "iter_rule_findings": ("(ref: 'ArtifactRef') -> 'Iterator[RuleFinding]'"),
    "keyed_contract": (
        "(columns: 'Sequence[ColumnSpec]', *, keys: 'Sequence[str]', incomplete: "
        "'Incomplete' = 'reject', policy: 'ComparisonPolicy | None' = None, multi"
        "plicity: 'Multiplicity' = 'preserve', reference: 'Reference' = 'expected"
        "', contract_id: 'str' = 'diff', revision: 'int' = 1) -> 'DiffContract'"
    ),
    "read_bundle": ("(path: 'Path', *, expected_sha256: 'str | None' = None) -> 'EvidenceBundle'"),
    "read_comparison": ("(path: 'Path') -> 'ComparisonResult'"),
    "read_comparison_report": (
        "(path: 'Path', *, max_bytes: 'int' = 2097152) -> 'ComparisonReport'"
    ),
    "read_contract": ("(path: str | pathlib.Path) -> equiframe.contracts.Contract"),
    "read_diff_contract": ("(result: 'ComparisonResult') -> 'DiffContract'"),
    "read_rule_evaluation": ("(path: 'Path') -> 'RuleEvaluation'"),
    "read_table": ("(ref: 'ArtifactRef') -> 'pa.Table'"),
    "read_verification": ("(path: 'Path') -> 'VerificationResult'"),
    "render_comparison_html": ("(report: equiframe.report_types.ComparisonReport) -> str"),
    "render_comparison_notebook": ("(report: equiframe.report_types.ComparisonReport) -> str"),
    "render_comparison_text": ("(report: equiframe.report_types.ComparisonReport) -> str"),
    "rule_set_fingerprint": (
        "(contract: 'Contract', registry: 'RuleRegistry', options: 'RuleOptions') -> 'str'"
    ),
    "sequence_contract": (
        "(columns: 'Sequence[ColumnSpec]', *, by: 'Sequence[SortSpec]', ties: 'Ti"
        "es' = 'preserve', policy: 'ComparisonPolicy | None' = None, multiplicity"
        ": 'Multiplicity' = 'preserve', reference: 'Reference' = 'expected', cont"
        "ract_id: 'str' = 'diff', revision: 'int' = 1) -> 'DiffContract'"
    ),
    "validate_contract": (
        "(document: str | bytes | collections.abc.Mapping[str, object]) -> equifr"
        "ame.contracts.Contract"
    ),
    "verification_summary": ("(result: 'VerificationResult') -> 'dict[str, object]'"),
    "verify": (
        "(outputs: 'Mapping[str, VerificationInput]', *, contract: 'Contract', ex"
        "pected: 'ArtifactRef | ExecutionResult | None' = None, provenance: 'Expe"
        "ctedProvenance | None' = None, reviews: 'tuple[IndependentReviewEvidence"
        ", ...]' = (), request_review: 'bool' = False, require_expected: 'bool' ="
        " False, require_rules: 'bool' = False, snapshots: 'Mapping[str, Artifact"
        "Ref] | None' = None, plan_sha256: 'str | None' = None, policy: 'Comparis"
        "onPolicy | None' = None, options: 'ComparisonOptions | None' = None, wor"
        "k_dir: 'Path | None' = None) -> 'VerificationResult'"
    ),
    "verify_events": (
        "(path: pathlib.Path, *, operation_id: str) -> tuple[equiframe.evidence.EvidenceEvent, ...]"
    ),
    "verify_migration": (
        "(path: 'Path', *, work_dir: 'Path | None' = None, provenance: 'ExpectedP"
        "rovenance | None' = None, reviews: 'tuple[IndependentReviewEvidence, ..."
        "]' = (), request_review: 'bool' = False) -> 'VerificationResult'"
    ),
    "write_comparison_report": (
        "(result: 'ComparisonResult', directory: 'Path', *, options: 'ReportOptio"
        "ns | None' = None, evidence_root: 'Path | None' = None, declaration: 'Di"
        "ffContract | None' = None) -> 'ComparisonReport'"
    ),
    "write_contract": (
        "(contract: equiframe.contracts.Contract, path: str | pathlib.Path) -> None"
    ),
}

MODEL_SHAPES = {
    "StageRecord": "a901e1f35808cb0de9a2b2995307192ec43703726d1a58b21753b4944959fe85",
    "Aggregate": "b6c5b7eda83ce13cecbdfeda861e5221b0866072e4a2c91f0b551d2f38db0547",
    "Arithmetic": "0d1893e3cb2f948a9d190c6f8e9d9a03adfc54ee83d7b4be75c5255a7f3357e7",
    "Boolean": "d673b9105dbc210e054aac117b9c2fc11e9e2aa65ff0755b6ce2e159dcc5f59b",
    "Cast": "21886dd309fb2dbc60b9fb727030262af83a98763b2c42c23bfede26249e2dcf",
    "CastColumn": "d83aba584922851c692c6e0de597beb29f07c2a2680b054dd3175e1c016cce64",
    "Coalesce": "c2eb92a99f90667f10500d61caf726e3c8de6e03aed0d088e048006b82303697",
    "Column": "a88273e1437fa598a16761161811a1760469791fac893b22ad4e11d1554c73f4",
    "Compare": "7bbf0041c4eb6928340c660f3be1418495f768ea1cdf9ca012dbc8662d396e88",
    "CompilationCheck": "f1a56ae1199c000fa337f318d0fe648531bf435428497712c8a58cb24ad43c13",
    "CompilationDiagnostic": "934c78c65d58d384d5ed2e7d9c12001e7292c78e7b89efe9b157d943bf3da214",
    "CompilerRecord": "155abf44d2acf50ac0ef9dea8ca4a055bcceb7b5d91df915d405fcd75900b17d",
    "ComponentDecision": "455d92bbdc763c392757cf6f2f504a1050e082b94596d2c301d2abfaa356832f",
    "ComponentDetectionResult": "3b34398f8cabc5e6b9a691f57b8e9a7c9a1e4997efe6efca389c5ce2810fe231",
    "Concatenate": "c3bb0823c4ed7dc82c6cbc14ada3b3ceec1d216b6823cf3a9ff274c8fa69aa7a",
    "Conditional": "8b503fbccada879386c68eb64f82007a53f3761840ae877c5a392b9042a87605",
    "DecimalRound": "274dd2c88fdf2418a295e2504554bc0103a1adf1ebe2f99b3e43cb2dd1be945c",
    "Deduplicate": "d64ccbc7cf6847b828c6ae6ed651f07ffac86cc4984626ff47767c78a086e8a3",
    "DetectionResult": "dabd0f1de4a7437b89572330096c38375e081618f032e3d9cdde05fa45a56b87",
    "DetectorBundle": "adea73af8d4ca17c1a0e40c82ea40d3c9ce7ac841bd7d2b001f5eb94d529d720",
    "DetectorCalibration": "d7fda2ce2f914d7433b4fff257366b670d7e1c0d0decd6b6a2df8085bd32a348",
    "DetectorDecision": "feb569e4caa62d6ad8c2cd03280250647e97100feb892925e817ad87f66074ee",
    "DetectorFit": "3e5a0cacede941489b5e2121f387dad8233e61fb75cbfba16921551842f3fca8",
    "DetectorModel": "dee1cff255a5d462627ce82f1242b7534672f6027c56cf6b3568c87ed41c2d8f",
    "DetectorScoreResult": "d2ba844388cabad55c1cf29428e86611b69b66572dc7f47d3eab2584eec83cf1",
    "DetectorScores": "d8df865c220ee33bf48c392c4fed85d696a79113cf4b14eee5d8bd12fcc6faa9",
    "DetectorSupport": "0c0f7a369a4aa1979c4fb9d799f3340e4088908e0221b3ef1ceaac8cf2f5e48d",
    "DetectorVersions": "914636cc8205656279395c20e994aebb7a90a58fc2c5b14f2792029c81c08103",
    "DuckDBCaptureOptions": "5ccc6cf33a1ef7ff7b915aaf35f7090c6987b7ef66f76a92994e33e767257f7a",
    "EquiJoin": "ea9df499c66b7d86babd5fdb25c946fd484cd635a2a7eb73efbd840c94132b73",
    "EvidenceFile": "30cdc2ca75fa18ebf2f510e308f8e91ecae6d73fd91acd3b9083396bb3c3887f",
    "FeatureFit": "06fc0c015371b19e04431d79099a7a8ca90d57fa35b730023f1d772549c462d1",
    "FeatureMatrix": "d4021f00e8eea912bd7f77bd408c174b2b725d2c892b555163cf68d1b775520d",
    "FeatureObservation": "d1604b12518b0e47b533955a522007dcf0d21d3c2fcba26c6b6fb682e1e552c6",
    "FeatureSupport": "8ebcc4e39a1ee2d6fb948a8c7ef963c27274dbf2f12f0f1627d1c4825d0a0b5c",
    "Filter": "abe7e2979b9b3c077699388763fa4768d5ce5fc4a6e7cfb13da5dcc177c8ba52",
    "HybridDecision": "94b65efb9988bf9a922f0e35b082eef38e667e7b4292fe97badd3662e554b429",
    "IRColumn": "c97d2b497b6bed6ba1d8339b1b648a5ffa3cab54bb1a88331abb6cc46a8e17d7",
    "IsNaN": "cb317fddeec39f579a404a6e75b8686eefe12eb9683f124b8be05cfb25a2a316",
    "IsNull": "4f59534322a29ddac679c90218f9e4c131fe39e8077d0d85e948f505d6ad5764",
    "IsolationForestConfig": "cc9147a5bd7615461dac5a54fe790c69d105d5c409ac3912fec051b7b71863dc",
    "JoinKey": "f0da8bae5dd326557a53e0155dc96357facb0a9fdfa3ce853fed558085aada86",
    "LiteralExpression": "71bac7d94c8d2d0d1c937b52dee23c6402b100794df5565834e6b6dc35b13c4e",
    "LocalizeTimestamp": "3c5571388f208b462ffc9a227a61c89e291fad61e77adc6eba33c3e7494f56ce",
    "Measure": "718508cd579ba85818318c6e7b4021155a43f6e910d6f355abff33a458053e29",
    "MigrationOptions": "7469d5d6dc2af4f5ceffce37ffe1263e6d1360bfc959530ab42244abcab33bfa",
    "MigrationRequest": "fe42af3c7eff94ab06ec3b358ffbe3049715656690f9cf44f10c51a11d42d1fb",
    "MigrationResult": "e8fab4f562f45cdd52b6d3d07fea6315cb3c332b1fde301a352efdaa9b269fa3",
    "MigrationSpec": "537797da0c99c27c441fa70931bbfc12bcb24d672da52ebac9fa48105d32fc28",
    "MigrationStage": "f56660315debc2d619d777f5c199d102f8b2f68e10fc10eb0b2b4fb864a3eef9",
    "NamedExpression": "1f9ffca3583545d215071f1123da5bae3dea33436ebf9fa44bc0cfcfadec1925",
    "NodeSchema": "928bafa04edf914591b7b2adbf3d760a6155bb3ec1cb01152356975a1a7a2ec1",
    "NormalCalibrationProfiles": "b00f3a5d32bc802b73a2ec4bda83737df4d7f3c81c23b85babcceaecbd55210e",
    "NormalTrainingProfiles": "532661b6dd668f5aade9e3ba463898ac49ca7bbd8c1c8ae30de269b9bfe52bf4",
    "Not": "3e00cacd8f6b877a32bc43d3c26d91033b1520706e611679cb0534a1404e9955",
    "PipelineInput": "d6b4eee48a88e3e5f921bc4a9df42fe2e7bbc3301d5bb10f200f559ae46d470d",
    "PipelineResult": "81f8b621857e700a1f8b07c28fc708ba6581a559c9a852fe82efea2dc1324267",
    "PipelineSpec": "153e88c89867a6ab890b3af1648e6f8a063a8d86dbcaa9c7844e23dfac434633",
    "PreprocessorBundle": "6af7f07c9ee4478fcf030ece1de07ae988ee8e9e2cf4a1bb36083668e11646a0",
    "ProfileFeature": "9638104c55a48175cb88f035e0be2b783a5d6f1ed34af2e1d8860563aadb3ca2",
    "ProfileMetadata": "10022ab97e5cd1374a4c6ac8646381ff861bd8c9e95c5096a90848bdd8df0502",
    "ProfileOptions": "763d9d1f9c1c51ae4819712890892f3fa2404cce70c2410ec1d000d72e777da7",
    "ProfileResult": "5c95b094421f9efe4ac367e4729ea9ce5d5a440a4fffdda5c8ec429c02678544",
    "ProfileSpec": "77c5af8f8a222edd515131392f2d684fc7db6aabd010de8b90d229d5051c6c49",
    "ProfileVector": "b204e84b811425c0e286cf437725953d8f37aae9e108cbdddc59bf2d8605353c",
    "Project": "ef53eb5911d0c160bed8ed74876054e548bf032d4d637d041cf8bff5c747a731",
    "RelationalPlan": "3746a0d31fa221fd94b0fe8dfcd4ac53b74797993d95365493c47f7b5d1c1bca",
    "ReviewedDecision": "5f4402ffe22318ec66b30f7d1060bfda63844d075148b2a8d8f3fbf1bc0b66e8",
    "RExecutionBinding": "46d7b30a2ebe8a7eeff8e3f484b04b5e509412c638d1e0467eaad86adce4401d",
    "RReviewBinding": "b246dab63a6b38a03fb65f6c646ab895940f8c5b6d4d88ea55a75a3442ac2f45",
    "RReviewOptions": "e58898a62bfd4e521b5f449b0759791469d918b78e95ab08cba6a765f0070c02",
    "RReviewResult": "fe90eef205d50fb00da1de0b4643430da52570fd262599234d5373a68c338848",
    "Scan": "1a99eb52f09570d571b63fec294aea58a82361fab81e0cae590e28cf7026266e",
    "Sort": "abc9d72359ba468cb5718a5fc93af4d9ad3c964f46518efc20eb85ce2681daf1",
    "SortKey": "0629ac4ad9cb182000ab5bff27671ec553eca32c409a9712ee36dacc2712eeea",
    "Window": "1f690a03cf326f0b2c730771add4f803ba5725b92f7a1ac043209df59a34f2e0",
    "WindowMeasure": "5228783adcc239520ad1340373b4ee0aa7073fdb14b6c2309ae8d942fbc48c49",
    "AdapterCapability": "594a9d87ce663e950dcac34865d387f1bbf2a1812b6faa6e94107cf5fa34cc32",
    "AggregateCheck": "82f9f93bd1f4e525b59298b8e8215c940d8ee5d7eca21a52dd9b5cf476674d4d",
    "AppliedPolicy": "31ffafd29753a685172e5c351ef06fbbf054e4ce5217fb8508260ffebf70ebc6",
    "ArtifactRef": "a07bfab18772f05d5eb78a9a2ea5967808320d306b162553a7ea93c96e6a7b70",
    "BooleanType": "e8a9b9d3d299ee32385002f0bac777970203b9753e8aafbdc9d740ca5978f799",
    "BooleanValue": "742fd9d61286d8b2bfe8048e0fc23355810bf6a48cfaed167c156275a817c09a",
    "BundleReference": "5f82f21f3b25d187544675743e1c720bf21c71ffb2a848c5029954c38e74ebc1",
    "CapabilityStage": "1ba60264dad1363a3f7065c756739c89f658e619150a8ac361a83bf6d4a4c152",
    "CardinalityCheck": "82c73d4a82eed88c14b69d9d98f36074bd301b76322259ded3dccacf757fd43a",
    "CheckResult": "d6bd5c828859fdb751f1c4c063047c3f49e0e3cab007458ee4a637059606cc64",
    "ColumnKeyScope": "7435fbb7bf3fbd17d4f455b10920d9ee21da2637edd3a5d536a2daee69c069e8",
    "ColumnSpec": "3b68577d943f1e1d1b012eebcc3ce092aa70ba1b9ed16af02d5190b8807d431d",
    "ComparisonCounts": "8b840c39ab65ae6e3f9d34618f34195e3b52e784adecd4289f86d626fce724bf",
    "ComparisonDiagnostic": "66f0efddb2d2016a37cc1f92c55ac012335f80d8aec5a5d13cc348f00483fd9a",
    "ComparisonDifference": "efd5fa548b99ea6bf78530a8ce88c313d85af51576ed603ccd4f4572d3643801",
    "ComparisonOptions": "3b71a66755842f9d1a6485f9782f3b2c05a8d5078bd3a314c06f14bc262a2e3f",
    "ComparisonPolicy": "6112737f94553d2af7ca5c6dcd28af97dd5a4446547c47414d787c2b7932c307",
    "ComparisonReport": "df2a15514915af4f8f24f6481ea984bd43fbab6801c8892eeae1f4c7a9d2f2a7",
    "ComparisonResult": "a52e69258dbef0011b7321ef8a674d979891b7eb283471b2f7f1e29207ba3fba",
    "ComparisonSource": "ec8cf72811c97416aeda6be7e495ab7290b2a938d8e14aed4c90500eea52cb34",
    "ComparisonSpec": "6d3ffdbb73d04cb52414684364fb7a5c1d0a467d5306c1e88f4f229fbd0e97e4",
    "ComparisonValue": "ddf3501fb12f0c1ab3f0a3d3637dd0ad65b61f59897bd28b29a3d654e3c5ffea",
    "CompatibilityPolicy": "74e033187250e2da7f31fd24a1ffdd5dbf996003548ea6e115d4729df2ad9ca4",
    "Contract": "faebdcc7adcb20b6f5b89eb2b355dbb7c110cd38d101e60a162c510c0bdcc24e",
    "DatePolicy": "f70b4df718947bff34c1ae6091dc4b695d1563512e00d324e8331516bc72e8bc",
    "DateType": "3fdd683a8f63a51994a07abde481782f3ad1690935f3de8621a5490bcdc99512",
    "DateValue": "f5a3577b73802049a5853104309178ba03e3fc025d3a5087b97a51f083dc1094",
    "DecimalType": "178c8432a009e75b9095fda5dbee0c6740a6d6843a70471d697e033957bfd14f",
    "DecimalValue": "8491cdc218bece327a44fd646aef1e28924656b14e6dfd95fcc679591d98e094",
    "DiffCaptureOptions": "5d0fb5dd3c9017edc6d47510c8956a067ac72565b62a9f9beec7f78da25823d5",
    "DiffContract": "1607b342fe4c928632d31526290275451ad4d97d9a992060ff3b39c9542f84b3",
    "EngineCapabilities": "869b5b56b677b537bfd09f7702dfb8f46f7c8ddd983c2129ef279707df0b13ea",
    "EquivalenceDecision": "ca095206e8439a2699d81dd81c3d9ee25876de11d44214db93aa2222e987802e",
    "EquivalencePolicy": "5533bdeb44f34f1aa93847865a09aa8c187f12284e93f057fe05044cc1f70dac",
    "EvidenceBundle": "3261937386cceafa7fb5850554b50891d7133a3365c168b01bf3f3f6e4c54e9c",
    "EvidenceEvent": "bf436cc9e1c29b4d1376a184830494d59cacd0e74f48153ee3b18d1b47389fcc",
    "ExecutionOptions": "dd9fce75debcbd311bc1b85a76a9f6f7433f41de2f0ff0f437f72a0d06c235fb",
    "ExecutionPlan": "522eba37e95ed9b0b149a380620d5180830185fbdb98a3b04093e82fd3715316",
    "ExecutionProblem": "1753dfc6d476d64e318d4e128bd557b079e35ad45e215781c9fbf3983272071f",
    "ExecutionResult": "32f65fb045bbccb6671bce8108c4082a55065ec7c2400b80e45f6bd3e0b79e5f",
    "ExpectedProvenance": "69f12205af11fa159dfb862b7b6d2480482515515eb89b586f85f0c8477217d7",
    "FloatType": "6d4209f7734d6b3079dbedccc1b39bdd05c4e75df1c5c49be3fa02d4d50bde86",
    "FloatValue": "f5aeb09703960b0975d3e0ecab82aa3750947cc555b5e09516dbee9ad1f31d1b",
    "GlobalKeyScope": "9cc395e91aa3b5a1d550b9505bc96d1f00c5519583f84cd8e5139d311e9306b8",
    "IgnoredOrder": "7b01ee898abf62b47379502e713757d64b0150dc7e768e5b3033a1d4cd2e36af",
    "IndependentReviewEvidence": "b5ac2c988b44ce2d743750300f9f3f218f9c1d14c9880aba5d58e59133d728c7",
    "InfinityValue": "23d8a25f00ae2aac7ac0ed4d268212d56f41ad9d619b0af94e2c3f96c412ee70",
    "IntegerType": "697afa289f1ebab51b8fc29a906ee1ed9c27f80c737f7b49bc198d7251d35dd6",
    "IntegerValue": "c3e0bd2d30114d4e4f2009cccc58f3ff96bbac488365f50c73790f403655e5d5",
    "JoinCheck": "7c0d3e6c3d01eeee18d102bfc70f26d8fb2ee76f3cde6f72ae17c8ad19db1c57",
    "KeyCheck": "782a579142b97de176d0db8db7b3f2d29a0b98a4b8437ad20e703b5669e8d5cd",
    "KeySpec": "7d6ac46d9b34d1e02f51cc8053c2aea22ab750d6d382b458d9339986e603d368",
    "NaNPolicy": "99fd07291e1b9aaf98b32a8cc56aab549a4c2a649c115f7a23510d425b132f54",
    "NaNValue": "761d377ec353de9e826ea5dddc67a3be0755cfaf8f017ad2243236826b9e98f6",
    "NullPolicy": "ade63ff6110f5e5529d12cda99bc6a2775bbb7823aa6e61e2466260de66554c1",
    "NullValue": "5b1ac00d4aa032aff890c192c78b75c27a829ae79782b4ae6acec0ecc0d7e24b",
    "NumericPolicy": "1dce474e140803ab594f24fb1add1b49452b65df154d0a8b6dad92293dbcce52",
    "OrderCheck": "fd81464aee7325d34e9880e3c25721f73351a4d65fd451610c4f80943adff0d3",
    "Parameter": "b4546d97e967ab4e1d20dda8257517db3d844e2fafb5996fe212dc92ec98d6c6",
    "PhysicalColumn": "cbf7cfeb1c704ddc4edc3f319dcdfed2a06d47ae724aaf55ba8af79f30cb81e7",
    "PolicyProvenance": "5e7e19642f07a91a05853ceaf33ee54e6811f0025d41492dcfc9ba2d6d6d773f",
    "PreconditionSpec": "60cd4af5aeddf63864373b01fad6b0dead73ca920324ba7c160b8c6cdb3f9e5f",
    "ReportCount": "d25ed77792ba8e0967c99913e54bfe29e63d9d210e4f590faa66304e0a961b3a",
    "ReportEvidenceManifest": "7ad21c1530bcf585020d692c1b675fed84f3569c92fd1f572c9f873fbec96734",
    "ReportOptions": "505c5bbc2bc5d5ad067fceec2902f19a3b2149180ff87016e4daf5b1b6550160",
    "ReportPolicy": "22b5fcae34575640c44c9fafaabaf4dcfd3cb3f6346669b2f46c6072de5c8f00",
    "ReportPublicationManifest": "deda976bd5a29430e58139730abc389ce28e5f458877918f9f62d59dd51652e3",
    "ReportValue": "087ffe9a733bdbea8a0e1bd5c29349c314c4b32ea7ae9864eb4af709f23b2ca9",
    "ReportViewPolicy": "799ac4401d5f977ba3e42cc4aa7f20c6f99bcdcb5cdb7ca6d5da129c187164f8",
    "ReportWitness": "7a4743121ac0e84df7ba88dd8f1994be64220f5c7daecbf16ea9763dfe22238a",
    "RuleCoverage": "99cb8d1b603a58eaa237cf3ff4a42ddbb2eff7f6149c90037195692dd6cf8559",
    "RuleEvaluation": "98f38f596cc9fa5e49ca17929fe26c4c016d3cd6e9d616ba955f52a8e6f77435",
    "RuleFinding": "23aa44c8ceabae2a471862bdcf440673b69483ec018bdb80a513e1d736ae9c1b",
    "RuleOptions": "e6546b88c0848b160407eec63aaf8e6b6122ff8edc38b40fb4c98ae4cb049c7a",
    "RuleSpec": "ee545f50b17c23e1439a4529558084ac1dcca8ab8d5632f253c2f11d8a9a55f6",
    "SchemaCheck": "3ba66998d177614ef12f11533a3b1dafdbde36346f31250a3f671ab6552d22e0",
    "SchemaRef": "fd8a723bd5608ea3551c1bd29b643a4e63877b04c704e915ffbb4abf7a7307d5",
    "SignificantOrder": "16ef3f6a54b40653207c6ec0d16ee5cd1a93a74874843e7225b1ffa7584975d2",
    "SortSpec": "d5da703ff2c3a370410876fb87038dac36b9d8c2fbc2cc224eed421a49aca5ed",
    "StabilityRecord": "05fd18bbb824f9163a7deef03f307ef8f82f81b8a058c5df1f88719416606213",
    "StageTiming": "6c467b6470fd87b62057a0828d1ac19304add320aafa301df8ba2bda10aa6b34",
    "StringType": "5e6df8eea05c2a2dbfac3f7dba5ad928d205306903b42fff7299e91d7475671a",
    "StringValue": "44c64b71c39d00dd70ddf28b874be0a64e6773716e858ddc0f58b0294cc48b19",
    "TableArtifact": "abe2ad305d64564af5aaabb01f6bd7913d3ba5c008437b136d38e594be67ab2a",
    "TableKeyScope": "6ba02464d00f8eb367137f377214c49ba00785528c41791fa53ece253005c063",
    "TableSchema": "d97fb2787de3fef7f96713952fa930dda3660bd0f97bc9121365b5c2f0cd1af5",
    "TableSpec": "d179b4214668f998595dfeb5778669d561c1c6cd34fd66e565ed02b4abf472e6",
    "TimestampPolicy": "e0bcd0289787d50a5a4770d4400c14df8f5d490551bdde24cfa0b2dce2f5201b",
    "TimestampType": "9944d0acc632569d7758bd80cd558fa2cc2cd41a0a34511eb403e4a53300d6a9",
    "TimestampValue": "2dab134416ee49c929112d98fdb34525efe20e8f4599d991519a198c2a04fc96",
    "Tolerance": "ba93db177a420d3f0c3bb6686d4a36c81f5990e1f5d2a4e30fd51b6b659065e3",
    "VerificationBinding": "849f8b77ca6eb9712143e164caf452a277809db6f51940cc636acf66ff449e4a",
    "VerificationCheck": "fa8d551a04706db4f402d866a112725f825567fedf31a3557181be2018e923cd",
    "VerificationCoverage": "362b3aef6c3cd874b9ac8e996a482b951895a247eeeeeeeaf50d7e94aef773b0",
    "VerificationRequest": "eb0fa1998062944180db55db805c993340736923ceaba5bbb630d2595e047180",
    "VerificationResult": "65b5457c5feea88190016e843b780f2382edef7af1f3c8d100fb84de5f01d4b6",
    "VerificationReview": "b4ef6bbf2ad01c67e7fcdf6af0ab8f97c27e9bd67c26645d924c0487c33a41a5",
    "VersionInfo": "d535207c7d621e9cd03ae8aefa82e3900d593bc02a36d91cd9413e8279e812d4",
}
