# Documentation maintenance

[Portal](README.md) · [Contributing](../CONTRIBUTING.md) · [DOC-PRO-20-v1](DOCUMENTATION_PLAN_20261010.md)

## Source of truth and readers

The root portal separates user guidance, developer instructions, research design
and dated engineering receipts. The core's English handbook remains the user
reference carried in each identified distribution. Repository-level Spanish
guides explain team integration and evidence without becoming runtime dependencies.
Keep architecture/API/integration current headers consistent with both package
metadata files. Keep historical sections explicitly dated/versioned.

API names/fields come from the identified package's exports and stability register.
Metadata admission and a platform's actual passed receipt are different claims.
Contract revision, schema version, algorithm identity and package version must
not be used interchangeably. Do not promote draft experimental requirements to
accepted scientific decisions. Owner/component boundaries remain in
[TEAM_INTEGRATION](TEAM_INTEGRATION.md).

## Change procedure

1. Locate the canonical page; update it before adding another summary. Link the
   portal to a useful task and name the expected outcome and limits.
2. If runtime/API meaning changes, update the applicable handbook, changelog,
   schemas, compatibility and tests in the same reviewed change. Synthetic
   examples must preserve types/keys/nulls/multiplicity and fail explicitly.
3. Keep receipt hashes, original results and reviewed expected outputs immutable.
   A new artifact or assessment gets a new receipt/cut. Never apply A11/A12
   scores automatically to A13. Distinguish unique cases from repeated attempts.
4. Add new current pages to the scope inventory; register only complete, trusted,
   reproducible Python examples. Snippets illustrating unsafe/partial patterns
   must be labelled and are not executed automatically.
5. Run the checks below manually. Preserve new output paths and failures, correct
   the cause, and repeat only affected checks. Record code/document/wheel hashes.
6. Review the diff and publish only within authorized private repository scope.
   A manual check, push or PR does not run Actions or approve PyPI/public docs.

## Manual checks

Run from the repository root with supported Python 3.10–3.13. Supply a **new**
existing output parent outside the checkout, such as `../documentation-checks`.
On Windows replace `python` with your selected absolute interpreter or `py -3.12`.

```text
python tools/check_documentation.py --output ../documentation-checks/navigation.json
python -m unittest discover -s tests -p test_documentation_tools.py -v
```

The [scope manifest](../tools/documentation_scope.json) covers the root portal,
current architecture/API/integration, contribution/assessment pages and the
complete source handbook. The checker inventories physical UTF-8 bytes, local
inline/reference links, heading anchors and explicit current-version statements.
Links to dated reports must resolve; the historical reports themselves are not
traversed or rewritten. HTTP/HTTPS/mailto targets are listed without fetching.
This is a check of the declared Markdown syntax, not a general rendering engine:
HTML hrefs, generated-site routing, remote availability and visual accessibility
are outside its claims. Add targeted fixtures if new Markdown syntax is adopted.

For the [four selected examples](../tools/documentation_examples.json), first
audit and install the exact privately supplied wheel with `arrow` into a clean
consumer environment outside the checkout, following the
[private install guide](../packages/equiframe/docs/installed-private.md).
Run `pip check`. Then supply the trusted SHA-256 and absolute paths:

```text
python tools/run_documentation_examples.py --python /absolute/consumer-env/python --wheel /absolute/equiframe-0.12.0a13-py3-none-any.whl --sha256 TRUSTED_64_HEX_DIGEST --work-dir /absolute/new-example-results
```

Paths and `TRUSTED_64_HEX_DIGEST` are placeholders to replace, not literal commands
to paste unchanged. The checker audits the wheel using the existing offline
auditor, rejects editable/in-checkout SDK imports, compares installed package
payload bytes with that wheel, extracts the exact registered Python fences, and
runs each in fresh directories under normal Python and `-O`, both with
`-X utf8` and UTF-8 capture. This makes redirected Unicode handbook output
portable on Windows; for manual resource printing use `python -I -X utf8` too.
Explicit exit/marker
checks record failures even when Python assertions are optimized away. It never
runs arbitrary blocks, installs dependencies, or requests network access.
The trusted registered examples execute real Python; this tool is not a sandbox.

## Receipts and artifact changes

Root-only documentation and these tools do not modify a delivered wheel. Changes
inside package READMEs/handbook resources do change distribution bytes: rebuild,
audit and identify new artifacts before claiming that updated text is installed.
Do not overwrite a historical hash or call a fresh build identical without
checking it. CRLF/LF also affects physical document/distribution hashes; receipts
record the environment. Extracted examples use LF for their code hash.

Keep private runs, raw evidence, environments and binary artifacts outside Git.
An aggregate repository report may include safe counts, hashes, status and limits;
raw stdout/stderr and machine paths stay in a private evidence archive. Retain
the identified artifacts, then remove owned temporary environments after validation.

## Open external reviews

D19 requires a real reader other than the author to follow the written route and
record difficulties with consent. Automated execution and an independent consumer
repository do not impersonate that reader. D20 requires owner-approved rights and
an actually accessible public documentation channel for this distribution.
Neither is completed by writing a protocol, reusing another project's name, or
declaring a site public. Both remain in the score's denominator.
