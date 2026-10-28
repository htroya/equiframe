"""Opt-in pytest example: one pass and two intentional assertion failures.

From packages/equiframe, run:
    python -m pytest -q examples/test_assertion_recipe.py -k equivalent
    python -m pytest -q examples/test_assertion_recipe.py -k different
    python -m pytest -q examples/test_assertion_recipe.py -k not_evaluable

Each command needs a fresh ci-reports/<scenario> directory. For CI, select the
appropriate test, run verify_upload_directory in an always() step, and upload
only that exact REDACTED directory if verification succeeds. The assertions
remain failures after reports are written. Ordinary
package tests do not collect this opt-in example. No pytest plugin is required.
"""

from pathlib import Path

import pytest
from assertion_ci import Scenario, run_recipe


@pytest.mark.parametrize("scenario", ["equivalent", "different", "not_evaluable"])
def test_materialized_output(scenario: Scenario) -> None:
    run_recipe(Path("ci-reports") / scenario, scenario=scenario)
