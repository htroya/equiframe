# EquiFrame Benchmark 0.12.2

**Experimental evaluation, reproducible evidence and bounded engineering costs.**

[Principal paired protocol V2](PROTOCOL_V2.md) provides a separately versioned
freeze → native study → paired evaluation → seven tables → portable reproduction
route for the three primary families and three engine pairs. V1 readers,
fingerprints and common-support results remain unchanged. Twenty-four focused
engineering checks cover the new route, including real API/CLI roundtrips over
fictional held-out native cases and portable reproduction. These checks provide no scientific approval;
final protocol review remains an explicit requirement.

`equiframe-benchmark` is separate from the core `equiframe` package. It provides
scenario catalogs, independent-review records, grouped splits, reviewed normal
selection, frozen studies, paired evaluation, reproducible tables/bundles and
resource measurements. The core never imports it or receives oracle labels as
detector features.

## Release scope and compatibility

This distribution is paired exactly with `equiframe[arrow]==0.12.2` and
supports Python `>=3.10,<3.14`. Original code is licensed under [MIT](LICENSE);
dependencies retain their own terms in [third-party notices](THIRD_PARTY_NOTICES.md).

The owner authorized publication on 2026-10-27 and confirmed local manual
publication on 2026-10-28. Uploads use an ephemeral local API token, revoked
after use; no GitHub Actions job or stored GitHub publishing secret is used.
The release checklist binds the inspected commit and all four artifact hashes,
checks the security review and clean consumers, and promotes the same bytes.
A version label or this README does not establish a successful upload.

The benchmark's scientific protocols and APIs remain experimental. Software
correctness tests preserve their documented contracts but do not establish
real-data accuracy, reviewed corpus labels, independent human acceptance,
external adoption or a deployed service/data warehouse.

