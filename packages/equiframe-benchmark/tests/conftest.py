"""All people and review decisions here are TEST FIXTURES, never scientific approvals."""

import os
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import equiframe as ef
import pytest

import equiframe_benchmark as eb
from equiframe_benchmark.fixtures import COMPARISON_POLICY, cases, expected_table, registry
from equiframe_benchmark.pilot import profile_spec, write_table


@pytest.fixture(scope="session")
def source_packages():
    """Explicit read-only source inventory, separate from installed imports."""
    configured = os.environ.get("EQUIFRAME_TEST_SOURCE_PACKAGES")
    if configured:
        root = Path(configured)
        packages = {name: root / name for name in ("equiframe", "equiframe-benchmark")}
    else:
        benchmark = Path(__file__).resolve().parents[1]
        config = tomllib.loads((benchmark / "pyproject.toml").read_text("utf-8"))
        core = (benchmark / config["tool"]["uv"]["sources"]["equiframe"]["path"]).resolve()
        packages = {"equiframe": core, "equiframe-benchmark": benchmark}
    if not all((path / "pyproject.toml").is_file() for path in packages.values()):
        pytest.skip("source inventory requires both declared source distributions")
    return packages


@pytest.fixture
def make_case(tmp_path):
    count = 0

    def create(family="nulls_types", *, table=None, kind="control", native=False):
        nonlocal count
        root = tmp_path / str(count)
        count += 1
        root.mkdir()
        case = next(c for c in cases() if c.contract.family == family)
        expected = expected_table(case)
        expected_ref = write_table(expected, root / "expected.arrow")
        inputs = tuple(
            eb.InputBinding(name=n, artifact=write_table(t, root / (n + ".arrow")))
            for n, t in case.inputs.items()
        )
        spec = profile_spec(family)
        scenario = eb.Scenario(
            scenario_id="test." + family,
            family=family,
            dependencies=("template:" + family,),
            authors=("test-author",),
            inputs=inputs,
            transformation_revision="synthetic.v1",
            comparison=ef.ComparisonSpec(contract=case.contract, policy=COMPARISON_POLICY),
            rules_sha256=ef.rule_set_fingerprint(
                case.contract, ef.default_rule_registry(), ef.RuleOptions()
            ),
            features_sha256=ef.profile_spec_fingerprint(spec),
            expected=expected_ref,
            expected_method="manually enumerated test rows",
            expected_authors=("test-author",),
        )
        execution = profile = None
        if native:
            execution = ef.execute(
                ef.ExecutionPlan(contract=case.contract, engine="duckdb", transformation_id=family),
                source=ef.LocalDataSource({i.name: i.artifact for i in inputs}),
                registry=registry(),
                work_dir=root,
            )
            assert execution.state == "completed"
            output = execution.output.data
            profile = ef.profile_execution(execution, spec=spec, work_dir=root)
        else:
            output = write_table(
                expected if table is None else table, root / "secret-mutant-duckdb.arrow"
            )
        candidate = eb.Candidate(
            candidate_id="test.candidate",
            scenario_sha256=eb.digest(scenario),
            output=output,
            authors=("test-author",),
            kind=kind,
            description="private proposed mutation",
            implementation="synthetic.v1",
            rules_sha256_before_candidate=scenario.rules_sha256,
        )
        packet = eb.review_packet(scenario, candidate, directory=root / "review")
        assignment = eb.ReviewAssignment(
            packet_sha256=eb.digest(packet),
            reviewers=("test-reviewer-a", "test-reviewer-b"),
            arbitrator="test-arbitrator",
            assigned_at="2026-10-01T00:00:00Z",
        )
        return scenario, candidate, packet, assignment, execution, profile

    return create


def reviews(packet, labels=("normal", "normal")):
    return tuple(
        eb.Review(
            packet_sha256=eb.digest(packet),
            reviewer=person,
            label=label,
            reason="synthetic test expectation",
            recorded_at="2026-10-01T01:00:00Z",
            blind_attestation=True,
        )
        for person, label in zip(("test-reviewer-a", "test-reviewer-b"), labels, strict=True)
    )


def oracle(data, tmp_path: Path, labels=("normal", "normal"), **kwargs):
    scenario, candidate, packet, assignment, _, _ = data
    return eb.evaluate_oracle(
        scenario,
        candidate,
        packet=packet,
        assignment=assignment,
        reviews=reviews(packet, labels),
        work_dir=tmp_path,
        **kwargs,
    )
