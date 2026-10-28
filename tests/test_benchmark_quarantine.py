"""The retired auxiliary benchmark must fail without producing false evidence."""

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

import equiframe.benchmark as benchmark

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "benchmark_local.py"
HELPERS = (
    "run_benchmark",
    "collect_profile_vectors",
    "fit_isolation_forest_mad",
    "detect_anomalies",
    "rule_divergence",
    "compute_metrics",
    "write_summary_tables",
)
EMPTY_ARGUMENTS = {
    "engines": [],
    "families": [],
    "training_vectors": [],
    "bundle": None,
    "vectors": [],
    "results": {},
    "rule_diverge": {},
    "model_decisions": [],
    "profile_vectors": [],
    "m_decisions": [],
    "b_decisions": [],
}


def snapshot(directory: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("name", HELPERS)
@pytest.mark.parametrize("existing", [False, True])
def test_helpers_reject_empty_inputs_without_results_or_files(
    name: str, existing: bool, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work_dir = tmp_path / "benchmark-runs"
    if existing:
        summary = work_dir / "summary"
        summary.mkdir(parents=True)
        (summary / "decisions.csv").write_bytes(b"existing evidence must remain unchanged\n")
    before = snapshot(tmp_path)
    helper = getattr(benchmark, name)
    arguments = {"work_dir": work_dir, **EMPTY_ARGUMENTS}
    keywords = {
        key: arguments[key] for key in inspect.signature(helper).parameters if key in arguments
    }

    with pytest.raises(benchmark.UnsupportedBenchmarkError) as error:
        helper(**keywords)

    assert "quarantined" in str(error.value)
    assert "equiframe_benchmark" in str(error.value)
    assert "packages/equiframe-benchmark/README.md" in str(error.value)
    assert "not a drop-in replacement" in str(error.value)
    assert snapshot(tmp_path) == before
    assert work_dir.exists() is existing
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("name", HELPERS)
def test_helpers_reject_before_accessing_supplied_objects(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Unreadable:
        def __getattribute__(self, name: str) -> object:
            raise AssertionError("quarantine accessed an input")

        def __iter__(self) -> object:
            raise AssertionError("quarantine iterated an input")

        def __len__(self) -> int:
            raise AssertionError("quarantine measured an input")

        def __getitem__(self, key: object) -> object:
            raise AssertionError("quarantine indexed an input")

    def forbidden_io(*args: object, **kwargs: object) -> None:
        raise AssertionError("quarantine attempted filesystem I/O")

    helper = getattr(benchmark, name)
    keywords = {key: Unreadable() for key in inspect.signature(helper).parameters}
    with monkeypatch.context() as patch:
        patch.setattr("builtins.open", forbidden_io)
        patch.setattr("io.open", forbidden_io)
        patch.setattr("os.mkdir", forbidden_io)
        with pytest.raises(benchmark.UnsupportedBenchmarkError, match="quarantined"):
            helper(**keywords)


@pytest.mark.parametrize("entrypoint", [("-m", "equiframe.benchmark"), (str(EXAMPLE),)])
@pytest.mark.parametrize("options", [(), ("--work-dir", "requested", "--fit-only")])
def test_old_cli_fails_clearly_without_artifacts(
    entrypoint: tuple[str, ...], options: tuple[str, ...], tmp_path: Path
) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-B", *entrypoint, *options],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "quarantined" in result.stderr
    assert "equiframe_benchmark" in result.stderr
    assert "packages/equiframe-benchmark/README.md" in result.stderr
    assert "Traceback" not in result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("entrypoint", [("-m", "equiframe.benchmark"), (str(EXAMPLE),)])
def test_old_cli_help_explains_quarantine(entrypoint: tuple[str, ...], tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-B", *entrypoint, "--help"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "quarantined" in result.stdout
    assert "equiframe_benchmark" in result.stdout
    assert result.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_import_and_error_path_need_no_engines_or_benchmark_package(tmp_path: Path) -> None:
    script = """
import importlib.abc
import sys
blocked = {'pandas', 'polars', 'duckdb', 'sklearn', 'numpy', 'pyarrow', 'equiframe_benchmark'}
class RejectOptionalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in blocked:
            raise AssertionError('unexpected optional import: ' + fullname)
sys.meta_path.insert(0, RejectOptionalImports())
original_path = sys.path.copy()
import equiframe as ef
assert 'equiframe.benchmark' not in sys.modules
import equiframe.benchmark as benchmark
assert sys.path == original_path
assert not (blocked & set(sys.modules))
assert not hasattr(benchmark, '_run_single')
for name in ('run_benchmark', 'collect_profile_vectors', 'fit_isolation_forest_mad',
             'detect_anomalies', 'rule_divergence', 'compute_metrics', 'write_summary_tables'):
    assert name not in ef.__all__
try:
    benchmark.compute_metrics({}, [], [])
except benchmark.UnsupportedBenchmarkError:
    pass
else:
    raise AssertionError('quarantined metrics returned a result')
assert not (blocked & set(sys.modules))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == result.stderr == ""
    assert list(tmp_path.iterdir()) == []
