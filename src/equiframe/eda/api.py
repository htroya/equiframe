"""One execution path for Python/CLI, immutable snapshots and independent evidence."""

from __future__ import annotations

import csv
import hashlib
import importlib
import importlib.metadata
import os
import platform
import sys
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from equiframe import __version__
from equiframe._error_reporting import report_failure
from equiframe._report_io import _open_regular
from equiframe.errors import CapabilityError
from equiframe.evidence import canonical_bytes, load_json, parse_json, publish_json
from equiframe.execution_types import TableArtifact
from equiframe.local import local_path

from ._backend import Backend
from ._paths import manifest_member, ordinary_path
from .models import EdaConfig, EdaManifest, EdaResult, Source

LIMITS = (
    "Diagnostics only: no equivalence, independent correctness, fraud or DW publication decision.",
    "DuckDB memory controls buffer manager, not hard process RSS; temp cap covers DuckDB "
    "spill only.",
    "Input-byte/row/column/group caps and cancellation callbacks are cooperative; "
    "queries have interrupt timer.",
    "Snapshot copies, typed outputs and HTML consume additional disk "
    "outside DuckDB temporary-disk quota.",
    "Row references are zero-based ordinals of the fixed snapshot; no business uniqueness "
    "inferred.",
    "Raw NULL, NaN, empty and zero are distinct; missingness lost in an export is not "
    "reconstructed.",
    "Floating mean/stddev/histogram/visualization are approximate; "
    "monetary sums and discrete quantiles exact.",
    "Group budgets and unavailable outlier metrics remain explicit, never zero alerts.",
)


class _Unavailable(Exception):
    pass


class _Cancelled(Exception):
    pass


def _admit_arrow_schema(schema: Any) -> None:
    """Reject scalar transport loss before DuckDB rewrites source types."""
    types = importlib.import_module("pyarrow.types")
    for field in schema:
        dtype = field.type
        preserved = (
            types.is_null(dtype)
            or types.is_boolean(dtype)
            or types.is_integer(dtype)
            or (types.is_floating(dtype) and dtype.bit_width in (32, 64))
            or types.is_string(dtype)
            or types.is_large_string(dtype)
            or types.is_date32(dtype)
            or (types.is_timestamp(dtype) and dtype.unit != "ns" and dtype.tz is None)
            or (
                types.is_decimal(dtype)
                and dtype.precision <= 38
                and 0 <= dtype.scale <= dtype.precision
            )
        )
        if not preserved:
            raise CapabilityError(
                f"MVP raw Arrow type {dtype} in {field.name!r} requires a separate explicit "
                "projection; DuckDB/Python report transport is not faithful"
            )


def _sha(path: Path, checkpoint: Callable[[], None] | None = None) -> str:
    h = hashlib.sha256()
    with _open_regular(path) as stream:
        while block := stream.read(1024 * 1024):
            if checkpoint is not None:
                checkpoint()
            h.update(block)
    return h.hexdigest()


def _manifest(source: Source, path: Path, output: Path) -> dict[str, Any] | None:
    if source.manifest_path is None:
        return None
    manifest = ordinary_path(Path(source.manifest_path))
    if output.is_relative_to(manifest.parent):
        raise ValueError("EDA output must be outside the source delivery")
    if manifest.stat().st_size > 16 * 1024**2:
        raise ValueError("Source delivery manifest exceeds its byte budget")
    with _open_regular(manifest) as stream:
        payload = stream.read(16 * 1024**2 + 1)
    if len(payload) > 16 * 1024**2:
        raise ValueError("Source delivery manifest exceeds its byte budget")
    if hashlib.sha256(payload).hexdigest() != source.manifest_sha256:
        raise ValueError("source manifest SHA-256 mismatch")
    parsed = parse_json(payload)
    if not isinstance(parsed, dict):
        raise ValueError("Source delivery manifest must be an object")
    doc = parsed
    if doc.get("schema") != "equiframe.sercop-public-dataset-delivery.v1":
        raise ValueError("unsupported external delivery manifest version")
    records = doc.get("files")
    if not isinstance(records, list) or len(records) > 2000:
        raise ValueError("Invalid bounded source delivery inventory")
    matches = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid source inventory member")
        if manifest_member(manifest.parent, record.get("file")) == path:
            matches.append(record)
    if len(matches) != 1:
        raise ValueError("selected source is not a unique manifest member")
    return cast("dict[str, Any]", matches[0])


