# Matriz de revisión de madurez M01 a M16

Candidato producto c4f6a903f580f5e98d63db6e225e0a042221f4ec. Corte de revisión 8 de octubre de 2026. Alcance y denominador originales conservados.

**1/16 criterios íntegramente cumplidos = 6.25 % de cierre de este plan.** No es una medida universal de madurez, ni comparable con el 65 % sin rúbrica. Las subpruebas aprobadas no suman criterios fraccionarios. Las obligaciones pendientes impiden el cierre global.

| Criterio | Estado | Evidencia observada y límite | Próximo paso |
|---|---|---|---|
| M01 Identidad, alcance y trazabilidad | CUMPLIDO | Base/usabilidad identificadas; fuente c4 y consumidor 28cd3d7, seis artefactos y manifiesto verificados; alcance 16 fijo; parche posterior separado. | Conservar vínculos e identidades al incorporar nuevos recibos. |
| M02 Comportamiento funcional y semántica | PARCIAL | Núcleo c4: 4484 pruebas fuente y 4484 instaladas en 3.10; casos equivalentes/diferentes/no evaluables y rechazo optimizado. No está completo el recorrido de todos los paquetes comprometidos. | Completar el benchmark y consumidor del candidato tras resolver recursos/lock, sin cambiar esperados. |
| M03 API, CLI, contratos y formatos | PARCIAL | Registros, firmas, assets y lectores históricos del núcleo comprobados; seis esquemas extienden solo productor a8/default. Falta consolidar el cierre final del conjunto núcleo/benchmark/consumidor. | Cerrar metadatos y controles finales del benchmark; conservar versiones de formato y fixtures. |
| M04 Compatibilidad ejecutada | BLOQUEADO | La meta conserva 3.10–3.13, perfiles y extremos. ARM64 3.10/3.12 no ejecutado; Windows/macOS sin runner autorizado; matriz final Linux incompleta. | Ejecutar las celdas restantes en entornos autorizados y revisar recibos del mismo candidato. |
| M05 Artefactos, instalación y reproducción | PARCIAL | Seis artefactos congelados; núcleo c4 3.10: base/extras, wheel/sdist y reconstrucción idéntica. Benchmark requiere declaración directa de typing_extensions y lock coherente; el parche aún no produjo artefactos. | Autorizar la operación de lock pendiente, construir nueva identidad si cambian bytes y revalidar paquetes/celdas afectados. |
| M06 Calidad repetible y CI honesta | PARCIAL | Nueve etapas del núcleo c4 3.10 en exit 0. Benchmark c4 3.10: 581 pases, 7 fallos y 7 errores por admisión de disco. Herramientas revisadas: 34 tests en 3.10 y 3.12; Ruff/formato pasan. Actions no ejecutado. | Completar los controles finales aún abiertos con espacio suficiente y el lock coherente. |
| M07 Regresión con esperados independientes | PARCIAL | Conservados fallos previos de sintaxis, fechas/Decimal, tipado, dependencia directa y controles del handoff; regresiones del núcleo pasan. Falta verificación del parche benchmark y matriz final restante. | Verificar el fallo y su corrección en metadatos instalados del próximo benchmark; completar celdas requeridas. |
| M08 Dependencias y revisión de seguridad | BLOQUEADO | Inventario c4 3.10 generado. Consulta OSV nueva detenida por autorización de transmisión; revisión de seguridad de fuente anterior detenida por plataforma. Consulta previa 3.11 no cubre el candidato/matriz completos. | Resolver el permiso específico de consulta y la vía permitida para la revisión pendiente; ningún pase de seguridad se infiere. |
| M09 Derechos y distribución | BLOQUEADO | No se recibió decisión real del titular sobre derechos/condiciones; tampoco se eligió una licencia en su nombre. | El titular confirma titulares, destinatarios/condiciones y notices aplicables; nueva identidad si cambian bytes. |
| M10 Recursos y rendimiento | PARCIAL | 100 y 1000 filas, tres repeticiones por tamaño, seis resultados correctos y límite no evaluable. RSS/tiempo/disco observados; psutil AccessDenied deja instrumentación incompleta, exit 3. | Completar la medición en un entorno que permita observar los contadores requeridos; no declarar SLO ni rendimiento VM. |
| M11 Actualización y recuperación | PARCIAL | Recorrido offline A7 → c4 → A7 y recuperación nueva: 42 comandos correctos, pip check, payload exacto, cuatro estados H bajo -O y fallos de consumidor; 235 archivos previos intactos. Es un avance acotado Linux 3.12, no todos los controles del alcance. | Consolidar interrupción/reanudación y recuperación en celdas/paquetes pendientes; no repetir la prueba offline ya válida sin cambio. |
| M12 Evidencia e integridad | PARCIAL | Kit original: 36 miembros verificados; logs/recibos de recuperación cotejados; lectores y alteraciones cubiertos en el núcleo. Revisor de VM rechaza omisiones, mezcla de candidato y falsa arquitectura con fixtures unitarias explícitas. | Revisar la evidencia real del resto de paquetes/celdas; hashes y tests sintéticos no prueban ejecución VM ni autoría. |
| M13 Laboratorio maestria-vnic | BLOQUEADO | Ninguna autenticación, transferencia o ejecución VM de esta tarea. TCP 22 devolvió Network is unreachable. Se admite el entorno Codex existente con acceso, pero no llegaron recibos. | Ejecutar el kit revisado standalone en ARM64 3.10/3.12, registrar ejecutor y transporte, devolver evidencia y revisarla. |
| M14 Consumidor e interfaces | PARCIAL | Consumidor 0.1.10 identificado; recorridos instalados del núcleo y recuperación externa verificados. Recorrido completo de 72 casos del consumidor nuevo pendiente por guardia de 4 GiB libres y celdas abiertas. | Completar consumidor wheel/sdist sin rebajar guardias; el alcance no incluye implementar gateway/DW. |
| M15 Mantenimiento y gobierno | BLOQUEADO | Procedimientos y ensayo de defecto existentes; faltan responsables/suplentes aceptados, canal y política real de soporte legado. | El titular y responsables aceptan funciones y política; no se prometen SLA ni se contacta a terceros automáticamente. |
| M16 Revisión independiente y cierre | BLOQUEADO | Faltan criterios anteriores y reproducción/revisión humana independiente; U12 de usabilidad sigue pendiente. | Una persona independiente revisa el mismo candidato/evidencia; después se decide el cierre. Main requiere nueva autorización expresa tras revisión. |

