# Optional SERCOP award DW

This optional local prototype preserves Jhair Alarcon's DW contribution, including
the `modalidad` and `procedimiento` columns and their award JSON mapping. See
[attribution](ATTRIBUTION.md) and the [current script guide](README_SCRIPTS.md).
The original project code is covered by the repository's MIT license, reproduced
here. DuckDB is an external dependency and retains its own license.

This directory is outside both PyPI distributions. It does not change the core
API, certify a real DW delivery, or inherit the core release's validation receipts.
No procurement data, database, model, downloaded export or historical Git parents
are included.

Python 3.10+ and the project's supported DuckDB version are required. Use an
existing environment with DuckDB; the scripts do not install packages or contact
services. Run the independent checks explicitly:

```text
python -B validation/sercop_dw/test_dw.py
```

The checks generate temporary synthetic records, including a 30,000-award batch.
Their databases and input files are deleted after execution.

## Scope and limits

Input is a single award, an array of awards, or an object with an `awards` array.
Each award needs an ID, OCID (optionally inherited from the enclosing object),
explicit date, contracting entity ID, amount and currency. Amounts must fit
nonnegative DECIMAL(18,2) exactly; missing data and extra decimal places fail.
At most one supplier and one item are admitted; multiple entries fail explicitly.

Dates are the calendar date stated by the award. The prototype uses that date for
both legacy date columns; it does not infer the actual procedure start date.
Snapshot timestamps require an explicit UTC offset. No date, currency, amount,
supplier type or identifier is invented.

A snapshot ID is immutable. Repeating the same normalized records and metadata,
in any order, is a no-op. Changed content or metadata needs a new ID. Dimension
attributes use current values across snapshots (type 1); this is not historical
dimension tracking or a tamper-evident archive. Conflicting attributes within one
batch fail. Each load commits all rows or rolls back; no batch is partly accepted.

The schema is a curated version 1, with ASCII column identifiers and sequence
keys. Existing legacy or unrelated databases are rejected; no automatic migration
or destructive schema reset is provided. Reconciliation storage is reserved;
a reconciliation algorithm, full OCDS release/record processing, production
concurrency, real procurement-data acceptance and large-volume performance are
not validated here. The caller controls an ordinary local directory; path checks
are not a sandbox against a hostile process modifying it concurrently.

## Español

Prototipo local opcional que conserva el aporte de Jhair Alarcon: modalidad,
procedimiento y su carga desde JSON. Queda fuera de los paquetes PyPI y no acredita
una entrega productiva del DW. No incluye datos reales ni historial privado.

La inicialización crea sólo el esquema en una ruta explícita, sin semillas.
Cada carga es transaccional. Repetir un snapshot idéntico no duplica filas; cambiar
su contenido exige otro ID. Se rechazan fechas o campos obligatorios ausentes,
decimales no representables, claves duplicadas y proveedores/ítems múltiples.
Las dimensiones mantienen atributos actuales, sin historia de cambios.
Los límites, comandos y pruebas sintéticas están descritos arriba y en la guía.
