# Synthetic A12 metadata option cases

`catalog-a12.json` is trusted test data with explicit inputs, literal expectations
and exact obligation IDs. `manifest.json` freezes its SHA-256 and candidate.
The 191 seeds are synthetic constructor inputs from existing tests/fixtures and
manually authored generic examples. Discovery and preparation do not earn passes.
No real corpus, credentials, executable callback or engine output is included.

Every case checks JSON field conservation, an explicitly declared default, required
omission, or a wrong JSON type rejected at that field. This tests the public
metadata contract. It does not show that an option has the intended effect in a
native engine, profile fit, detector, workflow or benchmark experiment. Existing
scientific formats and fixtures are untouched.

Defaults which require another cross-field context remain unlinked. Unbounded
types with no independent wrong-type expectation remain unlinked too. Finite
values absent from the selected input, numeric/string boundaries, collection
members and option interactions are not silently credited. The installed audit
retains all 8,383 obligations in its denominator.

Several inventoried obligations describe overlapping contracts, for example
invalid input and the wrong-type class. One explicit rejection can prove both;
4,296 covered rows are **3,443 distinct cases**, not 4,296 independent tests.
Windows, Linux and optimized Python repeats do not add rows to the numerator.

Changes to these inputs/expectations require review of the declared contract,
preservation of unsuccessful attempts and a new identified catalog. Never change
the denominator, relax a contract or generate expectations from fresh outputs
to reach a desired percentage. Run the standalone installed audit as described
in the repository's `docs/OPTION_TRACEABILITY_20261010.md`.

A13 corrects detector producer identity. This original A12 catalog remains byte
identical: its `DetectorVersions.equiframe.default` case must detect the deliberate
default change from A11 to A13. The current regression suite asserts that historical
drift as a failure of the old expectation; it does not count the old receipt as
passing A13 coverage. A current installed inventory/catalog must bind new artifact
hashes and state the new default explicitly before any new percentage is credited.
