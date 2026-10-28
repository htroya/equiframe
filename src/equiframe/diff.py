"""A direct-input facade over the existing complete comparison kernel.

Actual DuckDB relations explicitly supplied by the caller are consumed as native
inputs. SQL strings, connections and Polars lazy plans are not accepted. Capture
and inference failures before a valid contract exists raise; once configured,
the kernel owns semantic failure states.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from typing_extensions import TypeAliasType

from equiframe._base import FrozenModel
from equiframe._diff_capture import (
    DiffCaptureOptions,
    _CapturedInput,
    _NativeInput,
    capture_native,
)
from equiframe._document_io import read_document
from equiframe._regular_io import local_input_path
from equiframe.comparison import ComparisonInput, _compare, comparison_fingerprint
from equiframe.comparison_types import ComparisonOptions, ComparisonPolicy, ComparisonResult
from equiframe.contracts import Contract
from equiframe.diff_contracts import DiffContract, infer_diff_contract
from equiframe.errors import ArtifactIntegrityError, CapabilityError, ExecutionCancelled
from equiframe.execution import CancellationToken
from equiframe.execution_types import ExecutionResult, TableArtifact
from equiframe.local import local_path
from equiframe.tables import ArrowInput
from equiframe.types import ArtifactRef, Sha256

if TYPE_CHECKING:
    import duckdb
    import pandas as pd
    import polars as pl
    import pyarrow as pa

    DiffInput = TypeAliasType(
        "DiffInput",
        ComparisonInput | pd.DataFrame | pl.DataFrame | pa.Table | duckdb.DuckDBPyRelation,
    )
else:
    # Introspection must not import optional engines. Capture performs actual
    # class admission; this runtime alias is not an admission validator.
    DiffInput = TypeAliasType("DiffInput", ComparisonInput | object)


class _DiffReceipt(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    comparison_id: str
    spec_sha256: Sha256
    declaration: DiffContract
    capture_options: DiffCaptureOptions


def _input(
    value: DiffInput, options: DiffCaptureOptions, cancellation: CancellationToken | None = None
) -> ComparisonInput | _NativeInput:
    if isinstance(value, (ArrowInput, ArtifactRef, TableArtifact, ExecutionResult, Path)):
        return value
    return _NativeInput(value, options, cancellation)


def diff(
    candidate: DiffInput,
    expected: DiffInput,
    *,
    contract: Contract | DiffContract | None = None,
    keys: Sequence[str] | None = None,
    policy: ComparisonPolicy | None = None,
    reference: Literal["peer", "expected"] | None = None,
    options: ComparisonOptions | None = None,
    capture_options: DiffCaptureOptions | None = None,
    work_dir: Path | None = None,
    cancellation: CancellationToken | None = None,
) -> ComparisonResult:
    """Compare native tables, using the right-hand expected schema by default.

    Passing a real DuckDBPyRelation authorizes consuming its caller-owned native
    plan once per input. Capture is bounded by rows and Arrow batch bytes, with
    cooperative cancellation between batches. SQL strings/connections and
    Polars LazyFrame objects are not executed through this facade.

    With no contract, infer types only from the right-hand captured table; keys
    are always explicit. Read all resulting policies and their origins through
    :func:`read_diff_contract`. Explicit contracts also accept the existing
    materialized comparison inputs. DiffContract forbids overrides: construct a
    new declaration to change its policies. Native row/byte capture bounds are
    separate from cooperative comparison bounds; neither is a hard RSS quota.

    Raises ValueError/Pydantic ValidationError/InvalidExecutionInput for invalid configuration;
    CapabilityError for unsupported or ambiguous reference inference;
    MissingDependencyError, ResourceLimitError or ExecutionCancelled during
    pre-contract capture; and OSError if evidence cannot be published. These
    failures do not guarantee a persisted final report. Configured comparisons
    retain the core's equivalent/different/not_evaluable states and diagnostics.
    """
    capture = DiffCaptureOptions.model_validate(
        DiffCaptureOptions() if capture_options is None else capture_options
    )
    checked_options = ComparisonOptions.model_validate(
        ComparisonOptions() if options is None else options
    )
    if reference not in (None, "peer", "expected"):
        raise ValueError("reference must be peer or expected")
    if contract is not None and keys is not None:
        raise ValueError("keys cannot override an explicit contract")
    right: ComparisonInput | _NativeInput | _CapturedInput
    if isinstance(contract, DiffContract):
        if policy is not None or reference is not None:
            raise ValueError("policy/reference cannot override a DiffContract")
        declaration = DiffContract.model_validate(contract)
        right = _input(expected, capture, cancellation)
    elif contract is not None:
        if reference is None:
            declaration = DiffContract.from_contract(contract, policy=policy)
        else:
            declaration = DiffContract.from_contract(contract, policy=policy, reference=reference)
        right = _input(expected, capture, cancellation)
    else:
        if isinstance(expected, (ArtifactRef, TableArtifact, ExecutionResult, Path)):
            raise CapabilityError(
                "schema inference requires an eager table or an explicit DuckDB relation; "
                "supply an explicit contract for materialized artifact/execution inputs"
            )
        if cancellation is not None and cancellation.cancelled:
            raise ExecutionCancelled("cancelled before reference capture and inference")
        observed = expected.table if isinstance(expected, ArrowInput) else expected
        loaded = capture_native(observed, capture, cancellation=cancellation)
        if reference is None:
            declaration = infer_diff_contract(loaded.table.schema, keys=keys, policy=policy)
        else:
            declaration = infer_diff_contract(
                loaded.table.schema, keys=keys, policy=policy, reference=reference
            )
        right = _CapturedInput(loaded)
    result = _compare(
        _input(candidate, capture, cancellation),
        right,
        contract=declaration.spec.contract,
        policy=declaration.spec.policy,
        reference=declaration.reference,
        options=checked_options,
        work_dir=work_dir,
        cancellation=cancellation,
    )
    receipt = _DiffReceipt(
        comparison_id=result.comparison_id,
        spec_sha256=result.spec_sha256,
        declaration=declaration,
        capture_options=capture,
    )
    directory = local_path(result.differences).parent
    temporary = directory / "diff-contract.json.part"
    try:
        with temporary.open("xb") as target:
            target.write(receipt.model_dump_json(indent=2).encode("utf-8"))
            target.flush()
            os.fsync(target.fileno())
        os.link(temporary, directory / "diff-contract.json")
    finally:
        temporary.unlink(missing_ok=True)
    return result


def read_diff_contract(result: ComparisonResult) -> DiffContract:
    """Read a diff's companion declaration, bound to its result and policies.

    This supplementary provenance is not a signature or producer attestation.
    Comparisons made directly with compare have no such companion. Reading
    does not execute the source or query, or verify all comparison evidence.
    """
    result = ComparisonResult.model_validate(result)
    path = local_path(result.differences).parent / "diff-contract.json"
    raw = read_document(local_input_path(path))
    receipt = _DiffReceipt.model_validate_json(raw)
    declaration = receipt.declaration
    if (
        receipt.comparison_id != result.comparison_id
        or receipt.spec_sha256 != result.spec_sha256
        or comparison_fingerprint(declaration.spec) != result.spec_sha256
        or declaration.spec != result.spec
        or declaration.reference != result.reference
    ):
        raise ArtifactIntegrityError("diff declaration does not match the comparison")
    return declaration
