"""Incomplete scale evidence fails with safe, actionable public errors."""

import os
import subprocess

import equiframe as ef
import pytest

from equiframe_benchmark.scaling import read_scale


def test_existing_operation_without_finalization_keeps_a_safe_os_failure(tmp_path):
    with pytest.raises(FileNotFoundError, match="finalization is missing or unreadable") as caught:
        read_scale(tmp_path)
    assert caught.value.filename is None and caught.value.errno == 2
    assert list(tmp_path.iterdir()) == []


def test_missing_directory_retains_the_io_recovery_cause(tmp_path):
    with pytest.raises(ef.ArtifactIOError) as caught:
        read_scale(tmp_path / "missing")
    assert isinstance(caught.value.__cause__, FileNotFoundError)
    assert not (tmp_path / "missing").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction")
def test_junction_root_is_rejected_before_reading_any_finalization(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "linked"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert completed.returncode == 0
    try:
        with pytest.raises(ef.ArtifactIntegrityError, match="reparse"):
            read_scale(link)
        assert list(real.iterdir()) == []
    finally:
        link.rmdir()
