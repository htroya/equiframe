"""Bounded inspection/export of explicitly authorized comparison evidence.

Integrity means internal consistency with a supplied manifest, not independent
semantic evaluation or authentication. Inspection opens only the manifest and
JSONL; raw snapshots are read only by the separately requested export helper.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TypeVar
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname

from equiframe._base import FrozenModel
from equiframe._regular_io import absolute_path, open_regular_file, regular_directory
from equiframe.comparison_types import ComparisonDifference, ComparisonResult
from equiframe.contracts import ColumnKeyScope, SignificantOrder
from equiframe.errors import ArtifactIntegrityError, ResourceLimitError
from equiframe.types import ArtifactRef

_ModelT = TypeVar("_ModelT", bound=FrozenModel)

_MAX_DOCUMENT_BYTES = 16 * 1024 * 1024
_MAX_LINE_BYTES = 8 * 1024 * 1024
_SCALAR_CODES = frozenset(
    {
        "nan_forbidden",
        "null_forbidden",
        "integer_range",
        "float_precision",
        "decimal_precision",
        "date_granularity",
        "temporal_interval",
        "naive_timestamp",
        "nonexistent_time",
        "ambiguous_time",
        "timestamp_granularity",
        "allowed_values",
    }
)
_SCHEMA_CODES = frozenset({"missing_column", "additional_column", "column_order", "logical_type"})


@dataclass(frozen=True)
class EvidenceInspection:
    """Verified counts; caller retains counts.final for exact/lower-bound meaning.

    Added/removed refer to left candidate versus right reference. These and
    modified remain unknown for bags and before alignment.
    """

    examples: tuple[ComparisonDifference, ...]
    records: int
    violations: int
    added: int | None
    removed: int | None
    modified: int | None
    code_counts: tuple[tuple[str, int], ...]
    candidate_excess: int
    reference_excess: int


class EvidencePathError(ArtifactIntegrityError):
    """A comparison evidence path or file type violates confinement requirements."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactIntegrityError(message)


def _path_require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidencePathError(message)


def _limits(max_bytes: int, max_records: int, max_examples: int) -> None:
    for value, name, minimum in (
        (max_bytes, "max_bytes", 1),
        (max_records, "max_records", 1),
        (max_examples, "max_examples", 0),
    ):
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")


def _absolute(path: Path) -> Path:
    return absolute_path(path, path_error=EvidencePathError)


def _directory(path: Path) -> Path:
    return regular_directory(path, path_error=EvidencePathError)


def _reference_path(ref: ArtifactRef, root: Path) -> Path:
    try:
        parts = urlsplit(ref.uri)
    except ValueError:
        raise EvidencePathError("evidence URI is invalid") from None
    _path_require(
        parts.scheme == "file" and not parts.netloc and not parts.query and not parts.fragment,
        "evidence requires a local file URI without a host",
    )
    try:
        decoded = unquote(parts.path, errors="strict")
    except UnicodeError:
        raise EvidencePathError("evidence path encoding is invalid") from None
    _path_require(
        not decoded.startswith("//") and "\\" not in decoded and "\x00" not in decoded,
        "network or malformed evidence paths are not permitted",
    )
    path = Path(url2pathname(parts.path))
    _path_require(path.is_absolute(), "evidence paths must be absolute")
    path = _absolute(path)
    _path_require(path.is_relative_to(root), "evidence reference is outside the authorized root")
    return path


@contextmanager
def _open_regular(path: Path) -> Iterator[BinaryIO]:
    """Check every ancestor, reject special files, and pin POSIX directories.

    On systems without openat/O_NOFOLLOW, identities are checked around open.
    These cooperative checks do not sandbox a hostile concurrent filesystem.
    """
    with open_regular_file(path, path_error=EvidencePathError) as stream:
        yield stream


def _object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON object member in evidence")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise ArtifactIntegrityError("nonstandard JSON number in evidence")


def _document(raw: bytes, model: type[_ModelT]) -> _ModelT:
    try:
        text = raw.decode("utf-8")
        parsed = json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
        _require(isinstance(parsed, dict), "evidence JSON must be an object")
        return model.model_validate_json(text)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ArtifactIntegrityError("invalid typed evidence JSON") from error


