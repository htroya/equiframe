"""Inspect existing results without rerunning their ETL or requiring the benchmark."""

from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import datetime
from datetime import timezone as _timezone
from itertools import combinations
from pathlib import Path
from uuid import uuid4

from typing_extensions import TypeAliasType

from equiframe._comparison_io import snapshot
from equiframe._error_reporting import report_failure
from equiframe._physical import verify_table_metadata
from equiframe._regular_io import local_output_directory
from equiframe._report_format_v1 import verification_html_v1, verification_summary_v1
from equiframe.comparison import compare, iter_differences, read_comparison
from equiframe.comparison_types import ComparisonOptions, ComparisonPolicy, ComparisonResult
from equiframe.contracts import Contract, TableSpec
from equiframe.errors import ArtifactIntegrityError
from equiframe.evidence import inventory, load_json, parse_json, publish_json, verify_files
from equiframe.execution_types import ExecutionResult, TableArtifact
from equiframe.local import local_path
from equiframe.pipeline_types import PipelineResult
from equiframe.rule_types import RuleEvaluation
from equiframe.rules import evaluate_rules, iter_rule_findings, read_rule_evaluation
from equiframe.serialization import contract_fingerprint
from equiframe.tables import read_table
from equiframe.types import ArtifactRef
from equiframe.verify_types import (
    ExpectedProvenance,
    IndependentReviewEvidence,
    VerificationBinding,
    VerificationCheck,
    VerificationCoverage,
    VerificationResult,
)

UTC = _timezone.utc

VerificationInput = TypeAliasType(
    "VerificationInput", ArtifactRef | ExecutionResult | PipelineResult
)


def _check(
    state: str, reason: str, output: str | None = None, comparison: ComparisonResult | None = None
) -> VerificationCheck:
    return VerificationCheck.model_validate(
        dict(
            state=state,
            reason=reason,
            output=output,
            comparison_id=comparison.comparison_id if comparison is not None else None,
        )
    )


def _comparison_check(c: ComparisonResult, output: str | None = None) -> VerificationCheck:
    state = {"equivalent": "passed", "different": "failed", "not_evaluable": "not_evaluable"}
    return _check(state[c.state], f"Complete output comparison: {c.state}", output, c)


def _aggregate(checks: tuple[VerificationCheck, ...], reason: str) -> VerificationCheck:
    state = "passed"
    if any(c.state == "failed" for c in checks):
        state = "failed"
    elif any(c.state == "not_evaluable" for c in checks):
        state = "not_evaluable"
    elif any(c.state == "pending_review" for c in checks):
        state = "pending_review"
    return _check(state, reason)


def _review(
    binding: VerificationBinding,
    provenance: ExpectedProvenance | None,
    reviews: tuple[IndependentReviewEvidence, ...],
    expected_checks: tuple[VerificationCheck, ...],
    requested: bool,
) -> VerificationCheck:
    if not requested:
        return _check("not_requested", "Scientific O was not requested")
    if not binding.expected_sha256:
        return _check("not_evaluable", "Scientific O requires an expected artifact")
    if provenance is None or not provenance.independently_constructed:
        return _check("not_evaluable", "Independent expected construction is not established")
    if not binding.snapshots or binding.plan_sha256 is None:
        return _check("not_evaluable", "Scientific O requires snapshot and plan identities")
    by_output = {r.output: r for r in reviews}
    if len(by_output) != len(reviews):
        raise ValueError("duplicate review evidence for an output")
    states: list[VerificationCheck] = []
    prohibited = set(provenance.authors + provenance.implementation_authors)
    for check in expected_checks:
        review = by_output.get(check.output or "")
        if review is None:
            states.append(_check("pending_review", "Two independent blind reviews required"))
            continue
        rb = review.binding
        if (
            rb.contract_sha256 != binding.contract_sha256
            or rb.snapshots != binding.snapshots
            or rb.plan_sha256 != binding.plan_sha256
            or rb.expected_sha256 != binding.expected_sha256
            or dict(rb.outputs).get(review.output) != dict(binding.outputs).get(review.output)
        ):
            raise ValueError("review identity differs from verified content")
        if prohibited.intersection((*review.reviewers, review.arbitrator)):
            states.append(_check("not_evaluable", "Reviewers overlap declared authors"))
        elif check.state == "not_evaluable":
            states.append(_check("not_evaluable", "Expected comparison is incomplete"))
        elif len(review.reviews) != 2:
            states.append(_check("pending_review", "Two primary reviews are required"))
        elif review.reviews[0].label != review.reviews[1].label and review.resolution is None:
            states.append(_check("pending_review", "Independent arbitration is required"))
        else:
            selected = review.resolution.label if review.resolution else review.reviews[0].label
            observed = "normal" if check.state == "passed" else "divergent"
            states.append(
                _check(
                    "not_evaluable"
                    if selected == "not_evaluable"
                    else "passed"
                    if selected == observed
                    else "failed",
                    "Declared independent human decisions checked against the expected comparison",
                )
            )
    return _aggregate(
        tuple(states),
        "Scientific O checks declared provenance and reviews; identities are not authenticated",
    )


