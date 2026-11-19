# EquiFrame 0.14.0 release errata

EquiFrame 0.14.0 and its exact benchmark companion were published as Beta
on 19 November 2026. The phrase “Release target: 0.14.0” in the PyPI
description and the publication targets in the bundled compatibility page
predate publication. The technical checks from 0.13.5 in that page identify
0.13.5. Use the 0.14.0 release notes for the checks and hashes of 0.14.0.
[Core on PyPI](https://pypi.org/project/equiframe/0.14.0/) ·
[Benchmark on PyPI](https://pypi.org/project/equiframe-benchmark/0.14.0/) ·
[Release notes and hashes](https://github.com/htroya/equiframe/releases/tag/v0.14.0)

The published core wheel SHA-256 is
`c1956d8cfeca3b558fccda9955d1cdba235934041df67ed753cca698ed461219`.
Profile feature version 1.1 admits grouped execution metrics. The grouped
mean and variance in experimental feature version 1.2 require a later
development build. The experiments run with `0.15.0.dev1` identify that wheel
and are reported separately from measurements on 0.14.0.
[0.14.0 grouped profiles guide](https://github.com/htroya/equiframe/blob/v0.14.0/docs/grouped-profiles.md)

The [exact-wheel public-data evaluation](equiframe-0.14.0-evaluation.md) reports
detection, false alarms, misses and cost for profile feature version 1.1.

The 200-tree synthetic Isolation Forest probe timed a single profile at a
median of 2.4 seconds in the review scenario. It included validation,
fingerprints, preprocessing and scoring on that host. The practical cost
depends on the model, input and environment. The 0.14.3 candidate reduces
repeated work within each call.