def _read_document(path: Path, model: type[_ModelT], budget: int) -> tuple[_ModelT, int]:
    with _open_regular(path) as source:
        limit = min(budget, _MAX_DOCUMENT_BYTES)
        if os.fstat(source.fileno()).st_size > limit:
            raise ResourceLimitError("manifest exceeds report byte budget")
        raw = source.read(limit + 1)
        if len(raw) > limit:
            raise ResourceLimitError("manifest exceeds report byte budget")
    return _document(raw, model), len(raw)


def _manifest(result: ComparisonResult, root: Path, max_bytes: int) -> tuple[Path, int]:
    root = _directory(root)
    path = _reference_path(result.differences, root)
    _path_require(
        path.name == "differences.jsonl" and path.parent.name == result.comparison_id,
        "evidence must use the comparison identifier and conventional filenames",
    )
    persisted, size = _read_document(path.with_name("comparison.json"), ComparisonResult, max_bytes)
    _require(persisted == result, "persisted comparison manifest differs from supplied result")
    return path, size


def _validate_difference(difference: ComparisonDifference, result: ComparisonResult) -> None:
    schema = result.spec.contract.output.schema_spec
    names = {column.name for column in schema.columns}
    width = len(names)
    rows = {"left": result.counts.left_rows, "right": result.counts.right_rows}
    d = difference
    if d.category == "content":
        _require(result.strategy != "pending", "content evidence requires an alignment strategy")
        _require(d.side is None, "content differences must not carry a violation side")
        for position, count, values, side in (
            (d.position, d.left_count, d.left, "left"),
            (d.other_position, d.right_count, d.right, "right"),
        ):
            _require((position is not None) == (count > 0), "content count/position mismatch")
            _require(bool(values) == (count > 0), "content count/value mismatch")
            _require(count <= rows[side], "content count exceeds observed rows")
            if position is not None:
                _require(position < rows[side], "content position exceeds observed rows")
        if d.code == "cell_value":
            _require(result.strategy in ("key", "sequence"), "cell differences require alignment")
            _require(d.column in names, "cell column is not declared")
            _require(
                d.left_count == d.right_count == len(d.left) == len(d.right) == 1,
                "cell difference must contain two single values",
            )
            if result.strategy == "key":
                key = next(key for key in schema.keys if key.name == result.selected_key)
                key_width = len(key.columns)
                if isinstance(key.scope, ColumnKeyScope):
                    key_width += len(key.scope.columns)
                _require(len(d.key) == key_width, "cell key dimensions do not match selected key")
            else:
                _require(not d.key, "sequence differences must not claim a key")
                _require(d.position == d.other_position, "sequence cell positions must align")
        elif d.code == "row_multiplicity":
            _require(d.column is None and not d.key, "row differences have no column or key")
            _require(d.left_count != d.right_count, "row difference must change multiplicity")
            _require(
                (not d.left or len(d.left) == width) and (not d.right or len(d.right) == width),
                "row value dimensions do not match declared columns",
            )
            if result.strategy != "multiset":
                _require(
                    (d.left_count, d.right_count) in ((1, 0), (0, 1)),
                    "aligned/matching unmatched rows must be single-sided occurrences",
                )
        else:
            raise ArtifactIntegrityError("unknown content difference code")
        return
    _require(d.side is not None, "contract/schema evidence requires a side")
    _require(
        not d.key and not d.left_count and not d.right_count and d.other_position is None,
        "violation must not claim aligned row counts or keys",
    )
    _require(
        not (d.right if d.side == "left" else d.left),
        "violation values must belong to their declared side",
    )
    values = d.left if d.side == "left" else d.right
    if d.category == "schema":
        _require(d.code in _SCHEMA_CODES, "unknown schema difference code")
        _require(d.position is None and not values, "schema evidence must not claim row values")
        if d.code == "column_order":
            _require(d.column is None, "column order evidence must not select one column")
        elif d.code == "additional_column":
            _require(d.column is not None and d.column not in names, "invalid additional column")
        else:
            _require(d.column in names, "schema column is not declared")
        return
    if not (d.side is not None):
        raise AssertionError("Internal invariant check failed.")
    _require(d.position is not None, "contract evidence requires a row position")
    if not (d.position is not None):
        raise AssertionError("Internal invariant check failed.")
    # Ingest emits violations before incrementing its row count. Interruption
    # can retain a violation at exactly the next observed position.
    _require(
        d.position < rows[d.side] or (not result.complete and d.position == rows[d.side]),
        "violation position exceeds observed rows",
    )
    if d.code in _SCALAR_CODES:
        _require(d.column in names and len(values) == 1, "scalar violation dimensions mismatch")
        return
    _require(d.column is None, "row/key violations must not select one column")
    if d.code in ("order_violation", "order_tie"):
        _require(isinstance(schema.order, SignificantOrder), "order violation needs ordered policy")
        _require(len(values) == width, "order violation row dimensions mismatch")
        return
    if d.code == "duplicate_normalized_row":
        _require(schema.multiplicity == "distinct", "duplicate row needs distinct policy")
        _require(len(values) == width, "duplicate row dimensions mismatch")
        return
    for key in schema.keys:
        key_width = len(key.columns)
        if isinstance(key.scope, ColumnKeyScope):
            key_width += len(key.scope.columns)
        incomplete = {f"incomplete_{phase}_{key.name}" for phase in ("raw", "normalized")}
        duplicate = {f"duplicate_{phase}_key_{key.name}" for phase in ("raw", "normalized")}
        if d.code in incomplete | duplicate:
            _require(len(values) == key_width, "key violation dimensions mismatch")
            _require(
                key.incomplete == "reject" if d.code in incomplete else key.unique,
                "key violation requires the corresponding declared policy",
            )
            return
    raise ArtifactIntegrityError("unknown contract difference code")


