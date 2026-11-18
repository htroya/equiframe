# Calidad, pruebas y operación

Evaluación manual 2026-10-10 del par privado `0.12.0a13`:
[16/20 controles = 80 % en la rúbrica propia inspirada en Real Python](PACKAGE_QUALITY_RESULT_20261010.md).
El [resultado estructurado](PACKAGE_QUALITY_RESULT_20261010.json) identifica wheels,
sdists, entornos Windows/Python 3.12.4 y Linux ARM64/Python 3.10.12, suites completas,
omisiones y fallos conservados. La publicación pública, adopción externa, comunidad
y licencia siguen pendientes. No se ejecutó Actions ni se crearon recursos de pago.

Requisitos de desarrollo y verificación. Corte histórico 2026-10-03: CI manual `workflow_dispatch`, matriz de plataformas opcional y candidato 0.11.0 validado localmente en Windows x64/Python 3.12.4. No se ejecutaron jobs remotos nuevos ni se cambió cuota/facturación. Los pasos 1 y 2 incorporaron pruebas de contratos, serialización, propiedades, tiempo y CLI; sus descripciones de CI abajo son históricas. [Comandos del paquete](../packages/equiframe/README.md). Las áreas de pasos posteriores de la matriz siguen siendo requisitos pendientes, no controles ya implementados.

## 1. Contrato de entrega por incremento

Un incremento está terminado cuando cumple su alcance funcional, pruebas de comportamiento, tipado, estilo, documentación ejecutable y empaquetado correspondiente. Las pruebas deben detectar fallos relevantes, no reproducir línea por línea la implementación. Cobertura numérica por sí sola no prueba corrección.

El paso 1 crea CI con permisos mínimos (`contents: read`), dependencias fijadas y acciones verificadas/pinadas. La CI usa Python 3.12. La matriz configurada manualmente incluye Windows x64, Ubuntu x64/ARM64 y macOS Intel/Apple Silicon; la evidencia de cada entrega distingue configuración y checks completados. Los controles de paquete opcional prueban también la importación sin motores o ML instalados.

## 2. Matriz de pruebas requerida

| Área | Evidencia mínima |
|---|---|
| Contratos | Campos/versiones desconocidos, claves inexistentes, tipos/coerciones, precisión/escala, políticas de orden/nulos/tiempo |
| Serialización | Roundtrip de decimal, fecha/instante, estados, valores especiales y hashes deterministas |
| Adaptadores | Código nativo en cada motor, salida materializada, captura de esquema antes de conversión, cierre tras excepción |
| Comparación | Multiconjunto, orden condicionado, IDs con ceros, montos intercambiados, nulos/NaN/vacío/cero, límite temporal, tolerancia explícita |
| Recursos | Spill, memoria/tiempo insuficientes, cancelación y comparaciones incompletas sin falso equivalente |
| R | No acceso a O/otro motor, aplicabilidad, fallos individuales, conjunto vacío y agregación |
| Perfiles | Denominadores, vacíos, no aplicabilidad, claves incompletas y features excluidas |
| Modelos | Ajuste/calibración separados, cuantiles sin interpolar, signo IF, MAD=0/infinito, restauración y compatibilidad |
| H | Todas las combinaciones de disponibilidad y alerta, incluidas decisiones parciales |
| Benchmark | Mutante sin efecto, revisión pendiente, autor no revisor, grupos transitivos, ausencia de fuga |
| Métricas | Matrices conocidas, denominador cero, una clase, soportes distintos, remuestreo de grupos |
| Evidencia | Artefactos íntegros, errores parciales, repetición sin sobrescritura, escape HTML y ausencia de secretos |
| Integración | Snapshot fijo, hash alterado, timeout/estado de trabajo y consumidor compatible con servicio/DW |

Fixtures pequeños sintéticos versionados en Git. Datos reales y modelos se descargan explícitamente desde referencias confiables y no se requieren para pruebas unitarias. Separar pruebas unitarias, por propiedades, entre motores e integración remota; las últimas no corren en PR sin entorno autorizado.

## 3. Pruebas de propiedades y metamórficas

Ejemplos: permutar filas conserva resultado cuando orden no importa; duplicar fila incrementa multiplicidad y debe detectarse; alterar monto bajo clave única cambia comparación aunque total global coincida; serializar/restaurar un contrato conserva significado y hash canónico; cambiar una feature/version invalida bundle incompatible.

Las precondiciones se verifican. No se permite que el mismo algoritmo de normalización genere simultáneamente el esperado y su verificación sin un control independiente. Las semillas se guardan; un fallo reducido se incorpora como regresión sintética.

## 4. Seguridad y confianza

Callbacks y plugins son código confiable del proyecto/usuario. La biblioteca no ejecuta código arbitrario contenido en contratos ni se anuncia como sandbox. SQL parametriza valores; identificadores se validan contra metadatos permitidos. Acceso remoto, autorización y cuotas corresponden a José.

