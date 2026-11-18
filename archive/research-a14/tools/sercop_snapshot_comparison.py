"""Compare every package/release between two retained annual JSON captures.

Exact JSON encoding retains Decimal exponent/scale and signed zero. Package
metadata differences are kept separately; matching release arrays does not
replace either original, relabel a projection or approve a scientific cohort.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from itertools import zip_longest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "sources", Path(__file__).with_name("sercop_local_repository.py")
)
sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sources)


def compare_packages(old_archive, new_archive, output):
    sources.require(not output.exists(), "Preserve existing snapshot comparison")
    output.mkdir(parents=True)
    old_sha, new_sha = sources.digest(old_archive), sources.digest(new_archive)
    source_sha = sources.digest(Path(__file__))
    counters, metadata_groups, changes = Counter(), {}, Counter()
    hashes = {name: hashlib.sha256() for name in ("old_releases", "new_releases")}
    with (
        (output / "all-package-observations.jsonl").open(
            "x", encoding="utf-8", newline="\n"
        ) as observations,
        (output / "changed-release-packages.jsonl").open(
            "x", encoding="utf-8", newline="\n"
        ) as differences,
    ):
        for left, right in zip_longest(
            sources.source_packages(old_archive), sources.source_packages(new_archive)
        ):
            counters["package_positions"] += 1
            release_text = {}
            for label, package in (("old", left), ("new", right)):
                if package is not None:
                    text = sources.exact_json(package[2]["releases"])
                    release_text[label] = text
                    hashes[label + "_releases"].update((text + "\n").encode())
                    counters[label + "_release_occurrences"] += len(
                        package[2]["releases"]
                    )
            if left is None or right is None:
                counters["unpaired_packages"] += 1
                record = {
                    "index": counters["package_positions"] - 1,
                    "old_package": left[2] if left else None,
                    "new_package": right[2] if right else None,
                }
                differences.write(sources.exact_json(record) + "\n")
                observations.write(
                    sources.exact_json(
                        {
                            "index": record["index"],
                            "unpaired": True,
                            "old_present": left is not None,
                            "new_present": right is not None,
                        }
                    )
                    + "\n"
                )
                continue
            old_member, index, old = left
            new_member, new_index, new = right
            sources.require(index == new_index, "Package position drift")
            old_releases, new_releases = (
                release_text["old"],
                release_text["new"],
            )
            old_release_sha = hashlib.sha256(old_releases.encode()).hexdigest()
            new_release_sha = hashlib.sha256(new_releases.encode()).hexdigest()
            equal = old_releases == new_releases
            counters[
                "equal_release_arrays" if equal else "different_release_arrays"
            ] += 1
            if not equal:
                differences.write(
                    sources.exact_json(
                        {
                            "index": index,
                            "old_releases": old["releases"],
                            "new_releases": new["releases"],
                        }
                    )
                    + "\n"
                )
            old_meta = {k: v for k, v in old.items() if k != "releases"}
            new_meta = {k: v for k, v in new.items() if k != "releases"}
            old_meta_json, new_meta_json = (
                sources.exact_json(old_meta),
                sources.exact_json(new_meta),
            )
            group = hashlib.sha256(
                (old_meta_json + "\n" + new_meta_json).encode()
            ).hexdigest()
            if group not in metadata_groups:
                metadata_groups[group] = {
                    "old": old_meta,
                    "new": new_meta,
                    "package_count": 0,
                }
            metadata_groups[group]["package_count"] += 1
            changed_keys = []
            for key in sorted(set(old_meta) | set(new_meta)):
                if (
                    key not in old_meta
                    or key not in new_meta
                    or sources.exact_json(old_meta[key])
                    != sources.exact_json(new_meta[key])
                ):
                    changed_keys.append(key)
                    changes[key] += 1
            observations.write(
                sources.exact_json(
                    {
                        "index": index,
                        "old_member": old_member,
                        "new_member": new_member,
                        "old_release_sha256": old_release_sha,
                        "new_release_sha256": new_release_sha,
                        "releases_equal": equal,
                        "metadata_group": group,
                        "changed_metadata_keys": changed_keys,
                    }
                )
                + "\n"
            )
    sources.require(
        sources.digest(old_archive) == old_sha
        and sources.digest(new_archive) == new_sha
        and sources.digest(Path(__file__)) == source_sha,
        "Source changed during comparison",
    )
    metadata_path = output / "complete-metadata-groups.json"
    metadata_path.write_text(
        sources.exact_json(metadata_groups) + "\n", encoding="utf-8", newline="\n"
    )
    report = {
        "schema": "equiframe.sercop-snapshot-comparison.v1",
        "old_archive_sha256": old_sha,
        "new_archive_sha256": new_sha,
        "tool_sha256": source_sha,
        "counts": dict(counters),
        "changed_package_metadata_keys": dict(changes),
        "distinct_complete_metadata_pairs": len(metadata_groups),
        "release_arrays_equal": counters["different_release_arrays"] == 0
        and counters["unpaired_packages"] == 0,
        "all_packages_checked": True,
        "release_sequence_sha256": {k: v.hexdigest() for k, v in hashes.items()},
        "observation_file_sha256": sources.digest(
            output / "all-package-observations.jsonl"
        ),
        "changed_release_file_sha256": sources.digest(
            output / "changed-release-packages.jsonl"
        ),
        "metadata_groups_sha256": sources.digest(metadata_path),
        "source_number_binary_float_conversion": False,
        "scope": "All paired annual release arrays and complete package metadata;exact Decimal text comparison;originals preserved;no projection relabeling or scientific approval",
    }
    sources.write(output / "result.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_packages(args.old, args.new, args.output)
    print(
        json.dumps(
            {
                "counts": result["counts"],
                "changed_metadata_keys": result["changed_package_metadata_keys"],
                "release_arrays_equal": result["release_arrays_equal"],
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
