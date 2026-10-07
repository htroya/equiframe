# Revisión de usabilidad verificable de EquiFrame

Fecha: 2026-10-07. Producto privado, Linux x86_64, Python 3.12/3.13;
el alcance completo y las 72 subcomprobaciones están en
[el plan](USABILITY_PLAN.md) y [la matriz](USABILITY_MATRIX.md).

## Resultado

**11 de 12 criterios CUMPLIDOS: 91,67 % del alcance. U12 BLOQUEADO.**
No hay porcentaje de satisfacción, adopción humana medida ni afirmación de
compatibilidad universal. La línea base retrospectiva reconstruida es 7/12 (58,33 %), con
brechas U01/U02/U09/U10 y ausencia de observaciones humanas U12. Se aplicaron
las mismas 72 subcomprobaciones al árbol/recibos originales; no se afirma una
medición humana o un porcentaje registrado antes del trabajo.

Se completó la parte técnica independiente y se preparó el protocolo. El encargo
no está cerrado al 100 %: faltan personas/proyectos/consentimientos reales y
observaciones iniciales/retención. Los tres perfiles ficticios autorizados se
marcan SIMULADO; no aportan resultados humanos ni reemplazan esas dependencias.

## Cambios concretos

- Dos entradas españolas ejecutables: [arquitecto](../packages/equiframe/docs/arquitecto.md)
  y [científico](../packages/equiframe/docs/cientifico.md), con la API existente
- Arquitecto: captura SQL DuckDB, esperado literal, reporte antes del gate,
  pytest local y propiedad explícita de transporte/snapshots/reintentos
- Científico: ID textual, NULL, Decimal y tiempo; variantes de pérdida de fila,
  cambio de clave/valor/ausencia/hora, referencia inválida y presupuesto insuficiente
- Receta actual A7 por pip normal separada del kit 0.11.1 histórico; sin no-deps
  ni homónimo público. Cabeceras actuales de integración/roadmap corregidas
- El recorrido E rechazaba un Scan por faltar Sort final bajo orden significativo;
  su explicación ya no atribuye ese rechazo a todos los timestamps del IR
- Protocolo U12 fija <=300 s antes de observar e incluye roles, ayuda/fallos,
  nuevas personas para revalidar primer uso e integración retenida

No cambian módulos runtime, métodos científicos, formatos, alias, compiladores,
dependencias ni consumidor. La versión privada sigue A7, con nuevos hashes de
artefacto documental. El consumidor 0.1.9 mantiene su pin exacto compatible.

## Identidad del candidato

Commit fuente de las guías/ejemplos:
`3e404de6ba1a31e07a2abb8955ff6262fbd5e363`.
Árbol: `6acb9bd00efe0342d4562e91dc5ddb2a6ea939a3`.
Rama revisable: `product/usability-20261007`.
La revisión/matriz añadidas después no alteran los bytes del paquete construido.

| Artefacto | SHA-256 |
|---|---|
| Wheel documental 0.12.0a7 | `abab950c4bdbaf38056f493ca4efc97148b0d85d8d34322d2725437c9f2b42c9` |
| Sdist documental 0.12.0a7 | `b7de8d869a6a58c0a6ff564eae1d07d4c7f7514431b71188594d44b4732f47ad` |
| Wheel A7 original reutilizado | `5d435e75a79754ab45c8a27f7d30ff513c006034bdddbff170ec9506816b9ff0` |
| Consumidor 0.1.9 sin cambios | `760db03975a15d327406a0baafb84da085bcc9ddc6fff924b04cb11b54635e02` |

No colocar los dos wheels core del mismo nombre en un wheelhouse. Seleccionar
por recibo, commit y hash, no solamente por versión. El benchmark permanece
sin cambios con su evidencia A7 original; no se construye ni se acredita otro.

## Evidencia sanitizada

El manifiesto externo vincula cada criterio/subcriterio con entrada, esperado,
observado, entorno, comando, commit, artefactos y hashes. No se incluyen datos
reales, identidades, modelos, consentimientos ni logs privados en Git.

