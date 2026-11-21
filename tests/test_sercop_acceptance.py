"""Exercise the installed SERCOP command with controlled captured outputs."""

import json
import shutil
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pytest
from typer.testing import CliRunner

import equiframe as ef
from equiframe import _sercop
from equiframe._bundled_r import _platform
from equiframe._sercop import bundled_model
from equiframe.cli import app
from equiframe.evidence import canonical_bytes, describe_file, publish_json


def write_arrow(table: pa.Table, path: Path) -> ef.ArtifactRef:
    with path.open("xb") as stream, pa.ipc.new_file(stream, table.schema) as writer:
        writer.write_table(table)
    identity = describe_file(path, path.parent)
    return ef.ArtifactRef(
        schema_version="1.0",
        uri=path.as_uri(),
        format="arrow",
        media_type="application/vnd.apache.arrow.file",
        sha256=identity.sha256,
        size_bytes=identity.size_bytes,
    )


def request(root: Path, fault: str) -> Path:
    pytest.importorskip("duckdb")
    info, _ = bundled_model()
    rows = [
        {
            "ocid": f"process-{i}",
            "award": f"award-{i}",
            "buyer": f"buyer-{i:02d}",
            "currency": "USD",
            "amount": 20_000 + i if i < 28 else 9_999,
        }
        for i in range(32)
    ]
    # The literal business rule yields 28 groups, in exact integer cents.
    reference = write_arrow(
        pa.table(
            {
                "buyer": [f"buyer-{i:02d}" for i in range(28)],
                "currency": ["USD"] * 28,
                "total": list(range(20_000, 20_028)),
            }
        ),
        root / "reference.arrow",
    )
    query = (
        "WITH grouped AS (SELECT buyer, currency, sum(amount) AS total FROM source "
        "WHERE amount >= 10000 GROUP BY buyer, currency) "
    )
    column = "CASE WHEN buyer = 'buyer-00' THEN total + 1 ELSE total END"
    if fault != "one_cent":
        column = "total"
    keys = "currency, buyer" if fault == "output_column_order" else "buyer, currency"
    query += f"SELECT {keys}, CAST({column} AS BIGINT) AS total FROM grouped"
    if fault == "missing_group":
        query += " WHERE buyer <> 'buyer-00'"
    if fault == "duplicate_group":
        query += " UNION ALL SELECT buyer, currency, CAST(total AS BIGINT) FROM grouped "
        query += "WHERE buyer = 'buyer-00'"
    registry = ef.TransformationRegistry()
    registry.register(ef.DuckDBTransformation("acceptance_check", query, "qa.1"))
    plan = ef.ExecutionPlan(
        contract=info.contract, engine="duckdb", transformation_id="acceptance_check"
    )
    source = pa.Table.from_pylist(rows)
    if fault == "input_column_order":
        source = source.select(source.column_names[::-1])
    execution = ef.execute(
        plan,
        source=ef.LocalDataSource({"source": ef.ArrowInput(source)}),
        registry=registry,
        work_dir=root / "execution",
    )
    assert execution.state == "completed" and execution.output is not None
    plan_sha = sha256(canonical_bytes(plan.model_dump(mode="json"))).hexdigest()
    snapshots = tuple(
        ef.PipelineInput(name=part.name, artifact=part.data) for part in execution.inputs
    )
    binding = ef.ReferenceBinding(
        contract_sha256=info.contract_sha256,
        plan_sha256=plan_sha,
        comparison_spec_sha256=ef.comparison_fingerprint(ef.ComparisonSpec(contract=info.contract)),
        snapshots=tuple((item.name, item.artifact.sha256) for item in snapshots),
        expected_sha256=reference.sha256,
        outputs=(),
    )
    publish_json(binding, root / "binding.json")
    doc = ef.VerificationRequest(
        contract=info.contract,
        plan_sha256=plan_sha,
        snapshots=snapshots,
        expected=reference,
        outputs=(ef.PipelineInput(name="candidate", artifact=execution.output.data),),
        executions=() if fault == "no_receipt" else (("candidate", execution),),
    )
    path = root / "request.json"
    publish_json(doc, path)
    if not fault:
        profile = ef.profile_execution(
            execution, spec=bundled_model()[1].fit.preprocessor.spec, work_dir=root / "features"
        )
        assert profile.complete
        publish_json(profile.vector, root / "vector.json")
    return path


