from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .domain_checks import run_domains
from .evidence import ConsumerError
from .programs import ENGINES, PROGRAMS, VARIANTS
from .runner import fault_checks, run_all, run_case


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independent offline consumer of installed EquiFrame 0.12.3"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser(
        "run", help="Execute actual workflows; every output must be a new directory"
    )
    run.add_argument(
        "--all",
        action="store_true",
        help="Run the finite 72-case matrix; suite exit refers to expected outcomes",
    )
    run.add_argument(
        "--require-optimized",
        action="store_true",
        help="Require a real python -O interpreter for this complete 72-case matrix",
    )
    run.add_argument("--data", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--program", choices=PROGRAMS, default="reconciliation")
    run.add_argument("--variant", choices=VARIANTS, default="good")
    run.add_argument("--source", choices=ENGINES, default="pandas")
    run.add_argument("--target", choices=ENGINES, default="duckdb")
    faults = sub.add_parser(
        "fault-checks", help="Bounded explicit acceptance/publication/corruption controls"
    )
    faults.add_argument("--output", type=Path, required=True)
    domains = sub.add_parser(
        "domain-checks",
        help="Synthetic finance/retail/telemetry: good, divergent and invalid inputs",
    )
    domains.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "fault-checks":
            return fault_checks(args.output.resolve())
        if args.command == "domain-checks":
            return run_domains(args.output.resolve())
        if args.require_optimized and not args.all:
            raise ConsumerError("--require-optimized is only valid with run --all")
        if args.source == args.target:
            raise ConsumerError("Source and target engines must differ")
        if args.all:
            return run_all(
                args.data.resolve(),
                args.output.resolve(),
                require_optimized=args.require_optimized,
            )
        return run_case(
            args.data.resolve(),
            args.output.resolve(),
            program=args.program,
            variant=args.variant,
            source=args.source,
            target=args.target,
        )
    except (ConsumerError, OSError, ValueError) as error:
        print(f"consumer_error: {error}", file=sys.stderr)
        return 2
