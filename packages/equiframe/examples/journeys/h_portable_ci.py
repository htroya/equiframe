"""H: portable verified evidence, minimized report and a fail-closed CI gate."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

import equiframe as ef

if TYPE_CHECKING or __package__:
    from .common import cli, column, comparison_record, new_output, write_summary
else:
    from common import cli, column, comparison_record, new_output, write_summary

SCENARIOS = ("good", "different", "not_evaluable", "error")


def capture_expected(table: pa.Table, directory: Path) -> ef.ArtifactRef:
    import pyarrow as pa

    path = directory / "literal-expected.arrow"
    with pa.OSFile(str(path), "wb") as sink, pa.ipc.new_file(sink, table.schema) as writer:
        writer.write_table(table)
    return ef.LocalArtifactStore(directory / "expected-store").put(
        path, media_type="application/vnd.apache.arrow.file"
    )


def run(output: Path, scenario: str = "good") -> dict[str, object]:
    import pyarrow as pa

    private = new_output(output, scenario, SCENARIOS)
    original = private / "original"
    original.mkdir()
    # Trusted synthetic SQL executes once in an owned/closed in-memory connection.
    captured = ef.capture_duckdb(
        "SELECT id, value FROM (VALUES ('SECRET_SYNTH_A', 10::BIGINT), "
        "('SECRET_SYNTH_B', $amount::BIGINT)) AS t(id, value)",
        parameters={"amount": 21 if scenario == "different" else 20},
        work_dir=original / "capture",
    )
    expected = capture_expected(
        pa.table({"id": ["SECRET_SYNTH_A", "SECRET_SYNTH_B"], "value": [10, 20]}), original
    )
    contract = ef.keyed_contract(
        (
            column("id", ef.StringType()),
            column("value", ef.IntegerType(bits=64, signed=True), unit="items"),
        ),
        keys=["id"],
        contract_id="journey.H.portable",
    ).spec.contract
    verified = ef.verify(
        {"candidate": captured.data},
        contract=contract,
        expected=expected,
        require_expected=True,
        options=ef.ComparisonOptions(max_rows=1 if scenario == "not_evaluable" else 100),
        work_dir=original / "verify",
    )
    portable = private / "portable"
    bundle = ef.export_bundle(original / "verify" / verified.verification_id, portable)
    manifest_sha256 = hashlib.sha256((portable / "bundle.json").read_bytes()).hexdigest()
    # The old absolute artifact paths cease to exist before import or inspection.
    original.rename(private / "retired-original")
    imported = private / "imported"
    imported_bundle = ef.import_bundle(portable, imported, expected_sha256=manifest_sha256)
    if imported_bundle != bundle:
        raise RuntimeError("Portable inventory changed during import")
    if scenario == "error":
        (imported / bundle.root_document).write_text("{}", encoding="utf-8")
        try:
            ef.read_bundle(imported, expected_sha256=manifest_sha256)
        except ef.ArtifactIntegrityError:
            return write_summary(
                output,
                {
                    "journey": "H",
                    "synthetic": True,
                    "scenario": scenario,
                    "accepted": False,
                    "exit_code": 2,
                    "integrity": "rejected",
                    "report_created": False,
                    "original_paths_available": original.exists(),
                },
            )
        raise RuntimeError("Synthetic corrupted bundle was unexpectedly accepted")
    inspected = ef.inspect_bundle(imported, expected_sha256=manifest_sha256)
    # read/inspect already verified the closed inventory and typed linked records.
    # Reopen only its validated root to render the imported comparison models.
    reread = ef.VerificationResult.model_validate_json(
        (imported / bundle.root_document).read_bytes()
    )
    comparisons = [
        comparison_record(comparison, output, f"comparison-{index}")
        for index, comparison in enumerate(reread.comparisons)
    ]
    accepted = (
        reread.publishable
        and bool(comparisons)
        and all(record["accepted"] for record in comparisons)
    )
    exit_code = 0 if accepted else 1 if reread.operational_state == "failed" else 3
    return write_summary(
        output,
        {
            "journey": "H",
            "synthetic": True,
            "scenario": scenario,
            "accepted": accepted,
            "exit_code": exit_code,
            "integrity": inspected["integrity"],
            "operational_state": reread.operational_state,
            "bundle_manifest_sha256": manifest_sha256,
            "original_paths_available": original.exists(),
            "report_created": True,
            "independent_review": reread.independent_review.state,
            "comparisons": comparisons,
        },
    )


if __name__ == "__main__":
    raise SystemExit(cli(run, __doc__ or "H", SCENARIOS))
