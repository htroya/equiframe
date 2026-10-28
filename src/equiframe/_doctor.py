"""Local installation metadata checks; no optional imports or network access."""

from __future__ import annotations

import sys
from enum import Enum
from importlib import metadata
from importlib.util import find_spec
from typing import Any


class Extra(str, Enum):
    base = "base"
    arrow = "arrow"
    pandas = "pandas"
    polars = "polars"
    duckdb = "duckdb"
    engines = "engines"
    files = "files"
    ml = "ml"


_BASE = (
    ("typing-extensions", "typing_extensions"),
    ("pydantic", "pydantic"),
    ("typer", "typer"),
    ("tzdata", "tzdata"),
)
_ARROW = (("pyarrow", "pyarrow"),)
_EXTRAS = {
    Extra.base: (),
    Extra.arrow: _ARROW,
    Extra.pandas: (*_ARROW, ("pandas", "pandas")),
    Extra.polars: (*_ARROW, ("polars", "polars")),
    Extra.duckdb: (*_ARROW, ("duckdb", "duckdb")),
    Extra.engines: (*_ARROW, ("pandas", "pandas"), ("polars", "polars"), ("duckdb", "duckdb")),
    Extra.files: (
        *_ARROW,
        ("pandas", "pandas"),
        ("openpyxl", "openpyxl"),
        ("xlrd", "xlrd"),
        ("defusedxml", "defusedxml"),
    ),
    Extra.ml: (("numpy", "numpy"), ("scikit-learn", "sklearn")),
}


def diagnose(extra: Extra) -> dict[str, Any]:
    """Report availability only; pip check and a native operation remain necessary."""
    from equiframe import __version__

    dependencies: list[dict[str, str | None]] = []
    for distribution, module in _BASE + _EXTRAS[extra]:
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            version = None
        available = find_spec(module) is not None
        dependencies.append(
            {
                "distribution": distribution,
                "version": version,
                "status": "available" if version is not None and available else "missing",
            }
        )
    try:
        installed_version = metadata.version("equiframe")
    except metadata.PackageNotFoundError:
        installed_version = None
    identity = installed_version == __version__
    python_supported = (3, 10) <= sys.version_info[:2] < (3, 14)
    ready = (
        identity
        and python_supported
        and all(item["status"] == "available" for item in dependencies)
    )
    if not identity:
        next_action = (
            "Reinstall the identified private candidate in this interpreter; "
            "code and distribution metadata must have the same version."
        )
    elif not python_supported:
        next_action = "Use a supported Python minor (3.10-3.13) with its matching artifact receipt."
    elif not ready:
        requirement = "equiframe" + (f"[{extra.value}]" if extra != Extra.base else "")
        next_action = (
            f"Install {requirement}=={__version__} from the reviewed private wheelhouse "
            "in this interpreter; do not install an unrelated public homonym."
        )
    else:
        next_action = (
            "Run python -m pip check in this interpreter, then the documented native "
            "example for your task. Metadata availability does not test binary compatibility."
        )
    return {
        "schema_version": "1.0",
        "extra": extra.value,
        "code_version": __version__,
        "installed_version": installed_version,
        "identity_matches": identity,
        "python": ".".join(map(str, sys.version_info[:3])),
        "python_admitted": python_supported,
        "dependencies": dependencies,
        "ready_metadata": ready,
        "native_execution_tested": False,
        "dependency_ranges_tested": False,
        "next_action": next_action,
    }


def diagnostic_text(result: dict[str, Any]) -> str:
    """A short human view of the same machine-readable diagnosis."""
    lines = [
        f"EquiFrame {result['code_version']} | Python {result['python']} | extra {result['extra']}",
        f"Distribution version: {result['installed_version'] or 'missing'}",
        f"Metadata ready: {result['ready_metadata']}",
    ]
    lines.extend(
        f"  {item['distribution']}: {item['status']} ({item['version'] or 'missing'})"
        for item in result["dependencies"]
    )
    lines.append("Next action: " + result["next_action"])
    return "\n".join(lines)
