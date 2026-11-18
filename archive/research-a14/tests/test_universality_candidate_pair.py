"""Reject a mislabeled/mixed wheel pair before installation or source execution."""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

CONTROLLER = Path(__file__).parents[1] / "tools/universality/validate_profiles.py"


@pytest.mark.parametrize(
    "core,benchmark", [("0.12.0a11", "0.12.0a13"), ("0.12.0a13", "0.12.0a12")]
)
def test_candidate_pair_identity_fails_before_invoking_installer(
    tmp_path, core, benchmark
):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    for name, version in [("equiframe", core), ("equiframe_benchmark", benchmark)]:
        with zipfile.ZipFile(
            artifacts / f"{name}-{version}-py3-none-any.whl", "w"
        ) as archive:
            archive.writestr(
                f"{name}-{version}.dist-info/METADATA",
                f"Metadata-Version: 2.4\nName: {name.replace('_', '-')}\nVersion: {version}\n",
            )
    command = [
        sys.executable,
        "-I",
        str(CONTROLLER),
        "--candidate-version",
        "0.12.0a13",
    ]
    for argument in (
        "uv",
        "base-python",
        "cache",
        "pins",
        "source",
        "benchmark-source",
        "benchmark-probe",
    ):
        command.extend(["--" + argument, str(tmp_path / "absent")])
    command.extend(
        ["--artifacts", str(artifacts), "--output", str(tmp_path / "output")]
    )
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode != 0
    assert "Candidate archive pair differs from requested identity" in result.stderr
    assert not (tmp_path / "output" / "manifest.json").exists()
