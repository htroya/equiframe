"""Read-only distribution inventory, never publication or a PyPI name reservation.

Wheel metadata verification is distinct from building, installing and testing a
release. Platform evidence and publication decisions remain outside this reader.
Requirements are parsed by packaging; no backend or packaged code is executed.
"""

import hashlib
import json
import re
import stat
import sys

from equiframe._path_compat import is_junction

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from datetime import datetime
from email import policy
from email.message import Message
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal
from urllib.parse import urlsplit
from zipfile import ZipFile, ZipInfo

from equiframe._base import strict_bool_literal
from pydantic import BeforeValidator, Field, model_validator
from typing_extensions import Self

from equiframe_benchmark.models import Digest, Document, Text

MAX_SOURCE_FILE = 32 * 1024 * 1024
MAX_SOURCE_TOTAL = 128 * 1024 * 1024
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_EXPANDED = 512 * 1024 * 1024
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_MEMBERS = 10000
NonNegativeInt = Annotated[int, Field(ge=0)]


class NameCheck(Document):
    """Injected observation; an HTTP response is not evidence of ownership."""

    name: Text
    query_url: Text
    fetched_at: datetime | None
    http_status: Annotated[int, Field(ge=100, le=599)] | None
    status: Literal["not_found", "exists", "unknown"]
    controlled: bool = False
    control_evidence: Text | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        canonical = _name(self.name)
        url = urlsplit(self.query_url)
        if url.scheme != "https" or url.hostname != "pypi.org" or url.username or url.password:
            raise ValueError("name observations require a credential-free official PyPI URL")
        if url.path not in (f"/pypi/{canonical}/json", f"/project/{canonical}/") or (
            url.query or url.fragment or url.port not in (None, 443)
        ):
            raise ValueError("name observation URL must identify the declared distribution")
        if self.fetched_at is not None and self.fetched_at.utcoffset() is None:
            raise ValueError("name observations require a timezone-aware fetch time")
        if self.status != "unknown":
            expected = 404 if self.status == "not_found" else 200
            if self.http_status != expected or self.fetched_at is None:
                raise ValueError("a resolved name observation requires HTTP status and fetch time")
        if self.controlled and (
            self.status != "exists" or self.http_status != 200 or self.control_evidence is None
        ):
            raise ValueError("name control requires separate evidence beyond an availability query")
        return self


class SourceFileEvidence(Document):
    relative_path: Text
    sha256: Digest
    size_bytes: NonNegativeInt

    @model_validator(mode="after")
    def path(self) -> Self:
        _relative(self.relative_path)
        return self


class ProjectURL(Document):
    label: Text
    url: Text

    @model_validator(mode="after")
    def valid_url(self) -> Self:
        url = urlsplit(self.url)
        if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password:
            raise ValueError("project URLs require an absolute credential-free HTTP(S) URL")
        return self


class OptionalDependencies(Document):
    extra: Text
    requirements: tuple[Text, ...]


class ReadmeMetadata(Document):
    file: Text | None
    inline_text: str | None
    content_type: Text | None

    @model_validator(mode="after")
    def one_source(self) -> Self:
        if (self.file is None) == (self.inline_text is None):
            raise ValueError("readme metadata requires exactly one file or inline text")
        if self.file is not None:
            _relative(self.file)
        if self.inline_text is not None and self.content_type is None:
            raise ValueError("inline readme metadata requires content type")
        return self


class LicenseMetadata(Document):
    expression: Text | None
    file: Text | None
    text: str | None

    @model_validator(mode="after")
    def defined_license(self) -> Self:
        if sum(value is not None for value in (self.expression, self.file, self.text)) != 1:
            raise ValueError("license metadata requires one expression, file or legacy text")
        if self.file is not None:
            _relative(self.file)
        if self.text is not None and not self.text.strip():
            raise ValueError("legacy license text must not be empty")
        if self.expression is not None:
            from packaging.licenses import canonicalize_license_expression

            if canonicalize_license_expression(self.expression) != self.expression:
                raise ValueError("license expressions must use canonical SPDX identifiers")
        return self


