# Security boundaries and responsible use

EquiFrame is a local Python library, not a sandbox or a hosted service.
The `0.12.2` release must satisfy the [release gates](releasing.md) before
publication; a version string alone does not establish acceptance. The historical
STEP9 assessment remains **incomplete** and is not relabelled by a later release.
Ordinary source review, dependency advisories and security regressions have their
own explicit scope. There is no completed security certification, universal
safety claim or assertion that the code has no vulnerabilities.
Dependency advisory results, when available, describe a dated snapshot and the
exact resolved versions; they do not replace a source review.

## Threat model and operating assumptions

Assets include source datasets, SQL and parameters, local paths, captured rows,
contracts, models, output reports, credentials in the host process and available
CPU, memory and disk. A consumer may receive damaged or malicious files from a
third party. A local user who can rewrite the evidence directory while it is
being checked is a stronger adversary than an immutable downloaded artifact.
Do not place trusted evidence in a directory writable by untrusted users.

| Boundary | Intended controls and residual responsibility |
|---|---|
| Contracts and JSON reports | Strict versioned data models, closed format inventories and validation reject many malformed inputs. Use only supported readers; unknown versions fail closed. Format validation does not guarantee a hard CPU/memory bound for every reader |
| Evidence and bundles | Hashes, sizes and closed inventories detect inconsistency. Hashes do not authenticate the producer or prove semantic correctness. Fix the expected hash through a trusted channel; inspect in an isolated working directory |
| HTML/text/notebook output | Common report views escape text and minimize values, names and paths by default. An explicit disclosure option can expose sensitive information. Inspect the chosen report before sharing; raw evidence is separate |
| Local paths and files | Keep controlled, private work/output roots. A filename is not proof of a regular file; device files, pipes, links, races and hostile mounts require host-level controls. Do not feed special files to readers |
| SQL and callbacks | Execute only trusted SQL, callbacks, adapters and compilers. Parameters protect value binding; they do not make SQL safe to run. Queries can read local files, access networks or invoke engine capabilities. JSON readers do not authorize executing referenced code |
| Plugins and models | Registration is explicit. Do not install or execute unknown plugins or deserialize executable Python objects. Detector persistence uses declared data formats; never substitute arbitrary pickle/joblib input |
| Language-R review | Only the shipped reviewer and a trusted, caller-selected `Rscript` executable may run. Review uses a private temporary directory and a subprocess timeout. It does not sandbox an arbitrary R program or make a semantic verdict a security verdict |
| Resources | Core budgets are cooperative and scoped to their operation. Capture, parsing, native allocation and custom callbacks may allocate or run before a checkpoint. Use OS/process/container quotas for hostile workloads; constrain disk, CPU, memory, threads and networking |
| Dependencies and build tools | Verify exact wheel/sdist hashes and the selected dependency profile. Keep build/dev tooling separate from runtime. Installation/building itself executes trusted tooling; an SBOM is an inventory, not a trust grant |

Read-only SQL is not a security perimeter. Explicit DuckDB capture disables
extension autoload/autoinstall on its private connection; a caller-owned
connection must already meet the declared conditions. These controls do not
make arbitrary third-party queries safe. Consistency across external files or
systems is not established merely by opening a database transaction.

## Local operation, networking and data disclosure

The product's default integration is local; it does not configure a telemetry
endpoint, background upload service or analytics opt-in. This is not a promise
of network isolation. Downloading dependencies, querying advisory services,
injected clients, user callbacks, database queries and external engine features
can use the network. Those are separate from rendering a stored report.

Use an isolated environment with networking denied when you require offline
processing, and provision its dependencies beforehand. Do not put credentials
in contracts, SQL text, data values, filenames, command arguments or diagnostics.
Error causes and third-party exception objects can retain details even when the
normal report view is minimized. Do not upload complete runs as bug reports.

Snapshot, spill, SQLite and raw evidence files can contain unredacted values.
A minimized HTML report does not sanitize these files. Use restrictive directory
permissions, encrypted storage if required, and an explicit retention policy.
Deleting a file is not a secure-erasure guarantee. Hashing low-entropy personal
values is not anonymization. Choose sharing and retention separately from the
comparison contract.

