# Offline validation corpus

This optional input set belongs in validation/corpus, separate from the library
and its PyPI distributions. This later integration does not change the v0.12.2
tag or artifacts and does not certify consumer, scientific, or production results.

## Contents and integrity

The 2026-10-07 capture contains 219 effective records: 17 Treasury average
interest rates, 150 USGS earthquake events, and 52 Census state-level rows.
Downloaded source files contain 233 records because the complete Census CSV
has 66 rows. USGS reached its 150-event limit on January 3; this capture does
not represent the entire requested week.

manifest.json is the active integration inventory. FROZEN fixes listed bytes;
it does not certify agency measurements or consumer outcomes. The consumer
verifies every listed member and the three inputs it reads. The local
.gitattributes preserves their exact bytes, including CRLF in population.csv.

The original Git population.csv is 1,655 bytes with SHA-256
ce4f9ae29406aea4a9d20c08e2d07690b18a5319cf1fcdd45d98298ec64f5047.
It fails its original manifest, which expects 1,708 bytes and SHA-256
4eccee3763c96b014aeebb6c87cac36973dbd4f3f2cb4498722390ecc84b2425.
An independent derivation from the preserved Census source produces exactly
the expected 1,708 bytes: 53 CRLF terminators instead of LF. That reproduced
file is included here. All 16 originals, including the original 1,655-byte
blob, remain in the maintainer's verified private Git backup. No original was
overwritten or silently accepted by normalizing a failed check.

source-manifest.json, NOTAS_DATOS_ES.md, conditions.json and the acquisition
receipts retain their historical bytes and statements. The original manifest
references documentary files omitted from this curated inventory and is not
the active manifest. The earlier instruction to keep the capture outside
project Git is retained as history; the maintainer authorized this limited
curated integration on 2026-10-28. See integration-provenance.json.

Original HTML captures, the Census layout PDF and the empty failed HTTP
response remain privately backed up. They are not redistributed: captured
HTML includes remote scripts/analytics, and document rights for third-party
material were not fully established. No offline consumer operation needs
to open those documents or contact their sites.

## Sources and conditions

Credit U.S. Department of the Treasury, Bureau of the Fiscal Service, Fiscal
Data; U.S. Geological Survey, Earthquake Hazards Program; and U.S. Census
Bureau, Population Division. Treasury rates are percentages, not additive
money amounts. Census values are aggregate Vintage 2025 estimates for 2024
and 2025. The inspected fields contain rates, state aggregates and earthquake
observations; no respondent identifiers were found.

- [Fiscal Data Open Data Policy 901-1](https://fiscaldata.treasury.gov/data/about-us/901-1%20Open%20Data%20Policy.pdf):
  official indexed text describes open source data as free to use/download
  in publicly readable formats. Direct policy/API/about retrieval returned
  HTTP 403 during the 2026-10-28 review; full current API terms were not
  independently retrieved.
- [USGS reuse guidance](https://www.usgs.gov/faqs/are-usgs-reportspublications-copyrighted):
  USGS-produced data are in the U.S. public domain; credit is requested.
  Third-party materials and agency marks have separate conditions.
- [Census DS027, page 9](https://www2.census.gov/foia/ds_policies/ds027.pdf):
  employee works generally lack U.S. copyright protection, with qualifications
  for foreign jurisdictions and nonemployee works.
- [Census source and release](https://www.census.gov/data/datasets/time-series/demo/popest/2020s-state-total.html),
  [official layout](https://www2.census.gov/programs-surveys/popest/technical-documentation/file-layouts/2020-2025/NST-EST2025-ALLDATA.pdf),
  and [USGS API documentation](https://earthquake.usgs.gov/fdsnws/event/1/)
  are reference links, not runtime dependencies.

The repository's MIT license covers its original code. It does not relabel
government data or third-party documents as MIT. These notes record checked
sources and remaining limits, not legal advice or agency endorsement.

## Offline use

With core and the consumer already installed, run from the repository root:

    python -I -m equiframe_consumer_lab run --data validation/corpus --output /new/path/consumer-output --program migration --variant good --source pandas --target duckdb

The output directory must be new. This is one real-data case, not the complete
72-case matrix. Outcomes check declared contracts and arithmetic, not independent
truth of estimates/events. No account, token, live API or auxiliary repository
is required. Write all mutations and results outside this frozen directory.

To reproduce the population selection into a new file using the standard library:

    python validation/corpus/derive_population.py validation/corpus/raw/population.csv /new/path/population.csv

Verify the integration manifest before consuming its inputs.

## Español

Este conjunto opcional queda en validation/corpus, fuera de la biblioteca y
de las distribuciones PyPI. La integración posterior no modifica el tag ni los
artefactos de v0.12.2. Conserva 219 registros efectivos: 17 tasas de Treasury,
150 eventos de USGS y 52 filas estatales de Census; los originales descargados
suman 233. La captura sísmica alcanzó su límite el 3 de enero y no representa
toda la semana solicitada.

manifest.json verifica los archivos integrados. FROZEN fija sus bytes; no
certifica observaciones, resultados científicos ni ejecuciones del consumidor.
El CSV de Git tenía 1.655 bytes y no satisfacía el manifiesto original.
La derivación independiente produce exactamente los 1.708 bytes y el SHA-256
esperado, con 53 finales CRLF. El original permanece intacto en el respaldo
privado verificado; .gitattributes impide conversiones de los bytes integrados.

La procedencia, condiciones, recibos, nota y manifiesto de origen mantienen su
contenido histórico. El manifiesto de origen no es el inventario activo.
La autorización del mantenedor del 2026-10-28 permite esta incorporación
curada; se conserva la instrucción anterior como evidencia fechada.
HTML y PDF quedan respaldados en privado y enlazados, sin redistribuir scripts
remotos ni documentos cuyos derechos de terceros no se establecieron por completo.

Atribuir Treasury/Bureau of the Fiscal Service, USGS/Earthquake Hazards Program
y Census/Population Division. Son tasas, estimaciones agregadas y observaciones
sísmicas; no se encontraron identificadores de encuestados en sus campos.
No se aplica MIT a datos o documentos gubernamentales. Se mantienen las
salvedades oficiales sobre terceros/marcas, jurisdicciones distintas de EE.UU.
y los términos completos de FiscalData no recuperados por HTTP 403.

Los comandos anteriores consumen archivos locales y exigen destinos nuevos.
El caso único no equivale a la matriz de 72 casos. No necesita cuentas,
tokens, API en vivo ni repositorios auxiliares. Guardar mutaciones y resultados
fuera de este directorio y verificar antes el manifiesto.
