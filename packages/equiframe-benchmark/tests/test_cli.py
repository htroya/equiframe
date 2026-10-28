import json

from typer.testing import CliRunner

import equiframe_benchmark as eb
from equiframe_benchmark.cli import app


def test_catalog_and_split_commands(make_case, tmp_path):
    catalog = eb.Catalog(catalog_id="cli.synthetic", synthetic=True, scenarios=(make_case()[0],))
    path, output = tmp_path / "catalog.json", tmp_path / "split.json"
    eb.save_document(catalog, path)
    runner = CliRunner()
    response = runner.invoke(app, ["validate", str(path)])
    assert response.exit_code == 0, response.output
    assert json.loads(response.stdout)["scientific_review_confirmed"] is False
    response = runner.invoke(app, ["split", str(path), "--output", str(output), "--seed", "8"])
    assert response.exit_code == 0, response.output
    manifest = eb.load_document(eb.SplitManifest, output)
    eb.validate_splits(catalog, manifest)
    assert runner.invoke(app, ["validate", str(path), "--splits", str(output)]).exit_code == 0
    assert (
        runner.invoke(app, ["split", str(path), "--output", str(output), "--seed", "8"]).exit_code
        == 3
    )
    assert eb.load_document(eb.SplitManifest, output) == manifest
    response = runner.invoke(
        app, ["split", str(path), "--output", str(tmp_path / "bad.json"), "--seed", "-1"]
    )
    assert response.exit_code == 2 and not (tmp_path / "bad.json").exists()


def test_invalid_and_unreadable_catalogs_do_not_log_contents(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"token":"do-not-log", "token":"duplicate"}', encoding="utf8")
    response = CliRunner().invoke(app, ["validate", str(path)])
    assert response.exit_code == 2 and "do-not-log" not in response.output
    response = CliRunner().invoke(app, ["validate", str(tmp_path / "missing.json")])
    assert response.exit_code == 3 and "Traceback" not in response.output