class ProjectDistributionMetadata(Document):
    name: Text
    canonical_name: Text
    version: Text
    requires_python: Text | None
    dependencies: tuple[Text, ...]
    optional_dependencies: tuple[OptionalDependencies, ...]
    classifiers: tuple[Text, ...]
    urls: tuple[ProjectURL, ...]
    readme: ReadmeMetadata | None
    license: LicenseMetadata | None
    license_file_patterns: tuple[Text, ...]
    license_files: tuple[Text, ...]
    typed_markers: tuple[Text, ...]

    @model_validator(mode="after")
    def metadata(self) -> Self:
        from packaging.version import Version

        if self.canonical_name != _name(self.name) or self.version != str(Version(self.version)):
            raise ValueError("project name and version must use their canonical metadata forms")
        if self.requires_python is not None and self.requires_python != _spec(self.requires_python):
            raise ValueError("Requires-Python must use canonical specifiers")
        for requirement in self.dependencies:
            if requirement != _requirement(requirement):
                raise ValueError("dependencies must use canonical parsed requirements")
        extras = tuple(item.extra for item in self.optional_dependencies)
        if len(set(extras)) != len(extras):
            raise ValueError("optional extras must be unique after normalization")
        for item in self.optional_dependencies:
            if _name(item.extra) != item.extra:
                raise ValueError("extra names must be normalized")
            for requirement in item.requirements:
                if requirement != _requirement(requirement):
                    raise ValueError("optional requirements must be canonical")
        for filename in (*self.license_files, *self.typed_markers):
            _relative(filename)
        return self


class WheelDistributionMetadata(Document):
    wheel_sha256: Digest
    wheel_size_bytes: NonNegativeInt
    metadata_sha256: Digest
    wheel_metadata_sha256: Digest
    metadata_version: Text
    name: Text
    canonical_name: Text
    version: Text
    requires_python: Text | None
    dependencies: tuple[Text, ...]
    extras: tuple[Text, ...]
    classifiers: tuple[Text, ...]
    urls: tuple[ProjectURL, ...]
    license_expression: Text | None
    license_text: Text | None
    license_files: tuple[Text, ...]
    typed_markers: tuple[Text, ...]
    wheel_version: Literal["1.0"]
    root_is_purelib: bool
    tags: Annotated[tuple[Text, ...], Field(min_length=1)]
    member_count: Annotated[int, Field(ge=1, le=MAX_MEMBERS)]
    expanded_size_bytes: Annotated[int, Field(ge=0, le=MAX_ARCHIVE_EXPANDED)]

    @model_validator(mode="after")
    def canonical_metadata(self) -> Self:
        from packaging.version import Version

        if self.canonical_name != _name(self.name) or self.version != str(Version(self.version)):
            raise ValueError("wheel name/version must use canonical metadata forms")
        if self.requires_python is not None and self.requires_python != _spec(self.requires_python):
            raise ValueError("wheel Requires-Python must be canonical")
        if self.metadata_version not in (
            "1.0",
            "1.1",
            "1.2",
            "2.1",
            "2.2",
            "2.3",
            "2.4",
            "2.5",
            "2.6",
        ):
            raise ValueError("unsupported distribution Metadata-Version")
        for requirement in self.dependencies:
            if requirement != _requirement(requirement):
                raise ValueError("wheel dependencies must use canonical parsed requirements")
        for path in (*self.typed_markers, *self.license_files):
            _relative(path)
        return self


