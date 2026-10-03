"""Explicit experimental commands; persisted JSON never selects executable code."""

import json
from pathlib import Path

import typer


def register(app: typer.Typer) -> None:
    from equiframe_benchmark.cli import _factory, _failure

    @app.command("freeze")
    def freeze_command(definition: Path, output: Path = typer.Option(...)) -> None:
        """Audit and seal a declared pilot/final protocol before test execution."""
        from equiframe_benchmark.freeze import FreezeDefinition, audit_freeze, create_freeze
        from equiframe_benchmark.io import load_document, save_document

        try:
            configuration = load_document(FreezeDefinition, definition)
            audit = audit_freeze(configuration)
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
            manifest = create_freeze(configuration)
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

    @app.command("verify-freeze")
    def verify_freeze_command(path: Path) -> None:
        from equiframe_benchmark.freeze import read_freeze

        try:
            manifest = read_freeze(path)
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

    @app.command("run-study")
    def study_command(
        freeze: Path,
        registry: str = typer.Option(...),
        output: Path = typer.Option(Path("equiframe-studies")),
    ) -> None:
        """Run sealed cases with an explicitly trusted registry, without fitting."""
        import equiframe as ef

        from equiframe_benchmark.freeze import read_freeze
        from equiframe_benchmark.study import read_study, run_study

        try:
            manifest = read_freeze(freeze)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        try:
            registered = _factory(registry)()
            if not isinstance(registered, ef.TransformationRegistry):
                raise ValueError("registry factory must return a TransformationRegistry")
            result = run_study(manifest, registry=registered, work_dir=output)
            if read_study(output.resolve() / result.study_id) != result:
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

    @app.command("verify-study")
    def verify_study_command(directory: Path) -> None:
        from equiframe_benchmark.study import read_study

        try:
            result = read_study(directory)
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

    @app.command("evaluate")
    def evaluate_command(study: Path, output: Path = typer.Option(...)) -> None:
        """Regenerate a verified study's report from its complete captured records."""
        from equiframe_benchmark.evaluation import evaluate_records
        from equiframe_benchmark.io import save_document
        from equiframe_benchmark.study import read_study

        try:
            captured = read_study(study).evaluation
        except Exception as error:
            _failure(error, input_validation=False)
            return
        try:
            report = evaluate_records(captured.records, config=captured.config)
            if report != captured:
                raise ValueError("evaluation must reproduce the captured report")
            save_document(report, output)
        except Exception as error:
            _failure(error)
            return
        typer.echo(json.dumps({"scientific": report.scientific, "regenerated": True}))

    @app.command("tables")
    def tables_command(study: Path, output: Path = typer.Option(...)) -> None:
        from equiframe_benchmark.study import read_study
        from equiframe_benchmark.tables import write_tables

        try:
            report = read_study(study).evaluation
        except Exception as error:
            _failure(error, input_validation=False)
            return
        try:
            receipt = write_tables(report, output)
        except Exception as error:
            _failure(error)
            return
        typer.echo(json.dumps({"tables": len(receipt.tables), "scientific": report.scientific}))

    @app.command("costs")
    def costs_command(
        spec: Path,
        bundle: Path = typer.Option(...),
        output: Path = typer.Option(Path("equiframe-costs")),
    ) -> None:
        """Measure profile+M and comparison on previously captured artifacts."""
        import equiframe as ef

        from equiframe_benchmark.costs import CostSpec, ProfileMCostResult, measure_costs
        from equiframe_benchmark.io import load_document

        try:
            configuration = load_document(CostSpec, spec)
            detector = ef.read_detector_bundle(bundle)
            if ef.detector_fingerprint(detector) != configuration.detector_bundle_sha256:
                raise ValueError("costs require the declared frozen detector bundle")

            def profile_m(
                directory: Path, cancellation: ef.CancellationToken
            ) -> ProfileMCostResult:
                profile = ef.profile_execution(
                    configuration.execution,
                    spec=configuration.profile,
                    options=configuration.profile_options,
                    work_dir=directory,
                    cancellation=cancellation,
                )
                detection = (
                    ef.detect_component(detector, (profile.vector,), method="isolation_forest")
                    if profile.complete
                    else None
                )
                return ProfileMCostResult(profile=profile, detection=detection)

            def comparison(
                directory: Path, cancellation: ef.CancellationToken
            ) -> ef.ComparisonResult:
                return ef.compare(
                    configuration.execution,
                    configuration.reference,
                    contract=configuration.execution.plan.contract,
                    policy=configuration.comparison_policy,
                    reference=configuration.comparison_reference,
                    options=configuration.comparison_options,
                    work_dir=directory,
                    cancellation=cancellation,
                )

            result = measure_costs(
                configuration, profile_m=profile_m, comparison=comparison, work_dir=output
            )
        except Exception as error:
            _failure(error)
            return
        typer.echo(
            json.dumps(
                {
                    "cost_id": result.cost_id,
                    "complete": result.complete,
                    "scientific_h3_confirmed": False,
                },
                sort_keys=True,
            )
        )
        raise typer.Exit(code=0 if result.complete else 3)

    @app.command("verify-costs")
    def verify_costs_command(directory: Path) -> None:
        from equiframe_benchmark.costs import read_costs

        try:
            result = read_costs(directory)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        typer.echo(
            json.dumps(
                {
                    "cost_id": result.cost_id,
                    "complete": result.complete,
                    "evidence_verified": True,
                },
                sort_keys=True,
            )
        )

    @app.command("cost-table")
    def cost_table_command(directory: Path, output: Path = typer.Option(...)) -> None:
        from equiframe_benchmark.cost_table import write_cost_table

        try:
            write_cost_table(directory, output=output)
        except Exception as error:
            _failure(error, input_validation=False)
            return
        typer.echo(json.dumps({"observations": 12, "scientific_h3_confirmed": False}))
