# Security boundaries and responsible use

This Alpha candidate is a local Python library, not a sandbox or a hosted service.
Public release is blocked. The STEP9 security assessment is **incomplete**:
the managed security-scan execution tools were unavailable, and the separate
manual review stopped before completion. There is no completed certification,
universal safety claim or assertion that the code has no vulnerabilities.
Dependency advisory results, when available, describe a dated snapshot and the
exact resolved versions; they do not replace a source review.

## Working threat model (owner review pending)

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
| Resources | Core budgets are cooperative and scoped to their operation. Capture, parsing, native allocation and custom callbacks may allocate or run before a checkpoint. Use OS/process/container quotas for hostile workloads; constrain disk, CPU, memory, threads and networking |
| Dependencies and build tools | Verify exact wheel/sdist hashes and the selected dependency profile. Keep build/dev tooling separate from runtime. Installation/building itself executes trusted tooling; an SBOM is an inventory, not a trust grant |

Read-only SQL is not a security perimeter. Explicit DuckDB capture disables
extension autoload/autoinstall on its private connection; a caller-owned
connection must already meet the declared conditions. These controls do not
make arbitrary third-party queries safe. Consistency across external files or
systems is not established merely by opening a database transaction.

## Local operation, networking and data disclosure

The product's default integration is local; this candidate does not configure a
telemetry endpoint, background upload service or analytics opt-in. A complete
source-security/egress review remains pending, so this is not a verified promise
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

The stopped review observed a special-file availability risk in a bundle reader;
that path has not been certified fixed. A capture-budget observation also needs
contract triage; per-comparison limits must not be represented as global quotas.
No new source-hardening claim is based on that unfinished assessment. Avoid
untrusted/special-file inputs until the affected paths have an authorized,
completed review and regression tests.

There is no assigned security-response owner, verified private reporting channel
or response-time SLA yet. These are release blockers, not implied commitments by
the package author. For this private candidate, contact the person who supplied
it through an already verified private channel and provide only a sanitized
reproducer, exact commit/artifact hash, dependency versions and impact. Do not
post credentials, personal data or a sensitive exploit in a public issue.

[Release and withdrawal process](releasing.md) · [Dependency evidence](dependencies.md)

## Consolidation review boundary, 2026-10-06

This consolidation does **not** resume the stopped source-security assessment,
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
Release and untrusted-input adoption remain blocked on the unresolved assessment
and owner decisions; a private branch is not a security certification.
