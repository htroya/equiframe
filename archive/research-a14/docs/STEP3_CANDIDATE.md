# STEP3: reporte común y políticas de evidencia

Fecha: 2026-10-05. Candidato privado 0.11.1. Base:
[`36ac0380b9d2f90b1b7ce73fafd0e76f21beeaef`](https://github.com/htroya/equiframe/commit/36ac0380b9d2f90b1b7ce73fafd0e76f21beeaef).

## Entrega

- Vista versionada común para JSON, texto, HTML independiente y notebook
- Inspección acotada de evidencia con raíz autorizada y divulgación explícita
- Conteos exactos, cotas inferiores y desconocidos; alineación y multiplicidad
- Manifiestos de evidencia/publicación y reproducción materializada admitida
- Ejemplo sintético y consumidores de distribución base/extras sin notebook

[Uso y límites](REPORTS.md) · [Decisiones A134–A138](DECISIONS.md#reporte-común-step3--2026-10-05)

La retención del comparador y `ComparisonResult` permanecen compatibles.
No incluye aserciones del paso siguiente, ampliación metodológica, publicación
PyPI, licencia, despliegue o cambios de la infraestructura de otros componentes.

## Verificación

Verificación técnica local completada en Linux x86_64/Python 3.12.14.
Se conservaron locks, rangos y versiones del candidato anterior. La revisión
independiente no encontró bloqueos sobre el árbol final; no sustituye revisión
humana del equipo ni aceptación científica.

| Etapa | Núcleo | Benchmark |
|---|---:|---:|
| Sync bloqueado con todos los extras | Aprobado | Aprobado |
| Ruff check / format | Aprobados | Aprobados |
| mypy estricto | Aprobado | Aprobado |
| Assets en modo check | Aprobado | Aprobado |
| Suite completa sobre fuente | 1603 passed | 456 passed |
| Build sin aislamiento | Aprobado | Aprobado |
| Twine estricto wheel/sdist | Aprobado | Aprobado |
| Consumidores externos y distribución | Aprobado | Aprobado |
| Suite instalada desde distribución | 1603 passed | 456 passed |

Son nueve etapas por paquete, cero fallos y cero omisiones. Las 223
pruebas nuevas del núcleo no incluyen dos veces su repetición instalada.
Los consumidores comprueban imports ligeros, API/CLI, typing, extras separados y
los ejemplos. El nuevo reporte se produce fuera del checkout y se vuelve a
leer/renderizar en la base instalada sin Arrow, motores, IPython ni Jupyter.
Los dos wheels se reconstruyeron idénticos byte a byte desde sus sdists.

### Bytes de fuente comprobados

Algoritmo `sha256-git-worktree-v1`:

- Núcleo, 202 archivos: `1ab0a05a6f930996d2edc42901c0b53dda2caf41a129feadcfc33793863a7936`
- Cierre benchmark + núcleo, 302 archivos: `783f268ef6f332154578719bb69193019f7aa62be8200312bc19758dded67f47`

### Artefactos privados comprobados

| Archivo | Bytes | SHA-256 |
|---|---:|---|
| equiframe-0.11.1-py3-none-any.whl | 224493 | `50aa1aa64a89463176242ec166d9c716857545d62588d047463f2d1e0718c919` |
| equiframe-0.11.1.tar.gz | 562783 | `4669457b539e0fd3e6dad49d58f0758f150aab3120a1702b8502acc7aba7237e` |
| equiframe_benchmark-0.11.1-py3-none-any.whl | 103882 | `a774443387edba9f20ea0078ef83d8e6e17f17cb228171b8d51c856ebbabe9c1` |
| equiframe_benchmark-0.11.1.tar.gz | 309324 | `ca6919b1aad00b7870bced26bb5f3d0ffd28665e7854903756ff8bba4ced610d` |

Los recibos externos conservan comandos, fechas, cwd, exit codes y huellas
antes/después; los manifiestos finales los vinculan al commit limpio y a los
artefactos. El SHA final y la verificación remota se registran después del
commit, evitando una referencia circular. No son una firma ni CI remota.

## Límites confirmados

- Las pruebas locales corresponden a Linux x86_64/Python 3.12.14 y versiones
  resueltas de los locks existentes; no acreditan todos sus rangos/plataformas
- Los workflows de GitHub permanecen manuales: configuración no equivale a CI
  ejecutada. No se atribuyen resultados remotos sin comprobar su SHA
- La validación estructural/seguridad HTML se ejecuta en tests. Chromium local
  no pudo iniciar por una restricción de sockets IPC, incluso mediante la ruta
  de aprobación soportada; no hay captura ni aprobación visual de navegador
- El modo reproducción conserva una comparación de salidas materializadas,
  no las transformaciones originales. Fuentes de ejecución se rechazan
- Sin cifrado/ACL remota, eliminación de originales o garantía de anonimización
- Hashes y recibos identifican bytes, no autentican ejecución ni conceden licencia
