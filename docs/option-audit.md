# Audit options without inventing coverage

[API](api.md) · [Compatibility](compatibility.md) · [Private installation](installed-private.md)

The developer tool `tools/option_inventory.py`, shipped in the source
archive, inspects a **normally installed** candidate. Run it from an external
folder with the target venv's Python and `-I`. Give the exact wheel and source
commit. It refuses imports outside that environment's site-packages and checks
every shipped package file against the wheel before recording an inventory.

```bash
python -I option_inventory.py --wheel equiframe-0.12.4-py3-none-any.whl \
  --commit EXACT_40_CHARACTER_COMMIT --output inventory.json --matrix obligations.json
```

To include the separate benchmark, install it normally and add `--benchmark
--benchmark-wheel equiframe_benchmark-0.12.4-py3-none-any.whl`.
The inspection harness uses only dependencies already declared by the inspected
packages. It never executes default factories merely to discover their names.

The output extends `get_stability_register()` and `get_adapter_capabilities()`;
it does not replace either with a competing support catalog. It records exports,
alias identity, function parameters/defaults, Pydantic fields/constraints,
Literal/Enum alternatives, boolean defaults and both branches, declared methods,
CLI paths/options and extras. Output/declarative types do not count as executable
features. Dependencies and operating system/Python are recorded explicitly.

Every obligation begins as NOT_RUN. Independent semantic evidence is necessary
to promote it; a discovered signature, matching schema, import, code mention or
line-coverage hit is not a correctness test. Defaults and explicit boolean values
are separate obligations. Numeric/text spaces require declared equivalence and
boundary classes; there is no exhaustive test of an infinite value space.

Execution states:

- PASS: the executed case satisfied an independent expected result
- EXPECTED_REJECTION: the rejection behaved correctly; application data was not accepted
- FAIL: observed behavior contradicted the expected result
- BLOCKED: a named external precondition prevented execution
- NOT_RUN: no qualifying execution receipt is linked

Count unique test IDs separately from option rows and repeated compatibility
runs. Record high-risk finite cross-products and constrained pairwise choices;
list any uncovered interactions. Do not report 100% behavioral option coverage
while obligations remain unlinked or their independent expectation is missing.
