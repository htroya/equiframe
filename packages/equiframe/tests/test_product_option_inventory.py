"""Audit discovery must never invent behavioral coverage or duplicate aliases."""

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType
from typing import Literal

import pytest
from pydantic import BaseModel, Field

PATH = Path(__file__).resolve().parents[1] / "tools" / "option_inventory.py"
SPEC = importlib.util.spec_from_file_location("product_option_inventory", PATH)
assert SPEC is not None and SPEC.loader is not None
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


class Example(BaseModel):
    enabled: bool = False
    choice: Literal["a", "b"] = "a"
    count: int = Field(default=2, ge=1, le=4)


def sample_function(flag: bool = True, *, mode: Literal["small", "large"] = "small"):
    return flag, mode


def test_finite_discrete_values_preserve_boolean_identity():
    assert inventory.finite_values(bool) == [False, True]
    assert inventory.finite_values(Literal["a", "b"] | None) == ["a", "b"]
    assert inventory.finite_values(int) == []
    assert inventory.encoded(inspect.Parameter.empty) == {"required": True}


def test_alias_and_model_fields_are_inspected_without_factory_execution():
    module = ModuleType("fixture")
    module.__all__ = ["Example", "Alias", "sample_function"]
    module.Example = Example
    module.Alias = Example
    module.sample_function = sample_function
    records = inventory.inspect_exports(module, {})
    assert sum(record["alias_of"] is None for record in records) == 2
    model = next(record for record in records if record["name"] == "fixture.Alias")
    assert model["kind"] == "model"
    fields = {field["id"].split(":")[-1]: field for field in model["fields"]}
    assert fields["enabled"]["finite_values"] == [False, True]
    assert fields["enabled"]["default"] is False
    assert fields["choice"]["finite_values"] == ["a", "b"]
    assert fields["count"]["constraints"] == [{"repr": "Ge(ge=1)"}, {"repr": "Le(le=4)"}]


def test_inventory_creates_unrun_obligations_and_never_false_passes():
    options = inventory.inspect_exports(
        type("Exports", (), {"__name__": "fixture", "__all__": ["Example"], "Example": Example}),
        {},
    )
    document = {
        "environment": {"python": "test"},
        "commit": "a" * 40,
        "wheel_sha256": "b" * 64,
        "exports": options,
        "cli": [],
        "distributions": [],
    }
    rows = inventory.obligations(document)
    assert len(rows) == 17
    assert len({row["id"] for row in rows}) == len(rows)
    assert {row["status"] for row in rows} == {"NOT_RUN"}
    assert all(row["independent_expected"] is None for row in rows)
    assert all(row["observed"] is None for row in rows)
    assert sum(row["option_value_or_class"] is False for row in rows) == 1
    assert sum(row["option_value_or_class"] is True for row in rows) == 1


def test_source_import_cannot_claim_installed_inventory(monkeypatch, tmp_path):
    module = ModuleType("fixture")
    module.__file__ = str(tmp_path / "src" / "__init__.py")
    monkeypatch.setattr(
        inventory.sysconfig, "get_paths", lambda: {"purelib": str(tmp_path / "venv")}
    )
    with pytest.raises(ValueError, match="outside this interpreter"):
        inventory.installed_identity(module, "not-a-real-distribution")
