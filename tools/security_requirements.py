"""Export every public lock pin for pip-audit without resolving or installing it.

Alternative Python/platform pins are placed in separate files because pip-audit
rejects two versions of one project in the same requirements input. No advisory
result, license decision or publication approval is inferred by this exporter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

LOCAL_PROJECTS = frozenset(("equiframe", "equiframe-benchmark"))


def audit_batches(locks: list[Path]) -> list[list[str]]:
    """Preserve all registry name/version pairs, including conditional pins."""
    versions: dict[str, set[str]] = {}
    for lock in locks:
        if lock.is_symlink() or not lock.is_file():
            raise ValueError("lock must be a regular local file")
        document = tomllib.loads(lock.read_text(encoding="utf-8"))
        for package in document["package"]:
            name, source = package["name"], package["source"]
            if (
                not isinstance(name, str)
                or re.fullmatch(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", name) is None
                or not isinstance(source, dict)
            ):
                raise ValueError("invalid locked project identity")
            canonical = re.sub(r"[-_.]+", "-", name).lower()
            if canonical in LOCAL_PROJECTS and set(source) in (
                {"editable"},
                {"directory"},
                {"virtual"},
            ):
                continue
            if source != {"registry": "https://pypi.org/simple"}:
                raise ValueError("audit requires reviewed PyPI pins or declared local projects")
            version = package.get("version")
            if (
                not isinstance(version, str)
                or re.fullmatch(r"[0-9][A-Za-z0-9.!+_-]*", version) is None
            ):
                raise ValueError("invalid locked project identity")
            versions.setdefault(canonical, set()).add(version)
    if not versions:
        raise ValueError("public locked dependencies are absent")
    batches: list[list[str]] = [[] for _ in range(max(map(len, versions.values())))]
    for name, pinned in sorted(versions.items()):
        for index, version in enumerate(sorted(pinned)):
            batches[index].append(name + "==" + version)
    return batches


def export(locks: list[Path], output: Path) -> dict[str, Any]:
    batches = audit_batches(locks)
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for index, batch in enumerate(batches):
        name = f"requirements-{index}.txt"
        data = ("\n".join(batch) + "\n").encode("ascii")
        with (output / name).open("xb") as stream:
            stream.write(data)
        files.append(
            {"file": name, "pairs": len(batch), "sha256": hashlib.sha256(data).hexdigest()}
        )
    return {"public_pairs": sum(map(len, batches)), "batches": files}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export(args.lock, args.output)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(2, "Cannot export reviewed public dependency pins to a new directory.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
