"""Bounded, disjoint monthly cohorts of public SERCOP compiled releases."""

from __future__ import annotations

import gzip
import heapq
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import public_spending as study
from run import digest

YEARS = tuple(range(2019, 2027))
ARCHIVE = "https://fastly.data.open-contracting.org/downloads/ecuador_sercop_bulk/4393/"
ARCHIVE_SHA256 = {
    2019: "e343df328def578559adae9d9726ed76580ffea3ea881763851ceda05d91ece5",
    2020: "59576f0cc384b4ee7536f75c75188bcb9d50a3a1b12eb71c1efa8c912b03dac8",
    2021: "0721e6fac70d2a512ece76a72ce727e8a651751e2c755b817ddec9fb3fdd6903",
    2022: "1755852fcbb293abac1ad96987b6e9a311af71698953c1cf2977b851d76c585f",
    2023: "56c659b4a3e2f0ca9eeb761b4934f971a5a373ec6e376b44e42bb4a53b3e320a",
    2024: "771fb341f6d1b7b63ff29f02cf336407ec3fa9c9158ba776725a92b71e522faf",
    2025: "05104580f33184d8d1d1a63a1f4d99874efebae72f71061b5480bfe27b389c2e",
    2026: "160d9481e81e54c14b8d5dd640158e199e55c8e635294982088b8019c5996040",
}
ZONE = ZoneInfo("America/Guayaquil")
FOR_MONTH = {
    f"{year:04d}-{month:02d}": (
        "training" if year < 2026 or month <= 5 else "calibration" if month <= 8 else "test"
    )
    for year in YEARS
    for month in range(1, 13 if year < 2026 else 12)
}
NORMAL_TEST_LOTS = 16
FAULTS_PER_MONTH = 20
SHIFTED_TEST_LOTS = 4
QUOTAS = {
    "training": 96,
    "calibration": 48,
    "test": NORMAL_TEST_LOTS + FAULTS_PER_MONTH + SHIFTED_TEST_LOTS,
}
RESERVOIR_LIMIT = 2048
Award = dict[str, Any]
RankedProcedure = tuple[int, str, list[Award]]


def awards(record: dict[str, Any], ocid: str, excluded: Counter[str]) -> list[Award]:
    buyer = (record.get("buyer") or {}).get("id")
    if not isinstance(buyer, str) or not buyer:
        excluded["missing_buyer"] += 1
        return []
    result = []
    identifiers = set()
    for award in record.get("awards") or ():
        identifier = award.get("id")
        if not isinstance(identifier, str) or not identifier:
            excluded["missing_award_id"] += 1
            continue
        if identifier in identifiers:
            excluded["duplicate_award_id_procedure"] += 1
            return []
        identifiers.add(identifier)
        value = award.get("value") or {}
        amount, currency = value.get("amount"), value.get("currency")
        if not isinstance(amount, (int, Decimal)) or isinstance(amount, bool) or currency != "USD":
            excluded["missing_amount_or_non_usd_award"] += 1
            continue
        cents = amount * 100
        if not (Decimal(cents).is_finite() and cents == int(cents) and abs(int(cents)) <= 10**14):
            excluded["amount_outside_supported_exact_cents"] += 1
            continue
        result.append(
            {
                "ocid": ocid,
                "award": identifier,
                "buyer": buyer,
                "currency": currency,
                "amount": int(cents),
            }
        )
    return result


