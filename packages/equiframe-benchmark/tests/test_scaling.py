"""Independent tiny workload facts, all stages and fail-closed finalization."""

import errno
import json
from pathlib import Path

import equiframe as ef
import pyarrow as pa
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from equiframe_benchmark import ScaleSpec, measure_scale, read_scale, summarize_scale
from equiframe_benchmark._scale_workload import capture, make_contract, run_trial
from equiframe_benchmark.cli import app
from equiframe_benchmark.io import save_document
from equiframe_benchmark.scale_types import STAGES, ScaleTrial


def spec(**kwargs):
    return ScaleSpec(case_id="tiny", rows=9, width=4, repetitions=2, batch_rows=3, **kwargs)


@pytest.mark.parametrize("alignment", ["keyed", "multiset"])
@pytest.mark.parametrize("different", [False, True])
def test_generator_and_baselines_have_independent_expected_rows(tmp_path, alignment, different):
    config = spec(alignment=alignment, null_every=3, difference_last=different)
    result = run_trial(config, tmp_path / "trial", 0)
    with pa.memory_map(str(tmp_path / "trial/expected.arrow")) as source:
        table = pa.ipc.open_file(source).read_all()
    assert table.to_pylist() == [
        {"id": 0, "value_1": None, "value_2": None, "value_3": None},
        {"id": 1, "value_1": 1, "value_2": "xx1", "value_3": 1},
        {"id": 2, "value_1": 2, "value_2": "xxx2", "value_3": 2},
        {"id": 3, "value_1": None, "value_2": None, "value_3": None},
        {"id": 4, "value_1": 4, "value_2": "xxxxx4", "value_3": 4},
        {"id": 5, "value_1": 5, "value_2": "xxxxxx5", "value_3": 5},
        {"id": 6, "value_1": None, "value_2": None, "value_3": None},
        {"id": 7, "value_1": 7, "value_2": "xxxxxxxx7", "value_3": 7},
        {"id": 8, "value_1": 8, "value_2": "xxxxxxxxx8", "value_3": 8},
    ]
    expected = "different" if different else "equivalent"
    assert result.comparison.state == expected and result.comparison.complete
    assert tuple(stage.name for stage in result.stages) == STAGES
    assert result.comparison.counts.left_rows == result.comparison.counts.right_rows == 9
    assert result.verified_difference_records == (1 if alignment == "keyed" else 2) * different
    for baseline in result.baselines:
        if baseline.method == "duckdb_sql" or (
            baseline.method == "pandas_assert" and alignment == "keyed"
        ):
            assert baseline.state == expected
        else:
            assert baseline.state in ("not_applicable", "not_available")
    assert all(stage.wall_seconds >= 0 for stage in result.stages)
    assert result.evidence_bytes > 0


def test_duplicate_skew_and_last_batch_keep_multiplicity(tmp_path):
    config = spec(distinct_rows=1, skew_percent=100, difference_last=True)
    result = run_trial(config, tmp_path / "trial", 0)
    assert result.comparison.state == "different"
    assert result.comparison.counts.matched_rows == 8
    records = list(ef.iter_differences(result.comparison.differences))
    assert len(records) == 2
    assert all(item.code == "row_multiplicity" for item in records)
    assert not list((tmp_path / "trial").rglob("work.sqlite*"))


def test_dense_difference_even_at_null_is_real(tmp_path):
    config = spec(difference_every=1, null_every=2, alignment="keyed", run_baselines=False)
    result = run_trial(config, tmp_path / "trial", 0)
    assert result.comparison.counts.difference_records == 9
    assert result.baselines == ()


