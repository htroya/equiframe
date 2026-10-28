"""Export V2 model schemas explicitly; never overwrite historical V1 schemas."""

import argparse
import json
from pathlib import Path

from equiframe_benchmark import (
    CommonSupportV2,
    ContrastSpecV2,
    EvaluationConfigV2,
    EvaluationReportV2,
    EvaluationStratumV2,
    FreezeDefinitionV2,
    FreezeManifestV2,
    PrincipalContrastV2,
    ProtocolReviewV2,
    SignedMetricV2,
    StudyCaseResultV2,
    StudyResultV2,
    TableExportV2,
)

MODELS_V2 = (
    CommonSupportV2,
    ContrastSpecV2,
    EvaluationConfigV2,
    EvaluationReportV2,
    EvaluationStratumV2,
    FreezeDefinitionV2,
    FreezeManifestV2,
    PrincipalContrastV2,
    ProtocolReviewV2,
    SignedMetricV2,
    StudyCaseResultV2,
    StudyResultV2,
    TableExportV2,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        args.output.mkdir(parents=True, exist_ok=False)
    for model in MODELS_V2:
        payload = (
            json.dumps(
                model.model_json_schema(),
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        target = args.output / (model.__name__ + "-2.0.schema.json")
        if args.check:
            if target.read_text(encoding="utf-8") != payload:
                raise SystemExit("outdated V2 schema: " + target.name)
            continue
        with target.open(
            "x",
            encoding="utf-8",
            newline="\n",
        ) as stream:
            stream.write(payload)


if __name__ == "__main__":
    main()
