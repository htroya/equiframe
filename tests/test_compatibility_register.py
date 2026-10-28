"""Executable drift guards for the published compatibility and capability boundary."""

import ast
import hashlib
import importlib
import inspect
import json
import subprocess
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from enum import Enum
from functools import reduce
from operator import or_
from pathlib import Path
from types import UnionType
from typing import get_args

import pytest
from packaging.requirements import Requirement
from pydantic import BaseModel, ValidationError
from typer.core import TyperGroup, TyperOption
from typer.main import get_command

import equiframe as ef
from equiframe._stability_inventory import (
    API_SIGNATURES,
    EXPERIMENTAL_API,
    MODEL_SHAPES,
    STABLE_API,
)
from equiframe.adapters import native_adapter
from equiframe.cli import app

ROOT = Path(__file__).resolve().parents[1]


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_every_public_export_is_explicitly_classified_once():
    names = STABLE_API + EXPERIMENTAL_API
    assert len(names) == len(set(names))
    assert set(names) == set(ef.__all__)
    records = [r for r in ef.get_stability_register() if r.surface == "api"]
    assert {r.name for r in records} == {"equiframe." + n for n in ef.__all__}
    assert {r.name for r in records if r.status == "stable"} == {
        "equiframe." + n for n in STABLE_API
    }
    for name in names:
        assert hasattr(ef, name)


# This display-only type is never passed to an implementation or a validator.
# Python 3.13 moved the real pathlib.Path class to pathlib._local. Normalize by
# class identity, not text: defaults, forward-reference strings, unrelated
# classes named Path, parameter kinds and all other annotations stay unchanged.
_DISPLAY_PATH = type("Path", (), {"__module__": "pathlib"})


def canonical_annotation(annotation):
    if annotation is Path:
        return _DISPLAY_PATH
    if isinstance(annotation, UnionType):
        return reduce(or_, (canonical_annotation(arg) for arg in get_args(annotation)))
    return annotation


def canonical_signature(signature):
    return str(
        signature.replace(
            parameters=[
                p.replace(annotation=canonical_annotation(p.annotation))
                for p in signature.parameters.values()
            ],
            return_annotation=canonical_annotation(signature.return_annotation),
        )
    )


@pytest.mark.parametrize("module", ["pathlib", "pathlib._local"])
def test_standard_library_path_relocation_has_one_canonical_signature(module, monkeypatch):
    monkeypatch.setattr(Path, "__module__", module)
    signature = inspect.Signature(
        [inspect.Parameter("path", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str | Path)],
        return_annotation=Path,
    )
    assert canonical_signature(signature) == "(path: str | pathlib.Path) -> pathlib.Path"


