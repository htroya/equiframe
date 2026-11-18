# A14: errores seguros y lectura de evidencias

Continúa el desarrollo autorizado para alcanzar el 90 % técnico por rubro.
Este registro no declara alcanzada la meta, cerrado Alpha ni completada una
certificación de seguridad. Los diez puntos manuales conservan su separación.
No se utilizó Codex Security ni se crearon agentes.

## Problemas reproducidos

Con el wheel del corte `7002256486fb5e3ab58640d3ce49818e0e781627`, un callback
de cancelación que fallaba una vez con un marcador sintético acabó publicando
ese marcador en `reason` y en HTML. La recuperación invocó el callback tres
veces. Otro callback que fallaba siempre escapó sin finalizar el resultado.
Los intentos anteriores de CSV no demostraron divulgación y no se cuentan.
Los recibos permanecen privados en `a14_review_fixes_20261013/`:
`eda-error-disclosure-before-v4` y `eda-error-disclosure-before-v5`.

En Linux ARM64, `inspect_bundle()` del mismo wheel quedó bloqueado durante
tres segundos al recibir `bundle.json` como FIFO sin escritor. El proceso de
prueba se terminó por timeout; no se interrumpieron servicios ni se modificaron
datos originales. Recibo remoto: `bundle-fifo-before-v1/reproduction.json`.

## Correcciones y límites

Los resultados operativos usan mensajes fijos y códigos controlados. No se
formatean excepciones externas. El logger opcional conserva hasta 32 registros
de módulo, función y línea propios; omite valores, rutas, fuente, locales y
nombres de callbacks externos. Un handler defectuoso no sustituye el resultado.
Las excepciones programáticas de validación y la evidencia cruda explícita
siguen requiriendo tratamiento por quien integra el paquete.

EDA exige callbacks invocables y resultados booleanos reales. Si fallan, no se
reinvocan durante la recuperación. Los fallos de gráficos quedan no evaluables
con un mensaje fijo. No se alteran estados de aceptación ni formatos 1.0.

Los lectores JSON, journals y descripciones de archivos comparten la lectura
regular ya utilizada por informes. Los bundles revisan ancestros antes de
resolverlos, rechazan miembros especiales y comprueban el hash de los mismos
bytes leídos. En POSIX se fijan descriptores de directorio y se usan flags de
no seguimiento/no bloqueo. Windows comprueba identidades y reparse points.
No constituye aislamiento frente a montajes hostiles o propietarios concurrentes;
las copias requieren una fuente controlada e inmutable.

Se regeneró solamente el catálogo actual de reglas porque su fingerprint incluye
el código de implementación. No se reescribieron fixtures ni resultados históricos.

## Verificación de fuente y candidato pendiente

El recibo `safe-evidence-final-source-v2/tests.xml` registra **112 aprobadas,
16 omitidas y cero fallidas** en Windows: lecturas regulares, privacidad de
errores, informes, integridad y recuperación. Incluye junctions reales. Las
omisiones POSIX y permisos de symlink quedan explícitas; no reciben crédito.
El intento anterior `safe-failure-source-v6` conserva una aserción obsoleta
de texto fallida; su actualización conserva el rechazo del artefacto alterado,
y esa prueba pasó en la tanda final. No se suman pruebas repetidas.

Mypy comprobó 109 archivos sin errores. Ruff y formato pasaron, los 71 activos
coincidieron y el análisis de imports registró 89 módulos, 586 imports, cero
ciclos eager y cero infracciones. Los ciclos de imports locales se conservan
en el recibo arquitectónico. Estos controles de fuente no sustituyen la
validación completa de los nuevos wheel/sdist, que requiere sus propios hashes.

## Saldo de trazabilidad del corte anterior

Los recibos `root-coupled-7002256-normal-v4/result.json` y
`root-coupled-7002256-optimized-v4/result.json` acreditan **282 IDs adicionales**:
259 admitidos y 23 rechazos esperados. Los observados coinciden íntegramente
entre modos. Su catálogo común tiene SHA-256
`7aaa7578d1f2b69e300fdb8de529d51656c46817cf7abc065b93c141a6f6eaa4`.
Son 60 obligaciones nuevas respecto de las 222 previamente acreditadas.

Para esos bytes: raíz **6.483/8.438**, EDA **704/704**, conjunto
**7.187/9.142**, con **1.955 pendientes**. Aplicando el reparto técnico/humano,
la parte de trazabilidad acreditada aporta **70,7537/90 puntos técnicos**.
No es el promedio general ni acredita el nuevo candidato aún sin validar.
Los catálogos originales, denominadores y controles científicos se conservan.

TestPyPI continúa solo en configuración. La revisión externa posterior a Robot
sigue condicionada a completar los siete rubros y subir el corte exacto.
