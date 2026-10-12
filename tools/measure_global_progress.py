"""Equal-weight tracking average explicitly requested by the project owner.

Nine original area rubrics keep their denominators, sources and candidates.
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


def calculate(metrics):
    """Use exact unrounded fractions and reject missing or repeated areas."""
    keys = [metric["key"] for metric in metrics]
    require(
        len(keys) == len(set(keys)) == 9 and set(keys) == set(BINDINGS),
        "All nine original areas are required",
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
                "weight": {"numerator": 1, "denominator": 9},
                "assessed_candidate": metric["assessed_candidate"],
                "record_targets_current_a13": metric["record_targets_current_a13"],
                "source": metric["source"],
                "source_sha256": metric["source_sha256"],
            }
        )
        if not metric["record_targets_current_a13"]:
            historical.append(key)
    average = total / 9
    return {
        "schema": "equiframe.global-progress.v1",
        "rubric": RUBRIC,
        "owner_selected_method": "Mean of all nine areas with equal weights; user confirmed2026-10-11",
        "formula": "sum(100 * verified_i / original_denominator_i) / 9",
        "area_count": 9,
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
            max(Fraction(0), 675 - total)
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


def measure(matrix_path, repo):
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
    result = calculate(metrics)
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
    args = parser.parse_args()
    result = measure(args.matrix, args.repo)
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
