# Avance técnico de Universalidad — corte 2026-10-10

**Resultado: 41/60 comprobaciones, 68,3 % de avance técnico según la rúbrica propia
`UV-TECH-A11-60-v1`.** Es una evaluación de ingeniería con alcance finito; no
certifica que EquiFrame funcione con todos los datos, operaciones o entornos.

Candidato evaluado: núcleo/benchmark `0.12.0a11`, integrado en `main` por el
[PR 28](https://github.com/htroya/equiframe/pull/28), commit
`eb3fd70ec1dc059c58d7c95699981231ba5e6f60`. Este corte identifica el código evaluado;
la incorporación posterior de este informe no cambia los paquetes ni sus artefactos.

## Método y comparación histórica

Cinco comprobaciones por cada una de doce áreas, igual peso por área y por comprobación. Demostrada=1; pendiente, desconocida o evidencia de otra versión=0. Porcentaje=100*suma/60. Se fija esta lista antes de asignar resultados; las reglas no se retocan para obtener una cifra deseada.

La selección y el peso uniforme de estos 60 puntos son decisiones propias de
evaluación, no un estándar externo ni una medida de la tesis. La lista se fijó
antes de asignar los resultados de este corte. No se ha puntuado todavía A9
con esta lista, por lo que no existe aquí una serie histórica comparable.

El **25 % histórico** de la [matriz A9](UNIVERSALITY_MATRIX.md) contabilizaba
tres criterios íntegros cerrados de doce. Este **68,3 %** contabiliza avances
parciales demostrados mediante una granularidad diferente. No demuestra un
salto del 25 al 68,3 % con la misma escala y no modifica aquellos estados
históricos ni las condiciones del [plan UV01–UV12](UNIVERSALITY_PLAN.md).

El [JSON de este corte](UNIVERSALITY_TECHNICAL_PROGRESS_20261010.json) conserva
las 60 definiciones, los puntos y los motivos. Permite revisar la selección
y reproducir la suma. Los recibos de ejecución permanecen fuera de Git:
este documento los resume, no sustituye su reproducción independiente.

## Distribución de los 41 puntos

Los identificadores agrupan las mismas doce áreas de interés; aprobar un
punto de esta rúbrica no cierra el criterio íntegro del plan original.

| Área | Demostradas | Pendientes/no acreditadas |
|---|---:|---:|
| UV01 — Núcleo, contratos y entradas | 5/5 | 0 |
| UV02 — Versiones Python | 2/5 | 3 |
| UV03 — Plataformas nativas | 2/5 | 3 |
| UV04 — Dependencias y perfiles | 3/5 | 2 |
| UV05 — Operaciones y motores | 4/5 | 1 |
| UV06 — Preservación semántica | 4/5 | 1 |
| UV07 — Extensiones externas | 4/5 | 1 |
| UV08 — Diversidad de dominios | 3/5 | 2 |
| UV09 — Operación y recursos | 4/5 | 1 |
| UV10 — API, documentación y primer uso | 4/5 | 1 |
| UV11 — Procedencia, dependencias públicas y licencia | 2/5 | 3 |
| UV12 — Integración y reproducción | 4/5 | 1 |
| **Total** | **41/60** | **19** |

## Evidencia y límites de este corte

La [entrega de los cinco pasos](PRODUCT_UNIVERSALITY_FIVE_STEPS.md) registra
pruebas, artefactos por SHA-256 y el laboratorio Linux ARM64 de la VM existente.
El código conserva ejecuciones propias en Pandas, Polars y DuckDB; seis
direcciones de migración; entradas tipadas; ventanas `row_number`, `lag` y
`lead`; puertos externos; controles cooperativos de recursos; guía española
y un ejemplo instalado de seis entradas por tres motores.

La ejecución completa inicial en Windows conserva 4527 pases, 25 omisiones
y tres fallos de expectativas de versión del compilador. Tras corregir esas
expectativas, las 51 comprobaciones afectadas aprobaron; Linux ARM64 aprobó
122 comprobaciones finales sin fallos ni omisiones. Benchmark aprobó 620
con siete omisiones. No se presenta como una ejecución completa final del
núcleo sin fallos ni se trasladan recibos de A9/A10 a A11.

También se comprobaron puertos externos con implementaciones delegadas de
compilador/adaptador, regla y destino. Esto acredita la invocación de esos
puertos; no acredita un motor nuevo ni un consumidor independiente de A11.

Las 19 comprobaciones restantes requieren:

- Instalar y ejecutar A11 en Python 3.10, 3.11 y 3.13; Linux x64, macOS Intel
  y Apple Silicon. Las dos plataformas/una versión observadas no cierran
  las veinte celdas ni todos sus perfiles y etapas.
- Ejecutar perfiles individuales y extremos de dependencias; completar el
  producto de operaciones/tipos/políticas y la semántica común pendiente
  de división Decimal y localización temporal. El rechazo explícito de
  una operación conserva el significado, pero no implementa esa operación.
- Validar el consumidor/corpus independiente con A11 y entradas inválidas
  propias en los tres dominios. Los casos financieros y de telemetría que
  agotan presupuesto no sustituyen casos de datos inválidos.
- Comprobar rollback fresco con A11, los recorridos completos de instalación
  y la aceptación/adopción externa real. Los datos sintéticos no la acreditan.
- Completar la revisión de dependencias efectivas y resolver licencia,
  titulares y condiciones de redistribución. La autorización de integrar
  código no aprueba una licencia ni la validación humana independiente.

No se ejecutaron Actions, publicaron paquetes ni crearon recursos de pago
para esta medición. No se incorporan bases, modelos, secretos ni recibos
privados al repositorio.

## Las 60 comprobaciones y su calificación

### UV01 — Núcleo, contratos y entradas (5/5)

- **01.1 — Demostrada: 1.** Núcleo separado de benchmark, proveedor de nube y esquema de dominio; admisión explícita de extras. Arquitectura e imports opcionales: 10 controles aprobados; núcleo sin cloud/DW/benchmark.
- **01.2 — Demostrada: 1.** Contratos configurables de columnas, tipos, claves, ausencias, unidades/monedas, duplicados y tiempo. Contratos declarativos y controles de admisión; casos tipados y errores preservados.
- **01.3 — Demostrada: 1.** Lectura CSV, JSON/JSONL, Parquet y Arrow bajo contratos explícitos. CSV/JSON/Parquet/Arrow ejercidos; ejemplo instalado de seis entradas y tres motores.
- **01.4 — Demostrada: 1.** Consulta SQLite parametrizada de solo lectura con tipos explícitos y límites. SQLite de solo lectura parametrizado, rechazo de REAL para dinero, límites y cancelación.
- **01.5 — Demostrada: 1.** Respuesta binaria de un cliente API externo con lectura acotada, digest y cierre; no exige un servicio remoto en el ejemplo. Respuesta sintética/context manager; SHA y presupuesto verificados; el cliente real pertenece al consumidor.

### UV02 — Versiones Python (2/5)

- **02.1 — Pendiente/no acreditada: 0.** A11 instalado y ejecutado en CPython 3.10 con identidad conservada. No hay recibo de instalación y ejecución específicamente A11/CPython 3.10; A10 no se transfiere.
- **02.2 — Pendiente/no acreditada: 0.** A11 instalado y ejecutado en CPython 3.11 con identidad conservada. No hay recibo A11/CPython 3.11.
- **02.3 — Demostrada: 1.** A11 instalado y ejecutado en CPython 3.12 con identidad conservada. A11 ejecutado en Windows CPython 3.12.4 y Linux ARM64 CPython 3.12.15.
- **02.4 — Pendiente/no acreditada: 0.** A11 instalado y ejecutado en CPython 3.13 con identidad conservada. No hay recibo A11/CPython 3.13.
- **02.5 — Demostrada: 1.** Metadatos de compatibilidad y par de versiones coherentes; identidad real del intérprete registrada, sin heredar resultados entre versiones. Wheels A11, >=3.10,<3.14 y pin exacto benchmark/core; identidad del intérprete registrada.

### UV03 — Plataformas nativas (2/5)

- **03.1 — Pendiente/no acreditada: 0.** Instalación y ejecución nativa de A11 en Linux x64, al menos en un Python declarado. Las ejecuciones Linux x64 históricas son A9; no existe recibo actual A11.
- **03.2 — Demostrada: 1.** Instalación y ejecución nativa de A11 en Linux ARM64, al menos en un Python declarado. A11 instalado y ejecutado nativamente en Linux ARM64: 122 comprobaciones finales sin omisiones.
- **03.3 — Demostrada: 1.** Instalación y ejecución nativa de A11 en Windows x64, al menos en un Python declarado. A11 instalado fuera del checkout en Windows y ejemplos nativos; no cierra las cuatro versiones.
- **03.4 — Pendiente/no acreditada: 0.** Instalación y ejecución nativa de A11 en macOS Intel, al menos en un Python declarado. Sin ejecución nativa A11/macOS Intel.
- **03.5 — Pendiente/no acreditada: 0.** Instalación y ejecución nativa de A11 en macOS Apple Silicon, al menos en un Python declarado. Sin ejecución nativa A11/macOS Apple Silicon.

### UV04 — Dependencias y perfiles (3/5)

- **04.1 — Demostrada: 1.** Dependencias directas y extras explícitos; motores opcionales sin importación eager al importar el núcleo. Dependencias/extras explícitos e imports de motores diferidos; no es validación de todos los perfiles.
- **04.2 — Demostrada: 1.** Locks y metadatos del par A11 coherentes y fijados. Locks del par A11 y pin de dependencia coinciden con metadatos.
- **04.3 — Demostrada: 1.** Comprobación de dependencias en el par A11 instalado y aislado. pip check del par instalado en Windows y VM aprobado.
- **04.4 — Pendiente/no acreditada: 0.** Todos los perfiles individuales base/extras de A11 ejecutados con recibos completos. Todos los perfiles A11 base/extras individuales no están ejecutados.
- **04.5 — Pendiente/no acreditada: 0.** Extremos mínimo/reciente de A11 y sus marcadores ejecutados en todas las celdas comprometidas. No existe matriz completa A11 de mínimos/recientes y marcadores.

### UV05 — Operaciones y motores (4/5)

- **05.1 — Demostrada: 1.** Pandas, Polars y DuckDB ejecutan implementaciones nativas propias. Tres implementaciones nativas observadas, sin resultado común convertido.
- **05.2 — Demostrada: 1.** Seis direcciones entre los tres motores comprobadas contra un esperado independiente. Seis direcciones en migración y ventanas, con esperado literal independiente.
- **05.3 — Demostrada: 1.** Filtros, proyecciones, conversiones admitidas, agregaciones, ordenamientos y seis joins implementados y comprobados. IR relacional implementado dentro de sus capacidades documentadas; no promete conversiones arbitrarias.
- **05.4 — Demostrada: 1.** row_number, lag y lead deterministas ejecutados nativamente en los tres motores. row_number/lag/lead: 15 pruebas de ventanas, 12 de fronteras y ejemplos instalados.
- **05.5 — Pendiente/no acreditada: 0.** Producto completo de operaciones/tipos/políticas/direcciones y entornos cerrado; las capacidades requeridas no se sustituyen por rechazo. Intersección completa no cerrada: división Decimal Polars/DuckDB y otras combinaciones siguen sin implementación.

### UV06 — Preservación semántica (4/5)

- **06.1 — Demostrada: 1.** Texto/identificadores, ausencia/NaN y multiplicidad preservados en casos con esperados independientes. Identificadores, NULL/NaN y multiplicidad tienen esperados explícitos, incluidos C/D/E/F y ventanas.
- **06.2 — Demostrada: 1.** Decimal exacto, precisión extrema y unidades/monedas preservados en operaciones admitidas. Decimal(38,2), importes exactos y unidades ejercidos; operaciones incompatibles se rechazan.
- **06.3 — Demostrada: 1.** Fechas y timestamps admitidos conservan unidades y zonas sin conversiones silenciosas. Fechas y timestamps admitidos conservados; restricciones s/ms/us/ns/UTC declaradas.
- **06.4 — Demostrada: 1.** Empates, overflow y errores intermedios tienen diagnósticos verificables y no se ocultan como éxito. Empates/overflow/error-pruning comprobados y preservados como fallo.
- **06.5 — Pendiente/no acreditada: 0.** Semántica común completa entre motores para todas las operaciones exigidas de Decimal y tiempo, incluidas división y localización. División Decimal y localización temporal no se implementan con semántica común en todos los motores.

### UV07 — Extensiones externas (4/5)

- **07.1 — Demostrada: 1.** DataSource/TableInput y composición de proveedores externos sin modificar el núcleo. Proveedor externo compuesto, captura única, batches tipados y propagación de fallos comprobados.
- **07.2 — Demostrada: 1.** PlanCompiler/EngineAdapter registrables explícitamente por instancia, con verificaciones de comportamiento. Registros por instancia, compilers externos delegados y adapters externos ejecutados; no son motores nuevos.
- **07.3 — Demostrada: 1.** ArtifactStore externo mediante un puerto pequeño con verificaciones de comportamiento. ArtifactStore inyectado con put/get; fallos y publicación parcial probados con implementaciones externas.
- **07.4 — Demostrada: 1.** Reglas y destinos externos mediante registros/puertos pequeños con verificaciones de comportamiento. Regla externa realmente invocada y destino delegado publica dos filas conservando el recibo.
- **07.5 — Pendiente/no acreditada: 0.** Consumidor independiente del repositorio principal instalado y comprobado específicamente con A11 y el corpus congelado. No existe validación del consumidor independiente/corpus con A11; el recibo A9 conserva esa identidad.

### UV08 — Diversidad de dominios (3/5)

- **08.1 — Demostrada: 1.** Ejemplo financiero con contrato propio y esperado independiente ejecutado con A11. Recorrido D financiero: correcto/diferente/no evaluable aprobados con Decimal y monedas.
- **08.2 — Demostrada: 1.** Ejemplo de comercio con contrato propio y esperado independiente ejecutado con A11. Recorrido C comercio: correcto/diferente/error, publicación y totales propios comprobados.
- **08.3 — Demostrada: 1.** Ejemplo de telemetría/ciencia con contrato propio y esperado independiente ejecutado con A11. Recorridos E/F telemetría/ciencia con expectativas, NULL/NaN y multiplicidad propias.
- **08.4 — Pendiente/no acreditada: 0.** Variantes equivalentes, discrepantes e inválidas ejecutadas en los tres dominios con A11. C tiene datos inválidos; D/E no_evaluable agota presupuesto y no demuestra entradas inválidas de esos dominios. No se le asigna un punto por esa equivalencia.
- **08.5 — Pendiente/no acreditada: 0.** Aceptación o adopción de A11 documentada por consumidores reales de dominios externos; no basta evidencia sintética. No se encontró aceptación/adopción real documentada; las pruebas son sintéticas.

### UV09 — Operación y recursos (4/5)

- **09.1 — Demostrada: 1.** Hashes, esquemas y errores de entrada impiden producir una comparación exitosa de datos inválidos. Respuesta corrupta termina con código 3, sin comparación exitosa; comprobaciones de tipos/digests preservadas.
- **09.2 — Demostrada: 1.** Presupuestos acumulados de filas/bytes, tiempo y cancelación con pruebas reales. Límites acumulados, cierre de reader y cancelación/timeout SQLite antes del primer resultado.
- **09.3 — Demostrada: 1.** Medición por plataforma y disponibilidad explícita de recursos; no se inventan contadores o cuotas duras. Mediciones y capacidad por plataforma ejercidas en benchmark; omisiones POSIX/Windows se conservan.
- **09.4 — Demostrada: 1.** Cierre/limpieza, transporte adversarial o fallos recuperables y controles relevantes bajo -O comprobados. Cierre/limpieza y errores, bundles relocalizados H y corrupto bajo -O ejecutados.
- **09.5 — Pendiente/no acreditada: 0.** Cambio de versión A11→anterior→A11 y recuperación fresca cerrados en los entornos requeridos. Rollback íntegro desde y hacia A11 en los entornos comprometidos no ejecutado.

### UV10 — API, documentación y primer uso (4/5)

- **10.1 — Demostrada: 1.** API y formatos históricos conservados; nuevos elementos experimentales identificados. Registros de compatibilidad y fixtures históricos comprobados; APIs nuevas experimentales.
- **10.2 — Demostrada: 1.** CLI y códigos de coincidencia, discrepancia y entrada inválida comprobados. Ayuda/códigos observados en recorridos; ejemplo actual distingue 0/1/3.
- **10.3 — Demostrada: 1.** Guía española, ejemplos completos y documentación distribuida coherentes con las capacidades. Guía española y ejemplo distribuidos; incluye límites de SQL, cliente API, ventanas y memoria.
- **10.4 — Demostrada: 1.** Primer uso instalado fuera del checkout con seis entradas y tres motores en Windows y Linux ARM64. Seis entradas/tres motores en instalación externa Windows y Linux ARM64, con positivo y negativos.
- **10.5 — Pendiente/no acreditada: 0.** Primer uso y recorridos completos de A11 en cinco plataformas por cuatro Python, con consumidor externo. Recorridos íntegros A11 veinte celdas y consumidor externo pendientes.

### UV11 — Procedencia, dependencias públicas y licencia (2/5)

- **11.1 — Demostrada: 1.** Dependencias declaradas y resueltas identificadas en metadatos y locks del candidato A11. Declaraciones y resolución en locks A11 identificadas; no sustituye inventario de todos los binarios nativos.
- **11.2 — Pendiente/no acreditada: 0.** Consultas completas de avisos para todas las dependencias efectivas de A11, sin desconocidos y con fechas/identidad de alcance. No se acreditan consultas completas para el candidato efectivo A11; las consultas A10 conservan sus fechas y alcance.
- **11.3 — Demostrada: 1.** Instalación offline desde dependencias fijadas con hashes y procedencia registrada, sin atribuir consultas antiguas a una auditoría nueva. VM: sync offline --require-hashes con locks y cache identificados. No se presenta como auditoría nueva.
- **11.4 — Pendiente/no acreditada: 0.** Titulares y licencia/condiciones de EquiFrame aprobados y registrados. Licencia/titulares aprobados pendientes según decisión registrada.
- **11.5 — Pendiente/no acreditada: 0.** Condiciones de terceros y corpus resueltas para el alcance de redistribución, incluida la restricción Treasury. Restricción Treasury y condiciones de redistribución del corpus/terceros sin cierre aprobado.

### UV12 — Integración y reproducción (4/5)

- **12.1 — Demostrada: 1.** Todos los cambios de A11 integrados en main y cotejados por árbol. PR28 fusionado; main contiene el árbol autorizado y está limpio.
- **12.2 — Demostrada: 1.** Wheels/sdists del par A11 identificados por SHA-256 y ligados a los bytes de Git. Cuatro artefactos con hashes verificados; 477+122 miembros distribuidos coinciden con main.
- **12.3 — Demostrada: 1.** Reconstrucción nativa desde sdists con wheels idénticos entre Windows y Linux ARM64. Ambos sdists reconstruyen los mismos wheels; fuente corregida core mantiene el hash del wheel.
- **12.4 — Demostrada: 1.** Recibos de pruebas/ejemplos conservados y ligados al código integrado, incluidos fallos y omisiones reales. JUnit/ejemplos/recibos preservan pases, fallos iniciales, omisiones y correcciones focales; paquetes coinciden con main.
- **12.5 — Pendiente/no acreditada: 0.** Toda la matriz nativa y obligaciones anteriores cerradas, con reproducción/aceptación independiente documentada. No existen matriz completa ni aceptación independiente; autorización de merge no las reemplaza.