@pytest.mark.parametrize(
    "options,code",
    [
        (ef.ComparisonOptions(max_rows=1), "resource_exhausted"),
        (ef.ComparisonOptions(max_work=1), "resource_exhausted"),
        (ef.ComparisonOptions(max_evidence_bytes=1), "resource_exhausted"),
        (ef.ComparisonOptions(max_disk_bytes=4096), "resource_exhausted"),
        (ef.ComparisonOptions(max_batch_bytes=1), "resource_exhausted"),
        (ef.ComparisonOptions(timeout_seconds=0.000000001), "timeout"),
    ],
)
def test_cooperative_budgets_never_become_success(tmp_path, options, code):
    config = spec(difference_last=True, run_baselines=False, comparison_options=options)
    result = run_trial(config, tmp_path / "trial", 0)
    assert result.comparison.state == "not_evaluable"
    assert not result.comparison.complete
    assert code in [issue.code for issue in result.comparison.diagnostics]
    assert not list((tmp_path / "trial").rglob("work.sqlite*"))


def test_cancelled_comparison_keeps_safe_state_and_cleans_owned_temp(tmp_path):
    config = spec()
    left, right = capture(config, tmp_path)
    token = ef.CancellationToken()
    token.cancel()
    result = ef.compare(
        left,
        right,
        contract=make_contract(config),
        cancellation=token,
        work_dir=tmp_path / "compare",
    )
    assert result.state == "not_evaluable" and not result.complete
    assert result.diagnostics[0].code == "cancelled"
    assert not list(tmp_path.rglob("work.sqlite*"))


def test_injected_enospc_at_publication_leaves_no_completion(tmp_path, monkeypatch):
    import equiframe.comparison as comparison

    config = spec()
    left, right = capture(config, tmp_path)
    original = comparison.os.link

    def fail(source, destination, *args, **kwargs):
        if Path(destination).name == "comparison.json":
            raise OSError(errno.ENOSPC, "injected bounded disk-full publication failure")
        return original(source, destination, *args, **kwargs)

    monkeypatch.setattr(comparison.os, "link", fail)
    with pytest.raises(OSError) as caught:
        ef.compare(left, right, contract=make_contract(config), work_dir=tmp_path / "compare")
    assert caught.value.errno == errno.ENOSPC
    assert not list((tmp_path / "compare").rglob("comparison.json"))
    assert not list((tmp_path / "compare").rglob("work.sqlite*"))


@pytest.fixture
def measured(tmp_path):
    result = measure_scale(spec(difference_last=True, run_baselines=False), work_dir=tmp_path)
    assert result.complete, result.issues
    return tmp_path / result.run_id, result


def test_real_supervised_pipeline_roundtrip_and_summary(measured):
    directory, result = measured
    assert read_scale(directory) == result
    assert result.process.cleanup_reaped and result.process.exit_code == 0
    assert result.process.observed_descendant_pids == ()
    assert result.process.sampled_rss_peak_bytes > 0
    assert result.process.sample_interval_seconds == 0.25
    assert all(trial.resources.sample_interval_seconds == 0.25 for trial in result.trials)
    assert result.resource_measurement_complete == (not result.process.monitoring_errors)
    summary = summarize_scale(result)
    assert summary["correct_complete_repetitions"] == 2
    assert summary["unsuccessful_or_missing_repetitions"] == 0
    assert summary["statistics_by_cache"]["warm_process_os_cache_uncontrolled"]["n"] == 1
    assert summary["resource_measurement_contract"]["id"] == ("equiframe_process_resources_v1")
    assert summary["resource_measurement_contract"]["platform"] in (
        "linux",
        "windows",
        "macos",
    )
    assert len(summary["resource_measurement_contract"]["metrics"]) == 9
    assert not any(name in result.environment for name in ("hostname", "username", "HOME", "PATH"))


@pytest.mark.parametrize(
    "file", ["finished.json", "worker/worker-completed.json", "worker/trial-000.json"]
)
def test_missing_completion_or_receipt_is_never_accepted(measured, file):
    directory, _ = measured
    (directory / file).unlink()
    with pytest.raises((OSError, ValueError, ef.ArtifactIntegrityError)):
        read_scale(directory)
    response = CliRunner().invoke(app, ["verify-scale", str(directory)])
    assert response.exit_code == 3


