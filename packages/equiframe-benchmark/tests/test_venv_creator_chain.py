"""Nested CPython venv creation metadata cannot authorize arbitrary commands."""

import pytest

from equiframe_benchmark.scale_process import _creator_matches_base, _venv_config


def base_python(tmp_path):
    home = tmp_path / "base"
    home.mkdir()
    base = home / "python.exe"
    base.write_bytes(b"synthetic interpreter identity; never executed")
    return home, base


def venv(tmp_path, name, home, creator):
    root = tmp_path / name
    scripts = root / "Scripts"
    scripts.mkdir(parents=True)
    launcher = scripts / "python.exe"
    launcher.write_bytes(b"synthetic launcher identity; never executed")
    (root / "pyvenv.cfg").write_text(
        f"home = {home}\nimplementation = CPython\nexecutable = {creator}\n", encoding="utf8"
    )
    return launcher


def test_two_creator_venvs_bind_to_the_same_actual_base(tmp_path):
    home, base = base_python(tmp_path)
    first = venv(tmp_path, "first", home, base)
    second = venv(tmp_path, "second", home, first)
    assert _creator_matches_base(second, base, home)
    assert _creator_matches_base(first, base, home)
    assert _creator_matches_base(base, base, home)


@pytest.mark.parametrize("problem", ["cycle", "wrong_home", "relative", "duplicate", "large"])
def test_invalid_creator_metadata_fails_closed(tmp_path, problem):
    home, base = base_python(tmp_path)
    launcher = venv(tmp_path, "creator", home, base)
    config = launcher.parent.parent / "pyvenv.cfg"
    if problem == "cycle":
        config.write_text(f"home = {home}\nexecutable = {launcher}\n", encoding="utf8")
    elif problem == "wrong_home":
        config.write_text(f"home = {tmp_path}\nexecutable = {base}\n", encoding="utf8")
    elif problem == "relative":
        config.write_text(f"home = {home}\nexecutable = relative/python.exe\n", encoding="utf8")
    elif problem == "duplicate":
        config.write_text(f"home = {home}\nHOME = {home}\nexecutable = {base}\n", encoding="utf8")
    else:
        config.write_bytes(b"#" * (64 * 1024 + 1))
    before = config.read_bytes()
    assert not _creator_matches_base(launcher, base, home)
    assert config.read_bytes() == before


def test_creator_chain_has_an_explicit_depth_limit(tmp_path):
    home, base = base_python(tmp_path)
    creator = base
    for index in range(16):
        creator = venv(tmp_path, f"creator-{index}", home, creator)
    assert _creator_matches_base(creator, base, home)
    seventeenth = venv(tmp_path, "creator-16", home, creator)
    assert not _creator_matches_base(seventeenth, base, home)


def test_directory_is_never_parsed_as_venv_configuration(tmp_path):
    path = tmp_path / "pyvenv.cfg"
    path.mkdir()
    assert _venv_config(path) is None


def test_unrelated_executable_is_never_a_creator_venv(tmp_path):
    home, base = base_python(tmp_path)
    unrelated = tmp_path / "other" / "python.exe"
    unrelated.parent.mkdir()
    unrelated.write_bytes(b"never executed")
    assert not _creator_matches_base(unrelated, base, home)
