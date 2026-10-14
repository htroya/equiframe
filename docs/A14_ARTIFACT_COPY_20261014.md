# A14: copia segura de artefactos locales

Continúa la meta de 90 % técnico por rubro, con diez puntos manuales separados.
Este cambio corrige un bloqueo reproducido y un límite de lectura tardío.
No se presenta como certificación ni como cierre de Alpha.

Con el wheel del corte `fc7a676`, `LocalArtifactStore.get()` quedó bloqueado al
copiar una FIFO sin escritor. El proceso privado de prueba fue terminado después
de tres segundos. El recibo `artifact-store-fifo-before-fc7a676-v2/reproduction.json`
conserva el inicio del lector, su timeout y el hash del wheel. El primer intento
no llegó al lector por faltar un campo del fixture; se conserva sin acreditación.
Se usaron datos sintéticos y no se tocaron servicios ni archivos originales.

La implementación comparte ahora la lectura regular protegida. Comprueba
directorio y tipo de archivo antes de crear salidas, rechaza symlinks/reparse
points y verifica los directorios de salida antes de escribir. No resuelve
enlaces antes de inspeccionarlos. La navegación explícita de rutas locales usa
el normalizador que comprueba cada directorio atravesado; no debilita las
fronteras de lectura de evidencias.

Cuando existe una identidad declarada, cada lectura admite como máximo los
bytes pendientes más uno: una copia que supera el tamaño declarado se rechaza
sin leer el resto. El SHA-256 y el tamaño completo se verifican antes de publicar.
Los temporales se retiran ante fallo, la publicación sigue siendo exclusiva y
un destino existente no se sobrescribe. Las comprobaciones son cooperativas;
no aíslan montajes hostiles ni propietarios que cambian directorios concurrentemente.

Se añaden errores explícitos para tipos incorrectos de raíz, entrada y destino.
Se mantienen los tipos de rechazo de integridad e I/O, las firmas públicas, los
formatos y las referencias 1.0. Los archivos vacíos verificados siguen admitidos.

La tanda `artifact-copy-source-v2` registró **167 aprobadas, cinco omitidas y cero
fallidas** junto con ejecuciones/regresiones existentes. Después de añadir los
rechazos explícitos de tipos, `artifact-runtime-preflight-v2` registró **24
aprobadas y cinco omitidas** del almacén, sin fallos. Incluye junctions reales,
ausencia de salidas parciales, conservación de bytes y límite de lectura probado.
Mypy pasó en 109 archivos; Ruff, los 71 activos y la comprobación arquitectónica
pasaron. Los casos POSIX requieren comprobación propia en Linux.

El nuevo `tools/revalidate_artifact_runtime.py` fija esperados antes de ejecutar
el SDK instalado y asigna 33 obligaciones de API/métodos/parámetros a once casos.
Exige baseline e identidad del wheel concordantes, entradas protegidas, ejecución
aislada, catálogo inmutable y IDs pendientes únicos. Los errores inesperados se
registran como fallos. No acredita ciencia ni completa otras opciones por inferencia.
Su ejecución y la nueva validación de los artefactos siguen pendientes.

La suite instalada completa de Linux del corte anterior `fc7a676` pasó: **8.182
aprobadas y diez omitidas** del núcleo, **636 aprobadas y tres omitidas** del
benchmark. Esos recibos conservan los bytes anteriores y no se trasladan a esta
modificación. El consumidor independiente sigue su validación separada.

No se usó Codex Security, no se crearon agentes, no se publicó en PyPI/TestPyPI
ni se ejecutaron Actions. El enlace de la tutora y el Word permanecen ajenos a
estas pruebas privadas. La revisión posterior a Robot conserva su condición:
siete rubros acreditados al 90 % y corte exacto subido a GitHub.
