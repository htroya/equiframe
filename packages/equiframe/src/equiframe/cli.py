"""CLI delegates contract validation to the public Python API."""

from pathlib import Path

import typer

from equiframe.errors import ContractIOError, ContractValidationError
from equiframe.serialization import contract_fingerprint, read_contract

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)
contract_app = typer.Typer(no_args_is_help=True)
app.add_typer(contract_app, name="contract", help="Validate semantic contract metadata.")


@contract_app.command("validate")
def validate(path: Path) -> None:
    """Validate a contract JSON file. Exit 0: valid; 2: invalid; 3: I/O failure."""
    try:
        contract = read_contract(path)
    except ContractValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except ContractIOError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    typer.echo(f"Valid contract: {contract.contract_id} revision {contract.revision}")
    typer.echo("SHA-256 metadata: " + contract_fingerprint(contract))


def main() -> None:
    app()
