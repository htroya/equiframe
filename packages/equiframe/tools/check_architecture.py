"""Report static import dependencies and enforce narrow architectural boundaries.

AST evidence includes local/function imports; eager edges omit functions, classes,
TYPE_CHECKING and conditionals. Neither graph proves all possible dynamic behavior.
Run from the source distribution; no optional engines or project imports are needed.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import TypedDict


class Edge(TypedDict):
    source: str
    target: str
    names: list[str]
    line: int
    eager: bool


class Report(TypedDict):
    modules: int
    imports: int
    eager_edges: int
    edges: list[Edge]
    eager_cycles: list[list[str]]
    runtime_cycles: list[list[str]]
    violations: list[str]


FORBIDDEN = ("equiframe_benchmark", "equiframe_data", "equiframe_sercop")
NEUTRAL = {
    "equiframe._document_io": {"equiframe.serialization"},
    "equiframe._physical": {
        "equiframe.errors",
        "equiframe.local",
        "equiframe.tables",
        "equiframe.execution_types",
        "equiframe.types",
    },
}


def cycles(nodes: set[str], edges: list[Edge], *, eager: bool) -> list[list[str]]:
    graph: dict[str, set[str]] = {node: set() for node in nodes}
    for edge in edges:
        if edge["target"] in graph and (not eager or edge["eager"]):
            graph[edge["source"]].add(edge["target"])
    visited: set[str] = set()
    order: list[str] = []

    def visit(node: str) -> None:
        if node in visited:
            return
        visited.add(node)
        for target in sorted(graph[node]):
            visit(target)
        order.append(node)

    for node in sorted(nodes):
        visit(node)
    reverse: dict[str, set[str]] = {node: set() for node in nodes}
    for source, targets in graph.items():
        for target in targets:
            reverse[target].add(source)
    visited.clear()
    result: list[list[str]] = []

    def collect(node: str, component: list[str]) -> None:
        if node in visited:
            return
        visited.add(node)
        component.append(node)
        for target in sorted(reverse[node]):
            collect(target, component)

    for node in reversed(order):
        if node in visited:
            continue
        component: list[str] = []
        collect(node, component)
        if len(component) > 1 or node in graph[node]:
            result.append(sorted(component))
    return sorted(result)


def inspect(root: Path) -> Report:
    nodes: set[str] = set()
    edges: list[Edge] = []
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).with_suffix("").parts
        source = ".".join(("equiframe", *parts))
        if source.endswith(".__init__"):
            source = source.removesuffix(".__init__")
        nodes.add(source)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            targets: list[tuple[str, list[str]]] = []
            if isinstance(node, ast.ImportFrom) and node.module and not node.level:
                targets = [(node.module, [alias.name for alias in node.names])]
            elif isinstance(node, ast.Import):
                targets = [(alias.name, []) for alias in node.names]
            for target, names in targets:
                if any(target == name or target.startswith(name + ".") for name in FORBIDDEN):
                    violations.append(f"{source}:{node.lineno}: core imports {target}")
                if not target.startswith("equiframe"):
                    continue
                edges.append(
                    Edge(
                        source=source,
                        target=target,
                        names=names,
                        line=node.lineno,
                        eager=node in tree.body,
                    )
                )
                if source in NEUTRAL and target not in NEUTRAL[source]:
                    violations.append(f"{source}:{node.lineno}: non-neutral dependency {target}")
                if (
                    source != "equiframe.profiles"
                    and target == "equiframe.profiles"
                    and set(names) & {"_write_document", "_read_document"}
                ):
                    violations.append(f"{source}:{node.lineno}: profile-owned generic I/O")
                if (
                    source != "equiframe.migration._physical"
                    and target == "equiframe.migration._physical"
                ):
                    violations.append(f"{source}:{node.lineno}: migration-owned captured-table I/O")
    eager_cycles = cycles(nodes, edges, eager=True)
    if eager_cycles:
        violations.append("eager import cycle: " + repr(eager_cycles))
    return Report(
        modules=len(nodes),
        imports=len(edges),
        eager_edges=sum(edge["eager"] for edge in edges),
        edges=edges,
        eager_cycles=eager_cycles,
        runtime_cycles=cycles(nodes, edges, eager=False),
        violations=violations,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on architectural violations")
    parser.add_argument("--output", type=Path, help="Write a new dependency JSON report")
    args = parser.parse_args()
    result = inspect(Path(__file__).resolve().parents[1] / "src" / "equiframe")
    if args.output is not None:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "edges"}, indent=2))
    return int(args.check and bool(result["violations"]))


if __name__ == "__main__":
    raise SystemExit(main())
