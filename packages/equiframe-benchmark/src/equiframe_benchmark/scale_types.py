"""Engineering cost protocol, separate from the frozen scientific paired protocol."""

from typing import Annotated, Literal

import equiframe as ef
from pydantic import Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.costs import ResourceMeasurement
from equiframe_benchmark.models import Digest, Document, Text

STAGES = (
    "capture",
    "snapshot",
    "transfer",
    "plan",
    "compare",
    "serialize",
    "persist",
    "render",
    "verify",
)
SCALE_SAMPLE_INTERVAL_SECONDS = 0.25


class ScaleSpec(Document):
    """Deterministic bounded synthetic integers/text/NULL, without detector labels."""

    case_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
    rows: Annotated[int, Field(ge=1, le=1_000_000)] = 1000
    width: Annotated[int, Field(ge=2, le=32)] = 2
    text_max_length: Annotated[int, Field(ge=1, le=1024)] = 32
    cardinality: Annotated[int, Field(ge=1, le=1_000_000)] = 1000
    distinct_rows: Annotated[int, Field(ge=1, le=1_000_000)] | None = None
    skew_percent: Annotated[int, Field(ge=0, le=100)] = 0
    null_every: Annotated[int, Field(ge=2)] | None = None
    difference_every: Annotated[int, Field(ge=1)] | None = None
    difference_last: bool = False
    alignment: Literal["keyed", "multiset"] = "multiset"
    repetitions: Annotated[int, Field(ge=2, le=10)] = 3
    batch_rows: Annotated[int, Field(ge=1, le=65_536)] = 4096
    timeout_seconds: Annotated[float, Field(gt=0, le=3600)] = 300.0
    rss_budget_bytes: Annotated[int, Field(ge=16 * 1024**2, le=8 * 1024**3)] = 1024**3
    disk_budget_bytes: Annotated[int, Field(ge=1024**2, le=8 * 1024**3)] = 2 * 1024**3
    comparison_options: ef.ComparisonOptions = ef.ComparisonOptions()
    run_baselines: bool = True
    concurrent_loads: Text = "not controlled; record other known workloads separately"

    @model_validator(mode="after")
    def valid_shape(self) -> Self:
        if self.distinct_rows is not None and self.distinct_rows > self.rows:
            raise ValueError("distinct_rows cannot exceed rows")
        if self.alignment == "keyed" and self.distinct_rows not in (None, self.rows):
            raise ValueError("keyed workload requires genuinely unique keys")
        # Safety admission is conservative, not a prediction or a hard quota.
        estimate = self.rows * self.width * (self.text_max_length + 128)
        if estimate > 8 * self.disk_budget_bytes:
            raise ValueError("synthetic workload is too large for the declared disk budget")
        return self

    @property
    def expected_state(self) -> Literal["equivalent", "different"]:
        return "different" if self.difference_last or self.difference_every else "equivalent"


class StageCost(Document):
    name: str
    wall_seconds: Annotated[float, Field(ge=0)]
    scope: Text


class BaselineCost(Document):
    method: Literal["pandas_assert", "duckdb_sql", "datacompy"]
    state: Literal["equivalent", "different", "not_available", "failed", "not_applicable"]
    wall_seconds: Annotated[float, Field(ge=0)] | None
    reason: Text
    service: Literal["verdict_only_no_complete_difference_evidence"] = (
        "verdict_only_no_complete_difference_evidence"
    )


class ScaleTrial(Document):
    case_sha256: Digest
    repetition: Annotated[int, Field(ge=0)]
    cache_state: Literal[
        "fresh_process_os_cache_uncontrolled", "warm_process_os_cache_uncontrolled"
    ]
    stages: tuple[StageCost, ...]
    end_to_end_seconds: Annotated[float, Field(ge=0)]
    resources: ResourceMeasurement
    comparison: ef.ComparisonResult
    verified_difference_records: Annotated[int, Field(ge=0)]
    evidence_bytes: Annotated[int, Field(ge=0)]
    evidence: tuple[ef.EvidenceFile, ...]
    baselines: tuple[BaselineCost, ...]

    @model_validator(mode="after")
    def complete_stage_order(self) -> Self:
        if tuple(stage.name for stage in self.stages) != STAGES:
            raise ValueError("trial requires the complete ordered measured pipeline")
        if sum(stage.wall_seconds for stage in self.stages) > self.end_to_end_seconds:
            raise ValueError("disjoint measured stages cannot exceed the full pipeline")
        if self.verified_difference_records != self.comparison.counts.difference_records:
            raise ValueError("verified evidence count must preserve the comparison count")
        if self.evidence_bytes != sum(item.size_bytes for item in self.evidence):
            raise ValueError("evidence size must preserve the measured inventory")
        if len({item.path for item in self.evidence}) != len(self.evidence):
            raise ValueError("evidence paths must be unique")
        if tuple(item.method for item in self.baselines) not in (
            (),
            ("pandas_assert", "duckdb_sql", "datacompy"),
        ):
            raise ValueError("baseline outcomes must retain all requested methods")
        return self


class ScaleWorkerCompletion(Document):
    environment: dict[str, str]
    case_sha256: Digest
    trial_files: tuple[ef.EvidenceFile, ...]
