"""Audit and install an identified private Beta from an offline wheelhouse.

An installation receipt establishes only its actual interpreter and artifacts.
Activation is separate from validation. This tool never uploads to an index.
"""

from __future__ import annotations

import argparse
import ast
import base64
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            result.update(block)
    return result.hexdigest()


def wheel(path):
    """Validate every RECORD payload; metadata alone is not an artifact check."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "Repeated wheel member")
        require(
            all(
                not name.startswith(("/", "\\")) and ".." not in Path(name).parts
                for name in names
            ),
            "Invalid wheel member",
        )
        records = [name for name in names if name.endswith(".dist-info/RECORD")]
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        require(
            len(records) == len(metadata) == 1, "Single distribution metadata required"
        )
        inventory = list(
            csv.reader(io.StringIO(archive.read(records[0]).decode("utf-8")))
        )
        require(
            len({row[0] for row in inventory}) == len(inventory)
            and {row[0] for row in inventory} == set(names),
            "RECORD inventory differs",
        )
        for name, hash_value, size in inventory:
            data = archive.read(name)
            if name == records[0]:
                require(not hash_value and not size, "RECORD self entry differs")
            else:
                encoded = (
                    base64.urlsafe_b64encode(hashlib.sha256(data).digest())
                    .rstrip(b"=")
                    .decode("ascii")
                )
                require(
                    hash_value == "sha256=" + encoded and size == str(len(data)),
                    "Wheel payload differs",
                )
        info = BytesParser().parsebytes(archive.read(metadata[0]))
        return {
            "name": canonicalize_name(info["Name"]),
            "version": info["Version"],
            "requires_dist": info.get_all("Requires-Dist", []),
            "classifiers": info.get_all("Classifier", []),
            "members": len(names),
        }


def artifact_path(directory, record):
    path = (directory / record["file"]).resolve()
    require(
        path.is_relative_to(directory.resolve())
        and path.is_file()
        and not path.is_symlink(),
        "Candidate artifact missing or outside its directory",
    )
    require(
        path.stat().st_size == record["size_bytes"]
        and digest(path) == record["sha256"],
        "Candidate artifact differs",
    )
    return path


def audit(path):
    candidate = json.loads(path.read_text("utf-8"))
    require(
        candidate["channel"] == "private"
        and candidate["public_publication_enabled"] is False,
        "This installer accepts the private channel only",
    )
    version = Version(candidate["version"])
    require(
        version.pre is not None and version.pre[0] == "b",
        "Identified Beta version required",
    )
    metadata = {}
    for record in candidate["wheels"]:
        artifact = artifact_path(path.parent, record)
        info = wheel(artifact)
        require(
            info["name"] in {"equiframe", "equiframe-benchmark"}
            and info["name"] not in metadata,
            "Exact core/benchmark pair required",
        )
        require(
            info["version"] == candidate["version"]
            and "Development Status :: 4 - Beta" in info["classifiers"],
            "Beta metadata differs",
        )
        with zipfile.ZipFile(artifact) as bundle:
            package = (
                "equiframe" if info["name"] == "equiframe" else "equiframe_benchmark"
            )
            module = ast.parse(bundle.read(package + "/__init__.py").decode("utf-8"))
            versions = [
                ast.literal_eval(node.value)
                for node in module.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "__version__"
                    for target in node.targets
                )
            ]
            require(
                versions == [candidate["version"]],
                "Code and distribution versions differ",
            )
        metadata[info["name"]] = info
    require(
        set(metadata) == {"equiframe", "equiframe-benchmark"},
        "Core/benchmark pair incomplete",
    )
    requirements = [
        Requirement(text) for text in metadata["equiframe-benchmark"]["requires_dist"]
    ]
    pins = [r for r in requirements if canonicalize_name(r.name) == "equiframe"]
    require(
        len(pins) == 3
        and all(str(r.specifier) == "==" + candidate["version"] for r in pins),
        "Benchmark must pin all three core profiles exactly",
    )
    dependencies = {}
    for record in candidate["dependencies"]:
        artifact = artifact_path(path.parent, record)
        info = wheel(artifact)
        require(
            info["name"] not in {*metadata, *dependencies},
            "Duplicate/private-name dependency",
        )
        dependencies[info["name"]] = info["version"]
    return candidate, {
        "status": "PASS",
        "sdk": metadata,
        "dependencies": dependencies,
        "candidate_sha256": digest(path),
        "public_publication_enabled": False,
        "human_acceptance_or_scientific_approval": False,
    }


PROBE = r"""
import hashlib,importlib,importlib.metadata as md,json,platform,sys,zipfile
from pathlib import Path
version,repository=sys.argv[1:3]
sources=json.loads(sys.argv[3])
checked={}
for module_name,distribution in [('equiframe','equiframe'),('equiframe_benchmark','equiframe-benchmark')]:
 module=importlib.import_module(module_name)
 if module.__version__!=version or md.version(distribution)!=version:
  raise ValueError('Installed identity differs')
 if Path(module.__file__).resolve().is_relative_to(Path(repository).resolve()):
  raise ValueError('Installed SDK must be outside the source checkout')
 root=Path(module.__file__).resolve().parent
 expected=set()
 with zipfile.ZipFile(sources[distribution]) as bundle:
  for member in bundle.namelist():
   if member.startswith(module_name+'/') and not member.endswith('/'):
    relative=member[len(module_name)+1:]
    expected.add(relative)
    installed=root/relative
    if not installed.is_file() or installed.is_symlink() or hashlib.sha256(installed.read_bytes()).digest()!=hashlib.sha256(bundle.read(member)).digest():
     raise ValueError('Installed payload differs: '+member)
 if any(p.relative_to(root).as_posix() not in expected for p in root.rglob('*') if p.is_file() and p.suffix in {'.py','.pyi','.pyd','.so'}):
  raise ValueError('Unexpected installed source module')
 checked[distribution]=len(expected)
