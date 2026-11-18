"""Preserve complete public SERCOP exports and expose all release collections.

This repository is a local consumer dataset, not the team's DW or an approved
scientific cohort. Every array occurrence keeps its source position. Numeric
tokens retain exact Decimal text and source type; raw archives remain intact.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import re
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "sercop_stream", Path(__file__).with_name("sercop_validation_workload.py")
)
if SPEC is None or SPEC.loader is None:
    raise ValueError("Original streaming reader unavailable")
streaming = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(streaming)
ORIGIN = "https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/"
ROOT = Path(__file__).resolve().parents[1] / "local-data/sercop/2025"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return streaming.digest(path)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(
            value, output, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        )
        output.write("\n")


def exact_json(value):
    """Independent JSON encoding; never convert a number to binary float."""
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if type(value) in (Decimal, int):
        require(type(value) is int or value.is_finite(), "Nonfinite source number")
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(exact_json(item) for item in value) + "]"
    require(isinstance(value, dict), "Unsupported source JSON value")
    return (
        "{"
        + ",".join(
            json.dumps(key, ensure_ascii=False) + ":" + exact_json(value[key])
            for key in sorted(value)
        )
        + "}"
    )


def row_json(row):
    """Byte-compatible canonical encoding for flat transport rows only."""
    require(
        all(
            type(key) is str and type(value) in (str, int, type(None))
            for key, value in row.items()
        ),
        "Transport row contains a non-flat or inferred scalar",
    )
    return json.dumps(
        row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def pointer(key):
    return str(key).replace("~", "~0").replace("/", "~1")


def fields(value, prefix=""):
    """Flatten scalars; array contents stay in payload and occurrence tables."""
    result = {}
    if not isinstance(value, dict):
        value = {"$value": value}
    for key, item in value.items():
        name = prefix + "/" + pointer(key)
        if isinstance(item, dict) and item:
            result.update(fields(item, name))
        elif isinstance(item, list):
            result[name] = (str(len(item)), "array_length")
        elif isinstance(item, dict):
            result[name] = ("{}", "empty_object")
        elif item is None:
            result[name] = (None, "null")
        elif type(item) is bool:
            result[name] = ("true" if item else "false", "boolean")
        elif type(item) in (Decimal, int):
            result[name] = (str(item), "number_exact_decimal_text")
        else:
            require(isinstance(item, str), "Unsupported scalar")
            result[name] = (item, "string")
    return result


def child_collections(value, path, collection, parent):
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = path + "/" + pointer(key)
            child_collection = collection + "/" + pointer(key)
            yield from child_collections(item, child_path, child_collection, parent)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            item_path = path + "/" + str(index)
            yield collection, item_path, parent, index, item
            yield from child_collections(item, item_path, collection + "/*", item_path)


def source_packages(archive):
    with zipfile.ZipFile(archive) as bundle:
        members = [m for m in bundle.infolist() if m.filename.endswith(".json")]
        require(len(members) == 1, "Expected one complete annual JSON member")
        with io.TextIOWrapper(
            bundle.open(members[0]), encoding="utf-8"
        ) as input_stream:
            for package_index, package in enumerate(streaming.packages(input_stream)):
                require(
                    isinstance(package.get("releases"), list), "Missing releases array"
                )
                yield members[0].filename, package_index, package


def rows(archive):
    for member, package_index, package in source_packages(archive):
        base = "/packages/" + str(package_index)
        metadata = {k: v for k, v in package.items() if k != "releases"}
        context = {
            "__source_member": member,
            "__package_index": package_index,
            "__ocid": None,
            "__release_id": None,
        }
        yield "packages", base, None, package_index, metadata, context
        for release_index, release in enumerate(package["releases"]):
            require(isinstance(release, dict), "Release must be an object")
            path = base + "/releases/" + str(release_index)
            context = {
                **context,
                "__ocid": release.get("ocid"),
                "__release_id": release.get("id"),
            }
            require(
                context["__ocid"] is None or isinstance(context["__ocid"], str),
                "OCID type",
            )
            require(
                context["__release_id"] is None
                or isinstance(context["__release_id"], str),
                "Release ID type",
            )
            yield "releases", path, base, release_index, release, context
            for collection, child_path, parent, index, item in child_collections(
                release, path, "releases", path
            ):
                yield collection, child_path, parent, index, item, context


def preserve(workspace, root):
    names = ("releases_2025.zip", "releases_2025_enero.zip")
    copied = []
    for name in names:
        original = workspace / "avance_95_20261011" / name
        receipt_path = original.with_name(name + ".receipt.json")
        receipt = json.loads(receipt_path.read_text("utf-8"))
        require(digest(original) == receipt["sha256"], "Original source differs")
        target = root / "01_fuentes_originales/snapshot_20261010" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        require(not target.exists(), "Preserve existing repository snapshot")
        shutil.copyfile(original, target)
        shutil.copyfile(receipt_path, target.with_name(name + ".receipt.json"))
        require(digest(target) == receipt["sha256"], "Copy differs")
        copied.append(
            {
                "file": target.relative_to(root).as_posix(),
                "sha256": digest(target),
                "bytes": target.stat().st_size,
                "original_receipt": receipt,
            }
        )
    evidence = root / "04_evidencias"
    evidence.mkdir(parents=True, exist_ok=True)
    for name in (
        "sercop-2025-inventory.json",
        "sercop-2025-enero-inventory.json",
        "sercop-pilot-protocol.json",
        "sercop-probe.json",
        "sercop-acquisition.json",
    ):
        original = workspace / "avance_95_20261011" / name
        if original.is_file():
            shutil.copyfile(original, evidence / name)
    for name in (
        "SERCOP_PUBLIC_PILOT_20261011.md",
        "SERCOP_ANNUAL_ENGINEERING_20261011.md",
        "SERCOP_ANNUAL_VM_20261011.md",
        "SERCOP_ANNUAL_VM_RESULT_20261011.json",
    ):
        original = Path(__file__).resolve().parents[1] / "docs" / name
        if original.is_file():
            shutil.copyfile(original, evidence / name)
    write(root / "03_metadatos/preserved-sources.json", copied)
    print(
        json.dumps({"preserved_archives": len(copied), "root": str(root)}), flush=True
    )


def acquire(root, formats, months):
    directory = root / "01_fuentes_originales/consulta_20261012"
    directory.mkdir(parents=True, exist_ok=True)
    receipts = []
    for month in months:
        for kind in formats:
            target = directory / f"sercop_2025_mes{month:02d}_{kind}.zip"
            receipt_path = target.with_name(target.name + ".receipt.json")
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text("utf-8"))
                require(
                    receipt.get("status") != "PASS"
                    or digest(target) == receipt["sha256"],
                    "Retained download differs",
                )
                receipts.append(receipt)
                continue
            url = ORIGIN + f"download?type={kind}&year=2025&month={month}&method=all"
            receipt = {
                "url": url,
                "selection": {
                    "year": 2025,
                    "month": month,
                    "method": "all",
                    "format": kind,
                },
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "NOT_ACQUIRED",
            }
            partial = target.with_name(target.name + ".part")
            require(not partial.exists(), "Keep earlier partial download")
            start = time.monotonic()
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": "EquiFrame-local-data/20261012"}
                )
                with urllib.request.urlopen(request, timeout=45) as response:
                    require(
                        response.status == 200 and response.url.startswith(ORIGIN),
                        "Official origin/status differs",
                    )
                    receipt["headers"] = {
                        k.lower(): v
                        for k, v in response.headers.items()
                        if k.lower()
                        in {
                            "content-type",
                            "content-length",
                            "content-disposition",
                            "last-modified",
                            "etag",
                            "date",
                        }
                    }
                    count = 0
                    with partial.open("xb") as output:
                        while block := response.read(1024**2):
                            count += len(block)
                            require(
                                count <= 2 * 1024**3
                                and shutil.disk_usage(root).free >= 10 * 1024**3,
                                "Local storage budget reached; partial preserved",
                            )
                            output.write(block)
                    length = int(response.headers.get("Content-Length", "0"))
                    require(not length or length == count, "Incomplete download")
                require(
                    zipfile.is_zipfile(partial),
                    "Official response is not the offered ZIP",
                )
                with zipfile.ZipFile(partial) as bundle:
                    require(bundle.testzip() is None, "Archive CRC mismatch")
                    receipt["members"] = [
                        {"name": m.filename, "bytes": m.file_size}
                        for m in bundle.infolist()
                    ]
                partial.rename(target)
                receipt.update(
                    {
                        "status": "PASS",
                        "file": target.relative_to(root).as_posix(),
                        "bytes": count,
                        "sha256": digest(target),
                        "zip_crc_verified": True,
                    }
                )
            except (OSError, ValueError, zipfile.BadZipFile) as error:
                receipt.update(
                    {
                        "error": type(error).__name__,
                        "detail": str(error),
                        "partial_file": partial.relative_to(root).as_posix()
                        if partial.exists()
                        else None,
                    }
                )
            receipt["elapsed_seconds"] = round(time.monotonic() - start, 3)
            write(receipt_path, receipt)
            receipts.append(receipt)
            print(
                json.dumps(
                    {
                        "month": month,
                        "format": kind,
                        "status": receipt["status"],
                        "bytes": receipt.get("bytes"),
                        "detail": receipt.get("detail"),
                    }
                ),
                flush=True,
            )
    write(root / "03_metadatos/current-acquisition.json", receipts)


def build(archive, root, *, batch_rows=4096):
    import pyarrow as pa
    import pyarrow.parquet as pq

    require(
        type(batch_rows) is int and 1 <= batch_rows <= 100000,
        "Invalid transport batch size",
    )
    archive_sha = digest(archive)
    directory = root / "02_tablas" / archive_sha[:16]
    require(not directory.exists(), "Do not replace an earlier table snapshot")
    directory.mkdir(parents=True)
    schemas, counts, types = {}, Counter(), {}
    scalar_count = 0
    for collection, _, _, _, value, _ in rows(archive):
        counts[collection] += 1
        mapped = fields(value)
        schemas.setdefault(collection, set()).update(mapped)
        typed = types.setdefault(collection, {})
        for key, (_, kind) in mapped.items():
            typed.setdefault(key, Counter())[kind] += 1
        scalar_count += len(mapped)
    print(
        json.dumps(
            {
                "phase": "inventory",
                "collections": len(counts),
                "rows": sum(counts.values()),
                "releases": counts["releases"],
                "awards": counts["releases/awards"],
            }
        ),
        flush=True,
    )
    writers, buffers, files, written = {}, {}, {}, Counter()
    expected_hashes = {collection: hashlib.sha256() for collection in schemas}
    common = [
        ("__source_sha256", pa.string()),
        ("__source_member", pa.string()),
        ("__package_index", pa.int64()),
        ("__ocid", pa.string()),
        ("__release_id", pa.string()),
        ("__row_path", pa.string()),
        ("__parent_row_path", pa.string()),
        ("__row_index", pa.int64()),
        ("__payload_json", pa.string()),
    ]
    for collection, keys in schemas.items():
        name = (
            re.sub(r"[^a-zA-Z0-9_-]", "_", collection)[:70]
            + "-"
            + hashlib.sha256(collection.encode()).hexdigest()[:12]
        )
        path = directory / (name + ".parquet")
        schema = pa.schema(
            [
                *common,
                *[(key, pa.string()) for key in sorted(keys)],
                *[("@type:" + key, pa.string()) for key in sorted(keys)],
            ]
        )
        writers[collection] = pq.ParquetWriter(path, schema, compression="zstd")
        buffers[collection] = []
        files[collection] = path

    def flush(collection):
        pending = buffers[collection]
        if pending:
            table = pa.Table.from_pylist(pending, schema=writers[collection].schema)
            writers[collection].write_table(table)
            written[collection] += len(pending)
            pending.clear()

    try:
        for collection, path, parent, index, value, context in rows(archive):
            row = {
                **context,
                "__source_sha256": archive_sha,
                "__row_path": path,
                "__parent_row_path": parent,
                "__row_index": index,
                "__payload_json": exact_json(value),
            }
            mapped = fields(value)
            for key in schemas[collection]:
                item, kind = mapped.get(key, (None, "missing"))
                row[key], row["@type:" + key] = item, kind
            expected_hashes[collection].update((row_json(row) + "\n").encode("utf-8"))
            buffers[collection].append(row)
            if len(buffers[collection]) >= batch_rows:
                flush(collection)
        for collection in writers:
            flush(collection)
    finally:
        for writer in writers.values():
            writer.close()
    require(written == counts, "Output collection counts differ")
    records = []
    for collection, path in files.items():
        meta = pq.ParquetFile(path)
        require(
            meta.metadata.num_rows == counts[collection],
            "Parquet readback count differs",
        )
        read_rows = 0
        observed_hash = hashlib.sha256()
        for batch in meta.iter_batches(batch_size=batch_rows):
            for row in batch.to_pylist():
                observed_hash.update((row_json(row) + "\n").encode("utf-8"))
                value = json.loads(
                    row["__payload_json"], parse_int=Decimal, parse_float=Decimal
                )
                mapped = fields(value)
                require(
                    row["__source_sha256"] == archive_sha, "Readback provenance differs"
                )
                for key in schemas[collection]:
                    expected, kind = mapped.get(key, (None, "missing"))
                    require(
                        row[key] == expected and row["@type:" + key] == kind,
                        "Scalar/type readback differs",
                    )
                read_rows += 1
        require(read_rows == counts[collection], "Full Parquet readback differs")
        require(
            observed_hash.hexdigest() == expected_hashes[collection].hexdigest(),
            "Source-constructed complete row oracle differs",
        )
        records.append(
            {
                "collection": collection,
                "file": path.relative_to(root).as_posix(),
                "rows": read_rows,
                "size_bytes": path.stat().st_size,
                "sha256": digest(path),
                "columns": meta.schema_arrow.names,
                "source_constructed_rows_sha256": expected_hashes[
                    collection
                ].hexdigest(),
                "source_types": {
                    key: dict(value) for key, value in types[collection].items()
                },
            }
        )
    report = {
        "schema": "equiframe.sercop-local-repository.v1",
        "source_sha256": archive_sha,
        "tool_sha256": digest(Path(__file__)),
        "batch_rows": batch_rows,
        "row_hash_encoder": "stdlib JSON for strict flat scalars, byte-compatible with original exact_json row encoding",
        "source_archive": str(archive.resolve()),
        "packages": counts["packages"],
        "releases": counts["releases"],
        "award_occurrences": counts["releases/awards"],
        "total_occurrence_rows": sum(counts.values()),
        "scalar_occurrences": scalar_count,
        "collection_count": len(records),
        "tables": records,
        "full_readback_verified": True,
        "source_numbers_converted_to_float": False,
        "duplicates_dropped": False,
        "scientific_cohort_or_training_support_approved": False,
        "representation": "Source numeric/boolean/string scalars use exact text plus @type; null and missing remain distinct. All payload JSON and array positions retained.",
        "limits": "Consumer occurrence tables, not compiled OCDS, the team's DW, financial normality or approved scientific labels.",
    }
    write(directory / "catalog.json", report)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "collection_count",
                    "packages",
                    "releases",
                    "award_occurrences",
                    "total_occurrence_rows",
                    "full_readback_verified",
                )
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preserve", "acquire", "build"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--workspace", type=Path, default=ROOT.parents[3])
    parser.add_argument("--archive", type=Path)
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=("json", "csv", "xlsx"),
        default=["json", "csv", "xlsx"],
    )
    parser.add_argument("--months", nargs="+", type=int, default=list(range(13)))
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    require(
        all(0 <= month <= 12 for month in args.months), "Month selector must be0..12"
    )
    if args.mode == "preserve":
        preserve(args.workspace, args.root)
    elif args.mode == "acquire":
        acquire(args.root, args.formats, args.months)
    else:
        require(args.archive is not None, "Complete archive required")
        build(args.archive, args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
