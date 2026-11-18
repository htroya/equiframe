# Plan de madurez verificable M01–M16

Congelación inicial: 2026-10-07T23:44:33.501697+00:00. Revisión 1, antes de medir el candidato nuevo.

Base remota `876033ce111fd38123799db4e4c40bd0202ec8df`, árbol `3a8ec2c938ccc716d33b4d0954ca00d56f83bebc`; el checkout recuperado tiene el mismo árbol y un historial local diferente, sin atribuirle commits remotos. Rama `maturity/python310-313-20261007`. Se preserva la entrega de usabilidad; U12 permanece pendiente. No se encontró rúbrica verificable del 65 % anterior.

## Alcance y soporte conservado

Biblioteca privada, benchmark y consumidor; sin integración real servicio/DW, publicación, Actions, despliegue, PC del titular ni cambios globales. Denominador fijo 16. Candidato propuesto: núcleo/benchmark 0.12.0a8 y consumidor 0.1.10; estos nombres no acreditan construcción ni pruebas.

Linux x64 CPython 3.10/3.11/3.12/3.13: perfiles base, arrow, pandas, polars, duckdb, engines, ml y all; benchmark base/engines/ml/resources/all, consumidor, wheel y sdist. Bandas mínimo-directo compatible, fijada y reciente permitida, con selección por riesgo y resolución real; no producto cartesiano universal. ARM64 maestria-vnic 3.10 y 3.12 es obligatorio y está bloqueado por red del ejecutor. Windows x64 y macOS Intel/ARM64 3.12 permanecen visibles conservadoramente por la hoja de ruta histórica, bloqueados sin runner autorizado. No se retira soporte tras observar resultados.

## Cambios y comprobaciones

1. Sustituir sintaxis/stdlib posterior a 3.10, conservando aliases nombrados, tipos, esquemas, gates, errores y semántica
2. Propagar el intérprete real en todos los arneses y declarar dependencias/backports compatibles
3. Resolver perfiles, ejecutar suites y casos equivalentes/diferentes/inválidos/incompletos con esperados independientes, incluidos -O, fixtures históricos, recuperación y consumidor externo
4. Congelar bytes finales, construir/reconstruir wheel/sdist, conservar hashes y comprobación de site-packages; separar cada fallo y reintento
5. Medir cargas sintéticas de 100 y 1000 filas, recursos y límites sin SLO aprobado; reutilizar controles existentes
6. Revisar solo alcance permitido de dependencias, contenido e integridad, sin reanudar la revisión de seguridad detenida ni atribuirle pase
7. Preparar decisiones concretas de derechos, mantenimiento y revisión humana independiente, sin fabricar aprobaciones

## Presupuestos fijados

Una suite a la vez, un hilo de motor/BLAS; ejemplos hasta 120 s, suite/celda hasta 1800 s y 512 MiB de evidencia nueva. Mantener al menos 1 GiB de disco y 2 GiB RAM disponible. Medir recursos observados; los presupuestos de EquiFrame son cooperativos, no cuotas duras. Entornos temporales propios pueden retirarse tras conservar inventarios, locks, logs y artefactos verificables; nunca se limpian recursos ajenos.

## Evidencia y fronteras

Cada criterio enlaza requisito → caso → comando → resultado → artefacto/hash. Un registro positivo sin prueba no suma. M09/M15/M16 exigen decisiones/aceptaciones reales. M08 conserva la revisión de seguridad incompleta; la compatibilidad ordinaria no la sustituye. José conserva transporte/infraestructura, Jhair modelo/ETL de dominio. J01–J08 se registran sin atribuir una entrega solicitada como realizada.

## Revisión de alcance 2

Actualización expresa del titular, 2026-10-07 23:58 UTC: los ensayos ARM64 3.10/3.12 pueden ejecutarse desde el entorno Codex que ya tiene acceso. Se entregan scripts y artefactos sin credenciales, registrando ejecutor, comandos y hashes. M13 y criterios vinculados permanecen pendientes hasta recibir y revisar los recibos reales. Los dieciséis criterios y celdas se conservan; no se autoriza push directo ni merge a main.