def _validate_dimensions(result: VerificationResult) -> None:
    """Reconstruct decisions from bound component records, including pending O."""
    if result.integrity.state not in ("passed", "failed", "not_evaluable"):
        raise ValueError("verification integrity cannot be skipped or pending review")
    by_id = {c.comparison_id: c for c in result.comparisons}
    if len(by_id) != len(result.comparisons):
        raise ValueError("verification comparison identities must be unique")
    refs = dict(result.outputs)
    executions = dict(result.executions)
    if len(executions) != len(result.executions) or not set(executions) <= {
        c.output for c in result.technical_outcomes
    }:
        raise ValueError("captured execution output identities must be unique and requested")
    for name, captured_execution in result.executions:
        if captured_execution.plan.contract != result.contract or (
            captured_execution.output is not None
            and (name not in refs or captured_execution.output.data.sha256 != refs[name].sha256)
        ):
            raise ValueError("captured execution contradicts verified contract or output")
    snapshot_identity = sorted((name, ref.sha256) for name, ref in result.input_artifacts)
    input_identity_mismatch = any(
        sorted((table.name, table.data.sha256) for table in execution.inputs) != snapshot_identity
        for execution in executions.values()
    )
    if input_identity_mismatch and (result.integrity.state != "failed" or result.coverage.complete):
        raise ValueError(
            "execution inputs differ from bound snapshots; failed integrity and "
            "incomplete coverage must remain recorded"
        )
    if result.coverage.complete and result.integrity.state != "passed":
        raise ValueError("complete verification requires passed integrity")
    for component in (*result.comparisons, *result.input_comparisons):
        if (
            component.spec.policy != result.comparison_policy
            or component.options != result.comparison_options
        ):
            raise ValueError("comparison policy or options contradict verification request")

    def bound(c: ComparisonResult, left: str, right: str | None) -> None:
        if c.spec.contract != result.contract:
            raise ValueError("comparison contract contradicts verification request")
        for source, name in ((c.left, left), (c.right, right)):
            ref = refs[name] if name is not None else result.expected_artifact
            if ref is None or (source is not None and source.data.sha256 != ref.sha256):
                raise ValueError("comparison content identities differ from requested pair")
            if source is not None:
                execution = executions.get(name or "")
                if source.execution != execution:
                    raise ValueError("comparison execution contradicts captured execution")

    names = tuple(c.output for c in result.expected)
    if (
        len(names) != result.coverage.outputs_requested
        or len(set(names)) != len(names)
        or None in names
        or tuple(c.output for c in result.rules) != names
        or tuple(c.output for c in result.technical_outcomes) != names
        or not set(refs) <= set(names)
    ):
        raise ValueError("verification dimensions must cover each requested output once")
    for check in result.expected:
        if check.comparison_id:
            c = by_id.get(check.comparison_id)
            if (
                c is None
                or c.reference != "expected"
                or check != _comparison_check(c, check.output)
            ):
                raise ValueError("expected dimension contradicts its comparison")
            ref = refs.get(check.output or "")
            if (
                ref is None
                or result.expected_artifact is None
                or (c.left is not None and c.left.data.sha256 != ref.sha256)
                or (c.right is not None and c.right.data.sha256 != result.expected_artifact.sha256)
            ):
                raise ValueError("expected comparison content identities differ")
            bound(c, check.output or "", None)
        else:
            if check.state not in ("not_requested", "not_evaluable"):
                raise ValueError("expected outcome requires a bound comparison")
            if (
                result.expected_artifact is not None or result.expected_required
            ) and check.state != "not_evaluable":
                raise ValueError("requested expected comparison cannot be skipped")
    inspected = len(result.outputs)
    self_comparisons = result.comparisons[:inspected]
    if len(self_comparisons) != inspected:
        raise ValueError("each inspected output requires its complete schema comparison")
    for (name, _), c in zip(result.outputs, self_comparisons, strict=True):
        if c.reference != "peer":
            raise ValueError("output self-comparison reference differs")
        bound(c, name, name)
    if len(result.input_comparisons) != len(result.input_artifacts):
        raise ValueError("each bound input requires its constraint comparison")
    for (name, ref), c in zip(result.input_artifacts, result.input_comparisons, strict=True):
        declared = next((t for t in result.contract.inputs if t.name == name), None)
        if (
            declared is None
            or c.spec.contract != _input_contract(result.contract, declared)
            or c.reference != "peer"
            or any(s is not None and s.data.sha256 != ref.sha256 for s in (c.left, c.right))
        ):
            raise ValueError("input constraint comparison identity differs")
    input_checks = tuple(_comparison_check(c) for c in result.input_comparisons)
    output_checks = tuple(
        _comparison_check(c, name)
        for (name, _), c in zip(result.outputs, self_comparisons, strict=True)
    )
    expected_inputs = (
        _aggregate(
            (*input_checks, *output_checks), "Complete output schema, keys and value constraints"
        )
        if inspected == result.coverage.outputs_requested
        else _check("not_evaluable", "Output capture incomplete")
    )
    if result.inputs != expected_inputs:
        raise ValueError("input dimension contradicts complete constraint comparisons")
    expected_ids = {c.comparison_id for c in result.expected if c.comparison_id}
    peer = tuple(c for c in result.comparisons[inspected:] if c.comparison_id not in expected_ids)
    peer_requested = result.coverage.outputs_requested > 1
    if (
        inspected == result.coverage.outputs_requested
        and len(peer) != inspected * (inspected - 1) // 2
    ):
        raise ValueError("verification must inspect every requested pair independently")
    if len(peer) != inspected * (inspected - 1) // 2:
        raise ValueError("captured outputs require each inspected pair exactly once")
    for ((left, _), (right, _)), c in zip(combinations(result.outputs, 2), peer, strict=True):
        if c.reference != "peer":
            raise ValueError("peer comparison reference differs")
        bound(c, left, right)
    expected_agreement = (
        _aggregate(
            tuple(_comparison_check(c) for c in peer), "All requested pairs compared independently"
        )
        if peer_requested and inspected == result.coverage.outputs_requested
        else _check("not_evaluable" if peer_requested else "not_requested", "Peer comparison scope")
    )
    if result.agreement != expected_agreement:
        raise ValueError("agreement dimension contradicts peer comparisons")
    expected_technical = _aggregate(
        result.technical_outcomes, "Technical outcomes retained separately"
    )
    if not any(c.state != "not_requested" for c in result.technical_outcomes):
        expected_technical = _check(
            "not_requested", "Artifact inspection does not assert ETL execution"
        )
    if result.technical != expected_technical:
        raise ValueError("technical dimension contradicts captured outcomes")
    for check in result.technical_outcomes:
        execution = executions.get(check.output or "")
        if execution is not None:
            observed = _check(
                "passed" if execution.state == "completed" else "not_evaluable",
                "Captured execution state: " + execution.state,
                check.output,
            )
            if check != observed:
                raise ValueError("technical outcome contradicts captured execution state")
        elif check.state not in ("not_requested", "not_evaluable"):
            raise ValueError("technical success requires captured execution evidence")
    evaluations = {r.execution_id: r for r in result.rule_evaluations}
    for check in result.rules:
        execution = executions.get(check.output or "")
        evaluation = evaluations.get(execution.execution_id) if execution is not None else None
        if evaluation is not None:
            state = (
                "failed"
                if evaluation.decision == "alert"
                else "passed"
                if evaluation.complete
                else "not_evaluable"
            )
            expected_rule = _check(state, "Selected rules: " + evaluation.decision, check.output)
            if evaluation.contract_sha256 != result.binding.contract_sha256:
                raise ValueError("selected rules belong to another contract")
        else:
            expected_rule = _check(
                "not_evaluable" if result.rules_required else "not_requested",
                "Rules require captured execution inputs"
                if result.rules_required
                else "No operational rules requested for this artifact",
                check.output,
            )
            if execution is not None and result.contract.rules:
                raise ValueError("captured execution requires its selected rule evaluations")
        if check != expected_rule:
            raise ValueError("rule dimension contradicts selected rule evaluations")
    expected_review = _review(
        result.binding,
        result.provenance,
        result.review_evidence,
        result.expected,
        result.review_requested,
    )
    if result.independent_review != expected_review:
        raise ValueError("independent-review dimension contradicts declared evidence")
    completed = sum(c.complete for c in (*result.comparisons, *result.input_comparisons))
    requested_outputs = result.coverage.outputs_requested
    expected_requested = (
        result.expected_artifact is not None
        or result.expected_required
        or any(check.state != "not_requested" for check in result.expected)
    )
    requested_comparisons = (
        requested_outputs
        + requested_outputs * (requested_outputs - 1) // 2
        + len(result.input_artifacts)
        + (requested_outputs if expected_requested else 0)
    )
    if result.coverage.comparisons_requested != requested_comparisons:
        raise ValueError("coverage contradicts requested comparison dimensions")
    if (
        result.coverage.comparisons_completed != completed
        or result.coverage.outputs_inspected != inspected
    ):
        raise ValueError("coverage contradicts inspected component records")
    complete = (
        inspected == requested_outputs
        and result.integrity.state == "passed"
        and len(result.comparisons) + len(result.input_comparisons) == requested_comparisons
        and all(c.complete for c in (*result.comparisons, *result.input_comparisons))
    )
    if result.coverage.complete != complete:
        raise ValueError("coverage completeness contradicts retained verification evidence")
    if result.coverage.input_execution_evidence_available != (
        len(executions) == result.coverage.outputs_requested
    ):
        raise ValueError("input execution coverage contradicts captured executions")


