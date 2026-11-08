"""Operational cost protocol on actual captures; resource test probes are synthetic."""

import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import equiframe as ef
import pytest
from equiframe.detector_types import IsolationNode, IsolationTree
from equiframe.local import local_path
from equiframe.profile_types import profile_digest
from pydantic import ValidationError

import equiframe_benchmark.costs as cost_module
from equiframe_benchmark.costs import (
    CostComparisonResult,
    CostProtocol,
    CostSpec,
    ProfileMCostResult,
    ResourceMeasurement,
    ResourceSample,
    measure_costs,
    read_costs,
)
from equiframe_benchmark.fixtures import COMPARISON_POLICY, cases, expected_table, registry
from equiframe_benchmark.pilot import write_table


def _captured_reference(path, data=b"captured bytes"):
    return ef.ArtifactRef(
        schema_version="1.0",
        uri=path.absolute().as_uri(),
        sha256=hashlib.sha256(data).hexdigest(),
        format="arrow",
        media_type="application/vnd.apache.arrow.file",
        size_bytes=len(data),
    )


@pytest.mark.parametrize(
    "kind", ["regular", "mismatch", "directory", "symlink", "broken", "parent"]
)
def test_cost_artifact_verification_requires_regular_files(tmp_path, kind):
    target = tmp_path / "capture.arrow"
    data = b"captured bytes"
    if kind == "directory":
        target.mkdir()
    else:
        target.write_bytes(data if kind != "mismatch" else b"changed bytes")
    selected = target
    if kind in ("symlink", "broken", "parent"):
        link = tmp_path / "link"
        destination = tmp_path / "absent" if kind == "broken" else target
        if kind == "parent":
            destination = tmp_path / "real"
            destination.mkdir()
            (destination / target.name).write_bytes(data)
        try:
            link.symlink_to(destination, target_is_directory=kind == "parent")
        except OSError as error:
            pytest.skip(f"Native symlink creation is unavailable: {type(error).__name__}")
        selected = link / target.name if kind == "parent" else link
    check = cost_module._verify((_captured_reference(selected),))[0]
    assert check.state == {"regular": "verified", "mismatch": "mismatch"}.get(kind, "unavailable")
    if kind in ("regular", "mismatch"):
        observed = selected.read_bytes()
        assert check.observed_sha256 == hashlib.sha256(observed).hexdigest()
        assert check.observed_size_bytes == len(observed)
    else:
        assert check.observed_sha256 is None
        assert check.observed_size_bytes is None


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO support is unavailable")
def test_cost_artifact_fifo_is_rejected_before_blocking_open(tmp_path):
    fifo = tmp_path / "capture.arrow"
    os.mkfifo(fifo)
    # The timeout is a regression guard: the old unprotected open blocks forever
    # without a writer. The child imports the same package locations as this test.
    module_roots = sorted(
        {str(Path(ef.__file__).parent.parent), str(Path(cost_module.__file__).parent.parent)}
    )
    serialized = _captured_reference(fifo).model_dump_json()
    source = (
        f"import sys; sys.path[:0] = {module_roots!r}; "
        "import equiframe as ef; from equiframe_benchmark.costs import _verify; "
        f"reference = ef.ArtifactRef.model_validate_json({serialized!r}); "
        "print(_verify((reference,))[0].state)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", source],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.stdout.strip() == "unavailable"


class ControlledProbe:
    """Declared software fixture, never reported as empirical resource evidence."""

    def __init__(self):
        self.count = 0

    def sample(self):
        self.count += 1
        return ResourceSample(cpu_seconds=self.count / 1000, rss_bytes=1000 * self.count)


def assert_controlled_resource_sequence(resources, probe):
    assert probe.count >= 2
    assert len(resources.samples) == probe.count
    assert [(point.sample.cpu_seconds, point.sample.rss_bytes) for point in resources.samples] == [
        (number / 1000, 1000 * number) for number in range(1, probe.count + 1)
    ]
    assert resources.rss_baseline_bytes == 1000
    assert resources.sampled_rss_peak_bytes == 1000 * probe.count
    assert resources.cpu_seconds == pytest.approx((probe.count - 1) / 1000)


