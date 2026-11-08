# DW contribution and curation / Aporte y adaptación

## English

Jhair Alarcon's original contribution added `modalidad` and
`procedimiento` to `fact_adjudicacion`, read them from award JSON,
bound both values in insertion/update statements, returned them from the loader,
and documented the change. Those fields and their mapping are retained here.
The exact source identity and author attribution are in [ATTRIBUTION.md](ATTRIBUTION.md).

This later adaptation supplies explicit database paths, schema-only initialization,
exact decimal validation, transactional loads, immutable snapshot IDs, closed
identifier choices, safe file checks, independent synthetic tests and bilingual
instructions. These subsequent edits are not attributed to the original author.
The loader now inserts a new complete snapshot or accepts an identical repeat;
it does not silently update an already recorded snapshot.

## Español

El aporte original de Jhair Alarcon añadió modalidad y procedimiento al esquema,
los extrajo del JSON y los incorporó a la carga y documentación. Esta copia conserva
esos campos. La adaptación posterior corrige rutas e inicialización, añade
transacciones y pruebas sintéticas y distingue su autoría del aporte original.
No se trasladaron datos, resultados, correos privados ni padres del historial Git.