def _input_contract(contract: Contract, declared: TableSpec) -> Contract:
    output_name = "verify_input"
    while output_name in {t.name for t in contract.inputs}:
        output_name += "_input"
    return Contract.model_validate(
        {
            **contract.model_dump(),
            "output": TableSpec(name=output_name, schema_spec=declared.schema_spec),
            "rules": (),
            "preconditions": (),
        }
    )


def verify(
    outputs: Mapping[str, VerificationInput],
    *,
    contract: Contract,
    expected: ArtifactRef | ExecutionResult | None = None,
    provenance: ExpectedProvenance | None = None,
    reviews: tuple[IndependentReviewEvidence, ...] = (),
    request_review: bool = False,
    require_expected: bool = False,
    require_rules: bool = False,
    snapshots: Mapping[str, ArtifactRef] | None = None,
    plan_sha256: str | None = None,
    policy: ComparisonPolicy | None = None,
    options: ComparisonOptions | None = None,
    work_dir: Path | None = None,
) -> VerificationResult:
    """Capture and inspect complete outputs, preserving separate scientific O.

    External artifact checks do not assert that an external ETL completed. Rules
    require captured execution inputs. No engine, callback or plugin is executed.
    """
    contract = Contract.model_validate(contract)
    if not outputs:
        raise ValueError("verify requires at least one named result")
    opts = ComparisonOptions.model_validate(ComparisonOptions() if options is None else options)
    policy = ComparisonPolicy.model_validate(ComparisonPolicy() if policy is None else policy)
    identifier = "verify_" + uuid4().hex
    directory = (
        local_output_directory(Path.cwd() / "equiframe-runs" if work_dir is None else work_dir)
        / identifier
    )
    directory.mkdir(parents=True, exist_ok=False)
    started = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    captured: dict[str, ArtifactRef] = {}
    executions: dict[str, ExecutionResult] = {}
    errors: list[VerificationCheck] = []
    technical_checks: list[VerificationCheck] = []

    def capture(ref: ArtifactRef) -> ArtifactRef:
        value = snapshot(ref, directory, opts, lambda: None)
        read_table(value)
        return value

    def table(t: TableArtifact) -> TableArtifact:
        copied = TableArtifact.model_validate(
            {
                **t.model_dump(),
                "data": capture(t.data),
                "index": capture(t.index) if t.index else None,
            }
        )
        verify_table_metadata(copied)
        return copied

    for name, value in outputs.items():
        _check("passed", "Output name validated", name)
        if isinstance(value, PipelineResult):
            value = PipelineResult.model_validate(value)
            if value.execution is None:
                technical_checks.append(_check("not_evaluable", "Pipeline has no execution", name))
                continue
            value = value.execution
        if isinstance(value, ExecutionResult):
            value = ExecutionResult.model_validate(value)
            if value.plan.contract != contract:
                raise ValueError("execution and verification contracts differ")
            technical_checks.append(
                _check(
                    "passed" if value.state == "completed" else "not_evaluable",
                    "Captured execution state: " + value.state,
                    name,
                )
            )
            try:
                output = table(value.output) if value.output else None
                inputs = tuple(table(t) for t in value.inputs)
                execution = ExecutionResult.model_validate(
                    {**value.model_dump(), "inputs": inputs, "output": output}
                )
                executions[name] = execution
                if output:
                    captured[name] = output.data
            except Exception as error:
                technical_checks[-1] = _check(
                    "not_evaluable", "Execution evidence could not be captured", name
                )
                errors.append(
                    _check("failed", report_failure(error, "execution_capture_failed"), name)
                )
        else:
            value = ArtifactRef.model_validate(value)
            technical_checks.append(
                _check(
                    "not_requested",
                    "External execution status was not supplied; artifact inspection only",
                    name,
                )
            )
            try:
                captured[name] = capture(value)
            except Exception as error:
                errors.append(
                    _check("failed", report_failure(error, "artifact_capture_failed"), name)
                )
    fixed_expected = None
    expected_engine = None
    if isinstance(expected, ExecutionResult):
        expected = ExecutionResult.model_validate(expected)
        expected_engine = expected.plan.engine
        if provenance is not None:
            provenance = ExpectedProvenance.model_validate(
                {
                    **provenance.model_dump(),
                    "derived_from_engines": tuple(
                        dict.fromkeys((*provenance.derived_from_engines, expected_engine))
                    ),
                }
            )
        if expected.state != "completed" or expected.output is None:
            errors.append(_check("not_evaluable", "Expected execution did not complete"))
            expected = None
            require_expected = True
        else:
            expected = expected.output.data
    if expected is not None:
        try:
            fixed_expected = capture(expected)
        except Exception as error:
            errors.append(_check("failed", report_failure(error, "expected_capture_failed")))
    fixed_snapshots = {name: capture(ref) for name, ref in (snapshots or {}).items()}
    if not fixed_snapshots and executions:
        first = next(iter(executions.values()))
        fixed_snapshots = {t.name: t.data for t in first.inputs}
        identities = tuple((t.name, t.data.sha256) for t in first.inputs)
        if any(
            tuple((t.name, t.data.sha256) for t in e.inputs) != identities
            for e in executions.values()
        ):
            errors.append(_check("failed", "Implementations received different input snapshots"))
    if fixed_snapshots and executions:
        identity = sorted((name, ref.sha256) for name, ref in fixed_snapshots.items())
        if any(
            sorted((t.name, t.data.sha256) for t in e.inputs) != identity
            for e in executions.values()
        ):
            errors.append(_check("failed", "Execution inputs differ from the bound snapshots"))
    binding = VerificationBinding.model_validate(
        dict(
            contract_sha256=contract_fingerprint(contract),
            snapshots=tuple((name, ref.sha256) for name, ref in fixed_snapshots.items()),
            plan_sha256=plan_sha256,
            outputs=tuple((name, ref.sha256) for name, ref in captured.items()),
            expected_sha256=fixed_expected.sha256 if fixed_expected else None,
        )
    )
    comparisons: list[ComparisonResult] = []
    input_comparisons: list[ComparisonResult] = []
    self_checks: list[VerificationCheck] = []
    for name, ref in fixed_snapshots.items():
        declared = next((t for t in contract.inputs if t.name == name), None)
        if declared is None:
            raise ValueError("snapshot is not a declared contract input")
        input_contract = _input_contract(contract, declared)
        c = compare(
            ref, ref, contract=input_contract, policy=policy, options=opts, work_dir=directory
        )
        input_comparisons.append(c)
        self_checks.append(_comparison_check(c))
    for name, ref in captured.items():
        value = executions.get(name, ref)
        c = compare(
            value, value, contract=contract, policy=policy, options=opts, work_dir=directory
        )
        comparisons.append(c)
        self_checks.append(_comparison_check(c, name))
    peer_checks: list[VerificationCheck] = []
    for (a, left), (b, right) in combinations(captured.items(), 2):
        c = compare(
            executions.get(a, left),
            executions.get(b, right),
            contract=contract,
            policy=policy,
            options=opts,
            work_dir=directory,
        )
        comparisons.append(c)
        peer_checks.append(_comparison_check(c))
    expected_checks: list[VerificationCheck] = []
    for name in outputs:
        if fixed_expected is not None and name in captured:
            c = compare(
                executions.get(name, captured[name]),
                fixed_expected,
                contract=contract,
                policy=policy,
                options=opts,
                reference="expected",
                work_dir=directory,
            )
            comparisons.append(c)
            expected_checks.append(_comparison_check(c, name))
        else:
            requested = expected is not None or require_expected
            expected_checks.append(
                _check(
                    "not_evaluable" if requested else "not_requested",
                    "Expected comparison unavailable" if requested else "No expected requested",
                    name,
                )
            )
    rules: list[VerificationCheck] = []
    evaluations: list[RuleEvaluation] = []
    for name in outputs:
        if name in executions and (contract.rules or require_rules):
            evaluation = evaluate_rules(executions[name], work_dir=directory)
            evaluations.append(evaluation)
            rules.append(
                _check(
                    "failed"
                    if evaluation.decision == "alert"
                    else "passed"
                    if evaluation.complete
                    else "not_evaluable",
                    "Selected rules: " + evaluation.decision,
                    name,
                )
            )
        else:
            rules.append(
                _check(
                    "not_evaluable" if require_rules else "not_requested",
                    "Rules require captured execution inputs"
                    if require_rules
                    else "No operational rules requested for this artifact",
                    name,
                )
            )
    requested_count = len(outputs) + len(outputs) * (len(outputs) - 1) // 2 + len(fixed_snapshots)
    if expected is not None or require_expected:
        requested_count += len(outputs)
    complete = (
        len(captured) == len(outputs)
        and not errors
        and len(comparisons) + len(input_comparisons) == requested_count
        and all(c.complete for c in (*comparisons, *input_comparisons))
    )
    result = VerificationResult(
        verification_id=identifier,
        contract=contract,
        binding=binding,
        outputs=tuple(captured.items()),
        expected_artifact=fixed_expected,
        expected_source_engine=expected_engine,
        comparison_policy=policy,
        comparison_options=opts,
        input_artifacts=tuple(fixed_snapshots.items()),
        expected_required=require_expected,
        rules_required=require_rules,
        review_requested=request_review,
        technical_outcomes=tuple(technical_checks),
        provenance=provenance,
        review_evidence=reviews,
        inputs=_aggregate(tuple(self_checks), "Complete output schema, keys and value constraints")
        if len(captured) == len(outputs)
        else _check("not_evaluable", "Output capture incomplete"),
        technical=_aggregate(tuple(technical_checks), "Technical outcomes retained separately")
        if any(c.state != "not_requested" for c in technical_checks)
        else _check("not_requested", "Artifact inspection does not assert ETL execution"),
        integrity=_aggregate(tuple(errors), "Captured bytes verified against SHA-256 and size"),
        agreement=_aggregate(tuple(peer_checks), "All requested pairs compared independently")
        if len(outputs) > 1 and len(captured) == len(outputs)
        else _check(
            "not_requested" if len(outputs) == 1 else "not_evaluable", "Peer comparison scope"
        ),
        expected=tuple(expected_checks),
        rules=tuple(rules),
        coverage=VerificationCoverage(
            outputs_requested=len(outputs),
            outputs_inspected=len(captured),
            comparisons_requested=requested_count,
            comparisons_completed=sum(c.complete for c in (*comparisons, *input_comparisons)),
            input_execution_evidence_available=len(executions) == len(outputs),
            complete=complete,
        ),
        independent_review=_review(
            binding, provenance, reviews, tuple(expected_checks), request_review
        ),
        comparisons=tuple(comparisons),
        input_comparisons=tuple(input_comparisons),
        executions=tuple(executions.items()),
        rule_evaluations=tuple(evaluations),
        started_at=started,
        elapsed_seconds=time.perf_counter() - start,
    )
    publish_json(verification_summary(result), directory / "report.json")
    (directory / "report.html").write_text(render_verification_report(result), encoding="utf-8")
    result = VerificationResult.model_validate(
        {**result.model_dump(), "evidence": inventory(directory)}
    )
    publish_json(result, directory / "verification.json")
    return result


