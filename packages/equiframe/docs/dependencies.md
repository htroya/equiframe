# Dependency inventory, licenses and advisory evidence

The package metadata declares allowed version ranges; `uv.lock` records exact
resolutions, including conditional branches for supported environments. Neither
means that every possible version combination has passed the test matrix.
Keep the exact Python/platform marker environment with the resolved inventory.

Runtime is deliberately separated from optional engines and ML: base contracts,
models and CLI depend on Pydantic, Typer and tzdata; Arrow and each native engine
are opt-in; ML is opt-in; the benchmark is a separate distribution. Build and
validation tools are development dependencies, not required by a normal core
import. The benchmark's dependency must resolve to the exact core candidate
wheel supplied with its evidence, not another private wheel with the same
version string.

## Reproducible evidence workflow

The source distribution carries `tools/dependency_inventory.py` and the pinned
CycloneDX schemas. Run the tool with the locked core development interpreter.
`generate` is offline: it inspects the selected package, exact wheel and sdist,
lock profiles and installed metadata. `scan` is explicitly networked, querying
version-specific PyPI metadata and OSV for registry dependencies. `verify`
rederives the inventory, validates the artifact bindings and schemas, and checks
snapshot consistency/freshness. Consult `--help` for exact options.

Run these from the repository root after both packages have been built and their
locked development environments have been prepared. The following paths use
POSIX virtual environments; on Windows use the corresponding `Scripts/python.exe`.
Output directories must be new so an earlier receipt cannot be overwritten.

```sh
PY=packages/equiframe/.venv/bin/python
TOOL=packages/equiframe/tools/dependency_inventory.py
CORE=packages/equiframe
BENCH=packages/equiframe-benchmark

$PY $TOOL generate --package "$CORE" \
  --artifact "$CORE/dist/equiframe-0.12.0a9-py3-none-any.whl" \
  --artifact "$CORE/dist/equiframe-0.12.0a9.tar.gz" \
  --output evidence/dependencies/core

$PY $TOOL generate --package "$BENCH" \
  --artifact "$BENCH/dist/equiframe_benchmark-0.12.0a9-py3-none-any.whl" \
  --artifact "$BENCH/dist/equiframe_benchmark-0.12.0a9.tar.gz" \
  --environment-python "$BENCH/.venv/bin/python" \
  --local-artifact "$CORE/dist/equiframe-0.12.0a9-py3-none-any.whl" \
  --output evidence/dependencies/benchmark
```

Each directory contains `inventory.json` (`equiframe.dependencies/1.0`) and two
`<artifact filename>.cdx.json` files. The BOMs are CycloneDX 1.6, validated against
the unmodified official draft-07 JSON schemas with pinned SHA-256 and a closed,
local schema registry. They contain a clearly labelled union of profile closures;
they do not imply that build/dev dependencies are embedded in, or required by,
the wheel. Each component lists its profile membership. Only explicitly stated,
valid SPDX expressions are represented as license expressions; other source
metadata is retained for review rather than converted to an invented license.

The tool needs `packaging` and `jsonschema` from the existing core development
lock. It installs nothing and does not add runtime dependencies. It reads
installed metadata and license files without importing dependency/project code.
The interpreter selected by `--environment-python` supplies the observed marker
environment and distribution metadata. Other-platform lock branches are not
claimed to have been installed or scanned. Missing installed metadata is recorded
as unknown; exact lock versions are never relabelled as installed when absent.

An advisory refresh requires an inspected public-only allowlist and an offline
request preview. Create `public-allowlist.json` containing only exact reviewed
public `name`/`version` objects from the artifact-bound inventory; exclude the
project, all private consumers/internal packages and any ambiguous provenance.
A registry label by itself is insufficient. This file and the preview remain
local; neither the complete inventory nor its metadata is uploaded.

```sh
$PY $TOOL prepare-scan --inventory evidence/dependencies/core/inventory.json \
  --public-allowlist public-allowlist.json --output public-requests.json
# Inspect public-requests.json: URLs, bodies, anonymous headers and exclusions.
$PY $TOOL scan --inventory evidence/dependencies/core/inventory.json \
  --public-allowlist public-allowlist.json --request-plan public-requests.json \
  --output evidence/dependencies/core-advisories
```

Repeat with the benchmark inventory and its own reviewed allowlist/preview.
Preparation is offline and proves no provider coverage. Execution rejects a
changed preview, names absent from the allowlist, private/local sources, extra
payload fields, URL query/userinfo/insecure destinations and all redirects.
No project-identifying User-Agent, credentials, cookies or referer is supplied.
Provider pagination tokens are validated and remain bound to the same query.
Platform-denied requests must stop; changing a route is not authorization.

