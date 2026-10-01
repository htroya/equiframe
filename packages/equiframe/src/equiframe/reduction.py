"""Deterministic, budgeted row deletion preserving an explicitly observed failure."""

import time
from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Self
from uuid import uuid4

from pydantic import Field, model_validator

from equiframe._base import FrozenModel, Identifier, NonNegativeInt, PositiveInt, Text
from equiframe.evidence import (
    EventJournal,
    inventory,
    load_json,
    publish_json,
    verify_events,
    verify_files,
)
from equiframe.execution import CancellationToken
from equiframe.local import LocalArtifactStore
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


class ReductionResult(FrozenModel):
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
    global_minimum_claimed: Literal[False] = False
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

    options = ReductionOptions.model_validate(options or ReductionOptions())
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
    directory = (work_dir or Path.cwd() / "equiframe-runs").resolve() / identifier
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
    path = path / "reduction.json" if path.is_dir() else path
    result = load_json(ReductionResult, path)
    verify_files(path.parent, result.evidence)
    from equiframe.errors import ArtifactIntegrityError

    events = verify_events(path.parent / "events.jsonl", operation_id=result.reduction_id)
    if (
        not events
        or events[-1].stage != "reduction"
        or events[-1].state != "finished"
        or events[-1].code != result.status
        or sum(e.stage == "predicate" and e.state == "started" for e in events)
        != result.evaluations
        or sum(e.stage == "reduction" and e.state == "accepted" for e in events)
        != result.accepted_candidates
    ):
        raise ArtifactIntegrityError("reduction journal contradicts final result")
    return result
