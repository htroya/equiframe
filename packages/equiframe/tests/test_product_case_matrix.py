"""A historical label or loosely similar node cannot become a fresh matrix pass."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "tools" / "case_matrix.py"
SPEC = importlib.util.spec_from_file_location("product_case_matrix", PATH)
assert SPEC is not None and SPEC.loader is not None
matrix = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(matrix)


def declaration(node="tests/test_case.py::test_exact", status="supported"):
    return {
        "category": "I",
        "operation": "exact",
        "type": "integer",
        "engine": "arrow",
        "direction": "comparison",
        "policy": "exact",
        "expected": "literal 1 != 2",
        "pytest_node": node,
        "status": status,
        "execution": "historical_pass",
    }


def receipt(cases):
    return {
        "cases": cases,
        "environment": {"python": "test"},
        "commit": "a" * 40,
        "wheel": {"sha256": "b" * 64},
    }


@pytest.mark.parametrize(
    "case_status,expected",
    [
        ("PASS", "PASS"),
        ("FAIL", "FAIL"),
        ("NOT_RUN", "NOT_RUN"),
        ("BLOCKED", "NOT_RUN"),
    ],
)
def test_exact_observed_state_is_not_inferred_from_history(case_status, expected):
    result = matrix.bind(
        {"rows": [declaration()]},
        receipt(
            [
                {"nodeid": "tests/test_case.py::test_exact", "status": case_status},
            ]
        ),
        "test.log",
    )
    assert result["rows"][0]["status"] == expected


def test_absent_similarly_named_and_skipped_nodes_are_not_passes():
    result = matrix.bind(
        {"rows": [declaration()]},
        receipt(
            [
                {"nodeid": "tests/test_case.py::test_exact_more", "status": "PASS"},
            ]
        ),
        "test.log",
    )
    assert result["rows"][0]["status"] == "NOT_RUN"
    assert result["rows"][0]["observed"] == []


def test_rejection_is_not_application_acceptance_and_parameters_are_not_lost():
    result = matrix.bind(
        {"rows": [declaration(status="rejected")]},
        receipt(
            [
                {
                    "nodeid": "packages/equiframe/tests/test_case.py::test_exact[left]",
                    "status": "PASS",
                },
                {
                    "nodeid": "packages/equiframe/tests/test_case.py::test_exact[right]",
                    "status": "PASS",
                },
            ]
        ),
        "test.log",
    )
    assert result["rows"][0]["status"] == "EXPECTED_REJECTION"
    assert result["denominators"]["distinct_matched_test_nodes"] == 2
    assert result["denominators"]["declaration_rows"] == 1
