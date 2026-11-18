"""Deterministic, budgeted row deletion preserving an explicitly observed failure."""

import time
from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Self

from equiframe._base import (
    FrozenModel,
    Identifier,
    NonNegativeInt,
    PositiveInt,
    Text,
    _ExplicitOutcome,
    strict_bool_literal,
)
from equiframe._regular_io import local_output_directory
from equiframe.evidence import (
    MAX_DOCUMENT_BYTES,
    EventJournal,
    EvidenceEvent,
    inventory,
    load_json,
    parse_json,
    publish_json,
    verify_events,
    verify_files,
)
from equiframe.execution import CancellationToken
from equiframe.local import LocalArtifactStore, local_path
from equiframe.pipeline_types import EvidenceFile
from equiframe.tables import ArrowInput
from equiframe.types import ArtifactRef


class ReductionOptions(FrozenModel):
    max_evaluations: PositiveInt = 100
    timeout_seconds: Annotated[float, Field(gt=0)] = 60.0
    confirmations: Annotated[int, Field(ge=1, le=5)] = 2
    max_input_rows: PositiveInt = 100_000


class ReductionObservation(FrozenModel):
    preconditions: Literal["satisfied", "violated", "not_evaluable"]
    failure_signature: Identifier | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.preconditions != "satisfied" and self.failure_signature is not None:
            raise ValueError("a failure is admissible only with satisfied preconditions")
        return self


