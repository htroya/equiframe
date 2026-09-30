# Calidad, pruebas y operación

Requisitos de desarrollo y verificación. Los pasos 1 y 2 incorporan pruebas reales de contratos, serialización, propiedades, tiempo y CLI; tipado/estilo, build e instalación limpia se ejecutan también en CI. [Comandos del paquete](../packages/equiframe/README.md). Las áreas de pasos posteriores de la matriz siguen siendo requisitos pendientes, no controles ya implementados.

## 1. Contrato de entrega por incremento

Un incremento está terminado cuando cumple su alcance funcional, pruebas de comportamiento, tipado, estilo, documentación ejecutable y empaquetado correspondiente. Las pruebas deben detectar fallos relevantes, no reproducir línea por línea la implementación. Cobertura numérica por sí sola no prueba corrección.

El paso 1 crea CI con permisos mínimos (`contents: read`), dependencias fijadas y acciones verificadas/pinadas. La CI usa Python 3.12. La matriz actual incluye Windows x64, Ubuntu x64/ARM64 y macOS Intel/Apple Silicon; la evidencia de cada entrega distingue configuración y checks completados. Los controles de paquete opcional prueban también la importación sin motores o ML instalados.

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
conservan ese perfil. La matriz tiene triggers de push y pull_request para
todas las ramas, incluidos colaboradores y PR dependientes.

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
