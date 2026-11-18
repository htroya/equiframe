"""Check the pending publisher identity without building, installing or uploading."""

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "schema_version": "1.0",
    "project_name": "equiframe",
    "owner": "htroya",
    "repository": "equiframe",
    "workflow_filename": "publish-testpypi.yml",
    "environment_name": "testpypi",
    "mode": "configuration_only",
    "publication_enabled": False,
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate configuration field")
        result[key] = value
    return result


def read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("Invalid configuration file")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def check(root):
    config = read_json(root / "tools/testpypi_publisher.json")
    if config != EXPECTED or config["publication_enabled"] is not False:
        raise ValueError("Publisher identity or preparation mode differs")
    project = tomllib.loads(
        (root / "packages/equiframe/pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    if project["name"] != config["project_name"]:
        raise ValueError("Project metadata differs")
    if project["urls"]["Repository"] != "https://github.com/htroya/equiframe":
        raise ValueError("Repository metadata differs")
    workflow = read_json(root / ".github/workflows" / config["workflow_filename"])
    if workflow["on"] != {"workflow_dispatch": {}}:
        raise ValueError("Workflow must remain manual")
    if workflow["permissions"] != {"contents": "read"}:
        raise ValueError("Unexpected workflow permission")
    if set(workflow["jobs"]) != {"configuration"}:
        raise ValueError("Unexpected workflow job")
    job = workflow["jobs"]["configuration"]
    if job["environment"] != {"name": config["environment_name"]}:
        raise ValueError("Environment identity differs")
    if "permissions" in job:
        raise ValueError("Unexpected job permission")
    actions = [step for step in job["steps"] if "uses" in step]
    if len(actions) != 2 or any(
        not re.fullmatch(r"actions/(checkout|setup-python)@[0-9a-f]{40}", step["uses"])
        for step in actions
    ):
        raise ValueError("Actions must remain pinned")
    if actions[0]["with"]["persist-credentials"] is not False:
        raise ValueError("Checkout must discard credentials")
    commands = [step["run"] for step in job["steps"] if "run" in step]
    if commands != ['python tools/check_testpypi_publisher.py --output "$GITHUB_STEP_SUMMARY"']:
        raise ValueError("Package operations are outside this preparation")
    policy = read_json(root / "packages/equiframe/tools/release-policy.json")
    if policy["publication_enabled"] is not False:
        raise ValueError("Publication policy must remain disabled")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if repository and repository != "htroya/equiframe":
        raise ValueError("Actions repository differs")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        config = check(ROOT)
    except (OSError, ValueError, KeyError, TypeError):
        print("Publisher configuration check failed.", file=sys.stderr)
        return 1
    report = (
        "TestPyPI configuration: PASS\n\n"
        "| Field | Value |\n|---|---|\n"
        + "".join(
            f"| {field} | `{config[field]}` |\n"
            for field in (
                "project_name",
                "owner",
                "repository",
                "workflow_filename",
                "environment_name",
            )
        )
        + "\nConfiguration only; no build, upload, package installation or OIDC token.\n"
    )
    if args.output:
        with args.output.open("a", encoding="utf-8") as stream:
            stream.write(report)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
