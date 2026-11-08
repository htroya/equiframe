"""Read immutable prior-candidate bytes; current writers never create the oracles.

The corpus is synthetic, source-commit identified, and retains format 1.0. It
is not a claim that either private candidate was a published release.
"""

import hashlib
import importlib
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

import equiframe as ef
from equiframe.evidence import describe_file, load_json, verify_events, verify_files
from equiframe.local import _bundle_paths
from equiframe.report_types import ReportPublicationManifest

CORPUS = Path(__file__).parent / "fixtures" / "versioned"
BASELINE = CORPUS / "baseline"
REPORTS = CORPUS / "reports"
DIRECT = CORPUS / "direct"
BUNDLE = BASELINE / "migration-bundle"
VERIFICATION_BUNDLE = CORPUS / "verification"
FAMILIES = ("nulls_types", "joins", "aggregations", "duplicates_order", "dates")
COMPARISONS = ("equivalent", "different", "not_evaluable", "invalid_expected")
REPORT_CASES = ("diagnostic", "detail", "reproduction", "equivalent", "not_evaluable")


def _json(path):
    return json.loads(path.read_bytes())


def _read_diff_receipt(path):
    result = ef.read_comparison(DIRECT / "comparison.json")
    with _bundle_paths({result.differences.uri: path.parent / "differences.jsonl"}):
        return ef.read_diff_contract(result)


