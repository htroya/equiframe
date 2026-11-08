"""Explicit experimental commands; persisted JSON never selects executable code."""

import json
from pathlib import Path

import typer


def register_v2(app: typer.Typer) -> None:
    from equiframe_benchmark.cli import _factory, _failure

    @app.command("freeze-v2")
    def freeze_command(definition: Path, output: Path = typer.Option(...)) -> None:
        """Audit and seal a declared pilot/final protocol before test execution."""
        from equiframe_benchmark.freeze_v2 import (
            FreezeDefinitionV2,
            audit_freeze_v2,
            create_freeze_v2,
        )
        from equiframe_benchmark.io import load_document, save_document

        try:
            configuration = load_document(FreezeDefinitionV2, definition)
            audit = audit_freeze_v2(configuration)
            if not audit.ready:
                typer.echo(
                    json.dumps(
                        {
                            "mode": configuration.mode,
                            "technical_ready": audit.technical_ready,
                            "scientific_ready": audit.scientific_ready,
                            "blockers": audit.blockers,
                            "sealed": False,
                        },
                        sort_keys=True,
                    )
                )
                raise typer.Exit(code=2)
            manifest = create_freeze_v2(configuration)
            save_document(manifest, output)
        except typer.Exit:
            raise
        except Exception as error:
            _failure(error)
            return
        typer.echo(
            json.dumps(
                {
                    "mode": manifest.definition.mode,
                    "technical_ready": manifest.audit.technical_ready,
                    "scientific_ready": manifest.audit.scientific_ready,
                    "blockers": manifest.audit.blockers,
                    "sealed": True,
                },
                sort_keys=True,
            )
        )

    @app.command("verify-freeze-v2")
    def verify_freeze_command(path: Path) -> None:
        from equiframe_benchmark.freeze_v2 import read_freeze_v2

        try:
            manifest = read_freeze_v2(path)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        typer.echo(
            json.dumps(
                {
                    "evidence_verified": True,
                    "mode": manifest.definition.mode,
                    "technical_ready": manifest.audit.technical_ready,
                    "scientific_ready": manifest.audit.scientific_ready,
                    "blockers": manifest.audit.blockers,
                },
                sort_keys=True,
            )
        )

    @app.command("run-study-v2")
    def study_command(
        freeze: Path,
        registry: str = typer.Option(...),
        output: Path = typer.Option(Path("equiframe-studies")),
    ) -> None:
        """Run sealed cases with an explicitly trusted registry, without fitting."""
        import equiframe as ef

        from equiframe_benchmark.freeze_v2 import read_freeze_v2
        from equiframe_benchmark.study_v2 import read_study_v2, run_study_v2

        try:
            manifest = read_freeze_v2(freeze)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        try:
            registered = _factory(registry)()
            if not isinstance(registered, ef.TransformationRegistry):
                raise ValueError("registry factory must return a TransformationRegistry")
            result = run_study_v2(manifest, registry=registered, work_dir=output)
            if read_study_v2(output.resolve() / result.study_id) != result:
                raise ValueError("published study differs from its verified receipt")
        except Exception as error:
            _failure(error)
            return
        typer.echo(
            json.dumps(
                {
                    "study_id": result.study_id,
                    "scientific": result.scientific,
                    "complete": result.complete,
                    "cases": len(result.evaluation.records),
                    "evidence_verified": True,
                },
                sort_keys=True,
            )
        )
        raise typer.Exit(code=result.exit_code)

    @app.command("verify-study-v2")
    def verify_study_command(directory: Path) -> None:
        from equiframe_benchmark.study_v2 import read_study_v2

        try:
            result = read_study_v2(directory)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        typer.echo(
            json.dumps(
                {
                    "study_id": result.study_id,
                    "scientific": result.scientific,
                    "complete": result.complete,
                    "cases": len(result.evaluation.records),
                    "evidence_verified": True,
                },
                sort_keys=True,
            )
        )

    @app.command("evaluate-v2")
    def evaluate_command(study: Path, output: Path = typer.Option(...)) -> None:
        """Regenerate a verified study's report from its complete captured records."""
        from equiframe_benchmark.evaluation_v2 import evaluate_records_v2
        from equiframe_benchmark.io import save_document
        from equiframe_benchmark.study_v2 import read_study_v2

        try:
            captured = read_study_v2(study).evaluation
        except Exception as error:
            _failure(error, input_validation=False)
            return
        try:
            report = evaluate_records_v2(captured.records, config=captured.config)
            if report != captured:
                raise ValueError("evaluation must reproduce the captured report")
            save_document(report, output)
        except Exception as error:
            _failure(error)
            return
        typer.echo(json.dumps({"scientific": report.scientific, "regenerated": True}))

    @app.command("tables-v2")
    def tables_command(study: Path, output: Path = typer.Option(...)) -> None:
        from equiframe_benchmark.study_v2 import read_study_v2
        from equiframe_benchmark.tables_v2 import write_tables_v2

        try:
            report = read_study_v2(study).evaluation
        except Exception as error:
            _failure(error, input_validation=False)
            return
        try:
            receipt = write_tables_v2(report, output)
        except Exception as error:
            _failure(error)
            return
        typer.echo(json.dumps({"tables": len(receipt.tables), "scientific": report.scientific}))

    @app.command("bundle-study-v2")
    def bundle_command(study: Path, output: Path = typer.Option(...)) -> None:
        """Copy the V2 captured study and original sources without rewriting provenance."""
        from equiframe_benchmark.study_bundle_v2 import bundle_study_v2

        try:
            result = bundle_study_v2(study, output=output)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        typer.echo(json.dumps({"protocol_version": "2.0", "bundle_id": result.bundle_id}))

    @app.command("reproduce-study-v2")
    def reproduce_command(directory: Path) -> None:
        """Regenerate paired tables from captured decisions, without executing native ETL."""
        from equiframe_benchmark.study_bundle_v2 import reproduce_study_bundle_v2

        try:
            result = reproduce_study_bundle_v2(directory)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        typer.echo(json.dumps({"protocol_version": "2.0", "status": result.status}))
        raise typer.Exit(code=0 if result.status == "reproduced" else 1)
