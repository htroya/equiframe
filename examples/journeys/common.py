"""Small example-only presentation helpers; all decisions use public EquiFrame APIs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from collections.abc import Callable
from pathlib import Path

import equiframe as ef

CASES = ("good", "different", "not_evaluable")


def column(
    name: str,
    kind: ef.LogicalType,
    *,
    nullable: bool = False,
    unit: str = "count",
) -> ef.ColumnSpec:
    numeric = isinstance(kind, (ef.IntegerType, ef.FloatType, ef.DecimalType))
    temporal = None
    if isinstance(kind, ef.TimestampType):
        temporal = ef.TimestampPolicy(
            granularity=kind.unit,
            timezone=kind.timezone,
            naive="reject" if kind.timezone else "preserve",
            comparison="instant" if kind.timezone else "wall_time",
            ambiguous="reject",
            closed="both",
        )
    return ef.ColumnSpec(
        name=name,
        logical_type=kind,
        nullable=nullable,
        null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit=unit) if numeric else None,
        nan_policy=ef.NaNPolicy(handling="distinct") if isinstance(kind, ef.FloatType) else None,
        temporal_policy=temporal,
    )


def new_output(output: Path, scenario: str, choices: tuple[str, ...] = CASES) -> Path:
    if scenario not in choices:
        raise ValueError("Unknown synthetic scenario")
    output.mkdir(parents=True, exist_ok=False)
    (output / "private").mkdir()
    return output / "private"


def comparison_record(result: ef.ComparisonResult, output: Path, label: str) -> dict[str, object]:
    """Write a minimized view before enforcing the actual assertion gate."""
    ef.write_comparison_report(result, output / "reports" / label)
    try:
        ef.assert_equivalent(result)
    except ef.EquivalenceDifferentError:
        exit_code = 1
    except ef.EquivalenceAssertionError:
        exit_code = 3
    else:
        exit_code = 0
    return {
        "state": result.state,
        "complete": result.complete,
        "counts_final": result.counts.final,
        "accepted": exit_code == 0,
        "exit_code": exit_code,
        "difference_records": result.counts.difference_records,
        "diagnostic_codes": [diagnostic.code for diagnostic in result.diagnostics],
        "report": f"reports/{label}/report.html",
    }


def write_summary(output: Path, summary: dict[str, object]) -> dict[str, object]:
    """Bind fresh example evidence to the observed interpreter/dependencies/scripts."""
    distributions = {
        distribution.metadata["Name"]: distribution.version
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    }
    manifest = {
        "synthetic": True,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
        "dependencies": dict(sorted(distributions.items())),
        "journey_scripts_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
        "privacy": summary.get(
            "privacy", "private/ contains raw synthetic data; reports/ contains minimized views"
        ),
    }
    (output / "environment.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def cli(
    run: Callable[[Path, str], dict[str, object]],
    description: str,
    choices: tuple[str, ...] = CASES,
) -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=choices, default="good")
    args = parser.parse_args()
    try:
        summary = run(args.output, args.case)
    except ModuleNotFoundError:
        print(
            "Optional dependency missing; install journey requirements.lock in this interpreter.",
            file=sys.stderr,
        )
        return 2
    except Exception:
        # Avoid disclosing arbitrary client errors, values or paths when adapted.
        print(
            "Journey failed before acceptance; check dependencies and use a new output.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(summary, sort_keys=True))
    exit_code = summary["exit_code"]
    if not isinstance(exit_code, int):
        raise TypeError("Journey exit code must be an integer")
    return exit_code
