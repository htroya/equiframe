"""Engineering scale commands do not change the scientific benchmark protocol."""

import json
from pathlib import Path

import typer
from equiframe._cli_support import exit_with_failure
from equiframe.evidence import load_json

from equiframe_benchmark.scale_types import ScaleSpec
from equiframe_benchmark.scaling import measure_scale, read_scale, summarize_scale


def register(app: typer.Typer) -> None:
    @app.command("scale")
    def scale_command(spec: Path, output: Path = typer.Option(...)) -> None:
        """Measure one bounded synthetic case with safe process completion checks."""
        try:
            result = measure_scale(load_json(ScaleSpec, spec), work_dir=output)
        except Exception as error:
            exit_with_failure(error, code="scale_operation_failed", exit_code=3)
        typer.echo(json.dumps(summarize_scale(result), sort_keys=True))
        raise typer.Exit(code=0 if result.complete else 3)

    @app.command("verify-scale")
    def verify_scale_command(directory: Path) -> None:
        """Verify all retained bytes and completion; never rerun a workload."""
        try:
            result = read_scale(directory)
        except Exception as error:
            exit_with_failure(
                error,
                code="scale_evidence_invalid_or_incomplete",
                exit_code=3,
                input_validation=False,
            )
        typer.echo(json.dumps(summarize_scale(result), sort_keys=True))
        raise typer.Exit(code=0 if result.complete else 3)
