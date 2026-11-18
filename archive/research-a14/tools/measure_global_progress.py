"""Equal-weight tracking average explicitly requested by the project owner.

Original area rubrics keep their denominators, sources and candidates.
The default retains nine areas. An explicit eight-area matrix and CLI switch
implement the owner's later exclusion of the security area without changing
historical results or removing requirements inside other area rubrics.
This is a project tracking index; it is not certification, a scientific result,
or evidence that any individual area met its target. Unknown inputs are errors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

BINDINGS = {
    "usability": ("passed_criteria", "total_criteria", 12),
    "universality": ("passed", "total", 60),
    "pypi_preparation": ("final_pass", "denominator", 20),
    "documentation": ("current_pass", "denominator", 20),
    "option_traceability": ("verified", "denominator", 8385),
    "package_quality": ("passed", "total", 20),
    "maturity": ("passed", "total", 16),
    "thesis": ("passed", "total", 22),
    "security": ("passed", "denominator", 20),
}
RUBRIC = "GLOBAL-NINE-EQUAL-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON member")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("Nonfinite JSON token: " + value)

    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=reject
    )


def calculate(metrics, *, exclude_security=False):
    """Use exact unrounded fractions and reject missing or repeated areas."""
    require(type(exclude_security) is bool, "Explicit scope selection required")
    expected_keys = set(BINDINGS) - ({"security"} if exclude_security else set())
    area_count = len(expected_keys)
    keys = [metric["key"] for metric in metrics]
    require(
        len(keys) == len(set(keys)) == area_count and set(keys) == expected_keys,
        "All selected original areas are required",
    )
    total = Fraction(0)
    historical = []
    areas = []
    for metric in metrics:
        key, numerator, denominator = (
            metric["key"],
            metric["numerator"],
            metric["denominator"],
        )
        require(
            type(numerator) is int
            and type(denominator) is int
            and denominator == BINDINGS[key][2]
            and 0 <= numerator <= denominator,
            "Invalid numerator or changed original denominator",
        )
        require(
            type(metric["record_targets_current_a13"]) is bool,
            "Candidate scope must be explicit",
        )
        percentage = Fraction(100 * numerator, denominator)
        total += percentage
        areas.append(
            {
                "key": key,
                "numerator": numerator,
                "denominator": denominator,
                "percent": float(percentage),
                "rounded_percent": round(float(percentage), 2),
                "weight": {"numerator": 1, "denominator": area_count},
                "assessed_candidate": metric["assessed_candidate"],
                "record_targets_current_a13": metric["record_targets_current_a13"],
                "source": metric["source"],
                "source_sha256": metric["source_sha256"],
            }
        )
        if not metric["record_targets_current_a13"]:
            historical.append(key)
    average = total / area_count
    return {
        "schema": "equiframe.global-progress.v1",
        "rubric": "GLOBAL-EIGHT-EQUAL-v1" if exclude_security else RUBRIC,
        "owner_selected_method": (
            "Mean of eight areas with equal weights; security explicitly excluded by owner2026-10-11"
            if exclude_security
            else "Mean of all nine areas with equal weights; user confirmed2026-10-11"
        ),
        "formula": f"sum(100 * verified_i / original_denominator_i) / {area_count}",
        "area_count": area_count,
        "excluded_areas": ["security"] if exclude_security else [],
        "scope_change_is_technical_progress": False,
        "areas": areas,
        "percent": float(average),
        "rounded_percent": round(float(average), 2),
        "exact_fraction": {
            "numerator": average.numerator,
            "denominator": average.denominator,
        },
        "target_percent": 75,
        "target_met": average >= 75,
        "percentage_points_remaining": float(max(Fraction(0), 75 - average)),
        "sum_of_area_percentage_point_gains_required": float(
            max(Fraction(0), 75 * area_count - total)
        ),
        "historical_candidate_areas": historical,
        "all_area_measurements_are_current_a13": not historical,
        "scope": "Tracking average of latest recorded area measurements; candidate-specific area scores and external requirements remain unchanged",
        "limitations": [
            "Equal weighting was explicitly selected; it is not an external or standardized quality assessment.",
            "A global average does not mean every area reached75%, nor that thesis hypotheses, safety or publication were approved.",
            "Historical A11/A12 measurements remain historical until their complete rubrics are reevaluated on A13.",
            "Repeated tests, proposed scenarios, unknown inputs and partial criteria earn no additional area points.",
        ],
    }


def measure(matrix_path, repo, *, exclude_security=False):
    matrix = read(matrix_path)
    metrics = matrix["metrics"]
    # Check every source before accepting its numbers; the matrix is a view,
    # never authority to invent a higher numerator or move an old score to A13.
    for metric in metrics:
        relative = Path(metric["source"])
        require(not relative.is_absolute(), "Source must be repository-relative")
        source_path = (repo / relative).resolve()
        require(
            source_path.is_relative_to(repo.resolve())
            and source_path.suffix == ".json",
            "Source escapes the repository",
        )
        require(
            hashlib.sha256(source_path.read_bytes()).hexdigest()
            == metric["source_sha256"],
            "Bound source changed",
        )
        source = read(source_path)
        require(metric["key"] in BINDINGS, "Unknown area")
        n_key, d_key, _ = BINDINGS[metric["key"]]
        require(
            type(source[n_key]) is int
            and type(source[d_key]) is int
            and source[n_key] == metric["numerator"]
            and source[d_key] == metric["denominator"],
            "Source numbers differ",
        )
        require(
            metric["record_targets_current_a13"]
            == (metric["assessed_candidate"] == "0.12.0a13"),
            "Historical candidate scope differs",
        )
        require("candidate" in source, "Source candidate is required")
        expected_candidate = metric["assessed_candidate"]
        if metric["key"] == "documentation":
            expected_candidate = {
                "equiframe": expected_candidate,
                "equiframe-benchmark": expected_candidate,
            }
        require(
            source["candidate"] == expected_candidate,
            "Source candidate differs",
        )
    result = calculate(metrics, exclude_security=exclude_security)
    result["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["input_matrix"] = matrix_path.name
    result["input_selection_rule"] = (
        "Explicit reviewed consolidated matrix; no automatic chronological retrieval"
    )
    result["input_matrix_sha256"] = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
    result["tool_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--exclude-security",
        action="store_true",
        help="Require the explicit eight-area matrix selected by the owner",
    )
    args = parser.parse_args()
    result = measure(args.matrix, args.repo, exclude_security=args.exclude_security)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(
            result,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        stream.write("\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "percent",
                    "rounded_percent",
                    "target_met",
                    "percentage_points_remaining",
                    "sum_of_area_percentage_point_gains_required",
                    "historical_candidate_areas",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