No cargar pickle/joblib no confiables. Persistencia de modelos con formato/tipos explícitos y versiones bloqueadas; documentar compatibilidad real. Logs y reportes omiten secretos y URLs firmadas; HTML escapa valores. Ejemplos usan identificadores sintéticos. Tokens nunca van en Git, remotes o notebooks compartidos.

Una integridad SHA-256 válida no autoriza redistribución ni ejecución. Datos SERCOP conservan atribución y condiciones de fuente. La licencia de software y publicación externa siguen pendientes de los autores.

## 5. Recursos y medición

Límites configurables de memoria, hilos, tiempo, tamaño de lotes, disco y detalle de diferencias. Evitar materializar simultáneamente todas las entradas/salidas de tres motores. Liberar recursos entre ejecuciones; registrar materialización lazy, caché y concurrencia interna.

En VM de 12 GB, José impone presupuesto total y colas; Hernán declara necesidades por tarea y registra configuración efectiva. No fijar automáticamente un presupuesto que multiplique la RAM disponible por usuario.

Benchmark en procesos controlados, calentamiento y repeticiones alternadas; trabajo remoto de transporte medido aparte. Si no se puede aislar memoria/costo de un componente, el reporte indica el alcance real. No afirmar SLO, escala o latencia antes de medir.

## 6. Versiones y releases

Cada paquete tiene versión y changelog. Esquemas y contratos tienen revisión propia. Migraciones incompatibles se rechazan explícitamente o se hacen con una herramienta documentada y evidencia. El entorno experimental se fija con lockfiles, hashes y versiones efectivas.

Paso 10 entrega wheel/sdist probado desde instalación limpia, documentación API, ejemplos ejecutables, manifiesto reproducible y notas de límites. Etiquetar release interno verificable. Publicación en PyPI o despliegue fuera del alcance requiere decisión expresa y licencia acordada.

## 7. Colaboración reproducible

Cada integrante trabaja en su clon y rama. Los datos compartidos se identifican por snapshot, no por una ruta mutable. La rama principal recibe PR revisables. Las convenciones de revisión no se presentan como protecciones técnicas si GitHub no las tiene configuradas.


## 8. Controles del paso 2

CI Python 3.12 en Windows x64, Ubuntu x64/ARM64 y macOS x64/ARM64 ejecuta la suite anterior y
regresiones de motores instalados, sin reemplazarlos por mocks ni saltarlos. La
instalación de desarrollo usa `uv sync --locked --all-extras`; comandos `uv run`
conservan ese perfil. La configuración histórica de ese paso tuvo triggers push/pull_request. La
actual usa sólo workflow_dispatch y gate explícito; ninguna rama/PR activa hoy
esa matriz automáticamente.

El verificador instala el wheel en entornos runtime-only fuera del checkout: base,
arrow, pandas, polars, duckdb y engines, con versiones del lock. Comprueba extras
reales, import ligero, API/CLI, ejemplos externos, consumidor mypy y toda la suite
contra wheel reconstruido desde sdist, además de identidad de todos sus bytes.
Las regresiones instrumentan conexiones DuckDB reales para demostrar cierre; las
pruebas de recursos registran el alcance cooperativo y límites nativos efectivos.

Evidencia/versiones/cantidades/checks: [revisión vigente](STEP_02_SECOND_REVIEW.md);
el informe 0.2.0 se conserva como histórico. Ningún resultado sintético acredita
el benchmark o el DW. Pruebas ARM64 en GitHub no acreditan integración OCI.


La revisión 0.2.1 exige preservación de anchos/signo, máscara NULL/NaN, índices
copiados, límites temporales exactos y rechazo de categorías/decimales no fieles.
Las regresiones usan los tres motores reales, instrumentación de conexiones
reales y fallos de almacén para verificar evidencia parcial y limpieza.

Cada runner GitHub es temporal: el workflow construye y verifica el paquete,
sin acceso a datos reales, claves OCI ni despliegue. El entorno OCI se valida
por separado conforme a [su contrato de integración](OCI_INTEGRATION.md).

## 9. Controles del paso 3

Comparaciones con esperados independientes y propiedades de las cinco familias;
emparejamiento aproximado contrastado con permutaciones exhaustivas pequeñas;
colisiones forzadas de partición, spill, sesgo, presupuestos, evidencia truncada
solo en el resumen, alteraciones de artefactos, índices y tres motores reales.
Los ejemplos instalados verifican comparación sin motores con el extra Arrow y
con cada motor individual. Wheel base expone modelos/API sin importar motores.
Los esquemas previos conservan bytes; se añaden cuatro esquemas independientes.

La evidencia anterior del usuario fue **462 passed y un fallo** en la prueba de
timeout de callback; su repetición aislada pasó. La CI del commit base
`751063580fda5c072e693f0c51e4c80bb677ee96` pasó en cinco plataformas, según el
contexto de entrega. Son evidencias distintas. El paso 3 sustituye el reloj real
de aquella prueba por uno controlado y añade vencimiento previo al callback.
Resultados del nuevo commit: [informe](STEP_03_REVIEW.md); la configuración de CI
por sí sola no demuestra que sus checks hayan pasado.