def frozen_bundle(spec):
    # Independent declarative tree with a split; no ML fitting occurs in a timed callback.
    vectors = tuple(
        ef.ProfileVector(
            spec=spec,
            spec_sha256=ef.profile_spec_fingerprint(spec),
            observations=(
                ef.FeatureObservation(
                    name="missing_amount",
                    state="available",
                    numerator=n,
                    denominator=4,
                    value=n / 4,
                ),
            ),
        )
        for n in (0, 1, 2, 4)
    )
    preprocessor = ef.fit_preprocessor(
        ef.NormalTrainingProfiles(
            purpose="normal_training", selection_manifest_sha256="a" * 64, profiles=vectors
        ),
        spec=spec,
    )
    fit = ef.DetectorFit(
        preprocessor=preprocessor,
        config=ef.IsolationForestConfig(random_state=7, n_estimators=1, max_samples=4),
        support=ef.DetectorSupport(
            min_training_rows=2,
            min_calibration_rows=2,
            rationale="Synthetic engineering fixture; not a scientific corpus",
        ),
        versions=ef.DetectorVersions(
            python="3.12", sklearn="declarative-test-fixture", numpy="declarative-test-fixture"
        ),
        training_matrix_sha256=profile_digest(
            ef.transform_profiles(preprocessor, vectors).model_dump(mode="json")
        ),
        m=ef.DetectorModel(
            method="isolation_forest",
            state="fitted",
            effective_samples=4,
            trees=(
                IsolationTree(
                    nodes=(
                        IsolationNode(samples=4, left=1, right=2, feature=0, threshold=0.5),
                        IsolationNode(samples=3),
                        IsolationNode(samples=1),
                    )
                ),
            ),
        ),
        b=ef.DetectorModel(
            method="mad",
            state="fitted",
            medians=(0.375, 0.0, 0.0),
            deviations=(0.25, 0.0, 0.0),
        ),
    )
    return ef.calibrate_detectors(
        fit,
        ef.NormalCalibrationProfiles(
            purpose="normal_calibration", selection_manifest_sha256="b" * 64, profiles=vectors
        ),
        alpha="0.5",
    )


def environment(tmp_path, *, engine="duckdb", reference_execution=False):
    case = cases()[0]
    execution = ef.execute(
        ef.ExecutionPlan(contract=case.contract, engine=engine, transformation_id="nulls_types"),
        source=ef.LocalDataSource({name: ef.ArrowInput(t) for name, t in case.inputs.items()}),
        registry=registry(),
        work_dir=tmp_path / "captured",
    )
    assert execution.state == "completed"
    profile = ef.ProfileSpec(
        family="nulls_types",
        features=(
            ef.ProfileFeature(
                name="missing_amount", metric="tasa_nulos", table="result", columns=("amount",)
            ),
        ),
    )
    bundle = frozen_bundle(profile)
    spec = CostSpec(
        case_id="synthetic.cost.identity",
        execution=execution,
        reference=execution
        if reference_execution
        else write_table(expected_table(case), tmp_path / "expected.arrow"),
        profile=profile,
        detector_bundle_sha256=profile_digest(bundle.model_dump(mode="json")),
        comparison_policy=COMPARISON_POLICY,
        protocol=CostProtocol(
            seed=7,
            sample_interval_seconds=1.0,
            cache_policy="warm OS cache; no flush",
            threads=1,
            memory_budget_bytes=None,
            concurrent_loads="test runner only",
            controls_rationale="Synthetic protocol conformance, no empirical cost claim",
        ),
    )
    calls = Counter()

    def profile_m(directory, token):
        calls["profile_m"] += 1
        measured = ef.profile_execution(
            execution,
            spec=profile,
            options=spec.profile_options,
            work_dir=directory,
            cancellation=token,
        )
        detected = ef.detect_component(bundle, (measured.vector,), method="isolation_forest")
        return ProfileMCostResult(profile=measured, detection=detected)

    def comparison(directory, token):
        calls["comparison"] += 1
        return ef.compare(
            execution,
            spec.reference,
            contract=case.contract,
            policy=COMPARISON_POLICY,
            reference=spec.comparison_reference,
            options=spec.comparison_options,
            work_dir=directory,
            cancellation=token,
        )

    return spec, profile_m, comparison, calls


