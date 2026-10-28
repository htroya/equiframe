"""Initialize the optional SERCOP DW without seed data. SPDX-License-Identifier: MIT."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from etl_load_ocds import initialize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Initialize an empty optional SERCOP DW")
    parser.add_argument("--db-path", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        initialize(args.db_path)
    except Exception:
        print("error: initialization failed; inspect destination before retry", file=sys.stderr)
        return 1
    print("Empty DW schema ready; no seed rows inserted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
