"""Audit discovery must never invent behavioral coverage or duplicate aliases."""

import importlib.util
import inspect
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Annotated, Literal, Protocol

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
    assert inventory.finite_values(Literal["a", "b"] | None) == ["a", "b", None]
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


@pytest.mark.parametrize("change", [None, "payload", "extra"])
def test_installed_wheel_paths_are_portable_and_payload_checks_remain_strict(
    monkeypatch, tmp_path, change
):
    purelib = tmp_path / "site-packages"
    module_file = purelib / "fixture" / "__init__.py"
    module_file.parent.mkdir(parents=True)
    module_file.write_bytes(b"CANDIDATE = 'synthetic'\n")
    wheel = tmp_path / "candidate.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("fixture/__init__.py", module_file.read_bytes())
    module = ModuleType("fixture")
    module.__file__ = str(module_file)
    monkeypatch.setattr(inventory.sysconfig, "get_paths", lambda: {"purelib": str(purelib)})
    if change == "payload":
        module_file.write_bytes(b"CHANGED = True\n")
        with pytest.raises(ValueError, match="payload differs"):
            inventory.installed_identity(module, "equiframe", wheel)
    elif change == "extra":
        (module_file.parent / "obsolete.py").write_bytes(b"STALE = True\n")
        with pytest.raises(ValueError, match="module inventory differs"):
            inventory.installed_identity(module, "equiframe", wheel)
    else:
        identity = inventory.installed_identity(module, "equiframe", wheel)
        assert identity["artifact"]["verified_payload_files"] == 1


def test_required_and_unbounded_options_do_not_invent_defaults_or_upper_bounds():
    required = inventory.option_record("field:required", int, inspect.Parameter.empty)
    assert required["required"] is True
    assert required["default"] is None
    assert "declared upper boundary" not in required["continuous_classes"]
    optional = inventory.option_record("field:optional", int | None, None)
    assert optional["finite_values"] == [None]
    assert optional["continuous_classes"] == ["admitted representative", "wrong Python/JSON type"]
    collection = inventory.option_record("field:tuple", tuple[Literal["a", "b"], ...], ())
    assert collection["finite_values"] == []
    assert collection["collection_member_values"] == [{"member_index": 0, "values": ["a", "b"]}]


def test_owned_public_method_options_are_in_the_audit_universe():
    class Port:
        def load(self, *, allow: bool = False):
            return allow

    exported = ModuleType("fixture")
    exported.__all__ = ["Port"]
    exported.Port = Port
    document = {
        "environment": {},
        "commit": "a" * 40,
        "wheel_sha256": "b" * 64,
        "exports": inventory.inspect_exports(exported, {}),
        "cli": [],
        "distributions": [],
    }
    rows = {row["id"]: row for row in inventory.obligations(document)}
    assert "method:fixture.Port.load" in rows
    assert "parameter:fixture.Port.load:allow:default" in rows
    assert "parameter:fixture.Port.load:allow:value:false" in rows
    assert "parameter:fixture.Port.load:allow:value:true" in rows
    assert "parameter:fixture.Port.load:allow:invalid" in rows


def test_optional_nested_limits_keep_branch_identity_instead_of_fake_intersection():
    annotation = Annotated[int, Field(ge=2, le=9)] | None
    record = inventory.option_record("field:optional", annotation, None)
    assert record["bounds"] == {"branches": [{"path": "union:0", "bounds": {"ge": 2, "le": 9}}]}
    assert "union:0 declared lower boundary" in record["continuous_classes"]
    assert "union:0 declared upper boundary" in record["continuous_classes"]
    mixed = Annotated[int, Field(ge=2, le=9)] | Annotated[float, Field(gt=20, lt=30)]
    limits = inventory.bounds(mixed)
    assert "ge" not in limits and "lt" not in limits
    assert limits["branches"][0]["bounds"] == {"ge": 2, "le": 9}
    assert limits["branches"][1]["bounds"] == {"gt": 20, "lt": 30}


