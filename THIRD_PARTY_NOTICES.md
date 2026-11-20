# Third-party notices

EquiFrame's original code and accompanying project documentation, examples and
tools are licensed under MIT; see LICENSE. Third-party material retains its
original terms.

## CycloneDX schemas

The source distribution includes these unmodified schemas under tools/cyclonedx;
the wheel includes the same files under equiframe/_vendor/cyclonedx:

- bom-1.6.schema.json
- spdx.schema.json
- jsf-0.82.schema.json

They come from the official CycloneDX specification, tag 1.6:
https://github.com/CycloneDX/specification/tree/1.6/schema

Their Apache License 2.0 is preserved in tools/cyclonedx/LICENSE. Provenance and
the original SHA-256 inventory remain in tools/cyclonedx/PROVENANCE.md. The
package's license files also carry this upstream license for redistribution.
MIT does not replace the schemas' Apache-2.0 terms.

## External dependencies and data

Python dependencies and the external R runtime are separate installations;
their licenses remain their own. EquiFrame's MIT grant does not relicense them.
Downloaded datasets and the thesis manuscript are not part of this grant.

### Bundled SERCOP statistical model

The declarative Isolation Forest resource comes from **Contrataciones Abiertas
Ecuador – OCDS**, published by the Servicio Nacional de Contratación Pública
(SERCOP). EquiFrame selected eligible awards, converted monetary amounts to integer
cents, generated batch profiles, fitted a forest and calibrated a threshold. The
resource carries these derived parameters and the contract. Its attribution is
under Creative Commons Attribution 3.0 Ecuador (`LicenseRef-CC-BY-3.0-EC`).
[Data publisher](https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos) ·
[Archived releases](https://data.open-contracting.org/es/publication/110) ·
[License](https://creativecommons.org/licenses/by/3.0/ec/legalcode)

### Optional legacy XLS reader

The optional `files` extra uses the separately installed `xlrd` package for
legacy XLS files. No xlrd source or binary is vendored in EquiFrame. The license
included with xlrd 2.0.2 contains both a later three-clause notice and an earlier
notice requiring attribution in advertising materials mentioning that software
and retention of the acknowledgement in redistributions:

> This product includes software developed by David Giffin <david@giffin.org>.

Preserve xlrd's complete upstream license and notices when redistributing it;
this acknowledgement does not replace either of its license texts. See
https://github.com/python-excel/xlrd/blob/2.0.2/LICENSE.