class ReducedTable(FrozenModel):
    name: Identifier
    original: ArtifactRef
    reduced: ArtifactRef
    original_rows: NonNegativeInt
    retained_positions: tuple[NonNegativeInt, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if tuple(sorted(set(self.retained_positions))) != self.retained_positions or any(
            index >= self.original_rows for index in self.retained_positions
        ):
            raise ValueError("retained positions must be unique, ordered original row positions")
        return self


class ReductionResult(_ExplicitOutcome, FrozenModel):
    _truth_value_guidance = "inspect .status, .baseline_verified and .minimality explicitly"

    schema_version: Literal["1.0"] = "1.0"
    reduction_id: Identifier
    predicate_version: Text
    failure_signature: Identifier
    options: ReductionOptions
    status: Literal[
        "reduced",
        "unchanged",
        "budget_exhausted",
        "cancelled",
        "invalid_baseline",
        "evaluation_failed",
    ]
    baseline_verified: bool
    evaluations: NonNegativeInt
    accepted_candidates: NonNegativeInt
    elapsed_seconds: Annotated[float, Field(ge=0)]
    minimality: Literal["one_minimal", "not_established"]
    global_minimum_claimed: Annotated[Literal[False], BeforeValidator(strict_bool_literal)] = False
    tables: tuple[ReducedTable, ...]
    evidence: tuple[EvidenceFile, ...]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.evaluations > self.options.max_evaluations:
            raise ValueError("evaluation budget exceeded")
        if self.minimality == "one_minimal" and (
            not self.baseline_verified or self.status not in ("reduced", "unchanged")
        ):
            raise ValueError("minimality requires a verified, exhaustive local search")
        if not self.baseline_verified and self.accepted_candidates:
            raise ValueError("cannot accept reductions of an unverified baseline")
        if len({table.name for table in self.tables}) != len(self.tables):
            raise ValueError("duplicate table names")
        if len({item.path for item in self.evidence}) != len(self.evidence):
            raise ValueError("duplicate evidence paths")
        return self


class _Stop(Exception):
    def __init__(self, status: Literal["budget_exhausted", "cancelled", "evaluation_failed"]):
        self.status = status


def reduce_case(
    inputs: Mapping[str, ArrowInput],
    *,
    predicate: Callable[[Mapping[str, ArrowInput]], ReductionObservation],
    predicate_version: str,
    failure_signature: str,
    options: ReductionOptions | None = None,
    work_dir: Path | None = None,
    cancellation: CancellationToken | None = None,
) -> ReductionResult:
    """Delete row chunks across tables, preserving order, schema and duplicate identity.

    The trusted predicate must check every required precondition and reproduce the
    SAME target failure. No SQL/callback is loaded from JSON. Timings are cooperative;
    a blocking callback cannot be preempted. A successful late callback is not accepted.
    """
    import pyarrow as pa
    from pydantic import TypeAdapter

    options = ReductionOptions.model_validate(ReductionOptions() if options is None else options)
    TypeAdapter(Identifier).validate_python(failure_signature, strict=True)
    TypeAdapter(Text).validate_python(predicate_version, strict=True)
    names = tuple(sorted(inputs))
    for name in names:
        TypeAdapter(Identifier).validate_python(name, strict=True)
    if not names or any(not isinstance(inputs[name], ArrowInput) for name in names):
        raise ValueError("named Arrow inputs are required")
    tables = {name: inputs[name].table for name in names}
    if any(not isinstance(table, pa.Table) for table in tables.values()):
        raise ValueError("reduction requires materialized Arrow tables")
    if sum(table.num_rows for table in tables.values()) > options.max_input_rows:
        raise ValueError("reduction input row budget exceeded")
    identifier = "reduction_" + uuid4().hex
    directory = (
        local_output_directory(Path.cwd() / "equiframe-runs" if work_dir is None else work_dir)
        / identifier
    )
    directory.mkdir(parents=True, exist_ok=False)
    token = cancellation if cancellation is not None else CancellationToken()
    journal = EventJournal(directory, identifier)
    journal.emit("reduction", "started", "reduction_started")
    publish_json(options, directory / "options.json")
    store = LocalArtifactStore(directory / "artifacts")

    def capture(name: str, table: pa.Table, kind: str) -> ArtifactRef:
        path = directory / f"{name}.{kind}.arrow"
        with path.open("xb") as stream, pa.ipc.new_file(stream, table.schema) as writer:
            writer.write_table(table)
        return store.put(path, media_type="application/vnd.apache.arrow.file")

    original = {name: capture(name, tables[name], "original") for name in names}
    selected = tuple((name, index) for name in names for index in range(tables[name].num_rows))
    evaluations = accepted = 0
    start = time.perf_counter()
    deadline = start + options.timeout_seconds

    def check_budget(*, count: bool) -> None:
        if token.cancelled:
            raise _Stop("cancelled")
        if time.perf_counter() >= deadline or (count and evaluations >= options.max_evaluations):
            raise _Stop("budget_exhausted")

    def positions(candidate: tuple[tuple[str, int], ...]) -> dict[str, tuple[int, ...]]:
        grouped: dict[str, list[int]] = {name: [] for name in names}
        for name, index in candidate:
            grouped[name].append(index)
        return {name: tuple(grouped[name]) for name in names}

    def materialize(candidate: tuple[tuple[str, int], ...]) -> Mapping[str, ArrowInput]:
        indexes = positions(candidate)
        return MappingProxyType(
            {
                name: ArrowInput(tables[name].take(pa.array(indexes[name], type=pa.int64())))
                for name in names
            }
        )

    def preserves(candidate: tuple[tuple[str, int], ...]) -> bool:
        nonlocal evaluations
        for _ in range(options.confirmations):
            check_budget(count=True)
            evaluations += 1
            attempt = directory / f"attempt-{evaluations:06d}"
            attempt.mkdir()
            publish_json({"positions": positions(candidate)}, attempt / "selection.json")
            journal.emit("predicate", "started", "predicate_started")
            try:
                observation = ReductionObservation.model_validate(predicate(materialize(candidate)))
            except Exception:
                publish_json({"code": "predicate_failed"}, attempt / "error.json")
                journal.emit("predicate", "failed", "predicate_failed")
                raise _Stop("evaluation_failed") from None
            publish_json(observation, attempt / "observation.json")
            matched = observation.preconditions == "satisfied" and (
                observation.failure_signature == failure_signature
            )
            journal.emit("predicate", "finished", "matched" if matched else "not_preserved")
            check_budget(count=False)
            if not matched:
                return False
        return True

    baseline_verified = False
    status: Literal[
        "reduced",
        "unchanged",
        "budget_exhausted",
        "cancelled",
        "invalid_baseline",
        "evaluation_failed",
    ] = "unchanged"
    minimality: Literal["one_minimal", "not_established"] = "not_established"
    try:
        baseline_verified = preserves(selected)
        if not baseline_verified:
            status = "invalid_baseline"
        else:
            granularity = 2
            while selected:
                width = max(1, (len(selected) + granularity - 1) // granularity)
                changed = False
                for offset in range(0, len(selected), width):
                    candidate = selected[:offset] + selected[offset + width :]
                    if preserves(candidate):
                        selected = candidate
                        accepted += 1
                        journal.emit("reduction", "accepted", "failure_preserved")
                        granularity = max(2, granularity - 1)
                        changed = True
                        break
                if changed:
                    continue
                if width == 1:
                    break
                granularity = min(len(selected), granularity * 2)
            status = "reduced" if accepted else "unchanged"
            minimality = "one_minimal"
    except _Stop as stopped:
        status = stopped.status
    retained = positions(selected)
    reduced = materialize(selected)
    results = tuple(
        ReducedTable(
            name=name,
            original=original[name],
            reduced=capture(name, reduced[name].table, "reduced"),
            original_rows=tables[name].num_rows,
            retained_positions=retained[name],
        )
        for name in names
    )
    journal.emit("reduction", "finished", status)
    result = ReductionResult(
        reduction_id=identifier,
        predicate_version=predicate_version,
        failure_signature=failure_signature,
        options=options,
        status=status,
        baseline_verified=baseline_verified,
        evaluations=evaluations,
        accepted_candidates=accepted,
        elapsed_seconds=time.perf_counter() - start,
        minimality=minimality,
        tables=results,
        evidence=inventory(directory),
    )
    publish_json(result, directory / "reduction.json")
    return result


def read_reduction(path: Path) -> ReductionResult:
    """Verify recorded decisions and row provenance without invoking the predicate."""
    path = path / "reduction.json" if path.is_dir() else path
    result = load_json(ReductionResult, path)
    directory = path.parent
    verify_files(directory, result.evidence)
    from equiframe.errors import ArtifactIntegrityError

    listed = {item.path: item for item in result.evidence}
    if not {"events.jsonl", "options.json"} <= listed.keys() or not result.tables:
        raise ArtifactIntegrityError("reduction is missing required evidence")
    if load_json(ReductionOptions, directory / "options.json") != result.options:
        raise ArtifactIntegrityError("reduction options contradict the recorded configuration")
    events = verify_events(directory / "events.jsonl", operation_id=result.reduction_id)
    if (
        len(events) < 2
        or (events[0].stage, events[0].state, events[0].code)
        != ("reduction", "started", "reduction_started")
        or events[-1].stage != "reduction"
        or events[-1].state != "finished"
        or events[-1].code != result.status
        or sum(e.stage == "predicate" and e.state == "started" for e in events)
        != result.evaluations
        or sum(e.stage == "reduction" and e.state == "accepted" for e in events)
        != result.accepted_candidates
    ):
        raise ArtifactIntegrityError("reduction journal contradicts final result")
    _verify_reduction_tables(result, directory, listed)
    _verify_reduction_attempts(result, directory, listed, events)
    return result


def _verify_reduction_tables(
    result: ReductionResult, directory: Path, listed: Mapping[str, EvidenceFile]
) -> None:
    import hashlib

    import pyarrow as pa

    from equiframe.errors import ArtifactIntegrityError

    root = directory.resolve()
    total_rows = 0
    for table in result.tables:
        paths: dict[str, Path] = {}
        for kind, ref in (("original", table.original), ("reduced", table.reduced)):
            named = listed.get(f"{table.name}.{kind}.arrow")
            artifact = local_path(ref).resolve()
            if not artifact.is_relative_to(root):
                raise ArtifactIntegrityError("reduction artifact escapes its operation directory")
            item = listed.get(artifact.relative_to(root).as_posix())
            if (
                named is None
                or item is None
                or ref.format != "arrow"
                or ref.media_type != "application/vnd.apache.arrow.file"
                or ref.schema_ref is not None
                or (ref.sha256, ref.size_bytes) != (item.sha256, item.size_bytes)
                or (ref.sha256, ref.size_bytes) != (named.sha256, named.size_bytes)
            ):
                raise ArtifactIntegrityError("reduction artifact contradicts its captured table")
            paths[kind] = artifact
        with paths["original"].open("rb") as stream, pa.ipc.open_file(stream) as reader:
            original = reader.read_all()
        original.validate(full=True)
        total_rows += original.num_rows
        if original.num_rows != table.original_rows or total_rows > result.options.max_input_rows:
            raise ArtifactIntegrityError("original table row count contradicts the reduction")
        expected = original.take(pa.array(table.retained_positions, type=pa.int64()))
        sink = pa.BufferOutputStream()
        with pa.ipc.new_file(sink, expected.schema) as writer:
            writer.write_table(expected)
        if hashlib.sha256(sink.getvalue()).hexdigest() != table.reduced.sha256:
            raise ArtifactIntegrityError(
                "reduced table does not preserve its recorded row positions"
            )


def _verify_reduction_attempts(
    result: ReductionResult,
    directory: Path,
    listed: Mapping[str, EvidenceFile],
    events: tuple[EvidenceEvent, ...],
) -> None:
    from pydantic import TypeAdapter

    from equiframe.errors import ArtifactIntegrityError

    names = tuple(table.name for table in result.tables)
    original_rows = {table.name: table.original_rows for table in result.tables}
    current = tuple((name, index) for name in names for index in range(original_rows[name]))
    initial = current
    pending: tuple[tuple[str, int], ...] | None = None
    matches = evaluation = accepted = baseline_matches = 0
    rejected: set[tuple[tuple[str, int], ...]] = set()
    required_attempts: set[str] = set()
    last_outcome = ""
    index = 1
    while index < len(events) - 1:
        event = events[index]
        if (event.stage, event.state, event.code) == ("reduction", "accepted", "failure_preserved"):
            if pending is None or matches != result.options.confirmations:
                raise ArtifactIntegrityError("accepted reduction lacks matching confirmations")
            current = pending
            accepted += 1
            pending = None
            matches = 0
            rejected.clear()
            index += 1
            continue
        if (event.stage, event.state, event.code) != ("predicate", "started", "predicate_started"):
            raise ArtifactIntegrityError("unexpected reduction journal transition")
        evaluation += 1
        attempt = f"attempt-{evaluation:06d}/"
        selection_file = attempt + "selection.json"
        required_attempts.add(selection_file)
        if selection_file not in listed:
            raise ArtifactIntegrityError("predicate selection is missing from the inventory")
        with (directory / selection_file).open("rb") as stream:
            data = stream.read(MAX_DOCUMENT_BYTES + 1)
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ArtifactIntegrityError("predicate selection exceeds the verification budget")
        selection = parse_json(data)
        if not isinstance(selection, dict) or set(selection) != {"positions"}:
            raise ArtifactIntegrityError("invalid predicate selection")
        positions = selection["positions"]
        if not isinstance(positions, dict) or set(positions) != set(names):
            raise ArtifactIntegrityError("predicate selection has different input tables")
        candidate_items: list[tuple[str, int]] = []
        for name in names:
            indexes = positions[name]
            if not isinstance(indexes, list):
                raise ArtifactIntegrityError("invalid predicate row positions")
            validated = tuple(
                TypeAdapter(NonNegativeInt).validate_python(i, strict=True) for i in indexes
            )
            if tuple(sorted(set(validated))) != validated or any(
                i >= original_rows[name] for i in validated
            ):
                raise ArtifactIntegrityError("invalid predicate row positions")
            candidate_items.extend((name, i) for i in validated)
        candidate = tuple(candidate_items)
        baseline = evaluation <= result.options.confirmations
        if not result.baseline_verified or baseline:
            if candidate != initial:
                raise ArtifactIntegrityError("baseline observations belong to different rows")
        elif not set(candidate) < set(current) or (pending is not None and candidate != pending):
            raise ArtifactIntegrityError(
                "predicate candidate is not a deletion of the current case"
            )
        index += 1
        if index >= len(events) - 1:
            raise ArtifactIntegrityError("predicate attempt has no recorded outcome")
        outcome = events[index]
        if (outcome.stage, outcome.state, outcome.code) == (
            "predicate",
            "failed",
            "predicate_failed",
        ):
            error_file = attempt + "error.json"
            required_attempts.add(error_file)
            if error_file not in listed or parse_json((directory / error_file).read_bytes()) != {
                "code": "predicate_failed"
            }:
                raise ArtifactIntegrityError(
                    "predicate failure evidence is missing or inconsistent"
                )
            if result.status != "evaluation_failed" or index != len(events) - 2:
                raise ArtifactIntegrityError("predicate failure contradicts the final status")
            last_outcome = "predicate_failed"
            index += 1
            continue
        observation_file = attempt + "observation.json"
        required_attempts.add(observation_file)
        if observation_file not in listed:
            raise ArtifactIntegrityError("predicate observation is missing from the inventory")
        observation = load_json(ReductionObservation, directory / observation_file)
        matched = observation.preconditions == "satisfied" and (
            observation.failure_signature == result.failure_signature
        )
        code = "matched" if matched else "not_preserved"
        if (outcome.stage, outcome.state, outcome.code) != ("predicate", "finished", code):
            raise ArtifactIntegrityError("predicate observation contradicts its journal outcome")
        if result.baseline_verified and baseline:
            if not matched:
                raise ArtifactIntegrityError(
                    "verified baseline does not reproduce the target failure"
                )
            baseline_matches += 1
        elif matched:
            pending = candidate
            matches += 1
            if matches > result.options.confirmations:
                raise ArtifactIntegrityError("predicate confirmations exceed the configured count")
        else:
            rejected.add(candidate)
            pending = None
            matches = 0
        last_outcome = code
        index += 1
    if (
        evaluation != result.evaluations
        or accepted != result.accepted_candidates
        or (result.baseline_verified and baseline_matches != result.options.confirmations)
        or {item for item in listed if item.startswith("attempt-")} != required_attempts
        or current
        != tuple((table.name, i) for table in result.tables for i in table.retained_positions)
    ):
        raise ArtifactIntegrityError("reduction attempts contradict the final result")
    if result.status == "invalid_baseline" and (
        result.baseline_verified or last_outcome != "not_preserved"
    ):
        raise ArtifactIntegrityError("invalid baseline status contradicts its observations")
    if result.status == "evaluation_failed" and last_outcome != "predicate_failed":
        raise ArtifactIntegrityError("evaluation failure lacks a failed predicate attempt")
    if result.status in ("reduced", "unchanged"):
        if (
            not result.baseline_verified
            or pending is not None
            or ((result.status == "reduced") != bool(accepted))
        ):
            raise ArtifactIntegrityError("successful reduction status contradicts its search")
        if result.minimality == "one_minimal" and any(
            current[:offset] + current[offset + 1 :] not in rejected
            for offset in range(len(current))
        ):
            raise ArtifactIntegrityError("one-minimal claim lacks the individual deletion checks")