def collect(source_dir: Path) -> tuple[dict[str, list[RankedProcedure]], dict[str, Any]]:
    selected: dict[str, list[RankedProcedure]] = defaultdict(list)
    source_inventory = {}
    seen: set[str] = set()
    for year in YEARS:
        path = source_dir / f"{year}.jsonl.gz"
        archive_hash = sha256()
        with path.open("rb") as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b""):
                archive_hash.update(part)
        archive_sha256 = archive_hash.hexdigest()
        if archive_sha256 != ARCHIVE_SHA256[year]:
            raise ValueError(f"{year} differs from the pinned public SERCOP snapshot")
        excluded: Counter[str] = Counter()
        eligible: Counter[str] = Counter()
        count = 0
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                count += 1
                record = json.loads(line, parse_float=Decimal)
                ocid = record.get("ocid")
                raw_date = record.get("date")
                if not isinstance(ocid, str) or not ocid or not isinstance(raw_date, str):
                    excluded["missing_ocid_or_date"] += 1
                    continue
                try:
                    date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except ValueError:
                    excluded["invalid_date"] += 1
                    continue
                if date.tzinfo is None:
                    excluded["missing_timezone"] += 1
                    continue
                date = date.astimezone(ZONE)
                month = date.strftime("%Y-%m")
                if date.year != year or month not in FOR_MONTH:
                    excluded["outside_declared_archive_window"] += 1
                    continue
                if ocid in seen:
                    excluded["previously_seen_procedure"] += 1
                    continue
                seen.add(ocid)
                rows = awards(record, ocid, excluded)
                if not rows:
                    excluded["empty_eligible_awards_procedure"] += 1
                    continue
                eligible[month] += 1
                item = (-int(digest(["sercop-thesis-2019-2026", month, ocid]), 16), ocid, rows)
                heap = selected[month]
                if len(heap) < RESERVOIR_LIMIT:
                    heapq.heappush(heap, item)
                elif item > heap[0]:
                    heapq.heapreplace(heap, item)
        source_inventory[str(year)] = {
            "url": ARCHIVE + path.name,
            "sha256": archive_sha256,
            "bytes": path.stat().st_size,
            "compiled_releases": count,
            "eligible_by_month": dict(sorted(eligible.items())),
            "excluded": dict(sorted(excluded.items())),
        }
    return dict(selected), source_inventory


def select(source_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pools, inventory = collect(source_dir)
    lots = []
    selections = {}
    periods: dict[str, list[str]] = defaultdict(list)
    for month, split in FOR_MONTH.items():
        key = month[:4] if split == "training" else month
        periods[key].append(month)
    for period, months in periods.items():
        split = FOR_MONTH[months[0]]
        pool = iter(
            sorted((item for month in months for item in pools.get(month, ())), reverse=True)
        )
        rejected = 0
        month_lots = []
        for index in range(QUOTAS[split]):
            shifted = split == "test" and index >= NORMAL_TEST_LOTS + FAULTS_PER_MONTH
            minimum = 64 if shifted else 32
            while True:
                rows: list[Award] = []
                identifiers = []
                for _, ocid, procedure in pool:
                    identifiers.append(ocid)
                    rows.extend(procedure)
                    if len(rows) >= minimum:
                        break
                if len(rows) < minimum:
                    raise ValueError(f"Insufficient disjoint eligible procedures for {period}")
                if len(study.expected(rows)) >= 2:
                    break
                rejected += 1
            kind = (
                study.FAULTS[(index - NORMAL_TEST_LOTS) % len(study.FAULTS)]
                if split == "test" and index >= NORMAL_TEST_LOTS and not shifted
                else "normal"
            )
            month_lots.append(
                {
                    "period": period,
                    "split": "shifted_normal" if shifted else split,
                    "index": index,
                    "kind": kind,
                    "source": rows,
                    "source_sha256": digest(rows),
                    "procedure_count": len(identifiers),
                    "procedures_sha256": digest(sorted(identifiers)),
                }
            )
        selections[period] = {
            "partition": split,
            "months": months,
            "batches": len(month_lots),
            "insufficient_group_chunks": rejected,
            "batch_sha256": [lot["source_sha256"] for lot in month_lots],
        }
        lots.extend(month_lots)
    if len({lot["source_sha256"] for lot in lots}) != len(lots):
        raise ValueError("A batch occurs in more than one partition")
    return lots, {"archives": inventory, "periods": selections}
