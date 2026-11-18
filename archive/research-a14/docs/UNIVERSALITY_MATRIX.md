# Matriz UV01–UV12

**Corte histórico A9.** Los estados, plataformas y referencias a `main` de esta
matriz corresponden al corte indicado, no al código A11 integrado posteriormente.
El [avance técnico A11 del 2026-10-10](UNIVERSALITY_TECHNICAL_PROGRESS_20261010.md)
evalúa 41/60 comprobaciones (68,3 %) con una rúbrica propia distinta; no cambia
este cierre histórico de 3/12 ni acredita las obligaciones pendientes del plan.
La [entrega A11](PRODUCT_UNIVERSALITY_FIVE_STEPS.md) conserva los resultados
manuales y límites de los cinco pasos integrados.

Universo fijado antes de las pruebas en [el plan](UNIVERSALITY_PLAN.md).
Corte 2026-10-09 UTC de A9; evaluación intermedia, no cierre. Las referencias de
recibos identifican evidencia privada conservada fuera de Git.

| Criterio | Subobligaciones acreditadas | Brecha restante del criterio íntegro | Estado |
|---|---|---|---|
| UV01 — Núcleo independiente | Arquitectura: 75 módulos, 530 imports, cero violaciones/ciclos eager; contratos genéricos en tres dominios; consumidor separado instalado | Ninguna en este criterio técnico; no atribuye entrega del DW/servicio | CUMPLIDO |
| UV02 — Python real | CPython 3.10.22/3.11.17/3.12.14/3.13.5 x64; núcleo 4.499 tests y benchmark 596 instalados por versión; tipos estrictos y propagación de intérprete | Distribución íntegra wheel/sdist y primera instalación aislada no cerradas en las cuatro versiones; runtime no sustituye esas etapas | PARCIAL |
| UV03 — Plataformas | Cuatro celdas Linux x64 con pruebas funcionales reales; arnés/workflows manuales fijan veinte celdas | Dieciséis celdas nativas sin recibo A9, incluido OCI ARM64 pendiente; ninguna celda tiene aún todas las subobligaciones del plan | BLOQUEADO |
| UV04 — Dependencias/extras | Typing-extensions directo; locks coherentes; instalación local normal y pip check donde constan; perfiles definidos por marcador | Base/extras individuales y extremos mínimo/reciente de todas las celdas no ejecutados; faltan metadatos/artefactos públicos en caché | PARCIAL |
| UV05 — Motores/direcciones | Tres motores nativos, seis direcciones, esperado independiente; 72 casos externos y 144 ejecuciones nativas por Python | No acredita el producto completo de operadores/tipos/políticas y perfiles/plataformas; rechazo no cuenta como transformación implementada | PARCIAL |
| UV06 — Semántica | Regresiones de ausencia, texto, Decimal, cardinalidad, orden y tiempo; 48 controles adicionales de tipo físico inválido sin ejecución nativa | Condiciones nativas de Decimal/tiempo y cobertura transversal no cerrada; ninguna función requerida se da por implementada por su rechazo | PARCIAL |
| UV07 — Extensión externa | Consumidor 0.1.11 en repositorio propio: DataSource/SnapshotClient, snapshots, productor SQLite existente, PlanCompiler/EngineAdapter Polars externos reales; registros por instancia y esperado independiente | Servicio/DW de José/Jhair y adopción humana siguen separados, sin afirmarlos como entregados | CUMPLIDO |
| UV08 — Tres dominios | Finanzas/comercio/telemetría, contratos y esperados propios, variantes equivalentes/diferentes/inválidas; consumidor actualizado e instalado fuera del checkout en cuatro Python | Evidencia sintética/técnica, no aceptación o adopción humana | CUMPLIDO |
| UV09 — Operación | Integridad, relocalización y fallos con recuperación bajo -O; transporte adversarial simulado; medición acotada identificada | Rutas/fs nativos adicionales, medición íntegra y A7→A9→A7 con recuperación fresca pendientes; faltan wheels públicos originales locales del replay | PARCIAL |
| UV10 — API/CLI/docs | A–H preservados; ayuda/códigos negativos comprobados; guía española DOC2 con cuatro Python y antecedentes separados | Primera instalación limpia completa y recorridos nativos/plataformas pendientes; documentación corregida no prueba el recorrido | PARCIAL |
| UV11 — Dependencias públicas | Inventario ligado a bytes finales; preparación offline/allowlist; URL/cuerpo/cabeceras/redirects probados | 19/140 consultas completas, 121 desconocidas por errores; bloqueo HTTP 403. Sin dictamen global limpio ni licencia aprobada | BLOQUEADO |
| UV12 — Integración reproducible | Seis artefactos congelados, dos manifests documentales, bundles y rama remota cotejados por árbol; consumidor probado | Recibos y controles obligatorios anteriores pendientes; main permanece en A8, sin integrar todavía la ampliación final validada | BLOQUEADO |

