"""Exercise the installed SERCOP command with controlled captured outputs."""

import json
import shutil
from hashlib import sha256
from pathlib import Path

import pyarrow as pa
import pytest
from typer.testing import CliRunner

import equiframe as ef
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
    query += f"SELECT buyer, currency, CAST({column} AS BIGINT) AS total FROM grouped"
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
    execution = ef.execute(
        plan,
        source=ef.LocalDataSource({"source": ef.ArrowInput(pa.Table.from_pylist(rows))}),
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


def call(root: Path, fault: str, rscript: str) -> tuple[int, dict]:
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
            "--rscript",
            rscript,
            "--output",
            str(output),
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
    assert code == (1 if fault else 3 if alert else 0)
    assert report["publishable"] == (code == 0)