def call(root: Path, fault: str, rscript: str | None = None) -> tuple[int, dict]:
    doc = request(root, fault)
    output = root / "review"
    run = CliRunner().invoke(
        app,
        [
            "sercop",
            "accept",
            str(doc),
            "--reference-binding",
            str(root / "binding.json"),
            "--output",
            str(output),
            *(["--rscript", rscript] if rscript is not None else []),
        ],
    )
    report = json.loads(run.stdout)
    (saved,) = output.glob("*-sercop/report.json")
    assert json.loads(saved.read_bytes()) == report
    return run.exit_code, report


def test_bundled_model_and_pure_profile_score(tmp_path):
    report = CliRunner().invoke(app, ["sercop", "model"])
    assert report.exit_code == 0, report.output
    assert json.loads(report.stdout)["source_years"] == list(range(2019, 2027))
    request(tmp_path, "")
    score = CliRunner().invoke(app, ["sercop", "score", str(tmp_path / "vector.json")])
    assert score.exit_code == 0, score.output
    observed = json.loads(score.stdout)
    assert observed["score"] is not None and observed["threshold"] is not None


@pytest.mark.parametrize("fault", ["", "no_receipt"])
def test_unavailable_verification_is_never_a_pass(tmp_path, fault):
    code, report = call(tmp_path, fault, str(tmp_path / "missing-Rscript"))
    assert code == 3 and report["publishable"] is False
    assert report["r_review"]["candidate"]["state"] == "not_evaluable"
    assert (
        report["isolation_forest"]["candidate"]["state"] == "not_evaluable"
        if fault
        else (report["isolation_forest"]["candidate"]["state"] in {"no_alert", "alert"})
    )


@pytest.mark.parametrize(
    "fault,forest,r_state,exit_code,case",
    [
        ("", "no_alert", None, 0, "equivalent"),
        ("one_cent", "alert", None, 1, "difference_detected"),
        ("", "alert", "equivalent", 0, "false_alarm_confirmed"),
        ("one_cent", "no_alert", "different", 1, "miss_confirmed"),
        ("", "alert", "different", 3, "comparators_disagree"),
        ("", "alert", "not_evaluable", 3, "r_confirmation_unavailable"),
        ("one_cent", "no_alert", "not_evaluable", 1, "r_confirmation_unavailable"),
        ("", "not_evaluable", "equivalent", 3, "isolation_forest_unavailable"),
    ],
)
def test_acceptance_reconciles_forest_with_independent_evidence(
    tmp_path, monkeypatch, fault, forest, r_state, exit_code, case
):
    calls = []

    def review(*args, **kwargs):
        calls.append((args, kwargs))
        return {"state": r_state}

    monkeypatch.setattr(_sercop, "score_profile", lambda *_: {"state": forest})
    monkeypatch.setattr(_sercop, "_review_capture_with_r", review)
    code, report = call(tmp_path, fault)
    assert code == exit_code and report["publishable"] == (exit_code == 0)
    assert report["isolation_forest"]["candidate"]["state"] == forest
    assert report["cases"]["candidate"]["state"] == case
    assert report["r_review"]["candidate"]["state"] == (r_state or "not_requested")
    assert len(calls) == (0 if r_state is None else 1)


@pytest.mark.parametrize(
    "fault,forest,scope,name,case",
    [
        ("input_column_order", "no_alert", "input", "source", "equivalent"),
        ("output_column_order", "alert", "output", "candidate", "difference_detected"),
    ],
)
def test_contract_failures_are_visible_in_the_case(
    tmp_path, monkeypatch, fault, forest, scope, name, case
):
    monkeypatch.setattr(_sercop, "score_profile", lambda *_: {"state": forest})
    code, report = call(tmp_path, fault)
    assert code == 1 and report["publishable"] is False
    observed = report["cases"]["candidate"]
    assert observed["state"] == "contract_constraints_failed"
    assert observed["comparison_case"] == case
    (failure,) = report["constraint_failures"]
    assert failure["scope"] == scope and failure["name"] == name
    (comparison,) = (
        item
        for item in report["contract"]["comparisons"]
        if item["comparison_id"] == failure["comparison_id"]
    )
    assert comparison["counts"]["contract_violations"] == failure["contract_violations"] > 0


