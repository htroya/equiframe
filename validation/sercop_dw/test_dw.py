"""Functional checks with local synthetic inputs only. SPDX-License-Identifier: MIT."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import duckdb

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("sercop_dw", ROOT / "etl_load_ocds.py")
assert SPEC is not None and SPEC.loader is not None
dw = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dw
SPEC.loader.exec_module(dw)
STAMP = "2026-01-02T03:04:05+00:00"


def award(index: int = 0) -> dict:
    return {
        "ocid": f"synthetic-ocid-{index // 10}",
        "id": f"award-{index}",
        "date": "2026-01-02",
        "value": {"amount": 1.01, "currency": "USD"},
        "status": "active",
        "modalidad": f"mode-{index % 3}",
        "procedimiento": f"procedure-{index % 5}",
        "procuringEntity": {"id": f"entity-{index % 7}", "name": f"Entity {index % 7}"},
        "suppliers": [{"id": f"supplier-{index % 17}", "name": f"Supplier {index % 17}"}],
        "items": [{"id": f"item-{index % 31}", "description": f"Item {index % 31}"}],
    }


class DWTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="sercop-functional-", dir=os.environ.get("EQUIFRAME_DW_TEST_ROOT")
        )
        self.root = Path(self.temporary.name)
        self.cwd = self.root / "unrelated-cwd"
        self.cwd.mkdir()
        self.db = self.root / "explicit.duckdb"
        self.input = self.root / "awards.json"

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, rows):
        self.input.write_text(json.dumps(rows, ensure_ascii=False), "utf-8")

    def run_cli(self, script, *args, success=True, timeout=120):
        result = subprocess.run(
            [sys.executable, "-E", "-s", "-B", str(ROOT / script), *map(str, args)],
            cwd=self.cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")
        else:
            self.assertGreaterEqual(result.returncode, 1)
            self.assertTrue(result.stderr)
        self.assertFalse((self.cwd / "dw_sercop.duckdb").exists())
        self.assertFalse(list(self.root.glob(".sercop-dw-*")))
        return result

    def cli_load(self, snapshot="synthetic-snapshot", success=True):
        return self.run_cli(
            "etl_load_ocds.py",
            self.input,
            "--db-path",
            self.db,
            "--snapshot-id",
            snapshot,
            "--snapshot-timestamp",
            STAMP,
            success=success,
        )

    def query(self, sql, parameters=None):
        with duckdb.connect(str(self.db), read_only=True) as connection:
            return connection.execute(sql, parameters or []).fetchall()

    def test_initialize_custom_path_is_schema_only_and_repeatable(self):
        self.run_cli("etl_init.py", "--db-path", self.db)
        for table in dw.TABLES:
            self.assertEqual(self.query(f"SELECT count(*) FROM {table}"), [(0,)])
        self.run_cli("etl_init.py", "--db-path", self.db)
        self.assertEqual(self.query("SELECT version FROM _sercop_dw_schema"), [(1,)])

    def test_thirty_thousand_real_rows_repeat_without_duplicates(self):
        rows = [award(i) for i in range(30_000)]
        self.write(rows)
        first = self.cli_load()
        self.assertEqual(json.loads(first.stdout), {"awards": 30_000, "repeated": False})
        self.assertEqual(
            self.query("SELECT count(*), sum(monto) FROM fact_adjudicacion"),
            [(30_000, Decimal("30300.00"))],
        )
        self.assertEqual(self.query("SELECT count(*) FROM dim_entidad"), [(7,)])
        self.assertEqual(self.query("SELECT count(*) FROM dim_proveedor"), [(17,)])
        self.assertEqual(self.query("SELECT count(*) FROM dim_item"), [(31,)])
        self.assertEqual(
            self.query(
                "SELECT modalidad, procedimiento FROM fact_adjudicacion WHERE award_id=?",
                ["award-29"],
            ),
            [("mode-2", "procedure-4")],
        )
        self.write(list(reversed(rows)))
        second = self.cli_load()
        self.assertEqual(json.loads(second.stdout), {"awards": 30_000, "repeated": True})
        self.assertEqual(self.query("SELECT count(*) FROM fact_adjudicacion"), [(30_000,)])
        self.assertEqual(self.query("SELECT count(*) FROM snapshot"), [(1,)])

    def test_changed_snapshot_and_metadata_are_rejected_without_mutation(self):
        self.write([award()])
        self.cli_load()
        changed = award()
        changed["modalidad"] = "changed"
        self.write([changed])
        self.cli_load(success=False)
        self.assertEqual(self.query("SELECT modalidad FROM fact_adjudicacion"), [("mode-0",)])
        self.write([award()])
        with self.assertRaises(dw.InputError):
            dw.load(
                self.input,
                self.db,
                snapshot_id="synthetic-snapshot",
                timestamp=STAMP,
                source="another-source",
            )
        self.assertEqual(self.query("SELECT count(*) FROM snapshot"), [(1,)])

    def test_actual_database_constraint_failure_rolls_back_all_changes(self):
        self.write([award()])
        self.cli_load()
        with duckdb.connect(str(self.db)) as connection:
            connection.execute(
                "CREATE UNIQUE INDEX reject_duplicate_modes ON fact_adjudicacion(modalidad)"
            )
        rows = [award(100), award(101)]
        for row in rows:
            row["modalidad"] = "duplicate-mode"
            row["procuringEntity"] = {"id": "entity-0", "name": "changed-in-failed-batch"}
        self.write(rows)
        result = self.cli_load("failed-snapshot", success=False)
        self.assertNotIn("changed-in-failed-batch", result.stderr)
        self.assertEqual(self.query("SELECT count(*) FROM snapshot"), [(1,)])
        self.assertEqual(self.query("SELECT count(*) FROM fact_adjudicacion"), [(1,)])
        self.assertEqual(self.query("SELECT entidad_nombre FROM dim_entidad"), [("Entity 0",)])
        self.assertEqual(self.query("SELECT count(*) FROM dim_proveedor"), [(1,)])
        self.assertEqual(self.query("SELECT count(*) FROM dim_item"), [(1,)])

    def test_bad_json_duplicates_missing_dates_and_multiple_items_fail_closed(self):
        base = award()
        invalid = [
            [base, base],
            [{**base, "date": None}],
            [{**base, "items": [{"id": "a"}, {"id": "b"}]}],
            [{**base, "suppliers": [{"id": "a"}, {"id": "b"}]}],
            [{**base, "value": {"amount": 1.001, "currency": "USD"}}],
            [{**base, "value": {"amount": True, "currency": "USD"}}],
        ]
        for rows in invalid:
            with self.subTest(rows_index=invalid.index(rows)):
                self.write(rows)
                self.cli_load(success=False)
                self.assertFalse(self.db.exists())
        self.input.write_text('{"awards":[],"awards":[]}', "utf-8")
        self.cli_load(success=False)
        self.input.write_text('{"value":NaN}', "utf-8")
        self.cli_load(success=False)
        self.assertFalse(self.db.exists())

    def test_bound_values_preserve_sql_like_text_and_exact_decimal(self):
        row = award()
        marker = "entity-name'); DROP TABLE snapshot; --"
        row["procuringEntity"]["name"] = marker
        self.write([row])
        self.cli_load()
        self.assertEqual(self.query("SELECT entidad_nombre FROM dim_entidad"), [(marker,)])
        self.assertEqual(self.query("SELECT monto FROM fact_adjudicacion"), [(Decimal("1.01"),)])
        self.assertEqual(self.query("SELECT count(*) FROM snapshot"), [(1,)])

    def test_existing_foreign_database_and_aliases_are_rejected(self):
        with duckdb.connect(str(self.db)) as connection:
            connection.execute("CREATE TABLE sentinel(value INTEGER)")
            connection.execute("INSERT INTO sentinel VALUES (42)")
        self.write([award()])
        self.cli_load(success=False)
        self.assertEqual(self.query("SELECT * FROM sentinel"), [(42,)])
        alias = self.root / "alias.json"
        os.link(self.input, alias)
        with self.assertRaises(dw.InputError):
            dw.read_awards(alias)

    def test_exclusive_publication_preserves_a_racing_destination(self):
        def race(_source, destination):
            Path(destination).write_bytes(b"synthetic-racing-file")
            raise FileExistsError("synthetic publication race")

        with patch.object(dw.os, "link", race), self.assertRaises(FileExistsError):
            dw.initialize(self.db)
        self.assertEqual(self.db.read_bytes(), b"synthetic-racing-file")
        self.assertFalse(list(self.root.glob(".sercop-dw-*")))

    def test_cli_help_and_argument_errors_use_standard_exit_channels(self):
        self.run_cli("etl_load_ocds.py", "--help")
        self.run_cli("etl_init.py", "--help")
        self.run_cli("etl_load_ocds.py", success=False)
        self.run_cli("etl_init.py", success=False)
        self.assertFalse(self.db.exists())

    def test_outer_ocid_and_dimension_conflicts_are_explicit(self):
        row = award()
        del row["ocid"]
        self.write({"ocid": "synthetic-parent", "awards": [row]})
        self.cli_load()
        self.assertEqual(self.query("SELECT ocid FROM fact_adjudicacion"), [("synthetic-parent",)])
        first = award(10)
        second = copy.deepcopy(first)
        second["id"] = "different-award"
        second["procuringEntity"]["name"] = "conflicting-name"
        self.write([first, second])
        self.cli_load("conflicting-snapshot", success=False)
        self.assertEqual(self.query("SELECT count(*) FROM snapshot"), [(1,)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
