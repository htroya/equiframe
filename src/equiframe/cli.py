"""Operational CLI delegates to the same APIs used by scripts and notebooks."""

import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from typing import Literal, cast

import typer

from equiframe._cli_support import exit_with_failure, write_failure
from equiframe._doctor import Extra, diagnose, diagnostic_text
from equiframe._first_use import Case, Role, run_demo
from equiframe.assertion_types import EquivalencePolicy
from equiframe.assertions import equivalence_decision
from equiframe.bundle import export_bundle, import_bundle, inspect_bundle
from equiframe.comparison import compare
from equiframe.comparison_types import ComparisonSpec
from equiframe.datasets import (
    DatasetChoiceRequired,
    DatasetFormat,
    DatasetReadError,
    DatasetReadOptions,
    DatasetResult,
    DatasetTarget,
    convert_dataset,
    load_dataset,
)
from equiframe.detectors import read_detector_bundle
from equiframe.eda.cli import app as eda_app
from equiframe.errors import (
    CapabilityError,
    ContractIOError,
    ContractValidationError,
)
from equiframe.evidence import inspect_evidence, load_json, read_pipeline
from equiframe.ingestion import IngestionSpec, ingest_file
from equiframe.migration import (
    MigrationRequest,
    MigrationSpec,
    check_migration,
    migrate,
    migration_summary,
    read_migration,
)
from equiframe.pipeline import run_pipeline
from equiframe.pipeline_types import PipelineRequest
from equiframe.reduction import ReductionObservation, ReductionOptions, reduce_case
from equiframe.registry import TransformationRegistry
from equiframe.reporting import pipeline_summary, write_report
from equiframe.serialization import contract_fingerprint, read_contract
from equiframe.tables import ArrowInput, LocalDataSource, read_table
from equiframe.verification_request import VerificationRequest
from equiframe.verify import read_verification, verification_summary, verify, verify_migration
from equiframe.workflow import read_workflow, run_workflow
from equiframe.workflow_request import WorkflowRequest

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)
contract_app = typer.Typer(no_args_is_help=True)
app.add_typer(contract_app, name="contract", help="Validate semantic contract metadata.")
evidence_app = typer.Typer(no_args_is_help=True)
app.add_typer(evidence_app, name="evidence", help="Verify final or interrupted evidence.")
migration_app = typer.Typer(no_args_is_help=True)
app.add_typer(migration_app, name="migration", help="Compile, migrate and compare native ETL.")
verify_app = typer.Typer(no_args_is_help=True)
app.add_typer(verify_app, name="verify", help="Inspect semantic dimensions without executing ETL.")
bundle_app = typer.Typer(no_args_is_help=True)
app.add_typer(bundle_app, name="bundle", help="Export, import and verify portable evidence.")
ingestion_app = typer.Typer(no_args_is_help=True)
app.add_typer(ingestion_app, name="ingestion", help="Parse explicit CSV/JSON/JSONL contracts.")
dataset_app = typer.Typer(no_args_is_help=True)
app.add_typer(
    dataset_app,
    name="dataset",
    help="Discover local files, load Pandas and convert to Polars or DuckDB.",
)
workflow_app = typer.Typer(no_args_is_help=True)
app.add_typer(workflow_app, name="workflow", help="Run dependent native ETL checkpoints.")
app.add_typer(
    eda_app, name="eda", help="Optional independent dataset diagnostics; no approval gate."
)


@app.command("doctor")
def doctor_command(
    extra: Extra = typer.Option(Extra.base, help="Check only the dependencies your task needs."),
    json_output: bool = typer.Option(False, "--json", help="Print a machine-readable diagnosis."),
) -> None:
    """Check local metadata without imports, installs or network. Exit 0 ready, 3 unavailable."""
    try:
        result = diagnose(extra)
    except Exception as error:
        _failure(error)
        return
    typer.echo(json.dumps(result, sort_keys=True) if json_output else diagnostic_text(result))
    raise typer.Exit(code=0 if result["ready_metadata"] else 3)


