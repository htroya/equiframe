# Vendored CycloneDX schema

These unmodified JSON schemas are from the official CycloneDX specification,
tag `1.6` (retrieved 2026-10-06). JSON Schema draft-07 validates CycloneDX 1.6;
this is a deliberate fixed schema version, not a claim about the newest release.

Source: https://github.com/CycloneDX/specification/tree/1.6/schema

- `bom-1.6.schema.json`: SHA-256 `3e92dddbc30cf7f6a02b80f0942b1a4cfd4fb1c26f1dfc4310afa9d613cafb93`
- `spdx.schema.json`: SHA-256 `baa9d3bd1ed57b6751b0887edead6b5063ff53ff7429cf85d476c6c94af0166e`
- `jsf-0.82.schema.json`: SHA-256 `8bae002c25e723db7ee1f26afde680ae1a2b1a8f6b4b4b0fd65dc3becb090aae`

The Apache-2.0 upstream LICENSE is copied alongside these schemas. This applies
to the schemas, and does not assign a license to EquiFrame. Local validation
checks these hashes and uses a closed schema registry without network retrieval.

Updating requires explicit schema review, updating the digest pins and tests,
and regenerating inventory evidence. Never relax the schema to accept a BOM.
