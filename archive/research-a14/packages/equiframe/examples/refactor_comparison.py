"""Compare a pandas refactor on three synthetic rows, with exact USD cents.

The default case deliberately fails (exit 1): B has 2001 instead of 2000.
Reports disclose these synthetic values unless --redacted is requested. Raw
captures are temporary unless --work-dir explicitly retains them. No files,
network, credentials or external datasets are read. Copy this file beside the
installed wheel consumer; it imports only public EquiFrame APIs.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

import equiframe as ef


def materialize(*, fault: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run old and refactored implementations separately on the same fixture."""
    import pandas as pd

    source = pd.DataFrame(
        {
            "id": pd.Series(["A", "B", "C"], dtype="string[pyarrow]"),
            "quantity": pd.Series([1, 2, 3], dtype="int64"),
            "unit_cents": pd.Series([1000, 1000, 1000], dtype="int64"),
        }
    )
    # Conserved reference: the old implementation. The literal assertion below
    # checks this tiny fixture independently; pandas itself is not an oracle.
    expected = pd.DataFrame(
        {
            "id": source["id"].copy(),
            "total_cents": pd.Series(
                [
                    int(quantity) * int(price)
                    for quantity, price in zip(
                        source["quantity"], source["unit_cents"], strict=True
                    )
                ],
                dtype="int64",
            ),
        }
    )
    assert expected["total_cents"].tolist() == [1000, 2000, 3000]
    # Refactor: vectorized computation, with an intentional one-cent regression.
    candidate = pd.DataFrame(
        {
            "id": source["id"].copy(),
            "total_cents": (
                source["quantity"] * source["unit_cents"]
                + source["id"].eq("B").astype("int64") * int(fault)
            ),
        }
    )
    # Deliberately reorder only rows; this generated RangeIndex has no identity.
    candidate = candidate.iloc[[2, 0, 1]].reset_index(drop=True)
    return candidate, expected


def declaration(*, without_key: bool = False) -> ef.DiffContract:
    """Policies are declared before observing the candidate, never relaxed."""
    columns = (
        ef.ColumnSpec(
            name="id",
            logical_type=ef.StringType(),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
        ),
        ef.ColumnSpec(
            name="total_cents",
            logical_type=ef.IntegerType(bits=64, signed=True),
            nullable=False,
            null_policy=ef.NullPolicy(representations=("null",)),
            numeric_policy=ef.NumericPolicy(comparison="exact", unit="USD_cent"),
        ),
    )
    if without_key:
        return ef.bag_contract(columns, contract_id="recipe.refactor.bag", revision=1)
    return ef.keyed_contract(columns, keys=["id"], contract_id="recipe.refactor.keyed", revision=1)


def run_recipe(
    output: Path,
    *,
    fault: bool = True,
    without_key: bool = False,
    redacted: bool = False,
    work_dir: Path | None = None,
) -> ef.ComparisonReport:
    """Persist a self-contained report before applying the strict gate."""
    if output.exists():
        raise ValueError("Choose a new output directory; previous evidence is never overwritten")
    output.mkdir(parents=True)
    candidate, expected = materialize(fault=fault)
    context = (
        tempfile.TemporaryDirectory(prefix="equiframe-refactor-private-")
        if work_dir is None
        else nullcontext(str(work_dir))
    )
    with context as private:
        root = Path(private)
        public = output.resolve()
        raw = root.resolve()
        if public == raw or public in raw.parents or raw in public.parents:
            raise ValueError("Report and private evidence directories must be separate")
        result = ef.diff(
            candidate, expected, contract=declaration(without_key=without_key), work_dir=root
        )
        contract = ef.read_diff_contract(result)
        (output / "contract.json").write_text(contract.model_dump_json(indent=2), encoding="utf-8")
        report = ef.write_comparison_report(
            result,
            output / "report",
            evidence_root=root,
            declaration=contract,
            options=ef.ReportOptions(
                mode="detail",
                include_values=not redacted,
                include_metadata=not redacted,
                require_exhaustive=True,
            ),
        )
        print(report.to_text())
        print("Report:", output / "report" / "report.html")
        print("Contract:", output / "contract.json")
        ef.assert_equivalent(
            result,
            policy=ef.EquivalencePolicy(require_persisted_evidence=True),
            evidence_root=root,
            report_path=output / "report" / "report.html",
        )
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("different", "equivalent"), default="different")
    parser.add_argument("--without-key", action="store_true")
    parser.add_argument("--redacted", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("refactor-report"))
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    try:
        run_recipe(
            args.output,
            fault=args.case == "different",
            without_key=args.without_key,
            redacted=args.redacted,
            work_dir=args.work_dir,
        )
    except ef.EquivalenceDifferentError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ef.EquivalenceAssertionError as error:
        print(str(error), file=sys.stderr)
        return 3
    except Exception:
        print(
            "Recipe failed before acceptance. Check dependencies and use separate, new writable "
            "output/private directories. No successful verdict was established.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
