"""Inventory an identified official SERCOP export without deriving scientific labels.

Only ZIP/JSON data are read. No archive member is extracted or executed.
An official year filter is not assumed to be the publication/award cohort.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TextIO


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError(f"Nonfinite JSON number: {value}")


def packages(stream: TextIO, chunk_size: int = 65536, max_item_chars: int = 16_777_216):
    """Read a top-level JSON array incrementally, retaining exact decimal tokens."""
    if chunk_size < 1 or max_item_chars < 1:
        raise ValueError("Positive stream budgets required")
    decoder = json.JSONDecoder(
        object_pairs_hook=_pairs, parse_float=Decimal, parse_constant=_nonfinite
    )
    buffer, eof = "", False

    def fill() -> None:
        nonlocal buffer, eof
        chunk = stream.read(chunk_size)
        eof = not chunk
        buffer += chunk

    def peek() -> str:
        nonlocal buffer
        while True:
            buffer = buffer.lstrip()
            if buffer or eof:
                return buffer[:1]
            fill()

    if peek() != "[":
        raise ValueError("Official export must be a top-level package array")
    buffer = buffer[1:]
    if peek() == "]":
        buffer = buffer[1:]
    else:
        while True:
            while True:
                peek()
                try:
                    item, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError as error:
                    if eof:
                        raise ValueError(
                            "Incomplete or invalid JSON package"
                        ) from error
                    if len(buffer) >= max_item_chars:
                        raise ValueError(
                            "JSON package exceeds inspection budget"
                        ) from error
                    fill()
                    continue
                if end > max_item_chars:
                    raise ValueError("JSON package exceeds inspection budget")
                if not isinstance(item, dict):
                    raise TypeError("Each package must be a JSON object")
                buffer = buffer[end:]
                yield item
                break
            separator = peek()
            if separator == "]":
                buffer = buffer[1:]
                break
            if separator != ",":
                raise ValueError("Expected package separator")
            buffer = buffer[1:]
            if peek() == "]":
                raise ValueError("Trailing comma is not JSON")
    if peek():
        raise ValueError("Trailing data after package array")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(path: Path, expected_sha256: str) -> dict[str, Any]:
    if len(expected_sha256) != 64 or file_sha256(path) != expected_sha256:
        raise ValueError("Archive identity differs from trusted SHA-256")
    counts: Counter[str] = Counter()
    licenses: Counter[str] = Counter()
    currencies: Counter[str] = Counter()
    years: Counter[str] = Counter()
    methods: Counter[str] = Counter()
    ocids: set[str] = set()
    release_ids: set[tuple[str, str]] = set()
    award_ids: set[tuple[str, str]] = set()
    with zipfile.ZipFile(path) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if len(members) != 1 or not members[0].filename.lower().endswith(".json"):
            raise ValueError("Exactly one JSON export member is required")
        member = members[0]
        if member.file_size > 3 * 1024**3 or member.flag_bits & 1:
            raise ValueError("Unsupported encrypted or oversized export")
        with (
            archive.open(member) as binary,
            io.TextIOWrapper(binary, encoding="utf-8") as text,
        ):
            for package in packages(text):
                counts["packages"] += 1
                license_value = package.get("license")
                licenses[
                    str(license_value) if isinstance(license_value, str) else "MISSING"
                ] += 1
                releases = package.get("releases")
                if not isinstance(releases, list):
                    raise TypeError("Package releases must be an array")
                if len(releases) != 1:
                    counts["packages_without_exactly_one_release"] += 1
                for release in releases:
                    if not isinstance(release, dict):
                        raise TypeError("Release must be an object")
                    counts["releases"] += 1
                    ocid, identifier = release.get("ocid"), release.get("id")
                    if not isinstance(ocid, str) or not isinstance(identifier, str):
                        raise TypeError("Release identity missing or invalid")
                    ocids.add(ocid)
                    if (ocid, identifier) in release_ids:
                        counts["duplicate_release_id_occurrences"] += 1
                    release_ids.add((ocid, identifier))
                    try:
                        year = str(
                            datetime.fromisoformat(
                                release["date"].replace("Z", "+00:00")
                            ).year
                        )
                    except (KeyError, TypeError, AttributeError, ValueError):
                        year = "MISSING_OR_INVALID"
                    years[year] += 1
                    tender = release.get("tender")
                    if isinstance(tender, dict):
                        method = tender.get("procurementMethodDetails")
                        methods[method if isinstance(method, str) else "MISSING"] += 1
                    awards = release.get("awards")
                    if awards is None:
                        counts["releases_awards_absent_or_null"] += 1
                        continue
                    if not isinstance(awards, list):
                        raise TypeError("Awards must be an array when supplied")
                    for award in awards:
                        if not isinstance(award, dict):
                            raise TypeError("Award must be an object")
                        counts["award_occurrences"] += 1
                        award_id = award.get("id")
                        if isinstance(award_id, str):
                            award_ids.add((ocid, award_id))
                        else:
                            counts["award_id_missing_or_invalid"] += 1
                        value = award.get("value")
                        if not isinstance(value, dict):
                            counts["award_value_absent_or_invalid"] += 1
                            continue
                        currency = value.get("currency")
                        currencies[
                            currency if isinstance(currency, str) else "MISSING"
                        ] += 1
                        amount = value.get("amount")
                        if isinstance(amount, bool) or not isinstance(
                            amount, int | Decimal
                        ):
                            counts["award_amount_absent_or_non_numeric"] += 1
    return {
        "schema": "equiframe.sercop-inventory.v1",
        "status": "INVENTORIED_NOT_SCIENTIFICALLY_ACCEPTED",
        "archive": path.name,
        "archive_sha256": expected_sha256,
        "json_member": member.filename,
        "json_member_uncompressed_bytes": member.file_size,
        "json_member_crc_verified_by_full_read": True,
        "counts": dict(sorted(counts.items())),
        "unique_ocids": len(ocids),
        "unique_release_identities": len(release_ids),
        "unique_award_identities": len(award_ids),
        "declared_licenses": dict(sorted(licenses.items())),
        "release_date_years": dict(sorted(years.items())),
        "procurement_method_details": dict(sorted(methods.items())),
        "award_currency_occurrences": dict(sorted(currencies.items())),
        "effective_training_profiles_accredited": None,
        "independent_labels_accredited": 0,
        "thesis_modified": False,
        "limits": "Export selection, release/award occurrences and rows are not training profiles, independent groups, compiled records, validated cohort or scientific results. Amounts are not summed across versions or currencies.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Receipt output must be new")
        result = inventory(args.archive, args.sha256)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError, TypeError, zipfile.BadZipFile) as error:
        parser.exit(2, f"Inventory rejected: {error}\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in ["status", "counts", "unique_ocids", "unique_award_identities"]
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
