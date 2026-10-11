"""Offline checks for the explicit, current Markdown documentation scope."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit


def prose(text: str) -> str:
    """Remove fenced code/comments; preserve line positions for diagnostics."""
    text = re.sub(
        r"<!--.*?-->",
        lambda match: "\n" * match.group(0).count("\n"),
        text,
        flags=re.DOTALL,
    )
    lines = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            lines.append("")
        else:
            lines.append(line if fence is None else "")
    return "\n".join(lines)


def anchors(text: str) -> set[str]:
    """GitHub-style ATX/setext heading IDs for the syntax used in this scope."""
    clean = prose(text)
    result = set(re.findall(r'<[^>]+\bid=["\']([^"\']+)["\']', clean))
    seen: dict[str, int] = {}
    headings = []
    lines = clean.splitlines()
    for index, line in enumerate(lines):
        atx = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$", line)
        if atx:
            headings.append(atx.group(1))
        elif index and re.fullmatch(r" {0,3}(?:=+|-+)\s*", line):
            previous = lines[index - 1].strip()
            if previous and not previous.startswith("|"):
                headings.append(previous)
    for heading in headings:
        heading = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)
        heading = re.sub(r"<[^>]*>", "", heading).lower()
        slug = "".join(
            char
            for char in heading
            if char in " -_" or unicodedata.category(char)[0] in "LNM"
        ).replace(" ", "-")
        number = seen.get(slug, 0)
        candidate = slug if not number else f"{slug}-{number}"
        while candidate in result:
            number += 1
            candidate = f"{slug}-{number}"
        seen[slug] = number + 1
        result.add(candidate)
    return result


def links(text: str) -> list[tuple[int, str]]:
    """Inline links/images and explicit/collapsed/defined shortcut references."""
    clean = prose(text)
    references = {}
    for match in re.finditer(
        r"^\s{0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)", clean, re.MULTILINE
    ):
        references[" ".join(match.group(1).lower().split())] = match.group(2).strip(
            "<>"
        )
    found = []
    for number, line in enumerate(clean.splitlines(), 1):
        if re.match(r"^\s{0,3}\[[^\]]+\]:", line):
            continue
        line = re.sub(r"(`+).*?\1", "", line)
        for match in re.finditer(r"!?\[([^\]\n]+)\]", line):
            label = match.group(1)
            tail = line[match.end() :]
            if tail.startswith("("):
                depth, end, angled = 1, 1, False
                while end < len(tail) and depth:
                    char = tail[end]
                    if char == "\\":
                        end += 2
                        continue
                    if char == "<":
                        angled = True
                    elif char == ">":
                        angled = False
                    elif not angled and char == "(":
                        depth += 1
                    elif not angled and char == ")":
                        depth -= 1
                    end += 1
                if depth:
                    raise ValueError(f"Unclosed Markdown link at line {number}")
                value = tail[1 : end - 1].strip()
                if value.startswith("<"):
                    target = value[1 : value.index(">")]
                else:
                    target = value.split()[0] if value else ""
                found.append((number, target))
            else:
                ref = re.match(r"\[([^\]]*)\]", tail)
                key = (ref.group(1) or label) if ref else label
                key = " ".join(key.lower().split())
                if ref or key in references:
                    if key not in references:
                        raise ValueError(
                            f"Undefined reference {key!r} at line {number}"
                        )
                    found.append((number, references[key]))
    return found


def local_path(root: Path, relative: str, parent: Path | None = None) -> Path:
    base = parent or root
    path = (base / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Destination outside the repository: " + relative)
    return path


def audit(root: Path, manifest: dict) -> dict:
    root = root.resolve()
    documents = {local_path(root, name) for name in manifest["documents"]}
    for directory in manifest.get("directories", []):
        folder = local_path(root, directory)
        if not folder.is_dir():
            raise ValueError("Missing documentation directory: " + directory)
        documents.update(folder.rglob("*.md"))
    failures, inventory, remote = [], [], []
    checked_files = checked_anchors = 0
    for document in sorted(documents):
        relative = document.relative_to(root).as_posix()
        try:
            raw = document.read_bytes()
            body = raw.decode("utf-8")
            navigation = links(body)
            for line, target in navigation:
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc:
                    if parsed.scheme.lower() not in {"http", "https", "mailto"}:
                        raise ValueError("Nonportable link: " + target)
                    remote.append(
                        {"document": relative, "line": line, "target": target}
                    )
                    continue
                decoded = unquote(parsed.path)
                if decoded.startswith(("/", "\\")) or "\\" in decoded:
                    raise ValueError("Nonportable local link: " + target)
                destination = (
                    local_path(root, decoded, document.parent) if decoded else document
                )
                if not destination.exists():
                    failures.append(
                        {
                            "document": relative,
                            "line": line,
                            "target": target,
                            "reason": "missing destination",
                        }
                    )
                    continue
                checked_files += 1
                if parsed.fragment:
                    if destination.suffix.lower() != ".md":
                        failures.append(
                            {
                                "document": relative,
                                "line": line,
                                "target": target,
                                "reason": "anchor on non-Markdown target is unsupported",
                            }
                        )
                    elif unquote(parsed.fragment) not in anchors(
                        destination.read_text(encoding="utf-8")
                    ):
                        failures.append(
                            {
                                "document": relative,
                                "line": line,
                                "target": target,
                                "reason": "missing heading anchor",
                            }
                        )
                    else:
                        checked_anchors += 1
            inventory.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "links": len(navigation),
                }
            )
        except (OSError, UnicodeError, ValueError) as error:
            failures.append({"document": relative, "reason": str(error)})
    versions = []
    for check in manifest.get("version_checks", []):
        body = local_path(root, check["document"]).read_text(encoding="utf-8")
        metadata = local_path(root, check["metadata"]).read_text(encoding="utf-8")
        expected = re.search(r'^version = "([^"]+)"$', metadata, re.MULTILINE).group(1)
        observed = re.search(check["pattern"], body, re.MULTILINE)
        value = observed.group(1) if observed else None
        versions.append(
            {"document": check["document"], "expected": expected, "observed": value}
        )
        if value != expected:
            failures.append(
                {
                    "document": check["document"],
                    "reason": "current version mismatch",
                    "expected": expected,
                    "observed": value,
                }
            )
    return {
        "status": "FAIL" if failures else "PASS",
        "scope": manifest["scope"],
        "documents": inventory,
        "document_count": len(inventory),
        "local_destinations_checked": checked_files,
        "local_anchors_checked": checked_anchors,
        "remote_targets_not_fetched": remote,
        "version_checks": versions,
        "failures": failures,
        "limits": "Offline explicit scope; inline/reference Markdown links and ATX/setext heading IDs. "
        "No general renderer equivalence, HTML href audit, remote availability or human review.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--output", type=Path, required=True, help="New receipt path; never overwritten"
    )
    args = parser.parse_args()
    manifest_path = args.manifest or args.root / "tools/documentation_scope.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = audit(args.root, manifest)
        result["manifest_sha256"] = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError, KeyError, AttributeError) as error:
        parser.exit(2, f"Documentation check error: {error}\n")
    print(
        f"{result['status']}: {result['document_count']} documents; "
        f"{result['local_destinations_checked']} local destinations; "
        f"{result['local_anchors_checked']} anchors; {len(result['failures'])} failures"
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
