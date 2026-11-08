# STEP1: ficha operativa del candidato

Fecha: 2026-10-04. **Estado: saneamiento y verificación técnica local completados**.
Este registro delimita el candidato de ingeniería; no declara una publicación,
aceptación externa ni evaluación científica. Complementa el proceso vigente de
[release](RELEASE_CANDIDATE.md) y no sustituye sus controles.

## Identidad y alcance

| Campo | Valor / evidencia |
|---|---|
| Repositorio y destino de integración | [htroya/equiframe](https://github.com/htroya/equiframe), `main` |
| Base de esta intervención | [`980c2db862d5a39cf3e8d1ee7d2a8ebfce71c637`](https://github.com/htroya/equiframe/commit/980c2db862d5a39cf3e8d1ee7d2a8ebfce71c637) |
| Base inspeccionada anteriormente | [`635e35b217e4271b82751024ecc0140609472474`](https://github.com/htroya/equiframe/commit/635e35b217e4271b82751024ecc0140609472474); la revisión documental posterior no aporta ejecución nueva |
| Commit final y estado remoto | El SHA completo se registra en los manifiestos externos después del commit para evitar autorreferencia; la comprobación del remoto se registra por separado. Esta ficha identifica los bytes comprobados mediante las huellas y recibos siguientes |
| Distribuciones declaradas | `equiframe==0.11.1` y `equiframe-benchmark==0.11.1`, según sus [metadatos núcleo](../packages/equiframe/pyproject.toml) y [benchmark](../packages/equiframe-benchmark/pyproject.toml) |
| Python y madurez declarados | `>=3.12,<3.13`, Alpha; no implica haber probado cada plataforma o rango de dependencia |
| Formatos | Formatos públicos versionados por separado; esta intervención no propone una versión nueva de `ComparisonResult`/contratos 1.0. [API](API_CONTRACTS.md) |
| Fuente local | Checkout Git reconstruido de objetos del repositorio, con HEAD fijado y verificación de objetos; historia local limitada a la base, no clon histórico completo |
| Frontera del trabajo | Gate CLI, disposición segura del auxiliar experimental del núcleo, controles del candidato y documentación operativa |
| Fuera del trabajo | Nueva fachada DataFrame, métodos de resumen/aserción/HTML de comparación, ampliación semántica, publicación, infraestructura o DW de otros componentes |

Una fuente identificada no equivale a una fuente ejecutada. La evidencia de
[la revisión del 3 de octubre](COMPREHENSIVE_REVIEW_20261003.md) pertenece al
commit/artefactos que identifica; no valida automáticamente este candidato.
El SHA del commit final se conserva en el manifiesto externo para evitar el
ciclo imposible de incluir el propio SHA de un commit en sus archivos.

## Documentos de decisión de esta intervención

- [Capacidades declaradas frente a verificadas](STEP1_CAPABILITIES.md): etapa,
  adaptador, tipo, evidencia, límite y rol responsable
- [Contrato de decisión semántica](STEP1_SEMANTIC_RFC.md): tres estados,
  `invalid_expected`, interrupciones y composición conservadora
- [Backlog de aceptación](STEP1_BACKLOG.md): defectos, límites y decisiones
  separados, con reproductores y responsables por rol
- [Tres pilotos sintéticos acotados](STEP1_PILOTS.md): subconjunto de tipos,
  resultados independientes y aceptación todavía por observar

La [matriz semántica existente](SEMANTIC_SUPPORT.json) sigue siendo el inventario
de casos por operación y dirección. Estas fichas no crean un segundo comparador,
un motor de migración ni un catálogo alternativo de conformidad.

## Recibos exigidos para cerrar la verificación

Guardar logs, entornos, datos de corrida y artefactos fuera de Git. Registrar
referencia verificable y SHA-256 del recibo; no incorporar credenciales ni
carpetas privadas de ejecución a los documentos públicos del repositorio.

| Evidencia | Identidad / resultado de este candidato |
|---|---|
| Fuente núcleo y dependencias locales | `964410002b9e76de2dd2cbf69846eb2fa6205336068e20097ee6eeaaf51c9db4` (180 archivos); misma huella antes/después en las nueve etapas |
| Fuente benchmark y dependencia núcleo | `d0333b57e31724314f565138f9fd9c5d4460500c2b88f4d9a1ad44b2356ecd5e` (280 archivos, incluido núcleo); misma huella antes/después en las nueve etapas |
| Entorno efectivo | Linux 6.18.44 x86_64 / glibc 2.41, Python 3.12.14, uv 0.12.19; extras de desarrollo/runtime resueltos por locks sin cambios. Versiones detalladas y resultados se vinculan al recibo final |
| Nueve etapas núcleo | **9/9 aprobadas**, exit 0: `locked_sync`, `ruff_check`, `ruff_format`, `mypy`, `assets`, `pytest`, `build`, `twine`, `distribution` |
| Nueve etapas benchmark | **9/9 aprobadas**, exit 0, mismas etapas con `--package`; núcleo incluido en fuente y artefacto de dependencia |
| Regresiones de saneamiento | Incluidas en la suite ejecutada: [decisiones CLI/parciales](../packages/equiframe/tests/test_comparison_decisions.py) y [cuarentena](../packages/equiframe/tests/test_benchmark_quarantine.py) |
| Wheel y sdist núcleo | Construidos, Twine estricto e instalación aprobados; bytes identificados abajo y vinculados en recibo |
| Wheel y sdist benchmark | Mismos controles aprobados; recibo identifica el wheel exacto del núcleo consumido |
| Consumidores instalados | Núcleo base + seis extras por separado, import ligero, consumidor tipado, API/CLI, ejemplos y suites fuera del checkout; ambos wheels reconstruidos byte a byte desde sdist |
| GitHub Actions del commit final | **No acreditado**: URL del run y SHA exacto si se ejecuta; configuración manual no es un resultado |
| Consumidor humano independiente | **Pendiente**: persona, plataforma, artefacto, recorrido, ayuda y resultado; no sustituirlo por ejecución del autor |

Los comandos y reconocimiento estricto de etapas están en
[RELEASE_CANDIDATE.md](RELEASE_CANDIDATE.md). Una selección pytest sirve para
reproducir un hallazgo; no acredita la etapa de suite completa. La recopilación
de tests tampoco acredita ejecución. Los recibos identifican bytes y resultados
declarados; `receipts_authenticated=false` sigue siendo una limitación expresa.

### Recibos finales y alcance ejecutado

Ambos recibos y sus logs se conservan fuera de Git. Se comprobó su contenido,
nueve exit codes 0 y huellas de fuente constantes antes/después. Identidades:

| Recibo | SHA-256 |
|---|---|
| `core-checks.json` | `9dc2499dffd512b2fc1280885d4b8331214847febf934f232b5ec389809ac90c` |
| `benchmark-checks.json` | `144b6d602f967d8945884e765e7f724a07d347fd50a8472d78260738a4a0551a` |

| Suite | Fuente | Instalación externa desde artefacto |
|---|---|---|
| Núcleo | 1086 passed, 58.63 s | 1086 passed, 64.45 s |
| Benchmark | 456 passed, 57.63 s | 456 passed, 58.43 s |

No hubo skips ni xfails en estas suites. Repetir la suite desde el wheel valida
el consumo del artefacto; no duplica el número de casos independientes. Los
tiempos son duración de tests en este entorno, no benchmarks del producto.

Los consumidores del núcleo verificaron las seis direcciones nativas y ejemplos
de Verify/ETL/bundles; los del benchmark comprobaron piloto nativo, integración
y evaluación. Son ejemplos sintéticos con sus estados y límites esperados:
pueden conservar una comparación fallida o componente parcial de forma correcta.
En particular, integridad aprobada no convierte una integración parcial en
equivalencia ni confirma O científico, DW real o aceptación humana.

### Artefactos construidos e identificados

Hashes y tamaños leídos de los bytes locales el 2026-10-04; no equivalen por sí
solos a procedencia firmada, instalación aprobada o publicación. Versión privada
0.11.1 conservada; SHA de fuente y artefactos distinguen este candidato.

| Archivo | Bytes | SHA-256 |
|---|---:|---|
| `equiframe-0.11.1-py3-none-any.whl` | 188112 | `9d322377552958526c3b3d80a2c12a494b3eeb2a816dec6799bc7606fc6f85cd` |
| `equiframe-0.11.1.tar.gz` | 484124 | `9a655630e7dfc0937cfbd5dee78072291f98a6f9cf3d4b5ece858446cf0cd736` |
| `equiframe_benchmark-0.11.1-py3-none-any.whl` | 103882 | `a774443387edba9f20ea0078ef83d8e6e17f17cb228171b8d51c856ebbabe9c1` |
| `equiframe_benchmark-0.11.1.tar.gz` | 309324 | `ca6919b1aad00b7870bced26bb5f3d0ffd28665e7854903756ff8bba4ced610d` |

## Criterios de cierre y bloqueos externos

1. Los hallazgos P0 del [backlog](STEP1_BACKLOG.md) tienen disposición segura y
   regresiones ejecutadas sobre la fuente final
2. Los controles de los dos paquetes y consumidores corresponden a los bytes
   exactos identificados; cualquier fallo, skip o etapa no ejecutada queda visible
3. Las capacidades anunciadas conservan fuente, caso, etapa y límite; una fila
   pendiente de recibo no se presenta como conformidad ejecutada
4. Las decisiones semánticas y los pilotos tienen roles responsables; aún deben
   asignarse personas antes de comprometer fechas o soporte
5. Licencia y nombre de distribución siguen **pendientes de decisión de los
   autores**. No se cambia `LICENSE`, titularidad, cuenta o visibilidad por
   completar pruebas. No se publica en PyPI/TestPyPI

Los puntos 1–3 permiten informar un candidato técnico saneado cuando exista la
evidencia. No cierran por sí solos los puntos humanos de los pilotos ni los
[gates de distribución](RELEASE_CANDIDATE.md#decisiones-externas-pendientes).
