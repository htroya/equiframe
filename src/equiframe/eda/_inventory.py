"""Explicit first EDA public surface; update only with reviewed contract changes."""

INVENTORY = {
    "status": "experimental",
    "format_version": "1.0",
    "public_names": (
        "ColumnProfile",
        "Conversion",
        "DuplicateProfile",
        "EdaConfig",
        "EdaManifest",
        "EdaResult",
        "Finding",
        "KeyRule",
        "NumericRule",
        "Resources",
        "ResultFile",
        "Source",
        "analyze",
        "analyze_artifact",
        "analyze_migration",
        "read_result",
    ),
    "signatures": {
        "analyze": "(source: 'Source', *, config: 'EdaConfig | None' = None, "
        "output: 'Path', cancellation: 'Callable[[], bool] | None' = "
        "None) -> 'EdaResult'",
        "analyze_artifact": "(artifact: 'TableArtifact', *, config: 'EdaConfig | "
        "None' = None, output: 'Path') -> 'EdaResult'",
        "analyze_migration": "(path: 'Path', *, side: \"Literal['source', "
        "'target']\" = 'source', config: 'EdaConfig | "
        "None' = None, output: 'Path') -> 'EdaResult'",
        "read_result": "(path: 'Path') -> 'EdaResult'",
    },
    "model_shapes": {
        "ColumnProfile": "fef8bbba53cfe502ec13bdbdb6c20e2635a1c9865b92655cebe367ace0ce81e9",
        "Conversion": "f6f432c6c02a2f3f770d6fc602cf6dc6202302b46bdf670540cc2f2dadc00f95",
        "DuplicateProfile": "2a1f6d9efd1618d82de32b4c4d5948f3a0d89b0452924da3c495c69caa9eeaa6",
        "EdaConfig": "65ea2de1dd1d43bd0f1bb8942dd5b28ff7a95f346c24edc01418ec5a04083fe1",
        "EdaManifest": "f9d3b6ccb63249f7bd796f8154135a04c844578231666a988e400c857d0b3e2d",
        "EdaResult": "5bce9ab1457ab99b5ed818ecaac7695caef205c12eff29dd0fe6507e8c8a0cad",
        "Finding": "331db5cf15d9e26ef8b94e2fd25e625e2e804165f6c584d78a6a3c83ea41faa2",
        "KeyRule": "4b0f8f2f6baf3eca22ab5c0da607d90f46c61bec008b5d8a760b61372a18828e",
        "NumericRule": "16951b2437617d4d52437d3124d7b394f546ba49eac98f9c049ab07fefe21938",
        "Resources": "82173ef020b2937c4c7aaf1cea037effbc836dfecf25e5929c29cd3702898e9a",
        "ResultFile": "eb3f6aa3e82b85493541404add0212327cf0b6223f2c858cd615d83df1e1b7e8",
        "Source": "182d1cc45e149e0251acdae721dd78b4f73721d69cd52f630140c805b96265fb",
    },
}
