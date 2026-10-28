"""Export supplementary paired supports from an existing evaluation JSON; no ETL/ML."""

import argparse
import json
from pathlib import Path

from equiframe_benchmark.evaluation import EvaluationReport
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.pairwise import evaluate_pairwise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    source = load_document(EvaluationReport, options.evaluation)
    paired = evaluate_pairwise(source)
    save_document(paired, options.output)
    global_result = paired.strata[0]
    print(
        json.dumps(
            {
                "analysis_role": paired.analysis_role,
                "scientific": paired.scientific,
                "source_scientific": source.scientific,
                "evaluation_sha256": paired.evaluation_sha256,
                "protocol_sha256": paired.protocol_sha256,
                "common_cases": len(global_result.common_case_ids),
                "pairs": {
                    f"{pair.left_method}-{pair.right_method}": len(pair.support_case_ids)
                    for pair in global_result.pairs
                },
                "output": str(options.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
