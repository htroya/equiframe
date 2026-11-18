"""Installed-package example: native execution, complete evidence and bounded reduction.

Run with the duckdb extra. All data and failure predicates are synthetic.
"""

import argparse
from pathlib import Path

import pyarrow as pa

import equiframe as ef


def registry():
    result = ef.TransformationRegistry()
    result.register(ef.DuckDBTransformation("identity", "SELECT * FROM source", "synthetic.v1"))
    return result


def run(output: Path) -> None:
    contract = ef.read_contract(Path(__file__).with_name("duplicates_order.json"))
    table = pa.table({"id": ["0007"] * 4, "position": [0] * 4})
    # Use the declared fixture's schema and independent row expectations.
    print("Declared columns:", [c.name for c in contract.output.schema_spec.columns])
    spec = ef.PipelineSpec(
        execution=ef.ExecutionPlan(
            contract=contract, engine="duckdb", transformation_id="identity"
        ),
        profile=ef.ProfileSpec(
            family="duplicates_order",
            features=(
                ef.ProfileFeature(name="rows", metric="log_filas", table=contract.output.name),
            ),
        ),
    )
    result = ef.run_pipeline(
        spec,
        source=ef.LocalDataSource({contract.inputs[0].name: ef.ArrowInput(table)}),
        registry=registry(),
        comparison=ef.ArrowInput(table),
        work_dir=output,
    )
    assert result.complete and result.exit_code == 0, ef.pipeline_summary(result)
    assert ef.read_pipeline(output / result.pipeline_id) == result
    print("Pipeline:", result.pipeline_id, "exit", result.exit_code)

    def reproduce(tables):
        values = tables["source"].table["id"].to_pylist()
        return ef.ReductionObservation(
            preconditions="satisfied",
            failure_signature="duplicate.id" if len(set(values)) != len(values) else None,
        )

    reduced = ef.reduce_case(
        {"source": ef.ArrowInput(table)},
        predicate=reproduce,
        predicate_version="synthetic.duplicate.v1",
        failure_signature="duplicate.id",
        options=ef.ReductionOptions(max_evaluations=40),
        work_dir=output,
    )
    assert reduced.status == "reduced" and len(reduced.tables[0].retained_positions) == 2
    assert ef.read_reduction(output / reduced.reduction_id) == reduced
    print("Reduction:", reduced.reduction_id, reduced.minimality, "global minimum:", False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("equiframe-runs"))
    run(parser.parse_args().output)
