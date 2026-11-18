# Correcciones de la revisión independiente A14

La revisión entregada por el propietario analiza el corte
`44aa0bde496338bab8c09b8f86df620f8158cf65`. Su texto original se conserva fuera
de Git con SHA-256 `c02faba94d0970a86548526442ba7d3b48b935d819abf91ac0f0246b7ee9770f`.
El ZIP de resultados mencionado por el revisor no está adjunto; esta ejecución
no presume haber leído su matriz completa, scripts o XML. Las reproducciones
descritas permiten corregir y comprobar los problemas de código.

| Hallazgo | Corrección implementada | Comprobación y límite |
|---|---|---|
| A14-001, precisión monetaria | Escala Polars calculada sobre todos los montos, `Decimal(38, escala)` explícito y comprobación de conservación | Importes de seis decimales en posiciones 0, 99, 100 y 101; capacidades excedidas y cero negativo se rechazan |
| A14-002, EDA en Linux | UTC se configura y verifica después de `connect`; descargas implícitas de extensiones deshabilitadas | 52 pruebas EDA en fuente Windows y Linux ARM64; cierre de conexión ante fallo de zona. El Linux x64 del revisor requiere su repetición propia |
| A14-003, datos inventados en DW | Ausencias NULL, moneda suministrada, fechas independientes y dinero exacto | Fechas inválidas y precisiones incompatibles se rechazan; no se aprueba una proyección temporal ni un nuevo DDL |
| A14-004, asociaciones descartadas | Extractor conserva la lista completa de proveedores; DW v1 rechaza múltiples proveedores/items antes de escribir | Un award con dos proveedores conserva dos asociaciones sin repetir el monto; queda pendiente el puente de dominio aprobado |
| A14-005, lote parcial | Snapshot, dimensiones y hechos dentro de una transacción | Fallo inducido después de la primera inserción revierte todo el lote y conserva el snapshot anterior |
| A14-006, recepción indefinida | Un segundo máximo sin bloque y cinco segundos totales; `/health` no recibe cuerpo ni usa cupos de negocio | Cuatro cuerpos incompletos liberan cupos; un cuerpo por bloques tampoco prolonga el plazo total |
| A14-007, cuota global agotable | Cuotas separadas para operación, lectura y peticiones anónimas; salud independiente | 120 intentos sin credenciales no bloquean operadores/lectores; agotar operación no bloquea lectura ni salud |
| A14-008, symlink de venv | El driver conserva la ruta absoluta del intérprete sin resolver su enlace | Registra executable/prefix/base_prefix; la ejecución con venv POSIX queda sujeta al recibo específico |
| A14-009, mypy Linux | Protocols privados para capacidades POSIX guardadas, sin los seis ignores inválidos | Configuración completa: núcleo 106 archivos y benchmark 37, Windows y Linux ARM64 |
| A14-010, cifra del README | 6.201/8.438 con 2.237 pendientes; dato A13 identificado como histórico | La revisión independiente reproduce el numerador; EDA adicional y monorepo completo no se acreditan con ese denominador |

La sospecha adicional sobre junctions de Windows se reprodujo con un enlace real
entre dos carpetas del laboratorio privado: `lstat` devolvía modo de directorio
y atributo reparse 0x400, y el lector anterior lo aceptaba. `_report_io` ahora
rechaza puntos reparse en archivos y ancestros. Dos regresiones con junctions
reales pasaron en Windows; no se consideran pruebas POSIX ejecutadas.

## Evidencia privada nueva

En `a14_review_fixes_20261013/source-regressions-v2.xml`, 292 pruebas pasaron,
ocho se omitieron y una falló porque Windows no puede recrear el proceso principal
desde `<stdin>`. `spawn-regression-v1.xml` repite únicamente esa prueba desde un
archivo y pasa. Se mantienen el fallo y su causa; no se alteraron las garantías
de bloqueo para conseguir el resultado. En conjunto son 293 casos distintos
aprobados y ocho omisiones: EDA 52, lector de reportes 77, DW 24, preparación
del expediente 29 y cliente/gateway 111.

El archivo de fuente remitido al laboratorio Linux contiene 1.006 archivos,
3.802.347 bytes, SHA-256
`eb2d82057f93f1c7cf4e75b0d7c3e4a2d664f4d8d85c417b0280168368f7ac80`.
Su manifiesto identifica cada archivo. Linux ARM64, Python 3.12.15 y DuckDB 1.5.6
aprobaron 185 pruebas de EDA, reportes, DW y extracción; se omitieron sólo los dos
junctions de Windows. La fuente se prueba sobre un entorno anterior reutilizado
sin modificarlo. Esto no acredita un wheel nuevo instalado ni una instalación limpia.
La suite completa del benchmark y los artefactos nuevos tienen recibos separados.
La primera suite del benchmark en este entorno mezcló fuente nueva en el padre
con el artefacto anterior en los procesos hijos: 617 aprobadas, dos omisiones,
un fallo y siete errores `worker_producer_environment_mismatch`. Se conserva ese
recibo y se prepara una instalación privada coherente para repetirla; el control
de identidad no se desactiva. Posteriormente se añadieron cuatro pruebas de límite
del paquete piloto, aprobadas, y una regresión que exige conservar los atributos
históricos de dimensiones en lugar de sobrescribir snapshots anteriores.

Los XML históricos del [corte anterior](A14_REVALIDATION_CHECKPOINT_20261013.md)
y el kit entregado al revisor se conservan. Sus miles de pruebas y trazabilidad
no se transfieren automáticamente a archivos reconstruidos con estos cambios.

## Meta y pendientes

El [reparto 90 técnico + 10 manual](A14_TECHNICAL_90_METHOD_20261013.md) mantiene
los criterios y esperados originales. La matriz ponderada A14 completa continúa
pendiente. Faltan obligaciones técnicas, inventario EDA, evaluación científica
final y aceptación de dominio, además de las decisiones humanas de publicación.
La [preparación de SERCOP](A14_SERCOP_EXPERIMENT_PREPARATION_20261013.md) ya tiene
ejecuciones y fichas ciegas verificadas; no contiene etiquetas humanas aprobadas.

Alpha privada A14 continúa. No se utilizó Codex Security, no se abrieron agentes,
no se publicó en PyPI/TestPyPI y no se modificó el Word.
