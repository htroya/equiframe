"""Closed portable inventories and exact reproduction of declared logical records.

Original evidence is copied verbatim. Rebasing an explicitly indexed ArtifactRef
does not rewrite a parent's manifest or certify its original fingerprint. JSON
never names executable code: regeneration requires a trusted callable supplied by
the caller. Technical receipts do not assert a colleague's review or approval.
"""

import hashlib
import os
import shutil
import stat
import unicodedata
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, TypeVar
from uuid import uuid4

from equiframe import ArtifactRef
from equiframe.errors import ArtifactIntegrityError, ResourceLimitError
from equiframe.evidence import canonical_bytes, parse_json
from pydantic import AfterValidator, BaseModel, Field, TypeAdapter, model_validator
from typing_extensions import Self

from equiframe_benchmark.models import Digest, Document, Text, digest

_ModelT = TypeVar("_ModelT", bound=BaseModel)

_CHUNK = 1024 * 1024
_MANIFEST = "bundle.json"
Component = Literal["configuration", "splits", "labels", "decisions", "tables"]
_COMPONENTS: tuple[Component, ...] = ("configuration", "splits", "labels", "decisions", "tables")
ArtifactFormat = Literal["json", "jsonl", "arrow", "parquet"]
_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
    *(f"com{i}" for i in "¹²³"),
    *(f"lpt{i}" for i in "¹²³"),
}


def _relative(value: str) -> str:
    parts = value.split("/")
    if (
        not value
        or "\\" in value
        or ":" in value
        or unicodedata.normalize("NFC", value) != value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
        or any(c in value for c in '<>"|?*')
        or any(not p or p in (".", "..") or p.endswith((".", " ")) for p in parts)
        or any(p.split(".")[0].casefold() in _RESERVED for p in parts)
    ):
        raise ValueError("bundle paths require canonical portable relative POSIX names")
    return value


RelativePath = Annotated[Text, AfterValidator(_relative)]


def _json(value: str) -> str:
    parsed = parse_json(value.encode("utf-8"))
    _check_json_value(parsed)
    if canonical_bytes(parsed).decode("utf-8") != value:
        raise ValueError("logical content must be canonical strict JSON")
    return value


CanonicalJson = Annotated[Text, AfterValidator(_json)]


class BundleLimits(Document):
    """Accounting budgets; no compression/archive extraction or hidden downloads."""

    max_files: Annotated[int, Field(gt=0)] = 10_000
    max_total_bytes: Annotated[int, Field(gt=0)] = 10 * 1024**3
    max_file_bytes: Annotated[int, Field(gt=0)] = 2 * 1024**3
    max_manifest_bytes: Annotated[int, Field(gt=0)] = 8 * 1024**2
    max_record_bytes: Annotated[int, Field(gt=0)] = 64 * 1024**2


class BundleFile(Document):
    path: RelativePath
    sha256: Digest
    size_bytes: Annotated[int, Field(ge=0)]
    source_uri: Text | None = None
    artifact_format: ArtifactFormat | None = None

    @model_validator(mode="after")
    def reference(self) -> Self:
        if self.path.split("/")[0].casefold() == _MANIFEST:
            raise ValueError("bundle manifest is reserved")
        if self.artifact_format is not None and self.source_uri is None:
            raise ValueError("artifact format requires its original URI binding")
        if self.source_uri is not None:
            ArtifactRef(
                schema_version="1.0",
                uri=self.source_uri,
                sha256=self.sha256,
                size_bytes=self.size_bytes,
                format=self.artifact_format or "json",
                media_type="application/octet-stream",
            )
        return self


