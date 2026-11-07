"""Asset preflight rejects stale format inventory instead of rewriting it."""

import importlib.util
import sys
from pathlib import Path

import pytest

from equiframe import _stability_inventory


def test_asset_check_rejects_stale_schema_inventory(monkeypatch, capsys):
    path = Path(__file__).parents[1] / "tools" / "generate_assets.py"
    spec = importlib.util.spec_from_file_location("asset_inventory_guard", path)
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    original = _stability_inventory.SCHEMA_INVENTORY
    name, status, _ = original[0]
    monkeypatch.setattr(
        _stability_inventory, "SCHEMA_INVENTORY", ((name, status, "0" * 64), *original[1:])
    )
    monkeypatch.setattr(sys, "argv", [str(path), "--check"])
    with pytest.raises(SystemExit) as stopped:
        generator.main()
    assert stopped.value.code == 1
    assert "Schema inventory differs: " + name in capsys.readouterr().err
    assert _stability_inventory.SCHEMA_INVENTORY[0][2] == "0" * 64