def _version_paths(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "schema_version":
                yield (*path, key)
            else:
                yield from _version_paths(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _version_paths(child, (*path, index))


def _set(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


def test_corpus_is_closed_immutable_and_identifies_actual_prior_source():
    provenance = _json(CORPUS / "provenance.json")
    assert provenance["corpus_version"] == "1"
    assert provenance["sources"]["baseline"]["commit"] == (
        "980c2db862d5a39cf3e8d1ee7d2a8ebfce71c637"
    )
    assert provenance["sources"]["reports"]["commit"] == (
        "4e0d09b611967566f9171d2dfbd9ed8f32b62d09"
    )
    actual = {p.relative_to(CORPUS).as_posix() for p in CORPUS.rglob("*") if p.is_file()}
    assert actual == {entry["path"] for entry in provenance["files"]} | {"provenance.json"}
    for entry in provenance["files"]:
        raw = (CORPUS / entry["path"]).read_bytes()
        assert len(raw) == entry["size_bytes"], entry["path"]
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"], entry["path"]
    for source in provenance["sources"].values():
        assert len(source["source_tree"]) == 40
        assert source["schema_versions"] == ["1.0"]
        assert source["package_version"] == "0.11.1"
        assert _json(CORPUS / source["producer_environment"])["python"] == "3.12.14"


@pytest.mark.parametrize("family", FAMILIES)
def test_historical_contracts_keep_canonical_bytes_and_fingerprints(family):
    original = BASELINE / "contracts" / (family + ".json")
    canonical = (BASELINE / "contracts" / (family + ".canonical.json")).read_bytes()
    contract = ef.read_contract(original)
    assert ef.canonical_contract_bytes(contract) == canonical
    assert ef.contract_fingerprint(contract) == hashlib.sha256(canonical).hexdigest()
    assert ef.validate_contract(canonical) == contract


def test_historical_direct_contract_keeps_bound_policy_provenance():
    declaration = _read_diff_receipt(DIRECT / "diff-contract.json")
    assert declaration.model_dump(mode="json") == _json(DIRECT / "declaration.json")
    assert declaration.reference == "expected"
    assert declaration.spec.contract.output.schema_spec.keys[0].columns == ("id",)
    assert declaration.provenance


@pytest.mark.parametrize(
    "name,state,complete,records,diagnostics",
    [
        ("equivalent", "equivalent", True, 0, ()),
        ("different", "different", True, 1, ()),
        ("not_evaluable", "not_evaluable", False, 0, ("resource_exhausted",)),
        ("invalid_expected", "not_evaluable", True, 4, ("invalid_expected",)),
    ],
)
def test_historical_comparisons_preserve_all_three_states(
    name, state, complete, records, diagnostics
):
    directory = BASELINE / "comparisons" / name
    result = ef.read_comparison(directory / "comparison.json")
    assert result.model_dump(mode="json") == _json(directory / "comparison.json")
    assert (result.state, result.complete, result.counts.final) == (state, complete, complete)
    assert result.counts.difference_records == records
    assert tuple(d.code for d in result.diagnostics) == diagnostics
    # Only relocate the reference used by this read, never the historical bytes.
    ref = result.differences.model_copy(
        update={"uri": (directory / "differences.jsonl").resolve().as_uri()}
    )
    differences = tuple(ef.iter_differences(ref))
    assert len(differences) == records
    assert differences[: len(result.examples)] == result.examples
    assert ef.equivalence_decision(result).accepted is (state == "equivalent")
    with pytest.raises(TypeError, match="no truth value"):
        bool(result)
    if name == "different":
        assert differences[0].code == "cell_value"
        assert differences[0].column == "value"
        assert differences[0].left[0].value == "11"
        assert differences[0].right[0].value == "10"


@pytest.mark.parametrize("name", REPORT_CASES)
def test_historical_reports_preserve_views_privacy_and_publication_inventory(name):
    directory = REPORTS / name
    report = ef.read_comparison_report(directory / "report.json")
    assert report.model_dump(mode="json") == _json(directory / "report.json")
    # Current presentation may evolve. Historical bytes are pinned by the
    # fixture/publication inventories, not by today's presentation templates.
    text, html = report.to_text(), report.to_html()
    for rendered in (text, html):
        assert report.state in rendered and report.coverage in rendered
        assert report.reference in rendered
        assert "file://" not in rendered
    assert "<script" not in html and "<iframe" not in html
    publication = load_json(ReportPublicationManifest, directory / "evidence-manifest.json")
    assert publication.report_evidence == report.evidence
    verify_files(directory, publication.files)
    assert report.state == (name if name in ("equivalent", "not_evaluable") else "different")
    assert report.complete is (name != "not_evaluable")
    assert report.options.include_values is (name in ("detail", "reproduction"))
    if name == "reproduction":
        assert report.evidence.reproduction == "exported_materialized_inputs"


def test_historical_portable_evidence_reads_after_relocation_without_execution(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("reading historical evidence must not execute a transformation")

    monkeypatch.setattr("equiframe.pipeline.run_pipeline", forbidden)
    monkeypatch.setattr("equiframe.migration.runner.migrate", forbidden)
    monkeypatch.setattr("equiframe.execution.execute", forbidden)
    trusted = hashlib.sha256((BUNDLE / "bundle.json").read_bytes()).hexdigest()
    restored = ef.import_bundle(BUNDLE, tmp_path / "relocated", expected_sha256=trusted)
    assert restored.schema_version == "1.0"
    assert restored.kind == "migration"
    assert restored.model_dump(mode="json") == _json(BUNDLE / "bundle.json")
    summary = ef.inspect_bundle(tmp_path / "relocated", expected_sha256=trusted)
    assert summary["integrity"] == "passed"
    assert summary["outcome"]["state"] == "equivalent"
    assert summary["outcome"]["complete"] is True
    for original in BUNDLE.rglob("*"):
        if original.is_file():
            assert (tmp_path / "relocated" / original.relative_to(BUNDLE)).read_bytes() == (
                original.read_bytes()
            )


# Each mutation starts from valid, archived bytes and asserts a version error at
# the exact nested location. A failed hash or an unrelated shape error cannot
# accidentally satisfy this regression.
_TYPED_DOCUMENTS = (
    ("direct-contract", DIRECT / "diff-contract.json", _read_diff_receipt),
    ("comparison", BASELINE / "comparisons/different/comparison.json", ef.read_comparison),
    ("report", REPORTS / "detail/report.json", ef.read_comparison_report),
    (
        "publication",
        REPORTS / "detail/evidence-manifest.json",
        lambda p: load_json(ReportPublicationManifest, p),
    ),
    ("bundle", BUNDLE / "bundle.json", ef.read_bundle),
    (
        "migration",
        BUNDLE / "operation/migration.json",
        lambda p: ef.read_migration(p, verify=False),
    ),
    *(
        (
            "pipeline-" + source.parent.name,
            source,
            lambda p: ef.read_pipeline(p, verify=False),
        )
        for source in sorted((BUNDLE / "operation").glob("pipeline_*/manifest.json"))
    ),
)
_VERSION_CASES = [
    pytest.param(source, reader, path, id=name + ":" + ".".join(map(str, path)))
    for name, source, reader in _TYPED_DOCUMENTS
    for path in _version_paths(_json(source))
]


def test_future_version_collection_covers_both_pipeline_layouts_deterministically():
    pipelines = [
        (name, source) for name, source, _ in _TYPED_DOCUMENTS if name.startswith("pipeline-")
    ]
    assert len(pipelines) == 2
    assert [str(source) for _, source in pipelines] == sorted(
        str(source) for _, source in pipelines
    )
    assert {_json(source)["spec"]["execution"]["engine"] for _, source in pipelines} == {
        "pandas",
        "duckdb",
    }
    version_paths = [path for _, source in pipelines for path in _version_paths(_json(source))]
    assert ("execution", "output", "index", "schema_version") in version_paths
    assert len({name for name, _ in pipelines}) == 2


@pytest.mark.parametrize("version", ["1.1", "2.0", "99.0"])
@pytest.mark.parametrize("source,reader,path", _VERSION_CASES)
def test_future_versions_are_rejected_at_every_nested_versioned_object(
    tmp_path, source, reader, path, version
):
    document = _json(source)
    _set(document, path, version)
    destination = tmp_path / source.name
    destination.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValidationError) as caught:
        reader(destination)
    assert any(
        issue["loc"] == path and issue["type"] == "literal_error" for issue in caught.value.errors()
    )


@pytest.mark.parametrize("version", ["1.1", "2.0", "99.0"])
def test_future_contract_versions_use_public_schema_version_error(tmp_path, version):
    document = _json(BASELINE / "contracts/nulls_types.json")
    document["schema_version"] = version
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ef.SchemaVersionError) as caught:
        ef.read_contract(path)
    assert caught.value.issues[0].code == "unsupported_schema_version"
    assert caught.value.issues[0].location == ("schema_version",)


@pytest.mark.parametrize("kind", ["differences", "events"])
@pytest.mark.parametrize("version", ["1.1", "2.0", "99.0"])
def test_future_jsonl_records_are_rejected_before_interpreting_evidence(tmp_path, kind, version):
    if kind == "differences":
        source = BASELINE / "comparisons/different/differences.jsonl"
    else:
        source = BUNDLE / "operation/events.jsonl"
    records = [json.loads(line) for line in source.read_bytes().splitlines()]
    records[0]["schema_version"] = version
    raw = b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in records)
    path = tmp_path / (kind + ".jsonl")
    path.write_bytes(raw)
    with pytest.raises(ValidationError) as caught:
        if kind == "differences":
            ref = ef.ArtifactRef(
                schema_version="1.0",
                uri=path.as_uri(),
                sha256=hashlib.sha256(raw).hexdigest(),
                size_bytes=len(raw),
                format="jsonl",
                media_type="application/x-ndjson",
            )
            tuple(ef.iter_differences(ref))
        else:
            verify_events(path, operation_id=records[0]["operation_id"])
    assert caught.value.errors()[0]["loc"] == ("schema_version",)
    assert caught.value.errors()[0]["type"] == "literal_error"


def test_missing_versions_keep_only_the_existing_explicit_model_defaults(tmp_path):
    original = _json(BASELINE / "comparisons/different/comparison.json")
    # Existing defaulted fields remain 1.0; this is not a historical migration.
    defaulted = json.loads(json.dumps(original))
    del defaulted["schema_version"]
    del defaulted["spec"]["schema_version"]
    del defaulted["examples"][0]["schema_version"]
    path = tmp_path / "defaults.json"
    path.write_text(json.dumps(defaulted), encoding="utf-8")
    assert ef.read_comparison(path).model_dump(mode="json") == original
    # Contract and ArtifactRef have always required an explicit version.
    for nested in (("spec", "contract"), ("differences",)):
        required = json.loads(json.dumps(original))
        target = required
        for key in nested:
            target = target[key]
        del target["schema_version"]
        path.write_text(json.dumps(required), encoding="utf-8")
        with pytest.raises(ValidationError) as caught:
            ef.read_comparison(path)
        assert any(
            issue["loc"] == (*nested, "schema_version") and issue["type"] == "missing"
            for issue in caught.value.errors()
        )


def test_historical_corpus_rejects_corrupt_and_truncated_portable_evidence(tmp_path):
    destination = tmp_path / "corrupt"
    shutil.copytree(BUNDLE, destination)
    capture = next(destination.rglob("*.arrow"))
    capture.write_bytes(capture.read_bytes()[:-1])
    with pytest.raises(ef.ArtifactIntegrityError, match="SHA-256 or size"):
        ef.read_bundle(destination)


@pytest.mark.parametrize("version", ["1.1", "2.0", "99.0", None, 1, True])
def test_rehashed_environment_cannot_smuggle_an_unsupported_format(tmp_path, version):
    root = tmp_path / "copied"
    shutil.copytree(BUNDLE, root)
    bundle = _json(root / "bundle.json")
    mappings = {r["uri"]: root / r["member"]["path"] for r in bundle["references"]}
    directory = next((root / "operation").glob("pipeline_*"))
    environment = directory / "environment.json"
    data = _json(environment)
    data["schema_version"] = version
    environment.write_text(json.dumps(data), encoding="utf-8")
    manifest = directory / "manifest.json"
    result = _json(manifest)
    # Refresh the hash to isolate format validation from byte-integrity checks.
    result["evidence"] = [
        describe_file(environment, directory).model_dump(mode="json")
        if item["path"] == "environment.json"
        else item
        for item in result["evidence"]
    ]
    manifest.write_text(json.dumps(result), encoding="utf-8")
    with _bundle_paths(mappings), pytest.raises(ValidationError) as caught:
        ef.read_pipeline(directory)
    assert caught.value.errors()[0]["loc"] == ("schema_version",)
    assert caught.value.errors()[0]["type"] == "literal_error"


@pytest.mark.parametrize("mutation", ["raise", "newline"])
def test_archived_readers_do_not_depend_on_current_public_renderers(monkeypatch, mutation):
    renderers = (
        ("equiframe.reporting", "render_report"),
        ("equiframe.migration.io", "render_migration_report"),
        ("equiframe.migration.io", "_render_report"),
        ("equiframe.verify", "render_verification_report"),
    )

    def replacement(original):
        def changed(*args, **kwargs):
            if mutation == "raise":
                raise AssertionError("historical reader called current presentation renderer")
            return original(*args, **kwargs) + "\n"

        return changed

    for module_name, name in renderers:
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, name, replacement(getattr(module, name)))
    assert ef.read_bundle(BUNDLE).kind == "migration"
    assert ef.read_bundle(VERIFICATION_BUNDLE).kind == "verification"


