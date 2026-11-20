# Development instructions

- The reusable core lives in `src/`, `tests/`, `docs/` and `pyproject.toml` at the
  root. The paired scientific package is `packages/equiframe-benchmark`.
  `archive/research-a14` preserves history; it is not an active package.
- Read `docs/api.md`, `docs/compatibility.md` and `docs/semantics.md` before changing
  public behavior. Preserve native execution and lazy optional imports.
- Preserve decimals, missing values, keys, multiplicity, dates and unavailable
  outcomes. Rules R, Isolation Forest M, MAD B, hybrid H and independent expected
  evidence O remain separate. Software publication is not scientific acceptance.
- Do not modify the DW or portal in a core task. Jhair owns
  `packages/equiframe-sercop` and `validation/sercop_dw`; Jose owns
  `packages/equiframe-data`, `packages/equiframe-portal`, `services` and `infra`.
- Never execute untrusted SQL, callbacks, plugins or serialized models. Never
  use concurrent independent writers on a shared DuckDB database.
- Test independent expectations, negative cases, exits, permissions and unavailable
  states. Never count unexecuted or failed work as passed. Run Ruff, strict mypy,
  assets and appropriate tests; release checks bind source and installed artifacts
  to the actual commit, tag and hashes.
- Git and publication are manual. Do not add or invoke GitHub Actions. TestPyPI
  precedes PyPI; promote identical bytes after downloaded-consumer checks pass.
  Use ephemeral credentials and revoke them afterward.
- Preserve historical fixtures and archives byte-for-byte. Keep raw data,
  databases, private models, credentials, private configurations and private
  Git history out of distributions. The explicitly authorized declarative SERCOP
  model may ship with its contract, fingerprint, provenance and attribution.
- Reuse the Windows QA lab under `equiframe-013-lab`, at most 3 GiB, and clean
  consumed scratch files. Preserve VM services, datasets and unrelated processes.
- Use only Opera Neon MCP, the dedicated NeonCodexQA profile, loopback port 9222
  and initial 75 percent zoom. Do not inspect personal tabs.
