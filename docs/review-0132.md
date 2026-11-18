# Readiness review and 0.13.2 action plan

## Assessment of published 0.13.1

Publishing 0.13.1 was defensible for its documented, bounded library interfaces:
identified artifacts passed source and installed tests on Windows and Linux,
independent artifact review and downloaded-consumer checks. This establishes
software checks for those artifacts, not scientific accuracy, universal input
support, production certification or completion of the warehouse and portal.

The published tag and the later integrated `main` are different trees. Public
`main` at `cdd4bf53f48ee8cc267fa32acea30c377bbcfc56` has 284 Ruff findings,
1,969 strict mypy errors in 70 files, and failures in reintroduced historical
tests, including tests for intentionally removed Actions workflows. These
observations do not invalidate checks of the different tagged tree; they show
that integrated main was not release ready.

## Changes and acceptance

| Finding | Action | Required evidence |
| --- | --- | --- |
| Historical tools/tests and a duplicate Alpha core became active | Preserve original bytes under `archive/research-a14`; maintain one root core | Hash inventory; root Ruff/mypy and complete current suites |
| Main could distribute obsolete development material | Exclude archives and check repository layout | Duplicate/workflow regressions; inspect wheel/sdist and rebuild |
| Global Production/Stable metadata overstates maturity | Classify the package as Beta, preserving all stable API/format commitments | Wheel metadata and compatibility checks |
| Missing-extra error still says public PyPI is unavailable | Provide the public installation command and retain the typed error/cause | Missing-extra consumer/error checks |
| Current and historical release statements are mixed | Link this review and clarify current candidate versus past publication | README consumers and documentation checks |

The patch preserves comparison formulas, grouping, native IR, detectors, labels
and scientific protocols. It adds no domain fields and does not modify Jhair's
warehouse or Jose's portal/client.

## Manual sequence

1. Apply narrow changes and run targeted regressions and layout checks.
2. Freeze one reviewed commit and new immutable tag; preserve past releases.
3. Run both packages' complete candidate controls on Windows and the authorized
   Linux VM: locked dependencies, Ruff, strict mypy, assets, full source tests,
   build, strict Twine and installed consumers/tests/rebuilds.
4. Review exact artifacts, licenses, dependency advisories and source changes.
   Missing or failed evidence blocks publication; skips retain their actual scope.
5. Push and integrate manually, without GitHub Actions.
6. Upload the four identified files to TestPyPI with an ephemeral credential,
   download them, verify hashes and test a clean consumer. Promote those same
   bytes to PyPI after success, then revoke credentials.

Final release records and official inventories establish completed steps.
This plan is not itself a passing test or publication receipt.
