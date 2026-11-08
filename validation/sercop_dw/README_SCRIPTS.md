# DW script guide / Guía de scripts

These commands replace the historical implicit-path recipes. This is a curated
optional prototype; original contributions and subsequent changes are distinguished
in [ATTRIBUTION.md](ATTRIBUTION.md).

## English

Provide explicit existing local directories. Initialization inserts no business
rows and never runs another initializer or seeds examples:

```text
python validation/sercop_dw/etl_init.py --db-path /absolute/local/awards.duckdb
python validation/sercop_dw/etl_load_ocds.py /absolute/local/input.json --db-path /absolute/local/awards.duckdb --snapshot-id synthetic-001 --snapshot-timestamp 2026-01-02T03:04:05+00:00
```

On Windows use explicit Windows paths and quote paths containing spaces.
Initialization is optional for a new database: a successful first load publishes
a complete database at exactly `--db-path`. A new file is published without
overwriting an existing destination. Existing databases must use this curated
schema. Validation or SQL errors roll back the complete batch. A publication or
cleanup error requires checking the destination before retrying. Do not copy this example snapshot ID for unrelated batches.

Load options `--source` and `--version` describe the input (defaults
`SERCOP-OCDS` and `1.0`). They are bound values, never network locations.
Standard output contains only a count and repeat status. Success exits 0;
input/database errors exit 1 to standard error, and argparse errors exit 2.
Diagnostics omit source records and native SQL exceptions.

Input must be UTF-8 JSON, at most 64 MiB and 100,000 awards. Duplicate object
keys, nonfinite numbers, duplicate award keys and dimension conflicts fail before
loading. Input/database files and ancestors cannot be symlinks, reparse points,
special files or hard-link aliases. The parent directory must already exist.
Run only against a database you own and manage; this tool is not a service.

## Español

Indique siempre el JSON local y `--db-path`; el directorio debe existir.
La inicialización no carga muestras. No se crea una base accidental en el
directorio de trabajo y no hay descarga ni acceso a servicios.

Una carga exitosa crea la base nueva completa o confirma una transacción en la
base existente. Los errores revierten la carga. Repetir el mismo snapshot es
idempotente; su contenido y metadatos son inmutables. Consulte los límites de
grano, fechas y dimensiones en [README.md](README.md).

La salida normal muestra sólo conteos/estado de repetición. Los códigos son
0 para éxito, 1 para errores de entrada/base y 2 para argumentos inválidos.
No se publican datos ni excepciones SQL originales en los diagnósticos.