def inspect_evidence(
    result: ComparisonResult,
    root: Path,
    *,
    max_bytes: int,
    max_records: int,
    max_examples: int,
) -> EvidenceInspection:
    """Verify all bounded persisted records without opening source/execution paths.

    The aggregate byte budget includes the manifest and JSONL. Oversized lines
    or manifests fail instead of returning truncated verification. Examples are
    the requested prefix, independent of how many persisted records are checked.
    """
    _limits(max_bytes, max_records, max_examples)
    result = ComparisonResult.model_validate(result)
    path, manifest_size = _manifest(result, root, max_bytes)
    ref = result.differences
    remaining = max_bytes - manifest_size
    if ref.size_bytes > remaining or result.counts.difference_records > max_records:
        raise ResourceLimitError("comparison evidence exceeds report inspection budget")
    digest = hashlib.sha256()
    size = records = violations = added = removed = 0
    codes: Counter[str] = Counter()
    examples: list[ComparisonDifference] = []
    modified: set[tuple[int, int]] = set()
    cells: set[tuple[int, int, str]] = set()
    left_positions: dict[int, int | None] = {}
    right_positions: dict[int, int | None] = {}
    with _open_regular(path) as source:
        _require(os.fstat(source.fileno()).st_size == ref.size_bytes, "difference size mismatch")
        while True:
            line = source.readline(min(_MAX_LINE_BYTES, remaining - size) + 1)
            if not line:
                break
            size += len(line)
            if size > remaining or len(line) > _MAX_LINE_BYTES:
                raise ResourceLimitError("difference line/total exceeds report byte budget")
            records += 1
            if records > max_records:
                raise ResourceLimitError("difference records exceed report record budget")
            digest.update(line)
            difference = _document(line, ComparisonDifference)
            _validate_difference(difference, result)
            if records <= len(result.examples):
                _require(
                    difference == result.examples[records - 1],
                    "manifest examples do not match the persisted prefix",
                )
            if records <= max_examples:
                examples.append(difference)
            codes[difference.code] += 1
            violations += difference.category in ("contract", "schema")
            if difference.category != "content":
                continue
            a, b = difference.position, difference.other_position
            if difference.code == "cell_value":
                if not (a is not None and b is not None and difference.column is not None):
                    raise AssertionError("Internal invariant check failed.")
                cell = (a, b, difference.column)
                _require(cell not in cells, "duplicate aligned cell evidence")
                cells.add(cell)
                _require(
                    left_positions.get(a, b) == b and right_positions.get(b, a) == a,
                    "content positions do not define a one-to-one alignment",
                )
                left_positions[a], right_positions[b] = b, a
                modified.add((a, b))
            else:
                for position, positions in ((a, left_positions), (b, right_positions)):
                    if position is not None:
                        _require(position not in positions, "repeated unmatched row position")
                        positions[position] = None
                added += max(0, difference.left_count - difference.right_count)
                removed += max(0, difference.right_count - difference.left_count)
    _require(
        size == ref.size_bytes and digest.hexdigest() == ref.sha256, "difference hash/size mismatch"
    )
    _require(records == result.counts.difference_records, "difference record count mismatch")
    _require(violations == result.counts.contract_violations, "contract violation count mismatch")
    _require(
        result.counts.matched_rows + len(modified) + added <= result.counts.left_rows
        and result.counts.matched_rows + len(modified) + removed <= result.counts.right_rows,
        "content evidence exceeds observed row counts",
    )
    if result.complete:
        _require(
            result.counts.matched_rows + len(modified) + added == result.counts.left_rows
            and result.counts.matched_rows + len(modified) + removed == result.counts.right_rows,
            "content evidence does not account for completed row counts",
        )
    aligned = result.strategy in ("key", "sequence")
    return EvidenceInspection(
        examples=tuple(examples),
        records=records,
        violations=violations,
        added=added if aligned else None,
        removed=removed if aligned else None,
        modified=len(modified) if aligned else None,
        code_counts=tuple(sorted(codes.items())),
        candidate_excess=added,
        reference_excess=removed,
    )


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _inventory(path: Path, digest: str, size: int) -> dict[str, object]:
    return {"path": path.name, "sha256": digest, "size_bytes": size}


