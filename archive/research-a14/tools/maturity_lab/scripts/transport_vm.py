#!/usr/bin/env python3
"""Credential-free kit inspection and owner-local SSH transport; never used by dot's cloud."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

PIN = "SHA256:f8cEqNHs2kOMivOwAqSawhz7JyEm59LkLpFT6b8fB7M"
MAX_BYTES = 2 * 1024**3


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_name(name: str) -> str:
    value = PurePosixPath(name)
    if (
        not name
        or value.is_absolute()
        or "\\" in name
        or ":" in name
        or any(part in ("", ".", "..") for part in name.split("/"))
        or not name.isprintable()
    ):
        raise ValueError("unsafe archive member")
    return name


def strict_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    if len(raw) > 16 * 1024**2:
        raise ValueError("manifest too large")
    return json.loads(raw, object_pairs_hook=pairs)


def inspect_zip(path: Path, expected_sha: str) -> dict:
    if path.is_symlink() or not path.is_file() or digest(path) != expected_sha:
        raise ValueError("ZIP hash differs from the separately supplied digest")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > 20000 or sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError("archive expansion exceeds the bounded kit size")
        names = [safe_name(i.filename) for i in infos]
        if len(names) != len(set(names)) or len({n.casefold() for n in names}) != len(names):
            raise ValueError("duplicate or case-colliding archive members")
        for item in infos:
            mode = item.external_attr >> 16
            if item.is_dir() or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise ValueError("only regular file members are admitted")
        manifest = strict_json(archive.read("candidate.json"))
        if manifest.get("schema") not in (
            "equiframe-maturity-candidate-1",
            "equiframe-maturity-candidate-2",
        ):
            raise ValueError("unsupported candidate schema")
        expected = set(manifest["files"]) | {"candidate.json", "SHA256SUMS"}
        if set(names) != expected:
            raise ValueError("unexpected or absent kit members")
        for name, item in manifest["files"].items():
            safe_name(name)
            data = archive.read(name)
            if (
                len(data) != item["size_bytes"]
                or hashlib.sha256(data).hexdigest() != item["sha256"]
            ):
                raise ValueError("manifest member hash/size mismatch")
        sums = "".join(f"{v['sha256']}  {n}\n" for n, v in sorted(manifest["files"].items()))
        sums += f"{hashlib.sha256(archive.read('candidate.json')).hexdigest()}  candidate.json\n"
        if archive.read("SHA256SUMS").decode("utf-8") != sums:
            raise ValueError("SHA256SUMS differs from candidate inventory")
    return manifest


def extract_zip(path: Path, expected_sha: str, destination: Path) -> dict:
    manifest = inspect_zip(path, expected_sha)
    if destination.exists():
        raise ValueError("choose a new extraction directory")
    destination.mkdir(mode=0o700, parents=True)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            target = destination / safe_name(name)
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with archive.open(name) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    return manifest


def pack_evidence(lab: Path, output: Path) -> None:
    inventory = strict_json((lab / "evidence-inventory.json").read_bytes())
    if output.exists():
        raise ValueError("preserve prior evidence archives")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, expected in inventory["files"].items():
            safe_name(name)
            path = lab / name
            if (
                path.is_symlink()
                or not path.resolve().is_relative_to(lab.resolve())
                or not path.is_file()
                or digest(path) != expected["sha256"]
                or path.stat().st_size != expected["size_bytes"]
            ):
                raise ValueError("returned evidence inventory mismatch")
            if any(
                p in {"venv", "controller", "uv-cache", "temporary", "sdist-environment"}
                for p in Path(name).parts
            ):
                raise ValueError("environment/cache must never enter evidence archive")
            archive.write(path, name)
        archive.write(lab / "evidence-inventory.json", "evidence-inventory.json")


def ssh_options(key: Path, known_hosts: Path) -> list[str]:
    # subprocess argv keeps KeyPath local and supports spaces; it is never sent or logged.
    return [
        "-i",
        str(key),
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "ForwardAgent=no",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        'UserKnownHostsFile="' + known_hosts.as_posix() + '"',
        "-o",
        "GlobalKnownHostsFile=none",
        "-o",
        "ConnectTimeout=20",
    ]


def run_local(
    command: list[str], *, input: str | None = None, timeout: int = 60
) -> subprocess.CompletedProcess:
    result = subprocess.run(command, input=input, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        # Do not echo argv/stderr that might disclose a local key path.
        raise RuntimeError(f"local transport command failed with exit {result.returncode}")
    return result


def pinned_hosts(source: Path, host: str, target: Path) -> None:
    found = run_local(["ssh-keygen", "-F", host, "-f", str(source)]).stdout
    trusted = []
    for line in found.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        observed = run_local(["ssh-keygen", "-lf", "-", "-E", "sha256"], input=line + "\n").stdout
        if PIN in observed.split() and "(ED25519)" in observed:
            trusted.append(line)
    if not trusted:
        raise ValueError("known_hosts does not contain the independently trusted Ed25519 pin")
    target.write_text("\n".join(trusted) + "\n", encoding="utf-8")


def transport(args) -> int:
    kit, key, known, output = (
        p.resolve() for p in (args.kit, args.key, args.known_hosts, args.output)
    )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", args.host) or not re.fullmatch(
        r"[a-z_][a-z0-9_-]*", args.user
    ):
        raise ValueError("invalid SSH host/user")
    if not args.operator.strip() or args.operator.strip().startswith("NOMBRE REAL"):
        raise ValueError("record the real operator/task identity")
    inspect_zip(kit, args.sha256)
    if key.is_symlink() or not key.is_file() or not known.is_file():
        raise ValueError("existing local key and known_hosts files are required")
    if output.exists():
        raise ValueError("choose a new output directory")
    output.mkdir(parents=True, mode=0o700)
    receipt = {
        "schema": "owner-local-transport-1",
        "operator_declared": args.operator,
        "operator_authenticated": False,
        "kit_sha256": args.sha256,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stages": [],
        "status": "running",
    }

    def save():
        (output / "transport.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )

    save()
    target = args.user + "@" + args.host
    try:
        with tempfile.TemporaryDirectory(prefix="public-known-hosts-") as temporary:
            copied_known = Path(temporary) / "known_hosts"
            pinned_hosts(known, args.host, copied_known)
            options = ssh_options(key, copied_known)
            receipt["host_key_fingerprint_verified"] = PIN
            create = (
                "import pathlib,tempfile; p=pathlib.Path.home(); "
                "print(tempfile.mkdtemp(prefix='equiframe-universality-transfer-',dir=p))"
            )
            remote = run_local(
                [
                    "ssh",
                    *options,
                    "-T",
                    target,
                    "python3.12 -I -c " + shlex.quote(create),
                ]
            ).stdout.strip()
            if not re.fullmatch(
                r"/home/"
                + re.escape(args.user)
                + r"/equiframe-universality-transfer-[A-Za-z0-9_-]+",
                remote,
            ):
                raise ValueError("remote transfer directory has unexpected identity")
            receipt["remote_transfer_directory"] = remote
            run_local(
                ["scp", *options, str(kit), target + ":" + remote + "/kit.zip"],
                timeout=300,
            )
            receipt["stages"].append({"name": "upload", "exit": 0})
            save()
            # Only the reviewed, hashed transport helper is staged independently, never KeyPath.
            helper = Path(__file__).resolve()
            run_local(
                [
                    "scp",
                    *options,
                    str(helper),
                    target + ":" + remote + "/transport_vm.py",
                ],
                timeout=300,
            )
            verify = (
                "import hashlib,pathlib; p=pathlib.Path("
                + repr(remote + "/transport_vm.py")
                + "); assert hashlib.sha256(p.read_bytes()).hexdigest()=="
                + repr(digest(helper))
            )
            run_local(
                [
                    "ssh",
                    *options,
                    "-T",
                    target,
                    "python3.12 -I -c " + shlex.quote(verify),
                ]
            )
            command = [
                "python3.12",
                "-I",
                remote + "/transport_vm.py",
                "execute",
                "--kit",
                remote + "/kit.zip",
                "--sha256",
                args.sha256,
                "--output",
                remote + "/work",
                "--operator",
                args.operator,
            ]
            try:
                completed = subprocess.run(
                    ["ssh", *options, "-T", target, shlex.join(command)],
                    capture_output=True,
                    text=True,
                    timeout=args.timeout,
                )
            except subprocess.TimeoutExpired as error:
                receipt["remote_timed_out"] = True
                completed = subprocess.CompletedProcess(
                    [],
                    124,
                    error.stdout.decode("utf-8", "replace")
                    if isinstance(error.stdout, bytes)
                    else (error.stdout or ""),
                    error.stderr.decode("utf-8", "replace")
                    if isinstance(error.stderr, bytes)
                    else (error.stderr or ""),
                )
            receipt["stages"].append({"name": "remote-lab", "exit": completed.returncode})
            (output / "remote-stdout.log").write_text(completed.stdout, encoding="utf-8")
            (output / "remote-stderr.log").write_text(
                completed.stderr.replace(str(key), "[local identity path]"), encoding="utf-8"
            )
            save()
            # Collect failures as well as passes; a nonzero remote test never suppresses collection.
            run_local(
                [
                    "scp",
                    *options,
                    target + ":" + remote + "/work/result.json",
                    str(output / "result.json"),
                ],
                timeout=300,
            )
            result = strict_json((output / "result.json").read_bytes())
            if result.get("evidence_archive"):
                if result["evidence_archive"] != remote + "/work/evidence.zip":
                    raise ValueError("unexpected remote evidence path")
                run_local(
                    [
                        "scp",
                        *options,
                        target + ":" + result["evidence_archive"],
                        str(output / "evidence.zip"),
                    ],
                    timeout=600,
                )
                if digest(output / "evidence.zip") != result["sha256"]:
                    raise ValueError("returned evidence transfer hash mismatch")
                receipt["returned_evidence_sha256"] = result["sha256"]
            success = (
                completed.returncode == 0
                and result.get("status") == "completed"
                and result.get("exit_code") == 0
                and bool(result.get("evidence_archive"))
            )
            receipt["status"] = "collected" if success else "failed_collected"
            return 0 if success else 1
    except Exception as error:
        receipt.update(
            status="failed",
            error_type=type(error).__name__,
            error="Transport failed; inspect the stage and local tool status",
        )
        return 1
    finally:
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        save()


def execute(args) -> int:
    output = args.output.resolve()
    if output.exists():
        raise ValueError("choose a new remote work directory")
    output.mkdir(mode=0o700)
    result = {"status": "failed", "evidence_archive": None}
    try:
        kit = output / "kit"
        extract_zip(args.kit.resolve(), args.sha256, kit)
        command = [
            "python3.12",
            str(kit / "scripts/run_vm_lab.py"),
            "--kit",
            str(kit),
            "--executor",
            args.operator,
        ]
        with (output / "runner.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True)
        text = (output / "runner.log").read_text("utf-8")
        labs = re.findall(r"^Isolated lab: (/home/[^\n]+)$", text, re.M)
        if len(labs) != 1:
            raise ValueError("runner did not leave exactly one identifiable evidence directory")
        if len(labs) == 1:
            lab = Path(labs[0])
            if (
                not lab.is_dir()
                or lab.parent != Path.home()
                or not lab.name.startswith("equiframe-maturity-")
            ):
                raise ValueError("unexpected runner lab directory")
            archive = output / "evidence.zip"
            pack_evidence(lab, archive)
            result.update(evidence_archive=str(archive), sha256=digest(archive), lab=str(lab))
        result.update(
            status="completed" if completed.returncode == 0 else "failed",
            exit_code=completed.returncode,
        )
        return 0 if completed.returncode == 0 else 1
    except Exception as error:
        result.update(
            error_type=type(error).__name__,
            error="Transport failed; inspect the stage and local tool status",
        )
        return 1
    finally:
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("transport", "execute", "inspect"):
        sub = commands.add_parser(name)
        sub.add_argument("--kit", type=Path, required=True)
        sub.add_argument("--sha256", required=True)
        if name != "inspect":
            sub.add_argument("--output", type=Path, required=True)
            sub.add_argument("--operator", required=True)
        if name == "transport":
            sub.add_argument("--key", type=Path, required=True)
            sub.add_argument("--known-hosts", type=Path, required=True)
            sub.add_argument("--host", required=True)
            sub.add_argument("--user", default="hernan")
            sub.add_argument("--timeout", type=int, default=86400)
    args = parser.parse_args()
    if args.command == "transport":
        return transport(args)
    if args.command == "execute":
        return execute(args)
    print(json.dumps({"verified": True, "schema": inspect_zip(args.kit, args.sha256)["schema"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
