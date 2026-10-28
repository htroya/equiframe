# Three reproducible installed recipes

This standalone guide accompanies the verified private kit. The installed
wheel also includes an English handbook, available through
`importlib.resources.files("equiframe").joinpath("docs/index.md")`.

These recipes use the private EquiFrame **0.12.0a10** first-use kit and **the Python minor selected in the kit manifest (3.10-3.13)**. The kit contains the exact wheel, three recipe scripts and their
pytest fixture, pinned dependencies with hashes, an integrity verifier and
English guides. No checkout, real dataset, credential, remote SQL, notebook or
service is required. Inputs are small synthetic fixtures defined in the scripts.

The target of a first useful diagnosis within five minutes is **not yet validated
by human observation**. Automated independent artifact checks are technical
evidence, not a substitute for that observation. Preserve the kit's unfilled
`OBSERVATION.md` and record a real attempt separately if you participate.

## 1. Obtain, verify and install the kit

Obtain the candidate kit through the authorized private channel. Compare its
archive SHA-256 with the separately supplied trusted receipt **before extraction**.
Extract it into a new directory named `kit`, outside the repository, and open a
terminal there. Keep the kit unchanged: environments, outputs and completed
observation records belong in sibling directories. The internal manifest detects
byte changes; it does not authenticate the sender.

The commands below show 3.12. If the manifest selects 3.10, 3.11 or 3.13,
replace each python3.12 command with that exact interpreter; the supplied
requirements.lock must belong to that same minor.

```bash
python3.12 --version
python3.12 verify_kit.py
python3.12 -m venv ../first-use-env
```

On Windows use `py -3.12` in place of `python3.12`. Activate the environment:

- Linux/macOS shell: `source ../first-use-env/bin/activate`
- PowerShell: `..\first-use-env\Scripts\Activate.ps1`. If local policy prevents
  activation, use `..\first-use-env\Scripts\python.exe` directly; do not change
  security policy

These are platform command conventions, not new platform acceptance results.
Install into the new environment:

```bash
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
python -m pip install --no-index wheels/equiframe-0.12.0a10-py3-none-any.whl
python -m pip check
python -I -c "import equiframe, sys; print(sys.version); print(equiframe.__file__)"
```

The **first command deliberately downloads dependencies from your configured pip
index**; it does not download datasets. Pins and hashes come from the candidate's
`uv.lock`. The second command installs the verified local EquiFrame wheel with normal
dependency validation against the already pinned environment.
The import must resolve to the environment, not the source checkout. Do not add
`PYTHONPATH` or use an editable install.

For offline installation, first obtain a reviewed wheelhouse containing those
same pinned dependency wheels and add
`--no-index --find-links /absolute/path/wheelhouse` to the first install command.
Dependency binaries are not inside the kit. Do not remove hashes or force other
versions to bypass a failure. If your platform has no compatible wheel, record
the blocker; this guide does not certify a new platform matrix.

A maintainer with the source distribution and built wheel can prepare a kit with
`python tools/build_first_use_kit.py --python-minor 3.12 --output /absolute/path/new-kit` from the
core package directory. That builder does not resolve new dependencies or
publish a package. Consumers continue using only the resulting kit.

## 2. Diagnose a pandas refactor

Create a sibling working directory and run all commands below from there:

```bash
python -c "from pathlib import Path; Path('../first-use-work').mkdir()"
cd ../first-use-work
python -I ../kit/refactor_comparison.py --output refactor-different
```

**Expected process exit: 1**, a deliberate regression. The report identifies:

- `different`, complete evaluation and coverage, strategy `key`
- Key `id="B"`, column `total_cents`
- Candidate `integer(2001)` versus expected `integer(2000)`, both `int64`
- Exact numeric policy, declared unit `USD_cent`, one modified row

