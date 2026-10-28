# Security status and reporting

Hernán Troya (`htroya`) accepted responsibility for EquiFrame maintenance,
releases and security on 2026-10-27. No response-time SLA or staffed on-call
coverage is promised. The working threat model, current review scope and safe-use
limits are in the [packaged security guide](docs/security.md).
Historical STEP9 assessments retain their original scope and findings.

Report sensitive vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/htroya/equiframe/security/advisories/new).
This private intake is enabled in the public documentation repository.
Use [public issues](https://github.com/htroya/equiframe/issues) for ordinary
bugs without confidential information.

Include the package version, interpreter and engine versions, impact, exact
artifact hash when available, and a minimal sanitized reproducer. Never post
secrets, credentials, personal data or entire private evidence directories in a
public issue. Security findings and dependency advisories must be reviewed for
the exact release; this policy does not certify the absence of vulnerabilities.

The [release process](docs/releasing.md) separates fixing,
release approval, withdrawal/yanking and isolated rollback. Do not run untrusted
SQL, callbacks or plugins; a read-only query or a valid report hash is not a
sandbox. Keep hostile inputs out of production processes and use host-level
resource and networking restrictions when appropriate.

Before a release, run the local secret, static-analysis and dependency checks
described in the [security guide](docs/security.md#maintainer-checks).
Retain each scanner's actual exit code and review every finding. A failed or
unavailable check is not a clean result. Do not upload source or candidate secrets
to a scanning service or enable credential verification without separate approval.

Keep publishing credentials out of source, command arguments, logs and persistent
environment files. Publishing is manual for the current release task: use only
the approved files and a locally handled token for that upload. Do not store it
in GitHub, an environment file, a command line or a receipt. Revoke it after use.
Git ignore rules prevent accidental additions; they do not remove already tracked
secrets. Revoke a leaked credential and assess its exposure before arranging any
history cleanup.
