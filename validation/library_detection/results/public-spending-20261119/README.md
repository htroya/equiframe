# Frozen public-spending evidence, 19 November 2026

Read the [study and limits](../../../../docs/public-spending-evaluation.md) first.
The public PyPI release remains 0.14.0. This study measured an installed local
experimental 0.15.0.dev1 artifact, identified by its wheel and package-file hashes.

`manifest.json` identifies ten losslessly compressed records. Gzip timestamps
are fixed to zero; decompression must reproduce each uncompressed SHA-256.
No source rows, database, credentials or fitted model is distributed here.

## Read and reconcile the evidence

Extract into new private directories, preserving the prefixes as follows:

- `primary-*.json.gz` → `primary/<name>.json`.
- `severity-*.json.gz` → `severity/<name>.json`.
- `cost-report.json.gz` → `cost/report.json`.

Use Python's standard `gzip.decompress` and verify both hashes from the manifest
before parsing. Then, from the repository root:

```sh
python validation/library_detection/verify_spending.py --primary /new/primary --severity /new/severity
```

The verifier recomputes confusion counts and denominators from 7,552 recorded
decisions, checks strict thresholds, fixed model identities and ten forest-path
reconstructions. It does not infer actual row equality from an output hash.
Actual values and source-procedure disjointness were checked during execution.

## Execute the experiment again

Use a separate Python 3.10–3.13 environment and install the experimental source
with its engine and ML extras. A public 0.14.0 installation rejects profile 1.2.
The measured core files are identified individually in the primary protocol;
later documentation or compatibility-register edits do not identify a different
numeric model as the original measured artifact.

Download the annual 2025 CSV export from the
[official SERCOP endpoint](https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/download?type=csv&year=2025&month=0&method=all).
The exact project snapshot is available in the
[public read-only corpus](https://mailinternacionaledu-my.sharepoint.com/:f:/g/personal/hetroyapr_uide_edu_ec/IgDQM22xG5UGS6U_UsKmaXoBAc4YkPrvEqZ277Z_lzno-CY).
The protocol requires these original, unmodified files:

| CSV | SHA-256 |
| --- | --- |
| `releases_2025.csv` | `ac2befc303dbbe1aaeeecc8739f657878e05cb06a8cf12d6560356a30bc81d24` |
| `awards_2025.csv` | `63cdb63bc413c419a3bf33cce3d6755e5566440e959c56ec77f18d43c3d6e91d` |

Keep an installation receipt with the wheel hash, actual distribution version and
the SHA-256 of every installed `equiframe/` package file. The primary protocol's
`runtime_identity` shows that structure and the 177 measured file identities.
Do not claim a different installation has the measured hash.

The supplied helper verifies every installed package file against a local wheel:

```sh
python validation/library_detection/runtime_receipt.py /private/equiframe-candidate.whl > /private/installation-receipt.json
```

```sh
python validation/library_detection/public_spending.py --csv-dir /original/csv --runtime-receipt /private/installation-receipt.json --output /new/primary
python validation/library_detection/spending_severity.py --csv-dir /original/csv --primary /new/primary --preregistration validation/library_detection/results/public-spending-20261119/severity-preregistration.json --output /new/severity
python validation/library_detection/spending_cost.py --csv-dir /original/csv --primary /new/primary --models /new/severity --output /new/cost
```

Directories must be new. The primary protocol is written before case execution.
The severity script reconstructs primary training/calibration and rejects a model
fingerprint mismatch before scoring supplementary test cases. Temporary captures
are private and removed. `private-model-*.json` files are for the local cost pass;
do not publish them. Run the cost pass after other measurement/test jobs finish.

The source snapshot, procedures, dependency versions and seed affect numerical
reproduction. Host latency and timing records are observations, not reproducible
byte identities or service-level guarantees. Pooled counts in the supplementary
JSON are descriptive; the inferential difference uses the recorded whole-source
cluster bootstrap, not an independence assumption for paired severity variants.
