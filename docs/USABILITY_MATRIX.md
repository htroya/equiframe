# Matriz de usabilidad U01–U12

La tabla siguiente conserva el corte A7. El
[plan vigente](USABILITY_CURRENT_PLAN_20261010.md) mantiene los doce criterios y
sus subcomprobaciones y separa la evidencia por candidato/entorno.

Revisión 2026-10-07. Alcance fijado en [USABILITY_PLAN](USABILITY_PLAN.md).
Cada criterio es indivisible y vale un punto. Se muestran sus 72 subcomprobaciones.
La evidencia E01–E10 se describe en [USABILITY_REVIEW](USABILITY_REVIEW.md#evidencia-sanitizada).
Los recibos completos, comandos y hashes están en el manifiesto entregado fuera de Git.

## Línea base verificada y resultado

Línea base retrospectiva del A7 original: 7/12 criterios cumplidos (58,33 %).
Se reconstruye ahora con el árbol original y los recibos anteriores, aplicando
las mismas 72 subcomprobaciones fijadas antes de las pruebas nuevas. No fue una
medición humana ni un porcentaje registrado antes de esta revisión. Las brechas
concretas están en «Reconstrucción de la línea base»; los recibos antiguos no se
atribuyen al wheel documental.

Resultado de la revisión documental del A7: **11/12 CUMPLIDOS = 91,67 %**.
U12 permanece BLOQUEADO por ausencia de observaciones reales. Los perfiles
ficticios autorizados sirven para ensayo, no cambian el denominador ni acreditan
consentimientos/independencia/tiempos humanos. No se declara 100 %.

| Criterio | Línea base | Candidato | Evidencia |
|---|---|---|---|
| U01 | PARCIAL | CUMPLIDO | E01, E02 |
| U02 | PARCIAL | CUMPLIDO | E02, E03, E04 |
| U03 | CUMPLIDO | CUMPLIDO | E01, E02, E05 |
| U04 | CUMPLIDO | CUMPLIDO | E01, E02, E05 |
| U05 | CUMPLIDO | CUMPLIDO | E02, E05, E06 |
| U06 | CUMPLIDO | CUMPLIDO | E05, E07 |
| U07 | CUMPLIDO | CUMPLIDO | E05, E06, E07 |
| U08 | CUMPLIDO | CUMPLIDO | E01, E02, E07 |
| U09 | PARCIAL | CUMPLIDO | E01, E02, E07 |
| U10 | PARCIAL | CUMPLIDO | E01, E02, E03, E08 |
| U11 | CUMPLIDO | CUMPLIDO | E04, E07 |
| U12 | BLOQUEADO | BLOQUEADO | E09 |

## U01

Usuario afectado: ambos perfiles. Entrada: Tarea de comparar/preparar/integrar.
Necesidad: Elegir una API y completar una tarea sin aprender toda la biblioteca.
Implementación/disposición: Añadidas dos guías españolas enlazadas desde inicio/README/manual.
Prioridad: P1/P2.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U01.01 Entradas españolas por ambos roles | CUMPLIDO | README/inicio enlazan las dos guías ejecutables; **D-entry, D-architect, D-scientist, ROLES** |
| U01.02 Problema, API, requisitos y límites | CUMPLIDO | Arquitecto duckdb; científico arrow; engines para seis pares; sin ML obligatorio; **D-architect, D-scientist, D-choice, D-install** |
| U01.03 Comparación, preparación, migración e integración sin nuevo orquestador | CUMPLIDO | Tabla de entradas, scripts externos y cuatro programas conservados; **D-choice, ROLES, H-consumer** |

## U02

Usuario afectado: ambos perfiles. Entrada: Wheel, dependencias y lock identificados.
Necesidad: Instalar con resolución completa fuera del checkout.
Implementación/disposición: Receta A7 separada del kit histórico; instalación normal y con hashes del nuevo wheel.
Prioridad: P1/P2.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U02.01 Entornos nuevos externos; resolver normal y pip check | CUMPLIDO | 3.12 normal y 3.13 lock completo: install y pip-check 0; **N312, N313** |
| U02.02 Extras y versiones efectivas; import site-packages | CUMPLIDO | 119 miembros iguales antes/después; versiones registradas; perfiles previos compatibles; **B312, B313, DELTA** |
| U02.03 Lock completo con hashes por entorno | CUMPLIDO | 3.13 completa con hashes; 3.12 normal conserva lock identificado; **N313, N312** |
| U02.04 Canal privado; no homónimo, editable, sys.path o no-deps | CUMPLIDO | Comandos -I --no-index --find-links y pip report conservados; **N312, N313, D-install** |

## U03

Usuario afectado: ambos perfiles. Entrada: Tablas candidatas y esperado independiente.
Necesidad: Aceptar solo equivalencia bajo el contrato.
Implementación/disposición: Sin cambio de comparador; ampliar ejemplos de referencias inválidas y presupuesto.
Prioridad: P0 de preservación.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U03.01 Equivalente y diferente contra esperado independiente | CUMPLIDO | 18 combinaciones nativas y scripts nuevos coinciden con esperado; **T-money, ROLES** |
| U03.02 Esperado inválido y evaluación incompleta rechazan | CUMPLIDO | not_evaluable y EquivalenceNotEvaluableError; nunca ausencia de diferencias válida; **T-invalid, ROLES** |
| U03.03 Claves compuestas, duplicados, NULL/NaN, Decimal, tipos y orden | CUMPLIDO | Tenant/id; duplicado tardío; clave incompleta allow/reject; máscara NULL/NaN; precisión y timestamps; ties preserve/reject; **T-money, T-key, T-values** |
| U03.04 Totales compensados no ocultan cambios por clave | CUMPLIDO | compensated_reject: different, accepted=false, EquivalenceDifferentError, normal y -O; **H-fault, H-fault-O** |
| U03.05 Inferencia visible y contrato de dominio explícito | CUMPLIDO | Solo esquema esperado; contrato/política declarados se preservan; **T-contract, D-semantics, D-choice** |
| U03.06 Gate funciona bajo Python -O; bool/complete/report no aceptan | CUMPLIDO | 20 scripts por entorno incluyen modo -O; reporte rechazado como input; completos diferentes no pasan; **ROLES, T-reportinput, T-invalid, D-choice** |

## U04

Usuario afectado: ambos perfiles. Entrada: Resultado y evidencia sintética.
Necesidad: Encontrar causa, clave, columna y siguiente acción.
Implementación/disposición: Dos vistas: minimizada por defecto y detalle explícito solo sintético.
Prioridad: P2.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U04.01 Consola, HTML y notebook coinciden en estado, completitud y conteos | CUMPLIDO | 13 pruebas exactas de vistas y estados; HTML/notebook mismo texto visible; role scripts nuevos tres vistas; **T-views, ROLES, RENDER** |
| U04.02 Causa y siguiente acción | CUMPLIDO | Captured values differ, next_action y limitaciones presentes; guías conservan explicación; **T-views, ROLES, D-diagnosis, RENDER** |
| U04.03 Clave, columna y valores sintéticos localizables | CUMPLIDO | En los reportes sintéticos ya producidos: clave B, columna quantity, integer(21)/integer(20), y ejemplos científicos con observed_at/duration_s/sample_id; hechos visibles comprobados en texto/HTML/notebook. Clave compuesta [1,7] adicional en recibo histórico exacto.; **T-money, T-views, ROLES, RENDER** |
| U04.04 Minimización por defecto y evidencia original privada | CUMPLIDO | Test roles verifica include_metadata/values False versus True; vistas indican unchanged_in_original_comparison y until_caller_deletes; **ROLES, T-views, D-architect, RENDER** |
| U04.05 Ejemplos versus diferencias completas; parcial/desconocido no es cero | CUMPLIDO | added/removed/modified=1 cada uno; records=4; examples=2; unknown/partial preservados; **T-counts, T-views, RENDER** |
| U04.06 Diagnóstico guardado antes de rechazar | CUMPLIDO | 20 scripts comprueban report.json y detalle legibles incluso cuando retorna 1; **ROLES** |

## U05

Usuario afectado: ambos perfiles. Entrada: Fallos de uso, capacidad, recursos y artefactos propios.
Necesidad: Diagnosticar y repetir sin éxito falso ni sobrescritura.
Implementación/disposición: Reusar errores/recuperación existentes y comprobar nuevo destino repetido.
Prioridad: P0 de preservación.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U05.01 Dependencias ausentes | CUMPLIDO | pyarrow/pandas/polars/duckdb/scikit-learn/numpy EXPECTED_REJECTION; pip check solo salud metadata, no prueba extra funcional; **H-absence, D-diagnosis** |
| U05.02 Claves inválidas | CUMPLIDO | Estados y diagnósticos explícitos según expected/peer e incomplete allow/reject; **T-key, T-invalid** |
| U05.03 Tipos/planes no admitidos | CUMPLIDO | Ambos compiladores comprobados antes del proveedor; recorrido E not_evaluable por orden contractual; **T-preflight, A312, D-journeys** |
| U05.04 Corrupción funcional de reporte propio, acotada | CUMPLIDO | report_corruption.rejected=true en recibos históricos normal y -O; **H-fault, H-fault-O** |
| U05.05 Permisos insuficientes y presupuestos acotados | CUMPLIDO | Permiso inyectado: hint[permission_denied], exit3; destino ocupado queda intacto; presupuesto not_evaluable. No se atribuye una prueba OS ACL nueva; **T-permission, T-invalid, D-diagnosis** |
| U05.06 Etapa/acción; fallo nunca equivale a éxito | CUMPLIDO | CLI dos líneas operation_failed + hint[categoría], exit3, sin traceback/private; fallos no se anuncian aceptados; **T-hints, H-fault, D-diagnosis** |
| U05.07 Repetición nueva sin sobrescribir entrada o corrida | CUMPLIDO | Test comprueba bytes de reporte intactos tras repetición rechazada; A-H por carpeta distinta; **ROLES, T-no-overwrite, A312** |

## U06

Usuario afectado: arquitecto. Entrada: IR admitido y entradas fijadas.
Necesidad: Migrar entre seis pares con esperado independiente.
Implementación/disposición: Sin cambio de compilador; corregir explicación de preflight E.
Prioridad: P2.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U06.01 Seis direcciones entre tres motores | CUMPLIDO | 18 observaciones: 3 familias × 6 pares; dos SpyAdapter calls por caso; **T-six** |
| U06.02 Misma entrada y esperado independiente | CUMPLIDO | 6 filas explícitas join; USD3.75/EURNULL/JPY900; captured expected, agreement y reglas separados de O; **T-six** |
| U06.03 Filtros | CUMPLIDO | 36 observaciones de filtro compuesto (seis pares × seis nombres) pasadas en A7 original; **T-filter** |
| U06.04 Joins con ausencias y multiplicidad | CUMPLIDO | 4 matches cartesianos + NULL izquierdo + id2 sin match; seis direcciones; **T-six** |
| U06.05 Agregaciones del recorrido | CUMPLIDO | USD3.75/2; EURNULL/2; JPY900.00/1, en seis direcciones; **T-six** |
| U06.06 Ejecuciones nativas y preflight con límites explícitos | CUMPLIDO | Adapters llamados una vez cada uno; plan.engine correcto; preflight anterior a proveedor; **T-six, T-preflight, D-architect** |

## U07

Usuario afectado: arquitecto. Entrada: Archivos de esquema explícito y salida Parquet local.
Necesidad: Conservar registros/recibos y publicar tras el gate.
Implementación/disposición: Reusar workflow/destino; explicar precommit frente a postcommit.
Prioridad: P0 de preservación.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U07.01 Recorridos CSV y JSON/JSONL admitidos | CUMPLIDO | Tres nodeids conservan id001/002/003 y Decimal1234.50/NULL/0.00; **T-ingest** |
| U07.02 Esquema, conversiones, registros inválidos | CUMPLIDO | 6 conversiones; JSONL2 registros→1 aceptado+1 quarantined; esquema/JSON/ID inválido no publica; **T-ingest, T-quarantine** |
| U07.03 Checkpoints y gate antes de salida | CUMPLIDO | Captura única/roundtrip; independiente continúa; Parquet rechaza esperado no aprobado; **T-checkpoint** |
| U07.04 Repetición idempotente local | CUMPLIDO | Mismo recibo y puntero; una versión de dos filas; reemplazo explícito retiene anterior; **T-idempotent** |
| U07.05 Fallo precommit conserva versión anterior | CUMPLIDO | Fallos precommit conservan current; intento nuevo no publicado puede recuperarse; **T-precommit, H-fault** |
| U07.06 Fallo postcommit distingue publicación de recibo | CUMPLIDO | Dos tests postcommit normales y -O preservan estado committed_application_incomplete y no cero; **H-regressions, D-architect** |
| U07.07 Sin extrapolar a servicio o DW productivo | CUMPLIDO | Guía limita transacción, concurrencia y durabilidad; José/Jhair siguen separados; **D-architect, D-choice** |

## U08

Usuario afectado: arquitecto. Entrada: Python/SQL y snapshot versionado.
Necesidad: Integrar un gate en proyecto/pytest externo.
Implementación/disposición: Ejemplo SQL+Python y test pytest local; reutilizar aplicación 0.1.9.
Prioridad: P2.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U08.01 Consumidor externo instalado | CUMPLIDO | Consumer0.1.9 externo histórico; nuevos scripts exactos en role-project fuera de fuente; **H-current, H-consumer, ROLES, B312** |
| U08.02 Python y SQL-DuckDB | CUMPLIDO | Good acepta; different rechaza y deja diagnóstico, normal y -O; **D-architect, ROLES** |
| U08.03 Prueba pytest local reutilizable en CI | CUMPLIDO | Test real pytest anidado produce 1 passed en cada entorno; **ROLES** |
| U08.04 Snapshot fijado y comprobación de artefactos cuando aplica | CUMPLIDO | Pruebas ID fijado, captura desacoplada y mismatch sha/bytes/schema/rows/nullability; **T-snapshot, A312** |
| U08.05 Transporte/credenciales/cuotas/reintentos pertenecen al consumidor | CUMPLIDO | Guía y elección API mantienen esas responsabilidades fuera del core; **D-architect, D-choice** |
| U08.06 No afirmar job remoto ni servicio real de José | CUMPLIDO | Declaración explícita CI local/mock; sin Actions ni infraestructura ajena; **D-architect** |

## U09

Usuario afectado: científico. Entrada: Versiones de preparación de datos.
Necesidad: Conservar ID, NULL, Decimal y tiempo.
Implementación/disposición: Script de ocho casos y explicación de consecuencias para el dataset.
Prioridad: P1/P2.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U09.01 Script de preparación ejecutable | CUMPLIDO | Ocho casos × normal/-O en ambos Python; **D-scientist, ROLES** |
| U09.02 IDs, ausencias, precisión y fechas conservadas | CUMPLIDO | Good equivalente; los cambios de valor/ausencia/hora rechazan; **D-scientist, ROLES** |
| U09.03 Esperado independiente | CUMPLIDO | Esperado literal Decimal e instantes enteros de Arrow; **D-scientist, ROLES** |
| U09.04 Pérdida de filas, clave cambiada y desplazamiento temporal rechazados | CUMPLIDO | Tres escenarios different y gate no cero, normal/-O; **ROLES** |
| U09.05 Consecuencia para dataset explicada | CUMPLIDO | Guía describe ventanas, joins, cobertura y distribución; equivalencia no acredita ciencia; **D-scientist** |
| U09.06 Perfiles/modelos separados; requisitos/no estimable; sin resultado científico | CUMPLIDO | Guía remite a contratos y estados; no entrena ni afirma calibración/utilidad científica; **D-scientist, D-semantics, D-diagnosis** |

## U10

Usuario afectado: ambos perfiles. Entrada: Guías/CLI/artifactos históricos y actuales.
Necesidad: Instalar, diagnosticar, cambiar y volver a un artefacto identificado.
Implementación/disposición: Corregir cabeceras/recetas; mantener decisiones de soporte explícitamente pendientes.
Prioridad: P1/P2.
Dependencia: Responsables/respaldos/canales y compromisos operativos requieren decisión del titular; documentarlos no los aprueba.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U10.01 README, guías, firmas, CLI, ejemplos/versiones/changelog coherentes | CUMPLIDO | 62 tests afectados + assets, formato, Ruff, mypy, build/Twine; guías empaquetadas iguales; CLI0; **BUILD, DIST, N312, D-api** |
| U10.02 Instalación y diagnóstico ejecutables | CUMPLIDO | Dos instalaciones nuevas, 21 casos roles y 31 A-H por entorno; **N312, N313, ROLES, A312** |
| U10.03 Actualización y reversión con artefactos identificados | CUMPLIDO | Lifecycle A7 original histórico + selección rollback A7 identificado; good acepta/different y límite rechazan; no formato reescrito; **H-lifecycle, ROLLBACK, D-rollback** |
| U10.04 Sin rutas del autor ni pasos esenciales ocultos | CUMPLIDO | Scripts usan --output y valores locales; pruebas externas pasan; wheelhouse requiere ubicación propia explícita; **ROLES, D-install** |
| U10.05 Reporte de problemas y soporte real | CUMPLIDO | Issues privados solo usuarios autorizados o proveedor por canal ya verificado; no servicio de soporte garantizado; **D-problems, D-maintenance** |
| U10.06 Responsables/canales/SLA pendientes explícitos | CUMPLIDO | Cada owner/backup Pending; canal dedicado seguridad sin verificar; SLA no aprobado; **D-maintenance, D-problems** |
| U10.07 Historia preservada y separada | CUMPLIDO | Hashes A7 viejo/nuevo distintos; receta antigua rotulada; historial no reescrito; **DELTA, D-journeys, D-install** |

## U11

Usuario afectado: integrador/reproductor. Entrada: Consumidor 0.1.9, tres fuentes permitidas y esperados stdlib.
Necesidad: Reproducir cuatro programas desde instalación externa.
Implementación/disposición: Reutilizar matriz completa 72 casos del A7 original con prueba de identidad runtime.
Prioridad: P2.
Dependencia: Sin dependencia externa para este alcance local; servicio/DW y plataformas no medidas siguen separados.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U11.01 Reusar consumidor 0.1.9 y cuatro programas | CUMPLIDO | Mismo wheel pin A7 y cuatro programas; no consumidor reimplementado; **H-current, H-consumer** |
| U11.02 Datos permitidos de tres dominios; esperados stdlib independientes | CUMPLIDO | Provenance e independiente review fijan fuentes y 1152 salidas verificadas; **H-data, H-review** |
| U11.03 Entorno externo limpio identificado | CUMPLIDO | Ocho matrices principales y relocalizada identificadas por recibo, commit y wheel; **H-current, H-review** |
| U11.04 Matriz completa: 72 casos verificados | CUMPLIDO | 72 recibos válidos por matriz; 576 ejecuciones principales y72 relocalizadas; **H-consumer, H-current** |
| U11.05 Aceptaciones, rechazos esperados y fallos separados | CUMPLIDO | Por matriz24 PASS aceptadas+48 EXPECTED_REJECTION;0 FAIL; principales192/384; **H-consumer, H-current** |
| U11.06 Recibos/hashes; reutilización compatible explícita sin atribuir runs nuevos | CUMPLIDO | Módulos74 y dependencies idénticos; matrices pertenecen al wheel5d435e, no al documentalabab95; **DELTA, H-current, H-review** |

## U12

Usuario afectado: personas reales independientes. Entrada: Personas/proyectos/consentimiento reales.
Necesidad: Observar primer uso correcto y retención real.
Implementación/disposición: Protocolo preparado y tres perfiles ficticios; ninguna observación humana.
Prioridad: P2.
Dependencia: Hernán coordina tres proyectos/personas reales, permisos y revisión humana.

| Subcomprobación | Estado | Comprobación/evidencia |
|---|---|---|
| U12.01 Tres proyectos reales independientes: refactor, SQL y CI | BLOQUEADO | Protocolo y perfiles ficticios únicamente; falta evidencia humana auténtica. No se ejecutó ni se otorga punto; **D-adoption, D-fiction** |
| U12.02 Arquitectura y ciencia representadas | BLOQUEADO | Protocolo y perfiles ficticios únicamente; falta evidencia humana auténtica. No se ejecutó ni se otorga punto; **D-adoption, D-fiction** |
| U12.03 Consentimiento real e independencia con revisión humana | BLOQUEADO | Protocolo y perfiles ficticios únicamente; falta evidencia humana auténtica. No se ejecutó ni se otorga punto; **D-adoption, D-fiction** |
| U12.04 Ayuda, intentos, interpretación y utilidad observadas | BLOQUEADO | Protocolo y perfiles ficticios únicamente; falta evidencia humana auténtica. No se ejecutó ni se otorga punto; **D-adoption, D-fiction** |
| U12.05 Tres primeros diagnósticos <=300s con reloj predeclarado | BLOQUEADO | Protocolo y perfiles ficticios únicamente; falta evidencia humana auténtica. No se ejecutó ni se otorga punto; **D-adoption, D-fiction** |
| U12.06 Ninguna instrucción esencial fuera de guía; prácticas no cuentan como primer uso | BLOQUEADO | Protocolo y perfiles ficticios únicamente; falta evidencia humana auténtica. No se ejecutó ni se otorga punto; **D-adoption, D-fiction** |
| U12.07 Cambio real posterior e integración retenida en cada proyecto | BLOQUEADO | Protocolo y perfiles ficticios únicamente; falta evidencia humana auténtica. No se ejecutó ni se otorga punto; **D-adoption, D-fiction** |
| U12.08 Observaciones desfavorables conservadas; revalidación honesta | BLOQUEADO | Protocolo y perfiles ficticios únicamente; falta evidencia humana auténtica. No se ejecutó ni se otorga punto; **D-adoption, D-fiction** |

## Límites que no cambian el índice por conveniencia

El wheel documental final conserva versión privada 0.12.0a7 con hashes nuevos.
Sus 74 módulos runtime y metadatos de dependencias son byte-identical al A7
original. Los recibos heredados siguen identificando el wheel original; nunca
se describen como nuevas ejecuciones del wheel documental. Los nuevos ejemplos,
instalaciones, byte bindings y presentación tienen sus propios recibos.

U10 acredita documentación coherente y límites honestos, no disponibilidad de
un servicio de soporte. No hay responsables aceptados, SLA ni canal dedicado
de seguridad verificado. No se cierran licencia, publicación, seguridad integral,
ciencia, servicio de José, DW de Jhair ni plataformas sin ejecución.

## Reconstrucción de la línea base

El manifiesto `baseline-reconstruction.json` conserva bytes/hash del árbol original,
no una descripción retrospectiva sin fuente. La revisión mantiene el denominador
12 y no incorpora exigencias nuevas para bajar la base o mejorar el resultado.

| Brecha original | Hecho observado con el mismo criterio |
|---|---|
| U01.01 | Entrada española general, sin recorridos enlazados por ambos roles |
| U02.01 | A7 ya tenía instalaciones válidas; la receta activa de journeys aún indicaba 0.11.1 sin rotularla histórica. Esto es incoherencia de receta, no fallo de pip A7 |
| U09.02 | F usaba floats, sin NULL/fechas. El consumidor ya probaba Decimal/UTC y desplazamiento de una hora, pero su preparación era no-nullable. Faltaba mostrar preservación de ausencias en la ruta de preparación |
| U10.01 | Receta y cabeceras actuales desfasadas; no se penalizan textos que ya estaban rotulados históricos |
| U12.01–08 | No había observaciones humanas reales y continúan ausentes |

U03/U04/U05/U06/U07/U08/U11 estaban técnicamente cubiertos por los recibos
originales específicos que se relacionan abajo. Su reutilización depende de la
identidad de runtime y metadatos, no solamente de compartir versión A7.

## Referencias específicas de las subcomprobaciones

Cada identificador se desarrolla íntegramente en `subcheck-evidence.json` (E10):
archivo/hash, selector exacto, comando, entorno, entrada/esperado/observado y vínculo
al artefacto. Las pruebas históricas citadas tienen observación `call=passed`;
los IDs parametrizados completos están en ese archivo. Estos enlaces permiten
leer su comprobación en la fuente, sin confundir una prueba escrita con su recibo.

### D-entry

[packages/equiframe/docs/inicio.md](../packages/equiframe/docs/inicio.md), línea 1: Entradas españolas por rol y ruta diff/reporte/gate sin nuevo orquestador. Inspección documental, no observación humana.

### D-architect

[packages/equiframe/docs/arquitecto.md](../packages/equiframe/docs/arquitecto.md), línea 5: SQL con esperado literal, reportes antes del gate y pytest local. Inspección documental, no observación humana.

### D-scientist

[packages/equiframe/docs/cientifico.md](../packages/equiframe/docs/cientifico.md), línea 5: Preparación con Decimal, IDs, ausencias y fechas; esperado ajeno al cálculo. Inspección documental, no observación humana.

### D-choice

[packages/equiframe/docs/choosing-api.md](../packages/equiframe/docs/choosing-api.md), línea 12: Tabla por entrada: comparar, preparar, migrar, fijar snapshot, workflow. Inspección documental, no observación humana.

### D-install

[packages/equiframe/docs/installed-private.md](../packages/equiframe/docs/installed-private.md), línea 13: Canal privado; Python/plataforma y hash específicos; normal y lock separado. Inspección documental, no observación humana.

### D-journeys

[packages/equiframe/docs/journeys.md](../packages/equiframe/docs/journeys.md), línea 1: Receta vigente separada del 0.11.1 histórico; A-H con resultados esperados. Inspección documental, no observación humana.

### D-api

[packages/equiframe/docs/api.md](../packages/equiframe/docs/api.md), línea 173: Funciones y métodos reales; ComparisonReport.to_text/to_html/_repr_html_. Inspección documental, no observación humana.

### D-semantics

[packages/equiframe/docs/semantics.md](../packages/equiframe/docs/semantics.md), línea 35: Inferencia conservadora no reemplaza contrato de dominio. Inspección documental, no observación humana.

### D-maintenance

[packages/equiframe/docs/maintenance.md](../packages/equiframe/docs/maintenance.md), línea 6: Proceso propuesto, responsables y respaldos pendientes; sin SLA. Inspección documental, no observación humana.

### D-problems

[packages/equiframe/docs/maintenance.md](../packages/equiframe/docs/maintenance.md), línea 34: Issues privados para autorizados y datos no sensibles; proveedor por canal verificado. Inspección documental, no observación humana.

### D-rollback

[packages/equiframe/docs/upgrading.md](../packages/equiframe/docs/upgrading.md), línea 158: Seleccionar artefacto conocido y entorno compatible; revalidar; no reescribir formatos. Inspección documental, no observación humana.

### D-diagnosis

[packages/equiframe/docs/upgrading.md](../packages/equiframe/docs/upgrading.md), línea 113: Acciones por dependencia, capacidad, integridad, recursos, destino y ML. Inspección documental, no observación humana.

### D-adoption

[packages/equiframe/docs/adoption.md](../packages/equiframe/docs/adoption.md), línea 1: Protocolo sin observaciones humanas; tres proyectos y retención real requeridos. Inspección documental, no observación humana.

### D-fiction

[packages/equiframe/docs/piloto-simulado.md](../packages/equiframe/docs/piloto-simulado.md), línea 5: Tres perfiles ficticios; sin consentimientos, tiempos o resultados humanos. Inspección documental, no observación humana.

### N312

Recibo `installed-312-normal-002/receipt.json`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### N313

Recibo `installed-313-hashed-001/receipt.json`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### B312

Recibo `installed-312-normal-002/binding-final.log`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### B313

Recibo `installed-313-hashed-001/binding-final.log`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### A312

Recibo `installed-312-normal-002/journeys/summary.json`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### A313

Recibo `installed-313-hashed-001/journeys/summary.json`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### BUILD

Recibo `evidence/affected-checks-002/receipt.json`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### DIST

Recibo `evidence/distribution-content.json`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### DELTA

Recibo `evidence/artifact-delta.json`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### ROLLBACK

Recibo `evidence/rollback-001/receipt.json`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

### ROLES

[test_role_guides.py](../packages/equiframe/tests/test_role_guides.py): archivo exacto sin filtros, 21 PASS por entorno. `test_role_script_preserves_diagnosis_before_gate` contiene 8 casos científicos y 2 de arquitectura, normales y `-O`; `test_architect_pytest_recipe_is_a_real_local_test` agrega el test CI local. La recolección posterior enumera los 21 nodeids y no se cuenta como otra ejecución.

### T-money

- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_native_cross_product_has_independent_keyed_money_expectation`; 18 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-invalid

- [tests/test_assertions.py](../packages/equiframe/tests/test_assertions.py): `test_incomplete_budget_never_passes_as_empty_differences`; 1 observación(es) original(es) PASS
- [tests/test_assertions.py](../packages/equiframe/tests/test_assertions.py): `test_invalid_expected_with_complete_final_counts_still_fails`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-key

- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_composite_key_duplicate_in_later_batch_is_invalid_and_falls_back`; 2 observación(es) original(es) PASS
- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_incomplete_composite_keys_keep_core_bag_fallback`; 2 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-values

- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_decimal_precision_does_not_use_float_or_global_decimal_context`; 1 observación(es) original(es) PASS
- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_pandas_nullable_float_independent_validity_mask`; 1 observación(es) original(es) PASS
- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_schema_only_inference_preserves_types_and_declares_conservative_defaults`; 1 observación(es) original(es) PASS
- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_sequence_equal_sort_keys_do_not_permit_reordering_values`; 2 observación(es) original(es) PASS
- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_time_zone_and_nanosecond_difference_require_explicit_policy`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-contract

- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_inference_uses_expected_schema_only_and_never_infers_keys_from_unique_rows`; 1 observación(es) original(es) PASS
- [tests/test_diff_contracts.py](../packages/equiframe/tests/test_diff_contracts.py): `test_existing_contract_preserves_exact_contract_and_explicit_policy`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-reportinput

- [tests/test_assertions.py](../packages/equiframe/tests/test_assertions.py): `test_different_is_never_accepted_even_when_display_omits_all_witnesses`; 3 observación(es) original(es) PASS
- [tests/test_assertions.py](../packages/equiframe/tests/test_assertions.py): `test_report_mapping_decision_and_other_non_result_inputs_are_rejected`; 5 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-views

- [tests/test_report_rendering.py](../packages/equiframe/tests/test_report_rendering.py): `test_all_views_use_the_same_facts_and_meaningful_type_columns`; 1 observación(es) original(es) PASS
- [tests/test_report_rendering.py](../packages/equiframe/tests/test_report_rendering.py): `test_verdict_does_not_depend_on_complete_alone`; 12 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-counts

- [tests/test_diff.py](../packages/equiframe/tests/test_diff.py): `test_partial_differences_survive_limit_without_becoming_final_counts`; 1 observación(es) original(es) PASS
- [tests/test_report_io.py](../packages/equiframe/tests/test_report_io.py): `test_bag_counts_keep_modified_and_named_row_counts_unknown`; 1 observación(es) original(es) PASS
- [tests/test_report_io.py](../packages/equiframe/tests/test_report_io.py): `test_verified_keyed_counts_are_distinct_rows_and_examples_are_only_display`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-permission

- [tests/test_cli_diagnostics.py](../packages/equiframe/tests/test_cli_diagnostics.py): `test_categories_keep_fixed_hints_and_caller_exit_policy`; 1 observación(es) original(es) PASS
- [tests/test_comparison_decisions.py](../packages/equiframe/tests/test_comparison_decisions.py): `test_cli_unwritable_evidence_exits_3_without_success_json`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-hints

- [tests/test_cli_diagnostics.py](../packages/equiframe/tests/test_cli_diagnostics.py): `test_categories_keep_fixed_hints_and_caller_exit_policy`; 21 observación(es) original(es) PASS
- [tests/test_cli_diagnostics.py](../packages/equiframe/tests/test_cli_diagnostics.py): `test_validation_hint_distinguishes_request_from_stored_evidence`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-no-overwrite

- [tests/test_product_journeys.py](../packages/equiframe/tests/test_product_journeys.py): `test_example_scripts_never_overwrite_existing_evidence`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-six

- [tests/test_migration_semantic_directions.py](../packages/equiframe/tests/test_migration_semantic_directions.py): `test_semantic_native_directions_and_independent_validation_scope`; 18 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-filter

- [tests/test_migration_polars_composition.py](../packages/equiframe/tests/test_migration_polars_composition.py): `test_composed_filter_public_migration_six_directions`; 36 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-preflight

- [tests/test_migration.py](../packages/equiframe/tests/test_migration.py): `test_preflight_checks_both_compilers_before_provider`; 1 observación(es) original(es) PASS
- [tests/test_migration_product_semantics.py](../packages/equiframe/tests/test_migration_product_semantics.py): `test_native_metadata_boundaries_remain_explicit`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-ingest

- [tests/test_ingestion.py](../packages/equiframe/tests/test_ingestion.py): `test_exact_money_ids_sources_and_receipts`; 3 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-quarantine

- [tests/test_ingestion.py](../packages/equiframe/tests/test_ingestion.py): `test_invalid_money_is_quarantined_without_repair`; 5 observación(es) original(es) PASS
- [tests/test_ingestion.py](../packages/equiframe/tests/test_ingestion.py): `test_rejected_schema_bad_json_and_numeric_id_do_not_publish`; 6 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-checkpoint

- [tests/test_destinations.py](../packages/equiframe/tests/test_destinations.py): `test_failed_expected_gate_blocks_publication`; 1 observación(es) original(es) PASS
- [tests/test_workflow.py](../packages/equiframe/tests/test_workflow.py): `test_expected_divergence_blocks_dependent_but_not_independent_stage`; 1 observación(es) original(es) PASS
- [tests/test_workflow.py](../packages/equiframe/tests/test_workflow.py): `test_multiple_checkpoints_capture_once_and_roundtrip`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-idempotent

- [tests/test_destinations.py](../packages/equiframe/tests/test_destinations.py): `test_idempotent_load_versions_create_replace_and_row_counts`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-precommit

- [tests/test_destinations.py](../packages/equiframe/tests/test_destinations.py): `test_failure_halfway_loading_multiple_tables_keeps_previous`; 1 observación(es) original(es) PASS
- [tests/test_destinations.py](../packages/equiframe/tests/test_destinations.py): `test_pointer_write_failure_is_recoverable_without_losing_prior`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### T-snapshot

- [tests/test_sqlite_snapshot_example.py](../packages/equiframe/tests/test_sqlite_snapshot_example.py): `test_consumer_pins_manifest_once_and_subset_keeps_full_identity`; 1 observación(es) original(es) PASS
- [tests/test_sqlite_snapshot_example.py](../packages/equiframe/tests/test_sqlite_snapshot_example.py): `test_existing_consumer_rejects_controlled_transport_or_declaration_mismatch`; 5 observación(es) original(es) PASS
- [tests/test_sqlite_snapshot_example.py](../packages/equiframe/tests/test_sqlite_snapshot_example.py): `test_snapshot_is_detached_pinned_and_preserves_exact_values`; 1 observación(es) original(es) PASS

Recibo original: `a7-validation-new/suites/312-latest-core-full-001/pytest-observations.json`; SHA-256 `2b0b192041492e14153b7d88fda695c4f287d85117ab90721fb19393d7bb5e76`.

### H-absence

Recibo `a7-validation-new/absence/312-latest-core-optionals-001/receipt.json`; selector `target_results`. A7 original reutilizado, no ejecución nueva.

### H-fault

Recibo `consumer019-fault-normal-001/fault-checks.json`; selector `checks`. A7 original reutilizado, no ejecución nueva.

### H-fault-O

Recibo `consumer019-fault-optimized-001/fault-checks.json`; selector `checks`. A7 original reutilizado, no ejecución nueva.

### H-regressions

Recibo `consumer019-regressions/focused-regression-receipt-final.json`; selector `documento completo`. A7 original reutilizado, no ejecución nueva.

### H-lifecycle

Recibo `a7-validation-new/lifecycle/312-latest-001/receipt.json`; selector `documento completo`. A7 original reutilizado, no ejecución nueva.

### H-consumer

Recibo `consumer019-run-normal-001/summary.json`; selector `documento completo`. A7 original reutilizado, no ejecución nueva.

### H-current

Recibo `consumer-checkpoint/CURRENT.json`; selector `documento completo`. A7 original reutilizado, no ejecución nueva.

### H-data

Recibo `consumer-data-20261007/provenance.json`; selector `documento completo`. A7 original reutilizado, no ejecución nueva.

### H-review

Recibo `independent-consumer-contract-review/review-final-endpoints-20261007/FINAL_INDEPENDENT_REVIEW.json`; selector `documento completo`. A7 original reutilizado, no ejecución nueva.

### RENDER

Recibo `evidence/rendered-examples-001.json`; selector `documento completo`. Artefacto/inspección de esta revisión; alcance declarado en el recibo.