`scan` writes `advisories.json` (`equiframe.advisories/1.0`) and one snapshot per
public package/version/provider. It preserves the exact UTF-8 JSON response,
its SHA-256, parsed content, request, source URL, time and failures. It queries
PyPI's release endpoint and OSV, retaining GHSA IDs/advisories supplied through
those sources. It does not claim an independent direct GitHub Advisory API scan.
Private/local project packages are explicitly excluded from public name lookups.
The command exits 0 for complete `no_known_advisories`, 2 for `findings` or
`unknown`, and 1 for invalid inputs. Failure receipts remain available.

Reverify the final artifact bytes, lock, selected environment, BOMs and audit:

```sh
$PY $TOOL verify --package "$CORE" \
  --artifact "$CORE/dist/equiframe-0.12.0a9-py3-none-any.whl" \
  --artifact "$CORE/dist/equiframe-0.12.0a9.tar.gz" \
  --inventory evidence/dependencies/core/inventory.json \
  --advisories evidence/dependencies/core-advisories/advisories.json \
  --max-age-hours 24 --require-clean

$PY $TOOL verify --package "$BENCH" \
  --artifact "$BENCH/dist/equiframe_benchmark-0.12.0a9-py3-none-any.whl" \
  --artifact "$BENCH/dist/equiframe_benchmark-0.12.0a9.tar.gz" \
  --environment-python "$BENCH/.venv/bin/python" \
  --local-artifact "$CORE/dist/equiframe-0.12.0a9-py3-none-any.whl" \
  --inventory evidence/dependencies/benchmark/inventory.json \
  --advisories evidence/dependencies/benchmark-advisories/advisories.json \
  --max-age-hours 24 --require-clean
```

For an offline-only verification, omit `--advisories` and `--require-clean`;
that result establishes no advisory coverage. `--require-clean` always needs a
complete fresh audit. Freshness defaults to 24 hours; an explicit larger window
is bounded at 168 hours and must be justified by release policy. Missing snapshots,
changed hashes, changed local core wheel, stale timestamps, omitted packages,
inconsistent summaries and changed source declarations fail verification.
The verifier reconstructs the expected inventory and BOM instead of trusting
positive fields in a receipt. Receipts are unsigned: consistent total replacement
of artifacts and evidence is outside their authenticity guarantee.

The evidence distinguishes runtime base, individual extras, all extras, dev and
build profiles. It records declared requirements, resolved versions, lock and
artifact hashes, observed dependency metadata and license-file hashes. A
CycloneDX BOM is tied to each artifact rather than to an unspecified checkout.
Local project dependencies require an explicit candidate wheel. The schemas
are retained with source URLs and hashes for offline validation; their upstream
license notices apply to those schemas, not to EquiFrame.

An installed dependency's license expression, classifiers, free-form metadata
and files may disagree or be incomplete. Preserve those observations and their
provenance; do not guess a missing license or treat metadata as legal clearance.
Native wheels can bundle third-party libraries that are not separate Python
distributions. The Python dependency inventory is not an exhaustive inventory
of every bundled native component, the operating system or build infrastructure.
Redistribution review must inspect the applicable binary notices and conditions.

## Interpreting advisory results

Retain the query time, exact name/version, provider, URL, returned bytes/hash and
errors. A successful response with no listed advisories means only that the
provider returned none for that version at that time. Missing releases, blocked
networks, HTTP errors, incomplete provider coverage, stale or malformed evidence
are **unknown**, never zero vulnerabilities. A provider identifier is not a
confirmed exploitability assessment of EquiFrame's usage.

Inspect primary advisory records for affected/fixed ranges, severity and relevant
runtime paths. Record each correction, justified exception or unresolved result.
Changing a dependency requires rebuilding the lock/first-use pins as applicable,
rerunning the affected profiles and full release checks, and regenerating all
artifact-bound evidence. Do not suppress an advisory merely to obtain a green
release status. Recheck close to publication; an old snapshot cannot establish
current safety. `--require-clean` fails closed if coverage is unknown, findings
remain or the snapshot is stale.

## Release limits

The inventory and scan are separate from the unfinished source-security review.
They do not assign a project license, prove publisher identity, authorize public
redistribution or establish that the software is secure. Public release remains
blocked by the [recorded release decisions](releasing.md). The dated candidate
report states exactly which scans completed and which checks were unavailable.

Standards and provider documentation:
[CycloneDX 1.6](https://cyclonedx.org/docs/1.6/json/),
[PyPI JSON API](https://docs.pypi.org/api/json/),
[OSV query API](https://google.github.io/osv.dev/api/)
