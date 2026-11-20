"""Load the offline base-R interpreter installed with EquiFrame."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from pathlib import Path, PurePosixPath

from equiframe.errors import CapabilityError


@dataclass(frozen=True)
class BundledR:
    prefix: Path
    manifest_sha256: str

    @property
    def executable(self) -> Path:
        relative = "lib/R/bin/x64/Rscript.exe" if os.name == "nt" else "lib/R/bin/exec/R"
        return self.prefix / relative

    def command(self, script: Path, directory: Path) -> list[str]:
        if os.name == "nt":
            return [
                str(self.executable),
                "--vanilla",
                "--default-packages=NULL",
                str(script),
                str(directory),
            ]
        return [
            str(self.executable),
            "--vanilla",
            "--slave",
            f"--file={script}",
            "--args",
            str(directory),
        ]

    def patch_environment(self, environment: dict[str, str]) -> None:
        for name in tuple(environment):
            if name.startswith(("R_", "LD_", "DYLD_")):
                del environment[name]
        environment["R_HOME"] = str(self.prefix / "lib/R")
        environment["R_DEFAULT_PACKAGES"] = "NULL"
        if os.name == "nt":
            system = Path(environment.get("SystemRoot", r"C:\Windows"))
            paths = (self.prefix / "Library/bin", system / "System32", system)
        else:
            paths = (self.prefix / "bin", Path("/usr/bin"), Path("/bin"))
            environment["LD_LIBRARY_PATH"] = os.pathsep.join(
                map(str, (self.prefix / "lib/R/lib", self.prefix / "lib"))
            )
        environment["PATH"] = os.pathsep.join(map(str, paths))


def _platform() -> str:
    if platform.machine().lower() in ("x86_64", "amd64"):
        if sys.platform == "win32":
            return "win-64"
        if sys.platform == "linux" and platform.libc_ver()[0] == "glibc":
            return "linux-64"
    raise CapabilityError("rscript_bundled_platform_unavailable")


def _digest(path: Path) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            sha256.update(chunk)
    return sha256.hexdigest()


@cache
def bundled_r() -> BundledR:
    """Verify and reuse the installed, platform-matched runtime for this process."""
    root = files("equiframe").joinpath("_r_runtime", _platform())
    if not isinstance(root, Path) or not root.is_dir():
        raise CapabilityError("rscript_bundled_runtime_unavailable")
    root = root.resolve()
    try:
        raw = (root / "manifest.json").read_bytes()
        manifest = json.loads(raw)
        if manifest.get("version") != "4.6.2" or not isinstance(manifest.get("files"), dict):
            raise ValueError("unexpected bundled R manifest")
        runtime = BundledR(root, hashlib.sha256(raw).hexdigest())
        expected = manifest["files"]
        if runtime.executable.relative_to(root).as_posix() not in expected:
            raise ValueError("bundled R manifest omits the interpreter")
        for name, digest in expected.items():
            relative = PurePosixPath(name)
            path = root.joinpath(*relative.parts)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or "\\" in name
                or path.is_symlink()
                or not path.resolve().is_relative_to(root)
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or _digest(path) != digest
            ):
                raise ValueError("bundled R resource fingerprint mismatch")
    except (OSError, TypeError, ValueError, AttributeError) as error:
        raise CapabilityError("rscript_bundled_runtime_integrity") from error
    return runtime
