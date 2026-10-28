"""Identify candidate artifacts and executed checks; never publish or assign a license."""

import argparse
import hashlib
import importlib.metadata
import io
import json
import platform
import re
import runpy
import subprocess
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from datetime import datetime
from datetime import timezone as _timezone
from pathlib import Path, PurePosixPath
from typing import Any

UTC = _timezone.utc

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CHECK_STAGES = (
    "locked_sync",
    "ruff_check",
    "ruff_format",
    "mypy",
    "assets",
    "pytest",
    "build",
    "twine",
    "distribution",
)


def project_version(package: Path, *, require_tag: bool = False) -> str:
    """Load the fixed, repository-owned version resolver without importing the library."""
    namespace = runpy.run_path(str(Path(__file__).with_name("release_version.py")))
    value = namespace["project_version"](package, require_tag=require_tag)
    if not isinstance(value, str):
        raise ValueError("project version resolver must return text")
    return value


def repository_root(package: Path) -> Path:
    """Resolve the real checkout independently of a package's directory depth."""
    return Path(git_output(package, "rev-parse", "--show-toplevel")).resolve()


def source_snapshot(package: Path) -> dict[str, Any]:
    """Identify tested worktree bytes, including locally resolved dependencies."""
    repository = repository_root(package)
    pending = [package.resolve()]
    visited: set[Path] = set()
    inventory: dict[str, str] = {}
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        if not current.is_relative_to(repository):
            raise SystemExit("local check dependencies must belong to the source repository")
        visited.add(current)
        relative = current.relative_to(repository).as_posix()
        paths = git_output(
            repository,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            ":(literal)" + relative,
        ).split("\0")
        for name in paths:
            if not name:
                continue
            file = repository / name
            if file.is_symlink() or not file.is_file():
                raise SystemExit("check source must contain regular existing files: " + name)
            inventory[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        project = tomllib.loads((current / "pyproject.toml").read_text(encoding="utf-8"))
        sources = project.get("tool", {}).get("uv", {}).get("sources", {})
        for source in sources.values():
            if isinstance(source, list):
                raise SystemExit(
                    "conditional uv sources require explicit candidate binding support"
                )
            if isinstance(source, dict) and isinstance(source.get("path"), str):
                pending.append((current / source["path"]).resolve())
    encoded = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "algorithm": "sha256-git-worktree-v1",
        "packages": sorted(path.relative_to(repository).as_posix() for path in visited),
        "file_count": len(inventory),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def require_canonical_git_bytes(package: Path) -> None:
    """Reject clean filter/EOL conversions instead of attributing them to HEAD.

    Worktree snapshots remain useful for dirty-source diagnostics. A release
    candidate additionally requires raw bytes equal to its committed blobs.
    Read those blobs in one batch; filenames never become batch instructions.
    """
    repository = repository_root(package)
    head = git_output(package, "rev-parse", "--verify", "HEAD^{commit}")
    scopes = source_snapshot(package)["packages"]

    def output(*arguments: str, data: bytes | None = None) -> bytes:
        result = subprocess.run(
            ["git", *arguments], cwd=repository, input=data, capture_output=True, check=False
        )
        if result.returncode:
            raise SystemExit("Git canonical source bytes cannot be verified")
        return result.stdout

    prefixes = [scope.encode("utf-8") for scope in scopes]
    committed: dict[str, bytes] = {}
    for entry in output("ls-tree", "-r", "-z", "--full-tree", head).split(b"\0"):
        if not entry:
            continue
        metadata, separator, raw_name = entry.partition(b"\t")
        if not separator:
            raise SystemExit("Git canonical source inventory is malformed")
        if not any(
            prefix == b"." or raw_name == prefix or raw_name.startswith(prefix + b"/")
            for prefix in prefixes
        ):
            continue
        mode, kind, oid = metadata.split()
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            raise SystemExit("Git canonical source must contain regular files")
        committed[raw_name.decode("utf-8")] = oid
    current = {
        name.decode("utf-8")
        for name in output(
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            *(":(literal)" + scope for scope in scopes),
        ).split(b"\0")
        if name
    }
    if current != set(committed):
        raise SystemExit(
            "check source paths must match Git HEAD before canonical byte verification"
        )
    objects = list(dict.fromkeys(committed.values()))
    stream = io.BytesIO(output("cat-file", "--batch", data=b"\n".join(objects) + b"\n"))
    fingerprints: dict[bytes, str] = {}
    for oid in objects:
        header = stream.readline().split()
        if len(header) != 3 or header[:2] != [oid, b"blob"] or not header[2].isdigit():
            raise SystemExit("Git canonical blob batch is malformed")
        size = int(header[2])
        blob = stream.read(size)
        if len(blob) != size or stream.read(1) != b"\n":
            raise SystemExit("Git canonical blob batch is incomplete")
        fingerprints[oid] = hashlib.sha256(blob).hexdigest()
    if stream.read(1):
        raise SystemExit("Git canonical blob batch contains unexpected bytes")
    for name, oid in committed.items():
        file = repository / name
        if file.is_symlink() or not file.is_file():
            raise SystemExit("check source must contain regular existing files: " + name)
        if hashlib.sha256(file.read_bytes()).hexdigest() != fingerprints[oid]:
            raise SystemExit("raw worktree bytes differ from Git HEAD blob: " + name)
    if git_output(package, "rev-parse", "--verify", "HEAD^{commit}") != head:
        raise SystemExit("Git HEAD changed during canonical byte verification")


def local_dependency_names(package: Path) -> list[str]:
    """Distribution names in the same local source closure used by receipts."""
    repository = Path(git_output(package, "rev-parse", "--show-toplevel")).resolve()
    names = []
    for relative in source_snapshot(package)["packages"]:
        dependency = repository / relative
        if dependency == package.resolve():
            continue
        project = tomllib.loads((dependency / "pyproject.toml").read_text("utf-8"))["project"]
        name = project["name"]
        if (
            not isinstance(name, str)
            or re.fullmatch(r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*", name) is None
        ):
            raise SystemExit("invalid local dependency distribution name")
        names.append(re.sub(r"[-_.]+", "-", name).lower())
    if len(names) != len(set(names)):
        raise SystemExit("local dependency distribution names must be unique")
    return sorted(names)


def included_runtime_sources(
    repository: Path, dependency: Path, imports: set[str]
) -> dict[str, dict[str, str]]:
    """Bind explicitly packaged Python examples as strictly as src-layout modules.

    Only Git-visible files and declarative in-package wheel mappings are supported.
    No configuration callback or example code is executed to discover these bytes.
    """
    config = tomllib.loads((dependency / "pyproject.toml").read_text("utf-8"))
    mappings = (
        config.get("tool", {})
        .get("hatch", {})
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    result: dict[str, dict[str, str]] = {}
    for source_name, destination_name in mappings.items():
        destination = PurePosixPath(destination_name)
        source_root = (dependency / source_name).resolve()
        if (
            not source_root.is_relative_to(dependency)
            or destination.is_absolute()
            or ".." in destination.parts
            or not destination.parts
            or destination.parts[0] not in imports
        ):
            raise SystemExit("local dependency wheel inclusion needs an in-package mapping")
        relative = source_root.relative_to(repository).as_posix()
        for name in git_output(
            repository,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            ":(literal)" + relative,
        ).split("\0"):
            if not name:
                continue
            source = repository / name
            if source.suffix not in {".py", ".pyi", ".so", ".pyd"}:
                continue
            installed = (
                destination
                if source_root.is_file()
                else destination / source.relative_to(source_root)
            )
            key = PurePosixPath(*installed.parts[1:]).as_posix()
            result.setdefault(installed.parts[0], {})[key] = hashlib.sha256(
                source.read_bytes()
            ).hexdigest()
    return result


def local_dependency_sources(package: Path) -> list[dict[str, Any]]:
    """Enumerate Git-visible runtime files, without executing configuration code.

    This bounded checker supports ordinary src-layout Python packages. Other
    layouts need explicit support rather than silently omitting their bytes.
    """
    repository = Path(git_output(package, "rev-parse", "--show-toplevel")).resolve()
    dependencies = []
    for relative in source_snapshot(package)["packages"]:
        dependency = repository / relative
        if dependency == package.resolve():
            continue
        project = tomllib.loads((dependency / "pyproject.toml").read_text("utf-8"))["project"]
        files: dict[str, dict[str, str]] = {}
        for name in git_output(
            repository,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            ":(literal)" + relative + "/src",
        ).split("\0"):
            if not name:
                continue
            source = repository / name
            local = source.relative_to(dependency / "src")
            import_name = local.parts[0]
            if (
                len(local.parts) < 2
                or not import_name.isidentifier()
                or not (dependency / "src" / import_name / "__init__.py").is_file()
            ):
                raise SystemExit("local dependency binding requires regular src-layout packages")
            files.setdefault(import_name, {})[Path(*local.parts[1:]).as_posix()] = hashlib.sha256(
                source.read_bytes()
            ).hexdigest()
        if not files:
            raise SystemExit("local dependency has no Git-visible src package files")
        for name, included in included_runtime_sources(repository, dependency, set(files)).items():
            for target, fingerprint in included.items():
                if target in files[name] and files[name][target] != fingerprint:
                    raise SystemExit("local dependency wheel mapping replaces src bytes")
                files[name][target] = fingerprint
        dependencies.append(
            {
                "distribution": re.sub(r"[-_.]+", "-", project["name"]).lower(),
                "source_package": relative,
                "imports": [
                    {"name": name, "files": dict(sorted(values.items()))}
                    for name, values in sorted(files.items())
                ],
            }
        )
    return dependencies


def runtime_binding_matches(binding: Any, package: Path) -> bool:
    """A source-only receipt never proves which local dependency bytes resolved."""
    if not isinstance(binding, dict):
        return False
    if (
        binding.get("algorithm") != "sha256-imported-local-source-v1"
        or binding.get("verified") is not True
        or binding.get("source_dependencies") != local_dependency_sources(package)
        or binding.get("source_snapshot") != source_snapshot(package)
    ):
        return False
    observed = binding.get("resolved_dependencies")
    expected = binding["source_dependencies"]
    if not isinstance(observed, list) or len(observed) != len(expected):
        return False
    for dependency, source in zip(observed, expected, strict=True):
        if (
            not isinstance(dependency, dict)
            or dependency.get("distribution") != source["distribution"]
        ):
            return False
        imports = dependency.get("imports")
        if not isinstance(imports, list) or len(imports) != len(source["imports"]):
            return False
        for imported, wanted in zip(imports, source["imports"], strict=True):
            if not isinstance(imported, dict):
                return False
            origin, root = imported.get("origin"), imported.get("root")
            if (
                imported.get("name") != wanted["name"]
                or imported.get("files") != wanted["files"]
                or not isinstance(origin, str)
                or not isinstance(root, str)
                or not Path(root).is_absolute()
                or origin != str(Path(root) / "__init__.py")
            ):
                return False
    return True


def artifact_inventory(paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    return [
        {
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in paths
        if path.is_file()
    ]


def dependency_artifacts(package: Path) -> tuple[Path, ...]:
    """Wheels consumed by installed tests for locally resolved dependencies."""
    repository = Path(git_output(package, "rev-parse", "--show-toplevel")).resolve()
    paths = []
    for relative in source_snapshot(package)["packages"]:
        dependency = repository / relative
        if dependency.resolve() == package.resolve():
            continue
        project = tomllib.loads((dependency / "pyproject.toml").read_text("utf-8"))["project"]
        stem = (
            project["name"].replace("-", "_") + "-" + project_version(dependency, require_tag=True)
        )
        paths.append(dependency / "dist" / (stem + "-py3-none-any.whl"))
    return tuple(paths)


def git_output(directory: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as error:
        raise SystemExit("Git source cannot be verified: git executable unavailable") from error
    if result.returncode:
        raise SystemExit("Git source cannot be verified: a tracked Git package is required")
    return result.stdout.strip()


def verified_source_commit(package: Path, requested: str | None) -> str:
    repository = Path(git_output(package, "rev-parse", "--show-toplevel")).resolve()
    head = git_output(package, "rev-parse", "--verify", "HEAD^{commit}")
    commit = requested if requested is not None else head
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise SystemExit("commit must be an exact 40-character source revision")
    if commit != head:
        raise SystemExit("commit must identify the verified package Git HEAD exactly")
    for relative in source_snapshot(package)["packages"]:
        project = (Path(relative) / "pyproject.toml").as_posix()
        git_output(repository, "ls-files", "--error-unmatch", "--", project)
        status = git_output(
            repository,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            ":(literal)" + relative,
        )
        if status:
            raise SystemExit(
                "verified package and local dependencies must have no tracked changes "
                "or untracked source files"
            )
    require_canonical_git_bytes(package)
    return commit


def command_parts(command: list[str], package: Path) -> tuple[str, list[str]] | None:
    program = Path(command[0]).name.lower().removesuffix(".exe")
    arguments = command[1:]
    if program == "uv":
        if arguments and arguments[0] == "sync":
            return "locked_sync", arguments[1:]
        if not arguments or arguments[0] != "run":
            return None
        arguments = arguments[1:]
        while arguments and arguments[0] in {
            "--locked",
            "--all-extras",
            "--frozen",
            "--no-sync",
            "--python",
        }:
            if arguments[0] == "--python":
                if len(arguments) < 2 or not arguments[1] or arguments[1].startswith("-"):
                    return None
                arguments = arguments[2:]
            else:
                arguments = arguments[1:]
        if not arguments:
            return None
        program = Path(arguments[0]).name.lower().removesuffix(".exe")
        arguments = arguments[1:]
    if program in {"python", "python3", "python3.10", "python3.11", "python3.12", "python3.13"}:
        while arguments and arguments[0] in {"-I", "-B", "-u"}:
            arguments = arguments[1:]
        if len(arguments) >= 2 and arguments[0] == "-m":
            if arguments[1] in {"ruff", "mypy", "pytest", "build", "twine"}:
                return arguments[1], arguments[2:]
            return None
        if not arguments:
            return None
        script = (package / arguments[0]).resolve()
        for name, stage in (
            ("generate_assets.py", "assets"),
            ("verify_distribution.py", "distribution"),
        ):
            if script == (package / "tools" / name).resolve():
                return stage, arguments[1:]
        return None
    if program in {"ruff", "mypy", "pytest", "twine"}:
        return program, arguments
    return None


def whole_pytest(arguments: list[str]) -> bool:
    """Allow operational flags, never a selected test, marker or expression."""
    positional = []
    quiet = False
    index = 0
    switches = {"-q", "--quiet", "-ra", "-rA", "-x", "--exitfirst", "--disable-warnings", "-s"}
    valued = {"--basetemp", "--tb", "--color", "--capture"}
    while index < len(arguments):
        value = arguments[index]
        if value in switches:
            quiet = quiet or value in {"-q", "--quiet"}
        elif value in valued:
            index += 1
            if index >= len(arguments) or arguments[index].startswith("-"):
                return False
        elif any(value.startswith(option + "=") and value != option + "=" for option in valued):
            pass
        elif value == "-p":
            index += 1
            if index >= len(arguments) or arguments[index] != "no:cacheprovider":
                return False
        elif value in {".", "tests"}:
            positional.append(value)
        else:
            return False
        index += 1
    return quiet and len(positional) <= 1


def check_stage(command: list[str], package: Path, artifacts: tuple[Path, ...]) -> str | None:
    parts = command_parts(command, package)
    if parts is None:
        return None
    program, arguments = parts
    if program == "locked_sync":
        remaining = arguments.copy()
        reinstall = []
        for option in ("--python", "--reinstall-package"):
            while option in remaining:
                index = remaining.index(option)
                if index + 1 >= len(remaining) or remaining[index + 1].startswith("-"):
                    return None
                value = remaining[index + 1]
                del remaining[index : index + 2]
                if option == "--reinstall-package":
                    reinstall.append(value)
                elif option in remaining:
                    return None
        if (
            sorted(remaining)
            in (["--all-extras", "--locked"], ["--all-extras", "--locked", "--no-editable"])
            and len(reinstall) == len(set(reinstall))
            and set(reinstall).issubset(
                {
                    tomllib.loads((package / "pyproject.toml").read_text("utf-8"))["project"][
                        "name"
                    ],
                    *local_dependency_names(package),
                }
            )
        ):
            return "locked_sync"
    elif program == "ruff":
        if arguments == ["check", "."]:
            return "ruff_check"
        if arguments == ["format", "--check", "."]:
            return "ruff_format"
    elif program == "mypy":
        arguments = arguments.copy()
        if "--python-version" in arguments:
            index = arguments.index("--python-version")
            if index + 1 >= len(arguments) or arguments[index + 1] not in {
                "3.10",
                "3.11",
                "3.12",
                "3.13",
            }:
                return None
            del arguments[index : index + 2]
            if "--python-version" in arguments:
                return None
        positional = [value for value in arguments if value not in {"--strict", "--no-incremental"}]
        if positional in ([], ["."]) or set(positional) == {"src", "tools"}:
            return "mypy"
    elif program == "assets" and arguments == ["--check"]:
        return "assets"
    elif program == "pytest" and whole_pytest(arguments):
        return "pytest"
    elif program == "build":
        if set(arguments) in ({"--no-isolation"}, {"--no-isolation", "--wheel", "--sdist"}):
            return "build"
    elif program == "twine" and arguments[:2] == ["check", "--strict"]:
        filenames = arguments[2:]
        if filenames and not any(value.startswith("-") for value in filenames):
            checked = {(package / value).resolve() for value in filenames}
            if set(artifacts).issubset(checked):
                return "twine"
    elif program == "distribution":
        remaining = arguments.copy()
        for option in ("--uv", "--qa-workspace"):
            if option in remaining:
                index = remaining.index(option)
                if (
                    index + 1 >= len(remaining)
                    or not remaining[index + 1]
                    or remaining[index + 1].startswith("-")
                ):
                    return None
                del remaining[index : index + 2]
        if not remaining:
            return "distribution"
    return None


def read_check_receipts(
    paths: list[Path], package: Path, artifacts: tuple[Path, ...]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    receipts = []
    successful: set[str] = set()
    bound: set[str] = set()
    runtime_bound: set[str] = set()
    current_source = source_snapshot(package)
    current_artifacts = artifact_inventory(artifacts)
    dependencies = dependency_artifacts(package)
    current_dependencies = artifact_inventory(dependencies)
    failed_commands = 0
    for path in paths:
        raw = path.read_bytes()
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise SystemExit("invalid check receipt")
        results = document.get("results")
        if not isinstance(results, list) or not results:
            raise SystemExit("check receipt requires executed commands")
        for check in results:
            if not isinstance(check, dict):
                raise SystemExit("invalid check receipt")
            command, exit_code, cwd = check.get("command"), check.get("exit_code"), check.get("cwd")
            if (
                type(exit_code) is not int
                or not isinstance(command, list)
                or not command
                or not all(isinstance(value, str) and value for value in command)
            ):
                raise SystemExit("invalid check receipt")
            if (
                not isinstance(cwd, str)
                or not Path(cwd).is_absolute()
                or Path(cwd).resolve() != package
            ):
                raise SystemExit("check receipt cwd must identify the verified package exactly")
            if exit_code:
                failed_commands += 1
            else:
                stage = check_stage(command, package, artifacts)
                if stage is not None:
                    successful.add(stage)
                    if not dependencies or runtime_binding_matches(
                        check.get("local_dependency_runtime_binding"), package
                    ):
                        runtime_bound.add(stage)
                    before, after = check.get("source_before"), check.get("source_after")
                    if (
                        before == current_source
                        and after == current_source
                        and (
                            stage not in {"build", "twine", "distribution"}
                            or check.get("artifacts") == current_artifacts
                        )
                        and (
                            stage not in {"twine", "distribution"}
                            or check.get("artifacts_before") == current_artifacts
                        )
                        and (
                            stage != "distribution"
                            or (
                                len(current_dependencies) == len(dependencies)
                                and check.get("dependency_artifacts") == current_dependencies
                                and check.get("dependency_artifacts_before") == current_dependencies
                            )
                        )
                    ):
                        bound.add(stage)
        receipts.append(
            {
                "file": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "results": results,
                "environment": document.get("environment"),
            }
        )
    completion = {
        "required_stages": list(REQUIRED_CHECK_STAGES),
        "successful_stages": [stage for stage in REQUIRED_CHECK_STAGES if stage in successful],
        "missing_stages": [stage for stage in REQUIRED_CHECK_STAGES if stage not in successful],
        "failed_commands": failed_commands,
        "source_snapshot": current_source,
        "dependency_artifacts": current_dependencies,
        "source_bound_stages": [stage for stage in REQUIRED_CHECK_STAGES if stage in bound],
        "unbound_stages": [stage for stage in REQUIRED_CHECK_STAGES if stage not in bound],
        "local_dependency_runtime_bound_stages": [
            stage for stage in REQUIRED_CHECK_STAGES if stage in runtime_bound
        ],
        "local_dependency_runtime_unbound_stages": [
            stage for stage in REQUIRED_CHECK_STAGES if stage not in runtime_bound
        ]
        if dependencies
        else [],
        "receipts_authenticated": False,
    }
    return receipts, completion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=ROOT)
    parser.add_argument("--checks", type=Path, action="append", default=[])
    parser.add_argument("--commit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    project = tomllib.loads((package / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    name, version = project["name"], project_version(package, require_tag=True)
    stem = name.replace("-", "_")
    artifacts = (
        package / "dist" / f"{stem}-{version}-py3-none-any.whl",
        package / "dist" / f"{stem}-{version}.tar.gz",
    )
    if not all(path.is_file() for path in artifacts):
        raise SystemExit("build the identified wheel and sdist first")
    commit = verified_source_commit(package, args.commit)
    receipts, completion = read_check_receipts(args.checks, package, artifacts)
    # This artifact manifest does not inspect accounts, public access or owner
    # instructions. The external factual packet is checked per index by
    # verify_publication; do not manufacture pending facts or accept them here.
    blockers: list[str] = []
    if not project.get("license"):
        blockers.insert(0, "author-approved license and redistribution terms absent")
    if completion["missing_stages"]:
        blockers.append(
            "complete successful execution receipts absent; missing stages: "
            + ", ".join(completion["missing_stages"])
        )
    if completion["failed_commands"]:
        blockers.append("one or more supplied execution receipts records a failed command")
    if completion["unbound_stages"]:
        blockers.append(
            "checks are not bound to current source/artifact bytes; stages: "
            + ", ".join(completion["unbound_stages"])
        )
    if completion["local_dependency_runtime_unbound_stages"]:
        blockers.append(
            "local dependency imported bytes are not bound to current source; stages: "
            + ", ".join(completion["local_dependency_runtime_unbound_stages"])
        )
    tools = {tool: importlib.metadata.version(tool) for tool in ("build", "hatchling", "twine")}
    if "version" in project.get("dynamic", []):
        tools.update(
            {tool: importlib.metadata.version(tool) for tool in ("hatch-vcs", "setuptools-scm")}
        )
    manifest = {
        "schema_version": "1.0",
        "distribution": name,
        "version": version,
        "source_commit": commit,
        "source_validation": {"git_head": commit, "package_clean": True, "project_tracked": True},
        "generated_at": datetime.now(UTC).isoformat(),
        "python_support": project["requires-python"],
        "environment": {"python": sys.version, "platform": platform.platform(), "tools": tools},
        "artifacts": artifact_inventory(artifacts),
        "checks": receipts,
        "check_completion": completion,
        "evidence_scope": {
            "source": "Git HEAD and clean package checked at manifest generation",
            "checks": "supplied command records; execution and identity are not authenticated",
            "artifacts": (
                "hashes and sizes identify current bytes; build origin is not authenticated"
            ),
        },
        "license": project.get("license"),
        "publication_blockers": blockers,
        "publication_readiness_evaluated": False,
        "publication_requirements": (
            "Run verify_publication with the current policy and an independently inspected "
            "exact-artifact factual packet for the selected index. A manifest does not "
            "authenticate authorization, account control, public documentation or security."
        ),
        "published": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n")
    except OSError:
        parser.exit(2, "Release manifest output requires a new writable file.\n")
    print(
        json.dumps(
            {
                "version": version,
                "artifacts": manifest["artifacts"],
                "publication_blockers": blockers,
            }
        )
    )


if __name__ == "__main__":
    main()
