"""Truth testing cannot promote object existence to comparison acceptance."""

import pyarrow as pa
import pytest

import equiframe as ef


@pytest.fixture(params=["equivalent", "different", "not_evaluable", "invalid_expected"])
def result(request, tmp_path):
    expected = pa.table({"id": [1, 2], "value": [10, 20]})
    candidate = pa.table({"id": [1, 2], "value": [10, 21]})
    options = ef.ComparisonOptions(max_work=1) if request.param == "not_evaluable" else None
    if request.param == "equivalent":
        candidate = expected
    if request.param == "invalid_expected":
        expected = pa.table({"id": [1, 1], "value": [10, 20]})
    result = ef.diff(candidate, expected, keys=["id"], options=options, work_dir=tmp_path)
    assert result.state == (
        "not_evaluable" if request.param == "invalid_expected" else request.param
    )
    return result


@pytest.mark.parametrize("operation", ["bool", "if", "not", "and", "or", "assert", "any", "all"])
def test_every_truth_test_requires_explicit_verdict(result, operation):
    with pytest.raises(TypeError, match="use assert_equivalent"):
        if operation == "bool":
            bool(result)
        elif operation == "if":
            if result:
                pytest.fail("a result is not a boolean")
        elif operation == "not":
            _ = not result
        elif operation == "and":
            _ = result and True
        elif operation == "or":
            _ = result or False
        elif operation == "assert":
            assert result
        elif operation == "any":
            any([result])
        else:
            all([result])


def test_explicit_state_serialization_and_container_use_remain_supported(result):
    restored = ef.ComparisonResult.model_validate_json(result.model_dump_json())
    assert restored == result
    assert [result][0] is result
    assert isinstance(result.state == "equivalent", bool)
    assert isinstance(result.complete, bool)
    assert ef.comparison_report(result).state == result.state