@pytest.mark.parametrize(
    "changed",
    [
        inspect.Parameter("renamed", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Path),
        inspect.Parameter("path", inspect.Parameter.KEYWORD_ONLY, annotation=Path),
        inspect.Parameter("path", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
        inspect.Parameter(
            "path", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Path, default=None
        ),
        inspect.Parameter(
            "path", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation="pathlib._local.Path"
        ),
        inspect.Parameter(
            "path",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=type("Path", (), {"__module__": "pathlib._local"}),
        ),
    ],
)
def test_path_canonicalization_does_not_hide_real_parameter_drift(changed):
    expected = "(path: pathlib.Path) -> None"
    assert canonical_signature(inspect.Signature([changed], return_annotation=None)) != expected


def test_path_canonicalization_preserves_defaults_and_return_contract():
    parameter = inspect.Parameter(
        "path",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=Path,
        default="pathlib._local.Path",
    )
    signature = inspect.Signature([parameter], return_annotation=None)
    assert canonical_signature(signature) == (
        "(path: pathlib.Path = 'pathlib._local.Path') -> None"
    )
    assert canonical_signature(signature.replace(return_annotation=str)) != (
        canonical_signature(signature)
    )


def test_stable_function_signatures_cannot_drift_silently():
    assert {
        name: canonical_signature(inspect.signature(getattr(ef, name)))
        for name in STABLE_API
        if inspect.isfunction(getattr(ef, name))
    } == API_SIGNATURES


def test_stable_model_fields_defaults_and_literals_cannot_drift_silently():
    assert {
        name: canonical_hash(getattr(ef, name).model_json_schema())
        for name in STABLE_API
        if inspect.isclass(getattr(ef, name)) and issubclass(getattr(ef, name), BaseModel)
    } == MODEL_SHAPES


def cli_inventory(command, prefix=()):
    if isinstance(command, TyperGroup):
        for name, child in command.commands.items():
            yield from cli_inventory(child, (*prefix, name))
    else:
        parameters = []
        for parameter in command.params:
            if parameter.name == "help":
                continue
            kind = "option" if isinstance(parameter, TyperOption) else "argument"
            options = ",".join([*parameter.opts, *getattr(parameter, "secondary_opts", [])])
            default = parameter.default
            if isinstance(default, Enum):
                default = default.value
            parameters.append(
                f"{kind}|{parameter.name}|{options}|required={parameter.required}|default={default}"
            )
        yield "equiframe " + " ".join(prefix), tuple(parameters)


def declared_cli_parameter(parameter):
    # These two reviewed enum members denote CLI choice values. Typer/Python
    # can expose an Enum or its value; an invalid raw "Extra.base" CLI default
    # stays invalid because only actual Enum instances are unwrapped above.
    stem, separator, default = parameter.rpartition("|default=")
    values = {"Extra.base": "base", "Case.good": "good"}
    return stem + separator + values.get(default, default)


def test_every_cli_command_option_requiredness_and_default_is_classified():
    records = [r for r in ef.get_stability_register() if r.surface == "cli"]
    assert dict(cli_inventory(get_command(app))) == {
        r.name: tuple(declared_cli_parameter(p) for p in r.parameters) for r in records
    }
    wrong = "option|extra|--extra|required=False|default=Extra.invalid"
    assert declared_cli_parameter(wrong).endswith("default=Extra.invalid")
    for record in records:
        assert record.exit_codes and set(record.exit_codes) <= {0, 1, 2, 3}
    assert next(r for r in records if r.name == "equiframe compare").exit_codes == (0, 1, 2, 3)
    assert next(r for r in records if r.name == "equiframe reduce").exit_codes == (0, 2, 3)


def test_all_shipped_core_schemas_are_classified_and_digest_guarded():
    declared = {
        r.name: r.schema_sha256
        for r in ef.get_stability_register()
        if r.surface == "format" and r.schema_sha256 is not None
    }
    actual = {
        p.name: canonical_hash(json.loads(p.read_text("utf-8")))
        for p in (ROOT / "schemas").glob("*.schema.json")
    }
    assert actual and actual == declared


def test_register_and_policy_are_immutable_machine_readable_records():
    records = ef.get_stability_register()
    assert len({(r.surface, r.name) for r in records}) == len(records)
    assert records == tuple(sorted(records, key=lambda r: (r.surface, r.name)))
    for record in records:
        assert ef.StabilityRecord.model_validate_json(record.model_dump_json()) == record
    with pytest.raises(ValidationError):
        records[0].status = "unsupported"
    policy = ef.get_compatibility_policy()
    assert policy.stable_notice_minor_releases >= 2
    assert policy.stable_notice_days >= 90
    assert policy.notice_threshold == "both"
    assert policy.applies_during_zero_major
    assert "reject" in policy.fail_closed_exception
    assert "Unknown versions are rejected" in policy.persisted_format_rule
    assert ef.CompatibilityPolicy.model_validate_json(policy.model_dump_json()) == policy


def test_capability_register_separates_every_stage_and_leaves_maintainers_unassigned():
    # Preserve the node ID referenced by the immutable A12 option-trace catalog.
    # Current built-in records have an owner; newly constructed records retain
    # their historical unassigned defaults unless the caller assigns them.
    records = ef.get_adapter_capabilities()
    assert tuple(r.adapter for r in records) == ("arrow", "pandas", "polars", "duckdb")
    for record in records:
        assert record.maintainer == ("Hernán Troya (htroya); EquiFrame adapter implementation only")
        assert record.maintenance_status == "assigned"
        unassigned = ef.AdapterCapability.model_validate(
            record.model_dump(exclude={"maintainer", "maintenance_status"})
        )
        assert unassigned.maintainer is None and unassigned.maintenance_status == "unassigned"
        assert record.evidence_scope == "repository_corpus_only_no_external_certification"
        assert tuple(s.stage for s in record.stages) == (
            "capture",
            "comparison",
            "native_execution",
            "migration",
        )
        assert all(s.conditions and s.implementation and s.tests for s in record.stages)
        assert ef.AdapterCapability.model_validate_json(record.model_dump_json()) == record
        with pytest.raises(ValidationError):
            record.maintainer = "invented owner"
        with pytest.raises(ValidationError):
            record.stages[0].scope = "expanded claim"
    duckdb = next(r for r in records if r.adapter == "duckdb")
    assert duckdb.stages[0].status == "supported_with_conditions"
    assert "capture_duckdb" in duckdb.stages[0].scope
    assert "exclusive borrowed ownership" in " ".join(duckdb.stages[0].conditions)
    assert duckdb.stages[1].status == duckdb.stages[2].status == "supported_with_conditions"


@pytest.mark.parametrize("engine", ["pandas", "polars", "duckdb"])
def test_runtime_capability_register_uses_actual_adapter_and_compiler(engine):
    record = next(r for r in ef.get_adapter_capabilities() if r.adapter == engine)
    assert record.runtime == native_adapter(engine).capabilities()
    assert ef.native_compiler_registry().resolve(engine).engine == engine
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    declared = metadata["project"]["optional-dependencies"][record.required_extra]
    for dependency in record.runtime.required_packages:
        assert any(requirement.startswith(dependency + ">=") for requirement in declared)
    if engine == "pandas":
        for profile in ("pandas", "engines"):
            requirement = next(
                Requirement(value)
                for value in metadata["project"]["optional-dependencies"][profile]
                if Requirement(value).name == "pandas"
            )
            for version in ("3.0.3", "3.0.4", "3.0.5", "3.0.6"):
                assert version not in requirement.specifier
            for version in ("2.2.0", "2.3.3", "3.0.0", "3.0.2", "3.1.0"):
                assert version in requirement.specifier


def test_arrow_has_no_builtin_execution_or_compiler():
    with pytest.raises(ef.CapabilityError):
        native_adapter("arrow")
    with pytest.raises(ef.CapabilityError):
        ef.native_compiler_registry().resolve("arrow")
    record = ef.get_adapter_capabilities()[0]
    assert record.runtime is None
    assert record.stages[2].status == record.stages[3].status == "not_applicable"


def test_capability_implementation_and_test_references_resolve():
    for record in ef.get_adapter_capabilities():
        for stage in record.stages:
            for reference in stage.implementation:
                module, name = reference.rsplit(".", 1)
                assert hasattr(importlib.import_module(module), name), reference
            for reference in stage.tests:
                file, name = reference.split("::")
                tree = ast.parse((ROOT / file).read_text("utf-8"))
                assert name in {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}, (
                    reference
                )


def test_introspection_does_not_import_optional_engines_or_execute_sources(tmp_path):
    program = """
import sys
import equiframe as ef
for value in ef.get_stability_register():
    value.model_dump_json()
for value in ef.get_adapter_capabilities():
    value.model_dump_json()
ef.get_compatibility_policy().model_dump_json()
assert not {'pandas', 'polars', 'duckdb', 'pyarrow', 'numpy', 'sklearn'} & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", program], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())


def test_stable_file_boundary_keeps_full_values_and_rejects_mutation(tmp_path):
    pa = pytest.importorskip("pyarrow")
    pytest.importorskip("pandas")
    pytest.importorskip("polars")
    pytest.importorskip("duckdb")
    expected = [
        {"id": str(i).zfill(8), "amount": i % 101, "note": None if i % 7 == 0 else "value"}
        for i in range(30_000)
    ]
    source = tmp_path / "source.json"
    source.write_text(json.dumps(expected), encoding="utf-8")
    original_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    with ef.load_dataset(source) as loaded:
        assert loaded.provenance.source.sha256 == original_sha
        assert pa.Table.from_pandas(loaded.pandas, preserve_index=False).to_pylist() == expected
        for engine in ("polars", "duckdb"):
            with ef.convert_dataset(loaded, target=engine) as converted:
                assert converted.pandas is loaded.pandas
                actual = (
                    converted.frame.to_arrow()
                    if engine == "polars"
                    else converted.frame.to_arrow_table()
                )
                assert actual.to_pylist() == expected
                assert actual.schema.names == ["id", "amount", "note"]
                assert pa.types.is_integer(actual.schema.field("amount").type)
                assert actual.column("note").null_count == sum(r["note"] is None for r in expected)
        loaded.pandas.loc[29_999, "id"] = "changed-after-capture"
        with pytest.raises(ef.DatasetReadError):
            ef.convert_dataset(loaded, target="polars")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_sha


@pytest.mark.parametrize("kind", ["ir", "profile", "r_options"])
def test_stabilized_models_keep_strict_roundtrips_and_format_versions(kind):
    instance = (
        ef.RelationalPlan(nodes=(ef.Scan(node_id="source", table="input"),), output="source")
        if kind == "ir"
        else ef.ProfileSpec(
            family="nulls_types",
            features=(
                ef.ProfileFeature(
                    name="missing", metric="tasa_nulos", table="result", columns=("value",)
                ),
            ),
        )
        if kind == "profile"
        else ef.RReviewOptions()
    )
    model = type(instance)
    payload = json.loads(instance.model_dump_json())
    assert model.model_validate_json(instance.model_dump_json()) == instance
    with pytest.raises(ValidationError):
        model.model_validate({**payload, "unrecognized_release_field": True})
    if "schema_version" in payload:
        with pytest.raises(ValidationError):
            model.model_validate({**payload, "schema_version": "0.12.0"})


@pytest.mark.parametrize("rule_state", ["alert", "no_alert", "not_evaluable"])
def test_stable_r_finalization_never_accepts_an_unavailable_reviewer(rule_state):
    pa = pytest.importorskip("pyarrow")
    table = pa.table({"value": list(range(30_000))})
    rules = ef.ComponentDecision(
        decision=rule_state,
        complete=rule_state != "not_evaluable",
        reason="missing_rules" if rule_state == "not_evaluable" else None,
    )
    result = ef.finalize_with_r(
        rules,
        ef.ComponentDecision(decision="no_alert", complete=True),
        left=table,
        right=table,
        contract=ef.infer_diff_contract(table.schema),
        options=ef.RReviewOptions(rscript="equiframe-stability-missing-rscript"),
    )
    assert result.r_review.state == "not_evaluable"
    assert not result.r_review.complete and not result.accepted
    assert not result.result.complete
    assert result.result.decision == ("alert" if rule_state == "alert" else "not_evaluable")
