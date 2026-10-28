"""Operational rules over one captured execution; never invokes a comparator or ETL."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as _timezone
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Literal
from uuid import uuid4

from equiframe._decimal import exact_decimal_context
from equiframe._document_io import read_document
from equiframe._error_reporting import report_failure
from equiframe._regular_io import local_input_path, local_output_directory
from equiframe.comparison_types import ComparisonPolicy, ComparisonValue
from equiframe.contracts import (
    AggregateCheck,
    CardinalityCheck,
    ColumnKeyScope,
    Contract,
    JoinCheck,
    KeyCheck,
    OrderCheck,
    RuleDefinition,
    SchemaCheck,
    SignificantOrder,
    TableSpec,
)
from equiframe.errors import (
    ArtifactIntegrityError,
    CapabilityError,
    ExecutionCancelled,
    ExecutionTimeout,
    ResourceLimitError,
)
from equiframe.execution import CancellationToken
from equiframe.execution_types import ExecutionResult
from equiframe.local import LocalArtifactStore, local_path
from equiframe.normalization import (
    equal,
    identity,
    normalize,
    number,
    order_value,
    physical_value,
    schema_compatible,
)
from equiframe.rule_types import (
    CheckResult,
    CheckState,
    RuleCoverage,
    RuleEvaluation,
    RuleFinding,
    RuleOptions,
)
from equiframe.serialization import _constant, _JsonObject, _unique_objects, contract_fingerprint
from equiframe.tables import read_table
from equiframe.types import ArtifactRef, DecisionState

UTC = _timezone.utc

if TYPE_CHECKING:
    import pyarrow as pa

RuleFunction = Callable[[RuleDefinition, "RuleContext"], None]
RuleKind = Literal["schema", "key", "cardinality", "join", "order", "aggregate"]


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _ref(path: Path) -> ArtifactRef:
    data = path.read_bytes()
    return ArtifactRef(
        schema_version="1.0",
        uri=path.resolve().as_uri(),
        sha256=hashlib.sha256(data).hexdigest(),
        format="jsonl",
        media_type="application/x-ndjson",
        size_bytes=len(data),
    )


@dataclass(frozen=True)
class RuleImplementation:
    kind: RuleKind
    revision: int
    identity: str
    evaluate: RuleFunction


class RuleRegistry:
    """Explicit trusted implementations; source bytes and revision enter the freeze hash."""

    def __init__(self) -> None:
        self._items: dict[RuleKind, RuleImplementation] = {}

    def register(self, kind: RuleKind, revision: int, evaluate: RuleFunction) -> None:
        if kind in self._items or revision < 1:
            raise ValueError("duplicate rule kind or invalid implementation revision")
        try:
            source_path = inspect.getsourcefile(evaluate)
            if source_path is None:
                raise OSError("source path unavailable")
            source = Path(source_path).read_bytes()
            # Built-in semantic helpers are part of R's implementation identity.
            if evaluate.__module__ == __name__:
                helper_path = inspect.getsourcefile(normalize)
                if helper_path is None:
                    raise OSError("normalization source path unavailable")
                source += Path(helper_path).read_bytes()
        except (OSError, TypeError) as error:
            raise ValueError("rule implementation must have inspectable source") from error
        digest = hashlib.sha256(source).hexdigest()
        name = f"{evaluate.__module__}.{evaluate.__qualname__}"
        self._items[kind] = RuleImplementation(
            kind, revision, f"{name}@{revision}:{digest}", evaluate
        )

    def resolve(self, kind: RuleKind) -> RuleImplementation | None:
        return self._items.get(kind)

    def identities(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((kind, item.identity) for kind, item in self._items.items()))


def default_rule_registry() -> RuleRegistry:
    result = RuleRegistry()
    implementations: tuple[tuple[RuleKind, RuleFunction], ...] = (
        ("schema", _schema),
        ("key", _key),
        ("cardinality", _cardinality),
        ("join", _join),
        ("order", _order),
        ("aggregate", _aggregate),
    )
    for kind, function in implementations:
        result.register(kind, 1, function)
    return result


def rule_set_fingerprint(contract: Contract, registry: RuleRegistry, options: RuleOptions) -> str:
    """Freeze exact contract, rule code, and resource/configuration choices."""
    return hashlib.sha256(
        _json(
            {
                "contract_sha256": contract_fingerprint(contract),
                "implementations": registry.identities(),
                "options": options.model_dump(mode="json"),
                "format": "equiframe-rules-1.0",
            }
        )
    ).hexdigest()


class RuleContext:
    """Only declared contract and verified tables are visible to a rule implementation."""

    def __init__(
        self,
        contract: Contract,
        tables: Mapping[str, pa.Table],
        options: RuleOptions,
        cancellation: CancellationToken,
        started: float,
    ) -> None:
        self.contract, self.tables, self.options = contract, tables, options
        self.cancellation, self.started = cancellation, started
        self.work = self.examined = self.violations = self.evidence_bytes = 0
        self.examples: list[RuleFinding] = []
        self.check_id = ""
        self.sink: BinaryIO | None = None

    def checkpoint(self, cost: int = 1) -> None:
        self.work += cost
        if self.cancellation.cancelled:
            raise ExecutionCancelled("rule evaluation cancelled at checkpoint")
        if (
            self.options.timeout_seconds is not None
            and time.perf_counter() - self.started >= self.options.timeout_seconds
        ):
            raise ExecutionTimeout("cooperative rule evaluation timeout")
        if self.work > self.options.max_work:
            raise ResourceLimitError("rule max_work exhausted")

    def table(self, name: str) -> pa.Table:
        self.checkpoint()
        if name not in self.tables:
            raise CapabilityError("captured table unavailable: " + name)
        return self.tables[name]

    def spec(self, name: str) -> TableSpec:
        return next(t for t in (*self.contract.inputs, self.contract.output) if t.name == name)

    def rows(
        self, name: str, columns: tuple[str, ...]
    ) -> Iterator[tuple[int, tuple[ComparisonValue, ...]]]:
        table = self.table(name)
        missing = set(columns) - set(table.column_names)
        if missing:
            raise CapabilityError("missing columns in " + name + ": " + ", ".join(sorted(missing)))
        declared = {column.name: column for column in self.spec(name).schema_spec.columns}
        for column_name in columns:
            if not schema_compatible(
                table.schema.field(column_name).type, declared[column_name], ComparisonPolicy()
            ):
                raise CapabilityError("incompatible captured type: " + name + "." + column_name)
        for position in range(table.num_rows):
            self.checkpoint()
            self.examined += 1
            if self.examined > self.options.max_rows:
                raise ResourceLimitError("rule max_rows exhausted")
            values = tuple(
                normalize(physical_value(table[name][position]), declared[name])[0]
                for name in columns
            )
            yield position, values

    def emit(
        self,
        code: str,
        table: str,
        *,
        position: int | None = None,
        column: str | None = None,
        observed: tuple[ComparisonValue, ...] = (),
        expected: tuple[ComparisonValue, ...] = (),
        message: str | None = None,
    ) -> None:
        finding = RuleFinding(
            check_id=self.check_id,
            code=code,
            table=table,
            position=position,
            column=column,
            observed=observed,
            expected=expected,
            message=message or code.replace("_", " "),
        )
        if not (self.sink is not None):
            raise AssertionError("Internal invariant check failed.")
        block = _json(finding.model_dump(mode="json")) + b"\n"
        if self.evidence_bytes + len(block) > self.options.max_evidence_bytes:
            raise ResourceLimitError("rule max_evidence_bytes exhausted")
        self.sink.write(block)
        self.evidence_bytes += len(block)
        self.violations += 1
        if len(self.examples) < self.options.max_examples:
            self.examples.append(finding)
        self.checkpoint()


def _schema(definition: RuleDefinition, context: RuleContext) -> None:
    if not (isinstance(definition, SchemaCheck)):
        raise AssertionError("Internal invariant check failed.")
    table = context.table(definition.table)
    columns = context.spec(definition.table).schema_spec.columns
    expected_names = tuple(column.name for column in columns)
    if tuple(table.column_names) != expected_names:
        context.emit(
            "schema_columns",
            definition.table,
            message=f"expected columns {expected_names!r}; observed {tuple(table.column_names)!r}",
        )
    for column in columns:
        if column.name not in table.column_names:
            continue
        try:
            compatible = schema_compatible(
                table.schema.field(column.name).type, column, ComparisonPolicy()
            )
        except CapabilityError:
            compatible = False
        if not compatible:
            context.emit(
                "schema_type",
                definition.table,
                column=column.name,
                message=(
                    f"expected {column.logical_type!r}; "
                    f"observed {table.schema.field(column.name).type}"
                ),
            )
            continue
        for position, values in context.rows(definition.table, (column.name,)):
            _, issues = normalize(physical_value(table[column.name][position]), column)
            for issue in issues:
                context.emit(
                    issue, definition.table, position=position, column=column.name, observed=values
                )


def _key(definition: RuleDefinition, context: RuleContext) -> None:
    if not (isinstance(definition, KeyCheck)):
        raise AssertionError("Internal invariant check failed.")
    key = next(
        k for k in context.spec(definition.table).schema_spec.keys if k.name == definition.key
    )
    scope = key.scope.columns if isinstance(key.scope, ColumnKeyScope) else ()
    seen: dict[tuple[object, ...], int] = {}
    for position, values in context.rows(definition.table, (*scope, *key.columns)):
        scoped, keyed = values[: len(scope)], values[len(scope) :]
        if any(value.kind == "null" for value in keyed):
            if key.incomplete == "reject":
                context.emit("incomplete_key", definition.table, position=position, observed=keyed)
            continue
        token = tuple(identity(v) for v in (*scoped, *keyed))
        if key.unique and token in seen:
            context.emit(
                "duplicate_key",
                definition.table,
                position=position,
                observed=keyed,
                message=f"duplicate key; first position {seen[token]}",
            )
        else:
            seen[token] = position


def _cardinality(definition: RuleDefinition, context: RuleContext) -> None:
    if not (isinstance(definition, CardinalityCheck)):
        raise AssertionError("Internal invariant check failed.")
    count = context.table(definition.table).num_rows
    if count < definition.minimum or (
        definition.maximum is not None and count > definition.maximum
    ):
        context.emit(
            "row_count",
            definition.table,
            observed=(ComparisonValue(kind="integer", value=str(count)),),
            message=f"row count {count}; expected {definition.minimum}..{definition.maximum}",
        )


def _join(definition: RuleDefinition, context: RuleContext) -> None:
    if not (isinstance(definition, JoinCheck)):
        raise AssertionError("Internal invariant check failed.")
    sides: list[dict[tuple[object, ...], list[int]]] = []
    for name, columns in (
        (definition.left_table, definition.left_columns),
        (definition.right_table, definition.right_columns),
    ):
        groups: dict[tuple[object, ...], list[int]] = {}
        for position, values in context.rows(name, columns):
            if any(value.kind == "null" for value in values):
                if definition.unmatched == "reject":
                    context.emit("unmatched_null_key", name, position=position, observed=values)
                continue
            groups.setdefault(tuple(identity(v) for v in values), []).append(position)
        sides.append(groups)
    left, right = sides
    unique_left = definition.relationship in ("one_to_one", "one_to_many")
    unique_right = definition.relationship in ("one_to_one", "many_to_one")
    for name, groups, require_unique, other in (
        (definition.left_table, left, unique_left, right),
        (definition.right_table, right, unique_right, left),
    ):
        for token, positions in groups.items():
            context.checkpoint()
            if require_unique and len(positions) > 1:
                context.emit(
                    "join_cardinality",
                    name,
                    position=positions[1],
                    message=f"key multiplicity {len(positions)}",
                )
            if definition.unmatched == "reject" and token not in other:
                context.emit(
                    "unmatched_key",
                    name,
                    position=positions[0],
                    message=f"{len(positions)} rows have no partner",
                )


def _order(definition: RuleDefinition, context: RuleContext) -> None:
    if not (isinstance(definition, OrderCheck)):
        raise AssertionError("Internal invariant check failed.")
    policy = context.spec(definition.table).schema_spec.order
    if not (isinstance(policy, SignificantOrder)):
        raise AssertionError("Internal invariant check failed.")
    previous: tuple[ComparisonValue, ...] | None = None
    for position, values in context.rows(definition.table, definition.columns):
        if previous is not None:
            direction = 0
            for old, new, sort in zip(previous, values, policy.by, strict=True):
                if old.kind == "null" or new.kind == "null":
                    if old.kind == new.kind:
                        continue
                    direction = -1 if (old.kind == "null") == (sort.nulls == "first") else 1
                else:
                    a, b = order_value(old), order_value(new)
                    direction = -1 if a < b else 1 if a > b else 0
                    if sort.direction == "descending":
                        direction = -direction
                if direction:
                    break
            if direction > 0:
                context.emit(
                    "out_of_order",
                    definition.table,
                    position=position,
                    observed=values,
                    expected=previous,
                )
            elif direction == 0 and policy.ties == "reject":
                context.emit("order_tie", definition.table, position=position, observed=values)
        previous = values


def _aggregate(definition: RuleDefinition, context: RuleContext) -> None:
    if not (isinstance(definition, AggregateCheck)):
        raise AssertionError("Internal invariant check failed.")
    source_columns = (*definition.group_by, *((definition.measure,) if definition.measure else ()))
    groups: dict[tuple[object, ...], tuple[tuple[ComparisonValue, ...], list[ComparisonValue]]] = {}
    source_rows = 0
    for _, values in context.rows(definition.table, source_columns):
        source_rows += 1
        group_values = values[: len(definition.group_by)]
        token = tuple(identity(v) for v in group_values)
        if token not in groups:
            groups[token] = group_values, []
        if definition.measure is None or values[-1].kind != "null":
            groups[token][1].append(
                values[-1] if definition.measure else ComparisonValue(kind="integer", value="1")
            )
    if not definition.group_by and source_rows == 0:
        groups[()] = (), []
    observed: dict[tuple[object, ...], tuple[int, ComparisonValue]] = {}
    for position, values in context.rows(
        definition.output_table, (*definition.group_by, definition.output_column)
    ):
        token = tuple(identity(v) for v in values[:-1])
        if token in observed:
            context.emit(
                "duplicate_group", definition.output_table, position=position, observed=values
            )
        observed[token] = position, values[-1]
        if token not in groups:
            context.emit(
                "unexpected_group", definition.output_table, position=position, observed=values
            )
    target = next(
        c
        for c in context.spec(definition.output_table).schema_spec.columns
        if c.name == definition.output_column
    )
    for group_token, (group_values, members) in groups.items():
        context.checkpoint()
        if group_token not in observed:
            context.emit("missing_group", definition.output_table, observed=group_values)
            continue
        position, actual = observed[group_token]
        expected: ComparisonValue
        if definition.function == "count":
            expected = ComparisonValue(kind="integer", value=str(len(members)))
        elif not members:
            expected = ComparisonValue(kind="null")
        elif definition.function in ("min", "max"):
            expected = (min if definition.function == "min" else max)(members, key=order_value)
        else:
            if members[0].kind == "float":
                if target.numeric_policy is None or target.numeric_policy.tolerance is None:
                    raise CapabilityError(
                        "float sum requires a declared tolerance to account for rounding"
                    )
                exact = sum((number(v) for v in members), Fraction())
                if actual.kind != "float":
                    context.emit(
                        "aggregate_value",
                        definition.output_table,
                        position=position,
                        observed=(actual,),
                    )
                    continue
                got = number(actual)
                tolerance = target.numeric_policy.tolerance
                bound = max(
                    Fraction(tolerance.absolute or 0),
                    Fraction(tolerance.relative or 0) * max(abs(exact), abs(got)),
                )
                if abs(exact - got) > bound:
                    context.emit(
                        "aggregate_value",
                        definition.output_table,
                        position=position,
                        observed=(actual,),
                        message="float sum outside declared tolerance",
                    )
                continue
            if members[0].kind == "integer":
                expected = ComparisonValue(
                    kind="integer", value=str(sum(int(v.value or "0") for v in members))
                )
            else:
                with localcontext(exact_decimal_context()) as decimal_context:
                    decimal_context.prec = 1000
                    value = sum((Decimal(v.value or "0") for v in members), Decimal())
                expected = ComparisonValue(kind="decimal", value=str(value))
        if not equal(actual, expected, target):
            context.emit(
                "aggregate_value",
                definition.output_table,
                position=position,
                observed=(actual,),
                expected=(expected,),
            )


def _verified_tables(execution: ExecutionResult, options: RuleOptions) -> dict[str, pa.Table]:
    if execution.state != "completed":
        raise CapabilityError("execution state is " + execution.state)
    if execution.output is None:
        raise CapabilityError("completed execution lacks output")
    declared = {item.name for item in execution.plan.contract.inputs}
    artifacts = (*execution.inputs, execution.output)
    if (
        len(execution.inputs) != len(declared)
        or {item.name for item in execution.inputs} != declared
    ):
        raise CapabilityError("captured inputs do not match contract")
    if execution.output.name != execution.plan.contract.output.name:
        raise CapabilityError("captured output name does not match contract")
    result: dict[str, pa.Table] = {}
    total_bytes = 0
    actual_bytes = 0
    decoded_bytes = 0
    for artifact in artifacts:
        total_bytes += artifact.data.size_bytes
        actual_bytes += local_path(artifact.data).stat().st_size
        if total_bytes > options.max_artifact_bytes or actual_bytes > options.max_artifact_bytes:
            raise ResourceLimitError("rule max_artifact_bytes exhausted")
        table = read_table(artifact.data)
        decoded_bytes += table.nbytes
        if decoded_bytes > options.max_artifact_bytes:
            raise ResourceLimitError("decoded table exceeds rule max_artifact_bytes")
        if table.num_rows != artifact.row_count:
            raise ArtifactIntegrityError("captured row count does not match table")
        if tuple(table.column_names) != tuple(column.name for column in artifact.columns):
            raise ArtifactIntegrityError("captured columns do not match table")
        for column in artifact.columns:
            array = table[column.name]
            import pyarrow as pa
            import pyarrow.compute as pc

            nan_count = (
                int(pc.sum(pc.is_nan(array)).as_py() or 0)
                if pa.types.is_floating(array.type)
                else 0
            )
            if (
                str(array.type) != column.arrow_type
                or array.null_count != column.null_count
                or nan_count != column.nan_count
            ):
                raise ArtifactIntegrityError("captured physical column metadata mismatch")
        if artifact.index is not None:
            total_bytes += artifact.index.size_bytes
            actual_bytes += local_path(artifact.index).stat().st_size
            if (
                total_bytes > options.max_artifact_bytes
                or actual_bytes > options.max_artifact_bytes
            ):
                raise ResourceLimitError("rule max_artifact_bytes exhausted")
            index = read_table(artifact.index)
            decoded_bytes += index.nbytes
            if decoded_bytes > options.max_artifact_bytes:
                raise ResourceLimitError("decoded index exceeds rule max_artifact_bytes")
            if index.num_rows != table.num_rows or tuple(index.column_names) != tuple(
                c.name for c in artifact.index_columns
            ):
                raise ArtifactIntegrityError("captured index metadata mismatch")
        result[artifact.name] = table
    return result


def _check(
    definition: RuleDefinition,
    check_id: str,
    *,
    kind: Literal["precondition", "rule"],
    context: RuleContext | None,
    registry: RuleRegistry,
    directory: Path,
    revision: int | None = None,
    required: bool | None = None,
    severity: Literal["info", "warning", "error"] | None = None,
    reason: str | None = None,
    applicable: bool = True,
) -> CheckResult:
    implementation = registry.resolve(definition.kind)
    state: CheckState
    if not applicable:
        state, complete = "not_applicable", True
    elif reason or context is None or implementation is None:
        state, complete = "not_evaluable", False
        reason = reason or (
            "missing implementation: " + definition.kind
            if implementation is None
            else "evidence unavailable"
        )
    else:
        state, complete = "satisfied", True
    before_work = context.work if context else 0
    path = directory / (uuid4().hex + ".jsonl")
    with path.open("xb") as sink:
        if context and state == "satisfied" and implementation is not None:
            context.check_id, context.sink = check_id, sink
            context.examples, context.violations, context.examined = [], 0, 0
            try:
                context.checkpoint()
                implementation.evaluate(definition, context)
            except Exception as error:
                reason, complete = report_failure(error, "rule_evaluation_failed"), False
                state = "violated" if context.violations else "not_evaluable"
            else:
                state = "violated" if context.violations else "satisfied"
            finally:
                context.sink = None
        sink.flush()
        os.fsync(sink.fileno())
    findings = _ref(path)
    return CheckResult(
        check_id=check_id,
        revision=revision,
        kind=kind,
        implementation=implementation.identity if implementation else None,
        state=state,
        complete=complete,
        required=required,
        severity=severity,
        reason=reason,
        violation_count=context.violations
        if context and applicable and before_work != context.work
        else 0,
        examined_rows=context.examined
        if context and applicable and before_work != context.work
        else 0,
        examples=tuple(context.examples)
        if context and applicable and before_work != context.work
        else (),
        findings=findings,
    )


def evaluate_rules(
    execution: ExecutionResult,
    *,
    registry: RuleRegistry | None = None,
    options: RuleOptions | None = None,
    work_dir: Path | None = None,
    cancellation: CancellationToken | None = None,
) -> RuleEvaluation:
    """Evaluate only a single completed run's captured inputs/output; persist fresh evidence."""
    execution = ExecutionResult.model_validate(execution)
    contract = execution.plan.contract
    if execution.contract_sha256 != contract_fingerprint(contract):
        raise ValueError("execution contract fingerprint mismatch")
    options = RuleOptions.model_validate(RuleOptions() if options is None else options)
    registry = registry or default_rule_registry()
    cancellation = cancellation or CancellationToken()
    identifier = "rules_" + uuid4().hex
    directory = (
        local_output_directory(Path.cwd() / "equiframe-runs" if work_dir is None else work_dir)
        / identifier
    )
    directory.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    context: RuleContext | None = None
    diagnostic: str | None = None
    try:
        if cancellation.cancelled:
            raise ExecutionCancelled("rule evaluation cancelled before artifact loading")
        tables = _verified_tables(execution, options)
        context = RuleContext(contract, tables, options, cancellation, start)
        context.checkpoint()
    except Exception as error:
        diagnostic = report_failure(error, "rule_inputs_unavailable")
    preconditions = tuple(
        _check(
            item.requirement,
            item.precondition_id,
            kind="precondition",
            context=context,
            registry=registry,
            directory=directory,
            reason=diagnostic,
        )
        for item in contract.preconditions
    )
    precondition_map = {item.check_id: item for item in preconditions}
    rules: list[CheckResult] = []
    for rule in contract.rules:
        dependencies = [precondition_map[name] for name in rule.applicability]
        unavailable = [
            item.check_id
            for item in dependencies
            if item.state == "not_evaluable" or not item.complete
        ]
        false = [
            item.check_id for item in dependencies if item.state in ("violated", "not_applicable")
        ]
        reason = diagnostic
        if false:
            reason = "verified false precondition: " + ", ".join(false)
        elif unavailable:
            reason = "unverified applicability: " + ", ".join(unavailable)
        rules.append(
            _check(
                rule.specification,
                rule.rule_id,
                kind="rule",
                context=context,
                registry=registry,
                directory=directory,
                revision=rule.revision,
                required=rule.required,
                severity=rule.severity,
                reason=reason,
                applicable=not false,
            )
        )
    has_alert = any(item.state == "violated" for item in rules)
    complete = (
        bool(rules)
        and diagnostic is None
        and all(item.complete for item in (*preconditions, *rules))
        and any(item.state in ("satisfied", "violated") for item in rules)
    )
    decision: DecisionState = "alert" if has_alert else "no_alert" if complete else "not_evaluable"
    checked = tuple(item for item in rules if item.state in ("satisfied", "violated"))
    alerts = tuple(item for item in rules if item.state == "violated")
    severity_rank = {"info": 1, "warning": 2, "error": 3}
    highest = max(
        (item.severity for item in alerts if item.severity is not None),
        key=severity_rank.__getitem__,
        default=None,
    )
    coverage = RuleCoverage(
        declared=len(rules),
        checked=len(checked),
        skipped=sum(item.state == "not_applicable" for item in rules),
        unavailable=sum(item.state == "not_evaluable" for item in rules),
        required_declared=sum(item.required is True for item in rules),
        required_checked=sum(item.required is True for item in checked),
        alerts=len(alerts),
        finding_count=sum(item.violation_count for item in rules),
        preconditions_declared=len(preconditions),
        preconditions_verified=sum(item.complete for item in preconditions),
        preconditions_unavailable=sum(not item.complete for item in preconditions),
        highest_alert_severity=highest,
    )
    result = RuleEvaluation(
        evaluation_id=identifier,
        run_id=execution.run_id,
        execution_id=execution.execution_id,
        contract_id=contract.contract_id,
        contract_revision=contract.revision,
        contract_sha256=execution.contract_sha256,
        rule_set_sha256=rule_set_fingerprint(contract, registry, options),
        execution_state=execution.state,
        options=options,
        decision=decision,
        complete=complete,
        preconditions=preconditions,
        rules=tuple(rules),
        coverage=coverage,
        started_at=started_at,
        elapsed_seconds=time.perf_counter() - start,
        work_units=context.work if context else 0,
        diagnostic=diagnostic or ("empty rule set" if not rules else None),
    )
    temporary = directory / "rules.json.part"
    with temporary.open("xb") as output:
        output.write(_json(result.model_dump(mode="json")))
        output.flush()
        os.fsync(output.fileno())
    os.link(temporary, directory / "rules.json")
    temporary.unlink()
    return result


def read_rule_evaluation(path: Path) -> RuleEvaluation:
    """Validate manifest structure; call iter_rule_findings to verify referenced bytes."""
    raw = read_document(local_input_path(path))
    return RuleEvaluation.model_validate_json(raw)


def iter_rule_findings(ref: ArtifactRef) -> Iterator[RuleFinding]:
    """Verify all finding bytes before yielding typed locations."""
    if ref.format != "jsonl":
        raise ValueError("rule findings require JSONL")
    with tempfile.TemporaryDirectory(prefix="equiframe-rule-findings-") as temporary:
        path = Path(temporary) / "findings.jsonl"
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
                yield RuleFinding.model_validate_json(line)