class ReproductionBundle(Document):
    bundle_id: Text
    files: tuple[BundleFile, ...]
    record_path: RelativePath | None = None

    @model_validator(mode="after")
    def closed(self) -> Self:
        names = [item.path.casefold() for item in self.files]
        uris = [item.source_uri for item in self.files if item.source_uri is not None]
        if not names or len(set(names)) != len(names) or len(set(uris)) != len(uris):
            raise ValueError("bundle files and original URI bindings must be unique")
        if tuple(item.path for item in self.files) != tuple(sorted(i.path for i in self.files)):
            raise ValueError("bundle inventory must be sorted")
        name_set = set(names)
        portable_nodes: dict[str, str] = {}
        for item in self.files:
            for node in (PurePosixPath(item.path), *PurePosixPath(item.path).parents):
                if str(node) != ".":
                    key = str(node).casefold()
                    if portable_nodes.get(key, str(node)) != str(node):
                        raise ValueError("bundle directories cannot have case aliases")
                    portable_nodes[key] = str(node)
        for name in names:
            if any(
                str(p).casefold() in name_set for p in PurePosixPath(name).parents if str(p) != "."
            ):
                raise ValueError("file paths cannot contain another file")
        if self.record_path is not None and self.record_path not in {i.path for i in self.files}:
            raise ValueError("reproduction record must belong to the closed inventory")
        return self


class ReproductionRecord(Document):
    """Full declared logical payloads, immutable JSON with tagged exact quantities.

    Tables must contain complete logical rows or verified full-content identities,
    including currency amounts where applicable. Counts alone cannot establish table
    equivalence; this generic record does not certify tables omitted by a caller.
    """

    configuration: CanonicalJson
    splits: CanonicalJson
    labels: CanonicalJson
    decisions: CanonicalJson
    tables: CanonicalJson