def test_tamper_and_extra_files_are_rejected(measured):
    directory, _ = measured
    (directory / "unlisted.txt").write_text("unlisted")
    with pytest.raises(ValueError, match="inventory"):
        read_scale(directory)


def test_timeout_keeps_failure_receipt_and_missing_trials(tmp_path):
    result = measure_scale(spec(timeout_seconds=0.0000001), work_dir=tmp_path)
    assert not result.complete
    assert result.process.termination_reason == "timeout"
    assert result.process.exit_code != 0
    assert not result.worker_finalized
    assert read_scale(tmp_path / result.run_id) == result
    summary = summarize_scale(result)
    assert summary["unsuccessful_or_missing_repetitions"] == 2
    response = CliRunner().invoke(app, ["verify-scale", str(tmp_path / result.run_id)])
    assert response.exit_code == 3


def test_cli_valid_measurement_then_verify(tmp_path):
    save_document(spec(run_baselines=False), tmp_path / "spec.json")
    runner = CliRunner()
    response = runner.invoke(
        app, ["scale", str(tmp_path / "spec.json"), "--output", str(tmp_path / "output")]
    )
    assert response.exit_code == 0, response.output
    summary = json.loads(response.output)
    verified = runner.invoke(app, ["verify-scale", str(tmp_path / "output" / summary["run_id"])])
    assert verified.exit_code == 0
    assert json.loads(verified.output)["complete"]


@pytest.mark.parametrize(
    "changes",
    [
        {"rows": 1_000_001},
        {"width": 33},
        {"repetitions": 1},
        {"rows": 5, "distinct_rows": 6},
        {"alignment": "keyed", "distinct_rows": 1},
    ],
)
def test_unsafe_or_contradictory_spec_rejected(changes):
    with pytest.raises(ValidationError):
        ScaleSpec(case_id="invalid", **changes)


def test_trial_schema_rejects_missing_stage_or_false_counts(tmp_path):
    result = run_trial(spec(run_baselines=False), tmp_path / "trial", 0)
    for updates in (
        {"stages": result.stages[:-1]},
        {"verified_difference_records": 1},
        {"evidence_bytes": 0},
    ):
        with pytest.raises(ValidationError):
            ScaleTrial.model_validate({**result.model_dump(), **updates})


def test_real_native_kill_no_manifest_cleanup_and_safe_reader(tmp_path, monkeypatch):
    import sys

    import equiframe_benchmark.scaling as scaling
    from equiframe_benchmark.scale_process import supervise

    def killed_worker(command, **kwargs):
        script = (
            "import os,signal,pathlib; "
            "p=pathlib.Path('trial-000/comparison/comparison-interrupted'); "
            "p.mkdir(parents=True); (p/'work.sqlite').write_bytes(b'x'*4096); "
            "(p/'input.arrow').write_bytes(b'partial evidence retained'); "
            "os.kill(os.getpid(),signal.SIGKILL)"
        )
        return supervise([sys.executable, "-I", "-c", script], **kwargs)

    monkeypatch.setattr(scaling, "supervise", killed_worker)
    result = measure_scale(spec(run_baselines=False), work_dir=tmp_path)
    assert not result.complete and result.process.exit_code != 0
    assert not result.worker_finalized and not result.trials
    assert result.removed_temporary_bytes == {
        "trial-000/comparison/comparison-interrupted/work.sqlite": 4096
    }
    directory = tmp_path / result.run_id
    assert not list(directory.rglob("work.sqlite*"))
    assert (directory / "worker/trial-000/comparison/comparison-interrupted/input.arrow").is_file()
    assert read_scale(directory) == result


