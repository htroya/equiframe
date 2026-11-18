"""Check all expected synthetic outcomes; exit 0 means the demonstration suite passed.

This harness EXPECTS deliberate negative cases. It is not a production data gate.
Use an individual journey or assert_equivalent for production acceptance instead.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__:
    from .common import write_summary
else:
    from common import write_summary

CASES = {
    "a_pandas_refactor": {"good": 0, "different": 1, "not_evaluable": 3, "duplicate": 1},
    "b_native_migration": {"good": 0, "different": 1, "not_evaluable": 3},
    "c_retail_etl": {"good": 0, "different": 1, "error": 2},
    "d_financial_reconciliation": {"good": 0, "different": 1, "not_evaluable": 3},
    "e_telemetry": {
        "good": 0,
        "different": 1,
        "not_evaluable": 3,
        "null_nan": 1,
        "duplicate_loss": 1,
    },
    "f_data_science_preparation": {
        "good": 0,
        "different": 1,
        "not_evaluable": 3,
        "dropped_row": 1,
        "changed_id": 1,
    },
    "g_external_snapshots": {"good": 0, "different": 1, "error": 2, "schema_error": 2},
    "h_portable_ci": {"good": 0, "different": 1, "not_evaluable": 3, "error": 2},
}


def run(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=False)
    outcomes = []
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    for module, cases in CASES.items():
        for scenario, expected_exit in cases.items():
            directory = output / f"{module[0]}-{scenario}"
            command = (
                [sys.executable, "-I", "-m", f"{__package__}.{module}"]
                if __package__ and __package__.startswith("equiframe.")
                else [sys.executable, str(Path(__file__).with_name(module + ".py"))]
            )
            response = subprocess.run(
                [*command, "--case", scenario, "--output", str(directory.resolve())],
                cwd=output,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            (output / f"{module[0]}-{scenario}.log").write_text(
                response.stdout + response.stderr, encoding="utf-8"
            )
            summary_path = directory / "summary.json"
            summary = json.loads(summary_path.read_bytes()) if summary_path.is_file() else {}
            matched = (
                response.returncode == expected_exit
                and summary.get("exit_code") == expected_exit
                and summary.get("accepted") is (expected_exit == 0)
                and summary.get("synthetic") is True
            )
            outcomes.append(
                {
                    "journey": module[0].upper(),
                    "scenario": scenario,
                    "expected_exit": expected_exit,
                    "observed_exit": response.returncode,
                    "matched": matched,
                }
            )
    passed = all(outcome["matched"] for outcome in outcomes)
    return write_summary(
        output,
        {
            "synthetic": True,
            "meaning": "Good and deliberately negative synthetic outcomes matched expectations",
            "production_data_approval": False,
            "suite_passed": passed,
            "exit_code": 0 if passed else 1,
            "cases": outcomes,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = run(args.output)
    except Exception:
        print("Suite did not finish; check dependencies and choose a new output.", file=sys.stderr)
        return 2
    print(json.dumps(summary, sort_keys=True))
    code = summary["exit_code"]
    return code if isinstance(code, int) else 2


if __name__ == "__main__":
    raise SystemExit(main())