@app.command("demo")
def demo_command(
    role: Role = typer.Option(..., help="Choose a synthetic SQL or data-preparation exercise."),
    case: Case = typer.Option(Case.good, help="Exercise acceptance, difference or a row limit."),
    output: Path = typer.Option(..., help="New private directory; existing evidence is preserved."),
) -> None:
    """Save a role diagnosis before the gate. Exit 0 accepted, 1 different, 3 unavailable."""
    try:
        result = run_demo(role, case, output)
    except Exception as error:
        _failure(error)
        return
    typer.echo(result["synthetic_detail"])
    typer.echo("Report HTML: " + result["report_html"])
    typer.echo("Synthetic detail HTML: " + result["synthetic_detail_html"])
    typer.echo(
        json.dumps({key: result[key] for key in ("role", "case", "state", "complete", "accepted")})
    )
    raise typer.Exit(code=0 if result["accepted"] else 1 if result["state"] == "different" else 3)


@ingestion_app.command("run")
def ingestion_run(
    spec: Path, source: Path, output: Path = typer.Option(Path("equiframe-runs"))
) -> None:
    """Preserve and ingest a file. Exit 0 complete, 1 quarantine/rejected, 2 invalid, 3 I/O."""
    try:
        result = ingest_file(source, spec=load_json(IngestionSpec, spec), work_dir=output)
    except Exception as error:
        _failure(error)
        return
    typer.echo(result.model_dump_json())
    raise typer.Exit(code=0 if result.state == "completed" else 1)


def _dataset_load_interactive(source: Path, options: DatasetReadOptions) -> DatasetResult:
    """Resolve only an explicit structural choice, with at most eight prompts."""
    for _ in range(8):
        try:
            return load_dataset(source, options=options)
        except DatasetChoiceRequired as error:
            if not sys.stdin.isatty():
                raise
            typer.echo(str(error))
            choices = list(error.choices)
            for index, choice in enumerate(choices, start=1):
                typer.echo(f"{index}: {json.dumps(choice, ensure_ascii=True)}")
            selected = typer.prompt("Seleccione el número", type=int)
            if selected < 1 or selected > len(choices):
                raise DatasetReadError("Select one of the listed choice numbers.") from None
            options = replace(options, **{error.option: choices[selected - 1]})
    raise DatasetReadError("Too many unresolved input choices; pass explicit dataset options.")


@dataset_app.command("load")
def dataset_load(
    source: Path,
    target: str | None = typer.Option(None, help="pandas, polars or duckdb; omitted: prompt."),
    output: Path | None = typer.Option(None, help="Optional new .parquet destination."),
    file_format: str | None = typer.Option(None, "--format", help="Override file extension."),
    sheet: str | None = typer.Option(None, help="Excel sheet; prompted when ambiguous."),
    records_path: str | None = typer.Option(None, help="JSON Pointer or XML element path."),
    delimiter: str | None = typer.Option(None, help="Delimiter; use tab for a tabulation."),
    header: bool = typer.Option(True, "--header/--no-header"),
    text_mode: str = typer.Option("auto", help="TXT: auto, lines or delimited."),
    infer_types: bool = typer.Option(True, "--infer-types/--keep-text"),
    encoding: str = typer.Option("utf-8-sig"),
    max_bytes: int = typer.Option(128 * 1024 * 1024, min=1),
    max_rows: int = typer.Option(1_000_000, min=1),
) -> None:
    """Load a file into Pandas, then select the destination in this same command.

    The JSON summary contains column names/types/counts, not sample values.
    Without --output the converted object exists only during this command.
    Python users receive the DataFrame/relation directly from load_dataset.
    """
    loaded = None
    converted = None
    try:
        if target is not None and target.lower() not in ("pandas", "polars", "duckdb"):
            raise DatasetReadError("--target must be pandas, polars or duckdb.")
        if target is None and not sys.stdin.isatty():
            raise DatasetReadError("Use --target pandas|polars|duckdb for noninteractive input.")
        options = DatasetReadOptions(
            format=cast(DatasetFormat | None, file_format),
            sheet=sheet,
            records_path=records_path,
            delimiter="\t" if delimiter == "tab" else delimiter,
            header=header,
            text_mode=cast(Literal["auto", "lines", "delimited"], text_mode),
            infer_text_types=infer_types,
            encoding=encoding,
            max_bytes=max_bytes,
            max_rows=max_rows,
        )
        loaded = _dataset_load_interactive(source, options)
        if target is None:
            typer.echo(json.dumps(loaded.info.to_dict(), ensure_ascii=True, default=str), err=True)
            target = (
                typer.prompt(
                    "¿A qué motor quiere migrar desde Pandas? pandas / polars / duckdb",
                    default="pandas",
                )
                .strip()
                .lower()
            )
        converted = convert_dataset(loaded, target=cast(DatasetTarget, target.lower()))
        if output is not None:
            converted.to_parquet(output)
        typer.echo(json.dumps(converted.info.to_dict(), ensure_ascii=True, default=str))
        typer.echo(
            json.dumps(
                {
                    "source_engine": "pandas",
                    "target_engine": converted.target,
                    "rows": converted.info.rows,
                    "saved": output is not None,
                    "output_format": "parquet" if output is not None else None,
                    "semantic_comparison_performed": False,
                }
            )
        )
    except Exception as error:
        _failure(error)
    finally:
        if converted is not None:
            converted.close()
        if loaded is not None:
            loaded.close()


