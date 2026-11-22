# EquiFrame 0.15.8 compatibility measurements

The wheel tested was `equiframe-0.15.8-py3-none-any.whl`, SHA-256
`5fefa27b8f6ba00d56d54881fab88ab2f254fd7261e0a74331d24642fc1806c1`.
The Windows measurement verified the installed hashes and sizes of the 453
package files listed in the wheel's `RECORD`. [PyPI wheel details](https://pypi.org/project/equiframe/0.15.8/#files) · [Release notes](https://github.com/htroya/equiframe/releases/tag/v0.15.8)

| Platform | CPython | Pandas | Polars | DuckDB | PyArrow | NumPy | Observed evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Windows 11 x86-64, build 26200 | 3.13.18 | 3.1.1 | 1.44.2 | 1.5.6 | 25.0.1 | 2.5.5 | All six native directions at 30,000 and 100,000 rows. Both one-cent controls detected. |
| Windows 11 x86-64, build 26200 | 3.13.18 | 3.1.0 | 1.44.2 | 1.5.6 | 25.0.1 | 2.5.3 | All six native directions at 30,000 rows. One-cent control detected. |
| Debian 13 x86-64, WSL 2 | 3.13.5 | 3.1.1 | 1.44.2 | 1.5.6 | 25.0.1 | 2.5.5 | Release records show dependency installation and `pip check`, generic acceptance controls with exits 0, 1 and 3, and bundled R review. Timed six-direction conversions are pending. |
| Windows x86-64 | 3.10.22 | — | — | — | — | — | Blocked by available disk space during installation of PyArrow. |
| Windows x86-64 | 3.11–3.12 | — | — | — | — | — | Pending measurement. |
| Linux x86-64 | 3.10–3.12 | — | — | — | — | — | Pending measurement. |

## Windows timings

Each cell gives elapsed seconds for loading the Parquet file into the source
engine, converting to the target engine, and checking both native frames
against the independent Arrow fixture. The fixture contains a unique integer
key, integer cents and a nullable text field. Comparison sorts by the key and
normalizes Arrow storage types to the fixture schema. Each value is one
observation on this host. The validation time includes reading any lazy
relation and sorting. Background processes were active.

| Direction | 30,000 rows, load / convert / verify (s) | 100,000 rows, load / convert / verify (s) |
| --- | ---: | ---: |
| Pandas → Polars | 3.51 / 9.33 / 0.04 | 6.14 / 12.63 / 0.05 |
| Pandas → DuckDB | 3.89 / 7.84 / 0.07 | 9.80 / 15.98 / 0.09 |
| Polars → Pandas | 7.09 / 10.77 / 0.04 | 12.77 / 15.94 / 0.04 |
| Polars → DuckDB | 8.13 / 6.54 / 0.06 | 13.41 / 26.01 / 0.04 |
| DuckDB → Pandas | 9.30 / 9.88 / 0.02 | 17.16 / 24.42 / 0.05 |
| DuckDB → Polars | 5.56 / 4.76 / 0.02 | 29.44 / 20.56 / 0.07 |

The Windows run with Pandas 3.1.0 and NumPy 2.5.3 used the same 30,000-row fixture.

| Direction | 30,000 rows, load / convert / verify (s) |
| --- | ---: |
| Pandas → Polars | 2.59 / 5.57 / 0.02 |
| Pandas → DuckDB | 2.27 / 5.24 / 0.03 |
| Polars → Pandas | 8.11 / 6.74 / 0.02 |
| Polars → DuckDB | 6.77 / 4.13 / 0.02 |
| DuckDB → Pandas | 4.63 / 5.87 / 0.02 |
| DuckDB → Polars | 6.40 / 9.45 / 0.03 |

Each Windows run used a separate 256-row slice per input size for its one-cent
control. All three controls returned a complete `different` result through
`equiframe.diff`.
The version ranges in the [compatibility register](compatibility.md) describe
admitted dependencies. The table above records the combinations exercised and
the scope of each check.
