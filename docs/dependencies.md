# Dependency inventory, licenses and advisory evidence

The package metadata declares allowed version ranges; `uv.lock` records exact
resolutions, including conditional branches for supported environments. Neither
means that every possible version combination has passed the test matrix.
Keep the exact Python/platform marker environment with the resolved inventory.

The `pandas` and `engines` extras exclude Pandas 3.0.3–3.0.6. Their upstream
`ZoneInfo.from_file` regression can ignore the supplied rules and silently alter
historical timestamps; the correction is documented in
[Pandas 3.1.0](https://pandas.pydata.org/pandas-docs/version/3.1.0/whatsnew/v3.1.0.html).
The minimum supported Pandas range remains available on Python 3.10. A changed
resolved profile requires fresh native evidence; previous 3.0.6 receipts retain
their actual version and outcome.

Runtime is deliberately separated from optional engines and ML: base contracts,
models and CLI depend on Pydantic, Typer and tzdata; Arrow and each native engine
are opt-in; ML is opt-in; the benchmark is a separate distribution. Build and
validation tools are development dependencies, not required by a normal core
import. The benchmark's dependency must resolve to the exact core candidate
wheel supplied with its evidence, not another private wheel with the same
version string.

TLS trust is also part of the build and advisory-query environment. The
[Python security notice for the emSign incident](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576)
requires corrected CA bundles and identifies minimum repaired versions including
`certifi>=2026.10.19`, `pip>=26.2.2` and `uv>=0.13.4`. The release locks use
`certifi==2026.10.23`. A standalone tool can embed its own CA bundle, so inspecting
installed Python distributions alone does not cover `uv` or other native tools.
Do not disable certificate verification to work around a download failure.

Use a maintained Python security patch release and an updated operating-system
trust store. The same notice recommends Python 3.13.18 (and corrected releases of
other maintained branches) as an additional mitigation independent of CA bundles.
The package's Python compatibility floor is not a claim that an end-of-life
interpreter still receives upstream security fixes. Updating a QA runtime must
not silently replace a consumer's system interpreter or certificate store.

The optional `files` profile adds Pandas/Arrow, openpyxl for XLSX/XLSM, xlrd for
legacy XLS and defusedxml for XML. Imports occur only when a selected operation
needs that reader; no automatic installation occurs. Target conversion additionally
uses the existing `polars` or `duckdb` profile. The exact allowed ranges are in
the [compatibility table](compatibility.md#declared-runtime-dependencies).
`equiframe doctor --extra files` diagnoses installation metadata without reading
user data. File discovery, inference and conversion are documented in
[the file guide](lectura-conversion.md).

The optional [language-R review](r_review.md) uses a user-installed `Rscript`
and base R. It does not add an R package dependency or install a runtime.
R's observed version and the reviewer source hash belong to each returned
review; Python wheel metadata alone cannot identify the external R executable.
Validation of the 26 October source additions and lock updates is reported
separately; lock resolution alone does not establish native or semantic behavior.

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
PY=.venv/bin/python
TOOL=tools/dependency_inventory.py
CORE=.
BENCH=packages/equiframe-benchmark

$PY $TOOL generate --package "$CORE" \
  --artifact "$CORE/dist/equiframe-0.12.4-py3-none-any.whl" \
  --artifact "$CORE/dist/equiframe-0.12.4.tar.gz" \
  --output evidence/dependencies/core

$PY $TOOL generate --package "$BENCH" \
  --artifact "$BENCH/dist/equiframe_benchmark-0.12.4-py3-none-any.whl" \
  --artifact "$BENCH/dist/equiframe_benchmark-0.12.4.tar.gz" \
  --environment-python "$BENCH/.venv/bin/python" \
  --local-artifact "$CORE/dist/equiframe-0.12.4-py3-none-any.whl" \
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
Declared `License-File` members, including names such as `AUTHORS` and legacy
`mit.LICENSE`, are collected alongside conventional `LICENSE`, `LICENCE`, copying
and notice files inside the distribution metadata boundary. Paths outside that
boundary are not followed. Missing files or declarations still require review;
collecting a file does not establish a compatible license.
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
  --artifact "$CORE/dist/equiframe-0.12.4-py3-none-any.whl" \
  --artifact "$CORE/dist/equiframe-0.12.4.tar.gz" \
  --inventory evidence/dependencies/core/inventory.json \
  --advisories evidence/dependencies/core-advisories/advisories.json \
  --max-age-hours 24 --require-clean

$PY $TOOL verify --package "$BENCH" \
  --artifact "$BENCH/dist/equiframe_benchmark-0.12.4-py3-none-any.whl" \
  --artifact "$BENCH/dist/equiframe_benchmark-0.12.4.tar.gz" \
  --environment-python "$BENCH/.venv/bin/python" \
  --local-artifact "$CORE/dist/equiframe-0.12.4-py3-none-any.whl" \
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

The optional legacy XLS reader `xlrd==2.0.2` illustrates why a generic `BSD`
metadata label is insufficient: its [license text](https://github.com/python-excel/xlrd/blob/2.0.2/LICENSE)
contains both a later three-clause notice and an earlier notice with advertising
and retained-acknowledgement conditions. Preserve both when redistributing that
dependency and retain the required acknowledgement:

> This product includes software developed by David Giffin <david@giffin.org>.

SciPy binary notices separately identify OpenBLAS/LAPACK, the GCC runtime with
its runtime exception, and libquadmath under their respective terms. Docutils
identifies its public-domain files and separately licensed exceptions. These
notices must not be replaced by EquiFrame's MIT license or collapsed into a
guessed single SPDX expression. Normal dependency installation retains upstream
notices; repackaging dependencies requires a separate review of the actual files.

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

The inventory and advisory scan are separate from source review and the partial
historical STEP9 assessment. They do not prove publisher identity, grant rights
over dependencies or establish that the software is secure. EquiFrame's own
license and bundled notices do not replace third-party redistribution conditions.
Publication follows the [release decisions and gates](releasing.md), including
resolution of real findings and explicit treatment of unknown coverage. Bind the
completed checks to the final four artifact hashes; do not transfer acceptance
from an earlier wheel, sdist, dependency resolution or source snapshot.

Standards and provider documentation:
[CycloneDX 1.6](https://cyclonedx.org/docs/1.6/json/),
[PyPI JSON API](https://docs.pypi.org/api/json/),
[OSV query API](https://google.github.io/osv.dev/api/)
