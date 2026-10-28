"""Regular-file reads without following links or blocking on special files."""

from __future__ import annotations

import errno
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from equiframe.errors import ArtifactIntegrityError, ArtifactIOError


def absolute_path(
    path: Path, *, path_error: type[ArtifactIntegrityError] = ArtifactIntegrityError
) -> Path:
    if ".." in path.parts:
        raise path_error("parent traversal is not permitted")
    try:
        return path.absolute()
    except OSError as error:
        raise ArtifactIOError("cannot determine absolute evidence path") from error


def regular_directory(
    path: Path, *, path_error: type[ArtifactIntegrityError] = ArtifactIntegrityError
) -> Path:
    path = absolute_path(path, path_error=path_error)
    try:
        for item in (*reversed(path.parents), path):
            inspected = item.lstat()
            if not (
                stat.S_ISDIR(inspected.st_mode)
                and not getattr(inspected, "st_file_attributes", 0) & 0x400
            ):
                raise path_error("evidence directories must not be symlinks or reparse points")
    except OSError as error:
        raise ArtifactIOError("cannot inspect evidence directory") from error
    return path


def local_input_path(path: Path) -> Path:
    """Admit explicit local parent navigation after inspecting traversed directories.

    Evidence confinement still uses absolute_path and refuses parent navigation.
    This helper is for caller-selected local paths, which have no fixed root.
    """
    if not isinstance(path, Path):
        raise TypeError("local path must be a Path")
    path = path.absolute()
    current = Path(path.anchor)
    for component in path.parts[1:]:
        if component == "..":
            regular_directory(current)
            current = current.parent
        else:
            current = current / component
    return current


def new_directory_path(path: Path, *, ordinary_file_error: bool = False) -> Path:
    """Check existing lexical ancestors before creating a new output directory."""
    path = absolute_path(path)
    for item in (*reversed(path.parents), path):
        try:
            inspected = item.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise ArtifactIOError("cannot inspect output directory") from error
        if (
            ordinary_file_error
            and stat.S_ISREG(inspected.st_mode)
            and not (getattr(inspected, "st_file_attributes", 0) & 0x400)
        ):
            raise NotADirectoryError(errno.ENOTDIR, "operation output requires a directory")
        if not stat.S_ISDIR(inspected.st_mode) or (
            getattr(inspected, "st_file_attributes", 0) & 0x400
        ):
            raise ArtifactIntegrityError("output directories must not be links or special files")
    return path


def _walk_error(error: OSError) -> None:
    raise ArtifactIOError("cannot inventory evidence directory") from error


def local_output_directory(path: Path) -> Path:
    """Inspect caller-selected ancestors before normalizing a new operation root.

    Returning a path does not create directories or sandbox concurrent filesystem
    owners. Each writer retains its existing exclusive publication mechanism.
    """
    return new_directory_path(local_input_path(path), ordinary_file_error=True)


def regular_files(directory: Path) -> tuple[Path, ...]:
    """Inventory a regular directory tree, refusing links and special members."""
    root = regular_directory(directory)
    members: list[Path] = []
    for parent, directories, files in os.walk(root, followlinks=False, onerror=_walk_error):
        for names, expected in ((directories, stat.S_ISDIR), (files, stat.S_ISREG)):
            for name in names:
                path = Path(parent) / name
                try:
                    inspected = path.lstat()
                except OSError as error:
                    raise ArtifactIOError("cannot inspect evidence member") from error
                if not expected(inspected.st_mode) or (
                    getattr(inspected, "st_file_attributes", 0) & 0x400
                ):
                    raise ArtifactIntegrityError(
                        "evidence inventory rejects links and special files"
                    )
        members.extend(Path(parent) / name for name in files)
    return tuple(sorted(members))


@contextmanager
def open_regular_file(
    path: Path, *, path_error: type[ArtifactIntegrityError] = ArtifactIntegrityError
) -> Iterator[BinaryIO]:
    """Pin POSIX directories; on other hosts check identities around open.

    These checks do not sandbox hostile concurrent mounts or filesystem owners.
    """
    parent = regular_directory(path.parent, path_error=path_error)
    descriptor: int | None = None
    directory_descriptors: list[int] = []
    try:
        before = path.lstat()
        if not (
            stat.S_ISREG(before.st_mode) and not getattr(before, "st_file_attributes", 0) & 0x400
        ):
            raise path_error("evidence must be a regular file, not a link or reparse point")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
            no_follow = getattr(os, "O_NOFOLLOW", 0)
            directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | no_follow
            current = os.open(parent.anchor, directory_flags)
            directory_descriptors.append(current)
            for component in parent.parts[1:]:
                current = os.open(component, directory_flags, dir_fd=current)
                directory_descriptors.append(current)
            descriptor = os.open(path.name, flags | no_follow, dir_fd=current)
        else:
            descriptor = os.open(path, flags)
            regular_directory(parent, path_error=path_error)
        after = os.fstat(descriptor)
        if not (
            stat.S_ISREG(after.st_mode) and not getattr(after, "st_file_attributes", 0) & 0x400
        ):
            raise path_error("evidence must remain a regular file without reparse points")
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ArtifactIntegrityError("evidence file changed while opening")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            yield stream
    except OSError as error:
        raise ArtifactIOError("cannot read evidence file") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        for directory_descriptor in reversed(directory_descriptors):
            os.close(directory_descriptor)