def _write_private(path: Path, data: bytes) -> dict[str, object]:
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600
    )
    with os.fdopen(descriptor, "wb") as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())
    return _inventory(path, hashlib.sha256(data).hexdigest(), len(data))


def _copy_capture(
    ref: ArtifactRef, root: Path, destination: Path, budget: int
) -> dict[str, object]:
    _require(ref.format in ("arrow", "parquet"), "reproduction captures require Arrow/Parquet")
    if ref.size_bytes > budget:
        raise ResourceLimitError("reproduction captures exceed export byte budget")
    source_path = _reference_path(ref, root)
    digest = hashlib.sha256()
    size = 0
    with _open_regular(source_path) as source:
        _require(os.fstat(source.fileno()).st_size == ref.size_bytes, "capture size mismatch")
        descriptor = os.open(
            destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600
        )
        with os.fdopen(descriptor, "wb") as target:
            while block := source.read(min(1024 * 1024, budget - size + 1)):
                size += len(block)
                if size > budget:
                    raise ResourceLimitError("reproduction captures exceed export byte budget")
                digest.update(block)
                target.write(block)
            target.flush()
            os.fsync(target.fileno())
    _require(
        size == ref.size_bytes and digest.hexdigest() == ref.sha256, "capture hash/size mismatch"
    )
    return _inventory(destination, digest.hexdigest(), size)


