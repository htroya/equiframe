"""Optional, independent base-R comparison after the existing R/M decisions.

Here ``R`` in ``HybridDecision.r`` still means rules. The language-R reviewer
does not train, score, calibrate or consume Isolation Forest features. It reads
lossless observations and an admitted exact contract, never Python's verdict.
"""

from __future__ import annotations

import hashlib
import math
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterable, Iterator
from importlib.resources import as_file, files
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe._base import FrozenModel, NonNegativeInt, PositiveInt, Text, _ExplicitOutcome
from equiframe._diff_capture import DiffCaptureOptions, capture_native
from equiframe.comparison import comparison_fingerprint
from equiframe.comparison_types import ComparisonResult, ComparisonSpec
from equiframe.contracts import ColumnSpec, Contract, SignificantOrder
from equiframe.decision import combine_decisions
from equiframe.detector_types import ComponentDecision, ComponentDetectionResult, HybridDecision
from equiframe.diff_contracts import DiffContract
from equiframe.errors import (
    CapabilityError,
    EquiFrameError,
    ExecutionCancelled,
    ExecutionTimeout,
    ResourceLimitError,
)
from equiframe.execution import CancellationToken
from equiframe.execution_types import ExecutionResult, TableArtifact
from equiframe.profile_types import ProfileResult, profile_digest
from equiframe.rule_types import RuleEvaluation
from equiframe.tables import ArrowInput, LoadedTable, read_table
from equiframe.types import ArtifactRef, ComparisonState, Sha256

if TYPE_CHECKING:
    import pyarrow as pa


class RReviewOptions(FrozenModel):
    """Explicit local executable and cooperative capture/process budgets.

    R must already be installed. This API never installs R or any R package.
    Byte limits cover captures and the generated transport, not hard process RSS.
    """

    rscript: Text = "Rscript"
    timeout_seconds: Annotated[float, Field(gt=0)] = 30.0
    max_rows: PositiveInt = 100_000
    max_bytes: PositiveInt = 64 * 1024 * 1024
    max_columns: PositiveInt = 256


class RReviewBinding(FrozenModel):
    """Verified local artifacts whose full observations were sent to R."""

    comparison_id: Text
    left_artifact_sha256: Sha256
    right_artifact_sha256: Sha256


class RExecutionBinding(FrozenModel):
    """Actual execution/profile/IF result associated by the bound finalizer."""

    execution_id: Text
    execution_sha256: Sha256
    profile_id: Text
    profile_sha256: Sha256
    detection_sha256: Sha256
    output_sha256: Sha256


class RReviewResult(_ExplicitOutcome, FrozenModel):
    """Independent exact comparison, with unsupported/unavailable states explicit."""

    _truth_value_guidance = "inspect .state and .complete; availability is not equivalence"
    schema_version: Literal["1.0"] = "1.0"
    reviewer: Literal["equiframe-base-r-exact-1.0"] = "equiframe-base-r-exact-1.0"
    state: ComparisonState
    complete: bool
    reason: Text | None = None
    spec_sha256: Sha256
    reviewer_sha256: Sha256
    left_transport_sha256: Sha256 | None = None
    right_transport_sha256: Sha256 | None = None
    binding: RReviewBinding | None = None
    columns: tuple[str, ...] = ()
    left_rows: NonNegativeInt = 0
    right_rows: NonNegativeInt = 0
    matched_rows: NonNegativeInt = 0
    unmatched_rows: NonNegativeInt = 0
    contract_violations: NonNegativeInt = 0
    diagnostics: tuple[Text, ...] = ()
    r_version: Text | None = None
    returncode: int | None = None
    elapsed_seconds: Annotated[float, Field(ge=0)]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.complete != (self.reason is None):
            raise ValueError("incomplete R review requires a reason")
        if (self.state == "not_evaluable") != (not self.complete):
            raise ValueError("R review requires either a complete verdict or not_evaluable")
        if self.matched_rows > min(self.left_rows, self.right_rows):
            raise ValueError("matched rows exceed inputs")
        if self.complete:
            if not self.left_transport_sha256 or not self.right_transport_sha256:
                raise ValueError("completed R review requires both observed transports")
            if not self.r_version or self.returncode != 0:
                raise ValueError("completed R review requires a successful real R process")
            expected = (
                "different" if self.unmatched_rows or self.contract_violations else "equivalent"
            )
            if self.state != expected:
                raise ValueError("R state must preserve all reported differences")
            if self.unmatched_rows != self.left_rows + self.right_rows - 2 * self.matched_rows:
                raise ValueError("R row accounting is inconsistent")
        return self


