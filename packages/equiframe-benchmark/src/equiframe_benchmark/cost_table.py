"""Raw warmup/measurement CSV from a verified cost receipt, with explicit units."""

import csv
import io
from pathlib import Path

from equiframe_benchmark.costs import read_costs


def write_cost_table(directory: Path, *, output: Path) -> None:
    """Keep all twelve observations, failures and missing resources; no aggregates."""
    result = read_costs(directory)
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(
        (
            "cost_id",
            "case_id",
            "phase",
            "repetition",
            "position",
            "method",
            "state",
            "resource_state",
            "wall_seconds",
            "cpu_seconds",
            "rss_baseline_bytes",
            "sampled_absolute_rss_peak_bytes",
            "sample_interval_seconds",
            "max_sample_gap_seconds",
            "cpu_method",
            "rss_method",
            "resource_scope",
            "issues",
        )
    )
    for observation in (*result.warmups, *result.observations):
        resources = observation.resources
        writer.writerow(
            (
                result.cost_id,
                result.spec.case_id,
                observation.phase,
                observation.repetition,
                observation.position,
                observation.method,
                observation.state,
                resources.state,
                resources.wall_seconds,
                resources.cpu_seconds,
                resources.rss_baseline_bytes,
                resources.sampled_rss_peak_bytes,
                resources.sample_interval_seconds,
                resources.max_sample_gap_seconds,
                resources.cpu_method,
                resources.rss_method,
                resources.scope,
                "|".join(i.code for i in (*observation.issues, *resources.issues)),
            )
        )
    with output.open("xb") as stream:
        stream.write(text.getvalue().encode("utf-8"))