def test_archived_readers_do_not_depend_on_current_summary_builders(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("historical reader called an evolving current summary builder")

    for module_name, name in (
        ("equiframe.reporting", "pipeline_summary"),
        ("equiframe.migration.io", "migration_summary"),
        ("equiframe.migration.io", "_legacy_summary"),
        ("equiframe.verify", "verification_summary"),
    ):
        monkeypatch.setattr(importlib.import_module(module_name), name, forbidden)
    assert ef.read_bundle(BUNDLE).kind == "migration"
    assert ef.read_bundle(VERIFICATION_BUNDLE).kind == "verification"


@pytest.mark.parametrize("kind", ["pipeline", "migration", "verification"])
@pytest.mark.parametrize("part", ["html", "json"])
def test_rehashed_false_historical_reports_are_still_rejected(tmp_path, kind, part):
    root = tmp_path / "copied"
    shutil.copytree(VERIFICATION_BUNDLE if kind == "verification" else BUNDLE, root)
    bundle = _json(root / "bundle.json")
    mappings = {r["uri"]: root / r["member"]["path"] for r in bundle["references"]}
    directory = root / "operation"
    if kind == "pipeline":
        directory = next(directory.glob("pipeline_*"))
    document, reader = {
        "pipeline": ("manifest.json", ef.read_pipeline),
        "migration": ("migration.json", ef.read_migration),
        "verification": ("verification.json", ef.read_verification),
    }[kind]
    report = directory / ("report." + part)
    if part == "html":
        old, new = {
            "pipeline": (b"completed", b"failed"),
            "migration": (b"equivalent", b"different"),
            "verification": (b"passed", b"failed"),
        }[kind]
        raw = report.read_bytes()
        assert old in raw
        report.write_bytes(raw.replace(old, new))
    else:
        summary = _json(report)
        field = "publishable" if kind == "verification" else "complete"
        assert summary[field] is True
        summary[field] = False
        report.write_text(json.dumps(summary), encoding="utf-8")
    manifest = directory / document
    result = _json(manifest)
    result["evidence"] = [
        describe_file(report, directory).model_dump(mode="json")
        if item["path"] == report.name
        else item
        for item in result["evidence"]
    ]
    manifest.write_text(json.dumps(result), encoding="utf-8")
    with _bundle_paths(mappings), pytest.raises(ef.ArtifactIntegrityError, match="contradicts"):
        reader(directory)
