"""Run only explicitly registered, trusted Python documentation fences offline."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


def python_fences(text: str) -> list[str]:
    blocks, lines, fence = [], [], None
    selected = False
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence is None:
            if marker:
                fence = marker.group(1)
                selected = marker.group(2).strip() == "python"
                lines = []
        elif (
            marker
            and marker.group(1)[0] == fence[0]
            and len(marker.group(1)) >= len(fence)
        ):
            if selected:
                blocks.append("\n".join(lines) + "\n")
            fence = None
        else:
            lines.append(line)
    if fence is not None:
        raise ValueError("Unclosed fenced code block")
    return blocks


IDENTITY_PROBE = """
import hashlib, importlib.metadata as md, json, sys, zipfile
from pathlib import Path
import equiframe
import pyarrow
package = Path(equiframe.__file__).resolve().parent
root = Path(sys.argv[2]).resolve()
if package.is_relative_to(root) or not package.is_relative_to(Path(sys.prefix).resolve()):
    raise RuntimeError('SDK must be installed in selected environment, outside checkout')
if md.version('equiframe') != sys.argv[3] or equiframe.__version__ != sys.argv[3]:
    raise RuntimeError('SDK metadata/import identity mismatch')
checked = 0
with zipfile.ZipFile(sys.argv[1]) as archive:
    for name in archive.namelist():
        if name.startswith('equiframe/') and not name.endswith('/'):
            installed = package.parent / name
            if hashlib.sha256(installed.read_bytes()).digest() != hashlib.sha256(archive.read(name)).digest():
                raise RuntimeError('Installed SDK payload differs: ' + name)
            checked += 1
print(json.dumps({'python': sys.version, 'executable': sys.executable, 'prefix': sys.prefix,
                 'base_prefix': sys.base_prefix, 'utf8_mode': sys.flags.utf8_mode, 'sdk': equiframe.__version__,
                 'arrow': pyarrow.__version__, 'sdk_path': str(package), 'payload_members': checked}))
"""


def prepare_examples(root: Path, registry: dict) -> list[tuple[dict, str]]:
    examples = registry["examples"]
    if not isinstance(examples, list) or not examples:
        raise ValueError("A nonempty example registry is required")
    prepared, identifiers = [], set()
    for example in examples:
        identifier = example["id"]
        if not isinstance(identifier, str) or not re.fullmatch(
            r"[a-z0-9-]+", identifier
        ):
            raise ValueError("Nonportable example identifier")
        if identifier in identifiers:
            raise ValueError("Duplicate example identifier")
        identifiers.add(identifier)
        markers = example["expected_stdout"]
        if (
            not isinstance(markers, list)
            or not markers
            or any(not isinstance(x, str) or not x for x in markers)
        ):
            raise ValueError("Nonempty expected output markers are required")
        document = (root / example["document"]).resolve()
        if not document.is_relative_to(root):
            raise ValueError("Registered document outside checkout")
        blocks = python_fences(document.read_text(encoding="utf-8"))
        number = example["python_fence"]
        if (
            isinstance(number, bool)
            or not isinstance(number, int)
            or not 1 <= number <= len(blocks)
        ):
            raise ValueError("Invalid Python fence selection")
        prepared.append((example, blocks[number - 1]))
    return prepared


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--registry", type=Path)
    parser.add_argument(
        "--python", type=Path, required=True, help="Installed consumer interpreter"
    )
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument(
        "--sha256", required=True, help="Expected wheel digest from a trusted receipt"
    )
    parser.add_argument(
        "--work-dir", type=Path, required=True, help="New directory outside checkout"
    )
    args = parser.parse_args()
    root, work = args.root.resolve(), args.work_dir.resolve()
    try:
        if work.is_relative_to(root):
            raise ValueError("Working outputs must be outside the repository")
        registry_path = args.registry or root / "tools/documentation_examples.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        auditor_path = root / "packages/equiframe/tools/audit_wheel.py"
        spec = importlib.util.spec_from_file_location(
            "documentation_wheel_auditor", auditor_path
        )
        auditor = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = auditor
        spec.loader.exec_module(auditor)
        wheel = args.wheel.resolve()
        audit = auditor.audit(wheel, args.sha256, "equiframe", registry["sdk_version"])
        if audit["status"] != "PASS":
            raise ValueError("Wheel offline audit failed")
        prepared = prepare_examples(root, registry)
        work.mkdir(parents=True, exist_ok=False)
        probe = subprocess.run(
            [
                str(args.python.absolute()),
                "-I",
                "-X",
                "utf8",
                "-c",
                IDENTITY_PROBE,
                str(wheel),
                str(root),
                registry["sdk_version"],
            ],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
            encoding="utf-8",
        )
        if probe.returncode:
            raise ValueError(
                "Installed SDK identity/payload probe failed: " + probe.stderr
            )
        identity = json.loads(probe.stdout)
        attempts = []
        for example, code in prepared:
            for optimized in (False, True):
                folder = work / (
                    example["id"] + ("-optimized" if optimized else "-normal")
                )
                folder.mkdir()
                script = folder / "example.py"
                script.write_text(code, encoding="utf-8", newline="\n")
                command = [str(args.python.absolute()), "-I", "-X", "utf8"]
                if optimized:
                    command.append("-O")
                command.append(str(script))
                try:
                    outcome = subprocess.run(
                        command,
                        cwd=folder,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        check=False,
                        encoding="utf-8",
                    )
                    stdout, stderr, exit_code = (
                        outcome.stdout,
                        outcome.stderr,
                        outcome.returncode,
                    )
                    missing = [
                        value
                        for value in example["expected_stdout"]
                        if value not in stdout
                    ]
                    status = "PASS" if exit_code == 0 and not missing else "FAIL"
                except subprocess.TimeoutExpired:
                    stdout, stderr, exit_code, missing, status = (
                        "",
                        "Execution timeout",
                        None,
                        [],
                        "FAIL",
                    )
                (folder / "stdout.txt").write_text(stdout, encoding="utf-8")
                (folder / "stderr.txt").write_text(stderr, encoding="utf-8")
                attempts.append(
                    {
                        "id": example["id"],
                        "document": example["document"],
                        "python_fence": example["python_fence"],
                        "optimized": optimized,
                        "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
                        "status": status,
                        "exit_code": exit_code,
                        "missing_markers": missing,
                        "stdout_sha256": hashlib.sha256(
                            stdout.encode("utf-8")
                        ).hexdigest(),
                        "stderr_sha256": hashlib.sha256(
                            stderr.encode("utf-8")
                        ).hexdigest(),
                    }
                )
                print(f"{status}: {example['id']} optimized={optimized}")
        result = {
            "status": "PASS"
            if all(x["status"] == "PASS" for x in attempts)
            else "FAIL",
            "wheel_sha256": args.sha256,
            "identity": identity,
            "attempts": attempts,
            "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
            "scope": "Four registered trusted Python fences; normal and -O, fresh outputs. "
            "Other snippets, shell installation commands and human usability not measured.",
        }
        with (work / "examples.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        return 0 if result["status"] == "PASS" else 1
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired) as error:
        parser.exit(2, f"Documentation example error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
