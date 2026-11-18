"""Freeze and execute a conservative extension of the A13 obligation catalog.

Expectations come from the frozen declaration inventory and literal fixtures,
never from a validation result. Metadata and Python binding receipts establish
only those surfaces; they do not establish native engine behavior.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import inspect
import json
import platform
import sys
from collections import Counter
from pathlib import Path
from typing import Any, get_args, get_origin

SPEC = importlib.util.spec_from_file_location(
    "option_operations", Path(__file__).with_name("option_operations.py")
)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Existing identity verifier unavailable")
op = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(op)
WHEEL = "c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23"
BASELINE = "2b8691cb9c3d0633d309a95fa471ca7df0414af2a3c31f203c60a12cdbe419b2"
SEEDS = "9eaa56aa71b803d901b07b56da0a89eb3cb610a44dc67a78513b553288ab59e1"


def write(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(
            value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
        stream.write("\n")


def literal_seeds() -> dict[str, dict[str, Any]]:
    # Transcribed from destinations.py and detector_types.py before execution.
    table = {
        "name": "a",
        "source_sha256": "0" * 64,
        "source_size_bytes": 0,
        "source_format": "arrow",
        "parquet": {"path": "a.parquet", "sha256": "0" * 64, "size_bytes": 0},
        "row_count": 0,
        "verification_id": "v",
        "verification_sha256": "0" * 64,
    }
    return {
        "PublishedTable": table,
        "LoadReceipt": {
            "run_id": "r",
            "policy": "create",
            "previous_run": None,
            "identity_sha256": "7ae43f1d75e8cf8955daa2335125146333839e6ceb466197e09dcf233f55845b",
            "tables": [table],
            "schema_version": "1.0",
            "guarantee": "local_atomic_pointer",
        },
        "ComponentDetectionResult": {
            "schema_version": "1.0",
            "method": "mad",
            "bundle_sha256": "0" * 64,
            "fit_sha256": "0" * 64,
            "profiles_sha256": "0" * 64,
            "matrix_sha256": "0" * 64,
            "rows": 1,
            "scores": {"state": "scored", "values": [0.0], "reason": None},
            "decisions": [
                {
                    "result": {
                        "decision": "no_alert",
                        "complete": True,
                        "reason": None,
                    },
                    "score": 0.0,
                    "threshold": 0.0,
                }
            ],
        },
    }


def unannotated(annotation: Any) -> Any:
    from typing import Annotated

    return (
        unannotated(get_args(annotation)[0])
        if get_origin(annotation) is Annotated
        else annotation
    )


def boundary(annotation: Any, limits: dict, label: str, old: Any):
    """Return a predeclared input/expectation, or exclude unsupported shapes."""
    annotation = unannotated(annotation)
    if label.startswith(("union:", "member:")):
        head, rest = label.split(" ", 1)
        kind, position = head.split(":")
        number = int(position)
        branches = [b for b in limits.get("branches", []) if b["path"] == head]
        args = get_args(annotation)
        if len(branches) != 1 or number >= len(args):
            return None
        if kind == "union":
            return boundary(args[number], branches[0]["bounds"], rest, old)
        origin = get_origin(annotation)
        # Dict key/value boundaries and empty heterogeneous containers require
        # individually reviewed fixtures and are deliberately excluded here.
        if origin not in (list, tuple) or number != 0:
            return None
        sample = old[0] if isinstance(old, list) and old else None
        child = boundary(args[number], branches[0]["bounds"], rest, sample)
        if child is None:
            return None
        value, admitted, code = child
        data = copy.deepcopy(old) if isinstance(old, list) and old else [value]
        data[0] = value
        return data, admitted, code
    lower = "lower" in label
    outside = "just outside" in label
    origin = get_origin(annotation)
    if "min_length" in limits or "max_length" in limits:
        key = "min_length" if lower else "max_length"
        if key not in limits:
            return None
        length = limits[key] + (-1 if lower and outside else 1 if outside else 0)
        if length < 0 or length > 4096:
            return None
        if annotation is str:
            value = (
                "/" if isinstance(old, str) and old.startswith("/") else "a"
            ) * length
            code = "string_too_short" if lower else "string_too_long"
        elif origin in (tuple, list) and isinstance(old, list) and old:
            value = [copy.deepcopy(old[0]) for _ in range(length)]
            code = "too_short" if lower else "too_long"
        else:
            return None
        return value, not outside, code if outside else None
    alternatives = ("ge", "gt") if lower else ("le", "lt")
    key = next((k for k in alternatives if k in limits), None)
    if key is None or annotation not in (int, float):
        return None
    value = limits[key] + (-1 if lower and outside else 1 if outside else 0)
    if annotation is float:
        value = float(value)
    admitted = not outside and key in ("ge", "le")
    codes = {
        "ge": "greater_than_equal",
        "gt": "greater_than",
        "le": "less_than_equal",
        "lt": "less_than",
    }
    return value, admitted, None if admitted else codes[key]


def prepare(inventory, rows, seeds, previous, ef):
    done = {identifier for r in previous for identifier in r["obligations"]}
    remaining = {
        r["id"]: r for r in rows if r["status"] == "NOT_RUN" and r["id"] not in done
    }
    fixtures = {
        name: copy.deepcopy(seed["input"]) for name, seed in seeds["seeds"].items()
    }
    extras = literal_seeds()
    fixtures.update(extras)
    # Reviewed historical model expectations already specify nested defaults
    # and JSON serialization. Reuse that literal oracle, not SDK serialization.
    serialized = {
        case["model"]: copy.deepcopy(case["expected"])
        for case in seeds["cases"]
        if case["operation"] == "model"
    }
    serialized.update(extras)
    planned = []
    exclusions = Counter()

    def add(case, links):
        links = [identifier for identifier in links if identifier in remaining]
        if links:
            op.require(
                all(identifier not in done for identifier in links),
                "Repeated planned obligation",
            )
            done.update(links)
            planned.append({**case, "obligations": links})

    for record in inventory["exports"]:
        if record["kind"] != "model" or record["alias_of"]:
            continue
        name = record["name"].split(".")[-1]
        if name not in fixtures:
            exclusions["no_reviewed_seed"] += 1
            continue
        model = getattr(ef, name)
        decorators = model.__pydantic_decorators__
        validators = list(decorators.model_validators.values())
        after_only = all(v.info.mode == "after" for v in validators)
        input_data = fixtures[name]
        if name in extras:
            add(
                {
                    "case_id": f"followup.{name}.literal",
                    "driver": "model",
                    "model": name,
                    "input": input_data,
                    "expected": input_data,
                    "basis": "Reviewed complete synthetic fixture; no real publication or fitted inference",
                },
                [record["id"]],
            )
        for field in record["fields"]:
            key = field["id"].split(":")[-1]
            base = {"model": name, "field": key, "input": copy.deepcopy(input_data)}
            declared = model.model_fields[key]
            specific = any(
                key in d.info.fields or "*" in d.info.fields
                for d in decorators.field_validators.values()
            )

            # AfterValidator/BeforeValidator metadata is not represented by the
            # numeric declaration. Only Text's reviewed whitespace check is
            # compatible with the literal 'a' representative used here.
            def metadata_callbacks(annotation):
                callbacks = [m for m in get_args(annotation) if hasattr(m, "func")]
                for part in get_args(annotation):
                    callbacks.extend(metadata_callbacks(part))
                return callbacks

            custom = [m for m in declared.metadata if hasattr(m, "func")]
            custom.extend(metadata_callbacks(declared.annotation))
            safe_metadata = all(
                getattr(m.func, "__name__", "") == "_text" for m in custom
            )
            for number, label in enumerate(field["continuous_classes"]):
                identifier = field["id"] + f":class:{number}"
                if (
                    identifier not in remaining
                    or identifier in done
                    or "boundary" not in label
                ):
                    continue
                variation = boundary(
                    declared.annotation, field["bounds"], label, input_data.get(key)
                )
                if variation is None or specific or not safe_metadata:
                    exclusions["shape_or_field_validator_requires_fixture"] += 1
                    continue
                value, admitted, code = variation
                normalized = boundary(
                    declared.annotation,
                    field["bounds"],
                    label,
                    serialized.get(name, {}).get(key, input_data.get(key)),
                )
                if admitted and normalized is None:
                    exclusions["missing_literal_serialization_oracle"] += 1
                    continue
                # Positive cases cannot ignore any cross-field invariant.
                # Field rejections may bypass only AFTER model validators.
                if (admitted and validators) or (not admitted and not after_only):
                    exclusions["cross_field_requires_coordinated_fixture"] += 1
                    continue
                data = copy.deepcopy(input_data)
                data[key] = value
                add(
                    {
                        **base,
                        "case_id": f"followup.{name}.{key}.boundary.{number}",
                        "driver": "field",
                        "input": data,
                        "expected": {"admitted": admitted, "value": normalized[0]}
                        if admitted
                        else {"admitted": False, "field": key, "error_codes": [code]},
                        "basis": {
                            "declaration": field["bounds"],
                            "class": label,
                            "rule": "Literal declared boundary, not first admissible value; no observed output used",
                        },
                    },
                    [identifier],
                )
            if not validators and not specific:
                for value in field["finite_values"]:
                    if (
                        name == "EquiJoin"
                        and key == "cardinality"
                        and value == "many_to_many"
                    ):
                        exclusions[
                            "serializer_omits_field_requires_attribute_fixture"
                        ] += 1
                        continue
                    suffix = json.dumps(
                        value, sort_keys=True, ensure_ascii=True, separators=(",", ":")
                    )
                    identifier = field["id"] + ":value:" + suffix
                    data = copy.deepcopy(input_data)
                    data[key] = value
                    add(
                        {
                            **base,
                            "case_id": f"followup.{name}.{key}.finite.{suffix}",
                            "driver": "field",
                            "input": data,
                            "expected": {"admitted": True, "value": value},
                            "basis": "Declared finite value with no cross-field or field validator",
                        },
                        [identifier],
                    )
            if name not in extras:
                continue
            # Each representative is checked against the literal field output;
            # it is not inferred from the API-level construction case.
            add(
                {
                    **base,
                    "case_id": f"followup.{name}.{key}.representative",
                    "driver": "field",
                    "expected": {"admitted": True, "value": input_data[key]},
                    "basis": "Reviewed literal fixture field",
                },
                [field["id"] + ":class:0"] if field["continuous_classes"] else [],
            )
            omission = copy.deepcopy(input_data)
            omission.pop(key, None)
            if field["required"]:
                expected = {"admitted": False, "field": key, "error_codes": ["missing"]}
                identifier = field["id"] + ":required_omission"
            else:
                expected = {"admitted": True, "value": input_data[key]}
                identifier = field["id"] + ":default"
            add(
                {
                    **base,
                    "case_id": f"followup.{name}.{key}.omission",
                    "driver": "field",
                    "input": omission,
                    "expected": expected,
                    "basis": "Literal fixture omitted field and documented required/default declaration",
                },
                [identifier],
            )
            if after_only and not specific:
                annotation = unannotated(declared.annotation)
                origin = get_origin(annotation)
                if origin in (tuple, list):
                    wrong, codes = False, ["tuple_type", "list_type"]
                elif annotation in (int, float):
                    wrong, codes = False, ["int_type", "float_type"]
                else:
                    wrong, codes = (
                        False,
                        [
                            "string_type",
                            "literal_error",
                            "model_type",
                            "enum",
                            "int_type",
                            "float_type",
                        ],
                    )
                data = copy.deepcopy(input_data)
                data[key] = wrong
                links = [field["id"] + ":invalid"]
                if "wrong Python/JSON type" in field["continuous_classes"]:
                    links.append(
                        field["id"]
                        + ":class:"
                        + str(
                            field["continuous_classes"].index("wrong Python/JSON type")
                        )
                    )
                add(
                    {
                        **base,
                        "case_id": f"followup.{name}.{key}.wrong",
                        "driver": "field",
                        "input": data,
                        "expected": {
                            "admitted": False,
                            "field": key,
                            "error_codes": codes,
                        },
                        "basis": "Strict declaration: boolean is not the required string, numeric, sequence or nested model",
                    },
                    links,
                )
    for identifier in sorted(remaining):
        if (
            identifier in done
            or not identifier.startswith("parameter:")
            or not identifier.endswith(":required_omission")
        ):
            continue
        _, qualified, argument, _ = identifier.split(":")
        parts = qualified.split(".")
        if len(parts) not in (2, 3) or parts[0] != "equiframe":
            continue
        target = getattr(ef, parts[1])
        if len(parts) == 3:
            target = getattr(target, parts[2])
        actual = target.__init__ if isinstance(target, type) else target
        function = getattr(actual, "__func__", actual)
        if (
            not inspect.isfunction(function)
            or function.__module__.split(".")[0] != "equiframe"
        ):
            exclusions["not_owned_python_binding"] += 1
            continue
        if getattr(function, "__wrapped__", None) is not None:
            exclusions["wrapper_requires_consumption_fixture"] += 1
            continue
        if isinstance(target, type) and inspect.isfunction(target.__new__):
            exclusions["custom_allocator_requires_fixture"] += 1
            continue
        signature = inspect.signature(target)
        if argument not in signature.parameters:
            exclusions["signature_disagrees"] += 1
            continue
        add(
            {
                "case_id": f"followup.binding.{qualified}.{argument}",
                "driver": "binding",
                "target": qualified,
                "omitted": argument,
                "expected": {
                    "exception": "TypeError",
                    "missing_argument": argument,
                    "entered_body": False,
                },
                "basis": "Actual Python invocation; inert placeholders for other required arguments; body-entry guard; only omission binding is claimed",
            },
            [identifier],
        )
    return {
        "schema": "equiframe.option-boundary-catalog.v1",
        "wheel_sha256": WHEEL,
        "baseline_sha256": BASELINE,
        "seed_catalog_sha256": SEEDS,
        "obligation_ids_sha256": seeds["obligation_ids_sha256"],
        "cases": planned,
        "exclusions": dict(exclusions),
        "scope": "Conservative metadata boundaries/finite values plus actual required-argument binding; no native behavior or scientific evidence",
    }


def execute(case, ef):
    from pydantic import ValidationError

    expected = case["expected"]
    if case["driver"] == "binding":
        parts = case["target"].split(".")
        target = getattr(ef, parts[1])
        if len(parts) == 3:
            target = getattr(target, parts[2])
        actual = target.__init__ if isinstance(target, type) else target
        function = getattr(actual, "__func__", actual)
        signature = inspect.signature(target)
        args, kwargs = [], {}
        for parameter in signature.parameters.values():
            if (
                parameter.name == case["omitted"]
                or parameter.default is not inspect.Parameter.empty
            ):
                continue
            if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
                args.append(None)
            elif parameter.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                kwargs[parameter.name] = None
        entered = False

        def guard(frame, event, arg):
            nonlocal entered
            if event == "call" and frame.f_code is function.__code__:
                entered = True
                raise RuntimeError(
                    "Binding receipt must never execute operational body"
                )
            return guard

        saved = sys.gettrace()
        try:
            sys.settrace(guard)
            target(*args, **kwargs)
        except TypeError as error:
            message = str(error)
            observed = {
                "exception": "TypeError",
                "missing_argument": case["omitted"]
                if case["omitted"] in message and "required" in message
                else None,
                "entered_body": entered,
            }
            status = "EXPECTED_REJECTION" if observed == expected else "FAIL"
        except Exception as error:  # noqa: BLE001 - retain unexpected failures as FAIL
            observed, status = (
                {"unexpected_exception": type(error).__name__, "entered_body": entered},
                "FAIL",
            )
        else:
            observed, status = {"exception": None, "entered_body": entered}, "FAIL"
        finally:
            sys.settrace(saved)
    else:
        model = getattr(ef, case["model"])
        try:
            output = model.model_validate_json(
                json.dumps(case["input"], allow_nan=False)
            ).model_dump(mode="json")
            if case["driver"] == "model":
                observed = output
                matched = json.dumps(observed, sort_keys=True) == json.dumps(
                    expected, sort_keys=True
                )
            else:
                observed = {"admitted": True, "value": output[case["field"]]}
                matched = json.dumps(observed, sort_keys=True) == json.dumps(
                    expected, sort_keys=True
                )
            status = "PASS" if matched else "FAIL"
        except ValidationError as error:
            errors = [
                {"loc": list(e["loc"]), "type": e["type"]} for e in error.errors()
            ]
            observed = {"admitted": False, "errors": errors}
            matched = (
                case["driver"] == "field"
                and expected.get("admitted") is False
                and any(
                    e["loc"]
                    and e["loc"][0] == expected["field"]
                    and e["type"] in expected["error_codes"]
                    for e in errors
                )
                and all(e["loc"] and e["loc"][0] == expected["field"] for e in errors)
            )
            status = "EXPECTED_REJECTION" if matched else "FAIL"
        except Exception as error:  # noqa: BLE001 - never relabel programming errors
            observed, status = {"unexpected_exception": type(error).__name__}, "FAIL"
    return {**case, "observed": observed, "status": status}


def aggregate(baseline, previous, receipts):
    counts = Counter(row["status"] for row in baseline["rows"])
    index = {row["id"]: row for row in baseline["rows"]}
    linked = {}
    seen = set()
    for receipt in previous + receipts:
        op.require(receipt["case_id"] not in seen, "Duplicate receipt")
        seen.add(receipt["case_id"])
        op.require(
            receipt["status"] in ("PASS", "EXPECTED_REJECTION", "FAIL"),
            "Invalid receipt state",
        )
        for identifier in receipt["obligations"]:
            op.require(
                identifier in index
                and index[identifier]["status"] == "NOT_RUN"
                and identifier not in linked,
                "Unknown, previously verified or duplicate obligation",
            )
            linked[identifier] = receipt["status"]
            counts["NOT_RUN"] -= 1
            counts[receipt["status"]] += 1
    verified = counts["PASS"] + counts["EXPECTED_REJECTION"]
    return {
        "total": 8385,
        "verified": verified,
        "percent": verified * 100 / 8385,
        "counts": dict(counts),
        "executed_incremental_cases": len(seen),
        "unique_new_cases": sum(bool(r["obligations"]) for r in previous + receipts),
        "regression_cases": sum(not r["obligations"] for r in previous + receipts),
        "linked_obligations": linked,
        "new_cases": len(receipts),
        "new_obligations": sum(len(r["obligations"]) for r in receipts),
        "case_counts": dict(Counter(r["status"] for r in receipts)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run"))
    for name in (
        "wheel",
        "baseline",
        "inventory",
        "seed-catalog",
        "previous",
        "catalog",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--previous-sha256", required=True)
    parser.add_argument("--catalog-sha256")
    args = parser.parse_args()
    op.require(
        op.digest(args.baseline) == BASELINE
        and op.digest(args.seed_catalog) == SEEDS
        and op.digest(args.previous) == args.previous_sha256,
        "Input receipt identity changed",
    )
    baseline, seeds, previous = (
        op.read(args.baseline),
        op.read(args.seed_catalog),
        op.read(args.previous),
    )
    op.baseline_identity(baseline, WHEEL)
    op.require(
        previous["package"]["wheel_sha256"] == WHEEL,
        "Previous increment belongs to another wheel",
    )
    op.summarize(baseline["rows"], previous["receipts"])
    import equiframe as ef

    package = op.identity(args.wheel, WHEEL, Path(__file__).resolve().parents[1])
    if args.mode == "plan":
        catalog = prepare(
            op.read(args.inventory), baseline["rows"], seeds, previous["receipts"], ef
        )
        aggregate(
            baseline,
            previous["receipts"],
            [{**c, "status": "PASS"} for c in catalog["cases"]],
        )
        write(args.catalog, catalog)
        print(
            json.dumps(
                {
                    "planned_cases": len(catalog["cases"]),
                    "planned_obligations": sum(
                        len(c["obligations"]) for c in catalog["cases"]
                    ),
                    "catalog_sha256": op.digest(args.catalog),
                    "executed": False,
                }
            )
        )
        return 0
    op.require(
        args.catalog_sha256 and op.digest(args.catalog) == args.catalog_sha256,
        "Frozen execution catalog changed",
    )
    catalog = op.read(args.catalog)
    op.require(
        catalog["wheel_sha256"] == WHEEL
        and catalog["baseline_sha256"] == BASELINE
        and catalog["seed_catalog_sha256"] == SEEDS
        and catalog["obligation_ids_sha256"] == seeds["obligation_ids_sha256"],
        "Catalog binding differs",
    )
    aggregate(
        baseline,
        previous["receipts"],
        [{**c, "status": "PASS"} for c in catalog["cases"]],
    )
    args.output.mkdir(parents=True, exist_ok=False)
    receipts = [execute(case, ef) for case in catalog["cases"]]
    summary = aggregate(baseline, previous["receipts"], receipts)
    result = {
        "schema": "equiframe.option-boundary-result.v1",
        "candidate": "0.12.0a13",
        "package": package,
        "baseline_sha256": BASELINE,
        "seed_catalog_sha256": SEEDS,
        "previous_sha256": args.previous_sha256,
        "catalog_sha256": args.catalog_sha256,
        "tool_sha256": op.digest(Path(__file__)),
        "inventory_sha256": op.digest(args.inventory),
        "python": sys.version,
        "platform": platform.platform(),
        "optimized": bool(sys.flags.optimize),
        "human_review": False,
        "summary": summary,
        "receipts": receipts,
        "scope": catalog["scope"],
    }
    write(args.output / "result.json", result)
    print(json.dumps({k: v for k, v in summary.items() if k != "linked_obligations"}))
    return 1 if summary["case_counts"].get("FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