def test_computed_outcome_properties_are_outputs_without_invented_defaults():
    class Outcome:
        @property
        def accepted(self) -> bool:
            raise RuntimeError("Inspection must never execute a property")

        @property
        def state(self) -> Literal["good", "bad", "unknown"]:
            raise RuntimeError("Inspection must never execute a property")

    exported = ModuleType("fixture")
    exported.__all__ = ["Outcome"]
    exported.Outcome = Outcome
    records = inventory.inspect_exports(exported, {})
    properties = records[0]["properties"]
    assert properties[0]["finite_values"] == [False, True]
    assert properties[1]["finite_values"] == ["good", "bad", "unknown"]
    rows = inventory.obligations(
        {
            "environment": {},
            "commit": "a" * 40,
            "wheel_sha256": "b" * 64,
            "exports": records,
            "cli": [],
            "distributions": [],
        }
    )
    ids = {row["id"] for row in rows}
    assert "property:fixture.Outcome.accepted:value:false" in ids
    assert 'property:fixture.Outcome.state:value:"unknown"' in ids
    assert not any(
        identifier.startswith("property:") and identifier.endswith(":default") for identifier in ids
    )


def test_one_unresolved_annotation_does_not_hide_other_parameter_options():
    def sample(context=None, flag: bool = False, mode: Literal["a", "b"] = "a"):
        return context, flag, mode

    sample.__annotations__["context"] = "MissingPort | None"
    rows = {p["id"].split(":")[-1]: p for p in inventory._signature(sample, "sample")}
    assert rows["context"]["annotation_resolution"] == "unresolved"
    assert rows["context"]["finite_values"] == [None]
    assert rows["flag"]["finite_values"] == [False, True]
    assert rows["mode"]["finite_values"] == ["a", "b"]


def test_owned_type_checking_port_resolves_without_optional_engine_imports():
    import equiframe as ef

    rows = {
        p["id"].split(":")[-1]: p
        for p in inventory._signature(ef.ingest_file, "equiframe.ingest_file")
    }
    assert rows["context"]["finite_values"] == [None]
    assert rows["context"]["annotation_resolution"] == "resolved"
    assert rows["batch_rows"]["annotation"] == "<class 'int'>"
    assert rows["batch_rows"]["default"] == 4096


@pytest.mark.parametrize(
    "annotation,expected",
    [
        ("pa.Table | None", [None]),
        ("bool | MissingPort", [False, True]),
        ("Literal['a','b'] | MissingPort | None", ["a", "b", None]),
        ("tuple[Literal['a','b'], ...]", []),
    ],
)
def test_unresolved_native_types_keep_syntactic_finite_alternatives(annotation, expected):
    assert inventory.finite_values(annotation) == expected


def test_declarative_aliases_and_protocols_do_not_invent_constructor_options():
    class Port(Protocol):
        def read(self, name: str) -> str: ...

    exported = ModuleType("fixture")
    exported.__all__ = ["State", "Port"]
    exported.State = Literal["good", "bad"]
    exported.Port = Port
    records = inventory.inspect_exports(exported, {})
    assert all(record["parameters"] == [] for record in records)
    assert next(record for record in records if record["name"] == "fixture.Port")["methods"]
    rows = inventory.obligations(
        {
            "environment": {},
            "commit": "a" * 40,
            "wheel_sha256": "b" * 64,
            "exports": records,
            "cli": [],
            "distributions": [],
        }
    )
    assert not any(":args:" in row["id"] or ":kwargs:" in row["id"] for row in rows)
    assert any(row["id"] == 'api:fixture.State:value:"good"' for row in rows)


def test_generated_signatures_omit_process_local_object_addresses():
    from pydantic import AfterValidator

    def keep(value):
        return value

    class WithValidator(BaseModel):
        value: Annotated[str, AfterValidator(keep)]

    module = ModuleType("fixture")
    module.__all__ = ["WithValidator"]
    module.WithValidator = WithValidator
    record = inventory.inspect_exports(module, {})[0]
    assert "AfterValidator" in record["signature"]
    assert "keep" in record["signature"]
    assert " at 0x" not in record["signature"]


def test_repeated_cli_discovery_has_stable_type_displays():
    first = inventory.inspect_cli("equiframe.cli", "equiframe")
    second = inventory.inspect_cli("equiframe.cli", "equiframe")
    assert first == second
    assert any(p["type"] for c in first for p in c["parameters"])
    assert all(" at 0x" not in p["type"] for c in first for p in c["parameters"])
