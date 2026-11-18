"""Inspect lexical EDA paths before resolving away links and Windows junctions."""

from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath


def ordinary_path(path: Path, *, directory: bool = False, allow_missing: bool = False) -> Path:
    lexical = path.absolute()
    for ancestor in reversed(lexical.parents):
        try:
            info = ancestor.lstat()
        except FileNotFoundError:
            if allow_missing:
                continue
            raise
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("EDA directories must not be symlinks or reparse points")
    try:
        info = lexical.lstat()
    except FileNotFoundError:
        if not allow_missing:
            raise
    else:
        expected = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not expected or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("EDA paths must be ordinary files/directories without links")
    return lexical.resolve(strict=not allow_missing)


def manifest_member(root: Path, name: object) -> Path:
    if not isinstance(name, str) or not 0 < len(name) <= 4096:
        raise ValueError("Invalid source inventory path")
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or relative.as_posix() != name
        or name == "."
        or ".." in relative.parts
        or "\\" in name
        or ":" in name
        or "\x00" in name
    ):
        raise ValueError("Source inventory paths must stay within their delivery")
    member = ordinary_path(root / relative)
    if not member.is_relative_to(root):
        raise ValueError("Source inventory member escaped its delivery")
    return member
