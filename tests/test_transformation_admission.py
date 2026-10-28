"""Built-in admission checks never invoke callbacks or import optional runtimes."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

import equiframe as ef

CLASSES = (ef.PandasTransformation, ef.PolarsTransformation, ef.DuckDBTransformation)


def valid_kwargs(cls):
    return {
        "transformation_id": "admitted",
        "code_version": "owned-v1",
        **(
            {"sql": "  SELECT 1 AS id\n"}
            if cls is ef.DuckDBTransformation
            else {"callback": lambda inputs, context: inputs["source"]}
        ),
    }


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize(
    "field,value",
    [
        ("transformation_id", 0),
        ("transformation_id", ""),
        ("transformation_id", "not an identifier"),
        ("revision", True),
        ("revision", 0),
        ("revision", "1"),
        ("code_version", 0),
        ("code_version", ""),
        ("code_version", " padded "),
        ("engine", "other"),
    ],
)
def test_invalid_metadata_is_rejected_before_registration_or_callback(cls, field, value):
    kwargs = valid_kwargs(cls)
    calls = []
    if cls is not ef.DuckDBTransformation:
        kwargs["callback"] = lambda inputs, context: calls.append("called")
    kwargs[field] = value
    expected = ef.InvalidExecutionInput if field == "engine" else ValidationError
    with pytest.raises(expected):
        cls(**kwargs)
    assert not calls


@pytest.mark.parametrize("cls", CLASSES[:2])
@pytest.mark.parametrize("callback", [None, 0, "module.function", {"call": "not-code"}])
def test_callbacks_require_explicit_callable_objects(cls, callback):
    kwargs = valid_kwargs(cls) | {"callback": callback}
    with pytest.raises(ef.InvalidExecutionInput, match="trusted callable"):
        cls(**kwargs)


@pytest.mark.parametrize(
    "sql", [None, 0, b"SELECT 1", "", " \n", "SELECT\x00 1", "SELECT '\ud800'"]
)
def test_sql_invalid_types_empty_nul_and_surrogates_are_rejected(sql):
    with pytest.raises(ef.InvalidExecutionInput):
        ef.DuckDBTransformation("admitted", sql, "owned-v1")


def test_sql_text_remains_exact_and_is_not_executed_or_normalized():
    text = "  SELECT 'quote'' and whitespace' AS id;\n"
    transformation = ef.DuckDBTransformation("admitted", text, "owned-v1")
    assert transformation.sql == text
    assert transformation.revision == 1 and transformation.engine == "duckdb"


def test_base_only_admission_is_lazy_and_never_calls_callback():
    child = """
import json,sys
import equiframe as ef
def callback(*args): raise AssertionError('constructor executed callback')
ef.PandasTransformation('p',callback,'v1')
ef.PolarsTransformation('q',callback,'v1')
ef.DuckDBTransformation('d',' SELECT 1 ','v1')
optional={'pyarrow','pandas','polars','duckdb','numpy','sklearn'}
if optional & set(sys.modules):raise AssertionError('constructor eagerly imported native runtime')
print(json.dumps({'passed':True,'sdk':ef.__file__}))
"""
    result = subprocess.run(
        [sys.executable, "-c", child], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["passed"]
    assert Path(receipt["sdk"]).resolve() == Path(ef.__file__).resolve()
