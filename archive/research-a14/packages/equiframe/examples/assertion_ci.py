"""Synthetic, offline pytest/CI recipe for independently materialized outputs.

Run ``python examples/assertion_ci.py --case equivalent --output ci-report``.
Add ``--work-dir private-evidence`` to retain private captures separately.
Use ``different`` or ``not_evaluable`` to demonstrate a failing gate. Optional
``--engine pandas|polars|duckdb`` executes that engine's own transformation; the
Arrow default needs only the arrow extra. The independent expected is literal
synthetic data, never another engine's converted output.

Raw captures live in a private temporary directory outside the upload directory
and are deleted when this example finishes unless --work-dir is supplied. A
supplied private work directory is retained and must not be uploaded. A new,
REDACTED report directory is published before asserting. Upload only its four
allowlisted files after verify_upload_directory succeeds, even when the assertion
fails; never upload temporary evidence,
the checkout, or arbitrary files from an existing directory. No credentials,
environment dumps, network, pytest plugin, production data, or EquiFrame runner
are needed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import Literal

import equiframe as ef

Scenario = Literal["equivalent", "different", "not_evaluable"]
Engine = Literal["arrow", "pandas", "polars", "duckdb"]
REPORT_FILES = frozenset({"report.json", "report.html", "report.txt", "evidence-manifest.json"})


class RecipeError(RuntimeError):
    """A redacted setup/publication failure; never successful equivalence."""


def _path_label(path: Path) -> str:
    # Paths are explicit caller-chosen report pointers; escape controls and bound
    # them just as other assertion diagnostics are bounded.
    return json.dumps(str(path)[:512], ensure_ascii=True)


def materialize(engine: Engine, scenario: Scenario) -> tuple[object, object]:
    """Execute one native implementation, then build an independent expected."""
    __tracebackhide__ = True
    import pyarrow as pa

    # All data is synthetic. The labels also exercise report value redaction.
    labels = ["North depot", "South depot", "West depot"]
    fault = int(scenario == "different")
    if engine == "arrow":
        candidate = pa.table(
            {
                "id": [1, 2, 3],
                "quantity": [
                    quantity * 2 + (fault if quantity == 2 else 0) for quantity in (1, 2, 3)
                ],
                "label": labels,
            }
        )
    elif engine == "pandas":
        import pandas as pd

        source = pd.DataFrame({"id": [1, 2, 3], "quantity": [1, 2, 3], "label": labels})
        candidate = source.assign(quantity=source["quantity"] * 2 + source["id"].eq(2) * fault)
    elif engine == "polars":
        import polars as pl

        source = pl.DataFrame({"id": [1, 2, 3], "quantity": [1, 2, 3], "label": labels})
        candidate = source.with_columns(
            (pl.col("quantity") * 2 + pl.when(pl.col("id") == 2).then(fault).otherwise(0)).alias(
                "quantity"
            )
        )
    elif engine == "duckdb":
        import duckdb

        # A private in-memory database; no shared DuckDB file or remote SQL.
        with duckdb.connect(":memory:") as connection:
            candidate = connection.execute(
                "SELECT CAST(id AS BIGINT) AS id, "
                "CAST(quantity * 2 + CASE WHEN id = 2 THEN ? ELSE 0 END AS BIGINT) AS quantity, "
                "label FROM (VALUES (1, 1, 'North depot'), (2, 2, 'South depot'), "
                "(3, 3, 'West depot')) AS source(id, quantity, label)",
                [fault],
            ).fetch_arrow_table()
    else:
        raise RecipeError("Unsupported synthetic engine")
    expected = pa.table(
        {
            "id": [1, 2, 3],
            "quantity": [2, 4, 6],
            "label": ["North depot", "South depot", "West depot"],
        }
    )
    return candidate, expected


def verify_upload_directory(directory: Path) -> None:
    """Verify a closed REDACTED report inventory; never traverse raw evidence."""
    __tracebackhide__ = True
    try:
        if directory.is_symlink() or {path.name for path in directory.iterdir()} != REPORT_FILES:
            raise ValueError("unexpected report inventory")
        for name in REPORT_FILES:
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("report file is not an ordinary file")
        receipt = ef.ReportPublicationManifest.model_validate_json(
            (directory / "evidence-manifest.json").read_bytes()
        )
        if {item.path for item in receipt.files} != REPORT_FILES - {"evidence-manifest.json"}:
            raise ValueError("unexpected manifest inventory")
        for item in receipt.files:
            raw = (directory / item.path).read_bytes()
            if len(raw) != item.size_bytes or hashlib.sha256(raw).hexdigest() != item.sha256:
                raise ValueError("report content does not match manifest")
        report = ef.read_comparison_report(directory / "report.json")
        if (
            report.options.include_values
            or report.options.include_metadata
            or report.options.mode != "diagnostic"
            or not report.evidence.values_withheld
            or not report.evidence.metadata_withheld
            or report.evidence.reproduction != "not_requested"
            or receipt.report_evidence != report.evidence
        ):
            raise ValueError("report is not a redacted publication")
    except Exception:
        raise RecipeError(
            "Report inventory verification failed; do not upload " + _path_label(directory)
        ) from None


def run_recipe(
    report_dir: Path,
    *,
    scenario: Scenario = "equivalent",
    engine: Engine = "arrow",
    work_dir: Path | None = None,
) -> None:
    """Publish safe diagnostics before the strict assertion, including on failure."""
    __tracebackhide__ = True
    if scenario not in ("equivalent", "different", "not_evaluable"):
        raise RecipeError("Unsupported synthetic scenario")
    try:
        candidate, expected = materialize(engine, scenario)
    except Exception:
        raise RecipeError(
            "Input materialization failed; check the selected optional engine extra. "
            "No comparison verdict or report was produced"
        ) from None
    decision = None
    try:
        private_context = (
            tempfile.TemporaryDirectory(prefix="equiframe-private-")
            if work_dir is None
            else nullcontext(str(work_dir))
        )
        with private_context as private:
            private_root = Path(private)
            upload = report_dir.resolve()
            raw = private_root.resolve()
            if upload == raw or upload in raw.parents or raw in upload.parents:
                raise RecipeError("Report and private evidence directories must be separate")
            try:
                result = ef.diff(
                    candidate,
                    expected,
                    keys=["id"],
                    work_dir=private_root,
                    options=ef.ComparisonOptions(
                        max_rows=1 if scenario == "not_evaluable" else 100
                    ),
                )
                decision = ef.equivalence_decision(result)
            except Exception:
                raise RecipeError(
                    "Comparison failed before a valid final result; equivalence was not established"
                ) from None
            try:
                # Default report disclosure is already redacted; keep it explicit at
                # this artifact boundary. Do not enable reproduction export here.
                ef.write_comparison_report(
                    result,
                    report_dir,
                    options=ef.ReportOptions(include_values=False, include_metadata=False),
                    evidence_root=private_root,
                )
                verify_upload_directory(report_dir)
            except Exception:
                raise RecipeError(
                    "Report publication failed; comparison state="
                    + decision.state
                    + ". Do not upload "
                    + _path_label(report_dir)
                    + "; select a fresh writable report directory and rerun"
                ) from None
            ef.assert_equivalent(
                result,
                policy=ef.EquivalencePolicy(require_persisted_evidence=True),
                evidence_root=private_root,
                report_path=report_dir / "report.html",
            )
    except (ef.EquivalenceAssertionError, RecipeError):
        raise
    except Exception:
        state = decision.state if decision is not None else "unavailable"
        raise RecipeError(
            "Recipe setup or cleanup failed; comparison state="
            + state
            + ". No successful acceptance was established; do not upload "
            + _path_label(report_dir)
        ) from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        dest="scenario",
        choices=("equivalent", "different", "not_evaluable"),
        default="equivalent",
    )
    parser.add_argument(
        "--engine", choices=("arrow", "pandas", "polars", "duckdb"), default="arrow"
    )
    parser.add_argument("--output", dest="report_dir", type=Path, default=Path("ci-report"))
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    try:
        run_recipe(
            args.report_dir, scenario=args.scenario, engine=args.engine, work_dir=args.work_dir
        )
    except ef.EquivalenceDifferentError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ef.EquivalenceAssertionError as error:
        print(str(error), file=sys.stderr)
        return 3
    except RecipeError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(
        "Complete equivalence accepted; REDACTED report: "
        + _path_label(args.report_dir / "report.html")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
