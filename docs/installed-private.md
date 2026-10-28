# Install identified 0.12.3 artifacts offline

[Quick start](quickstart.md) · [Compatibility](compatibility.md) · [Release policy](releasing.md)

The release target is `0.12.3` for both `equiframe` and
`equiframe-benchmark`; publication remains a separately verified step in the
[release process](releasing.md). This guide is the optional offline/local-artifact
route, not a claim that a private kit or public registry file is already available.
Historical A7 introduced the minimum-Polars expression-composition correction;
earlier alpha revisions remain in the changelog. Identify both current artifacts
by their separate wheel hashes.
The earlier 0.11.1 artifacts retain their historical identity. Match the commit and SHA-256 in the supplied receipt as well as
the version. Project-owned code is MIT; third-party notices retain their terms.
Registry ownership, upload and clean installation have their own gates; consult
the verified release status rather than installing an unrelated homonym.

## Normal pip resolution from a private wheelhouse

Obtain the identified wheelhouse for your Python/platform and verify its closed
SHA-256 inventory through a trusted channel. A Linux wheelhouse is not a Windows
wheelhouse. A provided command does not mean that platform was executed.
Create the environment outside the source checkout. Set `WHEELHOUSE` to its real
absolute path; never use `pip install -e`, `PYTHONPATH` or source-path fallbacks.

Linux (the commands illustrate Python 3.12; select any supported 3.10–3.13
minor only with its matching wheelhouse and identified validation):

```bash
mkdir equiframe-consumer
cd equiframe-consumer
python3.12 -m venv .venv
WHEELHOUSE=/absolute/path/reviewed-wheelhouse
.venv/bin/python -I -m pip install --no-index --find-links="$WHEELHOUSE" \
  'equiframe[engines,ml]==0.12.3' --report install-report.json
.venv/bin/python -I -m pip check
.venv/bin/python -I -c 'import equiframe, importlib.metadata, sys; print(sys.executable); print(equiframe.__file__); print(importlib.metadata.version("equiframe"))'
```

PowerShell (requires a wheelhouse resolved for Windows x64 and that interpreter):

```powershell
New-Item -ItemType Directory equiframe-consumer
Set-Location equiframe-consumer
py -3.12 -m venv .venv
$Wheelhouse = 'C:\authorized\wheelhouse'
.\.venv\Scripts\python.exe -I -m pip install --no-index --find-links="$Wheelhouse" 'equiframe[engines,ml]==0.12.3' --report install-report.json
.\.venv\Scripts\python.exe -I -m pip check
.\.venv\Scripts\python.exe -I -c 'import equiframe, importlib.metadata, sys; print(sys.executable); print(equiframe.__file__); print(importlib.metadata.version("equiframe"))'
```

The imported file must be under this environment's `site-packages`. The primary
trial deliberately lets pip resolve dependencies from wheel metadata. No
`--no-deps` is used to conceal missing requirements. Base and individual extras
must be tested in separate fresh environments; base must contain no Arrow,
engines, NumPy or scikit-learn. Benchmark base intentionally includes core Arrow;
its separate extras are `engines`, `ml` and `resources`.

For the benchmark, the wheelhouse must contain its exact matching core wheel:

```bash
.venv/bin/python -I -m pip install --no-index --find-links="$WHEELHOUSE" \
  'equiframe-benchmark[engines,ml,resources]==0.12.3' --report benchmark-install.json
.venv/bin/python -I -m pip check
```

## Independent reproducibility trial

Use a second fresh environment and the supplied platform-specific lock containing
exact versions and SHA-256 hashes for the candidate and every resolved runtime
dependency. Do not substitute a development lock or another Python's lock.

```bash
python3.12 -m venv .venv-hashed
.venv-hashed/bin/python -I -m pip install --no-index --find-links="$WHEELHOUSE" \
  --require-hashes -r runtime-with-candidate.lock --report hashed-install.json
.venv-hashed/bin/python -I -m pip check
```

Hash integrity does not authenticate a publisher or establish semantic correctness.
Minimum-direct and latest-permitted resolutions have separate real locks and
receipts. They do not prove every cross-product allowed by dependency ranges.
The stable `0.12.3` pin does not require prerelease resolution. Historical alpha
artifacts retain their separate exact pins and hashes. Never change global pip
configuration or describe an offline installation as a public PyPI installation.

## A useful comparison

Continue with the [complete quick-start comparison](quickstart.md#2-compare-two-complete-outputs):
`diff` → `write_comparison_report` → `assert_equivalent`. A finished execution,
integrity-check success or a caught expected rejection is not data acceptance.
Run the acceptance step with Python `-O` too; use `assert_equivalent`, not a Python
`assert` statement, for the gate that must survive optimization.

The independent consumer-lab application and permitted frozen real datasets are
separate artifacts. Its provenance, exact CLI, application return codes and
mutation outcomes belong to its own delivery receipt. The historical A–H
examples remain synthetic regression checks, not real-data adoption evidence.
