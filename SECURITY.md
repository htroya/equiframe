# Security status and reporting

EquiFrame is a private Alpha candidate. Public release is blocked, and its
STEP9 source-security assessment is incomplete. No audit certification or
absence-of-vulnerabilities claim is made. The working threat model and safe-use
limits are in the [packaged English security guide](packages/equiframe/docs/security.md).

A vulnerability-response owner, verified private reporting channel and response
SLA have not been assigned. The repository author field is not an acceptance of
those duties. Before public distribution, the owner must approve responsibilities
and a reporting route, complete the outstanding source review, and review exact
artifact-bound dependency/advisory evidence.

For an authorized private candidate, use the already verified private channel
through which you received it. Report the exact commit/wheel hash, package and
interpreter versions, impact, and a minimal sanitized reproducer. Never post
secrets, credentials, personal data or entire private evidence directories in a
public issue. No particular response deadline is promised.

The [release process](packages/equiframe/docs/releasing.md) separates fixing,
release approval, withdrawal/yanking and isolated rollback. Do not run untrusted
SQL, callbacks or plugins; a read-only query or a valid report hash is not a
sandbox. Keep hostile inputs out of production processes and use host-level
resource and networking restrictions when appropriate.
