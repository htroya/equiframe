"""Full local comparison with disk indexes, exact values and bounded matching."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import time
from collections import Counter, deque
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as _timezone
from pathlib import Path
from typing import BinaryIO, Literal
from uuid import uuid4

from typing_extensions import TypeAliasType

from equiframe._comparison_io import batches, file_ref, snapshot
from equiframe._diff_capture import _CapturedInput, _NativeInput
from equiframe._document_io import read_document
from equiframe._error_reporting import report_failure
from equiframe._regular_io import local_input_path, local_output_directory
from equiframe.comparison_types import (
    AppliedPolicy,
    ComparisonCounts,
    ComparisonDiagnostic,
    ComparisonDifference,
    ComparisonOptions,
    ComparisonPolicy,
    ComparisonResult,
    ComparisonSource,
    ComparisonSpec,
    ComparisonValue,
    Side,
)
from equiframe.contracts import ColumnKeyScope, Contract, KeySpec, SignificantOrder
from equiframe.errors import (
    ArtifactIntegrityError,
    CapabilityError,
    ExecutionCancelled,
    ExecutionTimeout,
    MissingDependencyError,
    ResourceLimitError,
)
from equiframe.execution import CancellationToken, _versions
from equiframe.execution_types import ExecutionResult, PhysicalColumn, TableArtifact
from equiframe.local import LocalArtifactStore, local_path
from equiframe.normalization import (
    equal,
    logical_signature,
    normalize,
    order_value,
    physical_value,
    row_identity,
    schema_compatible,
)
from equiframe.serialization import _constant, _JsonObject, _unique_objects, contract_fingerprint
from equiframe.tables import ArrowInput
from equiframe.types import ArtifactRef, ComparisonState

UTC = _timezone.utc

ComparisonInput = TypeAliasType(
    "ComparisonInput", ArrowInput | ArtifactRef | TableArtifact | ExecutionResult | Path
)
_ComparisonInput = TypeAliasType(
    "_ComparisonInput", ComparisonInput | _NativeInput | _CapturedInput
)


def comparison_fingerprint(spec: ComparisonSpec) -> str:
    """SHA-256 of the complete comparison specification, including authorization."""
    spec = ComparisonSpec.model_validate(spec)
    return hashlib.sha256(_json(spec.model_dump(mode="json"))).hexdigest()


def _json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def _partition(value: bytes, count: int) -> int:
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big") % count


def _values(data: str) -> tuple[ComparisonValue, ...]:
    return tuple(ComparisonValue.model_validate(v) for v in json.loads(data))


def _encoded(values: tuple[ComparisonValue, ...]) -> str:
    return _json([v.model_dump(mode="json") for v in values]).decode("ascii")


@dataclass
class _Row:
    position: int
    raw: tuple[ComparisonValue, ...]
    normalized: tuple[ComparisonValue, ...]


class _Work:
    def __init__(
        self,
        spec: ComparisonSpec,
        options: ComparisonOptions,
        directory: Path,
        cancellation: CancellationToken,
        start: float,
        evidence: BinaryIO,
    ) -> None:
        self.spec, self.options, self.directory = spec, options, directory
        self.cancellation, self.start, self.evidence = cancellation, start, evidence
        self.work = self.pairs = self.peak_disk = self.evidence_bytes = 0
        self.rows = {"left": 0, "right": 0}
        self.matched = self.differences = self.violations = 0
        self.invalid: set[str] = set()
        self.examples: list[ComparisonDifference] = []
        self.applied: Counter[tuple[Side, str | None, str]] = Counter()
        self.sources: dict[Side, ComparisonSource] = {}
        self.schema = spec.contract.output.schema_spec
        self.columns = self.schema.columns
        self.names = tuple(c.name for c in self.columns)
        self.key = next((key for key in self.schema.keys if key.unique), None)
        self.key_valid = self.key is not None
        self.strategy: Literal["pending", "sequence", "key", "multiset", "matching"] = "pending"
        self.selected_key: str | None = None
        self.db = sqlite3.connect(directory / "work.sqlite")
        self.db.execute("PRAGMA journal_mode=OFF")
        self.db.execute("PRAGMA temp_store=FILE")
        self.db.execute(f"PRAGMA cache_size=-{options.sqlite_cache_kib}")
        self.db.executescript("""
            CREATE TABLE rows(side TEXT, pos INTEGER, raw TEXT, norm TEXT, exact BLOB,
                              candidate BLOB, part INTEGER, grp BLOB, PRIMARY KEY(side,pos));
            CREATE TABLE seen(side TEXT, name TEXT, phase TEXT, value BLOB, pos INTEGER,
                              PRIMARY KEY(side,name,phase,value));
            CREATE INDEX grouping ON rows(part,grp,side,pos);
        """)
        self.db.execute(f"PRAGMA max_page_count={max(1, options.max_disk_bytes // 4096)}")
        self.db.set_progress_handler(self._progress, 1000)
        self.sql_error: Exception | None = None

    def _progress(self) -> int:
        try:
            self.check(1000)
        except Exception as error:
            self.sql_error = error
            return 1
        return 0

    def check(self, cost: int = 1) -> None:
        """Check controls and disk after operations that may grow files."""
        self.check_read(cost)
        self.check_disk()

    def check_read(self, cost: int = 1) -> None:
        """Check work, cancellation and time during operations without writes.

        Callers may omit disk measurement only while reading immutable input or
        calculating in memory. SQLite progress callbacks and every evidence/write
        checkpoint still use ``check``; read phases also measure disk at their
        boundaries. Work accounting is identical to the full checkpoint.
        """
        self.work += cost
        if self.cancellation.cancelled:
            raise ExecutionCancelled("comparison cancelled at checkpoint")
        if (
            self.options.timeout_seconds is not None
            and time.perf_counter() - self.start >= self.options.timeout_seconds
        ):
            raise ExecutionTimeout("cooperative comparison timeout")
        if self.work > self.options.max_work:
            raise ResourceLimitError("max_work")

    def check_disk(self) -> None:
        """Measure current files without consuming an additional work unit."""
        disk = 0
        with os.scandir(self.directory) as entries:
            for entry in entries:
                try:
                    is_file = entry.is_file()
                except OSError:
                    # Preserve Path.is_file's platform-specific handling of
                    # missing/invalid targets (including symlink loops).
                    is_file = Path(entry.path).is_file()
                if is_file:
                    disk += entry.stat().st_size
        self.peak_disk = max(self.peak_disk, disk)
        if disk > self.options.max_disk_bytes:
            raise ResourceLimitError("max_disk_bytes")

    def emit(self, difference: ComparisonDifference) -> None:
        block = _json(difference.model_dump(mode="json")) + b"\n"
        if self.evidence_bytes + len(block) > self.options.max_evidence_bytes:
            raise ResourceLimitError("max_evidence_bytes")
        self.evidence.write(block)
        self.evidence.flush()
        self.evidence_bytes += len(block)
        self.differences += 1
        if difference.category in ("contract", "schema"):
            self.violations += 1
            if difference.side:
                self.invalid.add(difference.side)
        if len(self.examples) < self.options.max_examples:
            self.examples.append(difference)
        self.check()

    def violation(
        self,
        code: str,
        side: Side,
        *,
        position: int | None = None,
        column: str | None = None,
        values: tuple[ComparisonValue, ...] = (),
        category: Literal["contract", "schema"] = "contract",
    ) -> None:
        self.emit(
            ComparisonDifference(
                category=category,
                code=code,
                side=side,
                position=position,
                column=column,
                left=values if side == "left" else (),
                right=values if side == "right" else (),
                message=code.replace("_", " "),
            )
        )

    def source(self, value: _ComparisonInput, side: Side) -> ComparisonSource:
        execution = None
        table = None
        captured = None
        if isinstance(value, (_NativeInput, _CapturedInput)):
            captured = value.load() if isinstance(value, _NativeInput) else value.loaded
            self.check()
            value = ArrowInput(captured.table)
        if isinstance(value, ExecutionResult):
            execution = ExecutionResult.model_validate(value)
            if execution.state != "completed" or execution.output is None:
                raise ValueError("execution_not_completed")
            if execution.contract_sha256 != contract_fingerprint(self.spec.contract):
                raise ValueError("execution_contract_mismatch")
            for item in execution.inputs:
                self.verify_table(item)
            table = execution.output
        elif isinstance(value, TableArtifact):
            table = TableArtifact.model_validate(value)
        if table:
            if table.name != self.spec.contract.output.name:
                raise ValueError("output_table_name_mismatch")
            value = table.data
        if not isinstance(value, (ArrowInput, ArtifactRef, Path)):
            raise TypeError(
                "compare accepts ArrowInput, ArtifactRef, TableArtifact, ExecutionResult or Path"
            )
        data = snapshot(value, self.directory, self.options, self.check)
        if captured is not None:
            import pyarrow.compute as pc

            def describe(
                loaded: object, native: tuple[tuple[str, str], ...]
            ) -> tuple[PhysicalColumn, ...]:
                import pyarrow as pa

                if not (isinstance(loaded, pa.Table)):
                    raise AssertionError("Internal invariant check failed.")
                types = dict(native)
                return tuple(
                    PhysicalColumn(
                        name=field.name,
                        engine_type=types.get(field.name, str(field.type)),
                        arrow_type=str(field.type),
                        null_count=loaded.column(field.name).null_count,
                        nan_count=(
                            int(pc.sum(pc.is_nan(loaded.column(field.name))).as_py() or 0)
                            if pa.types.is_floating(field.type)
                            else 0
                        ),
                    )
                    for field in loaded.schema
                )

            index = captured.index if captured.meaningful_index else None
            index_ref = (
                snapshot(ArrowInput(index), self.directory, self.options, self.check)
                if index is not None
                else None
            )
            table = TableArtifact(
                name=self.spec.contract.output.name,
                data=data,
                row_count=captured.table.num_rows,
                columns=describe(captured.table, captured.native_types),
                index=index_ref,
                index_columns=describe(index, ()) if index is not None else (),
                notes=captured.notes,
            )
        result = ComparisonSource(data=data, table=table, execution=execution)
        self.sources[side] = result
        if table and table.index:
            self.verify_table(table, index=True)
            if self.spec.policy.index == "reject":
                raise CapabilityError(
                    "separate index requires explicit ignore policy or promotion "
                    "to contract columns"
                )
            self.applied[side, None, "ignore_captured_index"] += table.row_count
        return result

    def verify_table(self, table: TableArtifact, *, index: bool = False) -> None:
        ref = table.index if index else table.data
        if not (ref is not None):
            raise AssertionError("Internal invariant check failed.")
        copied = snapshot(ref, self.directory, self.options, self.check)
        try:
            self.check_disk()
            # Only the private immutable snapshot is read in this phase. No
            # SQLite operation or evidence emission occurs inside these loops.
            with batches(copied, self.options, self.check_read) as (schema, reader):
                observed = tuple((f.name, str(f.type)) for f in schema)
                columns = table.index_columns if index else table.columns
                if observed != tuple((c.name, c.arrow_type) for c in columns):
                    raise ArtifactIntegrityError("table physical schema evidence mismatch")
                nulls, nans = [0] * len(columns), [0] * len(columns)
                count = 0
                for batch in reader:
                    count += batch.num_rows
                    for i, array in enumerate(batch.columns):
                        nulls[i] += array.null_count
                        for scalar in array:
                            self.check_read()
                            nans[i] += physical_value(scalar).kind == "nan"
                if count != table.row_count or any(
                    c.null_count != nulls[i] or c.nan_count != nans[i]
                    for i, c in enumerate(columns)
                ):
                    raise ArtifactIntegrityError("table row/NULL/NaN evidence mismatch")
            self.check_disk()
        finally:
            local_path(copied).unlink(missing_ok=True)
        if not index and table.index:
            self.verify_table(table, index=True)

    def key_values(
        self, row: tuple[ComparisonValue, ...], key: KeySpec
    ) -> tuple[ComparisonValue, ...]:
        names = (
            (*key.scope.columns, *key.columns)
            if isinstance(key.scope, ColumnKeyScope)
            else key.columns
        )
        return tuple(row[self.names.index(name)] for name in names)

    def check_unique(
        self, side: Side, name: str, phase: str, values: tuple[ComparisonValue, ...], pos: int
    ) -> bool:
        try:
            self.db.execute(
                "INSERT INTO seen VALUES(?,?,?,?,?)", (side, name, phase, row_identity(values), pos)
            )
        except sqlite3.IntegrityError:
            self.violation("duplicate_" + phase + "_" + name, side, position=pos, values=values)
            return False
        return True

    def ingest(self, source: ComparisonSource, side: Side) -> None:
        previous: tuple[ComparisonValue, ...] | None = None
        with batches(source.data, self.options, self.check) as (schema, reader):
            observed = tuple((f.name, str(f.type)) for f in schema)
            self.sources[side] = source.model_copy(update={"observed_schema": observed})
            if len(set(schema.names)) != len(schema.names) or any(not n for n in schema.names):
                raise CapabilityError("ambiguous physical column names")
            for name in self.names:
                if name not in schema.names:
                    self.violation("missing_column", side, column=name, category="schema")
            for name in schema.names:
                if name not in self.names:
                    self.violation("additional_column", side, column=name, category="schema")
            if set(schema.names) == set(self.names) and tuple(schema.names) != self.names:
                if self.spec.policy.column_order == "significant":
                    self.violation("column_order", side, category="schema")
                else:
                    self.applied[side, None, "align_column_names"] += 1
            compatible: dict[str, bool] = {}
            for field in schema:
                logical_signature(field.type)
                if field.name in self.names:
                    col = self.columns[self.names.index(field.name)]
                    compatible[field.name] = schema_compatible(field.type, col, self.spec.policy)
                    if not compatible[field.name]:
                        self.violation("logical_type", side, column=field.name, category="schema")
                    elif not schema_compatible(field.type, col, ComparisonPolicy()):
                        self.applied[side, field.name, "lossless_physical_type_validation"] += 1
            nulls, nans = Counter[str](), Counter[str]()
            for batch in reader:
                for row_index in range(batch.num_rows):
                    self.check(len(self.columns))
                    pos = self.rows[side]
                    if sum(self.rows.values()) >= self.options.max_rows:
                        raise ResourceLimitError("max_rows (combined inputs)")
                    raw_by_name = {
                        name: physical_value(batch.column(i)[row_index])
                        for i, name in enumerate(schema.names)
                    }
                    for name, v in raw_by_name.items():
                        nulls[name] += v.kind == "null"
                        nans[name] += v.kind == "nan"
                    raw = tuple(
                        raw_by_name.get(name, ComparisonValue(kind="null")) for name in self.names
                    )
                    norm = []
                    for col, v in zip(self.columns, raw, strict=True):
                        out, issues = normalize(v, col) if compatible.get(col.name) else (v, ())
                        norm.append(out)
                        if out != v:
                            self.applied[side, col.name, "authorized_scalar_normalization"] += 1
                        for issue in issues:
                            self.violation(issue, side, position=pos, column=col.name, values=(v,))
                    normalized = tuple(norm)
                    for key in self.schema.keys:
                        logical_incomplete = any(
                            v.kind == "null" for v in self.key_values(normalized, key)
                        )
                        for phase, row in (("raw", raw), ("normalized", normalized)):
                            values = self.key_values(row, key)
                            if logical_incomplete or any(v.kind == "null" for v in values):
                                if key.incomplete == "reject":
                                    self.violation(
                                        "incomplete_" + phase + "_" + key.name,
                                        side,
                                        position=pos,
                                        values=values,
                                    )
                                if key == self.key:
                                    self.key_valid = False
                            elif key.unique and not self.check_unique(
                                side, "key_" + key.name, phase, values, pos
                            ):
                                if key == self.key:
                                    self.key_valid = False
                    if self.schema.multiplicity == "distinct":
                        self.check_unique(side, "row", "normalized", normalized, pos)
                    if isinstance(self.schema.order, SignificantOrder) and previous is not None:
                        self.check_order(previous, normalized, side, pos)
                    previous = normalized
                    raw_json, norm_json = _encoded(raw), _encoded(normalized)
                    if len(raw_json) + len(norm_json) > self.options.max_row_bytes:
                        raise ResourceLimitError("max_row_bytes")
                    candidate = (
                        row_identity(self.key_values(normalized, self.key)) if self.key else b""
                    )
                    self.db.execute(
                        "INSERT INTO rows VALUES(?,?,?,?,?,?,0,?)",
                        (side, pos, raw_json, norm_json, row_identity(normalized), candidate, b""),
                    )
                    self.rows[side] += 1
            if source.table:
                t = source.table
                if (
                    observed != tuple((c.name, c.arrow_type) for c in t.columns)
                    or self.rows[side] != t.row_count
                    or any(
                        nulls[c.name] != c.null_count or nans[c.name] != c.nan_count
                        for c in t.columns
                    )
                ):
                    raise ArtifactIntegrityError(
                        "output observed schema/counts disagree with execution evidence"
                    )
        self.db.commit()

    def check_order(
        self,
        previous: tuple[ComparisonValue, ...],
        current: tuple[ComparisonValue, ...],
        side: Side,
        pos: int,
    ) -> None:
        order = self.schema.order
        if not (isinstance(order, SignificantOrder)):
            raise AssertionError("Internal invariant check failed.")
        result = 0
        for sort in order.by:
            index = self.names.index(sort.column)
            a, b = previous[index], current[index]
            if a.kind == "null" or b.kind == "null":
                result = (int(a.kind == "null") - int(b.kind == "null")) * (
                    -1 if sort.nulls == "first" else 1
                )
            else:
                x, y = order_value(a), order_value(b)
                result = (int(x > y) - int(x < y)) * (1 if sort.direction == "ascending" else -1)
            if result:
                break
        if result > 0 or (result == 0 and order.ties == "reject"):
            self.violation(
                "order_violation" if result > 0 else "order_tie", side, position=pos, values=current
            )

    def prepare(self) -> None:
        approximate = any(c.numeric_policy and c.numeric_policy.tolerance for c in self.columns)
        if isinstance(self.schema.order, SignificantOrder):
            self.strategy = "sequence"
        elif self.key_valid:
            self.strategy = "key"
            if not (self.key is not None):
                raise AssertionError("Internal invariant check failed.")
            self.selected_key = self.key.name
        else:
            self.strategy = "matching" if approximate else "multiset"
        for side, pos, norm, exact, candidate in self.db.execute(
            "SELECT side,pos,norm,exact,candidate FROM rows"
        ):
            self.check()
            if self.strategy == "sequence":
                group = str(pos).zfill(20).encode("ascii")
            elif self.strategy == "key":
                group = candidate
            elif self.strategy == "multiset":
                group = exact
            else:
                group = row_identity(
                    tuple(
                        v
                        for v, c in zip(_values(norm), self.columns, strict=True)
                        if not (c.numeric_policy and c.numeric_policy.tolerance)
                    )
                )
            self.db.execute(
                "UPDATE rows SET grp=?,part=? WHERE side=? AND pos=?",
                (group, _partition(group, self.options.partitions), side, pos),
            )
        self.db.commit()

    def row(self, side: str, part: int, group: bytes) -> _Row | None:
        item = self.db.execute(
            "SELECT pos,raw,norm FROM rows WHERE part=? AND grp=? AND side=? ORDER BY pos LIMIT 1",
            (part, group, side),
        ).fetchone()
        return _Row(item[0], _values(item[1]), _values(item[2])) if item else None

    def pair_equal(self, a: _Row, b: _Row) -> bool:
        self.check_read(len(self.columns))
        self.pairs += 1
        if self.pairs > self.options.max_pair_checks:
            raise ResourceLimitError("max_pair_checks")
        return all(
            equal(x, y, c) for x, y, c in zip(a.normalized, b.normalized, self.columns, strict=True)
        )

    def content(self, a: _Row | None, b: _Row | None, left_count: int, right_count: int) -> None:
        self.emit(
            ComparisonDifference(
                category="content",
                code="row_multiplicity",
                position=a.position if a else None,
                other_position=b.position if b else None,
                left=a.raw if a else (),
                right=b.raw if b else (),
                left_count=left_count,
                right_count=right_count,
                message="unmatched full rows with multiplicity",
            )
        )

    def compare_groups(self) -> None:
        self.check_disk()
        # Python grouping/matching only reads the prepared index and calculates
        # in memory. SQL progress retains full checks (including spill growth),
        # and emit checks disk after every flushed difference.
        for part in range(self.options.partitions):
            groups = self.db.execute(
                "SELECT grp,SUM(side='left'),SUM(side='right') FROM rows WHERE part=? GROUP BY grp",
                (part,),
            )
            for group, nleft, nright in groups:
                self.check_read()
                if self.strategy == "matching":
                    self.match_group(part, group, nleft, nright)
                    continue
                a, b = self.row("left", part, group), self.row("right", part, group)
                if self.strategy == "multiset":
                    # The complete canonical value tuple is the SQL key, never a hash.
                    self.matched += min(nleft, nright)
                    if nleft != nright:
                        self.content(a, b, nleft, nright)
                elif a is None or b is None:
                    self.content(a, b, nleft, nright)
                elif self.pair_equal(a, b):
                    self.matched += 1
                else:
                    for i, col in enumerate(self.columns):
                        if not equal(a.normalized[i], b.normalized[i], col):
                            self.emit(
                                ComparisonDifference(
                                    category="content",
                                    code="cell_value",
                                    position=a.position,
                                    other_position=b.position,
                                    column=col.name,
                                    key=self.key_values(a.normalized, self.key)
                                    if self.strategy == "key" and self.key
                                    else (),
                                    left=(a.raw[i],),
                                    right=(b.raw[i],),
                                    left_count=1,
                                    right_count=1,
                                    message="aligned values differ",
                                )
                            )
        self.check_disk()

    def match_group(self, part: int, group: bytes, nleft: int, nright: int) -> None:
        if not nleft or not nright:
            for side, pos, raw in self.db.execute(
                "SELECT side,pos,raw FROM rows WHERE part=? AND grp=? ORDER BY side,pos",
                (part, group),
            ):
                row = _Row(pos, _values(raw), ())
                self.content(
                    row if side == "left" else None,
                    row if side == "right" else None,
                    int(side == "left"),
                    int(side == "right"),
                )
            return
        if nleft + nright > self.options.max_matching_rows:
            raise ResourceLimitError("max_matching_rows in exact-column group (possibly skewed)")
        size = self.db.execute(
            "SELECT SUM(length(raw)+length(norm)) FROM rows WHERE part=? AND grp=?", (part, group)
        ).fetchone()[0]
        memory = size + (nleft + nright) * (256 + len(self.columns) * 256)
        if memory > self.options.max_matching_bytes:
            raise ResourceLimitError("max_matching_bytes")
        rows: dict[str, list[_Row]] = {"left": [], "right": []}
        for side, pos, raw, norm in self.db.execute(
            "SELECT side,pos,raw,norm FROM rows WHERE part=? AND grp=? ORDER BY side,pos",
            (part, group),
        ):
            rows[side].append(_Row(pos, _values(raw), _values(norm)))
        edges: list[list[int]] = []
        for a in rows["left"]:
            adjacent = []
            for j, b in enumerate(rows["right"]):
                if self.pair_equal(a, b):
                    memory += 64
                    if memory > self.options.max_matching_bytes:
                        raise ResourceLimitError("max_matching_bytes (edges)")
                    adjacent.append(j)
            edges.append(adjacent)
        # Augmenting paths find a maximum matching; no tolerance-based grouping,
        # deduplication, transitive closure or irrevocable greedy assignment.
        matched_right: dict[int, int] = {}
        for start in range(nleft):
            queue = deque([start])
            visited = {start}
            parents: dict[int, int] = {}
            found = None
            while queue and found is None:
                node = queue.popleft()
                for target in edges[node]:
                    self.check_read()
                    if target in parents:
                        continue
                    parents[target] = node
                    if target not in matched_right:
                        found = target
                        break
                    next_node = matched_right[target]
                    if next_node not in visited:
                        visited.add(next_node)
                        queue.append(next_node)
            if found is not None:
                reverse = {v: k for k, v in matched_right.items()}
                while found is not None:
                    node = parents[found]
                    old = reverse.get(node)
                    matched_right[found] = node
                    found = old
        self.matched += len(matched_right)
        matched_left = set(matched_right.values())
        for i, a in enumerate(rows["left"]):
            if i not in matched_left:
                self.content(a, None, 1, 0)
        for j, b in enumerate(rows["right"]):
            if j not in matched_right:
                self.content(None, b, 0, 1)


def compare(
    left: ComparisonInput,
    right: ComparisonInput,
    *,
    contract: Contract,
    policy: ComparisonPolicy | None = None,
    options: ComparisonOptions | None = None,
    reference: Literal["peer", "expected"] = "peer",
    work_dir: Path | None = None,
    cancellation: CancellationToken | None = None,
) -> ComparisonResult:
    """Compare complete local outputs. Right may be an independent expected result.

    A fresh directory contains comparison.json, differences.jsonl and immutable
    snapshots. Operational failures return not_evaluable; invalid API configuration
    and inability to create/publish evidence raise. No transformations are executed.
    """
    return _compare(
        left,
        right,
        contract=contract,
        policy=policy,
        options=options,
        reference=reference,
        work_dir=work_dir,
        cancellation=cancellation,
    )


def _compare(
    left: _ComparisonInput,
    right: _ComparisonInput,
    *,
    contract: Contract,
    policy: ComparisonPolicy | None = None,
    options: ComparisonOptions | None = None,
    reference: Literal["peer", "expected"] = "peer",
    work_dir: Path | None = None,
    cancellation: CancellationToken | None = None,
) -> ComparisonResult:
    """One comparison kernel; the facade only adds capture and contract construction."""
    spec = ComparisonSpec(
        contract=contract, policy=ComparisonPolicy() if policy is None else policy
    )
    options = ComparisonOptions.model_validate(ComparisonOptions() if options is None else options)
    if reference not in ("peer", "expected"):
        raise ValueError("reference must be peer or expected")
    identifier = "comparison-" + uuid4().hex
    directory = (
        local_output_directory(Path("equiframe-comparisons") if work_dir is None else work_dir)
        / identifier
    )
    directory.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    diagnostics: list[ComparisonDiagnostic] = []
    complete = False
    side: Side | None = None
    evidence_path = directory / "differences.jsonl"
    with evidence_path.open("xb") as evidence:
        work = _Work(spec, options, directory, cancellation or CancellationToken(), start, evidence)
        try:
            for column in work.columns:
                tolerance = column.numeric_policy.tolerance if column.numeric_policy else None
                if tolerance:
                    for tolerance_value in (tolerance.absolute, tolerance.relative):
                        if tolerance_value is not None:
                            parts = tolerance_value.as_tuple()
                            if not (isinstance(parts.exponent, int)):
                                raise AssertionError("Internal invariant check failed.")
                            if (
                                max(abs(parts.exponent), len(parts.digits))
                                > options.max_numeric_digits
                            ):
                                raise ResourceLimitError("max_numeric_digits in declared tolerance")
            inputs: tuple[tuple[Side, _ComparisonInput], ...] = (("left", left), ("right", right))
            for input_side, value in inputs:
                side = input_side
                work.check()
                source = work.source(value, input_side)
                work.ingest(source, input_side)
            side = None
            lrun, rrun = work.sources["left"].execution, work.sources["right"].execution
            if lrun is not None and rrun is not None:

                def input_identity(t: TableArtifact) -> tuple[object, ...]:
                    return (
                        t.name,
                        t.data.sha256,
                        t.data.size_bytes,
                        (t.index.sha256, t.index.size_bytes) if t.index else None,
                    )

                lhs = sorted((input_identity(t) for t in lrun.inputs), key=lambda t: str(t[0]))
                rhs = sorted((input_identity(t) for t in rrun.inputs), key=lambda t: str(t[0]))
                if lhs != rhs:
                    raise ValueError(
                        "execution_inputs_differ: require the same verified input artifacts"
                    )
                if lrun.plan.parameters != rrun.plan.parameters:
                    raise ValueError("execution_parameters_differ")
            work.prepare()
            work.compare_groups()
            work.check()
            complete = True
        except (Exception, KeyboardInterrupt) as caught:
            error: BaseException = work.sql_error or caught
            if isinstance(error, sqlite3.OperationalError) and (
                getattr(error, "sqlite_errorcode", None) == getattr(sqlite3, "SQLITE_FULL", 13)
                or (
                    # CPython 3.10 exposes no SQLite result-code attributes.
                    # Match only SQLite's exact canonical FULL diagnostic; a
                    # different available result code always takes precedence.
                    not hasattr(error, "sqlite_errorcode")
                    and error.args == ("database or disk is full",)
                )
            ):
                error = ResourceLimitError("SQLite disk budget exhausted")
            code = (
                "cancelled"
                if isinstance(error, (ExecutionCancelled, KeyboardInterrupt))
                else "timeout"
                if isinstance(error, ExecutionTimeout)
                else "resource_exhausted"
                if isinstance(error, (ResourceLimitError, MemoryError))
                else "invalid_artifact"
                if isinstance(error, ArtifactIntegrityError)
                else "unsupported_capability"
                if isinstance(error, CapabilityError)
                and not isinstance(error, MissingDependencyError)
                else "missing_optional_dependency"
                if isinstance(error, MissingDependencyError)
                else "evaluation_failed"
            )
            safe_message = "Comparison could not be completed: " + code
            if type(error) is ValueError and len(error.args) == 1 and type(error.args[0]) is str:
                if error.args == (
                    "execution_inputs_differ: require the same verified input artifacts",
                ):
                    safe_message = "execution_inputs_differ: use identical verified input artifacts"
                elif error.args == ("execution_parameters_differ",):
                    safe_message = "execution_parameters_differ: use identical execution parameters"
            diagnostics.append(
                ComparisonDiagnostic(
                    code=code,
                    message=report_failure(error, safe_message),
                    side=side,
                    exception_type=type(error).__name__,
                )
            )
        finally:
            work.db.close()
            for name in (
                "work.sqlite",
                "work.sqlite-journal",
                "work.sqlite-wal",
                "work.sqlite-shm",
            ):
                (directory / name).unlink(missing_ok=True)
        evidence.flush()
        os.fsync(evidence.fileno())
    state: ComparisonState = "not_evaluable"
    if complete:
        if reference == "expected" and "right" in work.invalid:
            diagnostics.append(
                ComparisonDiagnostic(
                    code="invalid_expected",
                    side="right",
                    message="independent expected reference violates the declared output contract",
                )
            )
        else:
            state = "different" if work.differences else "equivalent"
    result = ComparisonResult(
        comparison_id=identifier,
        spec=spec,
        contract_sha256=contract_fingerprint(spec.contract),
        spec_sha256=comparison_fingerprint(spec),
        state=state,
        complete=complete,
        reference=reference,
        strategy=work.strategy,
        selected_key=work.selected_key,
        left=work.sources.get("left"),
        right=work.sources.get("right"),
        counts=ComparisonCounts(
            left_rows=work.rows["left"],
            right_rows=work.rows["right"],
            matched_rows=work.matched,
            difference_records=work.differences,
            contract_violations=work.violations,
            final=complete,
        ),
        options=options,
        applied_policies=tuple(
            AppliedPolicy(side=s, column=c, operation=o, count=n)
            for (s, c, o), n in work.applied.items()
        ),
        diagnostics=tuple(diagnostics),
        examples=tuple(work.examples),
        differences=file_ref(evidence_path, "jsonl"),
        started_at=started_at,
        elapsed_seconds=time.perf_counter() - start,
        work_units=work.work,
        pair_checks=work.pairs,
        peak_disk_bytes=work.peak_disk,
        versions=_versions("comparison"),
    )
    temporary = directory / "comparison.json.part"
    with temporary.open("xb") as output:
        output.write(_json(result.model_dump(mode="json")))
        output.flush()
        os.fsync(output.fileno())
    os.link(temporary, directory / "comparison.json")
    temporary.unlink()
    return result


def read_comparison(path: Path) -> ComparisonResult:
    """Read and strictly revalidate a persisted comparison manifest."""
    raw = read_document(local_input_path(path))
    return ComparisonResult.model_validate_json(raw)


def iter_differences(ref: ArtifactRef) -> Iterator[ComparisonDifference]:
    """Verify all evidence bytes before yielding typed difference records."""
    ref = ArtifactRef.model_validate(ref)
    if ref.format != "jsonl":
        raise ValueError("differences require a JSONL artifact")
    with tempfile.TemporaryDirectory(prefix="equiframe-differences-") as temporary:
        path = Path(temporary) / "differences.jsonl"
        LocalArtifactStore(Path(temporary)).get(ref, path)
        with path.open("rb") as source:
            for line in source:
                _unique_objects(
                    json.loads(
                        line.decode("utf-8"),
                        object_pairs_hook=_JsonObject,
                        parse_constant=_constant,
                    )
                )
                yield ComparisonDifference.model_validate_json(line)
