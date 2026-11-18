"""Narrow command/SQL-shape regression tests, without DuckDB or production data."""

import importlib.util
import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


class RecordingConnection:
    def __init__(self, results=()):
        self.results = iter(results)
        self.statements = []
        self.closed = False

    def execute(self, sql, parameters=()):
        if sql.count("?") != len(parameters):
            raise ValueError("placeholder count does not match bound values")
        if "INSERT INTO dim_" in sql and "(['" in sql:
            raise ValueError("column list must be SQL identifiers, not a Python list")
        self.statements.append((sql, parameters))
        return self

    def fetchone(self):
        return next(self.results, (0,))

    def close(self):
        self.closed = True


class DomainLoaderContractTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "packages/equiframe-sercop/etl_load_ocds.py"
        spec = importlib.util.spec_from_file_location("synthetic_loader_contract", path)
        self.module = importlib.util.module_from_spec(spec)
        self.duckdb = types.ModuleType("duckdb")
        with patch.dict(sys.modules, {"duckdb": self.duckdb}):
            spec.loader.exec_module(self.module)

    def test_dimension_insert_uses_identifier_list(self):
        connection = RecordingConnection([None, (1,)])
        key = self.module.get_or_create_dimension(
            connection,
            "dim_entidad",
            "entidad_id",
            "synthetic.1",
            "entidad_surrogate_key",
            ["entidad_nombre"],
            ["Synthetic"],
        )
        self.assertEqual(key, 1)
        sql, values = connection.statements[-1]
        self.assertIn("(entidad_surrogate_key, entidad_id, entidad_nombre)", sql)
        self.assertEqual(values, [1, "synthetic.1", "Synthetic"])

    def test_fact_insert_binds_each_declared_value_once(self):
        connection = RecordingConnection([(1,)])
        self.module.load_ocds_award(
            connection,
            {
                "id": "award.synthetic",
                "ocid": "process.synthetic",
                "date": "2026-01-01",
                "procuringEntity": {"id": "entity.synthetic"},
                "value": {"amount": 1, "currency": "USD"},
            },
            "snapshot.synthetic",
        )
        inserts = [
            (sql, values)
            for sql, values in connection.statements
            if "INSERT OR IGNORE INTO fact_adjudicacion" in sql
        ]
        self.assertEqual(len(inserts), 1)
        self.assertEqual(len(inserts[0][1]), 12)
        self.assertEqual(inserts[0][0].count("?"), 12)

    def test_partial_load_returns_failure_and_closes_connection(self):
        with tempfile.TemporaryDirectory(prefix="equiframe domain unit ") as directory:
            root = Path(directory)
            database = root / "synthetic.duckdb"
            database.touch()
            source = root / "synthetic.json"
            source.write_text(json.dumps({"ocid": "synthetic", "id": "synthetic"}))
            connection = RecordingConnection()
            self.duckdb.connect = lambda **kwargs: connection
            args = [
                "loader",
                str(source),
                "--snapshot-id",
                "synthetic",
                "--db-path",
                str(database),
            ]
            output = io.StringIO()
            with (
                patch.object(sys, "argv", args),
                patch.object(
                    self.module,
                    "load_ocds_award",
                    side_effect=ValueError("synthetic failure"),
                ),
                redirect_stdout(output),
            ):
                status = self.module.main()
            self.assertEqual(status, 1)
            self.assertTrue(connection.closed)
            self.assertIn("ETL incompleto", output.getvalue())
            self.assertNotIn("ETL completado.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
