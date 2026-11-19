"""Reject plausible-looking report edits that disagree with captured records."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("library_result_verifier", HERE / "verify_results.py")
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def packet(tmp_path):
    for name in ("protocol.json", "report.json", "cases.csv.gz"):
        shutil.copyfile(HERE / "results/v1" / name, tmp_path / name)
    return tmp_path


def test_lossless_published_records_reconcile():
    result = verifier.verify(HERE / "results/v1", source=HERE / "run.py")
    assert result["native_executions"] == 2304
    assert result["scored_rows"] == 3840


def test_plausible_improved_detection_count_is_rejected(tmp_path):
    directory = packet(tmp_path)
    report_path = directory / "report.json"
    report = json.loads(report_path.read_bytes())
    report["workloads"][0]["models"][0]["results"]["in_distribution"]["m"]["tp"] += 1
    report_path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(AssertionError):
        verifier.verify(directory)


def test_changed_experiment_source_is_rejected(tmp_path):
    different = tmp_path / "changed.py"
    different.write_text("# modified evaluation\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        verifier.verify(HERE / "results/v1", source=different)
