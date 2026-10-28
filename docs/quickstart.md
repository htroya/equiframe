# Quick start

[Handbook](index.md) · [Recipes](recipes.md) · [Semantics](semantics.md)

This guide uses synthetic local data and identified **0.12.2** artifacts.
It works outside a source checkout. The supported range is Python 3.10–3.13;
use the exact interpreter/platform dependency closure reviewed for your artifact.
The first-use builder produces a separate hash lock for the selected minor.
Metadata admission is not a claim of support for every platform. See
[compatibility](compatibility.md).

## 1. Install the artifact you were given

The commands below demonstrate the optional [offline wheelhouse](installed-private.md)
route, with normal pip resolution and a separate hash-locked trial. For registry
installation, use the README after the corresponding [release gates](releasing.md)
have verified ownership and publication. For an offline delivery, obtain:

- `equiframe-0.12.2-py3-none-any.whl`
- A receipt identifying its commit and expected SHA-256, received through a
  channel you trust independently of the artifact
- A wheelhouse containing the reviewed runtime dependency wheels for your
  Python/platform and chosen extra, with their pins, hashes and inventory

A hash checks bytes against a trusted reference; a manifest packaged with the
same untrusted archive cannot authenticate its sender. Check the supplied wheel
against the separate receipt before installing. For example, from its directory:

```bash
python3.12 -c "from pathlib import Path; import hashlib; p=Path('equiframe-0.12.2-py3-none-any.whl'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
```

Compare the printed value with the receipt. Stop on a mismatch. Do not copy the
observed hash back into the expected receipt to make it pass.

Create a fresh directory **outside the repository**, then create an environment.
The following commands use a POSIX shell. Set both paths to your verified local
locations; `/absolute/path/...` is a placeholder, not a download URL:

```bash
mkdir equiframe-consumer
cd equiframe-consumer
python3.12 -m venv .venv
. .venv/bin/activate
WHEEL=/absolute/path/equiframe-0.12.2-py3-none-any.whl
WHEELHOUSE=/absolute/path/reviewed-wheelhouse
python -m pip install --no-index --find-links "$WHEELHOUSE" "${WHEEL}[arrow]"
python -m pip check
python -I -c "import equiframe, sys; print(sys.version); print(equiframe.__version__); print(equiframe.__file__)"
```

The import must point into this environment's installed package, not the checkout.
This command cannot fetch missing dependencies from an index. A missing compatible
wheel is a blocker to resolve with the artifact provider, not a reason to remove
integrity checks or install an unrelated `equiframe` from PyPI. For exact hashed
dependency installation, follow the kit's `--require-hashes` recipe. Do not use an
editable install or add the checkout to `PYTHONPATH` as an installation test.

On Windows, `py -3.12 -m venv .venv` creates the environment and
`.venv\Scripts\python.exe` can be used directly instead of activation. Do not
change security policy to activate it. These command conventions do not establish
that this candidate was verified on Windows. Each Python minor needs its matching
reviewed dependency set; do not reuse a 3.12 kit lock as a claim of compatibility
with 3.10, 3.11 or 3.13.

## 2. Compare two complete outputs

Save this complete script as `quickstart.py` in the new consumer directory:

```python
from pathlib import Path

import equiframe as ef
import pyarrow as pa

expected = pa.table({"id": ["A", "B"], "quantity": [10, 20]})
candidate = pa.table({"id": ["B", "A"], "quantity": [21, 10]})
private_root = Path("private-evidence")
result = ef.diff(candidate, expected, keys=["id"], work_dir=private_root)
assert result.state == "different" and result.complete
assert result.counts.final

# Default report hides values, names and paths. It does not delete the originals.
report = ef.write_comparison_report(result, Path("comparison-report"))
print(report.to_text())
print(ef.read_diff_contract(result).reference)

try:
    ef.assert_equivalent(result)
except ef.EquivalenceDifferentError:
    print("The regression was correctly rejected")
else:
    raise AssertionError("A different result must not pass")

fixed = ef.diff(expected, expected, keys=["id"], work_dir=private_root)
ef.assert_equivalent(fixed)
print(fixed.state, fixed.complete)
```

Run it once in that clean directory:

```bash
python -I quickstart.py
```

The first comparison is `different`; the corrected one prints `equivalent True`.
The key aligns `B` with `B` even though row order differs. Its quantity is 21
instead of 20. The script catches the deliberate failure only to demonstrate the
API; real tests should let `assert_equivalent` fail.

`comparison-report/` contains `report.json`, `report.txt`, `report.html` and a
publication inventory. Use a new report directory on repetition. `private-evidence/`
contains original snapshots and differences and can reveal your data. Do not
upload it automatically. With these known synthetic values only, explicit
`ReportOptions(include_values=True, include_metadata=True)` makes the diagnosis
visible. Review disclosure permission before using those options with real data.

## 3. Read states before acting

| Comparison state | Meaning | Equivalence gate |
|---|---|---|
| `equivalent` | Complete evaluation, no differences under the declared contract | Accepted only if the required guarantee/evidence also passes |
| `different` | Complete evaluation found a difference or contract violation | Fails |
| `not_evaluable` | Required judgment cannot be established | Fails, even if `complete=True` |

Use `ef.assert_equivalent(result)` or inspect
`ef.equivalence_decision(result).accepted`. `if result`, `bool(result)` and
`assert result` raise `TypeError` in every state. A returned object, zero displayed
examples, a successful HTML export or an integrity reader's exit zero is not an
equivalence decision.

`diff` infers a conservative contract from the right-hand schema, never from a
search for policies that make the pair agree. Inferred units are `unspecified`,
numbers are exact, only NULL is a missing-value representation, and nullable is
a visible default rather than inferred from observed rows. Use reviewed explicit
`ColumnSpec` definitions for domain units, allowed values and nullability.

## 4. Choose only the dependencies you need

| Extra | Purpose |
|---|---|
| None | Contract models/validation, serialization, CLI and local artifact support |
| `arrow` | Tabular comparison and Arrow capture/readers |
| `pandas`, `polars`, `duckdb` | The named native engine plus PyArrow |
| `engines` | All three native engines plus PyArrow |
| `ml` | Fit Isolation Forest with scikit-learn and NumPy |

Change `[arrow]` in the local wheel command to the extra you need. Use
`[engines,ml]` when you need both. Extra names do not supply missing binaries in an
offline wheelhouse. `import equiframe` itself does not import the optional engines,
Arrow, NumPy or scikit-learn. Missing optional dependencies fail explicitly.

Continue with [the three reproducible recipes](recipes.md),
[API reference](api.md), and [upgrade/failure guidance](upgrading.md).
