"""Serve only an explicitly selected public dataset directory using GET/HEAD."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar


class ReadOnlyHandler(SimpleHTTPRequestHandler):
    extensions_map: ClassVar[dict[str, str]] = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".json": "application/json; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
        ".parquet": "application/octet-stream",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    def translate_path(self, path):
        selected = Path(super().translate_path(path))
        root = Path(self.directory).resolve()
        if not selected.resolve().is_relative_to(root):
            return str(root / "__outside_selected_dataset__")
        for parent in (selected, *selected.parents):
            if parent == root:
                break
            if parent.is_symlink():
                return str(root / "__linked_dataset_member__")
        return str(selected)

    def reject_write(self):
        self.send_response(405)
        self.send_header("Allow", "GET, HEAD")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_POST = reject_write
    do_PUT = reject_write
    do_PATCH = reject_write
    do_DELETE = reject_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--public", action="store_true")
    args = parser.parse_args()
    if args.host != "127.0.0.1" and not args.public:
        parser.error("Non-loopback serving requires the explicit --public flag")
    root = args.root.resolve(strict=True)
    if not root.is_dir() or not (root / "manifest.json").is_file():
        parser.error("Require the prepared public dataset and its manifest")
    server = ThreadingHTTPServer((args.host, args.port), partial(ReadOnlyHandler, directory=str(root)))
    print(f"Dataset directory: {root}; listen: {args.host}:{args.port}; GET/HEAD only", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
