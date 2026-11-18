"""Optional diagnostics CLI using the same Python implementation."""

import json
from pathlib import Path

import typer

from equiframe._error_reporting import report_failure
from equiframe.evidence import load_json

from .api import analyze, analyze_migration, read_result
from .models import EdaConfig, Source

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)


@app.command("run")
def run(
    source: Path,
    output: Path = typer.Option(...),
    config: Path | None = typer.Option(None),
    format: str = typer.Option("parquet"),
    snapshot_id: str = typer.Option("local"),
    expected_sha256: str | None = typer.Option(None),
    manifest: Path | None = typer.Option(None),
    manifest_sha256: str | None = typer.Option(None),
) -> None:
    """Profile one immutable file; 0 complete, 2 invalid metadata, 3 unavailable/failure."""
    try:
        spec = Source.model_validate(
            {
                "path": str(source),
                "format": format,
                "snapshot_id": snapshot_id,
                "expected_sha256": expected_sha256,
                "manifest_path": str(manifest) if manifest is not None else None,
                "manifest_sha256": manifest_sha256,
            }
        )
        result = analyze(
            spec, config=load_json(EdaConfig, config) if config is not None else None, output=output
        )
    except Exception as error:
        typer.echo(
            report_failure(error, "EDA request failed. Check the inputs and retry."), err=True
        )
        raise typer.Exit(2) from None
    typer.echo(
        json.dumps(
            {
                "state": result.state,
                "run_id": result.run_id,
                "rows": result.rows,
                "reason": result.reason,
                "report": str(output / "report.html"),
            }
        )
    )
    raise typer.Exit(0 if result.state == "completed" else 3)


@app.command("migration")
def migration(
    path: Path,
    output: Path = typer.Option(...),
    side: str = typer.Option("source"),
    config: Path | None = typer.Option(None),
) -> None:
    """Read verified migration output; no ETL or original evidence edits."""
    from typing import Literal, cast

    try:
        result = analyze_migration(
            path,
            side=cast("Literal['source', 'target']", side),
            config=load_json(EdaConfig, config) if config is not None else None,
            output=output,
        )
    except Exception as error:
        typer.echo(
            report_failure(error, "EDA request failed. Check the inputs and retry."), err=True
        )
        raise typer.Exit(2) from None
    typer.echo(result.state)
    raise typer.Exit(0 if result.state == "completed" else 3)


@app.command("inspect")
def inspect(path: Path) -> None:
    """Check byte identity; 0 intact even for unavailable/failed stored results, 3 corrupt."""
    try:
        result = read_result(path)
    except Exception as error:
        typer.echo(report_failure(error, "EDA evidence could not be verified."), err=True)
        raise typer.Exit(3) from None
    typer.echo(
        json.dumps({"state": result.state, "run_id": result.run_id, "integrity": "verified"})
    )


def main() -> None:
    app()
