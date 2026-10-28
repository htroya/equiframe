"""Keep wheel metadata and sdist source boundaries independent of build context.

Hatchling 1.28 normalizes dates and permissions but ZipInfo.create_system still
defaults to the build host. Payload bytes, RECORD, ordering and modes stay intact.
This build hook is shipped in the sdist; it is never imported by the runtime.
Hatchling also adds ancestor VCS ignore files to sdists automatically. Only
project-owned ignore files belong in these explicitly inventoried distributions.
"""

import shutil
import tempfile
from copy import copy
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from hatchling.builders.config import BuilderConfig
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def canonicalize_wheel(path: Path) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".whl", delete=False) as temporary:
        target = Path(temporary.name)
    try:
        with ZipFile(path) as source, ZipFile(target, "w") as destination:
            destination.comment = source.comment
            for original in source.infolist():
                info = copy(original)
                info.create_system = 3  # Unix ZIP convention; normalized modes already use it.
                with source.open(original) as reader, destination.open(info, "w") as writer:
                    shutil.copyfileobj(reader, writer, length=64 * 1024)
        target.replace(path)
    finally:
        target.unlink(missing_ok=True)


class ReproducibleWheelHook(BuildHookInterface[BuilderConfig]):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "sdist":
            return
        project = Path(self.root).resolve()
        forced = build_data.get("force_include", {})
        for source, destination in tuple(forced.items()):
            if destination in {".gitignore", ".hgignore"} and not Path(
                source
            ).resolve().is_relative_to(project):
                del forced[source]

    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        if self.target_name == "wheel":
            canonicalize_wheel(Path(artifact_path))
