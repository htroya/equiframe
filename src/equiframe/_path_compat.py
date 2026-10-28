"""Filesystem compatibility for the supported CPython versions.

Windows junctions are mount-point reparse points. The lstat tag has existed
since Python 3.8, so older Python must inspect it rather than assume no junction.
This is not a race-free sandbox and does not extend the supported filesystems.
"""

import stat
import sys
from pathlib import Path


def is_junction(path: Path) -> bool:
    """Identify a Windows junction without following it, including on 3.10/3.11.

    POSIX has no Windows junctions. Missing paths are not junctions; other I/O
    failures propagate so inaccessible paths cannot be silently accepted.
    Symlinks are checked separately by the caller, preserving its error contract.
    """
    if sys.platform != "win32":
        return False
    try:
        result = path.lstat()
    except FileNotFoundError:
        return False
    return result.st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT
