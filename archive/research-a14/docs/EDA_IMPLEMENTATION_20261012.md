# EDA opcional implementado: Alpha privada A14

La entrega Alpha anterior quedó publicada y comprobada en `main`, commit
`cfd65b90e749053f68aaf7d1c2b1d1f508e2db8e`. Después se ejecutó el encargo
adjunto de EDA. Núcleo y benchmark pasan juntos a **0.12.0a14**, todavía Alpha
privada. No existe Beta ni publicación PyPI/TestPyPI. El
[recibo técnico](EDA_IMPLEMENTATION_RESULT_20261012.json) identifica artefactos,
fuentes, comprobaciones, intentos fallidos y límites. No transfiere las
[mediciones A13/A11](PROJECT_STATUS_MATRIX_20261011_EIGHT.md) al candidato nuevo.

## Implementación y uso

`equiframe.eda` es un subpaquete de la distribución existente, con API tipada
y CLI que usan la misma implementación: `analyze`, `analyze_artifact`,
`analyze_migration`, `read_result`; comandos `equiframe eda run`, `migration` e
`inspect`, también disponibles mediante `equiframe-eda`. DuckDB/Arrow y Plotly
se cargan sólo cuando se solicitan; los extras son `eda` y `eda-charts`.
La instalación básica se comprobó realmente sin DuckDB, Arrow, Plotly, pandas
ni Polars. El [manual](../packages/equiframe/docs/eda.md) explica contratos,
presupuestos, códigos de salida y representaciones admitidas.

Hay cuatro esquemas `1.0` nuevos y un inventario explícito de API/CLI/modelos.
El registro conserva las interfaces anteriores y distingue el namespace
experimental EDA. Sólo las dos schemas experimentales del productor de
detectores cambian para admitir A14; los formatos estables y fixtures
históricos no se reescribieron. R/M/B/H/O y el transporte del núcleo conservan
su función. No se entrenan detectores, generan etiquetas ni eliminan filas.

El backend calcula calidad, frecuencias, cardinalidad, duplicados completos
y por claves declaradas, conversiones explícitas y estadísticas de grupos
comparables. Conserva texto/identificadores, NULL/NaN/vacío/cero y valores
originales. Dinero usa Decimal y moneda separada; sumas/cuantiles discretos
son exactos. Medias flotantes, desviaciones e histogramas/gráficos declaran
aproximación. IQR/MAD proponen casos para investigar; pocos datos, dispersión
cero, moneda ausente y tipos/límites no representables quedan no evaluables.
Los ejemplos y gráficos de dispersión/caja son acotados y declaran su muestra.

Cada run usa copia fija privada, DuckDB propio en memoria y un directorio
nuevo exclusivo. `summary.json`, `findings.json`, `report.html`, configuración,
snapshot y eventual `typed.parquet` tienen inventario/hashes; el manifiesto
final actúa como marcador de finalización. El lector verifica inventario
cerrado y vínculos. Una migración/captura verificada se revalida antes de
finalizar EDA; el diagnóstico nunca sustituye comparación completa ni Verify.

El código y las pruebas pertenecen al commit
`57850aac819ab45a90ce69284f7e200ca0d9c332`. Las distribuciones definitivas se
reconstruyeron con bytes Git exactos: 629 miembros fuente comprobados, incluida
la procedencia del `.gitignore` ancestral. La alineación sólo cambió saltos
de línea de la licencia vendorizada y metadatos de ignorados en las sdists;
los textos de licencia y ambos wheels instalados permanecen idénticos.
El [manifiesto A14](../tools/pypi_candidate_a14.json) es independiente del
A13. La auditoría offline de sus cuatro artefactos pasó con publicación
deshabilitada; no acredita derechos, cuentas, ensayo público ni una nueva
puntuación completa de preparación PyPI. Los controles de entrega finalizaron
el 13 de octubre de 2026, después del inicio de este trabajo el día 12.

## Validación comprobada

| Alcance | Windows Python 3.12.4 | Linux ARM64 Python 3.12.15 |
|---|---:|---:|
| Núcleo, unión de IDs de suite completa y deltas pertinentes | 8.103 PASS / 25 SKIP | 8.128 PASS |
| Benchmark, unión de suite completa y reparación de laboratorio | 620 PASS / 7 SKIP | 622 PASS / 5 SKIP |
| Delta final instalado: EDA, productor, compatibilidad y estados | 157 PASS | 157 PASS |
| EDA y estados de resultado con Python `-O` | 86 PASS | 86 PASS |

Estas uniones **no son una ejecución monolítica nueva del wheel final**:
conservan los intentos completos anteriores y reemplazan sólo el resultado de
los mismos IDs reevaluados. El núcleo ARM ejecutó inicialmente 8.124 casos
completos; el delta añade y verifica los cuatro IDs nuevos y las correcciones
EDA. Windows conserva dos expectativas de versión obsoletas del primer
intento y su corrección posterior. No se cuentan repeticiones como IDs nuevos
ni como obligaciones adicionales del catálogo original de trazabilidad.