| ID | Evidencia comprobada y alcance |
|---|---|
| E01 | Ruff, formato, mypy y assets con salida 0; 62 pruebas afectadas del código/documentación; build de sdist y wheel desde ese sdist; Twine estricto. No se repitió la suite semántica completa sin cambio runtime |
| E02 | Wheel final: instalación normal pip en CPython 3.12.14 y completa con hashes en CPython 3.13.5; pip check, CLI e imports site-packages; 119 miembros del paquete vinculados antes/después; 21 tests de guías + 31 escenarios A–H por entorno. Son pruebas técnicas, no humanas |
| E03 | 460 archivos tracked del paquete iguales en sdist, 28 guías iguales en wheel, ejemplos incluidos y 74 módulos runtime idénticos al original; metadatos de dependencias sin cambio |
| E04 | 123 recibos existentes verificados por hash: instalaciones/perfiles, suites, lifecycle, ausencias, sdist/canales y nueve matrices del consumidor. Se conservan estados/intentonas anteriores sin convertirlos en pases nuevos |
| E05 | Observaciones instaladas originales de los paths funcionales pertinentes: comparación/aserción, reportes, CLI/errores, seis direcciones e ingestión/workflow. Se identifican nodeids y salidas originales en el manifiesto; no se ejecutó una nueva auditoría de opciones/modelos |
| E06 | Pruebas acotadas originales del consumidor sobre su propia evidencia: rechazo, presupuesto, corrupción de reporte y fallo de escritura precommit; once regresiones de aplicación normales y -O, incluidos recibos posteriores al commit. Idempotencia Parquet tiene su observación exacta preservada |
| E07 | Consumidor 0.1.9: cuatro programas, tres fuentes públicas permitidas, 219 filas efectivas, 72 casos distintos; 576 ejecuciones principales (192 aceptadas, 384 rechazos esperados), 1152 tablas nativas verificadas frente a stdlib. Repetición relocalizada 72 adicional. Todo corresponde al A7 original, compatible por identidad runtime, no a nuevos runs del wheel documental |
| E08 | Cuatro lifecycle originales: actualización, lectura histórica, desinstalación y reinstalación. Nuevo ensayo acotado de reversión seleccionando el entorno A7 original identificado: equivalente acepta, diferencia y límite rechazan; no se reescriben formatos ni se vuelve a una versión conocida defectuosa |
| E10 | Mapa preciso de 72 subcomprobaciones: 163 nodeids originales, recibos/selección por caso y comprobación de 40 reportes sintéticos existentes en tres vistas; línea base reconstruida con el árbol original. Los 21 casos por entorno tienen archivo exacto y pase completo sin filtros; no se inventan logs individuales |
| E09 | Protocolo escrito y tres perfiles ficticios; cero observaciones humanas, consentimientos otorgados o integraciones reales retenidas en esta revisión. U12 permanece abierto |

Las 8 suites normales y 52 perfiles originales siguen vinculados al wheel A7
original. No son pases de nuevos bytes por compartir número de versión. La
revisión justifica reutilizar comportamiento inalterado y prueba de nuevo las
rutas/instalaciones afectadas. No se anuncian todas las combinaciones de cada
rango de dependencia, Windows, macOS, ARM64 o GitHub Actions como ejecutadas.

## Fallos preservados y recuperación

- Primer control de formato: dos bloques Python de las guías necesitaban formato.
  Se corrigieron y el nuevo bloque afectado pasó; se retiene el primer log
- Primer arnés de instalación: uv intentó su caché predeterminada en home de solo
  lectura. Se corrigió la ubicación de trabajo y se usó una carpeta nueva;
  no fue defecto del producto ni se ocultó como instalación exitosa
- Los fallos históricos conservados en los recibos A7 no se borran ni se recuentan
  como incidentes nuevos. No hay regresión impeditiva observada en el alcance

La comprobación de permisos utiliza PermissionError controlado y destino ocupado,
con diagnóstico y no sobrescritura; no acredita una matriz nueva de ACL del SO.

Antes del commit de Parquet, un fallo conserva el puntero previo. Después del
commit puede haber datos publicados y aplicación/recibo incompleto; se consulta
el estado real antes de reintentar y no se declara rollback ficticio. Retener
una vista minimizada tampoco borra la evidencia original.

## Qué falta y quién decide

Hernán necesita coordinar tres proyectos reales independientes (refactor Python,
SQL/DuckDB, CI), al menos una persona de arquitectura y otra de ciencia, permisos
y revisión humana de independencia. Se conserva ayuda, fallos, interpretación,
utilidad y reloj de primer uso <=300 s, además de un cambio posterior real con
integración retenida. No se sustituyen por perfiles ficticios o pruebas automáticas.

Las decisiones de responsables/respaldos/canales de mantenimiento, licencia,
publicación y soporte quedan bajo el titular. No hay SLA aprobado. José conserva
servicio/transporte/cuotas; Jhair conserva modelo/carga del DW. Sus entregas reales
no se dan por realizadas. La revisión de seguridad integral sigue incompleta y
separada; esta tarea no la retomó. Ningún resultado técnico autoriza PyPI/TestPyPI,
cuentas, despliegues, Actions ni conclusiones científicas.

Main se integra solamente al final con el cambio validado, según la instrucción
posterior de Hernán. La evidencia y la revisión de la rama preceden a esa acción.
