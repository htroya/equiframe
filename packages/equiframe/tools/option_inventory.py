"""Inspect an installed candidate and extend its reviewed registers with audit obligations.

This is developer tooling, not another capability registry. A discovered field or
passing import is never marked as behavioral coverage. Results remain NOT_RUN
until an external case receipt supplies a matching, artifact-bound observation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import inspect
import json
import platform
import re
import sys
import sysconfig
import zipfile
from collections import Counter
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel
from pydantic_core import PydanticUndefined
from typer.main import get_command

STATUS = {
    "PASS": "Executed independent expectation satisfied; applies only to this case and candidate",
    "FAIL": "Executed observation contradicts the independent expectation",
    "BLOCKED": "Not executed because a named external precondition is unavailable",
    "NOT_RUN": "Required obligation is inventoried but has no qualifying execution receipt",
    "EXPECTED_REJECTION": "Executed rejection contract satisfied; application did not accept data",
}


def encoded(value: Any) -> Any:
    """JSON-safe display without invoking factories, callbacks or model constructors."""
    if value is PydanticUndefined or value is inspect.Parameter.empty:
        return {"required": True}
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple | list):
        return [encoded(item) for item in value]
    if isinstance(value, dict):
        return {str(key): encoded(item) for key, item in value.items()}
    if isinstance(value, Path):
        return {"path": str(value)}
    return {"repr": re.sub(r" at 0x[0-9a-fA-F]+", "", repr(value))}


def finite_values(annotation: Any) -> list[Any]:
    """Direct Literal/Enum/bool alternatives, including optional/annotated unions."""
    if annotation is bool:
        return [False, True]
    if get_origin(annotation) is Literal:
        return list(get_args(annotation))
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return [member.value for member in annotation]
    result: list[Any] = []
    for argument in get_args(annotation):
        for value in finite_values(argument):
            if not any(type(value) is type(old) and value == old for old in result):
                result.append(value)
    return result


def _key(value: Any) -> str:
    return json.dumps(encoded(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _annotation(annotation: Any) -> str:
    return re.sub(r" at 0x[0-9a-fA-F]+", "", str(annotation))


def option_record(identifier: str, annotation: Any, default: Any, **extra: Any) -> dict[str, Any]:
    values = finite_values(annotation)
    return {
        "id": identifier,
        "annotation": _annotation(annotation),
        "default": encoded(default),
        "finite_values": [encoded(value) for value in values],
        "continuous_classes": []
        if values
        else [
            "admitted representative",
            "declared lower boundary",
            "declared upper boundary",
            "just outside each declared boundary",
            "wrong Python/JSON type",
            "missing required",
        ],
        **extra,
    }


def _signature(value: Any, name: str) -> list[dict[str, Any]]:
    try:
        signature = inspect.signature(value)
    except (TypeError, ValueError):
        return []
    try:
        from typing import get_type_hints

        annotations = get_type_hints(value)
    except (TypeError, NameError):
        annotations = {}
    return [
        option_record(
            "parameter:" + name + ":" + parameter.name,
            annotations.get(parameter.name, parameter.annotation),
            parameter.default,
            parameter_kind=parameter.kind.name,
        )
        for parameter in signature.parameters.values()
        if parameter.name not in {"self", "cls"}
    ]


def inspect_exports(module: ModuleType, known: dict[int, str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for export in sorted(module.__all__):
        value = getattr(module, export)
        name = module.__name__ + "." + export
        kind = "constant"
        if inspect.isfunction(value):
            kind = "function"
        elif isinstance(value, type):
            kind = (
                "model"
                if issubclass(value, BaseModel)
                else "exception"
                if issubclass(value, BaseException)
                else "protocol"
                if getattr(value, "_is_protocol", False)
                else "class"
            )
        elif get_origin(value) is not None or hasattr(value, "__value__"):
            kind = "declarative_type"
        # Interned small constants are not aliases of an API merely because id matches.
        alias = known.get(id(value)) if kind != "constant" else None
        if kind != "constant":
            known.setdefault(id(value), name)
        record: dict[str, Any] = {
            "id": "api:" + name,
            "name": name,
            "kind": kind,
            "alias_of": alias,
            "implementation_module": getattr(value, "__module__", None),
            "qualname": getattr(value, "__qualname__", None),
            "parameters": _signature(value, name) if callable(value) else [],
            "finite_values": [encoded(item) for item in finite_values(value)],
        }
        try:
            record["signature"] = str(inspect.signature(value)) if callable(value) else None
        except (TypeError, ValueError):
            record["signature"] = None
        try:
            source_file = inspect.getsourcefile(value)
            record["source"] = (
                {
                    "module_file": source_file,
                    "sha256": hashlib.sha256(Path(source_file).read_bytes()).hexdigest(),
                    "first_line": inspect.getsourcelines(value)[1],
                }
                if source_file
                else None
            )
        except (TypeError, OSError):
            record["source"] = None
        if kind == "constant":
            record["value"] = encoded(value)
        if kind == "model":
            record["fields"] = [
                option_record(
                    "field:" + name + ":" + field_name,
                    field.annotation,
                    (
                        {"factory": encoded(field.default_factory)}
                        if field.default_factory is not None
                        else field.default
                    ),
                    required=field.is_required(),
                    alias=field.alias,
                    validation_alias=encoded(field.validation_alias),
                    serialization_alias=field.serialization_alias,
                    default_factory=encoded(field.default_factory),
                    constraints=[encoded(item) for item in field.metadata],
                    description=field.description,
                )
                for field_name, field in value.model_fields.items()
            ]
        if isinstance(value, type):
            record["methods"] = [
                {
                    "name": member,
                    "parameters": _signature(getattr(value, member), name + "." + member),
                }
                for member in sorted(vars(value))
                if not member.startswith("_")
                and callable(getattr(value, member))
                and not member.startswith("model_")
            ]
        result.append(record)
    return result


def inspect_cli(module_name: str, command_name: str) -> list[dict[str, Any]]:
    app = importlib.import_module(module_name).app
    result: list[dict[str, Any]] = []

    def walk(command: Any, path: str) -> None:
        parameters = []
        for parameter in command.params:
            values = list(getattr(parameter.type, "choices", ()))
            if getattr(parameter, "is_bool_flag", False):
                values = [False, True]
            parameters.append(
                {
                    "id": "cli-option:" + path + ":" + str(parameter.name),
                    "name": parameter.name,
                    "flags": list(parameter.opts),
                    "secondary_flags": list(getattr(parameter, "secondary_opts", ())),
                    "default": encoded(parameter.default),
                    "required": parameter.required,
                    "is_flag": getattr(parameter, "is_flag", False),
                    "multiple": parameter.multiple,
                    "nargs": parameter.nargs,
                    "type": str(parameter.type),
                    "finite_values": [encoded(v) for v in values],
                    "min": getattr(parameter.type, "min", None),
                    "max": getattr(parameter.type, "max", None),
                }
            )
        result.append({"id": "cli:" + path, "name": path, "parameters": parameters})
        for name, child in sorted(getattr(command, "commands", {}).items()):
            walk(child, path + " " + name)

    walk(get_command(app), command_name)
    return result


def installed_identity(
    module: ModuleType, distribution: str, wheel: Path | None = None
) -> dict[str, Any]:
    location = Path(module.__file__ or "").resolve()
    purelib = Path(sysconfig.get_paths()["purelib"]).resolve()
    if not location.is_relative_to(purelib):
        raise ValueError(f"Candidate import outside this interpreter's site-packages: {location}")
    metadata = importlib.metadata.metadata(distribution)
    artifact: dict[str, Any] | None = None
    if wheel is not None:
        with zipfile.ZipFile(wheel) as archive:
            members = [
                name
                for name in archive.namelist()
                if name.startswith(module.__name__ + "/") and not name.endswith("/")
            ]
            for member in members:
                installed_file = purelib / member
                if not installed_file.is_file() or installed_file.read_bytes() != archive.read(
                    member
                ):
                    raise ValueError(f"Installed payload differs from selected wheel: {member}")
            expected_python = {name for name in members if name.endswith(".py")}
            observed_python = {
                str(path.relative_to(purelib)) for path in location.parent.rglob("*.py")
            }
            if expected_python != observed_python:
                raise ValueError("Installed Python module inventory differs from selected wheel")
        artifact = {
            "filename": wheel.name,
            "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "size_bytes": wheel.stat().st_size,
            "verified_payload_files": len(members),
        }
    return {
        "distribution": distribution,
        "version": importlib.metadata.version(distribution),
        "artifact": artifact,
        "module_file": str(location),
        "site_packages": str(purelib),
        "requires_python": metadata.get("Requires-Python"),
        "requires_dist": metadata.get_all("Requires-Dist", []),
        "extras": metadata.get_all("Provides-Extra", []),
        "entry_points": [
            {"group": item.group, "name": item.name, "value": item.value}
            for item in importlib.metadata.distribution(distribution).entry_points
        ],
    }


def obligations(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(identifier: str, option: Any, default: Any = None) -> None:
        rows.append(
            {
                "id": identifier,
                "api_cli": identifier.split(":", 1)[-1],
                "option_value_or_class": option,
                "default": default,
                "preconditions": (
                    "Applicable declared schema, cross-field conditions and optional dependencies"
                ),
                "engine": None,
                "direction": None,
                "format": None,
                "policy": None,
                "independent_expected": None,
                "test_program": None,
                "observed": None,
                "status": "NOT_RUN",
                "log": None,
                "environment": inventory["environment"],
                "commit": inventory["commit"],
                "wheel_sha256": inventory["wheel_sha256"],
                "reason": (
                    "Inventory discovery is not behavioral verification; "
                    "link a reviewed case receipt"
                ),
            }
        )

    for record in inventory["exports"]:
        if record["alias_of"]:
            continue
        add(record["id"], {"surface_kind": record["kind"]})
        for value in record["finite_values"]:
            add(record["id"] + ":value:" + _key(value), value)
        for option in record.get("fields", []) + (
            [] if record["kind"] == "model" else record["parameters"]
        ):
            add(option["id"] + ":default", "default", option["default"])
            for value in option["finite_values"]:
                add(option["id"] + ":value:" + _key(value), value, option["default"])
            add(option["id"] + ":invalid", "wrong type / unsupported discrete value")
            for index, boundary in enumerate(option.get("continuous_classes", [])):
                add(option["id"] + ":class:" + str(index), boundary, option["default"])
    for command in inventory["cli"]:
        add(command["id"], "command and exit-code semantics")
        for option in command["parameters"]:
            add(option["id"] + ":default", "default", option["default"])
            for value in option["finite_values"]:
                add(option["id"] + ":value:" + _key(value), value, option["default"])
            add(option["id"] + ":invalid", "invalid argument")
    for distribution in inventory["distributions"]:
        for extra in ["base", *distribution["extras"]]:
            for availability in ("present", "absent"):
                add(
                    "dependency:" + distribution["distribution"] + ":" + extra + ":" + availability,
                    availability,
                )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--benchmark-wheel", type=Path)
    parser.add_argument("--benchmark", action="store_true")
    arguments = parser.parse_args()
    if not re.fullmatch("[a-f0-9]{40}", arguments.commit):
        parser.error("commit must be an exact SHA-1 identity")
    if arguments.benchmark and arguments.benchmark_wheel is None:
        parser.error("--benchmark requires --benchmark-wheel")
    wheel_sha256 = hashlib.sha256(arguments.wheel.read_bytes()).hexdigest()
    import equiframe as ef

    environment = {
        "sys_executable": sys.executable,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "dependencies": dict(
            sorted((d.metadata["Name"], d.version) for d in importlib.metadata.distributions())
        ),
    }
    known: dict[int, str] = {}
    inventory: dict[str, Any] = {
        "schema_version": "equiframe.option-inventory/1.0",
        "commit": arguments.commit,
        "wheel_sha256": wheel_sha256,
        "environment": environment,
        "distributions": [installed_identity(ef, "equiframe", arguments.wheel)],
        "register": [r.model_dump(mode="json") for r in ef.get_stability_register()],
        "adapter_capabilities": [r.model_dump(mode="json") for r in ef.get_adapter_capabilities()],
        "exports": inspect_exports(ef, known),
        "cli": inspect_cli("equiframe.cli", "equiframe"),
        "scope": (
            "Installed declared exports and owned methods, model fields, CLI and metadata; "
            "aliases excluded from capability denominator"
        ),
    }
    if arguments.benchmark:
        eb = importlib.import_module("equiframe_benchmark")

        inventory["distributions"].append(
            installed_identity(eb, "equiframe-benchmark", arguments.benchmark_wheel)
        )
        inventory["exports"].extend(inspect_exports(eb, known))
        inventory["cli"].extend(inspect_cli("equiframe_benchmark.cli", "equiframe-benchmark"))
    rows = obligations(inventory)
    inventory["denominators"] = {
        "export_names": len(inventory["exports"]),
        "unique_non_alias_exports": sum(not r["alias_of"] for r in inventory["exports"]),
        "classifications": dict(Counter(r["kind"] for r in inventory["exports"])),
        "declared_field_occurrences": sum(len(r.get("fields", [])) for r in inventory["exports"]),
        "audit_obligations": len(rows),
        "behaviorally_verified_obligations": 0,
    }
    for path, document in (
        (arguments.output, inventory),
        (
            arguments.matrix,
            {
                "schema_version": "equiframe.option-matrix/1.0",
                "status_definitions": STATUS,
                "scope": (
                    "Discovery creates obligations, not passes; behavioral mapping remains explicit"
                ),
                "rows": rows,
            },
        ),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(
                document, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
            )
            stream.write("\n")
    print(json.dumps(inventory["denominators"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
