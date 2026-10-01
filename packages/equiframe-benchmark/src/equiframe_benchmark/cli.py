"""Benchmark commands keep experimental labels outside the operational library."""

import json
from pathlib import Path
from uuid import uuid4

import typer

from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.models import Catalog, SplitManifest
from equiframe_benchmark.splits import dependency_groups, make_splits, split_counts, validate_splits

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)


def _failure(error: Exception) -> None:
    invalid = isinstance(error, ValueError)
    typer.echo("invalid_input" if invalid else "operation_failed", err=True)
    raise typer.Exit(code=2 if invalid else 3) from None


@app.command("validate")
def validate_command(catalog: Path, splits: Path | None = typer.Option(None)) -> None:
    """Validate a catalog and optional grouped partition manifest; never create labels."""
    try:
        document = load_document(Catalog, catalog)
        summary: dict[str, object] = {
            "catalog_id": document.catalog_id,
            "synthetic": document.synthetic,
            "scenarios": len(document.scenarios),
            "groups": len(dependency_groups(document)),
            "scientific_review_confirmed": False,
        }
        if splits:
            manifest = load_document(SplitManifest, splits)
            validate_splits(document, manifest)
            summary["partitions"] = split_counts(document, manifest)
    except Exception as error:
        _failure(error)
        return
    typer.echo(json.dumps(summary, sort_keys=True))


@app.command("split")
def split_command(
    catalog: Path,
    output: Path = typer.Option(...),
    seed: int = typer.Option(...),
    training: int = typer.Option(3),
    calibration: int = typer.Option(1),
    test: int = typer.Option(2),
) -> None:
    """Create an exclusive grouped split with an explicit seed and integer weights."""
    try:
        document = load_document(Catalog, catalog)
        manifest = make_splits(document, seed=seed, weights=(training, calibration, test))
        validate_splits(document, manifest)
        save_document(manifest, output)
    except Exception as error:
        _failure(error)
        return
    typer.echo(json.dumps(split_counts(document, manifest), sort_keys=True))


@app.command("pilot")
def pilot_command(output: Path = typer.Option(Path("equiframe-benchmark-runs"))) -> None:
    """Run a new synthetic native pilot; human reviews remain pending."""
    from equiframe_benchmark.pilot import run_pilot

    directory = output.resolve() / ("pilot_" + uuid4().hex)
    try:
        summary = run_pilot(directory)
    except Exception as error:
        _failure(error)
        return
    typer.echo(json.dumps({"pilot_id": directory.name, **summary}, sort_keys=True))


def main() -> None:
    app()
