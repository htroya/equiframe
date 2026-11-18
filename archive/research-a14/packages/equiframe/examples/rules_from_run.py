"""Evaluate previously captured run.json and its local artifacts with Arrow only."""

import argparse
from pathlib import Path

import equiframe as ef


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--work-dir", type=Path, default=Path.cwd() / "rule-evidence")
    args = parser.parse_args()
    execution = ef.ExecutionResult.model_validate_json(args.run.read_bytes())
    result = ef.evaluate_rules(execution, work_dir=args.work_dir)
    print(result.decision, result.complete, result.coverage)
    if result.decision != "no_alert":
        for check in result.rules:
            print(check.check_id, check.state, check.reason)


if __name__ == "__main__":
    main()
