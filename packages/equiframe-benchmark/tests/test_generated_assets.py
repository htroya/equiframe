"""The release asset command must validate both delivered protocol families."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def staged_assets(tmp_path):
    root = tmp_path / "assets"
    tools = root / "tools"
    tools.mkdir(parents=True)
    for name in ("generate_assets.py", "generate_assets_v2.py"):
        shutil.copyfile(ROOT / "tools" / name, tools / name)
    shutil.copytree(ROOT / "schemas", root / "schemas")
    return root


def schema_hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (root / "schemas").rglob("*.schema.json")
    }


def run_assets(root, *arguments):
    return subprocess.run(
        [sys.executable, "-I", "-B", str(root / "tools/generate_assets.py"), *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_assets_command_rejects_stale_v2_when_v1_is_current(tmp_path):
    root = staged_assets(tmp_path)
    before = schema_hashes(root)
    baseline = run_assets(root, "--check")
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    target = root / "schemas/protocol-v2/FreezeManifestV2-2.0.schema.json"
    schema = json.loads(target.read_text("utf-8"))
    schema["$defs"]["DetectorVersions"]["properties"]["equiframe"]["default"] = "0.12.0"
    target.write_text(json.dumps(schema, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    result = run_assets(root, "--check")
    assert result.returncode != 0
    assert "outdated schema: protocol-v2/FreezeManifestV2-2.0.schema.json" in result.stderr
    assert not result.stdout.strip()
    after = schema_hashes(root)
    assert {key: value for key, value in before.items() if "/protocol-v2/" not in key} == {
        key: value for key, value in after.items() if "/protocol-v2/" not in key
    }


def test_assets_generation_restores_both_families_and_preserves_matching_bytes(tmp_path):
    root = staged_assets(tmp_path)
    before = schema_hashes(root)
    for relative in (
        "schemas/StudyResult-1.0.schema.json",
        "schemas/protocol-v2/FreezeManifestV2-2.0.schema.json",
    ):
        (root / relative).unlink()
    result = run_assets(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert schema_hashes(root) == before
    checked = run_assets(root, "--check")
    assert checked.returncode == 0, checked.stdout + checked.stderr
