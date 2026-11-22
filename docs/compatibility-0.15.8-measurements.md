# EquiFrame 0.15.8 compatibility measurements

The tested artifact was `equiframe-0.15.8-py3-none-any.whl`, SHA-256
`5fefa27b8f6ba00d56d54881fab88ab2f254fd7261e0a74331d24642fc1806c1`.
The 453 package files listed in the wheel's `RECORD` matched the installed
hashes and sizes in each environment. [PyPI wheel details](https://pypi.org/project/equiframe/0.15.8/#files) · [Release notes](https://github.com/htroya/equiframe/releases/tag/v0.15.8)

| Platform, x86-64 | CPython | Pandas | Polars | DuckDB | PyArrow | NumPy | Rows per direction |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| Windows build 26200 | 3.10.22 | 2.2.3 | 1.44.2 | 1.5.6 | 23.0.1 | 1.26.4 | 30,000 |
| Windows build 26200 | 3.11.18 | 2.2.3 | 1.44.2 | 1.5.6 | 23.0.1 | 1.26.4 | 30,000 |
| Windows build 26200 | 3.12.16 | 2.2.3 | 1.44.2 | 1.5.6 | 23.0.1 | 1.26.4 | 30,000 |
| Windows build 26200 | 3.13.18 | 3.1.1 | 1.44.2 | 1.5.6 | 25.0.1 | 2.5.5 | 30,000 and 100,000 |
| Windows build 26200 | 3.13.18 | 3.1.0 | 1.44.2 | 1.5.6 | 25.0.1 | 2.5.3 | 30,000 |
| Debian 13 (WSL 2) | 3.10.22 | 2.2.3 | 1.30.0 | 1.5.6 | 23.0.1 | 2.2.6 | 30,000 |
| Debian 13 (WSL 2) | 3.11.18 | 2.2.3 | 1.30.0 | 1.5.6 | 23.0.1 | 2.2.6 | 30,000 |
| Debian 13 (WSL 2) | 3.12.16 | 2.2.3 | 1.30.0 | 1.5.6 | 23.0.1 | 2.2.6 | 30,000 |
| Debian 13 (WSL 2) | 3.13.18 | 2.2.3 | 1.30.0 | 1.5.6 | 23.0.1 | 2.2.6 | 30,000 |

All **60 conversion runs** completed and matched the independent fixture.
All **10 one-cent controls** returned a complete `different` result from
`equiframe.diff`. Each negative control used a separate 256-row slice.

## Elapsed seconds by direction

The six direction columns show the time inside `convert_dataset`. The last
two columns show the minimum and maximum across the six directions for source
loading and independent verification. Each row measures one run per direction.
The fixture is a Parquet table with a unique integer key, integer cents and a
nullable text field. Verification reads both native frames, materializes lazy
relations, normalizes Arrow storage types and sorts by key.

| Platform | CPython | Pandas | Rows | Pandas → Polars | Pandas → DuckDB | Polars → Pandas | Polars → DuckDB | DuckDB → Pandas | DuckDB → Polars | Load range | Verify range |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Windows build 26200 | 3.10.22 | 2.2.3 | 30,000 | 3.771 | 2.741 | 3.660 | 3.579 | 5.830 | 3.823 | 1.305–4.340 | 0.010–0.013 |
| Windows build 26200 | 3.11.18 | 2.2.3 | 30,000 | 8.353 | 2.737 | 3.726 | 4.795 | 3.692 | 4.703 | 1.527–3.834 | 0.010–0.014 |
| Windows build 26200 | 3.12.16 | 2.2.3 | 30,000 | 3.438 | 2.059 | 3.049 | 3.349 | 3.956 | 3.101 | 0.956–3.229 | 0.009–0.018 |
| Windows build 26200 | 3.13.18 | 3.1.1 | 30,000 | 9.329 | 7.840 | 10.769 | 6.537 | 9.882 | 4.761 | 3.509–9.299 | 0.018–0.073 |
| Windows build 26200 | 3.13.18 | 3.1.1 | 100,000 | 12.628 | 15.979 | 15.938 | 26.014 | 24.423 | 20.564 | 6.140–29.444 | 0.042–0.092 |
| Windows build 26200 | 3.13.18 | 3.1.0 | 30,000 | 5.572 | 5.244 | 6.737 | 4.131 | 5.870 | 9.454 | 2.270–8.109 | 0.017–0.029 |
| Debian 13 (WSL 2) | 3.10.22 | 2.2.3 | 30,000 | 3.112 | 5.268 | 5.584 | 5.884 | 6.238 | 3.609 | 1.468–6.216 | 0.017–0.052 |
| Debian 13 (WSL 2) | 3.11.18 | 2.2.3 | 30,000 | 2.448 | 2.917 | 2.333 | 2.435 | 3.254 | 2.363 | 0.899–7.526 | 0.011–0.060 |
| Debian 13 (WSL 2) | 3.12.16 | 2.2.3 | 30,000 | 2.255 | 2.062 | 2.817 | 2.664 | 2.957 | 4.352 | 0.745–4.424 | 0.008–0.025 |
| Debian 13 (WSL 2) | 3.13.18 | 2.2.3 | 30,000 | 2.614 | 2.416 | 3.246 | 3.017 | 2.439 | 2.959 | 0.811–3.366 | 0.012–0.046 |

The Windows environments used the same build 26200 host. Debian 13 ran in
WSL 2 with glibc 2.41 and temporary files in memory. The measurements describe
those environments and fixtures. The dependency ranges in
[compatibility](compatibility.md) describe admitted versions.