Open `refactor-different/report/report.html` or read `report.txt`. The inspectable
contract is `refactor-different/contract.json`. The vectorized refactor added one
cent. Reordered rows are allowed because the contract ignores order and verifies
a unique key. The reference preserves the earlier implementation and is also
checked against three literal fixture values. This does not make pandas or a
historical output a universal oracle.

Run the correction **without changing the policy**:

```bash
python -I ../kit/refactor_comparison.py --case equivalent --output refactor-equivalent
```

Expected exit 0, `equivalent`. Try the no-key extension:

```bash
python -I ../kit/refactor_comparison.py --without-key --output refactor-bag
python -I ../kit/refactor_comparison.py --without-key --case equivalent --output refactor-bag-ok
```

Expected exits 1 and 0. Without row identity, EquiFrame compares multisets and
preserves occurrences; it reports excess rows on each side rather than claiming
which business row changed. Do not deduplicate to make it pass. This fixture's
integers are small: it does not promise overflow-free int64 arithmetic for
arbitrary inputs, fractional currency handling or currency conversion.

This script displays only its known synthetic values. `--redacted` hides values
and metadata in the report. Raw captures are temporary unless you supply
`--work-dir private-refactor`, which retains private snapshots and full differences.
Keep that directory separate from reports and do not upload it automatically.
The attached contract still contains synthetic names/units in redacted mode;
share only `report/` for the minimized view.

## 3. Validate a bounded pandas → DuckDB migration

```bash
python -I ../kit/migrate_duckdb_recipe.py --case equivalent --output migration-ok
python -I ../kit/migrate_duckdb_recipe.py --case different --output migration-regression
python -I ../kit/migrate_duckdb_recipe.py --case not_evaluable --output migration-limited
```

Expected exits **0, 1 and 3**. The script uses the real `ef.migrate` API with a
`Scan` + `Aggregate` relational plan. It does not translate arbitrary Python or
SQL. Both engines execute their native implementation over the same snapshot;
the literal expected output is captured separately. Decimal type/scale, currency,
NULL amounts, empty-sum behavior and counts are declared before execution.

The negative case deliberately changes empty-sum semantics. The engines may
therefore be `equivalent` to each other while `verification="divergent"` against
the unchanged expected output. This is a shared error, not a fabricated
cross-engine discrepancy.

Each output contains `source-target/`, `source-expected/` and `target-expected/`.
Each directory retains `report.json`, `report.txt`, `report.html` and
`evidence-manifest.json`, verified before publication is announced. The limited
case permits one row per comparison; partial counts are not final totals. Do not
change the expected output to resolve an evaluation limit.

Use `--show-synthetic-values` to inspect the literal expected output and both
captured results. Expected values are EUR: NULL total/2 rows, JPY: 0.00/1 row and
USD: exact Decimal 1000000000000000.03/3 rows. The negative case changes only EUR
to 0.00 in both engines. Each comparison against the expected output retains one
difference. Values are not printed by default and reports are redacted.

`--work-dir private-migration` retains inputs, expected output, native outputs,
configuration and evidence instead of deleting temporary originals. Never mix
it with the shareable report directory. The DuckDB adapter owns an in-memory
connection per execution, uses one thread, an explicit 128 MB engine memory
limit and UTC session setting, then materializes and closes before returning.
The script rereads and verifies `read_migration` after that return.

The recipe does not open a shared DuckDB file, download extensions or execute
external SQL. The plan has no temporal values: UTC does not prove unsupported
date operations. Budgets remain cooperative, not a hard process-RSS quota.
Passing an actual `DuckDBPyRelation` directly to `diff` authorizes bounded native
materialization; SQL strings and connections are not accepted as data inputs.
Explicit capture or an adapter remains available when session ownership and SQL
execution controls are required. The example does not expand the IR or prove all
possible inputs valid.

## 4. Keep evidence before failing pytest or CI

```bash
python -I ../kit/assertion_ci.py --case equivalent --output ci-ok
python -I ../kit/assertion_ci.py --case different --output ci-different
python -I ../kit/assertion_ci.py --case not_evaluable --output ci-limited
```