## Referencias del expediente privado

Las rutas siguientes son relativas a evidence/ en el expediente adjunto, salvo ../review/. El índice JSON conserva hashes y separación entre recibos finales, preliminares y herramientas.

- M01: scope-freeze.json; scope-amendment-002.json; recovered-receipts-verification-001.json; maturity-evidence-index.json
- M02: checks-core-310-003.json; checks-core-310-003-05.log; checks-core-310-003-08.log; checks-benchmark-310-001.json
- M03: schema-delta.json; checks-core-310-003.json; benchmark-backport-before-001.log
- M04: scope-freeze.json; checks-core-310-003.json; interpreters.json; jose-preparation-status.json
- M05: artifacts-c4f6a90.json; checks-core-310-003.json; benchmark-backport-before-001.log
- M06: checks-core-310-003.json; checks-benchmark-310-001.json; handoff-final-310-002.log; handoff-final-312-001.log
- M07: baseline-syntax-py310.json; tests-310-focused-001.log; tests-310-focused-003.log; checks-core-310-003.json; benchmark-backport-before-001.log
- M08: dependencies-c4-core-310/inventory.json; advisories-c4-core-310-platform-rejection.json; advisories-draft-core-311/advisories.json
- M09: ../review/DECISIONES_PENDIENTES_ES.md
- M10: measure-c4-310-002/protocol.json; measure-c4-310-002/summary.json; measure-c4-310-002/bounded-limit.json; measurement-c4-pair-binding-310.json
- M11: upgrade-c4-offline-312-001/receipt.json; recovered-receipts-verification-001.json
- M12: recovered-receipts-verification-001.json; checks-core-310-003.json; handoff-final-310-002.log
- M13: jose-preparation-status.json; scope-amendment-002.json
- M14: checks-core-310-003-08.log; upgrade-c4-offline-312-001/receipt.json; cleanup-request-inventory.json
- M15: maintenance-exercise.json; ../review/MAINTENANCE_EXERCISE_ES.md; ../review/DECISIONES_PENDIENTES_ES.md
- M16: maturity-evidence-index.json; ../review/DECISIONES_PENDIENTES_ES.md
