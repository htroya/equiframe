"""The supplementary diff declaration follows the same bounded local admission."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pytest

import equiframe as ef
from equiframe.local import local_path


def completed_diff(root):
    table = pa.table({"id": [1, 2]})
    result = ef.diff(table, table, work_dir=root)
    declaration = ef.read_diff_contract(result)
    assert declaration.spec == result.spec
    manifest = local_path(result.differences).parent / "diff-contract.json"
    return result, manifest


@pytest.mark.parametrize("kind", ["directory", "oversized"])
def test_special_or_oversized_companion_is_refused(tmp_path, kind):
    result, manifest = completed_diff(tmp_path / "operation")
    manifest.unlink()
    if kind == "directory":
        manifest.mkdir()
        expected = ef.ArtifactIntegrityError
    else:
        with manifest.open("xb") as output:
            output.truncate(64 * 1024 * 1024 + 1)
        expected = ef.ResourceLimitError
    with pytest.raises(expected):
        ef.read_diff_contract(result)


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_companion_parent_links_do_not_erase_the_boundary(tmp_path, kind):
    if kind == "junction" and os.name != "nt":
        pytest.skip("Windows directory junction")
    result, manifest = completed_diff(tmp_path / "operation")
    original = manifest.read_bytes()
    link = tmp_path / "linked"
    if kind == "symlink":
        try:
            link.symlink_to(manifest.parent, target_is_directory=True)
        except OSError:
            pytest.skip("Host does not permit directory symlinks")
    else:
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(manifest.parent)],
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert created.returncode == 0, created.stderr
    try:
        redirected_ref = result.differences.model_copy(
            update={"uri": (link / "differences.jsonl").as_uri()}
        )
        redirected = result.model_copy(update={"differences": redirected_ref})
        with pytest.raises(ef.ArtifactIntegrityError):
            ef.read_diff_contract(redirected)
        assert manifest.read_bytes() == original
    finally:
        if kind == "junction":
            link.rmdir()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO")
def test_fifo_companion_is_refused_before_waiting_for_a_writer(tmp_path):
    _, manifest = completed_diff(tmp_path / "operation")
    manifest.unlink()
    os.mkfifo(manifest, 0o600)
    child = """
import json, sys
from pathlib import Path
import equiframe as ef
result = ef.read_comparison(Path(sys.argv[1]))
try:
    ef.read_diff_contract(result)
except ef.ArtifactIntegrityError:
    print(json.dumps({'rejected': True, 'sdk': ef.__file__}))
else:
    raise AssertionError('FIFO companion was admitted')
"""
    completed = subprocess.run(
        [sys.executable, "-c", child, str(manifest.parent / "comparison.json")],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["rejected"] is True
    assert Path(receipt["sdk"]).resolve() == Path(ef.__file__).resolve()
