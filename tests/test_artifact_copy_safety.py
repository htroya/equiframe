"""Artifact copies reject special files and bound reads by declared identities."""

import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

import equiframe as ef
from equiframe import local


def reference(path, size, digest=None):
    return ef.ArtifactRef(
        schema_version="1.0",
        uri=path.absolute().as_uri(),
        sha256=digest or hashlib.sha256(b"").hexdigest(),
        format="json",
        media_type="application/json",
        size_bytes=size,
    )


def test_copy_reads_at_most_declared_size_plus_one_before_refusing(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    source.write_bytes(b"x" * 1024)
    calls = []
    real_open = local.open_regular_file

    @contextmanager
    def tracked(path):
        with real_open(path) as stream:

            class Reader:
                def read(self, count):
                    calls.append(count)
                    return stream.read(count)

            yield Reader()

    monkeypatch.setattr(local, "open_regular_file", tracked)
    target = tmp_path / "copied.json"
    with pytest.raises(ef.ArtifactIntegrityError, match="declared byte size"):
        ef.LocalArtifactStore(tmp_path / "store").get(reference(source, 2), target)
    assert calls == [3]
    assert source.read_bytes() == b"x" * 1024
    assert not target.exists() and not list(tmp_path.rglob("*.part"))


def test_empty_verified_artifact_can_still_be_copied(tmp_path):
    source = tmp_path / "source.json"
    source.write_bytes(b"")
    target = tmp_path / "copied.json"
    assert ef.LocalArtifactStore(tmp_path / "store").get(reference(source, 0), target) == target
    assert source.read_bytes() == target.read_bytes() == b""


@pytest.mark.parametrize("value", [None, "path-as-text", {"wrong": 1}])
def test_public_artifact_paths_have_explicit_type_errors(tmp_path, value):
    with pytest.raises(TypeError, match="store root"):
        ef.LocalArtifactStore(value)
    store = ef.LocalArtifactStore(tmp_path / "store")
    with pytest.raises(TypeError, match="artifact input"):
        store.put(value, media_type="application/json")
    with pytest.raises(TypeError, match="artifact destination"):
        store.get(reference(tmp_path / "unused.json", 0), value)
    assert not (tmp_path / "store").exists()


def test_file_kind_is_checked_before_creating_output_directories(tmp_path):
    directory = tmp_path / "source.json"
    directory.mkdir()
    store = ef.LocalArtifactStore(tmp_path / "new-store")
    with pytest.raises(ef.ArtifactIntegrityError, match="regular file"):
        store.put(directory, media_type="application/json")
    assert not (tmp_path / "new-store").exists()


@pytest.mark.parametrize("boundary", ["source", "store", "destination"])
@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_linked_directories_cannot_redirect_an_artifact_copy(tmp_path, boundary, kind):
    if kind == "junction" and os.name != "nt":
        pytest.skip("Windows directory junction")
    real = tmp_path / "real"
    real.mkdir()
    (real / "source.json").write_bytes(b"{}")
    link = tmp_path / "linked"
    if kind == "junction":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(real)],
            capture_output=True,
            check=False,
            timeout=10,
        )
        assert result.returncode == 0
    else:
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError:
            pytest.skip("Host does not permit directory symlinks")
    try:
        with pytest.raises(ef.ArtifactIntegrityError, match=r"links|reparse"):
            if boundary == "source":
                ef.LocalArtifactStore(tmp_path / "store").put(
                    link / "source.json", media_type="application/json"
                )
            elif boundary == "store":
                ef.LocalArtifactStore(link).put(real / "source.json", media_type="application/json")
            else:
                ef.LocalArtifactStore(tmp_path / "store").get(
                    reference(real / "source.json", 2, hashlib.sha256(b"{}").hexdigest()),
                    link / "copied.json",
                )
        assert {p.name for p in real.iterdir()} == {"source.json"}
        assert (real / "source.json").read_bytes() == b"{}"
        assert not list(tmp_path.rglob("*.part"))
    finally:
        if kind == "junction":
            link.rmdir()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO")
@pytest.mark.parametrize("operation", ["put", "get"])
def test_fifo_cannot_block_an_artifact_copy(tmp_path, operation):
    fifo = tmp_path / "source.json"
    os.mkfifo(fifo, 0o600)
    code = """
import json,sys
from pathlib import Path
import equiframe as ef
p=Path(sys.argv[1]); operation=sys.argv[2]
store=ef.LocalArtifactStore(p.parent/'store')
try:
    if operation=='put': store.put(p,media_type='application/json')
    else: store.get(ef.ArtifactRef(schema_version='1.0',uri=p.as_uri(),
        sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        format='json',media_type='application/json',size_bytes=0),p.parent/'copied.json')
except ef.ArtifactIntegrityError:
    print(json.dumps({'rejected':True,'sdk':ef.__file__}))
else: raise AssertionError('Special file was accepted')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(fifo), operation],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["rejected"] is True
    assert Path(receipt["sdk"]).resolve() == Path(ef.__file__).resolve()
    assert not (tmp_path / "store").exists() and not (tmp_path / "copied.json").exists()
