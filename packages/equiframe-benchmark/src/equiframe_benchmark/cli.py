"""Benchmark commands keep experimental labels outside the operational library."""

import importlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import typer
from equiframe._cli_support import exit_with_failure

from equiframe_benchmark.commands import register as _register_delivery
from equiframe_benchmark.commands_scale import register as _register_scale
from equiframe_benchmark.commands_step10 import register as _register_step10
from equiframe_benchmark.commands_v2 import register_v2 as _register_v2
from equiframe_benchmark.io import load_document, save_document
from equiframe_benchmark.models import Catalog, SplitManifest
from equiframe_benchmark.splits import dependency_groups, make_splits, split_counts, validate_splits

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)


def _failure(error: Exception, *, input_validation: bool = True) -> None:
    invalid = input_validation and isinstance(error, ValueError)
    exit_with_failure(
        error,
        code="invalid_input" if invalid else "operation_failed",
        exit_code=2 if invalid else 3,
        input_validation=input_validation,
    )


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


def _factory(reference: str) -> Callable[[], object]:
    from typing import cast

    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", reference):
        raise ValueError("explicit module:factory reference is required")
    module, name = reference.split(":")
    factory = getattr(importlib.import_module(module), name)
    if not callable(factory):
        raise ValueError("registered factory must be callable")
    return cast(Callable[[], object], factory)


@app.command("integrate")
def integrate_command(
    spec: Path,
    snapshot_id: str = typer.Option(...),
    client: str = typer.Option(...),
    registry: str = typer.Option(...),
    output: Path = typer.Option(Path("equiframe-integration")),
    expected: Path | None = typer.Option(None),
    bundle: Path | None = typer.Option(None),
) -> None:
    """Consume a pinned snapshot through explicitly supplied trusted client/code."""
    from typing import cast

    import equiframe as ef
    from equiframe.evidence import load_json

    from equiframe_benchmark.integration import IntegrationSpec, run_integration
    from equiframe_benchmark.snapshot import SnapshotClient, SnapshotDataSource

    try:
        configuration = load_json(IntegrationSpec, spec)
        detector = load_json(ef.DetectorBundle, bundle) if bundle else None
        registered = _factory(registry)()
        if not isinstance(registered, ef.TransformationRegistry):
            raise ValueError("registry factory must return a TransformationRegistry")
        transport = _factory(client)()
        if not all(
            callable(getattr(transport, name, None))
            for name in ("get_snapshot", "download_artifact")
        ):
            raise ValueError("client factory must expose the snapshot client protocol")
        source = SnapshotDataSource(
            snapshot_id,
            client=cast(SnapshotClient, transport),
            expected_domain_schema_revision=configuration.domain_schema_revision,
            table_names=tuple(
                table.name for table in configuration.pipelines[0].execution.contract.inputs
            ),
        )
        result = run_integration(
            configuration,
            source=source,
            registry=registered,
            detector_bundle=detector,
            expected=expected,
            work_dir=output,
        )
    except Exception as error:
        _failure(error)
        return
    typer.echo(
        json.dumps(
            {
                "integration_id": result.integration_id,
                "complete": result.complete,
                "inputs_verified": result.inputs_verified,
                "scientific_equivalence_confirmed": False,
            },
            sort_keys=True,
        )
    )
    raise typer.Exit(code=result.exit_code)


@app.command("verify-integration")
def verify_integration_command(directory: Path) -> None:
    """Verify the existing receipt and evidence without contacting the service."""
    from equiframe_benchmark.integration import read_integration

    try:
        result = read_integration(directory)
    except Exception as error:
        _failure(error, input_validation=False)
        return
    typer.echo(
        json.dumps(
            {
                "integration_id": result.integration_id,
                "evidence_verified": True,
                "complete": result.complete,
            },
            sort_keys=True,
        )
    )


_register_scale(app)
_register_step10(app)
_register_v2(app)
_register_delivery(app)


def main() -> None:
    app()
