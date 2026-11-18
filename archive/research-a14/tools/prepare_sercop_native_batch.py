"""Execute bounded native controls from pinned annual candidate shards.

These are proposed engineering profiles, not confirmed normal training data.
The three implementations use owned code; input JSON cannot select callbacks,
SQL, features, rules, labels, partitions or an executable model.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from equiframe._regular_io import (
    local_input_path,
    new_directory_path,
    open_regular_file,
    regular_directory,
    regular_files,
)
from equiframe.errors import EquiFrameError

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3"
FAMILIES = ("nulls_types", "joins", "aggregations")
ENGINES = ("pandas", "polars", "duckdb")
MAX_UNITS = 256
MAX_OUTPUT_BYTES = 1024**3
MAX_OUTPUT_FILES = 100000
DISK_RESERVE = 2 * 1024**3


def require(condition, code):
    if not condition:
        raise ValueError(code)


def owned(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "owned_helper_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, allow_nan=False, indent=2)
        stream.write("\n")


def decode_unit(unit, reader):
    """Recheck a compiled unit without repairing monetary or absence semantics."""
    require(isinstance(unit, dict), "invalid_unit")
    ocid, ordinal, scale = (
        unit.get("ocid"),
        unit.get("source_record_ordinal"),
        unit.get("decimal_scale"),
    )
    require(
        isinstance(ocid, str)
        and 1 <= len(ocid) <= 256
        and type(ordinal) is int
        and 0 <= ordinal < 250000
        and type(scale) is int
        and 0 <= scale <= 38,
        "invalid_unit_identity_or_scale",
    )
    require(
        unit.get("normality") == "UNREVIEWED"
        and type(unit.get("native_profiles_prepared")) is int
        and unit["native_profiles_prepared"] == 0
        and unit.get("dependencies") == ["ocid:" + ocid],
        "unit_provenance_or_review_state_differs",
    )
    date, date_state = unit.get("release_date"), unit.get("release_date_state")
    require(
        date_state in {"missing", "null", "present"}
        and (
            isinstance(date, str) and 1 <= len(date) <= 64
            if date_state == "present"
            else date is None
        ),
        "invalid_release_presence",
    )
    source = unit.get("awards")
    require(isinstance(source, list) and 1 <= len(source) <= 256, "unit_row_budget")
    rows, identities = [], set()
    for raw in source:
        require(isinstance(raw, dict), "invalid_award")
        identity = raw.get("award_id")
        require(
            set(raw) == set(reader.AWARD_COLUMNS)
            and raw.get("ocid") == ocid
            and isinstance(identity, str)
            and 1 <= len(identity) <= 256
            and identity not in identities,
            "ambiguous_award_identity_or_columns",
        )
        identities.add(identity)
        row = dict(raw)
        for key in ("currency", "amount"):
            state, value = row.get(key + "_state"), row[key]
            require(
                state in {"missing", "null", "present", "not_applicable"}
                and (
                    isinstance(value, str)
                    and (0 if key == "currency" else 1)
                    <= len(value)
                    <= (16 if key == "currency" else 128)
                    if state == "present"
                    else value is None
                ),
                "invalid_award_presence",
            )
        require(
            row.get("value_state") in {"missing", "null", "present"}
            and (
                row["currency_state"] != "not_applicable"
                and row["amount_state"] != "not_applicable"
                if row["value_state"] == "present"
                else row["currency_state"] == row["amount_state"] == "not_applicable"
            ),
            "invalid_value_presence",
        )
        if row["amount"] is not None:
            try:
                amount = Decimal(row["amount"])
            except ArithmeticError as error:
                raise ValueError("unsupported_money") from error
            require(
                amount.is_finite()
                and not (amount.is_signed() and amount.is_zero())
                and format(amount, "f") == row["amount"]
                and reader.scaled_digits(amount, scale) <= 38,
                "unsupported_money",
            )
            row["amount"] = amount
        rows.append(row)
    return rows, {"ocid": ocid, "release_date": date, "release_date_state": date_state}


def selected_units(cohort, manifest, offset, count, packet_io, reader, *, min_awards=1):
    """Hash every candidate shard, then select its fixed source-order interval."""
    require(
        type(offset) is int
        and offset >= 0
        and type(count) is int
        and 1 <= count <= MAX_UNITS,
        "invalid_batch_interval",
    )
    shards = manifest.get("candidate_shards")
    require(
        isinstance(shards, list) and 1 <= len(shards) <= 64, "invalid_shard_inventory"
    )
    require(
        type(min_awards) is int and 1 <= min_awards <= 256, "invalid_award_selector"
    )
    units, seen, total, eligible, previous = [], set(), 0, 0, -1
    for number, entry in enumerate(shards):
        require(isinstance(entry, dict), "invalid_shard_declaration")
        require(
            entry.get("file") == f"candidate-inputs-{number:03}.jsonl"
            and type(entry.get("records")) is int
            and 1 <= entry["records"] <= 10000
            and type(entry.get("bytes")) is int
            and 0 < entry["bytes"] <= 16 * 1024**2,
            "invalid_shard_declaration",
        )
        raw = packet_io.read_bytes(cohort, entry["file"], 16 * 1024**2)
        require(
            len(raw) == entry["bytes"]
            and hashlib.sha256(raw).hexdigest() == entry.get("sha256")
            and raw.endswith(b"\n"),
            "shard_identity_differs",
        )
        lines = raw.splitlines()
        require(len(lines) == entry["records"], "shard_record_count_differs")
        for line in lines:
            require(len(line) <= 256 * 1024, "unit_byte_budget")
            unit = strict_json(line)
            rows, release = decode_unit(unit, reader)
            ordinal = unit["source_record_ordinal"]
            require(
                ordinal > previous and release["ocid"] not in seen,
                "source_order_or_identity_differs",
            )
            previous = ordinal
            seen.add(release["ocid"])
            if len(rows) >= min_awards:
                if offset <= eligible < offset + count:
                    units.append(
                        (unit, rows, release, hashlib.sha256(line).hexdigest())
                    )
                eligible += 1
            total += 1
    require(total == manifest.get("candidate_ocid_units"), "candidate_count_differs")
    require(len(units) == count, "insufficient_candidate_units")
    return units


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("nonfinite_json")

    def number(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite_json")
        return result

    try:
        return json.loads(
            raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=number
        )
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError("invalid_json") from error


def unit_inputs(rows, release, scale, pa):
    schema = pa.schema(
        [
            ("ocid", pa.string()),
            ("award_id", pa.string()),
            ("currency", pa.string()),
            ("amount", pa.decimal128(38, scale)),
            ("value_state", pa.string()),
            ("currency_state", pa.string()),
            ("amount_state", pa.string()),
        ]
    )
    return pa.Table.from_pylist(rows, schema=schema), pa.Table.from_pylist(
        [release],
        schema=pa.schema(
            [
                ("ocid", pa.string()),
                ("release_date", pa.string()),
                ("release_date_state", pa.string()),
            ]
        ),
    )


def expected_rows(family, rows, release):
    if family == "nulls_types":
        return rows
    if family == "joins":
        return [
            dict(
                r,
                release_date=release["release_date"],
                release_date_state=release["release_date_state"],
            )
            for r in rows
        ]
    return [
        {"currency": currency, "award_count": count}
        for currency, count in Counter(r["currency"] for r in rows).items()
    ]


def plan_family(ef, pa, awards, releases, family, rows, release, number):
    expected = expected_rows(family, rows, release)
    schema = (
        awards.schema
        if family == "nulls_types"
        else pa.schema(
            [
                *awards.schema,
                ("release_date", pa.string()),
                ("release_date_state", pa.string()),
            ]
        )
        if family == "joins"
        else pa.schema([("currency", pa.string()), ("award_count", pa.int64())])
    )
    output_schema = ef.infer_diff_contract(schema).spec.contract.output
    inputs = (
        ef.infer_diff_contract(awards.schema).spec.contract.output.model_copy(
            update={"name": "awards"}
        ),
    )
    if family == "joins":
        inputs += (
            ef.infer_diff_contract(releases.schema).spec.contract.output.model_copy(
                update={"name": "releases"}
            ),
        )
    contract = ef.Contract(
        schema_version="1.0",
        contract_id=f"sercop.native-batch.{number}.{family}",
        revision=1,
        family=family,
        inputs=inputs,
        output=output_schema,
        preconditions=(),
        rules=(
            ef.RuleSpec(
                rule_id="schema",
                revision=1,
                specification=ef.SchemaCheck(table=output_schema.name),
                severity="error",
                required=True,
            ),
        ),
    )
    profile = ef.ProfileSpec(
        family=family,
        features=(
            ef.ProfileFeature(
                name="rows", metric="log_filas", table=output_schema.name
            ),
            ef.ProfileFeature(
                name="output_input",
                metric="razon_salida_entrada",
                table=output_schema.name,
                denominator_table="awards",
            )
            if family == "aggregations"
            else ef.ProfileFeature(
                name="missing_amount",
                metric="tasa_nulos",
                table=output_schema.name,
                columns=("amount",),
            ),
        ),
    )
    expected_values = [
        math.log1p(len(expected)),
        len(expected) / len(rows)
        if family == "aggregations"
        else sum(r["amount"] is None for r in rows) / len(rows),
    ]
    return (
        contract,
        profile,
        pa.Table.from_pylist(expected, schema=schema),
        expected_values,
    )


def footprint(directory):
    count = total = 0
    for path in directory.rglob("*"):
        require(
            not path.is_symlink()
            and not getattr(path.lstat(), "st_file_attributes", 0) & 0x400,
            "linked_output",
        )
        if path.is_file():
            count += 1
            total += path.stat().st_size
            require(
                count <= MAX_OUTPUT_FILES and total <= MAX_OUTPUT_BYTES,
                "batch_output_budget_exceeded",
            )
    return {"files": count, "bytes": total}


def compact_unit(output, unit):
    """Verify a complete byte archive before removing only our generated tree.

    The original prefix is retained for bounded restoration. Archived SDK URIs
    are not advertised as live files or a portable URI bundle.
    """
    output = regular_directory(output)
    unit = regular_directory(unit)
    require(
        unit.parent == output
        and unit.name.startswith("unit-")
        and len(unit.name) == 11
        and unit.name[5:].isdigit(),
        "generated_unit_outside_batch",
    )
    files = regular_files(unit)
    require(0 < len(files) <= 512, "unit_archive_file_budget")
    archive = output / (unit.name + ".zip")
    inventory, total = [], 0
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in files:
            with open_regular_file(path) as stream:
                raw = stream.read(64 * 1024**2 + 1)
            total += len(raw)
            require(total <= 64 * 1024**2, "unit_archive_byte_budget")
            name = path.relative_to(unit).as_posix()
            require(name != "closed-unit.json", "unit_archive_manifest_collision")
            inventory.append(
                {
                    "file": name,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
            zipped.writestr(name, raw)
        manifest = {
            "schema": "equiframe.sercop-closed-unit.v1",
            "original_prefix": str(unit),
            "files": inventory,
        }
        raw_manifest = (json.dumps(manifest, indent=2) + "\n").encode()
        zipped.writestr("closed-unit.json", raw_manifest)
    with open_regular_file(archive) as source, zipfile.ZipFile(source) as zipped:
        require(
            set(zipped.namelist())
            == {"closed-unit.json", *(r["file"] for r in inventory)}
            and len(zipped.namelist()) == len(inventory) + 1,
            "unit_archive_inventory_differs",
        )
        require(
            zipped.read("closed-unit.json") == raw_manifest,
            "unit_archive_manifest_differs",
        )
        for entry in inventory:
            info = zipped.getinfo(entry["file"])
            require(info.file_size == entry["bytes"], "unit_archive_size_differs")
            with zipped.open(entry["file"]) as member:
                raw = member.read(entry["bytes"] + 1)
            require(
                len(raw) == entry["bytes"]
                and hashlib.sha256(raw).hexdigest() == entry["sha256"],
                "unit_archive_bytes_differ",
            )
    # The validated new direct child is the sole removal target. On failure,
    # the generated originals remain. Inputs and other batches are outside it.
    require(
        regular_directory(unit).parent == regular_directory(output),
        "generated_unit_outside_batch",
    )
    shutil.rmtree(unit)
    with open_regular_file(archive) as source:
        digest = hashlib.sha256()
        for raw in iter(lambda: source.read(1024**2), b""):
            digest.update(raw)
    return {
        "file": archive.name,
        "bytes": archive.stat().st_size,
        "sha256": digest.hexdigest(),
        "uncompressed_files": len(inventory),
        "uncompressed_bytes": total,
        "original_prefix": str(unit),
    }


def prepare(
    cohort,
    manifest_sha256,
    binding_path,
    output,
    *,
    offset=0,
    count=16,
    compact=False,
    min_awards=1,
):
    require(sys.flags.isolated, "isolated_installed_interpreter_required")
    require(
        type(offset) is int
        and offset >= 0
        and type(count) is int
        and 1 <= count <= MAX_UNITS,
        "invalid_batch_interval",
    )
    packet_io = owned("owned_batch_io", ROOT / "tools/thesis_packet_io.py")
    require(type(compact) is bool, "invalid_compaction_option")
    require(
        type(min_awards) is int and 1 <= min_awards <= 256, "invalid_award_selector"
    )
    cohort = regular_directory(local_input_path(cohort))
    output = new_directory_path(local_input_path(output))
    require(
        not output.exists()
        and not output.is_relative_to(ROOT)
        and not output.is_relative_to(cohort),
        "new_private_output_required",
    )
    raw = packet_io.read_bytes(cohort, "cohort-proposal.json", 16 * 1024**2)
    require(
        hashlib.sha256(raw).hexdigest() == manifest_sha256,
        "cohort_manifest_identity_differs",
    )
    manifest = strict_json(raw)
    require(isinstance(manifest, dict), "invalid_cohort_manifest")
    require(
        manifest.get("schema") == "equiframe.sercop-cohort-proposal.v1"
        and manifest.get("source_sha256") == SOURCE_SHA256
        and manifest.get("status") == "PROPOSED"
        and manifest.get("normality_confirmed") is False
        and manifest.get("scientific_ready") is False,
        "unapproved_proposal_required",
    )
    binding_path = local_input_path(binding_path)
    regular_directory(binding_path.parent)
    binding = packet_io.read_json(binding_path.parent, binding_path.name)
    binder = owned(
        "owned_batch_binding", ROOT / "packages/equiframe/tools/compatibility_probe.py"
    )
    runtime = binder.runtime_binding(binding)
    code_files = [
        Path(__file__),
        ROOT / "tools/thesis_packet_io.py",
        ROOT / "tools/prepare_sercop_experiment.py",
        ROOT / "tools/sercop_validation_workload.py",
        ROOT / "packages/equiframe/tools/compatibility_probe.py",
    ]
    code_hashes = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in code_files
    }
    reader = owned("owned_batch_reader", ROOT / "tools/sercop_validation_workload.py")
    units = selected_units(
        cohort, manifest, offset, count, packet_io, reader, min_awards=min_awards
    )
    require(
        shutil.disk_usage(output.parent).free >= DISK_RESERVE + MAX_OUTPUT_BYTES,
        "insufficient_private_disk_reserve",
    )
    import equiframe as ef
    import pyarrow as pa

    implementation = owned(
        "owned_batch_implementations", ROOT / "tools/prepare_sercop_experiment.py"
    )
    from equiframe_benchmark.pilot import write_table

    output.mkdir()
    frozen = {
        "schema": "equiframe.sercop-native-batch-plan.v1",
        "status": "PROPOSED",
        "source_sha256": SOURCE_SHA256,
        "cohort_manifest_sha256": manifest_sha256,
        "core_wheel_sha256": binding["wheel_sha256"],
        "tool_hashes": code_hashes,
        "offset": offset,
        "count": count,
        "selection": "Fixed source-order interval among candidates meeting the declared input award-count selector; no outcome selection",
        "minimum_awards": min_awards,
        "families": list(FAMILIES),
        "engines": list(ENGINES),
        "dependencies": "Original OCID plus shared template:sercop-proposed-<family>; no groups split or renamed",
        "confirmed_normal_profiles": 0,
        "human_labels": None,
        "partitions": None,
        "planned_native_executions": count * 9,
        "compact_evidence": compact,
        "units": [
            {
                "ocid": u["ocid"],
                "source_record_ordinal": u["source_record_ordinal"],
                "compiled_unit_sha256": h,
            }
            for u, _, _, h in units
        ],
    }
    save(output / "plan.json", frozen)
    save(output / "runtime.json", runtime)
    policy = ef.ComparisonPolicy(
        physical_types="lossless",
        index="ignore",
        justification="Explicit OCID/award_id columns retain multiplicity; pandas index is transport metadata. Decimal scale and values remain exact.",
    )
    records, vectors, archives = [], {family: set() for family in FAMILIES}, []
    started = time.monotonic()
    for number, (unit, rows, release, _) in enumerate(units, offset):
        root = output / f"unit-{number:06}"
        root.mkdir()
        save(root / "compiled-unit.json", unit)
        awards, releases = unit_inputs(rows, release, unit["decimal_scale"], pa)
        write_table(awards, root / "awards.arrow")
        write_table(releases, root / "releases.arrow")
        for family in FAMILIES:
            contract, profile, expected, expected_values = plan_family(
                ef, pa, awards, releases, family, rows, release, number
            )
            reference = write_table(expected, root / (family + "-expected.arrow"))
            save(root / (family + "-contract.json"), contract.model_dump(mode="json"))
            save(
                root / (family + "-profile-spec.json"), profile.model_dump(mode="json")
            )
            transforms, transform_id = implementation.registry(
                family, "control", "", unit["decimal_scale"]
            )
            for engine in ENGINES:
                work = root / (family + "-" + engine)
                before = time.monotonic()
                result = ef.run_pipeline(
                    ef.PipelineSpec(
                        execution=ef.ExecutionPlan(
                            contract=contract,
                            engine=engine,
                            transformation_id=transform_id,
                            options=ef.ExecutionOptions(
                                timeout_seconds=120.0,
                                max_input_rows=512,
                                max_output_rows=512,
                                max_transport_bytes=16 * 1024**2,
                                duckdb_threads=1,
                            ),
                        ),
                        profile=profile,
                        comparison_reference="expected",
                        comparison_policy=policy,
                    ),
                    source=ef.LocalDataSource(
                        {
                            "awards": ef.ArrowInput(awards),
                            **(
                                {"releases": ef.ArrowInput(releases)}
                                if family == "joins"
                                else {}
                            ),
                        }
                    ),
                    registry=transforms,
                    comparison=reference,
                    work_dir=work,
                )
                require(
                    result.complete
                    and result.execution is not None
                    and result.execution.state == "completed"
                    and result.execution.output is not None,
                    "native_execution_incomplete",
                )
                require(
                    result.comparison is not None
                    and result.comparison.complete
                    and result.comparison.state == "equivalent"
                    and result.comparison.counts.difference_records == 0,
                    "native_expected_disagrees",
                )
                require(
                    result.rules is not None
                    and result.rules.complete
                    and result.rules.decision == "no_alert",
                    "required_schema_rules_incomplete",
                )
                require(
                    result.profile is not None and result.profile.complete,
                    "native_profile_incomplete",
                )
                values = [o.value for o in result.profile.vector.observations]
                require(
                    len(values) == len(expected_values)
                    and all(
                        a is not None
                        and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
                        for a, b in zip(values, expected_values, strict=True)
                    ),
                    "independent_feature_values_disagree",
                )
                vectors[family].add(tuple(values))
                record = {
                    "family": family,
                    "engine": engine,
                    "ocid": unit["ocid"],
                    "source_record_ordinal": unit["source_record_ordinal"],
                    "dependencies": [
                        "ocid:" + unit["ocid"],
                        "template:sercop-proposed-" + family,
                    ],
                    "normality": "UNREVIEWED",
                    "oracle_label": None,
                    "partition": None,
                    "pipeline": result.model_dump(mode="json"),
                    "expected_features": expected_values,
                }
                save(work / "control.json", record)
                raw = (work / "control.json").read_bytes()
                records.append(
                    {
                        "file": (work / "control.json").relative_to(output).as_posix(),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "family": family,
                        "engine": engine,
                        "seconds": time.monotonic() - before,
                    }
                )
        if compact:
            archived = compact_unit(output, root)
            archives.append(archived)
            for record in records[-9:]:
                record["archived_in"] = archived["file"]
                record["member"] = (
                    Path(record["file"]).relative_to(root.name).as_posix()
                )
        footprint(output)
        require(
            shutil.disk_usage(output).free >= DISK_RESERVE,
            "private_disk_reserve_exhausted",
        )
        print(
            json.dumps(
                {
                    "prepared_units": number - offset + 1,
                    "native_executions": len(records),
                }
            ),
            flush=True,
        )
    require(
        all(
            hashlib.sha256(p.read_bytes()).hexdigest()
            == code_hashes[p.relative_to(ROOT).as_posix()]
            for p in code_files
        ),
        "owned_code_changed_during_batch",
    )
    require(
        hashlib.sha256(
            packet_io.read_bytes(cohort, "cohort-proposal.json", 16 * 1024**2)
        ).hexdigest()
        == manifest_sha256,
        "cohort_manifest_changed_during_batch",
    )
    for entry in manifest["candidate_shards"]:
        raw = packet_io.read_bytes(cohort, entry["file"], 16 * 1024**2)
        require(
            len(raw) == entry["bytes"]
            and hashlib.sha256(raw).hexdigest() == entry["sha256"],
            "cohort_shard_changed_during_batch",
        )
    result = {
        "schema": "equiframe.sercop-native-batch-result.v1",
        "complete": True,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10 compatibility
        "cohort_manifest_sha256": manifest_sha256,
        "source_sha256": SOURCE_SHA256,
        "core_wheel_sha256": binding["wheel_sha256"],
        "plan_sha256": hashlib.sha256((output / "plan.json").read_bytes()).hexdigest(),
        "native_executions": len(records),
        "candidate_ocid_units": count,
        "offset": offset,
        "distinct_numeric_vectors_per_family": {
            family: len(values) for family, values in vectors.items()
        },
        "normality_confirmed": False,
        "confirmed_normal_profiles": 0,
        "n_fit_accredited_per_family": {family: 0 for family in FAMILIES},
        "scientific_ready": False,
        "human_labels": None,
        "final_partitions": None,
        "seconds": time.monotonic() - started,
        "footprint": footprint(output),
        "records": records,
        "archives": archives,
    }
    save(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--count", type=int, default=16)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--min-awards", type=int, default=1)
    args = parser.parse_args()
    try:
        result = prepare(
            args.cohort,
            args.manifest_sha256,
            args.binding,
            args.output,
            offset=args.offset,
            count=args.count,
            compact=args.compact,
            min_awards=args.min_awards,
        )
    except (ValueError, TypeError, OSError, EquiFrameError) as failure:
        parser.exit(
            2, "Native batch preparation failed: " + type(failure).__name__ + "\n"
        )
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "native_executions",
                    "candidate_ocid_units",
                    "distinct_numeric_vectors_per_family",
                    "scientific_ready",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