**CUMPLIDOS: 3/12; índice de cierre de este alcance: 25 %.** Los otros estados
suman cero. No mide todas las capacidades del producto ni un descenso desde el
55 % histórico no reproducible. Madurez 1/16 y usabilidad 11/12 son antecedentes
con sus propias puertas; el 65 % citado históricamente pertenece a otro eje.

## Cobertura nativa, separada del índice

| Plataforma nativa | 3.10 | 3.11 | 3.12 | 3.13 |
|---|---|---|---|---|
| Linux x64 | PARCIAL | PARCIAL | PARCIAL | PARCIAL |
| Linux ARM64 | NO_EJECUTADO | NO_EJECUTADO | NO_EJECUTADO | NO_EJECUTADO |
| Windows x64 | NO_EJECUTADO | NO_EJECUTADO | NO_EJECUTADO | NO_EJECUTADO |
| macOS Intel | NO_EJECUTADO | NO_EJECUTADO | NO_EJECUTADO | NO_EJECUTADO |
| macOS Apple Silicon | NO_EJECUTADO | NO_EJECUTADO | NO_EJECUTADO | NO_EJECUTADO |

4/20 celdas tienen ejecución funcional A9; **0/20 están cerradas íntegramente**.
Los preparativos de la VM y las 34 unitarias históricas ARM64 de dos Python no
son ejecución de estos artefactos. Las 53 unitarias actuales en cuatro Python
x64 son controles del arnés, no cuatro recibos de producto ARM64.

## Evidencia por identidad

- Fuente de artefactos: `95d74a0e304790b347750451de75e9101b1f1b33`;
  consumidor externo: `86b76301d0f9a298c8f3a4c1add6a8c7f1a25e33`
- Núcleo: `installed310-pytest.xml`, `core-311-candidate-001.json`,
  `core-312-candidate-004.json`, `core-313-candidate-001.json` y bindings de wheel;
  los JSON conservan también etapas fallidas y no son pases íntegros
- Benchmark: `benchmark-312-candidate-004.json` completo;
  `benchmark310-installed-suite.xml`, `cached-311-benchmark.xml`,
  `cached-313-benchmark.xml` con cierre común de pruebas, no su lock de desarrollo
  propio en esas tres versiones
- Consumidor: `consumer312-full72/summary.json`,
  `cached-310-consumer72/summary.json`, `cached-311-consumer72/summary.json`,
  `cached-313-consumer72/summary.json`; cada uno conserva 24 aceptados,
  48 rechazos esperados, 0 fallos y 144 ejecuciones nativas conocidas
- Variantes inválidas: `domain-invalid-probes/py*/receipt.json`; 12 por versión
  bajo -I -O, todas con rechazo previo a ejecución
- Consultas: `dependencies-core312-public-advisories/advisories.json`;
  `dependencies-core312-frozen-rebind` y su mapeo offline conservan las fechas
  originales, sin convertir la consulta histórica en un escaneo nuevo

Repetir el corpus es compatibilidad de runtime, no 288 casos distintos ni muestras
científicas independientes. Hash acredita integridad, no autoría o aprobación
humana. [Informe y límites](UNIVERSALITY_REVIEW.md).