Expected exits **0, 1 and 3**. The script exports and verifies a report **before**
calling `ef.assert_equivalent`. Failures retain JSON/text/HTML diagnostics and
`evidence-manifest.json`. `assert result` and `if result` raise `TypeError` in all
three comparison states.

Run the real pytest fixture with a new output location for each selected case:

```bash
python -I -B -m pytest -q -o addopts= -p no:cacheprovider ../kit/test_assertion_recipe.py -k equivalent
python -I -B -m pytest -q -o addopts= -p no:cacheprovider ../kit/test_assertion_recipe.py -k different
python -I -B -m pytest -q -o addopts= -p no:cacheprovider ../kit/test_assertion_recipe.py -k not_evaluable
```

Pytest exits **0, 1 and 1** respectively. The final two are deliberately failing
tests, not `xfail`. Reports are under `ci-reports/<case>/`. Repeat from another
clean working directory that still points to the kit; never overwrite evidence.
`-B` prevents bytecode being created alongside the fixture. In your real pipeline,
provide your actual candidate/reference pair rather than a synthetic case
selector masquerading as validation.

Before uploading a report directory, verify the closed inventory with the
provided script:

```bash
python -I -c "import runpy; from pathlib import Path; recipe = runpy.run_path('../kit/assertion_ci.py'); recipe['verify_upload_directory'](Path('ci-different'))"
```

Run this check even if the test fails (`always()` or your CI equivalent). Upload
only the four verified report files, and preserve the test's nonzero exit status.
If publication or manifest verification fails, do not publish a success artifact.
Do not upload `--work-dir`, environments, snapshots, checkout files or raw JSONL.
This recipe produces a real local artifact; it does not claim a remote CI job ran.

## 5. Change a baseline or contract deliberately

There is no automatic "accept all" or reference-update operation. Inspect types,
values, keys, coverage and policy; fix an erroneous candidate. If a business
requirement genuinely changed:

1. Preserve the failed report, prior reference and their hashes
2. Record the precise change, rationale, responsible person and review
3. Create a new contract revision before comparison, changing only the approved
   policy. Generate/review a new expected output independently; never blindly
   copy the failed candidate
4. Test success, a real difference, an invalid expected result and interruption
5. Version the approved baseline and contract; review the change in a PR

`ef.read_diff_contract(result)` returns the inspectable declaration.
`DiffContract.model_validate_json(...)` rereads a saved declaration, and
`ef.diff(candidate, expected, contract=declaration)` reuses it exactly. Neither a
baseline change nor a new tolerance should be silently learned from a failure.
The recipes do not modify your external baselines.

## Troubleshooting and recording the attempt

Use Python 3.12, a clean environment, unchanged pins and fresh directories. Check
`pip check` and the import location. Exit 1 is expected in deliberate negative
examples; exit 3 means the requested judgment was not established; exit 2 denotes
invalid configuration/execution/publication in these scripts. Missing permissions,
disk space or a finalized report never mean equivalence. Do not publish tracebacks
containing environment variables or real data.

Keep `kit` intact and recheck it with `python ../kit/verify_kit.py`. Save a completed
copy of `OBSERVATION.md` in the work directory. Record installation time separately,
include failed attempts and help received, and distinguish engine agreement from
correctness against a reference. [Interpretation](INTERPRETATION.md) explains the guarantees and failures;
[observation record](OBSERVATION.md) remains pending until a real person completes it.

## Interpreter-specific candidate kits

The a8 builder can select Python 3.10, 3.11, 3.12 or 3.13. Read the received
manifest's Python field and use that interpreter explicitly to create the venv.
The kit's requirements.lock is generated for that minor; never reuse a 3.12
closure or platform-specific binary dependencies for another cell. The source
contains separately named closures for the other minors. Kit creation is not
a proof that installation or the human first-use exercise passed.