@pytest.mark.parametrize("changed", [None, "reference", "binding", "receipt", "invalid_json"])
def test_accept_execution_requires_bound_artifacts(tmp_path, monkeypatch, changed):
    request(tmp_path, "")
    monkeypatch.setattr(_sercop, "score_profile", lambda *_: {"state": "no_alert"})
    (receipt,) = (tmp_path / "execution").rglob("run.json")
    reference = tmp_path / "reference.arrow"
    binding = tmp_path / "binding.json"
    if changed == "reference":
        reference.write_bytes(reference.read_bytes() + b"different")
    elif changed == "binding":
        data = json.loads(binding.read_bytes())
        data["plan_sha256"] = "0" * 64
        binding.write_text(json.dumps(data), encoding="utf-8")
    elif changed == "receipt":
        receipt = receipt.with_name("unavailable.json")
    elif changed == "invalid_json":
        receipt = tmp_path / "invalid.json"
        receipt.write_text("{", encoding="utf-8")
    output = tmp_path / "accept"
    run = CliRunner().invoke(
        app,
        [
            "sercop",
            "accept-execution",
            str(receipt),
            str(reference),
            "--reference-binding",
            str(binding),
            "--output",
            str(output),
        ],
    )
    if changed:
        assert run.exit_code == (2 if changed == "invalid_json" else 3), run.output
        assert not output.exists()
        if changed in {"reference", "binding"}:
            assert "reference_binding_mismatch" in run.stderr
    else:
        assert run.exit_code == 0, run.output
        report = json.loads(run.stdout)
        assert report["publishable"] is True
        assert report["cases"]["candidate"]["state"] == "equivalent"
        assert report["constraint_failures"] == []
        (saved,) = output.glob("*-sercop/report.json")
        assert json.loads(saved.read_bytes()) == report


@pytest.mark.parametrize(
    "fault,detector_state,exit_code,case",
    [
        ("", "alert", 0, "false_alarm_confirmed"),
        ("one_cent", "no_alert", 1, "miss_confirmed"),
    ],
)
def test_bundled_r_resolves_discrepancies(
    tmp_path, monkeypatch, fault, detector_state, exit_code, case
):
    try:
        _platform()
    except ef.CapabilityError:
        pytest.skip("no bundled R distribution for this platform")
    monkeypatch.setattr(_sercop, "score_profile", lambda *_: {"state": detector_state})
    code, report = call(tmp_path, fault)
    assert code == exit_code
    assert report["cases"]["candidate"]["state"] == case
    review = report["r_review"]["candidate"]
    assert review["runtime"] == "bundled" and review["runtime_manifest_sha256"]
    assert "4.6.2" in review["r_version"] and review["binding"]


@pytest.mark.parametrize(
    "fault, expected",
    [
        ("", "equivalent"),
        ("one_cent", "different"),
        ("missing_group", "different"),
        ("duplicate_group", "different"),
    ],
)
def test_real_base_r_confirms_expected_captures(tmp_path, fault, expected):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("base R is required for the independent comparator test")
    code, report = call(tmp_path, fault, rscript)
    reviewed = report["r_review"]["candidate"]
    assert reviewed["state"] == expected and reviewed["r_version"]
    assert reviewed["binding"] and reviewed["python_state"] == expected
    alert = report["isolation_forest"]["candidate"]["state"] == "alert"
    assert report["cases"]["candidate"]["state"] == (
        ("difference_detected" if alert else "miss_confirmed")
        if fault
        else ("false_alarm_confirmed" if alert else "equivalent")
    )
    assert code == (1 if fault else 0)
    assert report["publishable"] == (code == 0)