def _disagreement(comparison: ComparisonResult | None, review: RReviewResult) -> bool:
    return (
        comparison is not None
        and comparison.complete
        and comparison.state != "not_evaluable"
        and review.complete
        and comparison.state != review.state
    )


def _final(
    hybrid: HybridDecision,
    review: RReviewResult,
    comparison: ComparisonResult | None = None,
) -> ComponentDecision:
    spec_mismatch = comparison is not None and comparison.spec_sha256 != review.spec_sha256
    binding = review.binding
    comparison_ready = comparison is None or (
        comparison.complete
        and comparison.state != "not_evaluable"
        and not spec_mismatch
        and binding is not None
        and comparison.left is not None
        and comparison.right is not None
        and binding.comparison_id == comparison.comparison_id
        and binding.left_artifact_sha256 == comparison.left.data.sha256
        and binding.right_artifact_sha256 == comparison.right.data.sha256
    )
    complete = hybrid.result.complete and review.complete and comparison_ready
    alert = (
        hybrid.result.decision == "alert"
        or review.state == "different"
        or (comparison is not None and comparison.state == "different")
    )
    return ComponentDecision(
        decision="alert" if alert else "no_alert" if complete else "not_evaluable",
        complete=complete,
        reason=(
            None
            if complete
            else "comparison_spec_mismatch"
            if spec_mismatch
            else "incomplete_hybrid_comparison_or_r_review"
        ),
    )


class ReviewedDecision(_ExplicitOutcome, FrozenModel):
    """H plus an independent exact comparison; alerts are never overwritten.

    ``accepted`` means all requested operational checks completed without an
    alert. It is not a scientific correctness label or approval of an IF model.
    """

    _truth_value_guidance = "inspect .accepted, .result and .r_review explicitly"
    schema_version: Literal["1.0"] = "1.0"
    hybrid: HybridDecision
    r_review: RReviewResult
    comparison: ComparisonResult | None = None
    comparison_disagreement: bool = False
    execution_binding: RExecutionBinding | None = None
    result: ComponentDecision
    accepted: bool

    @model_validator(mode="after")
    def consistent(self) -> Self:
        expected = _final(self.hybrid, self.r_review, self.comparison)
        if self.result != expected:
            raise ValueError("reviewed decision must preserve H, comparison and R review")
        if self.comparison_disagreement != _disagreement(self.comparison, self.r_review):
            raise ValueError("comparison disagreement must preserve both complete verdicts")
        if self.accepted != (expected.complete and expected.decision == "no_alert"):
            raise ValueError("acceptance requires complete checks without alerts")
        return self


def _spec(contract: Contract | DiffContract | ComparisonSpec) -> ComparisonSpec:
    if isinstance(contract, DiffContract):
        return DiffContract.model_validate(contract).spec
    if isinstance(contract, ComparisonSpec):
        return ComparisonSpec.model_validate(contract)
    return ComparisonSpec(contract=Contract.model_validate(contract))


def _admit(spec: ComparisonSpec) -> None:
    # Do not silently replace the original semantics with an easier R contract.
    if spec.policy.physical_types != "exact":
        raise CapabilityError("r_review_requires_exact_physical_types")
    for column in spec.contract.output.schema_spec.columns:
        if column.null_policy.representations != ("null",):
            raise CapabilityError("r_review_does_not_support_null_aliases")
        if column.allowed_values:
            raise CapabilityError("r_review_does_not_support_allowed_values")
        numeric = column.numeric_policy
        if numeric is not None and (numeric.comparison != "exact" or numeric.rounding is not None):
            raise CapabilityError("r_review_does_not_support_tolerance_or_rounding")
        if column.nan_policy is not None and column.nan_policy.handling == "as_null":
            raise CapabilityError("r_review_does_not_support_nan_as_null")
        temporal = column.temporal_policy
        if temporal is not None:
            if temporal.lower is not None or temporal.upper is not None:
                raise CapabilityError("r_review_does_not_support_temporal_bounds")
            if temporal.kind == "timestamp" and not (
                (temporal.naive == "preserve" and temporal.timezone is None)
                or (
                    temporal.comparison == "instant"
                    and temporal.naive == "reject"
                    and temporal.timezone is not None
                )
            ):
                raise CapabilityError("r_review_does_not_support_local_timezone_resolution")


