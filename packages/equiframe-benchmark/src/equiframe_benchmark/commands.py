"""Readiness and reproduction commands; JSON never chooses executable code."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import typer


def register(app: typer.Typer) -> None:
    """Attach commands to the caller's app without an eager circular CLI import."""
    from equiframe_benchmark.cli import _factory, _failure

    @app.command("distribution-readiness")
    def distribution_command(
        package_directory: Path,
        wheel: Path | None = typer.Option(None),
        name_check: Path | None = typer.Option(None),
        output: Path | None = typer.Option(None),
    ) -> None:
        """Inventory local metadata; no PyPI network requests or publication actions."""
        from equiframe_benchmark.distribution import NameCheck, inspect_distribution
        from equiframe_benchmark.io import load_document, save_document

        try:
            observation = load_document(NameCheck, name_check) if name_check else None
            result = inspect_distribution(package_directory, wheel, name_check=observation)
            if output is not None:
                save_document(result, output)
        except Exception as error:
            _failure(error)
            return
        typer.echo(result.model_dump_json())

    @app.command("verify-bundle")
    def verify_command(
        directory: Path,
        expected_sha256: str | None = typer.Option(None),
    ) -> None:
        """Verify closed bundle bytes and inventory without importing a regenerator."""
        from equiframe_benchmark.reproduction import read_bundle

        try:
            result = read_bundle(directory, expected_sha256=expected_sha256)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        typer.echo(
            json.dumps(
                {
                    "bundle_id": result.bundle_id,
                    "evidence_verified": True,
                    "files": len(result.files),
                    "reproduction_record_available": result.record_path is not None,
                    "independent_person_reproduced": False,
                },
                sort_keys=True,
            )
        )

    @app.command("reproduce-bundle")
    def reproduce_command(
        directory: Path,
        regenerator: str = typer.Option(
            ..., help="Explicit trusted module:factory, never from JSON."
        ),
        expected_sha256: str | None = typer.Option(None),
        output: Path | None = typer.Option(None),
    ) -> None:
        """Run an explicitly supplied trusted callable; compare complete logical content."""
        from equiframe_benchmark.io import save_document
        from equiframe_benchmark.reproduction import (
            ReproductionRecord,
            read_bundle,
            reproduce_bundle,
        )

        try:
            # Check persisted evidence before executing even the explicit factory.
            read_bundle(directory, expected_sha256=expected_sha256)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        try:
            supplied = _factory(regenerator)()
            if not callable(supplied):
                raise ValueError("regenerator factory must return a callable")
            callback = cast(Callable[[ReproductionRecord], ReproductionRecord], supplied)
        except Exception as error:
            _failure(error)
            return
        try:
            receipt = reproduce_bundle(
                directory,
                regenerator=callback,
                expected_sha256=expected_sha256,
            )
            if output is not None:
                save_document(receipt, output)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        typer.echo(receipt.model_dump_json())
        if receipt.status == "different":
            raise typer.Exit(code=1)

    @app.command("bundle-study")
    def bundle_study_command(directory: Path, output: Path = typer.Option(...)) -> None:
        """Copy a verified study into a closed bundle without rewriting original evidence."""
        from equiframe_benchmark.study_bundle import bundle_study

        try:
            result = bundle_study(directory, output=output)
        except Exception as error:
            _failure(error)
            return
        typer.echo(
            json.dumps(
                {
                    "bundle_id": result.bundle_id,
                    "files": len(result.files),
                    "independent_person_reproduced": False,
                    "etl_repeated": False,
                },
                sort_keys=True,
            )
        )

    @app.command("reproduce-study")
    def reproduce_study_command(
        directory: Path,
        expected_sha256: str | None = typer.Option(None),
        output: Path | None = typer.Option(None),
    ) -> None:
        """Regenerate metrics/tables from captured study decisions; never rerun ETL."""
        from equiframe_benchmark.io import save_document
        from equiframe_benchmark.study_bundle import reproduce_study_bundle

        try:
            result = reproduce_study_bundle(directory, expected_sha256=expected_sha256)
            if output is not None:
                save_document(result, output)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        typer.echo(result.model_dump_json())
        if result.status == "different":
            raise typer.Exit(code=1)