El primer laboratorio del benchmark omitió su extra declarado `resources`.
Se conservan sus fallos y omisiones y se reevaluaron los cuatro módulos
afectados, 135 IDs, con `psutil==7.2.2` fijado por hashes. No se modificó el
benchmark para aceptar falta de medición. Las omisiones restantes corresponden
a capacidades del sistema operativo. Los errores iniciales de selección de
tests, probe básico y frontend de reconstrucción se conservan y no acreditan
éxito. Los dos fallos de precisión/alias hallados en revisión IA se
reprodujeron y corrigieron con regresiones; «mi dot» sigue siendo un agente IA.

Los cuatro wheel/sdist pasaron Twine, `pip check` y cotejo instalado contra
cada miembro del wheel fuera del checkout. El wheel final reconstruido desde
su sdist tiene SHA-256 idéntico. Mypy pasó 106 fuentes del núcleo y 37 del
benchmark; Ruff pasó. Las pruebas del repositorio dieron 197 PASS / 9 SKIP;
la mejora del verificador documental pasó sus 17 pruebas. Sus recibos privados
preservan los comandos y hashes. Las suites/guías de A13 siguen siendo A13.

Opera Neon MCP usó el perfil dedicado, loopback 9222, zoom inicial 75 % y una
sola pestaña propia. El informe genérico final muestra siete gráficos con
datos, sin desbordamiento horizontal ni recursos HTTP externos; se comprobó
interacción y restauración del eje. El informe de adjudicaciones muestra 21
gráficos y el estado no evaluable. La captura genérica inicial se revisó en
línea; una captura posterior no respondió. No se acredita QA visual completa
del informe final ni se abrió otro navegador.

## Recorrido real, exclusivamente privado

Se recorrieron las **ocho tablas anuales**, 962.228 filas entre tablas
distintas, sin sumar los meses solapados. Se mantiene el manifiesto original
`712022f8470428f25fa12b307e301ad6ef6fb0f9c59634ab8b90569380ac279c`, sus
287 archivos y la captura retrospectiva del selector SERCOP 2025. Las
190.619 releases y 183.891 adjudicaciones son filas de esas tablas, no un
conteo de procesos únicos ni una cohorte científica aprobada.

Ambos hosts conservaron los mismos conteos, conversiones, fechas observadas y
estados de las reglas solicitadas: cuatro tablas completas y cuatro con
métricas monetarias no evaluables por moneda ausente. Los resultados
disponibles permanecen separados. La concordancia de esos campos agregados
no acredita igualdad de contenido ni corrección independiente; los IDs de
run, tiempos, rutas y hashes de informes son propios de cada ejecución.
Jhair debe aprobar grano, historia OCDS, cohorte, escala/monedas y significado
de fechas; José conserva la propiedad del servicio y coordinación de su DW.

- Windows: `eda_a14_20261012/sercop-installed-final`, fuera del repositorio Git.
- VM: `/home/hernan/equiframe-eda-runs/alpha-a14-20261013-final-v3/`.
- Instalación VM: `/home/hernan/equiframe-alpha-a14-20261013-v1/runtime/bin/python`.
- Artefactos finales VM: `/home/hernan/equiframe-alpha-a14-20261013-final-v3/`.

El consumidor reproducible está en [tools/sercop_eda.py](../tools/sercop_eda.py)
y sus [reglas externas](../tools/eda-sercop-configs.json). Los informes HTML,
JSON completos, snapshots y salidas derivadas quedan privados fuera de Git.
**No se cambió el Word, la carpeta pública, permisos, servicio, túnel ni URL**;
no se agregó reflexión. La [entrega de la tutora](SERCOP_PUBLIC_DELIVERY_20261012.md)
sigue ofreciendo sólo dataset y procedencia.

## Disco, custodia y pendientes

Se liberaron 9.421.471.744 bytes de dos laboratorios M13 ya respaldados y
683.454.464 bytes adicionales de temporales propios A14. Tras instalar A14 y
conservar evidencias, la VM tenía 32.404.795.392 bytes libres. Se conservaron
runtime vigente, todos los artefactos/intentos, logs/JUnit, datos y servicios.
El expediente VM devuelto tiene 343 miembros, 261.416.580 bytes y SHA-256
`6c6bc079bd2599707b664aba149bff611f7a2118e8ce3d032abad8dbd65e4066`;
cada miembro pasó SHA/CRC y se comprobó inventario cerrado.

Siguen pendientes otras plataformas/Python/perfiles nativos, reevaluación
completa de las ocho rúbricas sobre A14, obligaciones originales de
trazabilidad, aceptación humana/derechos, ciencia y DW/gateway del equipo.
Los [24 entregables humanos y de PyPI](HUMAN_REQUIREMENTS_20261012.md) y el
[plan Alpha](ALPHA_MAXIMIZATION_PLAN_20261012.md) conservan sus criterios.
La Beta continúa aplazada; el sufijo A14 no acredita Alpha al 100 %.