print(json.dumps({'python':platform.python_version(),'system':platform.system(),'machine':platform.machine(),
 'sdk':version,'benchmark':version,'sdk_path':str(importlib.import_module('equiframe').__file__),
 'benchmark_path':str(importlib.import_module('equiframe_benchmark').__file__),'payload_files_verified':checked}))
"""


def deploy(manifest, target, python):
    candidate, inspection = audit(manifest)
    workspace = Path(__file__).resolve().parents[2]
    require(
        target.resolve().is_relative_to(workspace) and not target.exists(),
        "Choose a new installation directory inside the workspace",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    result_directory = target.with_name(target.name + "-receipt")
    result_directory.mkdir(exist_ok=False)
    requirements = []
    for record in [*candidate["wheels"], *candidate["dependencies"]]:
        artifact = artifact_path(manifest.parent, record)
        info = wheel(artifact)
        requirements.append(
            f"{info['name']}=={info['version']} --hash=sha256:{record['sha256']}"
        )
    lock = result_directory / "requirements.lock"
    lock.write_text("\n".join(sorted(requirements)) + "\n", encoding="utf-8")
    environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "POLARS_MAX_THREADS": "1",
    }
    commands = []

    def run(argv, name):
        completed = subprocess.run(
            argv,
            cwd=result_directory,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1800,
            check=False,
        )
        log = result_directory / (name + ".log")
        log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
        commands.append(
            {
                "argv": [str(item) for item in argv],
                "exit_code": completed.returncode,
                "log": log.name,
                "sha256": digest(log),
            }
        )
        require(completed.returncode == 0, "Private installation step failed: " + name)
        return completed.stdout

    try:
        run([python, "-I", "-B", "-m", "venv", str(target)], "create")
        interpreter = target / (
            "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        )
        run(
            [
                str(interpreter),
                "-I",
                "-B",
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(manifest.parent),
                "--require-hashes",
                "--report",
                str(result_directory / "install.json"),
                "-r",
                str(lock),
            ],
            "install",
        )
        run([str(interpreter), "-I", "-B", "-m", "pip", "check"], "pip-check")
        identity = json.loads(
            run(
                [
                    str(interpreter),
                    "-I",
                    "-B",
                    "-c",
                    PROBE,
                    candidate["version"],
                    str(Path(__file__).parents[1]),
                    json.dumps(
                        {
                            wheel(artifact_path(manifest.parent, record))["name"]: str(
                                artifact_path(manifest.parent, record)
                            )
                            for record in candidate["wheels"]
                        }
                    ),
                ],
                "identity",
            )
        )
        status, error = "INSTALLED_PENDING_ACCEPTANCE", None
    except (OSError, ValueError, subprocess.SubprocessError) as exception:
        status, error, identity = "FAILED_NOT_ACTIVATED", str(exception), None
    receipt = {
        "schema": "equiframe.private-beta-installation.v1",
        "status": status,
        "error": error,
        "version": candidate["version"],
        "candidate_sha256": inspection["candidate_sha256"],
        "environment": identity,
        "commands": commands,
        "activated": False,
        "public_publication_enabled": False,
        "human_independent_acceptance": False,
    }
    with (result_directory / "receipt.json").open("x", encoding="utf-8") as output:
        json.dump(receipt, output, sort_keys=True, indent=2)
        output.write("\n")
    require(error is None, error)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "deploy"))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    if args.mode == "audit":
        _, result = audit(args.candidate.resolve())
    else:
        require(args.target is not None, "New target directory required")
        result = deploy(args.candidate.resolve(), args.target.resolve(), args.python)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
