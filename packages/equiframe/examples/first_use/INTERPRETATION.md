# Interpret before accepting

## Three states, completeness and evidence

- **equivalent:** complete comparison without differences under the declared
  contract and captured data. It does not establish business correctness,
  independence of the expected output or universal program equivalence
- **different:** complete comparison with differences or contract violations.
  Locate the key/position, column, both values/types, policy and reason
- **not_evaluable:** the required judgment cannot be established. Differences
  already observed may remain. `complete=False` means an incomplete scan, but an
  invalid expected output can cause this state even with `complete=True`

Do not infer success from completeness alone, no displayed examples, no anomaly,
a returned object, a valid report export or exit zero from an integrity reader.
`ef.assert_equivalent` is the gate;
`ef.equivalence_decision(result).accepted` is the explicit decision. Report
evidence has its own acceptance requirements.

## Correct minimum refactor diagnosis

B / total_cents: 2001 versus 2000, 64-bit integers, exact USD-cent policy. The
error is one added cent. Reordering is permitted because the contract ignores
row order and validates a unique key. Relaxing types or tolerance to hide that
cent changes the requirement instead of correcting the refactor.

Without a key there is no row identity: the report retains multiplicity and
shows excess occurrences. It cannot identify which business row changed.

## Distinctions that must not be erased

- A duplicate key is not resolved by taking its first occurrence; identity fails
- The number of diagnostic records is not necessarily the number of rows
- Decimal precision/scale are preserved; integers are not converted to float to
  make outputs agree
- NULL, NaN, empty text and zero are distinct without an explicit policy
- An all-NULL group's sum must follow its declared `empty_sum`; zero can be wrong
  even if both engines return zero
- Significant indices, order and multiplicity require a policy, not implicit
  cleanup. The fixture's trivial RangeIndex is not business identity
- Partial counts are lower bounds, not final totals. Limited examples do not
  limit the scan
- R/M/B/H anomaly signals are separate from equivalence and independent review O

The technical candidate gate runs these recipes, semantic fixtures and installed
tests. Synthetic tests do not replace real data, human review, service/DW
acceptance, platform certification or the scientific study.

## Minimum evidence and retention

All recipe data is synthetic. The refactor displays values to teach diagnosis;
the other two recipes redact by default. A filtered report does not erase
originals. By default, the scripts capture in temporary directories, export the
report and remove those captures on exit. `--work-dir` retains them under your
responsibility.

The report stays readable after originals are removed or the engine closes, but
a minimal view cannot reproduce an entire transformation. Keep CI uploads small
and closed-inventory. Hashes verify consistency, not authorship. Review permission,
names, keys, paths and values before enabling `include_values` or
`include_metadata` on real data. A manifest is not permission to share.

## Understanding check

Explain why B fails, why engine agreement can still fail against the expected
output, why `not_evaluable` is not a pass, and how to retain a report before
failing without uploading private snapshots. Record the answer, observed time
and help received in a separate copy of [OBSERVATION.md](OBSERVATION.md).