@pytest.mark.parametrize("engine", ["pandas", "polars", "duckdb"])
def test_same_materialized_native_capture_six_calls_per_method_and_restore(tmp_path, engine):
    spec, m, comparison, calls = environment(tmp_path, engine=engine)
    probes = []

    def factory():
        probe = ControlledProbe()
        probes.append(probe)
        return probe

    result = measure_costs(
        spec,
        profile_m=m,
        comparison=comparison,
        work_dir=tmp_path,
        probe_factory=factory,
    )
    assert result.complete
    assert calls == {"profile_m": 6, "comparison": 6}
    assert len(result.warmups) == 2 and len(result.observations) == 10
    pairs = [result.observations[i : i + 2] for i in range(0, 10, 2)]
    assert [r.method for r in result.warmups] == [r.method for r in pairs[0]]
    assert [r.method for r in pairs[1]] == [r.method for r in reversed(pairs[0])]
    assert [r.method for r in pairs[2]] == [r.method for r in pairs[0]]
    assert all(r.repetition == 0 and r.phase == "warmup" for r in result.warmups)
    assert len(probes) == 12
    for record, probe in zip((*result.warmups, *result.observations), probes, strict=True):
        assert_controlled_resource_sequence(record.resources, probe)
        assert record.resources.wall_seconds > 0
        assert all(
            c.state == "verified" for c in (*record.artifacts_before, *record.artifacts_after)
        )
        if record.profile_m:
            assert record.profile_m.detection.method == "isolation_forest"
            assert record.profile_m.profile.metadata.execution_id == spec.execution.execution_id
        else:
            assert record.comparison.state == "equivalent"
    assert read_costs(tmp_path / result.cost_id) == result


def test_controlled_probe_preserves_periodic_samples():
    probe = ControlledProbe()
    monitor = cost_module._Monitor(lambda: probe, 0.01)
    started = time.perf_counter()
    monitor.start()
    try:
        deadline = started + 5
        while probe.count < 3 and time.perf_counter() < deadline:
            time.sleep(0.001)
    finally:
        measurement = monitor.finish(time.perf_counter() - started)
    assert probe.count >= 4
    assert monitor.thread is not None and not monitor.thread.is_alive()
    assert_controlled_resource_sequence(measurement, probe)
    assert measurement.wall_seconds > 0


@pytest.mark.parametrize("failure", ["factory", "sample"])
def test_monitor_failure_never_skips_callbacks_or_fabricates_cpu_rss(tmp_path, failure):
    spec, m, comparison, calls = environment(tmp_path)

    class FailedProbe:
        def sample(self):
            raise OSError("synthetic probe failure")

    def factory():
        if failure == "factory":
            raise OSError("synthetic factory failure")
        return FailedProbe()

    result = measure_costs(
        spec, profile_m=m, comparison=comparison, work_dir=tmp_path, probe_factory=factory
    )
    assert not result.complete and calls == {"profile_m": 6, "comparison": 6}
    for record in (*result.warmups, *result.observations):
        assert record.state == "completed" and record.resources.state == "partial"
        assert record.resources.wall_seconds > 0
        assert record.resources.cpu_seconds is None
        assert record.resources.rss_baseline_bytes is None
        assert record.resources.sampled_rss_peak_bytes is None
        assert record.resources.issues
        assert record.profile_m is not None or record.comparison is not None
    assert read_costs(tmp_path / result.cost_id) == result