Hernán Troya (`htroya`) is the confirmed maintenance, release and security owner,
with no response-time SLA. Public documentation and ordinary issues are at
[EquiFrame documentation](https://github.com/htroya/equiframe).
Sensitive reports use its enabled
[private reporting channel](https://github.com/htroya/equiframe/security/advisories/new).
Historical Alpha artifacts and results retain their original identity and scope.

The core wheel includes the self-contained English handbook with API, semantics,
compatibility, contribution, security, dependency/SBOM and release procedures:

```python
from importlib.resources import files

print(files("equiframe").joinpath("docs/index.md").read_text(encoding="utf-8"))
```

From an authorized monorepo checkout the same guide is at
[core handbook](https://github.com/htroya/equiframe/blob/main/docs/index.md); installed consumers do not need
repository access. This README is included in distribution metadata. Benchmark
sdists also include examples, tests, tools and JSON schemas.

## Install exact artifacts, then run outside the checkout

Obtain both identified wheels and a reviewed dependency wheelhouse for your
interpreter/platform/profile. Verify supplied SHA-256 values before installation.
In a fresh directory outside the repository, using a POSIX shell:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
CORE=/absolute/path/equiframe-0.12.2-py3-none-any.whl
BENCH=/absolute/path/equiframe_benchmark-0.12.2-py3-none-any.whl
WHEELHOUSE=/absolute/path/reviewed-wheelhouse
python -m pip install --no-index --find-links "$WHEELHOUSE" "${CORE}[engines]" "${BENCH}[resources]"
python -m pip check
python -I -c "import equiframe, equiframe_benchmark; print(equiframe.__file__); print(equiframe_benchmark.__file__)"
python -I -m equiframe_benchmark.pilot --output pilot-synthetic
```

Absolute paths are placeholders for verified local files. Missing compatible
binary dependencies are a blocker; do not drop hashes or switch to an unrelated
index package. Avoid editable installs/PYTHONPATH as artifact validation. Windows
can use `py -3.12 -m venv .venv` and `.venv\Scripts\python.exe` directly without
changing activation security policy. Command conventions are not platform tests.

The benchmark base requires Arrow through core and `packaging>=26,<27`.
`engines` adds pandas/Polars/DuckDB; `ml` adds the core ML extra;
`resources` adds `psutil==7.2.2`. Choose reviewed dependency pins for the required
profiles. Metadata admission does not prove all platforms or range combinations.
Historical measured cells are Linux x86_64/Python 3.12.14 and 3.13.5; a current
candidate needs its own exact-artifact receipt. Manual CI configuration is not a
remote job result, and Windows/macOS/ARM64 are not newly claimed as verified.

The pilot destination must be new. `equiframe-benchmark-pilot --output DIR` is an
installed equivalent entry point. The synthetic pilot produces 5 scenarios,
35 candidates, 15 profiles and 4 dependency groups. **All 35 reviews remain
pending**. Its 15 mutations are artifact injections; its 15 control
transformations execute natively. These are not a completed thesis sample or
trained scientific model.

## Review, grouping and normal selection

Public models include `Scenario`, `Catalog`, `Candidate`, `ReviewPacket`,
`ReviewAssignment`, `Review`, `OracleResult`, `SplitManifest`, `TrainingSelection`
and `CalibrationSelection`. `load_document`, `save_document` and `digest` use
strict canonical JSON and explicit evidence identity.

This snippet continues from the synthetic pilot above:

```python
from pathlib import Path
import equiframe_benchmark as eb

root = Path("pilot-synthetic")
catalog = eb.load_document(eb.Catalog, root / "catalog.json")
splits = eb.load_document(eb.SplitManifest, root / "splits.json")
eb.validate_splits(catalog, splits)
print(eb.split_counts(catalog, splits))
scenario = catalog.scenarios[0]
candidate = eb.load_document(eb.Candidate, root / "nulls_types" / "pandas-candidate.json")
packet = eb.review_packet(scenario, candidate, directory=Path("review-packet"))
pending = eb.evaluate_oracle(scenario, candidate, packet=packet, work_dir=Path("oracle-evidence"))
assert pending.status == "pending" and pending.label is None
```

Only the blinded packet goes to the reviewer. Keep catalog/candidate metadata,
alerts and other reviewers' decisions separate. Record two independent reviewers
and an arbiter in an assignment before review, with UTC timestamps. Reviews
require packet hash, identity declaration, decision, rationale, timestamp and
blind attestation. Resolution is permitted for disagreement by the assigned
arbiter. Do not generate human approvals from comparator output. Hashes and JSON
names do not authenticate a human or establish true independence.

`dependency_groups` closes transitive declared/artifact dependencies before
`make_splits`; `validate_splits` and `split_counts` retain group/partition scope.
`select_normal_training` and `select_normal_calibration` require candidate,
oracle, execution and profile maps with exact linked identities, one family and
feature definition, confirmed normal O, and the appropriate disjoint partition.
The pending pilot is not eligible normal training evidence.

`audit_detector_selections` checks shared catalog/split, compatible features,
independent groups and no reused scenarios/executions/profiles. Respect
`eligible`/`not_estimable`, preserve counts and justify minimum support before
freeze. Core `fit_detectors`, `score_detectors`, `calibrate_detectors`, `detect`
and `detect_component` separate fitting, scoring, calibration and inference.
No anomaly/no-alert state is a comparison oracle; test never fits the model.

## Public workflow reference

The exhaustive experimental export namespace is `equiframe_benchmark.__all__`.
Use `inspect.signature(eb.function)` and each model's `model_json_schema()` for
installed signatures/defaults. These are distinct families:

| Family | Entry points |
|---|---|
| Blinded review | `review_packet`, `evaluate_oracle`, `oracle_verification_bridge` |
| Dependency splits | `dependency_groups`, `make_splits`, `validate_splits`, `split_counts` |
| Reviewed selections | `select_normal_training`, `select_normal_calibration`, `audit_detector_selections` |
| Snapshot consumer | Compatibility aliases of core `SnapshotClient`, `SnapshotDataSource`, `snapshot_fingerprint` |
| Three-engine integration | `run_integration`, `read_integration` |
| Domain-configurable reconciliation | `reconcile_awards`, `AwardReconciliationSpec` |
| Freeze/study | `audit_freeze`, `create_freeze`, `read_freeze`, `run_study`, `read_study` |
| Evaluation | `evaluate_records`, `evaluate_pairwise`, `evaluation_protocol_sha256` |
| Tables | `table_payloads`, `write_tables`, `read_tables` |
| Scientific cost protocol | `measure_costs`, `read_costs`, `write_cost_table` |
| Record reproduction | `make_reproduction_record`, `compare_reproductions` |
| Generic bundles | `create_bundle`, `read_bundle`, `bundle_artifact`, `reproduce_bundle` |
| Study bundles | `bundle_study`, `regenerate_study_record`, `reproduce_study_bundle` |
| Engineering scale | `measure_scale`, `read_scale`, `summarize_scale` |
| Distribution inventory | `inspect_distribution`, `DistributionReadiness`, `NameCheck` |

Snapshot consumers pin a declared publication and verify artifacts from an
explicit trusted client. `run_integration` executes each of three registered
native implementations once, then compares three pairs. A separate optional
expected output is fixed before execution. Shared captures do not become
additional independent observations when reused in several pair comparisons.
If a native execution fails, its expected-output comparison is recorded as
`execution_unavailable`; the operation stays incomplete and healthy independent
pairs retain their evidence. The synthetic date fixture uses Pandas' native UTC
microsecond dtype before extracting date32, including empty and NULL values,
so it does not require Arrow's separate C++ timezone database on Windows.
Client/DW authentication, service writer coordination and production acceptance
are not implemented by the consumer interface.

## Freeze, study and reproduction

`FreezeDefinition` records catalog, grouped splits, cases, family model slots,
reviewed selections, prior decisions, files/hashes, environment and evaluation/cost
protocols. Pilot freeze verifies technical readiness while retaining scientific
blockers. Final freeze requires those blockers resolved; it does not manufacture
reviews or fit on test data.

The following are command **templates** using your own reviewed files and trusted
registry factory; they are not a complete runnable scientific experiment:

```text
equiframe-benchmark freeze definition.json --output freeze.json
equiframe-benchmark verify-freeze freeze.json
equiframe-benchmark run-study freeze.json --registry my_etl:create_registry --output studies
equiframe-benchmark verify-study studies/study_ID
equiframe-benchmark evaluate studies/study_ID --output evaluation.json
equiframe-benchmark tables studies/study_ID --output regenerated-tables
equiframe-benchmark bundle-study studies/study_ID --output portable-study
equiframe-benchmark reproduce-study portable-study --expected-sha256 TRUSTED_BUNDLE_MANIFEST_SHA256
```

Factory references import and execute trusted code explicitly. JSON requests do
not authorize arbitrary plugins or contain credentials. The frozen historical
main comparison uses confirmed O and common complete R/M/B/H support, retaining
individual support, partial alerts, failures and exclusions. `evaluate_pairwise`
adds six descriptive pairwise supports with their own denominators; it preserves
the original report/protocol/six CSV and remains `scientific=False`. Using that
analysis as a new scientific primary protocol requires a new freeze.

Undefined precision, recall, F1 and FPR remain absent with reasons. Average
precision requires two classes and a common family/model. Bootstrap samples
whole groups and requires a prior independence rationale. CSVs regenerate from
verified records; editing a CSV and recomputing its hash does not create valid
changed evidence.

Study bundles preserve original captures/manifests and regenerate configuration,
splits, labels, decisions and tables without rerunning ETL. They do not certify a
colleague independently repeated the experiment. Raw costs are retained without
requiring identical timings on reproduction. The distribution inventory does not
reserve a name, resolve licensing, install a package or authorize publication.

## Cost protocols and engineering scale

`measure_costs` uses a frozen scientific `CostProtocol`: isolated profile+M versus
full comparison over already captured outputs, one warmup and five alternating
repetitions per method. Initial ETL/capture is excluded. `cost-table` retains all
twelve raw observations, warmups, failures and reasons. Repetitions do not increase
the independent detection sample. Missing monitoring is never imputed as zero.

The separate engineering protocol `ScaleSpec`/`ScaleTrial`/`ScaleRun` measures
bounded synthetic integer/text/NULL workloads. See the installed core handbook's
`docs/performance.md` for a complete small script, stage boundaries and budgets.
Source distributions also contain `examples/scale_local.py`, which defaults to
1k rows; 100k/1M require explicit `--rows` and larger recorded budgets.

One isolated trusted worker records fresh/warm process groups with uncontrolled
OS caches, nine stages, sampled RSS/CPU/I/O, disk and evidence bytes. RSS/disk
thresholds are reactive and can overshoot; they are not hard quotas. A valid
completion marker, expected verdict and verified inventory are required.
`complete` and `resource_measurement_complete` are separate: a successful
operation can have incomplete observations.

Restricted native pandas/DuckDB baselines provide less evidence; time ratios
are not equivalent-service speed rankings. DataComPy is unpinned/unavailable,
with no invented timing. Kill, missing finalization, failed/partial measurement,
ENOSPC and last-batch differences stay visible. Receipts are location-bound;
reproduction uses the specification and exact wheels, not an implied portable run.

## CLI exits and safe interpretation

`equiframe-benchmark --help` lists the installed commands, including catalog
`validate`, `split`, `pilot`, integration, freeze/study, evaluation, costs and scale.

- Study/integration operations distinguish complete without alert (0), complete
  with alert/difference (1), invalid input/freeze (2) and partial/unavailable (3)
- Integrity `verify-*` commands can return 0 for intact evidence of a historical
  incomplete run; read the stored semantic state. They do not turn it into success
- Reproduction disagreement uses 1; invalid evidence uses a failure code
- `costs` uses 3 for incomplete measurement
- `scale` and `verify-scale` use 3 for unsuccessful/incomplete measurement or
  invalid finalization. Their zero is expected-workload completion, not equivalence

The historical core `equiframe.benchmark` placeholder is quarantined and not a
compatible shortcut into this package. Do not reenable its removed metrics or
infer scientific results from synthetic demonstrations.

## Development and contribution

Operational errors retain their original first stderr line and exit status,
then add one fixed-text `hint[category]: ...` line. For example, an existing
output recommends a new path instead of overwriting evidence; a missing file
recommends checking the input and parent directory. Hints omit raw exception
messages, data and paths. Automation should read the exit status and first
line, not compare the complete stderr text. `scale` retains exit 3 for its
failed operation, including invalid specifications.
The standalone `equiframe-benchmark-pilot` entrypoint also uses fixed hints;
its operation failures retain exit 1 and print `pilot_operation_failed`.

From `packages/equiframe-benchmark`, with the matching core wheel already built:

```bash
uv sync --locked --all-extras --reinstall-package equiframe
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy
uv run --locked --all-extras python tools/generate_assets.py --check
uv run --locked --all-extras pytest -q
uv run --locked --all-extras python -m build --no-isolation
uv run --locked --all-extras twine check --strict dist/*.whl dist/*.tar.gz
uv run --locked --all-extras python tools/verify_distribution.py
```

`--reinstall-package equiframe` prevents stale local dependency caching while a
package version is unchanged. From this directory, the byte-bound candidate driver is
`python ../../tools/check_candidate.py --package . --output /absolute/path/new-checks.json`.
These are checks to execute, not claims they already passed this artifact.
Source tests, exact installed tests and remote CI are distinct evidence. Preserve
historical fixtures, safe failures and methodological boundaries. Follow the core
handbook's contribution, upgrade, security and release procedures. No public
publication or production deployment is authorized by building these artifacts.