def _check_json_value(value: object) -> None:
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("JSON member names must be strings")
        for key in value:
            _check_json_value(key)
        for item in value.values():
            _check_json_value(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_json_value(item)
    elif isinstance(value, str) and any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError("logical content requires valid Unicode scalars")
    elif value is not None and type(value) not in (bool, int, float, str):
        raise TypeError("logical quantities require explicit JSON tags, never implicit casts")


def make_reproduction_record(
    *, configuration: object, splits: object, labels: object, decisions: object, tables: object
) -> ReproductionRecord:
    values = {
        "configuration": configuration,
        "splits": splits,
        "labels": labels,
        "decisions": decisions,
        "tables": tables,
    }
    encoded = {}
    for name, value in values.items():
        _check_json_value(value)
        encoded[name] = canonical_bytes(value).decode("utf-8")
    return ReproductionRecord.model_validate(encoded)


class ComponentComparison(Document):
    component: Component
    recorded_sha256: Digest
    repeated_sha256: Digest
    identical: bool


class ComparisonReceipt(Document):
    """Technical equality of all supplied content; no human attestation field."""

    recorded: ReproductionRecord
    repeated: ReproductionRecord
    recorded_sha256: Digest
    repeated_sha256: Digest
    components: tuple[ComponentComparison, ...]
    status: Literal["reproduced", "different"]

    @model_validator(mode="after")
    def content(self) -> Self:
        if self.recorded_sha256 != digest(self.recorded) or self.repeated_sha256 != digest(
            self.repeated
        ):
            raise ValueError("reproduction content fingerprint mismatch")
        if tuple(c.component for c in self.components) != _COMPONENTS:
            raise ValueError("all five logical components require comparison")
        for item in self.components:
            left = getattr(self.recorded, item.component)
            right = getattr(self.repeated, item.component)
            if (
                item.recorded_sha256 != hashlib.sha256(left.encode()).hexdigest()
                or item.repeated_sha256 != hashlib.sha256(right.encode()).hexdigest()
                or item.identical != (left == right)
            ):
                raise ValueError("comparison contradicts complete logical content")
        expected = "reproduced" if all(c.identical for c in self.components) else "different"
        if self.status != expected:
            raise ValueError("reproduction status contradicts component comparisons")
        return self


def compare_reproductions(
    recorded: ReproductionRecord, repeated: ReproductionRecord
) -> ComparisonReceipt:
    recorded = ReproductionRecord.model_validate(recorded)
    repeated = ReproductionRecord.model_validate(repeated)
    components = tuple(
        ComponentComparison(
            component=name,
            recorded_sha256=hashlib.sha256(getattr(recorded, name).encode()).hexdigest(),
            repeated_sha256=hashlib.sha256(getattr(repeated, name).encode()).hexdigest(),
            identical=getattr(recorded, name) == getattr(repeated, name),
        )
        for name in _COMPONENTS
    )
    return ComparisonReceipt(
        recorded=recorded,
        repeated=repeated,
        recorded_sha256=digest(recorded),
        repeated_sha256=digest(repeated),
        components=components,
        status="reproduced" if all(c.identical for c in components) else "different",
    )


def _link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _plain_path(path: Path, *, directory: bool = False) -> Path:
    path = path.absolute()
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if _link(info) or (part != path and not stat.S_ISDIR(info.st_mode)):
            raise ArtifactIntegrityError("bundle paths cannot traverse links or reparse points")
    info = path.lstat()
    valid = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid:
        raise ArtifactIntegrityError("bundle input is not an ordinary file/directory")
    return path


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    # CPython 3.12 on Windows exposes birth time for path.stat().st_ctime but
    # modification time for fstat().st_ctime; those fields cannot be compared.
    changed = 0 if os.name == "nt" else info.st_ctime_ns
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, changed


def _stream_file(path: Path, maximum: int, destination: Path | None = None) -> tuple[str, int]:
    path = _plain_path(path)
    expected = path.lstat()
    if expected.st_size > maximum:
        raise ResourceLimitError("bundle file exceeds byte budget")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    checksum = hashlib.sha256()
    count = 0
    with os.fdopen(os.open(path, flags), "rb") as source:
        if _identity(os.fstat(source.fileno())) != _identity(expected):
            raise ArtifactIntegrityError("bundle source changed before opening")
        target = destination.open("xb") if destination is not None else None
        try:
            while block := source.read(_CHUNK):
                count += len(block)
                if count > maximum:
                    raise ResourceLimitError("bundle file exceeds byte budget")
                checksum.update(block)
                if target is not None:
                    target.write(block)
            if target is not None:
                target.flush()
                os.fsync(target.fileno())
        finally:
            if target is not None:
                target.close()
        if _identity(os.fstat(source.fileno())) != _identity(expected):
            raise ArtifactIntegrityError("bundle source changed during streaming")
    if _identity(path.lstat()) != _identity(expected) or _link(path.lstat()):
        raise ArtifactIntegrityError("bundle source changed after streaming")
    return checksum.hexdigest(), count


def _bounded_json(model: type[_ModelT], path: Path, maximum: int) -> tuple[_ModelT, str]:
    path = _plain_path(path)
    expected = path.lstat()
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(expected):
            raise ArtifactIntegrityError("bundle JSON changed before opening")
        data = stream.read(maximum + 1)
        if _identity(os.fstat(stream.fileno())) != _identity(expected):
            raise ArtifactIntegrityError("bundle JSON changed during reading")
    if len(data) > maximum:
        raise ResourceLimitError("bundle JSON exceeds byte budget")
    if _identity(path.lstat()) != _identity(expected) or _link(path.lstat()):
        raise ArtifactIntegrityError("bundle JSON changed after reading")
    parse_json(data)
    return model.model_validate_json(data), hashlib.sha256(data).hexdigest()


def _limits(bundle: ReproductionBundle, limits: BundleLimits) -> None:
    if len(bundle.files) > limits.max_files:
        raise ResourceLimitError("bundle file count exceeds budget")
    if sum(item.size_bytes for item in bundle.files) > limits.max_total_bytes:
        raise ResourceLimitError("bundle total bytes exceed budget")
    if any(item.size_bytes > limits.max_file_bytes for item in bundle.files):
        raise ResourceLimitError("bundle file bytes exceed budget")


def _inventory(directory: Path, maximum: int) -> set[str]:
    directory = _plain_path(directory, directory=True)
    observed: set[str] = set()
    pending = [directory]
    while pending:
        parent = pending.pop()
        with os.scandir(parent) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if _link(info):
                    raise ArtifactIntegrityError("bundle contains a link or reparse point")
                relative = Path(entry.path).relative_to(directory).as_posix()
                _relative(relative)
                observed.add(relative)
                if len(observed) > maximum:
                    raise ResourceLimitError("bundle inventory exceeds entry budget")
                if stat.S_ISDIR(info.st_mode):
                    pending.append(Path(entry.path))
                elif not stat.S_ISREG(info.st_mode):
                    raise ArtifactIntegrityError("bundle contains a non-ordinary file")
    return observed


def read_bundle(
    directory: Path, *, expected_sha256: str | None = None, limits: BundleLimits | None = None
) -> ReproductionBundle:
    """Verify every byte and the complete inventory; never execute imported code."""
    limits = BundleLimits.model_validate(limits or BundleLimits())
    directory = _plain_path(directory, directory=True)
    manifest = directory / _MANIFEST
    bundle, manifest_hash = _bounded_json(ReproductionBundle, manifest, limits.max_manifest_bytes)
    _limits(bundle, limits)
    if expected_sha256 is not None and manifest_hash != expected_sha256:
        raise ArtifactIntegrityError("bundle manifest fingerprint mismatch")
    expected = {_MANIFEST, *(item.path for item in bundle.files)}
    for item in bundle.files:
        expected.update(str(p) for p in PurePosixPath(item.path).parents if str(p) != ".")
    # Directories are counted too, preventing an unbounded tree of empty extras.
    if _inventory(directory, len(expected)) != expected:
        raise ArtifactIntegrityError("bundle inventory is missing files or contains extras")
    for item in bundle.files:
        observed_hash, size = _stream_file(directory / item.path, limits.max_file_bytes)
        if (observed_hash, size) != (item.sha256, item.size_bytes):
            raise ArtifactIntegrityError("bundle file SHA-256 or size mismatch")
    if _stream_file(manifest, limits.max_manifest_bytes)[0] != manifest_hash:
        raise ArtifactIntegrityError("bundle manifest changed during verification")
    return bundle


def create_bundle(
    files: Mapping[str, Path],
    *,
    directory: Path,
    bundle_id: str,
    record_path: str | None = None,
    artifacts: Mapping[str, ArtifactRef] | None = None,
    expected_files: Mapping[str, tuple[str, int]] | None = None,
    limits: BundleLimits | None = None,
) -> ReproductionBundle:
    """Copy to private staging; commit the final manifest atomically and exclusively.

    The final directory is reserved without replacement. Before its final manifest
    is linked, it is not a readable bundle. Publication never replaces an existing
    directory, including an empty one, on Windows or POSIX.
    Raw expected-file pins constrain the streamed bytes before any publication;
    they do not claim a file format or require an ArtifactRef.
    """
    limits = BundleLimits.model_validate(limits or BundleLimits())
    artifacts = {} if artifacts is None else artifacts
    if not set(artifacts).issubset(files):
        raise ValueError("artifact bindings must belong to the supplied files")
    expected_files = {} if expected_files is None else dict(expected_files)
    if not set(expected_files).issubset(files):
        raise ValueError("expected file pins must belong to the supplied files")
    for name, expected in expected_files.items():
        _relative(name)
        if not isinstance(expected, tuple) or len(expected) != 2:
            raise ValueError("expected file pins require a SHA-256 and nonnegative byte size tuple")
        TypeAdapter(Digest).validate_python(expected[0], strict=True)
        if type(expected[1]) is not int or expected[1] < 0:
            raise ValueError("expected file byte sizes must be nonnegative integers")
    if not files or len(files) > limits.max_files:
        raise ResourceLimitError("bundle file count is empty or exceeds budget")
    directory = directory.absolute()
    _plain_path(directory.parent, directory=True)
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(directory)
    staging = directory.parent / (".bundle-" + uuid4().hex)
    staging.mkdir(mode=0o700)
    reserved = False
    try:
        inventory = []
        total = 0
        for name, source in sorted(files.items()):
            _relative(name)
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            checksum, size = _stream_file(
                source, min(limits.max_file_bytes, limits.max_total_bytes - total), target
            )
            if name in expected_files and expected_files[name] != (checksum, size):
                raise ArtifactIntegrityError("expected file pin contradicts copied content")
            total += size
            ref = ArtifactRef.model_validate(artifacts[name]) if name in artifacts else None
            if ref is not None and (ref.sha256, ref.size_bytes) != (checksum, size):
                raise ArtifactIntegrityError("supplied ArtifactRef contradicts copied content")
            inventory.append(
                BundleFile(
                    path=name,
                    sha256=checksum,
                    size_bytes=size,
                    source_uri=ref.uri if ref else source.absolute().as_uri(),
                    artifact_format=ref.format if ref else None,
                )
            )
        bundle = ReproductionBundle(
            bundle_id=bundle_id, files=tuple(inventory), record_path=record_path
        )
        data = canonical_bytes(bundle.model_dump(mode="json")) + b"\n"
        if len(data) > limits.max_manifest_bytes:
            raise ResourceLimitError("bundle manifest exceeds byte budget")
        with (staging / _MANIFEST).open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        read_bundle(staging, limits=limits)
        directory.mkdir(mode=0o700)
        reserved = True
        for item in staging.iterdir():
            if item.name != _MANIFEST:
                os.rename(item, directory / item.name)
        os.link(staging / _MANIFEST, directory / _MANIFEST)
        return bundle
    except BaseException:
        if reserved:
            # Only our exclusive reservation; reject changed parent/link before cleanup.
            _plain_path(directory, directory=True)
            shutil.rmtree(directory)
        raise
    finally:
        _plain_path(staging, directory=True)
        shutil.rmtree(staging)


def bundle_artifact(
    bundle: ReproductionBundle,
    directory: Path,
    original: ArtifactRef,
    *,
    limits: BundleLimits | None = None,
) -> ArtifactRef:
    """Rebase only URI after matching original URI/SHA/size/registered format."""
    limits = BundleLimits.model_validate(limits or BundleLimits())
    original = ArtifactRef.model_validate(original)
    verified = read_bundle(directory, limits=limits)
    if verified != ReproductionBundle.model_validate(bundle):
        raise ArtifactIntegrityError("bundle metadata differs from verified inventory")
    matches = tuple(item for item in bundle.files if item.source_uri == original.uri)
    if len(matches) != 1:
        raise ArtifactIntegrityError("artifact has no unique original URI binding")
    item = matches[0]
    if (item.sha256, item.size_bytes, item.artifact_format) != (
        original.sha256,
        original.size_bytes,
        original.format,
    ):
        raise ArtifactIntegrityError("artifact identity or registered format differs")
    return ArtifactRef.model_validate(
        {
            **original.model_dump(mode="python"),
            "uri": (directory.absolute() / item.path).as_uri(),
        }
    )


def reproduce_bundle(
    directory: Path,
    *,
    regenerator: Callable[[ReproductionRecord], ReproductionRecord],
    expected_sha256: str | None = None,
    limits: BundleLimits | None = None,
) -> ComparisonReceipt:
    """Regenerate pure tables/decisions with explicit trusted consumer code.

    No ETL, plugin import, SQL, model deserialization or human approval is invoked by
    this module. The consumer's callable must operate on captured records/config.
    """
    limits = BundleLimits.model_validate(limits or BundleLimits())
    bundle = read_bundle(directory, expected_sha256=expected_sha256, limits=limits)
    if bundle.record_path is None:
        raise ValueError("bundle has no declared reproduction record")
    recorded, record_hash = _bounded_json(
        ReproductionRecord, directory / bundle.record_path, limits.max_record_bytes
    )
    item = next(item for item in bundle.files if item.path == bundle.record_path)
    if record_hash != item.sha256:
        raise ArtifactIntegrityError("reproduction record differs from verified inventory")
    repeated = ReproductionRecord.model_validate(regenerator(recorded))
    if read_bundle(directory, expected_sha256=expected_sha256, limits=limits) != bundle:
        raise ArtifactIntegrityError("regenerator changed the original bundle")
    return compare_reproductions(recorded, repeated)
