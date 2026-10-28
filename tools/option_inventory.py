"""Inspect an installed candidate and extend its reviewed registers with audit obligations.

This is developer tooling, not another capability registry. A discovered field or
passing import is never marked as behavioral coverage. Results remain NOT_RUN
until an external case receipt supplies a matching, artifact-bound observation.
"""

from __future__ import annotations

import argparse
import ast
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
from types import ModuleType, UnionType
from typing import Annotated, Any, Literal, Union, get_args, get_origin

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


def syntactic_values(annotation: str) -> list[Any]:
    """Read finite alternatives from an unresolved annotation without importing engines."""
    try:
        expression = ast.parse(annotation, mode="eval").body
    except SyntaxError:
        return []

    def walk(node: ast.AST) -> list[Any]:
        if isinstance(node, ast.Name) and node.id == "bool":
            return [False, True]
        if isinstance(node, ast.Constant) and node.value is None:
            return [None]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return walk(node.left) + walk(node.right)
        if isinstance(node, ast.Subscript):
            name = (
                node.value.id
                if isinstance(node.value, ast.Name)
                else (node.value.attr if isinstance(node.value, ast.Attribute) else "")
            )
            parts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if name == "Literal":
                return [
                    part.value
                    for part in parts
                    if isinstance(part, ast.Constant)
                    and (part.value is None or isinstance(part.value, str | int | bool))
                ]
            if name == "Annotated":
                return walk(parts[0])
            if name == "Optional":
                return [*walk(parts[0]), None]
            if name == "Union":
                return [value for part in parts for value in walk(part)]
        return []

    values: list[Any] = []
    for value in walk(expression):
        if not any(type(value) is type(old) and value == old for old in values):
            values.append(value)
    return values


def finite_values(annotation: Any) -> list[Any]:
    """Direct Literal/Enum/bool/None alternatives, not collection-member values."""
    if isinstance(annotation, str):
        return syntactic_values(annotation)
    if annotation is bool:
        return [False, True]
    if annotation is type(None):
        return [None]
    origin = get_origin(annotation)
    if origin is Annotated:
        return finite_values(get_args(annotation)[0])
    if origin is Literal:
        return list(get_args(annotation))
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return [member.value for member in annotation]
    result: list[Any] = []
    if origin in (Union, UnionType):
        for argument in get_args(annotation):
            for value in finite_values(argument):
                if not any(type(value) is type(old) and value == old for old in result):
                    result.append(value)
    return result


