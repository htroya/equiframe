# Eight complete synthetic journeys

Read the [packaged journey guide](../../docs/journeys.md) for installation,
independent expected values, acceptance criteria, artifacts, privacy and limits.
Everything is inline synthetic data; no credentials or network data sources.

After installing an identified private wheel and the exact dependencies in
`requirements.lock`, copy this entire directory outside the checkout:

```bash
python journeys/a_pandas_refactor.py --case good --output evidence-a
python journeys/verify_journeys.py --output all-journey-evidence
```

The first command is an equivalence gate. The second is an **acceptance harness**:
it expects both good cases and intentional failures, and returns 0 only when all
31 scenario exits match their declared meaning. It does not approve every input.

When these examples are installed inside the candidate wheel, the isolated route
requires no copied scripts:

```bash
python -I -m equiframe.examples.journeys.a_pandas_refactor --case good --output evidence-a
python -I -m equiframe.examples.journeys.verify_journeys --output all-journey-evidence
```

Use a fresh output directory every time. `private/` or `raw/` contains raw
captures. Only the `reports/` or `public_reports/` subtree is data-minimized.
A portable bundle, `summary.json`, and `environment.json` are not redacted sharing
packages. Local Parquet output is local file publication, never package/service
publication. Keep raw captures and local evidence out of public commits.
