"""Real directory links must be refused before EDA reads or publishes evidence."""

import csv
import hashlib
import html
import json
import os
import subprocess
from pathlib import Path

import pytest

from equiframe.eda import Conversion, EdaConfig, Source, analyze, analyze_migration, read_result


def directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        quoted_link = str(link).replace("'", "''")
        quoted_target = str(target).replace("'", "''")
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"New-Item -ItemType Junction -Path '{quoted_link}' "
                f"-Target '{quoted_target}' | Out-Null",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert link.lstat().st_file_attributes & 0x400
    else:
        link.symlink_to(target, target_is_directory=True)


def csv_source(tmp_path: Path) -> Source:
    folder = tmp_path / "input"
    folder.mkdir()
    path = folder / "source.csv"
    path.write_text("id,amount\nA,1\nB,2\n", encoding="utf-8")
    return Source(path=str(path), format="csv", snapshot_id="synthetic-path-test")


def test_source_directory_link_is_rejected_without_creating_output(tmp_path):
    source = csv_source(tmp_path)
    link = tmp_path / "alias"
    directory_link(link, Path(source.path).parent)
    aliased = source.model_copy(update={"path": str(link / "source.csv")})
    with pytest.raises(ValueError, match=r"link|reparse"):
        analyze(aliased, output=tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_output_directory_link_is_rejected_before_publication(tmp_path):
    source = csv_source(tmp_path)
    target = tmp_path / "actual-output"
    target.mkdir()
    link = tmp_path / "alias"
    directory_link(link, target)
    with pytest.raises(ValueError, match=r"link|reparse"):
        analyze(source, output=link / "new-run")
    assert list(target.iterdir()) == []


def test_source_manifest_directory_link_is_rejected_without_output(tmp_path):
    source = csv_source(tmp_path)
    actual = tmp_path / "delivery"
    actual.mkdir()
    manifest = actual / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    link = tmp_path / "alias"
    directory_link(link, actual)
    aliased = source.model_copy(
        update={
            "manifest_path": str(link / "manifest.json"),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match=r"link|reparse"):
        analyze(aliased, output=tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("reader", [read_result, analyze_migration])
def test_result_and_migration_directory_links_are_rejected_before_reads(tmp_path, reader):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "alias"
    directory_link(link, actual)
    with pytest.raises(ValueError, match=r"link|reparse"):
        if reader is read_result:
            reader(link)
        else:
            reader(link, output=tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("member", ["../source.csv", "/source.csv", "nested\\source.csv"])
def test_manifest_members_cannot_escape_their_delivery(tmp_path, member):
    source = csv_source(tmp_path)
    manifest = Path(source.path).parent / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"schema": "equiframe.sercop-public-dataset-delivery.v1", "files": [{"file": member}]}
        ),
        encoding="utf-8",
    )
    source = source.model_copy(
        update={
            "manifest_path": str(manifest),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match=r"inventory|delivery"):
        analyze(source, output=tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_source_manifest_must_be_an_object_before_creating_output(tmp_path):
    source = csv_source(tmp_path)
    manifest = Path(source.path).parent / "manifest.json"
    manifest.write_text("[]", encoding="utf-8")
    source = source.model_copy(
        update={
            "manifest_path": str(manifest),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }
    )
    with pytest.raises(ValueError, match="must be an object"):
        analyze(source, output=tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_csv_sql_and_html_syntax_remains_literal_column_text(tmp_path):
    source = csv_source(tmp_path)
    dangerous = "total'); DROP TABLE raw;--<script>alert('x')</script>"
    with Path(source.path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", dangerous])
        writer.writerows([["A", "one"], ["B", "two"]])
    result = analyze(source, output=tmp_path / "output")
    assert result.state == "completed" and result.rows == 2
    assert [column.name for column in result.columns] == ["id", dangerous]
    rendered = (tmp_path / "output/report.html").read_text(encoding="utf-8")
    assert html.escape(dangerous) in rendered
    assert "<script>alert('x')</script>" not in rendered


def test_quoted_output_directory_preserves_typed_parquet_without_sql_interpretation(tmp_path):
    source = csv_source(tmp_path)
    output = tmp_path / "output'quoted"
    result = analyze(
        source,
        output=output,
        config=EdaConfig(
            conversions=(Conversion(column="amount", target="number", kind="integer"),),
        ),
    )
    assert result.state == "completed" and result.rows == 2
    assert (output / "typed.parquet").is_file()
    assert read_result(output) == result