@dataset_app.command("inspect")
def dataset_inspect(
    source: Path,
    file_format: str | None = typer.Option(None, "--format"),
    sheet: str | None = typer.Option(None),
    records_path: str | None = typer.Option(None),
    delimiter: str | None = typer.Option(None),
    header: bool = typer.Option(True, "--header/--no-header"),
    encoding: str = typer.Option("utf-8-sig"),
) -> None:
    """Show complete bounded dataset structure without converting to another engine."""
    result = None
    try:
        options = DatasetReadOptions(
            format=cast(DatasetFormat | None, file_format),
            sheet=sheet,
            records_path=records_path,
            delimiter="\t" if delimiter == "tab" else delimiter,
            header=header,
            encoding=encoding,
        )
        result = _dataset_load_interactive(source, options)
        typer.echo(json.dumps(result.info.to_dict(), ensure_ascii=True, default=str))
    except Exception as error:
        _failure(error)
    finally:
        if result is not None:
            result.close()


@workflow_app.command("validate")
def workflow_validate(request: Path) -> None:
    """Validate bindings and both native compilers without reading inputs. Exit 0/2/3."""
    try:
        document = load_json(WorkflowRequest, request)
        checks = tuple(
            check for stage in document.spec.stages for check in check_migration(stage.migration)
        )
    except Exception as error:
        _failure(error)
        return
    typer.echo(
        json.dumps(
            {"compilation_only": True, "checks": [c.model_dump(mode="json") for c in checks]}
        )
    )
    raise typer.Exit(code=0 if all(c.supported for c in checks) else 2)


@workflow_app.command("run")
def workflow_run(request: Path, output: Path = typer.Option(Path("equiframe-runs"))) -> None:
    """Execute native migration checkpoints over fixed inputs. Exit 0/1/2/3."""
    try:
        document = load_json(WorkflowRequest, request)
        result = run_workflow(
            document.spec,
            source=LocalDataSource({item.name: item.artifact for item in document.inputs}),
            expected={item.stage_id: item.artifact for item in document.expected},
            work_dir=output,
        )
    except Exception as error:
        _failure(error)
        return
    typer.echo(result.model_dump_json())
    raise typer.Exit(code=result.exit_code)


@workflow_app.command("inspect")
def workflow_inspect(directory: Path) -> None:
    """Verify recorded ETL evidence without execution. Exit 0 intact, 3 corrupt."""
    try:
        result = read_workflow(directory)
    except Exception as error:
        _failure(error, input_validation=False)
        return
    typer.echo(result.model_dump_json())


@verify_app.command("validate")
def verification_validate(request: Path) -> None:
    """Validate data-only request metadata; does not inspect artifact bytes. Exit 0/2/3."""
    try:
        document = load_json(VerificationRequest, request)
    except Exception as error:
        _failure(error)
        return
    typer.echo(
        json.dumps(
            {"metadata_valid": True, "contract_sha256": contract_fingerprint(document.contract)}
        )
    )