def analyze(
    source: Source,
    *,
    config: EdaConfig | None = None,
    output: Path,
    cancellation: Callable[[], bool] | None = None,
) -> EdaResult:
    """Profile one fixed local file; exclusive output directory, optional explicit conversions.

    Invalid metadata/output collisions fail before execution. Runtime failure,
    exhausted budget and cancellation have distinct persisted diagnostic states.
    """
    return _analyze(source, config=config, output=output, cancellation=cancellation)


def _analyze(
    source: Source,
    *,
    config: EdaConfig | None,
    output: Path,
    cancellation: Callable[[], bool] | None = None,
    evidence_links: tuple[dict[str, str], ...] = (),
    before_finalize: Callable[[], None] | None = None,
) -> EdaResult:
    source = Source.model_validate(source)
    config = EdaConfig.model_validate(config) if config is not None else EdaConfig()
    if cancellation is not None and not callable(cancellation):
        raise TypeError("cancellation requires a callable returning bool")
    output = ordinary_path(output, directory=True, allow_missing=True)
    path = ordinary_path(Path(source.path))
    if output.is_relative_to(path.parent):
        raise ValueError("output must be outside the source file directory")
    binding = _manifest(source, path, output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    run_id = "eda_" + uuid4().hex
    started = time.monotonic()
    limits = config.resources
    fingerprint = hashlib.sha256(canonical_bytes(config.model_dump(mode="json"))).hexdigest()
    publish_json(config, output / "config.json")
    publish_json(source, output / "source.json")
    state: Literal["completed", "not_evaluable", "failed", "cancelled"] = "completed"
    reason: str | None = None
    source_hash: str | None = None
    unchanged: bool | None = None
    snapshot_complete = False
    rows: int | None = None
    columns: tuple[Any, ...] = ()
    duplicates: tuple[Any, ...] = ()
    conversions: tuple[dict[str, object], ...] = ()
    numeric: tuple[dict[str, object], ...] = ()
    backend: Backend | None = None
    connection: Any = None
    timer: threading.Timer | None = None
    environment = {"python": sys.version, "platform": platform.platform()}
    cancellation_failure: str | None = None

    def checkpoint() -> None:
        nonlocal cancellation_failure
        if cancellation_failure is not None:
            raise _Unavailable(cancellation_failure)
        if cancellation is not None:
            try:
                requested = cancellation()
            except Exception as error:
                report_failure(error, "Cancellation callback failed")
                cancellation_failure = "cancellation_callback_failed"
                raise _Unavailable(cancellation_failure) from None
            if type(requested) is not bool:
                cancellation_failure = "invalid_cancellation_result"
                raise _Unavailable(cancellation_failure)
            if requested:
                raise _Cancelled("cancellation_requested")
        if time.monotonic() - started >= limits.timeout_seconds:
            raise _Unavailable("timeout_budget_exhausted")

    try:
        checkpoint()
        if path.stat().st_size > limits.max_input_bytes:
            raise _Unavailable("input_bytes_budget_exhausted")
        source_hash = _sha(path, checkpoint)
        if source.expected_sha256 is not None and source_hash != source.expected_sha256:
            raise ValueError("source SHA-256 mismatch")
        if source.expected_bytes is not None and path.stat().st_size != source.expected_bytes:
            raise ValueError("source byte size mismatch")
        if binding and (
            source_hash != binding["sha256"] or path.stat().st_size != binding["bytes"]
        ):
            raise ValueError("selected source contradicts trusted manifest")
        snapshot = output / ("snapshot." + source.format)
        with _open_regular(path) as reader, snapshot.open("xb") as writer:
            while block := reader.read(1024 * 1024):
                checkpoint()
                writer.write(block)
            writer.flush()
            os.fsync(writer.fileno())
        if _sha(snapshot, checkpoint) != source_hash or _sha(path, checkpoint) != source_hash:
            raise ValueError("source changed during snapshot capture")
        snapshot_complete = True
        try:
            duckdb = importlib.import_module("duckdb")
        except ImportError as error:
            raise _Unavailable("missing_optional_dependency: install equiframe[eda]") from error
        environment["duckdb"] = duckdb.__version__
        temporary = output / "temporary"
        temporary.mkdir(mode=0o700)
        connection = duckdb.connect(
            ":memory:",
            config={
                "memory_limit": f"{limits.memory_mb}MB",
                "threads": limits.threads,
                "max_temp_directory_size": f"{limits.temp_disk_mb}MB",
                "temp_directory": str(temporary),
                "autoinstall_known_extensions": False,
                "preserve_insertion_order": True,
            },
        )
        # ICU bundled with the wheel is initialized during connect on some hosts.
        # Set UTC afterwards, while implicit extension downloads remain disabled.
        connection.execute("SET TimeZone='UTC'")
        if connection.execute("SELECT current_setting('TimeZone')").fetchone() != ("UTC",):
            raise ValueError("EDA requires an available UTC timezone setting")

        def interrupt() -> None:
            # Timer race with close is not a diagnostic success.
            with suppress(duckdb.Error):
                connection.interrupt()

        timer = threading.Timer(
            max(0.001, limits.timeout_seconds - (time.monotonic() - started)), interrupt
        )
        timer.daemon = True
        timer.start()
        if source.format == "parquet":
            parquet = importlib.import_module("pyarrow.parquet")
            original_schema = parquet.read_schema(snapshot)
            original_names = original_schema.names
            if len({n.casefold() for n in original_names}) != len(original_names):
                raise ValueError("Parquet column names collide before DuckDB name rewriting")
            _admit_arrow_schema(original_schema)
            connection.read_parquet(str(snapshot)).create_view("eda_input")
        elif source.format == "csv":
            with snapshot.open("r", encoding="utf-8", newline="") as stream:
                headers = next(csv.reader(stream, delimiter=source.delimiter))
            if not all(headers) or len({n.casefold() for n in headers}) != len(headers):
                raise ValueError("CSV requires nonempty unique case-insensitive column names")
            file_literal = str(snapshot).replace("'", "''")
            delimiter_literal = source.delimiter.replace("'", "''")
            required_strings = (
                "[" + ",".join("'" + h.replace("'", "''") + "'" for h in headers) + "]"
            )
            connection.execute(
                f"CREATE TEMP VIEW eda_input AS SELECT * FROM read_csv('{file_literal}', "
                f"all_varchar=true, header=true, force_not_null={required_strings}, "
                f"delim='{delimiter_literal}')"
            )
        else:
            arrow = importlib.import_module("pyarrow")
            environment["pyarrow"] = arrow.__version__
            reader = arrow.ipc.open_file(arrow.memory_map(str(snapshot), "r"))
            original_schema = reader.schema
            if len({n.casefold() for n in reader.schema.names}) != len(reader.schema.names):
                raise ValueError("Arrow column names collide before DuckDB name rewriting")
            _admit_arrow_schema(original_schema)
            connection.register("eda_input", reader.read_all())
        input_names = [r[0] for r in connection.execute("DESCRIBE eda_input").fetchall()]
        if not set(config.identifiers) <= set(input_names):
            raise ValueError("identifier rule references unknown source column")
        if any(n.casefold().startswith("__ef_") for n in input_names) or len(
            {n.casefold() for n in input_names}
        ) != len(input_names):
            raise ValueError("source column names conflict with reserved diagnostics namespace")
        if len(input_names) > limits.max_columns:
            raise _Unavailable("column_budget_exhausted")
        connection.execute(
            "CREATE TEMP TABLE raw AS SELECT row_number() OVER () - 1 "
            "AS __ef_eda_row, * FROM eda_input"
        )
        backend = Backend(connection, config, checkpoint)
        rows = backend.query("SELECT count(*) FROM raw")[0][0]
        if rows > limits.max_rows:
            raise _Unavailable("row_budget_exhausted")
        columns = backend.columns(rows)
        conversions = backend.convert()
        duplicates = (
            backend.duplicates(tuple(backend.raw_schema)),
            *(backend.duplicates(k.columns, k) for k in config.keys),
        )
        numeric = tuple(backend.numeric(rule) for rule in config.numeric)
        if any(n["state"] == "not_evaluable" for n in numeric) or any(
            f.severity == "not_evaluable" for f in backend.findings
        ):
            state, reason = "not_evaluable", "requested_metrics_unavailable"
        if config.conversions:
            destination = str(output / "typed.parquet").replace("'", "''")
            backend.query(f"COPY (SELECT * FROM typed) TO '{destination}' (FORMAT PARQUET)")
        checkpoint()
        if before_finalize is not None:
            before_finalize()
    except _Cancelled as error:
        state, reason = "cancelled", str(error)
    except _Unavailable as error:
        state, reason = "not_evaluable", str(error)
    except Exception as error:
        resource_error = isinstance(error, CapabilityError) or type(error).__name__ in {
            "OutOfMemoryException",
            "OutOfRangeException",
            "InterruptException",
        }
        state = "not_evaluable" if resource_error else "failed"
        reason = report_failure(
            error,
            "analysis_unavailable" if resource_error else "analysis_failed",
        )
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        if connection is not None:
            connection.close()
        try:
            if source_hash is not None:
                unchanged = _sha(path) == source_hash
                if not unchanged:
                    state, reason = "failed", "source_changed_during_analysis"
            if (
                source.manifest_path is not None
                and _sha(Path(source.manifest_path)) != source.manifest_sha256
            ):
                state, reason = "failed", "source_manifest_changed_during_analysis"
        except OSError:
            state, reason, unchanged = "failed", "source_readback_unavailable", False
    result = EdaResult(
        run_id=run_id,
        producer_version=__version__,
        snapshot_id=source.snapshot_id,
        state=state,
        reason=reason,
        elapsed_seconds=time.monotonic() - started,
        calculation_elapsed_seconds=time.monotonic() - started,
        source=source,
        source_sha256=source_hash,
        source_unchanged=unchanged,
        snapshot_complete=snapshot_complete,
        config_sha256=fingerprint,
        rows=rows,
        columns=columns,
        duplicates=duplicates,
        conversions=conversions,
        numeric=numeric,
        findings=tuple(backend.findings) if backend is not None else (),
        environment=environment,
        limits=LIMITS,
        evidence_links=evidence_links,
    )
    from ._report import publish_report

    return publish_report(
        result, config=config, output=output, checkpoint=checkpoint, started=started
    )


def analyze_artifact(
    artifact: TableArtifact, *, config: EdaConfig | None = None, output: Path
) -> EdaResult:
    """Use a captured table's original byte identity; no ETL or fictitious execution."""
    artifact = TableArtifact.model_validate(artifact)
    ref = artifact.data
    return analyze(
        Source(
            path=str(local_path(ref)),
            format=cast("Literal['arrow', 'parquet']", ref.format),
            snapshot_id=artifact.name + ":" + ref.sha256,
            expected_sha256=ref.sha256,
            expected_bytes=ref.size_bytes,
        ),
        config=config,
        output=output,
    )


def analyze_migration(
    path: Path,
    *,
    side: Literal["source", "target"] = "source",
    config: EdaConfig | None = None,
    output: Path,
) -> EdaResult:
    """Read/verify an existing migration, then diagnose its output independently."""
    from equiframe.bundle import read_bundle
    from equiframe.migration import MigrationResult, read_migration

    if side not in ("source", "target"):
        raise ValueError("side must be source or target")
    selected = ordinary_path(path, directory=path.is_dir())
    root = selected.parent if selected.is_file() else selected
    destination = ordinary_path(output, directory=True, allow_missing=True)
    if destination.is_relative_to(root):
        raise ValueError("EDA results must be outside the existing migration evidence")
    portable = (root / "bundle.json").is_file()
    if portable:
        bundle = read_bundle(root)
        if bundle.kind != "migration":
            raise ValueError("selected portable bundle must contain migration evidence")
        document = root / bundle.root_document
        # read_bundle has already invoked the original verified reader using its
        # closed public reference inventory. Do not rewrite those historical URIs.
        original = load_json(MigrationResult, document)
    else:
        original = read_migration(path)
        document = root / "migration.json"
    pipeline = original.source if side == "source" else original.target
    if pipeline is None or pipeline.execution is None or pipeline.execution.output is None:
        raise ValueError("migration has no captured output on the selected side")
    artifact = pipeline.execution.output
    ref = artifact.data
    links = (
        {
            "kind": "verified_migration",
            "migration_id": original.migration_id,
            "path": str(document),
            "sha256": _sha(document),
            "side": side,
            "state": original.state,
            "verification": original.verification,
            "index_scope": "index artifact not profiled"
            if artifact.index is not None
            else "no index",
        },
    )
    if portable:
        members = [r for r in bundle.references if r.uri == ref.uri]
        if len(members) != 1:
            raise ValueError("captured output is not a unique verified bundle member")
        input_path = root / members[0].member.path
    else:
        input_path = local_path(ref)

    def revalidate() -> None:
        if _sha(document) != links[0]["sha256"]:
            raise ValueError("migration document byte identity changed during diagnostics")
        if read_bundle(root) != bundle if portable else read_migration(path) != original:
            raise ValueError("migration evidence changed during diagnostics")

    result = _analyze(
        Source(
            path=str(input_path),
            format=cast("Literal['arrow', 'parquet']", ref.format),
            snapshot_id=artifact.name + ":" + ref.sha256,
            expected_sha256=ref.sha256,
            expected_bytes=ref.size_bytes,
        ),
        config=config,
        output=output,
        evidence_links=links,
        before_finalize=revalidate,
    )
    return result


def read_result(path: Path) -> EdaResult:
    """Read a closed versioned diagnostic run, checking all recorded byte identities."""
    selected = ordinary_path(path, directory=path.is_dir())
    root = selected if selected.is_dir() else selected.parent
    manifest = load_json(EdaManifest, root / "manifest.json").model_dump(mode="json")
    if manifest.get("schema_version") != "1.0" or manifest.get("kind") != "equiframe.eda":
        raise ValueError("unsupported EDA manifest")
    names = [r["path"] for r in manifest["files"]]
    if len(set(names)) != len(names):
        raise ValueError("duplicate EDA inventory member")
    for entry in manifest["files"]:
        member = manifest_member(root, entry["path"])
        if member.stat().st_size != entry["bytes"] or _sha(member) != entry["sha256"]:
            raise ValueError("EDA result artifact integrity mismatch")
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p.relative_to(root).as_posix() != "manifest.json"
    }
    if actual != set(names):
        raise ValueError("EDA inventory is not closed")
    result = load_json(EdaResult, root / "summary.json")
    config = load_json(EdaConfig, root / "config.json")
    if (
        result.run_id != manifest["run_id"]
        or result.state != manifest["state"]
        or result.source != load_json(Source, root / "source.json")
        or result.config_sha256
        != hashlib.sha256(canonical_bytes(config.model_dump(mode="json"))).hexdigest()
    ):
        raise ValueError("EDA result identity mismatch")
    with _open_regular(root / "findings.json") as stream:
        findings_raw = stream.read(16 * 1024**2 + 1)
    if len(findings_raw) > 16 * 1024**2:
        raise ValueError("EDA findings exceed their byte budget")
    if parse_json(findings_raw) != {
        "schema_version": "1.0",
        "kind": "equiframe.eda.findings",
        "run_id": result.run_id,
        "items": [f.model_dump(mode="json") for f in result.findings],
    }:
        raise ValueError("EDA findings contradict summary")
    snapshot = root / ("snapshot." + result.source.format)
    if result.snapshot_complete and (
        not snapshot.is_file() or result.source_sha256 != _sha(snapshot)
    ):
        raise ValueError("fixed snapshot contradicts source identity")
    return result