def _hex(value: str) -> str:
    return value.encode("utf-8").hex() or "-"


def _signature(dtype: pa.DataType) -> str:
    import pyarrow as pa

    if pa.types.is_boolean(dtype):
        return "boolean"
    if pa.types.is_integer(dtype):
        return f"integer:{dtype.bit_width}:{int(pa.types.is_signed_integer(dtype))}"
    if pa.types.is_floating(dtype):
        return f"float:{dtype.bit_width}"
    if (
        pa.types.is_string(dtype)
        or pa.types.is_large_string(dtype)
        or pa.types.is_string_view(dtype)
    ):
        return "string"
    if pa.types.is_decimal(dtype):
        return f"decimal:{dtype.precision}:{dtype.scale}"
    if pa.types.is_date32(dtype):
        return "date"
    if pa.types.is_timestamp(dtype):
        return f"timestamp:{dtype.unit}:{_hex(dtype.tz or '')}"
    # date64 requires exact day divisibility; never truncate it to date32 here.
    raise CapabilityError("r_review_unsupported_physical_type")


def _expected(column: ColumnSpec) -> str:
    dtype = column.logical_type
    if dtype.kind == "integer":
        return f"integer:{dtype.bits}:{int(dtype.signed)}"
    if dtype.kind == "float":
        return f"float:{dtype.bits}"
    if dtype.kind == "decimal":
        return f"decimal:{dtype.precision}:{dtype.scale}"
    if dtype.kind == "timestamp":
        return f"timestamp:{dtype.unit}:{_hex(dtype.timezone or '')}"
    return dtype.kind


def _token(scalar: pa.Scalar) -> str:
    import pyarrow as pa

    if not scalar.is_valid:
        return "N"
    dtype = scalar.type
    if pa.types.is_boolean(dtype):
        return "B1" if scalar.as_py() else "B0"
    if pa.types.is_integer(dtype):
        return "I" + str(scalar.as_py())
    if pa.types.is_floating(dtype):
        value = float(scalar.as_py())
        if math.isnan(value):
            return "Q"
        if math.isinf(value):
            return "P" if value > 0 else "M"
        return "F" + repr(value)
    if pa.types.is_decimal(dtype):
        return "D" + str(scalar.as_py())
    if pa.types.is_date32(dtype):
        return "A" + str(scalar.value)
    if pa.types.is_timestamp(dtype):
        return "T" + str(scalar.value)
    return "S" + _hex(scalar.as_py())


def _capture(value: object, options: RReviewOptions, spec: ComparisonSpec) -> LoadedTable:
    if isinstance(value, ExecutionResult):
        if value.output is None:
            raise CapabilityError("r_review_execution_output_unavailable")
        value = value.output
    if isinstance(value, TableArtifact):
        if value.index is not None and spec.policy.index != "ignore":
            raise CapabilityError("r_review_requires_explicit_index_policy")
        value = value.data
    if isinstance(value, ArtifactRef):
        if value.size_bytes > options.max_bytes:
            raise ResourceLimitError("r_review_artifact_max_bytes")
        value = read_table(value)
    loaded = capture_native(
        value.table if isinstance(value, ArrowInput) else value,
        DiffCaptureOptions(max_rows=options.max_rows, max_bytes=options.max_bytes),
    )
    if loaded.meaningful_index and spec.policy.index != "ignore":
        raise CapabilityError("r_review_requires_explicit_index_policy")
    if loaded.table.num_columns > options.max_columns:
        raise ResourceLimitError("r_review_max_columns")
    return loaded


def _table_lines(loaded: LoadedTable) -> Iterator[str]:
    yield "EFR_TABLE_1"
    yield f"{loaded.table.num_rows}\t{loaded.table.num_columns}"
    for field in loaded.table.schema:
        yield _hex(field.name) + "\t" + _signature(field.type)
    for batch in loaded.table.to_batches(max_chunksize=1024):
        for row in range(batch.num_rows):
            yield "\t".join(_token(column[row]) for column in batch.columns)