def test_sampling_lag_is_declared_with_observed_timestamps(tmp_path):
    spec, m, comparison, calls = environment(tmp_path)
    spec = spec.model_copy(
        update={"protocol": spec.protocol.model_copy(update={"sample_interval_seconds": 0.001})}
    )

    class LaggedProbe(ControlledProbe):
        def sample(self):
            time.sleep(0.005)
            return super().sample()

    result = measure_costs(
        spec, profile_m=m, comparison=comparison, work_dir=tmp_path, probe_factory=LaggedProbe
    )
    assert calls == {"profile_m": 6, "comparison": 6}
    assert not result.complete
    assert all(r.resources.state == "partial" for r in (*result.warmups, *result.observations))
    assert all(
        any(i.code == "sampling_lagged" for i in r.resources.issues)
        for r in (*result.warmups, *result.observations)
    )
    assert read_costs(tmp_path / result.cost_id) == result


def test_failure_preserves_other_method_and_actual_wall_measurement(tmp_path):
    spec, _, comparison, calls = environment(tmp_path)

    def failed(directory, token):
        calls["profile_m"] += 1
        raise RuntimeError("synthetic callback failure")

    result = measure_costs(
        spec,
        profile_m=failed,
        comparison=comparison,
        work_dir=tmp_path,
        probe_factory=ControlledProbe,
    )
    assert not result.complete and calls == {"profile_m": 6, "comparison": 6}
    for record in (*result.warmups, *result.observations):
        assert record.resources.wall_seconds > 0
        if record.method == "profile_m":
            assert record.state == "failed" and record.profile_m is None
            assert record.issues[0].exception_type == "RuntimeError"
        else:
            assert record.state == "completed" and record.comparison.state == "equivalent"
    assert read_costs(tmp_path / result.cost_id) == result


def test_pre_cancelled_operations_are_persisted_without_invented_zero(tmp_path):
    spec, m, comparison, calls = environment(tmp_path)
    token = ef.CancellationToken()
    token.cancel()
    result = measure_costs(
        spec,
        profile_m=m,
        comparison=comparison,
        cancellation=token,
        work_dir=tmp_path,
        probe_factory=ControlledProbe,
    )
    assert not result.complete and not calls
    for record in (*result.warmups, *result.observations):
        assert record.state == "cancelled" and record.resources.state == "not_available"
        assert record.resources.wall_seconds is None and record.resources.cpu_seconds is None
        assert record.resources.sampled_rss_peak_bytes is None
    assert read_costs(tmp_path / result.cost_id) == result


def test_changed_original_capture_is_failure_and_prevents_following_operations(tmp_path):
    spec, m, comparison, calls = environment(tmp_path)

    def changed(directory, token):
        returned = comparison(directory, token)
        local_path(spec.execution.output.data).write_bytes(b"altered original capture")
        return returned

    result = measure_costs(
        spec, profile_m=m, comparison=changed, work_dir=tmp_path, probe_factory=ControlledProbe
    )
    assert calls == {"comparison": 1}
    assert not result.complete and all(
        r.state == "failed" for r in (*result.warmups, *result.observations)
    )
    assert any(v.state == "mismatch" for v in result.artifacts_after)
    assert result.warmups[0].comparison.state == "equivalent"
    assert read_costs(tmp_path / result.cost_id) == result