class DistributionReadiness(Document):
    package_directory: Text
    project: ProjectDistributionMetadata
    source_files: tuple[SourceFileEvidence, ...]
    source_manifest_sha256: Digest
    lock_sha256: Digest | None
    wheel: WheelDistributionMetadata | None
    name_check: NameCheck
    pending_conditions: tuple[Text, ...]
    source_available: Annotated[Literal[True], BeforeValidator(strict_bool_literal)] = True
    wheel_metadata_verified: bool
    technical_inventory_complete: bool
    build_install_verified: Annotated[Literal[False], BeforeValidator(strict_bool_literal)] = False
    publication_ready: Annotated[Literal[False], BeforeValidator(strict_bool_literal)] = False

    @model_validator(mode="after")
    def evidence(self) -> Self:
        paths = tuple(item.relative_path for item in self.source_files)
        if paths != tuple(sorted(set(paths))) or "pyproject.toml" not in paths:
            raise ValueError("source inventory requires sorted unique paths and pyproject.toml")
        files = {item.relative_path: item for item in self.source_files}
        if any(
            path not in files for path in (*self.project.typed_markers, *self.project.license_files)
        ):
            raise ValueError("declared typing/license files must belong to the source inventory")
        lock = files.get("uv.lock")
        if self.lock_sha256 != (lock.sha256 if lock else None):
            raise ValueError("lock fingerprint disagrees with source inventory")
        if self.source_manifest_sha256 != _inventory_digest(self.source_files):
            raise ValueError("source fingerprint disagrees with its inventory")
        if _name(self.name_check.name) != self.project.canonical_name:
            raise ValueError("the name observation belongs to a different distribution")
        if self.wheel is not None:
            _check_wheel(self.project, self.wheel)
        pending = _pending(self.project, files, self.wheel, self.name_check)
        technical = not any(
            condition in pending
            for condition in (
                "pending_readme",
                "pending_lock",
                "pending_requires_python",
                "pending_typing_marker",
            )
        )
        if (
            self.pending_conditions != pending
            or self.wheel_metadata_verified != (self.wheel is not None)
            or self.technical_inventory_complete != technical
        ):
            raise ValueError("readiness flags must agree with the observed inventory")
        return self


def _name(value: str) -> str:
    from packaging.utils import canonicalize_name

    return canonicalize_name(value, validate=True)


def _requirement(value: str) -> str:
    from packaging.requirements import Requirement

    parsed = Requirement(value)
    parsed.name = _name(parsed.name)
    parsed.extras = {_name(extra) for extra in parsed.extras}
    return str(parsed)


def _optional_requirement(value: str, extra: str) -> str:
    from packaging.markers import Marker
    from packaging.requirements import Requirement

    requirement = Requirement(value)
    marker = f"extra == '{extra}'"
    if requirement.marker is not None:
        marker = f"({requirement.marker}) and {marker}"
    requirement.marker = Marker(marker)
    return _requirement(str(requirement))


def _spec(value: str) -> str:
    from packaging.specifiers import SpecifierSet

    if not isinstance(value, str) or not value.strip():
        raise ValueError("Requires-Python cannot be an empty compatibility claim")
    return str(SpecifierSet(value))


def _relative(value: str, *, pattern: bool = False) -> PurePosixPath:
    if not isinstance(value, str):
        raise ValueError("artifact paths must be strings")
    path = PurePosixPath(value)
    if (
        not value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or "\\" in value
        or ":" in value
        or path.is_absolute()
        or any(part in ("", ".", "..") for part in value.split("/"))
        or (not pattern and any(char in value for char in "*?[]"))
    ):
        raise ValueError("artifact paths must stay inside their source/archive root")
    return path


def _file(root: Path, relative: str) -> Path:
    parts = _relative(relative).parts
    path = root.joinpath(*parts)
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink() or is_junction(parent):
            raise ValueError("inventory does not follow source symlinks")
    if not path.resolve().is_relative_to(root):
        raise ValueError("source artifact escapes the package directory")
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("source artifacts must be regular files")
    return path


def _sha_file(path: Path, limit: int) -> tuple[str, int]:
    size = path.stat().st_size
    if size > limit:
        raise ValueError("artifact exceeds inventory size limit")
    fingerprint = hashlib.sha256()
    observed = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            observed += len(block)
            if observed > limit:
                raise ValueError("artifact exceeds inventory size limit")
            fingerprint.update(block)
    if observed != size:
        raise ValueError("artifact changed size while being inventoried")
    return fingerprint.hexdigest(), observed


