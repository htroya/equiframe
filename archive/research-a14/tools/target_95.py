"""Verify recorded measurements and calculate gaps without issuing new scores.

Only provenance and arithmetic are checked. A retained receipt or a target is
never promoted to a fresh assessment, human approval or scientific result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

AREA_KEYS = frozenset(
    {
        "usability",
        "maturity",
        "universality",
        "pypi_preparation",
        "thesis",
        "documentation",
        "security",
        "option_traceability",
        "package_quality",
    }
)


def _source_counts(source: dict[str, Any], key: str) -> tuple[int, int]:
    fields = {
        "usability": ("passed_criteria", "total_criteria"),
        "universality": ("passed", "total"),
        "pypi_preparation": ("final_pass", "denominator"),
        "documentation": ("current_pass", "denominator"),
        "package_quality": ("passed", "total"),
    }
    if key == "option_traceability":
        modes = source["current_option_traceability"]
        normal, optimized = modes["normal"], modes["optimized"]
        if normal != optimized:
            raise ValueError(
                "Traceability modes disagree; repeated runs cannot add coverage"
            )
        counts = normal["verified"], normal["total"]
    else:
        n, d = fields[key]
        counts = source[n], source[d]
    if any(type(value) is not int for value in counts):
        raise ValueError("Bound source counts must be integers")
    return counts


def _read(path: Path) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject(value: str) -> None:
        raise ValueError(f"Non-finite JSON number: {value}")

    result = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique,
        parse_constant=reject,
    )
    if not isinstance(result, dict):
        raise TypeError("Expected a JSON object")
    return result


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Evidence is missing or outside repository: {relative}")
    return path


def assess(
    root: Path, matrix_path: Path, target: Decimal = Decimal(95)
) -> dict[str, Any]:
    """Keep missing and historical scores distinct; require current evidence for a gate."""
    if not target.is_finite() or not Decimal(0) < target <= Decimal(100):
        raise ValueError("Target must be finite and in (0, 100]")
    matrix = _read(matrix_path)
    if matrix.get("schema") != "equiframe.project-status-matrix.v1":
        raise ValueError("Unknown matrix schema")
    if matrix.get("overall_percentage") is not None:
        raise ValueError("No aggregate rubric is defined for these nine areas")
    versions = matrix["current_package_versions"]
    metrics = matrix["metrics"]
    if not metrics:
        raise ValueError("No metrics")
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        key = metric["key"]
        if not isinstance(key, str) or not key or key in seen:
            raise ValueError("Empty or duplicate metric ID")
        seen.add(key)
        numerator, denominator = metric.get("numerator"), metric.get("denominator")
        row: dict[str, Any] = {
            "key": key,
            "aspect": metric["aspect"],
            "target_percent": float(target),
            "candidate": metric.get("assessed_candidate"),
            "rubric": metric.get("rubric"),
            "original_numerator": numerator,
            "original_denominator": denominator,
            "required_numerator": None,
            "additional_obligations": None,
            "last_recorded_percent": None,
            "current_candidate_percent": None,
            "target_met": False,
            "new_assessment": False,
            "remaining": metric.get("remaining", []),
        }
        if numerator is None and denominator is None:
            if metric.get("percent") is not None:
                raise ValueError("Unmeasured area must not have a percentage")
            row["status"] = "NO_CURRENT_MEASUREMENT"
        else:
            if (
                type(numerator) is not int
                or type(denominator) is not int
                or denominator <= 0
                or not 0 <= numerator <= denominator
            ):
                raise ValueError(
                    "Invalid counts; partial, blocked and not-run retain denominator"
                )
            observed = Decimal(numerator) * 100 / denominator
            declared = Decimal(str(metric["percent"]))
            if not declared.is_finite() or abs(declared - observed) > Decimal(
                "0.000001"
            ):
                raise ValueError(f"Percentage disagrees with original counts: {key}")
            source = _inside(root, metric["source"])
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if digest != metric["source_sha256"]:
                raise ValueError(f"Recorded evidence changed: {key}")
            source_data = _read(source)
            if _source_counts(source_data, key) != (numerator, denominator):
                raise ValueError(f"Counts differ from bound source: {key}")
            source_candidate = source_data.get(
                "candidate", source_data.get("assessed_candidate")
            )
            if source_candidate is None:
                raise ValueError(f"Bound source is missing a candidate: {key}")
            if isinstance(source_candidate, dict):
                # Documentation binds a core/benchmark pair, not a scalar release.
                if (
                    source_candidate.get("equiframe") != row["candidate"]
                    or source_candidate != versions
                ):
                    raise ValueError(f"Candidate pair differs from bound source: {key}")
                source_candidate = source_candidate["equiframe"]
            if source_candidate is not None and source_candidate != row["candidate"]:
                raise ValueError(f"Candidate differs from bound source: {key}")
            required = int(
                (target * denominator / 100).to_integral_value(rounding=ROUND_CEILING)
            )
            row.update(
                required_numerator=required,
                additional_obligations=max(0, required - numerator),
                last_recorded_percent=float(observed),
                source=metric["source"],
                source_sha256=digest,
            )
            current = metric.get("record_targets_current_a13", False)
            if type(current) is not bool:
                raise ValueError("Current-candidate flag must be a boolean")
            if current and row["candidate"] != versions["equiframe"]:
                raise ValueError(
                    f"Historical candidate cannot be marked current: {key}"
                )
            row["status"] = (
                "RETAINED_CURRENT_RECORD" if current else "RETAINED_HISTORICAL_RECORD"
            )
            if current:
                row["current_candidate_percent"] = float(observed)
                row["target_met"] = observed >= target
        rows.append(row)
    if seen != AREA_KEYS:
        raise ValueError("All nine original areas must remain in the assessment")
    achieved = all(row["target_met"] for row in rows)
    return {
        "schema": "equiframe.target-gap.v1",
        "target_percent": float(target),
        "source_matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "current_package_versions": versions,
        "overall_percentage": None,
        "all_targets_met": achieved,
        "status": "TARGET_MET_IN_RETAINED_RECORDS"
        if achieved
        else "TARGET_NOT_ACCREDITED",
        "metrics": rows,
        "limits": "Provenance/arithmetic only; no new execution, rubric, approval or source audit. "
        "Historical scores remain historical and missing measurements remain null.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=Decimal, default=Decimal(95))
    parser.add_argument("--require-target", action="store_true")
    args = parser.parse_args()
    try:
        matrix = args.matrix or args.root / "docs/PROJECT_STATUS_MATRIX_20261010.json"
        result = assess(args.root, matrix, args.target)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Assessment rejected: {error}\n")
    print(f"{result['status']}: {len(result['metrics'])} areas; no new scores issued")
    return 1 if args.require_target and not result["all_targets_met"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
