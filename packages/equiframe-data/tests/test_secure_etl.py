"""Preserve source values and reject malformed or excessive prototype input."""

import importlib.util
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "data_prototype_etl", Path(__file__).resolve().parents[1] / "etl/cargar_json.py"
)
etl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(etl)


def test_direct_source_execution_uses_its_own_validation_helper(tmp_path):
    """A hostile same-named module must neither run nor disable input limits."""
    poison = tmp_path / "poison"
    poison.mkdir()
    marker = tmp_path / "unexpected-import"
    (poison / "safe_io.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('unsafe')\n"
        "raise RuntimeError('hostile helper was imported')\n"
    )
    valid = tmp_path / "input.json"
    valid.write_text('[{"releases":[{"ocid":"o1"}]}]')
    source = Path(etl.__file__)
    script = tmp_path / "source_consumer.py"
    script.write_text(
        "import importlib.util, sys\n"
        f"sys.path.insert(0, {str(poison)!r})\n"
        f"spec = importlib.util.spec_from_file_location('source_etl', {str(source)!r})\n"
        "module = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n"
        f"frames = module.cargar({str(valid)!r})\n"
        "if frames[0].height != 1: raise RuntimeError('Incomplete extraction')\n"
        "try:\n"
        f"    module.cargar({str(valid)!r}, max_input_bytes=1)\n"
        "except ValueError:\n    print('EXPECTED_REJECTION')\n"
        "else:\n    raise RuntimeError('Input budget bypassed')\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "EXPECTED_REJECTION" in result.stdout
    assert not marker.exists()


def test_list_navigation_preserves_supplier_and_zero():
    assert (
        etl._val({"suppliers": [{"id": "EC-RUC-001", "amount": 0}]}, "suppliers", 0, "id")
        == "EC-RUC-001"
    )
    assert etl._val({"suppliers": [{"amount": 0}]}, "suppliers", 0, "amount", default=99) == 0
    assert etl._val({"suppliers": []}, "suppliers", 0, "id", default="missing") == "missing"


def test_no_currency_or_description_is_invented_or_truncated(tmp_path):
    description = "Long source description " * 30
    file = tmp_path / "input.json"
    file.write_text(
        json.dumps(
            [
                {
                    "releases": [
                        {
                            "ocid": "o1",
                            "awards": [
                                {
                                    "id": "a1",
                                    "description": description,
                                    "value": {"amount": 10.2},
                                    "suppliers": [{"id": "EC-RUC-001", "name": "Supplier"}],
                                }
                            ],
                        }
                    ]
                }
            ]
        )
    )
    _, _, awards, _ = etl.cargar(file)
    row = awards.to_dicts()[0]
    assert row["moneda"] == ""
    assert row["monto_usd"] == Decimal("10.2")
    assert row["proveedor_id"] == "EC-RUC-001"
    assert row["descripcion"] == description


@pytest.mark.parametrize(
    "content", ["{}", "[{}]", '[{"releases":[null]}]', '[{"releases":[] ,"releases":[]}]']
)
def test_malformed_package_is_rejected(tmp_path, content):
    file = tmp_path / "input.json"
    file.write_text(content)
    with pytest.raises(ValueError):
        etl.cargar(file)


def test_budgets_are_enforced_before_processing(tmp_path):
    file = tmp_path / "input.json"
    file.write_text('[{"releases":[{"ocid":"o1"},{"ocid":"o2"}]}]')
    with pytest.raises(ValueError):
        etl.cargar(file, max_input_bytes=1)
    with pytest.raises(ValueError):
        etl.cargar(file, max_releases=1)


def test_nested_lists_cannot_bypass_the_output_budget(tmp_path):
    file = tmp_path / "input.json"
    file.write_text(json.dumps([{"releases": [{"ocid": "o1", "awards": [{}, {}, {}]}]}]))
    with pytest.raises(ValueError, match="Output row budget"):
        etl.cargar(file, max_flat_rows=3)


def test_tender_preserves_zero_and_its_source_currency(tmp_path):
    file = tmp_path / "input.json"
    file.write_text(
        '[{"releases":[{"ocid":"o1","tender":{"value":{"amount":0,"currency":"EUR"}}}]}]'
    )
    _, tender, _, _ = etl.cargar(file)
    row = tender.to_dicts()[0]
    assert row["monto_usd"] == 0
    assert row["moneda"] == "EUR"


@pytest.mark.parametrize(
    "award",
    [
        {"value": "amount=secret"},
        {"value": {"amount": True}},
        {"value": {"amount": "10.20"}},
        {"value": {"amount": [10]}},
        {"value": {"amount": {"number": 10}}},
        {"value": {"currency": "USD\n"}},
        {"suppliers": "source"},
        {"suppliers": [{"id": 123}]},
        {"items": "items"},
        {"roles": {"supplier": True}},
    ],
)
def test_malformed_nested_values_are_rejected_without_echoing_them(tmp_path, award):
    file = tmp_path / "input.json"
    file.write_text(json.dumps([{"releases": [{"ocid": "o1", "awards": [award]}]}]))
    with pytest.raises(ValueError) as error:
        etl.cargar(file)
    assert "secret" not in str(error.value)
