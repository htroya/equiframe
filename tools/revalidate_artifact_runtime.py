"""Freeze artifact-store behavior expectations and bind them to an installed SDK.

Only named API/method/parameter obligations are covered. This does not infer
coverage from imports, change denominators or claim scientific acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import equiframe as ef
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def plan():
    payload = b'{"amount":"12.30","missing":null}\n'
    digest = hashlib.sha256(payload).hexdigest()
    prefix = "parameter:equiframe."
    return {
        "scope": "Public local artifact API and typed parameter rejection; no science",
        "cases": [
            {
                "id": "artifact.public.roundtrip",
                "operation": "roundtrip",
                "input": {"payload_hex": payload.hex()},
                "expected": {
                    "sha256": digest,
                    "bytes": len(payload),
                    "format": "json",
                    "media_type": "application/json",
                    "exclusive": True,
                },
                "obligations": [
                    "api:equiframe.LocalArtifactStore",
                    "api:equiframe.ArtifactStore",
                    "method:equiframe.LocalArtifactStore.put",
                    "method:equiframe.LocalArtifactStore.get",
                    "method:equiframe.ArtifactStore.put",
                    "method:equiframe.ArtifactStore.get",
                    prefix + "LocalArtifactStore:root:class:0",
                    prefix + "LocalArtifactStore.put:path:class:0",
                    prefix + "LocalArtifactStore.put:media_type:class:0",
                    prefix + "LocalArtifactStore.get:ref:class:0",
                    prefix + "LocalArtifactStore.get:destination:class:0",
                    prefix + "ArtifactStore.put:path:class:0",
                    prefix + "ArtifactStore.put:media_type:class:0",
                    prefix + "ArtifactStore.get:ref:class:0",
                    prefix + "ArtifactStore.get:destination:class:0",
                ],
            },
            *[
                {
                    "id": f"artifact.invalid.{operation}.{category}",
                    "operation": operation,
                    "input": {"bad": None if category == "invalid" else {"wrong": 1}},
                    "expected_error": expected_error,
                    "obligations": [
                        prefix + owner + ":" + parameter + ":" + category,
                        *(
                            [prefix + interface + ":" + parameter + ":" + category]
                            if interface is not None
                            else []
                        ),
                    ],
                }
                for operation, owner, interface, parameter, expected_error in (
                    ("root", "LocalArtifactStore", None, "root", "TypeError"),
                    (
                        "put_path",
                        "LocalArtifactStore.put",
                        "ArtifactStore.put",
                        "path",
                        "TypeError",
                    ),
                    (
                        "media",
                        "LocalArtifactStore.put",
                        "ArtifactStore.put",
                        "media_type",
                        "ValidationError",
                    ),
                    (
                        "ref",
                        "LocalArtifactStore.get",
                        "ArtifactStore.get",
                        "ref",
                        "ValidationError",
                    ),
                    (
                        "destination",
                        "LocalArtifactStore.get",
                        "ArtifactStore.get",
                        "destination",
                        "TypeError",
                    ),
                )
                for category in ("invalid", "class:1")
            ],
        ],
    }


def execute(case, directory):
    directory.mkdir()
    source = directory / "source.json"
    payload = b'{"amount":"12.30","missing":null}\n'
    source.write_bytes(payload)
    operation = case["operation"]
    if operation == "root":
        ef.LocalArtifactStore(case["input"]["bad"])
    else:
        store: ef.ArtifactStore = ef.LocalArtifactStore(directory / "store")
        if operation == "put_path":
            store.put(case["input"]["bad"], media_type="application/json")
        elif operation == "media":
            store.put(source, media_type=case["input"]["bad"])
        elif operation in {"ref", "destination"}:
            ref = ef.ArtifactRef(
                schema_version="1.0",
                uri=source.as_uri(),
                sha256=hashlib.sha256(payload).hexdigest(),
                format="json",
                media_type="application/json",
                size_bytes=len(payload),
            )
            store.get(
                case["input"]["bad"] if operation == "ref" else ref,
                case["input"]["bad"]
                if operation == "destination"
                else directory / "copy.json",
            )
        else:
            ref = store.put(source, media_type="application/json")
            target = directory / "copy.json"
            returned = store.get(ref, target)
            require(returned == target, "Public copy return path differs")
            require(
                source.read_bytes()
                == target.read_bytes()
                == bytes.fromhex(case["input"]["payload_hex"]),
                "Artifact bytes were changed",
            )
            exclusive = False
            try:
                store.get(ref, target)
            except ef.ArtifactIOError:
                exclusive = True
            require(not list(directory.rglob("*.part")), "Partial copy was retained")
            return {
                "sha256": ref.sha256,
                "bytes": ref.size_bytes,
                "format": ref.format,
                "media_type": ref.media_type,
                "exclusive": exclusive,
            }
    raise AssertionError("Invalid artifact parameter was admitted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(sys.flags.isolated, "Use an isolated installed interpreter")
    reader_spec = importlib.util.spec_from_file_location(
        "owned_artifact_inputs", ROOT / "tools/revalidate_root_contexts.py"
    )
    require(
        reader_spec is not None and reader_spec.loader is not None,
        "Safe input reader missing",
    )
    reader = importlib.util.module_from_spec(reader_spec)
    reader_spec.loader.exec_module(reader)
    raw, baseline = reader.bounded_json(args.baseline)
    require(
        hashlib.sha256(raw).hexdigest() == args.baseline_sha256,
        "Baseline identity differs",
    )
    require(
        baseline["candidate"] == ef.__version__ == "0.12.0a14"
        and baseline["total"] == 8438,
        "Full A14 baseline required",
    )
    require(baseline["optimized"] is (not __debug__), "Baseline execution mode differs")
    reader.require_ordinary_parents(args.output.absolute().parent)
    require(
        not args.output.exists() and not args.output.absolute().is_relative_to(ROOT),
        "Use a new private output directory",
    )
    specification = importlib.util.spec_from_file_location(
        "owned_artifact_binding",
        ROOT / "packages/equiframe/tools/compatibility_probe.py",
    )
    require(
        specification is not None and specification.loader is not None,
        "Binding tool missing",
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    _, binding = reader.bounded_json(args.binding)
    require(
        binding["wheel_sha256"] == baseline["wheel_sha256"],
        "Binding and baseline differ",
    )
    identity = module.runtime_binding(binding)
    require(
        identity["origin"] == str(Path(ef.__file__).resolve()), "SDK location changed"
    )
    planned = plan()
    pending = {r["id"] for r in baseline["rows"] if r["status"] == "NOT_RUN"}
    selected = [i for c in planned["cases"] for i in c["obligations"]]
    require(
        len(selected) == len(set(selected)) and set(selected) <= pending,
        "Runtime obligations overlap or are outside the baseline",
    )
    args.output.mkdir()
    frozen = (json.dumps(planned, indent=2, allow_nan=False) + "\n").encode()
    (args.output / "catalog.json").write_bytes(frozen)
    receipts = []
    for position, case in enumerate(planned["cases"]):
        observed = None
        error = None
        try:
            observed = execute(case, args.output / f"case-{position:03}")
            status = "PASS" if observed == case.get("expected") else "FAIL"
        except (TypeError, ValidationError) as failure:
            error = type(failure).__name__
            status = (
                "EXPECTED_REJECTION" if error == case.get("expected_error") else "FAIL"
            )
        except (
            ef.ArtifactIntegrityError,
            ef.ArtifactIOError,
            ef.CapabilityError,
            OSError,
            ValueError,
            RuntimeError,
            AttributeError,
            AssertionError,
        ) as failure:
            error = type(failure).__name__
            status = "FAIL"
        receipts.append(
            {
                "case_id": case["id"],
                "status": status,
                "observed": observed,
                "error": error,
                "obligations": case["obligations"],
            }
        )
    require(
        (args.output / "catalog.json").read_bytes() == frozen,
        "Expected catalogue changed",
    )
    result = {
        "source_commit": baseline["source_commit"],
        "wheel_sha256": baseline["wheel_sha256"],
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "baseline_sha256": args.baseline_sha256,
        "catalog_sha256": hashlib.sha256(frozen).hexdigest(),
        "optimized": not __debug__,
        "counts": dict(Counter(r["status"] for r in receipts)),
        "receipts": receipts,
        "scientific_credit": False,
    }
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"counts": result["counts"], "obligations": len(selected)}))
    return int(bool(result["counts"].get("FAIL")))


if __name__ == "__main__":
    raise SystemExit(main())