def export_reproduction(
    result: ComparisonResult,
    root: Path,
    destination: Path,
    *,
    max_bytes: int,
    max_records: int,
) -> dict[str, object]:
    """Export confined captured outputs and context, never execute transformations.

    The caller must separately authorize full data/metadata disclosure. The new
    destination is private on POSIX and must not exist. Only a final
    reproduction.json marks successful publication; failures remove files this
    helper created. This is materialized-comparison context, not original code,
    execution inputs, a promised deterministic replay, or an authenticated proof.
    """
    from equiframe.diff import _DiffReceipt

    _limits(max_bytes, max_records, 0)
    result = ComparisonResult.model_validate(result)
    _require(result.complete, "reproduction requires a complete comparison")
    _require(
        result.left is not None and result.right is not None,
        "reproduction requires both captured outputs",
    )
    if not (result.left is not None and result.right is not None):
        raise AssertionError("Internal invariant check failed.")
    _require(
        result.left.execution is None and result.right.execution is None,
        "execution-backed sources require their independent execution context; export unsupported",
    )
    inspect_evidence(result, root, max_bytes=max_bytes, max_records=max_records, max_examples=0)
    root = _directory(root)
    evidence_path, consumed = _manifest(result, root, max_bytes)
    consumed += result.differences.size_bytes
    context: dict[str, object] = {
        "schema_version": "1.0",
        "scope": "materialized_comparison_only_no_transform_reexecution",
        "spec": result.spec.model_dump(mode="json"),
        "options": result.options.model_dump(mode="json"),
        "reference": result.reference,
        "versions": [item.model_dump(mode="json") for item in result.versions],
    }
    companion = evidence_path.with_name("diff-contract.json")
    try:
        companion.lstat()
    except FileNotFoundError:
        pass
    else:
        receipt, size = _read_document(companion, _DiffReceipt, max_bytes - consumed)
        consumed += size
        _require(
            receipt.comparison_id == result.comparison_id
            and receipt.spec_sha256 == result.spec_sha256
            and receipt.declaration.spec == result.spec
            and receipt.declaration.reference == result.reference,
            "diff declaration does not match the comparison",
        )
        context["diff_declaration"] = receipt.declaration.model_dump(mode="json")
        context["capture_options"] = receipt.capture_options.model_dump(mode="json")
    destination = _absolute(destination)
    _directory(destination.parent)
    files: list[dict[str, object]] = []
    created: list[Path] = []
    made_directory = False
    try:
        destination.mkdir(mode=0o700)
        made_directory = True
        for side, source in (("left", result.left), ("right", result.right)):
            captured = destination / f"{side}.{source.data.format}"
            created.append(captured)
            item = _copy_capture(source.data, evidence_path.parent, captured, max_bytes - consumed)
            consumed += source.data.size_bytes
            files.append(item)
            capture: dict[str, object] = {"data": item | {"format": source.data.format}}
            if source.table is not None:
                table = source.table
                _require(
                    (table.data.sha256, table.data.size_bytes, table.data.format)
                    == (source.data.sha256, source.data.size_bytes, source.data.format),
                    "table context does not identify the captured output",
                )
                _require(
                    table.name == result.spec.contract.output.name
                    and table.row_count
                    == (result.counts.left_rows if side == "left" else result.counts.right_rows)
                    and tuple((column.name, column.arrow_type) for column in table.columns)
                    == source.observed_schema,
                    "table context does not match observed schema/rows",
                )
                capture["table"] = {
                    "name": table.name,
                    "row_count": table.row_count,
                    "columns": [column.model_dump(mode="json") for column in table.columns],
                    "index_columns": [
                        column.model_dump(mode="json") for column in table.index_columns
                    ],
                }
                if table.index is not None:
                    index_path = destination / f"{side}-index.{table.index.format}"
                    created.append(index_path)
                    index_item = _copy_capture(
                        table.index, evidence_path.parent, index_path, max_bytes - consumed
                    )
                    consumed += table.index.size_bytes
                    files.append(index_item)
                    capture["index"] = index_item | {"format": table.index.format}
            context[side] = capture
        data = _json_bytes(context)
        if consumed + len(data) > max_bytes or len(data) > _MAX_DOCUMENT_BYTES:
            raise ResourceLimitError("reproduction context exceeds export byte budget")
        context_path = destination / "context.json"
        created.append(context_path)
        files.append(_write_private(context_path, data))
        consumed += len(data)
        manifest: dict[str, object] = {
            "schema_version": "1.0",
            "scope": "materialized_comparison_only_no_transform_reexecution",
            "complete": True,
            "files": files,
            "context": "context.json",
            "source_state": result.state,
            "source_complete": result.complete,
            "source_spec_sha256": result.spec_sha256,
            "source_contract_sha256": result.contract_sha256,
            "integrity": "hashes_identify_bytes_not_authentication_or_semantic_proof",
        }
        manifest_bytes = _json_bytes(manifest)
        if consumed + len(manifest_bytes) > max_bytes:
            raise ResourceLimitError("reproduction manifest exceeds export byte budget")
        _require(
            {path.name for path in destination.iterdir()} == {item["path"] for item in files},
            "reproduction destination contains files outside the closed inventory",
        )
        final_path = destination / "reproduction.json"
        created.append(final_path)
        _write_private(final_path, manifest_bytes)
        return manifest
    except BaseException:
        for path in reversed(created):
            with suppress(OSError):
                path.unlink(missing_ok=True)
        if made_directory:
            with suppress(OSError):
                destination.rmdir()
        raise
