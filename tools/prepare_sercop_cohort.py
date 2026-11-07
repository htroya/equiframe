"""Compile the pinned annual export into bounded proposed native-input shards.

These are raw study candidates, not normal executions, approved cohort, labels
or effective training profiles. The untouched source preserves all omitted OCDS
attributes; this projection is not a replacement for the complete domain DW.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from equiframe._regular_io import (
    local_input_path,
    new_directory_path,
    open_regular_file,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3"
EXPECTED_SOURCE_COUNTS = (190619, 183891)
MAX_SOURCE_RECORDS = 250000
MAX_SHARD_BYTES = 16 * 1024**2
MAX_UNIT_BYTES = 256 * 1024
MAX_SHARD_RECORDS = 10000


def require(condition, code):
    if not condition:
        raise ValueError(code)


def helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "owned_helper_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stream_sha(stream):
    digest = hashlib.sha256()
    stream.seek(0)
    for block in iter(lambda: stream.read(1024**2), b""):
        digest.update(block)
    stream.seek(0)
    return digest.hexdigest()


class Shards:
    def __init__(self, root, prefix):
        self.root, self.prefix = root, prefix
        self.stream = None
        self.count = self.size = 0
        self.digest = hashlib.sha256()
        self.files = []

    def finish(self):
        if self.stream is not None:
            self.stream.close()
            self.files.append(
                {
                    "file": self.path.name,
                    "records": self.count,
                    "bytes": self.size,
                    "sha256": self.digest.hexdigest(),
                }
            )
            self.stream = None

    def write(self, record):
        raw = (
            json.dumps(
                record, ensure_ascii=True, separators=(",", ":"), allow_nan=False
            )
            + "\n"
        ).encode()
        require(len(raw) <= MAX_UNIT_BYTES, "unit_byte_budget_exceeded")
        if (
            self.stream is None
            or self.count >= MAX_SHARD_RECORDS
            or self.size + len(raw) > MAX_SHARD_BYTES
        ):
            self.finish()
            self.path = self.root / (self.prefix + f"-{len(self.files):03}.jsonl")
            self.stream = self.path.open("xb")
            self.count = self.size = 0
            self.digest = hashlib.sha256()
        self.stream.write(raw)
        self.digest.update(raw)
        self.size += len(raw)
        self.count += 1


def year_of(value):
    if value is None:
        return None, "missing_or_null"
    if not isinstance(value, str) or len(value) > 64:
        return None, "invalid"
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        date = datetime.fromisoformat(normalized)
    except ValueError:
        return None, "invalid"
    # Calendar year as published, not an inferred UTC/domain cohort.
    return date.year, "offset" if date.tzinfo is not None else "naive"


def compile_unit(release, ordinal, reader):
    ocid = release["ocid"]
    awards = release.get("awards")
    if not awards:
        return None, "no_awards"
    if len(awards) > 256:
        return None, "unit_row_budget"
    rows, identities, amounts = [], set(), []
    for award in awards:
        if not isinstance(award, dict):
            return None, "invalid_award_structure"
        identity = award.get("id")
        if (
            not isinstance(identity, str)
            or not 1 <= len(identity) <= 256
            or identity in identities
        ):
            return None, "invalid_or_duplicate_award_identity"
        identities.add(identity)
        try:
            value = reader.award_value(award)
        except ValueError:
            return None, "unsupported_award_value"
        if value["currency"] is not None and len(value["currency"]) > 16:
            return None, "currency_text_budget"
        amount = value["amount"]
        if amount is not None:
            require(isinstance(amount, Decimal), "exact_decimal_required")
            exponent = amount.as_tuple().exponent
            if not isinstance(exponent, int) or not -38 <= exponent <= 38:
                return None, "decimal_transport_budget"
            amounts.append(amount)
        rows.append({"ocid": ocid, "award_id": identity, **value})
    scale = max((max(0, -a.as_tuple().exponent) for a in amounts), default=0)
    try:
        if any(reader.scaled_digits(amount, scale) > 38 for amount in amounts):
            return None, "decimal_transport_budget"
    except ValueError:
        return None, "decimal_transport_budget"
    for row in rows:
        row["amount"] = (
            format(row["amount"], "f") if row["amount"] is not None else None
        )
    return {
        "source_record_ordinal": ordinal,
        "ocid": ocid,
        "release_date": release.get("date"),
        "release_date_state": reader.presence(release, "date"),
        "decimal_scale": scale,
        "awards": rows,
        "dependencies": ["ocid:" + ocid],
        "normality": "UNREVIEWED",
        "native_profiles_prepared": 0,
    }, None


def prepare(archive_path, output, *, publication_year=None):
    require(
        isinstance(archive_path, Path) and isinstance(output, Path),
        "path_objects_required",
    )
    require(
        publication_year is None
        or type(publication_year) is int
        and 1900 <= publication_year <= 9999,
        "invalid_proposed_publication_year",
    )
    archive_path = local_input_path(archive_path)
    output = new_directory_path(local_input_path(output))
    require(
        not output.exists() and not output.is_relative_to(ROOT),
        "new_private_output_required",
    )
    reader = helper("owned_cohort_reader", ROOT / "tools/sercop_validation_workload.py")
    tool_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    parser_sha = hashlib.sha256(
        (ROOT / "tools/sercop_validation_workload.py").read_bytes()
    ).hexdigest()
    years, date_states, exclusions, currency_counts, row_counts, money_states = (
        Counter() for _ in range(6)
    )
    seen = set()
    releases = awards_seen = eligible = 0
    candidates = rejected = None
    with open_regular_file(archive_path) as binary:
        require(stream_sha(binary) == SOURCE_SHA256, "source_identity_mismatch")
        with zipfile.ZipFile(binary) as archive:
            require(
                archive.namelist() == ["releases_2025.json"]
                and archive.getinfo("releases_2025.json").file_size <= 4 * 1024**3,
                "source_member_budget_or_inventory_mismatch",
            )
            output.mkdir()
            candidates = Shards(output, "candidate-inputs")
            rejected = Shards(output, "exclusions")
            try:
                with (
                    archive.open("releases_2025.json") as raw,
                    io.TextIOWrapper(raw, encoding="utf-8") as text,
                ):
                    for ordinal, package in enumerate(reader.packages(text)):
                        releases += 1
                        require(
                            releases <= MAX_SOURCE_RECORDS,
                            "source_record_budget_exceeded",
                        )
                        values = package.get("releases")
                        require(
                            isinstance(values, list)
                            and len(values) == 1
                            and isinstance(values[0], dict),
                            "ambiguous_release_history",
                        )
                        release = values[0]
                        ocid = release.get("ocid")
                        require(
                            isinstance(ocid, str)
                            and 1 <= len(ocid) <= 256
                            and ocid not in seen,
                            "ambiguous_release_identity",
                        )
                        seen.add(ocid)
                        awards = release.get("awards")
                        require(
                            awards is None or isinstance(awards, list),
                            "invalid_award_collection",
                        )
                        awards_seen += len(awards or ())
                        year, state = year_of(release.get("date"))
                        years[str(year) if year is not None else "UNKNOWN"] += 1
                        date_states[state] += 1
                        if state == "invalid":
                            unit, reason = None, "unsupported_release_date"
                        elif publication_year is not None and year != publication_year:
                            unit, reason = None, "outside_proposed_publication_year"
                        else:
                            unit, reason = compile_unit(release, ordinal, reader)
                        if unit is None:
                            exclusions[reason] += 1
                            rejected.write(
                                {
                                    "source_record_ordinal": ordinal,
                                    "ocid": ocid,
                                    "reason": reason,
                                }
                            )
                        else:
                            candidates.write(unit)
                            eligible += 1
                            row_counts[str(len(unit["awards"]))] += 1
                            for row in unit["awards"]:
                                currency_counts[
                                    row["currency"]
                                    if row["currency"] is not None
                                    else "MISSING_OR_NULL"
                                ] += 1
                                money_states[row["amount_state"]] += 1
            finally:
                candidates.finish()
                rejected.finish()
        require(
            (releases, awards_seen) == EXPECTED_SOURCE_COUNTS,
            "pinned_source_counts_differ",
        )
        require(
            stream_sha(binary) == SOURCE_SHA256, "source_changed_during_preparation"
        )
    with open_regular_file(archive_path) as final_source:
        require(
            stream_sha(final_source) == SOURCE_SHA256,
            "source_path_replaced_during_preparation",
        )
    require(
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == tool_sha
        and hashlib.sha256(
            (ROOT / "tools/sercop_validation_workload.py").read_bytes()
        ).hexdigest()
        == parser_sha,
        "preparation_code_changed",
    )
    result = {
        "schema": "equiframe.sercop-cohort-proposal.v1",
        "status": "PROPOSED",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10 compatibility
        "source_sha256": SOURCE_SHA256,
        "tool_sha256": tool_sha,
        "parser_sha256": parser_sha,
        "source_release_records": releases,
        "source_award_records": awards_seen,
        "source_publication_years": dict(years),
        "source_date_states": dict(date_states),
        "proposed_publication_year": publication_year,
        "selector_field": "release.date calendar year as published",
        "candidate_ocid_units": eligible,
        "excluded_ocid_units": sum(exclusions.values()),
        "exclusion_reasons": dict(exclusions),
        "candidate_awards_by_currency": dict(currency_counts),
        "candidate_money_presence": dict(money_states),
        "candidate_awards_per_unit": dict(row_counts),
        "candidate_shards": candidates.files,
        "exclusion_shards": rejected.files,
        "normality_confirmed": False,
        "confirmed_normal_profiles": 0,
        "native_executions": 0,
        "n_fit_accredited_per_family": {
            f: 0 for f in ("nulls_types", "joins", "aggregations")
        },
        "cohort_approved": False,
        "human_labels": None,
        "final_partitions": None,
        "scientific_ready": False,
        "remaining": [
            "Domain/cohort approval and complete OCDS/DW validation",
            "Native execution and profiles for proposed units, with template/fragment dependencies",
            "Viable whole-group training/calibration/test and confirmed blind labels",
            "Effective fit support, external calibration and paired final evaluation",
        ],
        "projection_limits": "Amounts and presence flags are exact; omitted OCDS fields remain in the pinned original. This is not complete domain compilation or N_fit.",
    }
    with (output / "cohort-proposal.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write("\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publication-year", type=int)
    args = parser.parse_args()
    try:
        result = prepare(
            args.archive, args.output, publication_year=args.publication_year
        )
    except (ValueError, OSError, TypeError) as failure:
        parser.exit(2, "Cohort preparation failed: " + type(failure).__name__ + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "candidate_ocid_units",
                    "excluded_ocid_units",
                    "source_release_records",
                    "scientific_ready",
                )
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