def open_domain(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is Annotated:
        return open_domain(get_args(annotation)[0])
    if origin in (Union, UnionType):
        return any(open_domain(argument) for argument in get_args(annotation))
    return not (
        annotation in (bool, type(None))
        or origin is Literal
        or (isinstance(annotation, type) and issubclass(annotation, Enum))
    )


def collection_values(annotation: Any) -> list[dict[str, Any]]:
    origin = get_origin(annotation)
    if origin is Annotated:
        return collection_values(get_args(annotation)[0])
    if origin in (Union, UnionType):
        return [value for argument in get_args(annotation) for value in collection_values(argument)]
    if origin not in (tuple, list, set, frozenset, dict):
        return []
    return [
        {"member_index": index, "values": finite_values(argument)}
        for index, argument in enumerate(get_args(annotation))
        if argument is not Ellipsis and finite_values(argument)
    ]


def bounds(annotation: Any, metadata: Any = ()) -> dict[str, Any]:
    """Preserve conditional branch/member limits; never intersect unrelated unions."""
    candidates = list(metadata)
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    branches = []
    if origin is Annotated:
        candidates.extend(arguments[1:])
        child = bounds(arguments[0])
        branches.extend(child.pop("branches", []))
        direct = child
    else:
        direct = {}
        for index, argument in enumerate(arguments):
            if argument is Ellipsis or origin is Literal:
                continue
            child = bounds(argument)
            if child:
                branches.append(
                    {
                        "path": ("union" if origin in (Union, UnionType) else "member")
                        + ":"
                        + str(index),
                        "bounds": child,
                    }
                )
    while candidates:
        item = candidates.pop()
        candidates.extend(getattr(item, "metadata", ()))
        for name in ("gt", "ge", "lt", "le", "min_length", "max_length", "multiple_of"):
            value = getattr(item, name, None)
            if value is not None:
                direct[name] = encoded(value)
    if branches:
        direct["branches"] = branches
    return direct


def boundary_classes(limits: dict[str, Any], prefix: str = "") -> list[str]:
    result = []
    if any(name in limits for name in ("gt", "ge", "min_length")):
        result += [
            prefix + "declared lower boundary",
            prefix + "just outside declared lower boundary",
        ]
    if any(name in limits for name in ("lt", "le", "max_length")):
        result += [
            prefix + "declared upper boundary",
            prefix + "just outside declared upper boundary",
        ]
    for branch in limits.get("branches", []):
        result += boundary_classes(branch["bounds"], prefix + branch["path"] + " ")
    return result


def _key(value: Any) -> str:
    return json.dumps(encoded(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _annotation(annotation: Any) -> str:
    return re.sub(r" at 0x[0-9a-fA-F]+", "", str(annotation))


def option_record(identifier: str, annotation: Any, default: Any, **extra: Any) -> dict[str, Any]:
    values = finite_values(annotation)
    limits = extra.pop("bounds", bounds(annotation))
    required = extra.pop(
        "required", default is PydanticUndefined or default is inspect.Parameter.empty
    )
    classes = []
    if open_domain(annotation):
        classes = ["admitted representative", "wrong Python/JSON type"]
        classes += boundary_classes(limits)
    return {
        "id": identifier,
        "annotation": _annotation(annotation),
        "required": required,
        "default": None if required else encoded(default),
        "finite_values": [encoded(value) for value in values],
        "collection_member_values": collection_values(annotation),
        "continuous_classes": classes,
        "bounds": limits,
        **extra,
    }


def _signature(value: Any, name: str) -> list[dict[str, Any]]:
    try:
        signature = inspect.signature(value)
    except (TypeError, ValueError):
        return []
    from typing import get_type_hints

    module = sys.modules.get(getattr(value, "__module__", ""))
    namespace = dict(vars(module)) if module is not None else {}
    # TYPE_CHECKING-only references to owned public ports are still inspectable
    # without importing optional engines. Do not replace the defining globals.
    for package_name in ("equiframe", "equiframe_benchmark"):
        package = sys.modules.get(package_name)
        if package is not None:
            for public_name in getattr(package, "__all__", ()):
                namespace.setdefault(public_name, getattr(package, public_name))
    records = []
    for parameter in signature.parameters.values():
        if parameter.name in {"self", "cls"}:
            continue
        annotation = parameter.annotation
        resolution_error = None
        if annotation is not inspect.Parameter.empty:
            holder = type("_OwnedAnnotation", (), {"__annotations__": {"value": annotation}})
            try:
                annotation = get_type_hints(holder, globalns=namespace)["value"]
            except (TypeError, NameError) as error:
                resolution_error = type(error).__name__
        records.append(
            option_record(
                "parameter:" + name + ":" + parameter.name,
                annotation,
                parameter.default,
                parameter_kind=parameter.kind.name,
                annotation_resolution="unresolved" if resolution_error else "resolved",
                annotation_resolution_error=resolution_error,
            )
        )
    return records


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
            "parameters": (
                _signature(value, name)
                if kind in {"function", "class", "model", "exception"}
                else []
            ),
            "finite_values": [encoded(item) for item in finite_values(value)],
        }
        try:
            record["signature"] = _annotation(inspect.signature(value)) if callable(value) else None
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
                    bounds=bounds(field.annotation, field.metadata),
                    description=field.description,
                )
                for field_name, field in value.model_fields.items()
            ]
        if isinstance(value, type):
            record["properties"] = []
            for property_name, descriptor in sorted(vars(value).items()):
                if property_name.startswith("_") or not isinstance(descriptor, property):
                    continue
                from typing import get_type_hints

                try:
                    output_type = get_type_hints(descriptor.fget).get("return", Any)
                except (TypeError, NameError):
                    output_type = Any
                record["properties"].append(
                    {
                        "id": "property:" + name + "." + property_name,
                        "name": property_name,
                        "read_only": descriptor.fset is None,
                        "return_annotation": _annotation(output_type),
                        "finite_values": finite_values(output_type),
                        "output_classes": (
                            [
                                "valid declared output",
                                "incomplete or unavailable output",
                            ]
                            if open_domain(output_type)
                            else []
                        ),
                        "documented_exit_codes_require_binding": property_name == "exit_code",
                    }
                )
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
        help_option = command.get_help_option(command.context_class(command))
        discovered = list(command.params)
        if help_option is not None and not any(p.name == help_option.name for p in discovered):
            discovered.append(help_option)
        for parameter in discovered:
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
                    "type": _annotation(parameter.type),
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
                path.relative_to(purelib).as_posix() for path in location.parent.rglob("*.py")
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
        "requires_python": next(iter(metadata.get_all("Requires-Python", [])), None),
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

    def add_option(option: dict[str, Any]) -> None:
        if option.get("required"):
            add(option["id"] + ":required_omission", "required argument omitted")
        else:
            add(option["id"] + ":default", "default", option["default"])
        for value in option["finite_values"]:
            add(option["id"] + ":value:" + _key(value), value, option["default"])
        add(option["id"] + ":invalid", "wrong type / unsupported discrete value")
        for member in option.get("collection_member_values", []):
            for value in member["values"]:
                add(
                    option["id"] + ":member:" + str(member["member_index"]) + ":" + _key(value),
                    {"collection_member": value},
                )
        for index, boundary in enumerate(option.get("continuous_classes", [])):
            add(option["id"] + ":class:" + str(index), boundary, option["default"])

    for record in inventory["exports"]:
        if record["alias_of"]:
            continue
        add(record["id"], {"surface_kind": record["kind"]})
        for value in record["finite_values"]:
            add(record["id"] + ":value:" + _key(value), value)
        for option in record.get("fields", []) + (
            [] if record["kind"] == "model" else record["parameters"]
        ):
            add_option(option)
        for property_record in record.get("properties", []):
            add(
                property_record["id"],
                {"surface_kind": "computed_property", "read_only_output": True},
            )
            for value in property_record["finite_values"]:
                add(
                    property_record["id"] + ":value:" + _key(value),
                    {"observed_output": value},
                )
            for index, output_class in enumerate(property_record["output_classes"]):
                add(property_record["id"] + ":class:" + str(index), output_class)
        for method in record.get("methods", []):
            add(
                "method:" + record["name"] + "." + method["name"],
                "declared public method",
            )
            for option in method["parameters"]:
                add_option(option)
    for command in inventory["cli"]:
        add(command["id"], "command and exit-code semantics")
        for option in command["parameters"]:
            if option.get("required"):
                add(option["id"] + ":required_omission", "required argument omitted")
            else:
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
        requirements = sorted(
            {
                match.group(0)
                for requirement in distribution["requires_dist"]
                if (match := re.match(r"[A-Za-z0-9_.-]+", requirement)) is not None
            }
        )
        for dependency in requirements:
            for availability in ("present", "absent"):
                add(
                    "requirement:"
                    + distribution["distribution"]
                    + ":"
                    + dependency
                    + ":"
                    + availability,
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
                document,
                stream,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            stream.write("\n")
    print(json.dumps(inventory["denominators"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
