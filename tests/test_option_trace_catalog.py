"""Frozen synthetic cases prove metadata behavior, never implicit native execution."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

import equiframe as ef

ROOT = Path(__file__).parents[1]
PATH = ROOT / "tools" / "option_trace.py"
SPEC = importlib.util.spec_from_file_location("option_trace_cases", PATH)
assert SPEC is not None and SPEC.loader is not None
trace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trace)
FIXTURES = ROOT / "tests" / "fixtures" / "option_trace"
CATALOG = trace.read_json(FIXTURES / "catalog-a12.json")


def test_frozen_catalog_has_exact_reviewable_identity():
    manifest = json.loads((FIXTURES / "manifest.json").read_text("utf-8"))
    assert (
        hashlib.sha256((FIXTURES / "catalog-a12.json").read_bytes()).hexdigest()
        == manifest["sha256"]
    )
    assert len(CATALOG["cases"]) == manifest["unique_cases"] == 3443
    assert len({c["id"] for c in CATALOG["cases"]}) == 3443
    assert CATALOG["wheel_sha256"] == manifest["wheel_sha256"]
    assert CATALOG["obligation_ids_sha256"] == manifest["obligation_ids_sha256"]


@pytest.mark.parametrize("case", CATALOG["cases"], ids=lambda case: case["id"])
def test_frozen_metadata_case(case):
    receipt = trace.execute_case(case, CATALOG["seeds"], ef)
    if case["id"] == "DetectorVersions.equiframe.default" and ef.__version__ in (
        "0.12.0a13",
        "0.12.0a14",
        "0.12.0",
        "0.12.1",
        "0.12.2",
        "0.12.3",
        "0.12.4",
    ):
        # The immutable A12 catalog describes the A11 default in the old wheel.
        # A13 fixes producer identity; subsequent candidates emit their own identity.
        # Detect that deliberate historical drift;
        # Never rewrite the fixture or credit its failed case as current coverage.
        assert receipt["status"] == "FAIL"
        assert receipt["independent_expected"] == "0.12.0a11"
        assert receipt["observed"] == {"present": True, "value": ef.__version__}
        return
    assert receipt["status"] in {"PASS", "EXPECTED_REJECTION"}, receipt