@verify_app.command("run")
def verification_run(request: Path, output: Path = typer.Option(Path("equiframe-runs"))) -> None:
    """Verify one or more existing artifacts. Exit 0 passed, 1 failed, 2 invalid, 3 unavailable."""
    try:
        document = load_json(VerificationRequest, request)
        result = verify(
            {item.name: item.artifact for item in document.outputs},
            contract=document.contract,
            expected=document.expected,
            provenance=document.provenance,
            reviews=document.reviews,
            request_review=document.request_review,
            require_expected=document.require_expected,
            require_rules=document.require_rules,
            snapshots={item.name: item.artifact for item in document.snapshots},
            plan_sha256=document.plan_sha256,
            policy=document.policy,
            options=document.options,
            work_dir=output,
        )
    except Exception as error:
        _failure(error)
        return
    typer.echo(json.dumps(verification_summary(result), sort_keys=True))
    raise typer.Exit(code=result.exit_code)


@verify_app.command("migration")
def verification_migration(
    directory: Path, output: Path = typer.Option(Path("equiframe-runs"))
) -> None:
    """Verify outputs of an existing migration. Exit 0/1/2/3; never reruns engines."""
    try:
        result = verify_migration(directory, work_dir=output)
    except Exception as error:
        _failure(error)
        return
    typer.echo(json.dumps(verification_summary(result), sort_keys=True))
    raise typer.Exit(code=result.exit_code)


@verify_app.command("inspect")
def verification_inspect(directory: Path) -> None:
    """Verify evidence integrity and report its semantic states. Exit 0 intact, 3 corrupt."""
    try:
        result = read_verification(directory)
    except Exception as error:
        _failure(error, input_validation=False)
        return
    typer.echo(
        json.dumps({**verification_summary(result), "integrity_verified": True}, sort_keys=True)
    )


@bundle_app.command("export")
def bundle_export(source: Path, destination: Path) -> None:
    """Export a finalized migration, verification or workflow. Exit 0/2/3."""
    try:
        result = export_bundle(source, destination)
    except Exception as error:
        _failure(error)
        return
    typer.echo(result.model_dump_json())


@bundle_app.command("import")
def bundle_import(source: Path, destination: Path, sha256: str | None = typer.Option(None)) -> None:
    """Copy a portable bundle and verify it again without ETL. Exit 0/2/3."""
    try:
        result = import_bundle(source, destination, expected_sha256=sha256)
    except Exception as error:
        _failure(error)
        return
    typer.echo(result.model_dump_json())


@bundle_app.command("verify")
def bundle_verify(directory: Path, sha256: str | None = typer.Option(None)) -> None:
    """Verify closed inventory and semantic receipts. Exit 0 intact, 3 corrupt."""
    try:
        result = inspect_bundle(directory, expected_sha256=sha256)
    except Exception as error:
        _failure(error, input_validation=False)
        return
    typer.echo(json.dumps(result, sort_keys=True))


@migration_app.command("validate")
def migration_validate(spec: Path) -> None:
    """Validate IR/contract support for both engines without executing or loading inputs."""
    try:
        document = load_json(MigrationSpec, spec)
        checks = check_migration(document)
    except CapabilityError as error:
        exit_with_failure(error, code="unsupported_capability", exit_code=2)
    except Exception as error:
        _failure(error)
        return
    typer.echo(
        json.dumps(
            {
                "compilation_only": True,
                "checks": [c.model_dump(mode="json") for c in checks],
            },
            sort_keys=True,
        )
    )
    raise typer.Exit(code=0 if all(c.supported for c in checks) else 2)


