"""Explicit artifact-level fault injection, never labels or native ETL mutants."""

from datetime import timedelta
from decimal import Decimal

import pyarrow as pa
from equiframe import Family


def semantic_fault(family: Family, table: pa.Table) -> pa.Table:
    """A concrete semantic change per family; the oracle still determines effect."""
    rows = table.to_pylist()
    if family == "nulls_types":
        for row in rows:
            if row["amount"] is None:
                row["amount"] = Decimal("0.00")
    elif family == "joins":
        rows = [row for row in rows if row["category"] is not None]
    elif family == "duplicates_order":
        seen = set()
        unique = []
        for row in rows:
            if row["id"] not in seen:
                seen.add(row["id"])
                unique.append(row)
        rows = unique
    elif family == "aggregations":
        if len(rows) >= 2:
            rows[0]["total"], rows[1]["total"] = rows[1]["total"], rows[0]["total"]
    elif family == "dates":
        for row in rows:
            if row["day"] is not None:
                row["day"] += timedelta(days=1)
    return pa.Table.from_pylist(rows, schema=table.schema)
