"""Only explicit boolean False may select the documented metadata-only reader."""

from decimal import Decimal

import equiframe as ef
import pytest
from test_integration import environment

import equiframe_benchmark as eb


class TruthMustNotRun:
    def __bool__(self):
        raise AssertionError("invalid verification option was truth-tested")


@pytest.fixture(scope="module")
def recorded_integration(tmp_path_factory):
    root = tmp_path_factory.mktemp("strict-reader-flag")
    spec, source, registry, *_ = environment(root)
    result = eb.run_integration(spec, source=source, registry=registry, work_dir=root)
    directory = root / result.integration_id
    assert result.complete and eb.read_integration(directory) == result
    return directory, result


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        0.0,
        1.0,
        None,
        "",
        "false",
        "true",
        [],
        {},
        (),
        Decimal(0),
        object(),
        TruthMustNotRun(),
    ],
    ids=[
        "int-zero",
        "int-one",
        "float-zero",
        "float-one",
        "none",
        "empty-text",
        "false-text",
        "true-text",
        "list",
        "dict",
        "tuple",
        "decimal",
        "object",
        "truth-hook",
    ],
)
def test_non_boolean_verification_options_are_rejected(recorded_integration, value):
    directory, _ = recorded_integration
    with pytest.raises(TypeError, match="verify must be a bool"):
        eb.read_integration(directory, verify=value)


def test_only_explicit_false_can_skip_corrupt_evidence(recorded_integration):
    directory, original = recorded_integration
    spec = directory / "spec.json"
    before = spec.read_bytes()
    try:
        spec.write_text("{}", encoding="utf-8")
        with pytest.raises(ef.ArtifactIntegrityError):
            eb.read_integration(directory, verify=True)
        # False is a deliberately metadata-only read, not proof of byte integrity.
        assert eb.read_integration(directory, verify=False) == original
        with pytest.raises(TypeError, match="verify must be a bool"):
            eb.read_integration(directory, verify=0)
    finally:
        spec.write_bytes(before)
    assert eb.read_integration(directory, verify=True) == original


def test_invalid_flag_is_rejected_before_missing_evidence_io(tmp_path):
    with pytest.raises(TypeError, match="verify must be a bool"):
        eb.read_integration(tmp_path / "missing", verify=None)