@migration_app.command("run")
def migration_run(
    request: Path,
    output: Path = typer.Option(Path("equiframe-runs")),
    bundle: Path | None = typer.Option(None),
) -> None:
    """Execute two native plans over fixed inputs; optionally compare a supplied expected."""
    try:
        document = load_json(MigrationRequest, request)
        result = migrate(
            document.spec,
            source=LocalDataSource({i.name: i.artifact for i in document.inputs}),
            expected=document.expected,
            work_dir=output,
            detector_bundle=read_detector_bundle(bundle) if bundle else None,
        )
    except Exception as error:
        _failure(error)
        return
    typer.echo(json.dumps(migration_summary(result), sort_keys=True))
    raise typer.Exit(code=result.exit_code)


@migration_app.command("verify")
def migration_verify(directory: Path) -> None:
    """Verify bundle integrity without ETL; exit 0 does not certify correctness."""
    try:
        result = read_migration(directory)
    except Exception as error:
        _failure(error, input_validation=False)
        return
    typer.echo(
        json.dumps({**migration_summary(result), "integrity_verified": True}, sort_keys=True)
    )


@contract_app.command("validate")
def validate(path: Path) -> None:
    """Validate a contract JSON file. Exit 0: valid; 2: invalid; 3: I/O failure."""
    try:
        contract = read_contract(path)
    except ContractValidationError as exc:
        _failure(exc)
    except ContractIOError as exc:
        _failure(exc, input_validation=False)
    typer.echo(f"Valid contract: {contract.contract_id} revision {contract.revision}")
    typer.echo("SHA-256 metadata: " + contract_fingerprint(contract))


def _trusted_callable(reference: str) -> Callable[..., object]:
    """Explicit user-selected importable code; never a registration embedded in JSON."""
    module, separator, member = reference.partition(":")
    if (
        not separator
        or not member.isidentifier()
        or not all(part.isidentifier() for part in module.split("."))
    ):
        raise ValueError("expected installed.module:callable")
    target = getattr(import_module(module), member)
    if not callable(target):
        raise ValueError("trusted registration must be callable")
    return cast(Callable[..., object], target)


def _failure(error: Exception, *, input_validation: bool = True) -> None:
    invalid = input_validation and isinstance(
        error, (ValueError, ContractValidationError, DatasetReadError)
    )
    if isinstance(error, DatasetReadError):
        write_failure(
            error,
            code="invalid_input" if invalid else "operation_failed",
            input_validation=input_validation,
        )
        typer.echo(str(error), err=True)
        if isinstance(error, DatasetChoiceRequired):
            typer.echo(
                json.dumps({"required_option": error.option, "choices": error.choices}),
                err=True,
            )
        raise typer.Exit(code=2 if invalid else 3) from None
    exit_with_failure(
        error,
        code="invalid_input" if invalid else "operation_failed",
        exit_code=2 if invalid else 3,
        input_validation=input_validation,
    )


@app.command("run")
def run_command(
    request: Path,
    registry: str = typer.Option(..., help="Trusted installed.module:factory."),
    output: Path = typer.Option(Path("equiframe-runs")),
    bundle: Path | None = typer.Option(None),
) -> None:
    """Execute R/profile/M/B/H and optional comparison. Exit 0/1/2/3."""
    try:
        document = load_json(PipelineRequest, request)
        registered = _trusted_callable(registry)()
        if not isinstance(registered, TransformationRegistry):
            raise ValueError("factory must return TransformationRegistry")
        result = run_pipeline(
            document.spec,
            source=LocalDataSource({item.name: item.artifact for item in document.inputs}),
            registry=registered,
            work_dir=output,
            comparison=document.comparison,
            detector_bundle=read_detector_bundle(bundle) if bundle else None,
        )
    except Exception as error:
        _failure(error)
        return
    typer.echo(json.dumps(pipeline_summary(result), sort_keys=True))
    raise typer.Exit(code=result.exit_code)