## Known review limits and reporting

The historical review observed a special-file availability risk in a bundle reader.
The A14 development follow-up reproduced blocking on a POSIX FIFO and added
regular-file checks to the bundle, JSON, event and file-description readers.
Capture budgets still require operation-specific interpretation; per-comparison
limits must not be represented as global quotas. The follow-up does not complete
or retroactively amend the historical assessment.

Hernán Troya (`htroya`) is responsible for maintenance, releases and security
response. There is no response-time SLA. Report suspected vulnerabilities through
the [private GitHub reporting channel](https://github.com/htroya/equiframe/security/advisories/new)
of the project's public repository when that route is available. A GitHub
account is required. For each release, the maintainer must enable this route
and the public issue channel and verify their availability. Use
[public issues](https://github.com/htroya/equiframe/issues) for non-sensitive
bugs and questions. If private intake cannot be verified, retain sensitive
details locally until confidential intake can be arranged.

Provide a sanitized reproducer, exact version and artifact hash, dependency and
runtime versions, expected behaviour and impact. Do not post credentials,
personal datasets or a sensitive exploit in a public issue. Reporting a concern
does not authorize accessing another user's data or running destructive tests.

[Release and withdrawal process](releasing.md) · [Dependency evidence](dependencies.md)

## Maintainer checks

Run security tools in a separate, disposable tooling environment. Pin the tool
versions, check downloaded hashes, fix the source commit and record the source
inventory. Scan the current tracked tree and any proposed additions, including
tests and documentation; Git history needs its own explicit scan when historical
exposure is in scope. A current-tree scan does not inspect every historical blob.
Keep raw reports local and private: scanner output may repeat the secret it found.
Share only sanitized locations, finding identifiers, dispositions and exit codes.
Delete temporary snapshots and reports after review. Do not overwrite dated
evidence or transfer a result to different release bytes.

For TruffleHog, use a local filesystem snapshot with `--no-verification`,
`--no-update`, `--no-ignore-tag`, `--fail`, `--fail-on-scan-errors` and JSON output.
Include verified, unknown, unverified and filtered-unverified result classes.
Disabling verification prevents checking candidate credentials against providers;
it does not establish whether a detected credential is valid. Exit 183 denotes
findings and must remain visible even when review determines they are false
positives. Exit 1 or a missing completion record must be investigated as a failed
scan. Review findings by their exact location and source context; do not suppress
all hexadecimal strings, URL credentials or a detector globally.

Run Bandit against both packages' `src`, `tools` and `examples` directories with
all rules, `--ignore-nosec` and JSON output. Preserve nonzero exits and collection
errors. Review SQL construction, subprocess arguments and inherited environment,
assertions and parser boundaries individually. A name-based warning can confuse
EquiFrame's local `load_dataset` with another project's API; prove the imported
call target before dismissing it. A subprocess argument list prevents shell
interpolation but still requires a trusted executable and trusted operations.
Do not pass publication credentials to build, test or package-execution jobs.

`tools/security_requirements.py` exports every public name/version pair from the
two locks, including alternative Python/platform pins. It puts alternative
versions of one project in separate files because pip-audit rejects duplicate
names in one input. From the repository root, export to a new temporary directory:

```bash
python tools/security_requirements.py \
  --lock uv.lock \
  --lock packages/equiframe-benchmark/uv.lock \
  --output /absolute/new/temporary/audit-requirements
```

For **each** exported requirements file, run the pinned `pip-audit` with
`--no-deps --disable-pip --strict --format json --progress-spinner off -r FILE`.
This sends public dependency names and versions to the selected advisory service;
it neither installs the project nor uploads its source. Preserve exits, all
advisories and skipped/failed collections. Also review admitted lower bounds and
new build dependencies: a clean resolved lock does not certify every version
allowed by a range. Do not use `--fix`, ignore lists or a zero-exit option to
manufacture a passing release.

Check exact distribution names and normalized spelling against the official
project documentation and PyPI metadata. Use one reviewed index, pinned hashes
and the exact expected package names. Similar spelling, a public metadata page or
a 404 does not authenticate a publisher, reserve a name or prove that a package
is benign. Never publish placeholder projects to reserve lookalike names.

The current release task uses manual publication, without GitHub Actions or
Trusted Publisher configuration. Use a locally handled publication token only
after the exact release gates pass. Limit its lifetime by revoking it after use.
Never put it in a command
argument, repository, persistent environment file, workflow secret or receipt;
use a hidden interactive prompt or an approved local secret store. Revoke it
after the authorized upload. Build and inspect without publication credentials,
then upload only the four approved files to the explicit index endpoint. TestPyPI
and PyPI have separate accounts. Reconcile every accepted filename/hash and test
the downloaded artifacts before promoting identical bytes to production. A
publication credential does not establish software safety or human acceptance.

Primary references: [TruffleHog usage](https://github.com/trufflesecurity/trufflehog),
[Bandit CLI](https://bandit.readthedocs.io/en/latest/man/bandit.html),
[pip-audit](https://github.com/pypa/pip-audit),
[PyPI account security](https://docs.pypi.org/your-account/two-factor-authentication/)
and [PyPA name normalization](https://packaging.python.org/en/latest/specifications/name-normalization/).

## Consolidation review boundary, 2026-10-06

The following paragraphs describe the historical 2026-10-06 consolidation.
That consolidation did **not** resume the stopped source-security assessment,
through a specialized scanner or through an equivalent manual audit. That is a
real unresolved coverage boundary, distinct from a temporarily missing tool.
The prior special-file observation and capture-budget contract question remain
open; no new reproduction, severity confirmation or remediation is claimed for
them. Ordinary functional tests, compatibility checks and documented resource
measurements do not close the security assessment.

A separate fresh reading of the official advisory for **CVE-2026-25087** on
2026-10-06 confirms Apache's stated scope: Arrow C++ 15.0.0 through 23.0.0 is
affected and 23.0.1 contains the fix; Python, Ruby and C GLib bindings are excluded
because the affected IPC pre-buffering functionality is not exposed through them.
This qualifies the historical minimum-profile package-version match. It does not
turn an inventory into a clean scan or prove every bundled native component and
EquiFrame usage safe. Sources: [Apache advisory](https://security.apache.org/projects/arrow/)
and [Arrow 23.0.1 release notes](https://arrow.apache.org/blog/2026/02/16/23.0.1-release/).
The dated source receipt is retained with this consolidation's evidence, separately
from earlier advisory snapshots. No dependency version was changed on that basis.

The final artifact-bound offline dependency inventories/SBOMs identify the new
wheel/sdist bytes. Offline regeneration performs no new registry-wide advisory
query and must not be presented as a current comprehensive vulnerability scan.
At that consolidation, release and untrusted-input adoption remained blocked on
the unresolved assessment and owner decisions. Current release decisions follow
the release gates; this historical snapshot is not a security certification.

## A14 secure-development follow-up, 2026-10-13

Stored operational failure summaries and CLI diagnostics use fixed messages.
They do not stringify external exceptions or publish their input values, source
paths or SQL. Optional DEBUG diagnostics contain at most 32 owned frame records
(module, function, line); external frames are anonymous and values, source text
and local variables are excluded. A broken logging handler cannot replace the
operational result. Programmatic validation exceptions and explicitly requested
raw data remain separate; applications must handle them before showing a UI.

EDA cancellation callbacks must be callable and return actual booleans. A failing
callback is not called again during error recovery; incomplete analysis persists
a closed diagnostic code. Unexpected optional-chart failures also remain
explicitly not evaluable, without exposing third-party exception text.

Evidence readers and bundle inventories inspect lexical ancestors before
resolution and reject symlinks, Windows reparse points and non-regular files.
POSIX reads pin directory descriptors and use O_NOFOLLOW/O_NONBLOCK; fallback
hosts check identities around opening. JSON and bundle documents retain their
64 MiB limit, and the bundle pin is checked against the bytes actually parsed.
These cooperative checks are not a filesystem sandbox against hostile mounts
or concurrent owners. Bundle copies still require a controlled, immutable source.

Contract and generic profile/detector document files also use protected regular
reads with a 64 MiB limit. Generic document readers retain OS exception classes
and errno for recovery, with fixed messages and no filenames. Relative output
directories retain relative member names in the published inventory.