def _inventory_digest(files: tuple[SourceFileEvidence, ...]) -> str:
    return hashlib.sha256(
        json.dumps(
            [item.model_dump(mode="json") for item in files],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _texts(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("project metadata collections must contain strings")
    return tuple(value)


def _readme(value: object) -> ReadmeMetadata | None:
    if value is None:
        return None
    if isinstance(value, str):
        _relative(value)
        content_type = {".md": "text/markdown", ".rst": "text/x-rst"}.get(Path(value).suffix)
        return ReadmeMetadata(file=value, inline_text=None, content_type=content_type)
    if isinstance(value, dict) and set(value) <= {"file", "text", "content-type"}:
        if ("file" in value) == ("text" in value) or "content-type" not in value:
            raise ValueError("readme table requires file or text and content-type")
        if "file" in value:
            _relative(value["file"])
        return ReadmeMetadata(
            file=value.get("file"),
            inline_text=value.get("text"),
            content_type=value["content-type"],
        )
    raise ValueError("invalid project readme metadata")


def _license(value: object) -> LicenseMetadata | None:
    if value is None:
        return None
    if isinstance(value, str):
        from packaging.licenses import canonicalize_license_expression

        return LicenseMetadata(
            expression=canonicalize_license_expression(value), file=None, text=None
        )
    if isinstance(value, dict) and set(value) in ({"file"}, {"text"}):
        if "file" in value:
            _relative(value["file"])
        return LicenseMetadata(expression=None, file=value.get("file"), text=value.get("text"))
    raise ValueError("invalid project license metadata")


def _source(
    root: Path, wheel: WheelDistributionMetadata | None = None
) -> tuple[ProjectDistributionMetadata, tuple[SourceFileEvidence, ...]]:
    from packaging.version import Version

    pyproject = _file(root, "pyproject.toml")
    if pyproject.stat().st_size > MAX_METADATA_BYTES:
        raise ValueError("project metadata exceeds inventory size limit")
    pyproject_bytes = pyproject.read_bytes()
    parsed = tomllib.loads(pyproject_bytes.decode("utf-8", errors="strict"))
    project = parsed.get("project")
    if not isinstance(project, dict):
        raise ValueError("pyproject requires a static project table")
    dynamic = _texts(project.get("dynamic", []))
    if any(
        key in dynamic
        for key in ("name", "dependencies", "optional-dependencies", "requires-python")
    ):
        raise ValueError("dynamic metadata cannot be verified without executing a backend")
    if not isinstance(project.get("name"), str):
        raise ValueError("project name must be a string")
    name = project["name"]
    pkg_info_bytes = None
    if "version" in dynamic:
        if "version" in project:
            raise ValueError("project version cannot be both static and dynamic")
        if wheel is not None and wheel.canonical_name != _name(name):
            raise ValueError("identified wheel name disagrees with dynamic project")
        pkg_info = root / "PKG-INFO"
        if pkg_info.exists() or pkg_info.is_symlink():
            pkg_info = _file(root, "PKG-INFO")
            if pkg_info.stat().st_size > MAX_METADATA_BYTES:
                raise ValueError("sdist metadata exceeds inventory size limit")
            with pkg_info.open("rb") as stream:
                pkg_info_bytes = stream.read(MAX_METADATA_BYTES + 1)
            if len(pkg_info_bytes) > MAX_METADATA_BYTES:
                raise ValueError("sdist metadata exceeds inventory size limit")
            message = _headers(pkg_info_bytes)
            if _name(_required(message, "Name")) != _name(name):
                raise ValueError("sdist metadata name disagrees with dynamic project")
            version = str(Version(_required(message, "Version")))
            if wheel is not None and version != wheel.version:
                raise ValueError("sdist metadata version disagrees with identified wheel")
        elif wheel is not None:
            version = wheel.version
        else:
            raise ValueError(
                "dynamic version requires identified wheel or sdist PKG-INFO; "
                "it cannot be verified without executing a backend"
            )
    else:
        if not isinstance(project.get("version"), str):
            raise ValueError("project static version must be a string")
        version = str(Version(project["version"]))
    dependencies = tuple(sorted(_requirement(s) for s in _texts(project.get("dependencies", []))))
    optional = project.get("optional-dependencies", {})
    urls = project.get("urls", {})
    if not isinstance(optional, dict) or not isinstance(urls, dict):
        raise ValueError("optional dependencies and project URLs must be tables")
    optional_rows = tuple(
        sorted(
            (
                OptionalDependencies(
                    extra=_name(extra),
                    requirements=tuple(sorted(_requirement(s) for s in _texts(requirements))),
                )
                for extra, requirements in optional.items()
            ),
            key=lambda row: row.extra,
        )
    )
    readme = _readme(project.get("readme"))
    license_metadata = _license(project.get("license"))
    patterns = _texts(
        project.get("license-files", ["LICENSE*", "LICENCE*", "COPYING*", "NOTICE*", "AUTHORS*"])
    )
    licenses: set[str] = set()
    for pattern in patterns:
        _relative(pattern, pattern=True)
        for match in root.glob(pattern):
            relative = match.relative_to(root).as_posix()
            _file(root, relative)
            licenses.add(relative)
    if (
        license_metadata is not None
        and license_metadata.file is not None
        and root.joinpath(license_metadata.file).exists()
    ):
        licenses.add(license_metadata.file)
    files: set[str] = {"pyproject.toml"}
    if pkg_info_bytes is not None:
        files.add("PKG-INFO")
    if (root / "uv.lock").exists():
        files.add("uv.lock")
    if readme is not None and readme.file is not None and root.joinpath(readme.file).exists():
        files.add(readme.file)
    files.update(licenses)
    source = root / "src"
    if source.is_symlink() or is_junction(source):
        raise ValueError("inventory does not follow a source-directory symlink")
    if source.exists():
        for scanned, path in enumerate(source.rglob("*"), start=1):
            if scanned > MAX_MEMBERS:
                raise ValueError("source inventory exceeds entry count limit")
            if path.is_symlink() or is_junction(path):
                raise ValueError("inventory does not follow source symlinks")
            if path.is_file() and "__pycache__" not in path.parts:
                files.add(path.relative_to(root).as_posix())
            if len(files) > MAX_MEMBERS:
                raise ValueError("source inventory exceeds file count limit")
    if len(files) > MAX_MEMBERS:
        raise ValueError("source inventory exceeds file count limit")
    collected: list[SourceFileEvidence] = []
    total = 0
    for relative in sorted(files):
        fingerprint, size = _sha_file(
            _file(root, relative),
            min(MAX_SOURCE_FILE, MAX_SOURCE_TOTAL - total),
        )
        total += size
        collected.append(
            SourceFileEvidence(relative_path=relative, sha256=fingerprint, size_bytes=size)
        )
    evidence = tuple(collected)
    if next(item.sha256 for item in evidence if item.relative_path == "pyproject.toml") != (
        hashlib.sha256(pyproject_bytes).hexdigest()
    ):
        raise ValueError("project metadata changed while being inventoried")
    metadata = ProjectDistributionMetadata(
        name=name,
        canonical_name=_name(name),
        version=version,
        requires_python=_spec(project["requires-python"]) if "requires-python" in project else None,
        dependencies=dependencies,
        optional_dependencies=optional_rows,
        classifiers=tuple(sorted(_texts(project.get("classifiers", [])))),
        urls=tuple(ProjectURL(label=label, url=url) for label, url in sorted(urls.items())),
        readme=readme,
        license=license_metadata,
        license_file_patterns=patterns,
        license_files=tuple(sorted(licenses)),
        typed_markers=tuple(
            relative for relative in sorted(files) if relative.endswith("/py.typed")
        ),
    )
    if pkg_info_bytes is not None:
        if next(item.sha256 for item in evidence if item.relative_path == "PKG-INFO") != (
            hashlib.sha256(pkg_info_bytes).hexdigest()
        ):
            raise ValueError("sdist metadata changed while being inventoried")
        _check_pkg_info(metadata, _headers(pkg_info_bytes))
    return metadata, evidence


def _headers(data: bytes) -> Message:
    data.decode("utf-8", errors="strict")
    parsed = BytesParser(policy=policy.compat32).parsebytes(data)
    if parsed.defects:
        raise ValueError("malformed email-formatted distribution metadata")
    return parsed


def _single(message: Message, field: str, *, required: bool = True) -> str | None:
    values = message.get_all(field, [])
    if len(values) > 1 or (required and len(values) != 1):
        raise ValueError(f"metadata requires exactly one {field} header")
    return str(values[0]).strip() if values else None


def _required(message: Message, field: str) -> str:
    value = _single(message, field)
    if value is None or not value:
        raise ValueError(f"missing required {field} metadata")
    return value


def _members(archive: ZipFile) -> tuple[ZipInfo, ...]:
    members = tuple(archive.infolist())
    if not members or len(members) > MAX_MEMBERS:
        raise ValueError("wheel archive exceeds member count limit")
    names: set[str] = set()
    total = 0
    for member in members:
        # ZipInfo normalizes backslashes to slashes on Windows. Check the raw
        # central-directory spelling as well, before accepting a portable path.
        original = member.orig_filename
        _relative(original.rstrip("/") if member.is_dir() else original)
        _relative(member.filename.rstrip("/") if member.is_dir() else member.filename)
        if member.filename in names:
            raise ValueError("wheel archive contains duplicate paths")
        names.add(member.filename)
        if member.flag_bits & 1 or stat.S_ISLNK(member.external_attr >> 16):
            raise ValueError("encrypted and symlink wheel members are unsupported")
        total += member.file_size
        if total > MAX_ARCHIVE_EXPANDED:
            raise ValueError("wheel archive exceeds expanded size limit")
    return members


def _read_member(archive: ZipFile, name: str) -> bytes:
    entry = archive.getinfo(name)
    if entry.file_size > MAX_METADATA_BYTES:
        raise ValueError("wheel metadata exceeds inventory size limit")
    with archive.open(entry) as stream:
        data = stream.read(MAX_METADATA_BYTES + 1)
    if len(data) != entry.file_size or len(data) > MAX_METADATA_BYTES:
        raise ValueError("wheel metadata size does not match its directory entry")
    return data


def _wheel(path: Path) -> WheelDistributionMetadata:
    from packaging.tags import parse_tag
    from packaging.utils import parse_wheel_filename
    from packaging.version import Version

    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("wheel must be a regular file")
    wheel_sha, size = _sha_file(path, MAX_ARCHIVE_BYTES)
    with ZipFile(path) as archive:
        members = _members(archive)
        names = {item.filename for item in members}
        metadata_paths = tuple(name for name in names if name.endswith(".dist-info/METADATA"))
        if len(metadata_paths) != 1:
            raise ValueError("wheel requires exactly one dist-info METADATA document")
        metadata_path = metadata_paths[0]
        prefix = metadata_path.removesuffix("METADATA")
        if "/" in prefix.rstrip("/") or any(
            prefix + file not in names for file in ("RECORD", "WHEEL")
        ):
            raise ValueError("wheel requires a top-level dist-info directory and RECORD")
        metadata_bytes = _read_member(archive, metadata_path)
        wheel_bytes = _read_member(archive, prefix + "WHEEL")
        metadata = _headers(metadata_bytes)
        wheel = _headers(wheel_bytes)
        metadata_version = _required(metadata, "Metadata-Version")
        if metadata_version not in ("1.0", "1.1", "1.2", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6"):
            raise ValueError("unsupported distribution Metadata-Version")
        wheel_version = _required(wheel, "Wheel-Version")
        if wheel_version != "1.0":
            raise ValueError("unsupported Wheel-Version")
        name = _required(metadata, "Name")
        canonical = _name(name)
        version = str(Version(_required(metadata, "Version")))
        directory_name, directory_version = prefix.removesuffix(".dist-info/").rsplit("-", 1)
        if _name(directory_name) != canonical or str(Version(directory_version)) != version:
            raise ValueError("dist-info directory disagrees with its name/version metadata")
        pure = _required(wheel, "Root-Is-Purelib")
        if pure not in ("true", "false"):
            raise ValueError("Root-Is-Purelib must be true or false")
        tags = tuple(sorted(str(value).strip() for value in wheel.get_all("Tag", [])))
        if any(
            len(tag.split("-")) != 3 or any(not part for part in tag.split("-")) for tag in tags
        ):
            raise ValueError("wheel tags require python-ABI-platform triples")
        filename_name, filename_version, _, filename_tags = parse_wheel_filename(path.name)
        if (
            filename_name != canonical
            or str(filename_version) != version
            or filename_tags != (frozenset(tag for text in tags for tag in parse_tag(text)))
        ):
            raise ValueError("wheel filename disagrees with its name/version/platform metadata")
        requires_python = _single(metadata, "Requires-Python", required=False)
        license_expression = _single(metadata, "License-Expression", required=False)
        license_text = _single(metadata, "License", required=False)
        if license_expression is not None and license_text is not None:
            raise ValueError("License and License-Expression are mutually exclusive")
        license_files = tuple(sorted(str(v).strip() for v in metadata.get_all("License-File", [])))
        for filename in license_files:
            _relative(filename)
            if prefix + "licenses/" + filename not in names and prefix + filename not in names:
                raise ValueError("wheel declares a missing license file")
        for filename in names:
            if filename.endswith("/py.typed"):
                _read_member(archive, filename)
        urls: list[ProjectURL] = []
        for value in metadata.get_all("Project-URL", []):
            label, separator, url = str(value).partition(",")
            if not separator:
                raise ValueError("Project-URL metadata requires label and URL")
            urls.append(ProjectURL(label=label.strip(), url=url.strip()))
        result = WheelDistributionMetadata(
            wheel_sha256=wheel_sha,
            wheel_size_bytes=size,
            metadata_sha256=hashlib.sha256(metadata_bytes).hexdigest(),
            wheel_metadata_sha256=hashlib.sha256(wheel_bytes).hexdigest(),
            metadata_version=metadata_version,
            name=name,
            canonical_name=canonical,
            version=version,
            requires_python=_spec(requires_python) if requires_python is not None else None,
            dependencies=tuple(
                sorted(_requirement(str(v)) for v in metadata.get_all("Requires-Dist", []))
            ),
            extras=tuple(sorted(_name(str(v)) for v in metadata.get_all("Provides-Extra", []))),
            classifiers=tuple(sorted(str(v).strip() for v in metadata.get_all("Classifier", []))),
            urls=tuple(sorted(urls, key=lambda item: item.label)),
            license_expression=license_expression,
            license_text=license_text,
            license_files=license_files,
            typed_markers=tuple(sorted(name for name in names if name.endswith("/py.typed"))),
            wheel_version="1.0",
            root_is_purelib=pure == "true",
            tags=tags,
            member_count=len(members),
            expanded_size_bytes=sum(item.file_size for item in members),
        )
    if _sha_file(path, MAX_ARCHIVE_BYTES) != (wheel_sha, size):
        raise ValueError("wheel changed while being inventoried")
    return result


def _check_wheel(project: ProjectDistributionMetadata, wheel: WheelDistributionMetadata) -> None:
    expected = list(project.dependencies)
    for optional in project.optional_dependencies:
        expected.extend(
            _optional_requirement(requirement, optional.extra)
            for requirement in optional.requirements
        )
    if (
        project.canonical_name != wheel.canonical_name
        or project.version != wheel.version
        or project.requires_python != wheel.requires_python
        or tuple(sorted(expected)) != wheel.dependencies
        or tuple(item.extra for item in project.optional_dependencies) != wheel.extras
        or project.classifiers != wheel.classifiers
        or project.urls != wheel.urls
    ):
        raise ValueError(
            "wheel metadata disagrees with project name/version/dependencies/Python/URLs"
        )
    markers = tuple(path.removeprefix("src/") for path in project.typed_markers)
    if markers != wheel.typed_markers:
        raise ValueError("wheel typing markers disagree with source")
    if project.license_files != wheel.license_files:
        raise ValueError("wheel license files disagree with source inventory")
    license_metadata = project.license
    expected_expression = license_metadata.expression if license_metadata is not None else None
    if expected_expression != wheel.license_expression:
        raise ValueError("wheel license expression disagrees with project")
    if (license_metadata is None and wheel.license_text is not None) or (
        license_metadata is not None
        and license_metadata.text is not None
        and license_metadata.text != wheel.license_text
    ):
        raise ValueError("wheel license text disagrees with project")


def _check_pkg_info(project: ProjectDistributionMetadata, message: Message) -> None:
    """Bind passive sdist metadata to every inventoried declaration, without execution."""
    from packaging.version import Version

    if _required(message, "Metadata-Version") not in (
        "1.0",
        "1.1",
        "1.2",
        "2.1",
        "2.2",
        "2.3",
        "2.4",
        "2.5",
        "2.6",
    ):
        raise ValueError("unsupported sdist Metadata-Version")
    for value in message.get_all("Dynamic", []):
        field = str(value).strip().lower()
        if re.fullmatch(r"[a-z][a-z0-9-]*", field) is None or field in {
            "name",
            "version",
            "requires-dist",
            "provides-extra",
            "requires-python",
            "classifier",
            "project-url",
            "license",
            "license-expression",
            "license-file",
        }:
            raise ValueError("sdist metadata retains an unresolved inventoried field")
    expected = list(project.dependencies)
    for optional in project.optional_dependencies:
        expected.extend(
            _optional_requirement(requirement, optional.extra)
            for requirement in optional.requirements
        )
    urls = []
    for value in message.get_all("Project-URL", []):
        label, separator, url = str(value).partition(",")
        if not separator:
            raise ValueError("sdist Project-URL metadata requires label and URL")
        urls.append(ProjectURL(label=label.strip(), url=url.strip()))
    requires_python = _single(message, "Requires-Python", required=False)
    if (
        project.canonical_name != _name(_required(message, "Name"))
        or project.version != str(Version(_required(message, "Version")))
        or project.requires_python != (_spec(requires_python) if requires_python else None)
        or tuple(sorted(expected))
        != tuple(sorted(_requirement(str(value)) for value in message.get_all("Requires-Dist", [])))
        or tuple(item.extra for item in project.optional_dependencies)
        != tuple(sorted(_name(str(value)) for value in message.get_all("Provides-Extra", [])))
        or project.classifiers
        != tuple(sorted(str(value).strip() for value in message.get_all("Classifier", [])))
        or project.urls != tuple(sorted(urls, key=lambda item: item.label))
    ):
        raise ValueError("sdist metadata disagrees with project declarations")
    license_metadata = project.license
    expression = license_metadata.expression if license_metadata is not None else None
    license_text = _single(message, "License", required=False)
    if (
        expression != _single(message, "License-Expression", required=False)
        or (expression is not None and license_text is not None)
        or (license_metadata is None and license_text is not None)
        or (
            license_metadata is not None
            and license_metadata.file is not None
            and license_text is not None
        )
        or (
            license_metadata is not None
            and license_metadata.text is not None
            and license_metadata.text != license_text
        )
        or project.license_files
        != tuple(sorted(str(value).strip() for value in message.get_all("License-File", [])))
    ):
        raise ValueError("sdist license metadata disagrees with project")


def _pending(
    project: ProjectDistributionMetadata,
    files: dict[str, SourceFileEvidence],
    wheel: WheelDistributionMetadata | None,
    name_check: NameCheck,
) -> tuple[str, ...]:
    pending: list[str] = []
    readme = project.readme
    if readme is None or (
        readme.file is not None and (readme.file not in files or files[readme.file].size_bytes == 0)
    ):
        pending.append("pending_readme")
    if "uv.lock" not in files or files["uv.lock"].size_bytes == 0:
        pending.append("pending_lock")
    if project.requires_python is None:
        pending.append("pending_requires_python")
    if not project.typed_markers:
        pending.append("pending_typing_marker")
    if project.license is None or not any(files[name].size_bytes for name in project.license_files):
        pending.append("pending_license")
    if not name_check.controlled:
        pending.append("pending_pypi_name_control")
    if wheel is None:
        pending.append("pending_wheel_metadata")
    pending.extend(
        ("pending_build_install_verification", "pending_current_release_platform_matrix")
    )
    return tuple(pending)


def inspect_distribution(
    package_directory: Path,
    wheel_path: Path | None = None,
    *,
    name_check: NameCheck | None = None,
) -> DistributionReadiness:
    """Inventory local source/wheel without fetching, building or importing the package.

    A dynamic version requires an identified wheel or an extracted sdist's
    concordant PKG-INFO. Their passive metadata does not authenticate a release;
    all existing build, platform and publication gates remain pending.
    """
    if package_directory.is_symlink() or not package_directory.is_dir():
        raise ValueError("package directory must be a real directory")
    root = package_directory.resolve()
    wheel = _wheel(wheel_path) if wheel_path is not None else None
    project, files = _source(root, wheel)
    observed = (
        NameCheck.model_validate(name_check)
        if name_check is not None
        else NameCheck(
            name=project.name,
            query_url=f"https://pypi.org/pypi/{project.canonical_name}/json",
            fetched_at=None,
            http_status=None,
            status="unknown",
        )
    )
    inventory = {item.relative_path: item for item in files}
    pending = _pending(project, inventory, wheel, observed)
    return DistributionReadiness(
        package_directory=str(root),
        project=project,
        source_files=files,
        source_manifest_sha256=_inventory_digest(files),
        lock_sha256=inventory["uv.lock"].sha256 if "uv.lock" in inventory else None,
        wheel=wheel,
        name_check=observed,
        pending_conditions=pending,
        wheel_metadata_verified=wheel is not None,
        technical_inventory_complete=not any(
            condition in pending
            for condition in (
                "pending_readme",
                "pending_lock",
                "pending_requires_python",
                "pending_typing_marker",
            )
        ),
    )