@app.command("compare")
def compare_command(
    spec: Path,
    left: Path,
    right: Path,
    expected: bool = typer.Option(False),
    output: Path = typer.Option(Path("equiframe-runs")),
) -> None:
    """Compare materialized content. Exit 0 equal, 1 different, 2 invalid, 3 unavailable."""
    try:
        document = load_json(ComparisonSpec, spec)
        result = compare(
            left,
            right,
            contract=document.contract,
            policy=document.policy,
            reference="expected" if expected else "peer",
            work_dir=output,
        )
    except Exception as error:
        _failure(error)
        return
    # A producer failure or malformed result is unavailable, never a verdict. Keep
    # this separate from configuration validation so it cannot become exit 2.
    try:
        decision = equivalence_decision(
            result,
            policy=EquivalencePolicy(require_persisted_evidence=True),
            evidence_root=output,
        )
        summary = {
            "comparison_id": result.comparison_id,
            "state": decision.state,
            "complete": decision.complete,
            "accepted": decision.accepted,
            "code": decision.code,
            "evidence_status": decision.evidence_status,
        }
    except Exception as error:
        _failure(error, input_validation=False)
        return
    typer.echo(json.dumps(summary, sort_keys=True))
    if decision.accepted:
        raise typer.Exit(code=0)
    # These diagnostics are deliberately fixed text. Diagnostic messages, column
    # names, producer exception text, and raw values belong in private evidence.
    if decision.state == "different" and decision.complete:
        typer.echo(
            "comparison_different: complete comparison found differences; "
            "inspect a redacted comparison report before sharing evidence",
            err=True,
        )
        raise typer.Exit(code=1)
    if decision.state == "equivalent":
        typer.echo(
            "comparison_unavailable: finalized comparison evidence could not be verified; "
            "restore the evidence or rerun before accepting equivalence",
            err=True,
        )
        raise typer.Exit(code=3)
    # Traversal can be complete while an invalid expected reference prevents a verdict.
    typer.echo(
        "comparison_not_evaluable: equivalence was not established; "
        "check the declared contract, input availability, and comparison limits",
        err=True,
    )
    raise typer.Exit(code=3)


@app.command("report")
def report_command(manifest: Path, output: Path = typer.Option(...)) -> None:
    """Verify evidence before generating a new JSON/HTML report directory."""
    try:
        result = read_pipeline(manifest)
        write_report(result, output)
    except Exception as error:
        _failure(error, input_validation=False)
        return
    typer.echo(json.dumps({"pipeline_id": result.pipeline_id, "report_created": True}))


@evidence_app.command("verify")
def verify_command(directory: Path) -> None:
    """Verify all manifest hashes and event-chain links; exit 3 on interrupted evidence."""
    try:
        summary = inspect_evidence(directory)
    except Exception as error:
        _failure(error, input_validation=False)
        return
    typer.echo(json.dumps(summary, sort_keys=True))
    raise typer.Exit(code=0 if summary["finalized"] else 3)


@app.command("reduce")
def reduce_command(
    request: Path,
    predicate: str = typer.Option(..., help="Trusted installed.module:predicate."),
    predicate_version: str = typer.Option(...),
    failure_signature: str = typer.Option(...),
    output: Path = typer.Option(Path("equiframe-runs")),
    max_evaluations: int = typer.Option(100),
    timeout_seconds: float = typer.Option(60.0),
    confirmations: int = typer.Option(2),
) -> None:
    """Reduce rows while an explicit predicate verifies preconditions and the target failure."""
    try:
        document = load_json(PipelineRequest, request)
        callback = cast(
            Callable[[Mapping[str, ArrowInput]], ReductionObservation], _trusted_callable(predicate)
        )
        result = reduce_case(
            {item.name: ArrowInput(read_table(item.artifact)) for item in document.inputs},
            predicate=callback,
            predicate_version=predicate_version,
            failure_signature=failure_signature,
            work_dir=output,
            options=ReductionOptions(
                max_evaluations=max_evaluations,
                timeout_seconds=timeout_seconds,
                confirmations=confirmations,
            ),
        )
    except Exception as error:
        _failure(error)
        return
    typer.echo(
        json.dumps(
            {
                "reduction_id": result.reduction_id,
                "status": result.status,
                "evaluations": result.evaluations,
                "minimality": result.minimality,
                "global_minimum_claimed": False,
            },
            sort_keys=True,
        )
    )
    raise typer.Exit(code=0 if result.status in ("reduced", "unchanged") else 3)


def main() -> None:
    app()