## 10. Controles del paso 6

El paquete experimental tiene su propio lock, tipado estricto, Ruff, esquemas y
suite. Comprueba esperados independientes en cinco familias, tres motores reales,
mutaciones sin efecto, conservación de suma con divergencia, paquetes ciegos,
conflictos y cronología de revisión, fallos, integridad, JSON estricto,
publicación concurrente exclusiva, grupos transitivos, propiedades de ausencia
de fuga y rechazo de calibración/prueba en entrenamiento.

La configuración de aquel paso previó ambos paquetes en cinco plataformas;
la configuración actual manual no acredita ejecución de esa matriz del candidato. La verificación
de distribución instala wheels por nombre con pip en otro directorio,
comprueba imports ligeros y rutas instaladas, ejecuta las pruebas/piloto contra
el wheel y reconstruye el mismo wheel desde sdist. Identidades de tests son
ficticias; sus decisiones nunca cuentan como revisiones de la tesis.
Resultados ejecutados y límites: [informe del paso 6](STEP_06_REVIEW.md).

## 11. Controles del paso 7

Scores de árboles exportados contrastados contra sklearn con varias submuestras
y filas repetidas; MAD contrastado contra valores manuales. Propiedades del rango
racional exacto, empates, indicadores, MAD cero/infinito, falta de soporte,
calibración insuficiente, versiones/familias incompatibles y H en nueve estados.
Persistencia exacta, integridad, árboles inválidos, JSON duplicado y ML ausente.
El benchmark prueba selección de calibración contra artefactos nativos, rechazo
de pendientes/prueba, fuga de grupos/capturas y cantidades de soporte.

El verificador de distribución añade `ml`: entrena en entorno con ese extra,
restaura y puntúa desde la instalación base sin sklearn/NumPy. Conserva ejemplos
de cada motor, tipado externo y wheel reconstruido desde sdist. GitHub ejecuta
ambos paquetes en cinco plataformas. [Resultados efectivos](STEP_07_REVIEW.md).

## 12. Controles del paso 8

Integración nativa única, ausencia de reajuste en inferencia, decisiones parciales,
comparación independiente ante fallo de perfil/modelo, cancelación, relanzamiento
y concurrencia. Evidencia: hashes, cadena de eventos, procedencia, rutas relativas,
reportes coherentes, JSON estricto, escape HTML y ausencia de datos/secretos del
entorno en reportes/logs. Reductor: precondiciones entre tablas, decimales,
multiplicidad, firma incorrecta, fallo/no determinismo del predicado, presupuesto
exacto, tiempo cooperativo y mínimo local sin afirmación global.

La distribución comprueba import base sin motores/ML, ejemplo del runner/reductor
instalado fuera del checkout y reconstrucción idéntica desde sdist. El benchmark
prueba CLI validate/split/pilot y el mismo piloto nativo, conservando sus revisiones
pendientes. [Resultados ejecutados](STEP_08_REVIEW.md).

## 13. Controles del paso 9

Snapshots fijados, manifiestos completos con selección parcial, transporte fallido,
hashes/tamaños/tipos/filas incompatibles, cancelación y límites cooperativos.
Las tres corridas nativas preservan sus entradas y comparaciones independientes;
el esperado queda capturado una vez. El lector comprueba el inventario y la
coherencia de los resultados hijos sin reconectar al servicio. La conciliación
verifica importes decimales exactos, NULL, duplicados, monedas y puentes sin
deduplicación ni conversión monetaria implícita.

La distribución instala el ejemplo de integración fuera del checkout y verifica
las suites contra el wheel reconstruido desde sdist. Fixtures e identidades de
prueba no son datos SERCOP ni revisiones académicas. El cierre real depende de
entregables externos identificados en el [informe](STEP_09_REVIEW.md).

## Controles actuales Verify/ETL y distribución

La [revisión actual](VERIFY_ETL_REVIEW_20261003.md) separa baseline del commit
`bb0b3aa`, suites nuevas, regresiones posteriores y pruebas instaladas. La
[matriz semántica](SEMANTIC_SUPPORT.md) enlaza casos a test nodes existentes,
sin extrapolar un producto cartesiano. Los tests de fallo de carga, gate alterado,
fuente/checkpoint sustituido y comparaciones forjadas protegen contra éxito falso.

El job manual de calidad reserva 90 minutos para comprobar los dos paquetes,
incluidas las suites de fuente y las suites instaladas desde sdist. Las suites
locales completas de fuente tardaron aproximadamente once y doce minutos por
paquete; el límite anterior de 35 minutos dejaba escaso margen para las cuatro
suites, instalaciones y ejemplos secuenciales. El nuevo límite conserva la
activación explícita; no ejecuta jobs ni acredita tiempos en runners remotos.

Twine `check --strict` valida metadatos del wheel/sdist; no certifica licencia ni
publicación. El [manifest de release](RELEASE_CANDIDATE.md) identifica bytes,
commit y recibos de comandos. La automatización de publicación está preparada
fuera de `workflows/`, requiere decisiones resueltas y jamás se invocó aquí.