@pytest.mark.parametrize("alteration", ["corrupt", "delete", "capture", "schedule"])
def test_cost_reader_rejects_missing_corrupt_rebound_evidence_and_schedule(tmp_path, alteration):
    spec, m, comparison, _ = environment(tmp_path)
    result = measure_costs(
        spec, profile_m=m, comparison=comparison, work_dir=tmp_path, probe_factory=ControlledProbe
    )
    directory = tmp_path / result.cost_id
    if alteration == "corrupt":
        (directory / "spec.json").write_bytes(b"corrupt cost spec")
    elif alteration == "delete":
        (directory / result.evidence[0].path).unlink()
    elif alteration == "capture":
        local_path(spec.reference).write_bytes(b"original expected capture altered")
    else:
        raw = json.loads((directory / "costs.json").read_text(encoding="utf-8"))
        raw["observations"].pop()
        (directory / "costs.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises((ef.ArtifactIntegrityError, ValidationError)):
        read_costs(directory)


def test_wrong_frozen_detector_result_is_retained_as_failed_operation(tmp_path):
    spec, m, comparison, calls = environment(tmp_path)

    def rebound(directory, token):
        returned = m(directory, token)
        return returned.model_copy(
            update={"detection": returned.detection.model_copy(update={"bundle_sha256": "c" * 64})}
        )

    result = measure_costs(
        spec,
        profile_m=rebound,
        comparison=comparison,
        work_dir=tmp_path,
        probe_factory=ControlledProbe,
    )
    assert not result.complete and calls == {"profile_m": 6, "comparison": 6}
    assert all(
        r.state == "failed" and r.profile_m is not None
        for r in (*result.warmups, *result.observations)
        if r.method == "profile_m"
    )
    assert read_costs(tmp_path / result.cost_id) == result


def test_original_expected_execution_metadata_survives_cost_measurement(tmp_path):
    spec, m, comparison, _ = environment(tmp_path, reference_execution=True)
    result = measure_costs(
        spec, profile_m=m, comparison=comparison, work_dir=tmp_path, probe_factory=ControlledProbe
    )
    assert result.complete
    assert all(
        r.comparison.right.execution == spec.reference
        for r in (*result.warmups, *result.observations)
        if r.comparison is not None
    )
    assert read_costs(tmp_path / result.cost_id) == result


def test_expected_execution_with_other_inputs_same_outputs_remains_not_evaluable(tmp_path):
    import pyarrow as pa

    spec, m, _, calls = environment(tmp_path)
    case = cases()[0]
    registered = ef.TransformationRegistry()
    registered.register(
        ef.DuckDBTransformation(
            "nulls_types", 'SELECT * FROM "items" LIMIT 4', "synthetic.other-inputs"
        )
    )
    expected = ef.execute(
        spec.execution.plan,
        source=ef.LocalDataSource(
            {
                "items": ef.ArrowInput(
                    pa.concat_tables([case.inputs["items"], case.inputs["items"].slice(0, 1)])
                )
            }
        ),
        registry=registered,
        work_dir=tmp_path / "other-expected",
    )
    assert expected.state == "completed"
    # Arrow buffers/chunking may differ; the independently compared table values
    # and types are the same, despite a genuinely different captured input.
    assert (
        ef.compare(
            spec.execution.output,
            expected.output,
            contract=spec.execution.plan.contract,
            policy=spec.comparison_policy,
            work_dir=tmp_path / "expected-output-check",
        ).state
        == "equivalent"
    )
    spec = spec.model_copy(update={"reference": expected})

    def comparison(directory, token):
        calls["comparison"] += 1
        return ef.compare(
            spec.execution,
            expected,
            contract=spec.execution.plan.contract,
            policy=spec.comparison_policy,
            reference="expected",
            work_dir=directory,
            cancellation=token,
        )

    result = measure_costs(
        spec, profile_m=m, comparison=comparison, work_dir=tmp_path, probe_factory=ControlledProbe
    )
    assert not result.complete and calls == {"profile_m": 6, "comparison": 6}
    for record in (*result.warmups, *result.observations):
        if record.comparison is not None:
            assert record.state == "not_evaluable"
            assert record.comparison.right.execution == expected
            assert any(
                "execution_inputs_differ" in d.message for d in record.comparison.diagnostics
            )
    assert read_costs(tmp_path / result.cost_id) == result


def test_monitor_thread_failure_preserves_callbacks(tmp_path, monkeypatch):
    import equiframe_benchmark.costs as costs

    spec, m, comparison, calls = environment(tmp_path)

    def failed_start(self):
        raise RuntimeError("synthetic unavailable thread")

    monkeypatch.setattr(costs.Thread, "start", failed_start)
    result = measure_costs(
        spec, profile_m=m, comparison=comparison, work_dir=tmp_path, probe_factory=ControlledProbe
    )
    assert calls == {"profile_m": 6, "comparison": 6} and not result.complete
    assert all(
        r.state == "completed" and r.resources.state == "partial"
        for r in (*result.warmups, *result.observations)
    )
    assert all(
        any(i.code == "sampling_thread_unavailable" for i in r.resources.issues)
        for r in (*result.warmups, *result.observations)
    )
    assert read_costs(tmp_path / result.cost_id) == result


def test_complete_processing_of_invalid_expected_is_not_evaluable_cost(tmp_path):
    import pyarrow as pa

    spec, m, _, calls = environment(tmp_path)
    expected = expected_table(cases()[0]).rename_columns(["id", "wrong_amount", "measurement"])
    assert isinstance(expected, pa.Table)
    ref = write_table(expected, tmp_path / "invalid-expected.arrow")
    spec = spec.model_copy(update={"reference": ref})

    def comparison(directory, token):
        calls["comparison"] += 1
        return ef.compare(
            spec.execution,
            ref,
            contract=spec.execution.plan.contract,
            policy=spec.comparison_policy,
            reference="expected",
            work_dir=directory,
            cancellation=token,
        )

    result = measure_costs(
        spec, profile_m=m, comparison=comparison, work_dir=tmp_path, probe_factory=ControlledProbe
    )
    assert not result.complete and calls == {"profile_m": 6, "comparison": 6}
    for record in (*result.warmups, *result.observations):
        if record.comparison is not None:
            assert record.comparison.complete and record.comparison.state == "not_evaluable"
            assert record.state == "not_evaluable" and record.resources.wall_seconds > 0
            assert any(d.code == "invalid_expected" for d in record.comparison.diagnostics)
    assert read_costs(tmp_path / result.cost_id) == result


def test_mid_operation_cancellation_keeps_original_comparison_and_diagnostics(tmp_path):
    spec, m, comparison, calls = environment(tmp_path)
    token = ef.CancellationToken()

    def cancelled(directory, cancellation):
        cancellation.cancel()
        return comparison(directory, cancellation)

    result = measure_costs(
        spec,
        profile_m=m,
        comparison=cancelled,
        cancellation=token,
        work_dir=tmp_path,
        probe_factory=ControlledProbe,
    )
    first = result.warmups[0]
    assert not result.complete and calls == {"comparison": 1}
    assert first.state == "cancelled" and first.comparison.state == "not_evaluable"
    assert first.resources.wall_seconds > 0
    assert any(d.code == "cancelled" for d in first.comparison.diagnostics)
    assert all(r.state == "cancelled" for r in (*result.warmups, *result.observations))
    assert read_costs(tmp_path / result.cost_id) == result


def test_optional_default_probe_collects_actual_process_resources(tmp_path):
    pytest.importorskip("psutil")
    spec, m, comparison, calls = environment(tmp_path)
    result = measure_costs(spec, profile_m=m, comparison=comparison, work_dir=tmp_path)
    assert calls == {"profile_m": 6, "comparison": 6}
    for record in (*result.warmups, *result.observations):
        assert record.state == "completed"
        assert record.resources.wall_seconds > 0 and record.resources.cpu_seconds >= 0
        assert record.resources.rss_baseline_bytes > 0
        assert record.resources.sampled_rss_peak_bytes >= record.resources.rss_baseline_bytes
    assert read_costs(tmp_path / result.cost_id) == result


def test_resource_results_reject_fake_peak_cpu_and_inconsistent_protocol(tmp_path):
    spec, m, comparison, _ = environment(tmp_path)
    result = measure_costs(
        spec, profile_m=m, comparison=comparison, work_dir=tmp_path, probe_factory=ControlledProbe
    )
    measured = result.observations[0].resources
    with pytest.raises(ValidationError, match="absolute RSS"):
        ResourceMeasurement.model_validate(
            {**measured.model_dump(), "sampled_rss_peak_bytes": 1000}
        )
    with pytest.raises(ValidationError, match="counter delta"):
        ResourceMeasurement.model_validate({**measured.model_dump(), "cpu_seconds": 0.0})
    with pytest.raises(ValidationError, match="alternating schedule"):
        CostComparisonResult.model_validate(
            {**result.model_dump(), "observations": result.observations[:-1]}
        )
    with pytest.raises(ValidationError):
        CostProtocol.model_validate({**spec.protocol.model_dump(), "repetitions": 10})