def verification_summary(result: VerificationResult) -> dict[str, object]:
    return verification_summary_v1(result)


def render_verification_report(result: VerificationResult) -> str:
    return verification_html_v1(result)


def read_verification(path: Path) -> VerificationResult:
    path = path / "verification.json" if path.is_dir() else path
    result = load_json(VerificationResult, path)
    directory = path.parent.resolve()
    verify_files(directory, result.evidence)
    actual = {
        p.relative_to(directory).as_posix()
        for p in directory.rglob("*")
        if p.is_file() and p != path.resolve()
    }
    if actual != {f.path for f in result.evidence}:
        raise ArtifactIntegrityError("verification inventory is not closed")
    listed = {f.path: f for f in result.evidence}
    refs = [ref for _, ref in result.outputs]
    refs.extend(ref for _, ref in result.input_artifacts)
    if result.expected_artifact:
        refs.append(result.expected_artifact)
    for _, e in result.executions:
        for t in (*e.inputs, *((e.output,) if e.output else ())):
            refs.extend((t.data, *((t.index,) if t.index else ())))
    for r in result.rule_evaluations:
        refs.extend(c.findings for c in (*r.preconditions, *r.rules) if c.findings)
    for c in (*result.comparisons, *result.input_comparisons):
        refs.append(c.differences)
        refs.extend(s.data for s in (c.left, c.right) if s is not None)
    for ref in refs:
        target = local_path(ref).resolve()
        if not target.is_relative_to(directory):
            raise ArtifactIntegrityError("verification artifact escapes inventory")
        item = listed.get(target.relative_to(directory).as_posix())
        if item is None or (item.sha256, item.size_bytes) != (ref.sha256, ref.size_bytes):
            raise ArtifactIntegrityError("verification artifact contradicts inventory")
    for _, e in result.executions:
        for t in (*e.inputs, *((e.output,) if e.output else ())):
            verify_table_metadata(t)
    for r in result.rule_evaluations:
        if read_rule_evaluation(directory / r.evaluation_id / "rules.json") != r:
            raise ArtifactIntegrityError(
                "selected rule evaluation contradicts verification manifest"
            )
        for check in (*r.preconditions, *r.rules):
            if check.findings:
                count = 0
                for finding in iter_rule_findings(check.findings):
                    if count < len(check.examples) and finding != check.examples[count]:
                        raise ArtifactIntegrityError("rule examples contradict complete findings")
                    count += 1
                if count != check.violation_count:
                    raise ArtifactIntegrityError("rule findings contradict recorded counts")
    for c in (*result.comparisons, *result.input_comparisons):
        if read_comparison(directory / c.comparison_id / "comparison.json") != c:
            raise ArtifactIntegrityError("verification comparison contradicts manifest")
        count = violations = 0
        for difference in iter_differences(c.differences):
            if count < len(c.examples) and difference != c.examples[count]:
                raise ArtifactIntegrityError("comparison examples contradict complete differences")
            count += 1
            violations += int(difference.category in ("schema", "contract"))
        if count != c.counts.difference_records or violations != c.counts.contract_violations:
            raise ArtifactIntegrityError("difference counts contradict complete evidence")
        if len(c.examples) != min(count, c.options.max_examples):
            raise ArtifactIntegrityError("comparison examples contradict the configured budget")
    if parse_json((directory / "report.json").read_bytes()) != verification_summary_v1(result):
        raise ArtifactIntegrityError("verification report contradicts manifest")
    if (directory / "report.html").read_bytes() != verification_html_v1(result).encode("utf-8"):
        raise ArtifactIntegrityError("verification HTML contradicts manifest")
    return result


def verify_migration(
    path: Path,
    *,
    work_dir: Path | None = None,
    provenance: ExpectedProvenance | None = None,
    reviews: tuple[IndependentReviewEvidence, ...] = (),
    request_review: bool = False,
) -> VerificationResult:
    from equiframe.migration.io import read_migration
    from equiframe.migration.validation import ir_fingerprint

    result = read_migration(path)
    outputs = {
        name: p
        for name, p in (("source", result.source), ("target", result.target))
        if p is not None
    }
    if len(outputs) != 2:
        raise ValueError("migration has no two captured pipelines to verify")
    return verify(
        outputs,
        contract=result.spec.contract,
        expected=result.expected,
        require_expected=result.expected_requested,
        require_rules=result.spec.require_rules,
        provenance=provenance,
        reviews=reviews,
        request_review=request_review,
        snapshots={t.name: t.data for t in result.inputs},
        plan_sha256=ir_fingerprint(result.spec.ir),
        policy=result.spec.comparison_policy,
        options=result.spec.comparison_options,
        work_dir=work_dir,
    )