def review_with_r(
    left: object,
    right: object,
    *,
    contract: Contract | DiffContract | ComparisonSpec,
    comparison: ComparisonResult | None = None,
    options: RReviewOptions | None = None,
    cancellation: CancellationToken | None = None,
) -> RReviewResult:
    """Compare captured Arrow/Pandas/Polars/DuckDB observations in base R.

    An explicitly supplied DuckDB relation authorizes consumption of its native
    plan under row/byte budgets and the caller's session settings. SQL strings,
    connections, callbacks and other lazy plans are not inferred as inputs.
    Unsupported policies, missing R, process
    failure, timeout and cancellation return ``not_evaluable``. Bad API options
    and invalid contracts raise validation errors. Temporary inputs/results are
    removed on every exit; only compact observations are returned to the caller.
    """
    checked = RReviewOptions.model_validate(RReviewOptions() if options is None else options)
    spec = _spec(contract)
    script_resource = files("equiframe").joinpath("_r_review.R")
    script_hash = hashlib.sha256(script_resource.read_bytes()).hexdigest()
    start = time.monotonic()
    details: dict[str, object] = {
        "spec_sha256": comparison_fingerprint(spec),
        "reviewer_sha256": script_hash,
    }

    def check() -> None:
        if cancellation is not None and cancellation.cancelled:
            raise ExecutionCancelled("r_review_cancelled")
        if time.monotonic() - start >= checked.timeout_seconds:
            raise ExecutionTimeout("r_review_timeout")

    try:
        check()
        _admit(spec)
        executable = shutil.which(checked.rscript)
        if executable is None:
            raise CapabilityError("rscript_unavailable")
        schema = spec.contract.output.schema_spec
        with tempfile.TemporaryDirectory(prefix="equiframe-r-review-") as temporary:
            directory = Path(temporary)
            used = 0

            def write(path: Path, lines: Iterable[str]) -> str:
                nonlocal used
                digest = hashlib.sha256()
                with path.open("xb") as sink:
                    for line in lines:
                        check()
                        block = (line + "\n").encode("ascii")
                        used += len(block)
                        if used > checked.max_bytes:
                            raise ResourceLimitError("r_review_transport_max_bytes")
                        sink.write(block)
                        digest.update(block)
                return digest.hexdigest()

            left_loaded = _capture(left, checked, spec)
            check()
            right_loaded = _capture(right, checked, spec)
            check()
            details.update(
                columns=tuple(column.name for column in schema.columns),
                left_rows=left_loaded.table.num_rows,
                right_rows=right_loaded.table.num_rows,
            )
            details["left_transport_sha256"] = write(
                directory / "left.txt", _table_lines(left_loaded)
            )
            details["right_transport_sha256"] = write(
                directory / "right.txt", _table_lines(right_loaded)
            )
            if comparison is not None:
                comparison = ComparisonResult.model_validate(comparison)
                if comparison.spec_sha256 != details["spec_sha256"]:
                    raise CapabilityError("r_review_comparison_spec_mismatch")
                if comparison.left is None or comparison.right is None:
                    raise CapabilityError("r_review_comparison_sources_unavailable")
                for side, source in (("left", comparison.left), ("right", comparison.right)):
                    if (
                        source.table is not None
                        and source.table.index is not None
                        and spec.policy.index != "ignore"
                    ):
                        raise CapabilityError("r_review_requires_explicit_index_policy")
                    expected = _capture(source.data, checked, spec)
                    digest = hashlib.sha256()
                    size = 0
                    for line in _table_lines(expected):
                        check()
                        block = (line + "\n").encode("ascii")
                        size += len(block)
                        if size > checked.max_bytes:
                            raise ResourceLimitError("r_review_transport_max_bytes")
                        digest.update(block)
                    if digest.hexdigest() != details[side + "_transport_sha256"]:
                        raise CapabilityError("r_review_comparison_data_mismatch")
                details["binding"] = RReviewBinding(
                    comparison_id=comparison.comparison_id,
                    left_artifact_sha256=comparison.left.data.sha256,
                    right_artifact_sha256=comparison.right.data.sha256,
                )
            names = tuple(column.name for column in schema.columns)
            order = schema.order
            config = [
                "EFR_CONTRACT_1",
                f"{len(names)}\t{spec.policy.column_order}\t{schema.multiplicity}",
                "sequence" if isinstance(order, SignificantOrder) else "bag",
            ]
            for column in schema.columns:
                config.append(
                    "\t".join(
                        (
                            _hex(column.name),
                            _expected(column),
                            str(int(column.nullable)),
                            column.nan_policy.handling if column.nan_policy is not None else "none",
                        )
                    )
                )
            config.append(str(len(schema.keys)))
            for key in schema.keys:
                indices = tuple(names.index(name) + 1 for name in key.columns)
                if key.scope.kind == "columns":
                    indices += tuple(names.index(name) + 1 for name in key.scope.columns)
                config.append(
                    "\t".join(
                        (
                            str(int(key.unique)),
                            key.incomplete,
                            ",".join(str(index) for index in indices),
                        )
                    )
                )
            sorts = order.by if isinstance(order, SignificantOrder) else ()
            ties = order.ties if isinstance(order, SignificantOrder) else "preserve"
            config.append(f"{len(sorts)}\t{ties}")
            for sort in sorts:
                config.append(f"{names.index(sort.column) + 1}\t{sort.direction}\t{sort.nulls}")
            write(directory / "contract.txt", config)
            with (
                as_file(script_resource) as script,
                (directory / "process.log").open("wb") as log,
            ):
                # The transport is ASCII and its numeric tokens use a dot.
                # Keep locale resolution deterministic in the R child only,
                # including Windows hosts with a Unix-only inherited locale.
                environment = dict(os.environ)
                for name in tuple(environment):
                    if name.startswith("LC_"):
                        environment[name] = "C"
                environment.update(LC_ALL="C", LANG="C", LANGUAGE="C")
                process = subprocess.Popen(
                    [
                        executable,
                        "--vanilla",
                        "--default-packages=NULL",
                        str(script),
                        str(directory),
                    ],
                    cwd=directory,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    shell=False,
                    env=environment,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                try:
                    while True:
                        check()
                        try:
                            process.wait(timeout=0.1)
                            break
                        except subprocess.TimeoutExpired:
                            continue
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            details["returncode"] = process.returncode
            if process.returncode != 0:
                raise CapabilityError("r_review_process_failed")
            check()
            result_path = directory / "result.txt"
            if not result_path.is_file() or result_path.stat().st_size > 8192:
                raise CapabilityError("r_review_invalid_process_result")
            lines = result_path.read_text(encoding="ascii").splitlines()
            if len(lines) != 8 or lines[0] != "EFR_RESULT_1":
                raise CapabilityError("r_review_invalid_process_result")
            matched, unmatched, violations = (int(value) for value in lines[2:5])
            if lines[1] not in ("equivalent", "different"):
                raise CapabilityError("r_review_invalid_process_result")
            if (
                int(lines[5]) != left_loaded.table.num_rows
                or int(lines[6]) != right_loaded.table.num_rows
            ):
                raise CapabilityError("r_review_result_row_mismatch")
            return RReviewResult.model_validate(
                {
                    **details,
                    "state": lines[1],
                    "complete": True,
                    "matched_rows": matched,
                    "unmatched_rows": unmatched,
                    "contract_violations": violations,
                    "diagnostics": ("independent_contract_violation",) if violations else (),
                    "r_version": bytes.fromhex(lines[7]).decode("utf-8"),
                    "elapsed_seconds": time.monotonic() - start,
                }
            )
    except (EquiFrameError, OSError, ValueError, TypeError) as error:
        # Error messages from third-party captures may contain user values.
        local_errors = (CapabilityError, ResourceLimitError, ExecutionCancelled, ExecutionTimeout)
        reason = (
            str(error)
            if type(error) in local_errors and str(error).startswith(("r_review_", "rscript_"))
            else type(error).__name__
        )
        return RReviewResult.model_validate(
            {
                **details,
                "state": "not_evaluable",
                "complete": False,
                "reason": reason,
                "elapsed_seconds": time.monotonic() - start,
            }
        )


def finalize_with_r(
    rules: ComponentDecision | RuleEvaluation,
    model: ComponentDecision,
    *,
    left: object,
    right: object,
    contract: Contract | DiffContract | ComparisonSpec,
    comparison: ComparisonResult | None = None,
    options: RReviewOptions | None = None,
    cancellation: CancellationToken | None = None,
) -> ReviewedDecision:
    """Combine actual rule/IF decisions, then request the independent R review.

    Pass the Isolation Forest decision for the corresponding execution/profile,
    not a MAD decision or a made-up default. Inputs and contract remain explicit:
    IF/rules receive no peer output through this finalization function. When an
    existing Python comparison is supplied, its differences and incomplete state
    also remain binding. It is combined only after R finishes, never sent to R.
    """
    hybrid = combine_decisions(rules, model)
    checked_comparison = None if comparison is None else ComparisonResult.model_validate(comparison)
    review = review_with_r(
        left,
        right,
        contract=contract,
        comparison=checked_comparison,
        options=options,
        cancellation=cancellation,
    )
    result = _final(hybrid, review, checked_comparison)
    return ReviewedDecision(
        hybrid=hybrid,
        r_review=review,
        comparison=checked_comparison,
        comparison_disagreement=_disagreement(checked_comparison, review),
        result=result,
        accepted=result.complete and result.decision == "no_alert",
    )


def finalize_execution_with_r(
    execution: ExecutionResult,
    rules: RuleEvaluation,
    profile: ProfileResult,
    detection: ComponentDetectionResult,
    *,
    comparison: ComparisonResult,
    options: RReviewOptions | None = None,
    cancellation: CancellationToken | None = None,
) -> ReviewedDecision:
    """Finalize one real execution using its rules, profile, frozen IF and comparison.

    Reject mismatched identifiers/hashes before starting R. Detection must come
    from ``detect_component(bundle, (profile.vector,), method='isolation_forest')``.
    The comparator artifacts are verified and read afresh; its verdict, rules
    and model scores are never included in the R input.
    """
    execution = ExecutionResult.model_validate(execution)
    rules = RuleEvaluation.model_validate(rules)
    profile = ProfileResult.model_validate(profile)
    detection = ComponentDetectionResult.model_validate(detection)
    comparison = ComparisonResult.model_validate(comparison)
    execution_hash = profile_digest(execution.model_dump(mode="json"))
    if execution.output is None or execution.state != "completed":
        raise ValueError("R finalization requires a completed execution output")
    if (rules.execution_id, rules.run_id, rules.contract_sha256) != (
        execution.execution_id,
        execution.run_id,
        execution.contract_sha256,
    ):
        raise ValueError("rules do not belong to the execution")
    metadata = profile.metadata
    artifacts = tuple(
        ref
        for table in (*execution.inputs, execution.output)
        for ref in (table.data, *((table.index,) if table.index is not None else ()))
    )
    if (
        metadata.execution_id,
        metadata.run_id,
        metadata.contract_sha256,
        metadata.execution_sha256,
        metadata.artifacts,
    ) != (
        execution.execution_id,
        execution.run_id,
        execution.contract_sha256,
        execution_hash,
        artifacts,
    ):
        raise ValueError("profile does not belong to the execution and artifacts")
    if (
        detection.method != "isolation_forest"
        or detection.rows != 1
        or detection.profiles_sha256 != profile_digest([profile.vector.model_dump(mode="json")])
    ):
        raise ValueError("IF detection does not belong to this single profile")
    if comparison.contract_sha256 != execution.contract_sha256 or not any(
        source is not None
        and source.execution == execution
        and source.data.sha256 == execution.output.data.sha256
        for source in (comparison.left, comparison.right)
    ):
        raise ValueError("comparison does not include this execution output")
    if comparison.left is None or comparison.right is None:
        raise ValueError("comparison must retain both captured artifacts")
    reviewed = finalize_with_r(
        rules,
        detection.decisions[0].result,
        left=comparison.left.data,
        right=comparison.right.data,
        contract=comparison.spec,
        comparison=comparison,
        options=options,
        cancellation=cancellation,
    )
    return ReviewedDecision(
        **reviewed.model_dump(exclude={"execution_binding"}),
        execution_binding=RExecutionBinding(
            execution_id=execution.execution_id,
            execution_sha256=execution_hash,
            profile_id=metadata.profile_id,
            profile_sha256=profile_digest(profile.model_dump(mode="json")),
            detection_sha256=profile_digest(detection.model_dump(mode="json")),
            output_sha256=execution.output.data.sha256,
        ),
    )
