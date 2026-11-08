"""Organize every acquired public export without inference or deduplication.

CSV tables keep every cell as text, including blank cells. XLSX files keep their
original bytes. JSON exports stay complete; their nested projections are made
by sercop_local_repository.py in separate source-hash directories.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SPEC = importlib.util.spec_from_file_location(
    "local_sources", Path(__file__).with_name("sercop_local_repository.py")
)
sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sources)
require, digest, write = sources.require, sources.digest, sources.write


def safe_member(directory, name):
    relative = PurePosixPath(name)
    require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and "\\" not in name
        and ":" not in name,
        "Unexpected archive member path",
    )
    target = directory.joinpath(*relative.parts).resolve()
    require(target.is_relative_to(directory.resolve()), "Member escapes destination")
    return target


def csv_rows(path):
    csv.field_size_limit(32 * 1024**2)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader)
        require(len(header) == len(set(header)) and all(header), "Ambiguous CSV header")
        for values in reader:
            # The official exports put empty physical lines between records.
            if not values:
                continue
            require(len(values) == len(header), "CSV width differs from header")
            yield dict(zip(header, values, strict=True))


def text_csv(path, output):
    import pyarrow as pa
    import pyarrow.parquet as pq

    require(not output.exists(), "Do not replace a previous CSV projection")
    output.parent.mkdir(parents=True, exist_ok=True)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream, strict=True))
    require(len(header) == len(set(header)) and all(header), "Ambiguous CSV header")
    schema = pa.schema([(column, pa.string()) for column in header])
    expected, count, pending = hashlib.sha256(), 0, []
    with pq.ParquetWriter(output, schema, compression="zstd") as writer:
        for row in csv_rows(path):
            expected.update((sources.exact_json(row) + "\n").encode("utf-8"))
            count += 1
            pending.append(row)
            if len(pending) == 4096:
                writer.write_table(pa.Table.from_pylist(pending, schema=schema))
                pending.clear()
        if pending:
            writer.write_table(pa.Table.from_pylist(pending, schema=schema))
    observed, read_count = hashlib.sha256(), 0
    for batch in pq.ParquetFile(output).iter_batches(batch_size=4096):
        for row in batch.to_pylist():
            observed.update((sources.exact_json(row) + "\n").encode("utf-8"))
            read_count += 1
    require(
        read_count == count and observed.digest() == expected.digest(),
        "CSV readback differs",
    )
    return {
        "rows": count,
        "columns": header,
        "physical_types": "all UTF8 text; empty cells remain empty text",
        "source_row_sha256": expected.hexdigest(),
        "full_readback_verified": True,
        "parquet_sha256": digest(output),
        "parquet_bytes": output.stat().st_size,
        "source_csv_sha256": digest(path),
    }


def organize(root):
    acquired = json.loads(
        (root / "03_metadatos/current-acquisition.json").read_text("utf-8")
    )
    require(
        len(acquired) == 39 and all(r["status"] == "PASS" for r in acquired),
        "Incomplete acquisition",
    )
    destination = root / "05_exports/consulta_20261012"
    require(not destination.exists(), "Do not replace export snapshot")
    destination.mkdir(parents=True)
    records = []
    for receipt in acquired:
        archive = (root / receipt["file"]).resolve()
        require(
            archive.is_relative_to(root.resolve())
            and digest(archive) == receipt["sha256"],
            "Source identity differs",
        )
        selection = receipt["selection"]
        month, kind = selection["month"], selection["format"]
        directory = destination / f"mes{month:02d}" / kind
        directory.mkdir(parents=True)
        with zipfile.ZipFile(archive) as bundle:
            require(bundle.testzip() is None, "Retained archive CRC differs")
            if kind == "xlsx":
                target = directory / f"sercop_2025_mes{month:02d}.xlsx"
                shutil.copyfile(archive, target)
                require(digest(target) == receipt["sha256"], "XLSX bytes differ")
                records.append(
                    {
                        "file": target.relative_to(root).as_posix(),
                        "source_sha256": receipt["sha256"],
                        "kind": kind,
                        "month": month,
                        "original_bytes": True,
                    }
                )
            else:
                require(
                    len(bundle.namelist()) == len(set(bundle.namelist())),
                    "Repeated archive member",
                )
                for member in bundle.infolist():
                    require(not member.is_dir(), "Unexpected directory member")
                    target = safe_member(directory, member.filename)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(member) as incoming, target.open("xb") as outgoing:
                        shutil.copyfileobj(incoming, outgoing, length=1024**2)
                    require(
                        target.stat().st_size == member.file_size,
                        "Extracted length differs",
                    )
                    record = {
                        "file": target.relative_to(root).as_posix(),
                        "sha256": digest(target),
                        "bytes": member.file_size,
                        "source_archive_sha256": receipt["sha256"],
                        "kind": kind,
                        "month": month,
                        "member": member.filename,
                    }
                    if kind == "csv":
                        output = directory / (target.stem + ".parquet")
                        record["projection"] = {
                            "file": output.relative_to(root).as_posix(),
                            **text_csv(target, output),
                        }
                    records.append(record)
        print(
            json.dumps({"phase": "exports", "month": month, "format": kind}), flush=True
        )
    catalog = {
        "schema": "equiframe.sercop-local-exports.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": records,
        "source_acquisition_sha256": digest(
            root / "03_metadatos/current-acquisition.json"
        ),
        "tool_sha256": digest(Path(__file__)),
        "raw_csv_not_normalized": True,
        "row_order_and_duplicates_preserved": True,
        "scientific_cohort_approved": False,
    }
    write(root / "03_metadatos/organized-exports.json", catalog)
    print(
        json.dumps(
            {
                "complete": True,
                "files": len(records),
                "csv_rows": sum(
                    r.get("projection", {}).get("rows", 0) for r in records
                ),
            }
        ),
        flush=True,
    )


def download_reference(root, url, receipts):
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    extension = Path(urllib.parse.urlsplit(url).path).suffix
    suffix = extension if extension in (".json", ".pdf", ".csv") else ".html"
    target = root / "06_referencias" / (key + suffix)
    target.parent.mkdir(parents=True, exist_ok=True)
    require(not target.exists(), "Do not overwrite reference snapshot")
    record = {
        "url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "NOT_ACQUIRED",
    }
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                url, headers={"User-Agent": "EquiFrame-local-data/20261012"}
            ),
            timeout=30,
        ) as response:
            payload = response.read(16 * 1024**2 + 1)
            require(
                response.status == 200 and len(payload) <= 16 * 1024**2,
                "Reference budget/status differs",
            )
            if suffix == ".json":
                require(
                    isinstance(json.loads(payload), (dict, list)),
                    "Reference JSON differs",
                )
            if suffix == ".pdf":
                require(payload.startswith(b"%PDF-"), "Reference is not PDF")
            target.write_bytes(payload)
            record.update(
                {
                    "status": "PASS",
                    "file": target.relative_to(root).as_posix(),
                    "bytes": len(payload),
                    "sha256": digest(target),
                    "response_url": response.url,
                    "content_type": response.headers.get("Content-Type"),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                }
            )
    except (OSError, ValueError) as error:
        record.update({"error": type(error).__name__, "detail": str(error)})
    receipts.append(record)
    return record


def references(root):
    archive = (
        root / "01_fuentes_originales/consulta_20261012/sercop_2025_mes00_json.zip"
    )
    stream = sources.source_packages(archive)
    try:
        _, _, package = next(stream)
        metadata = {key: value for key, value in package.items() if key != "releases"}
    finally:
        stream.close()
    write(
        root / "03_metadatos/current-json-package-metadata.json",
        json.loads(sources.exact_json(metadata)),
    )
    urls = [
        sources.ORIGIN + "datos-abiertos/",
        metadata["publicationPolicy"],
        metadata["license"],
        "https://standard.open-contracting.org/schema/1__1__5/release-schema.json",
        "https://standard.open-contracting.org/schema/1__1__5/release-package-schema.json",
        *metadata.get("extensions", []),
    ]
    receipts = []
    for url in dict.fromkeys(urls):
        record = download_reference(root, url, receipts)
        if record["status"] == "PASS" and url.endswith("/extension.json"):
            extension = json.loads((root / record["file"]).read_text("utf-8"))
            for name in extension.get("schemas", []):
                if isinstance(name, str):
                    download_reference(root, urllib.parse.urljoin(url, name), receipts)
    write(root / "03_metadatos/reference-acquisition.json", receipts)
    print(
        json.dumps(
            {
                "references": len(receipts),
                "pass": sum(r["status"] == "PASS" for r in receipts),
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("organize", "references"))
    parser.add_argument("--root", type=Path, default=sources.ROOT)
    args = parser.parse_args()
    require(args.root.is_dir(), "Source repository is missing")
    (organize if args.mode == "organize" else references)(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