def test_exit_zero_without_worker_completion_never_succeeds(tmp_path, monkeypatch):
    import sys

    import equiframe_benchmark.scaling as scaling
    from equiframe_benchmark.scale_process import supervise

    def empty_worker(command, **kwargs):
        return supervise([sys.executable, "-I", "-c", "pass"], **kwargs)

    monkeypatch.setattr(scaling, "supervise", empty_worker)
    result = measure_scale(spec(run_baselines=False), work_dir=tmp_path)
    assert result.process.exit_code == 0
    assert not result.complete and not result.worker_finalized
    assert read_scale(tmp_path / result.run_id) == result


def test_result_rejects_changed_contract_and_dropped_baselines(measured):
    from equiframe_benchmark.scaling import ScaleRun

    _, result = measured
    changed = result.model_dump()
    changed["trials"][0]["comparison"]["reference"] = "peer"
    with pytest.raises(ValidationError):
        ScaleRun.model_validate(changed)


def test_reader_uses_bounded_strict_json(tmp_path, monkeypatch):
    import equiframe.evidence as evidence

    from equiframe_benchmark.scaling import ScaleFinalization, load_json

    monkeypatch.setattr(evidence, "MAX_DOCUMENT_BYTES", 32)
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * 33)
    with pytest.raises(ef.ResourceLimitError, match="budget"):
        load_json(ScaleFinalization, path)


def test_measurement_quality_keeps_missing_counters_explicit(measured):
    from equiframe_benchmark.scaling import ScaleRun

    _, result = measured
    data = result.model_dump()
    data["process"]["sampled_rss_peak_bytes"] = None
    data["process"]["monitoring_errors"] = ("sampled_rss_peak_bytes_unavailable",)
    coverage = next(
        item
        for item in data["process"]["metric_coverage"]
        if item["metric"] == "sampled_rss_peak_bytes"
    )
    coverage.update(
        state="measurement_failed",
        source=None,
        reason="sampled_rss_peak_bytes_unavailable",
    )
    partial = ScaleRun.model_validate(data)
    assert partial.complete
    assert not partial.resource_measurement_complete
    summary = summarize_scale(partial)
    assert summary["complete"] and not summary["resource_measurement_complete"]


def test_parent_child_producer_mismatch_fails_closed(tmp_path, monkeypatch):
    import equiframe_benchmark.scaling as scaling

    original = scaling._environment

    def mismatched_parent():
        return {**original(), "core_python_sources_sha256": "0" * 64}

    monkeypatch.setattr(scaling, "_environment", mismatched_parent)
    result = measure_scale(spec(run_baselines=False), work_dir=tmp_path)
    assert result.worker_finalized and result.process.exit_code == 0
    assert result.environment_origin == "worker"
    assert result.environment["core_python_sources_sha256"] != "0" * 64
    assert result.producer_runtime_matches_parent is False
    assert not result.complete
    assert "worker_producer_environment_mismatch" in result.issues
    assert read_scale(tmp_path / result.run_id) == result


def test_missing_worker_environment_never_claims_producer_binding(tmp_path):
    result = measure_scale(spec(timeout_seconds=0.0000001), work_dir=tmp_path)
    assert result.environment_origin == "parent_only_worker_unavailable"
    assert result.producer_runtime_matches_parent is None
    assert not result.complete


def test_oversized_aggregate_never_publishes_success(tmp_path, monkeypatch):
    import equiframe_benchmark.scale_io as scale_io

    # The spec fits; the complete embedded two-trial result is larger. The
    # isolated worker retains its normal budget, so this exercises parent publication.
    monkeypatch.setattr(scale_io, "MAX_SCALE_DOCUMENT_BYTES", 4096)
    with pytest.raises(ef.ResourceLimitError, match="publication budget"):
        measure_scale(spec(run_baselines=False), work_dir=tmp_path)
    run = next(tmp_path.glob("scale-*"))
    assert (run / "worker/worker-completed.json").is_file()
    assert not (run / "scale.json").exists()
    assert not (run / "finished.json").exists()
    with pytest.raises(FileNotFoundError):
        read_scale(run)
