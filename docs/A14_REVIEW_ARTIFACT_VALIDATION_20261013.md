# Revalidación privada de las correcciones A14

El código corregido está en `37e0ea76250787761645a48719bc3bf6e4b14b0e`.
La [revisión y sus correcciones](A14_INDEPENDENT_REVIEW_FIXES_20261013.md)
conservan el corte anterior y los intentos fallidos. Se reconstruyeron seis
artefactos privados; TestPyPI permanece sólo en configuración.

## Resultados sobre los nuevos bytes

| Comprobación | Resultado | Alcance |
|---|---|---|
| Núcleo completo instalado | 8.134 aprobadas, dos omisiones, cero fallos; 8.136 casos | Linux ARM64, Python 3.12.15; sólo se omiten los junctions de Windows |
| Benchmark completo instalado | 625 aprobadas, dos omisiones, cero fallos; 627 casos | Linux ARM64; se omiten dos comportamientos exclusivos de Windows |
| Cliente/gateway, DW y preparador | 169 aprobadas, dos omisiones, cero fallos | Entorno nuevo Windows 3.12.4; omisiones de permisos de symlink |
| DW corregido | 25 aprobadas, cero fallos | También repetidas en Linux, incluyendo conservación de dimensiones históricas |
| Mypy completo | Núcleo 106 archivos; benchmark 37, sin errores | Configuraciones completas en Windows y Linux ARM64 |
| Documentación actual | 94 documentos, 794 destinos locales, 19 anclas, cero fallos | Registro previo a añadir este recibo |
| Ejemplos documentales | Ocho aprobados | Cuatro textos, normal y `-O`, wheel instalado en venv POSIX; conserva su symlink |
| Trazabilidad raíz | 6.201/8.438, con 2.237 NOT_RUN | 5.230 casos por modo, normal y `-O`, vinculados al wheel nuevo |
| Trazabilidad EDA añadida | 704/704, sin fallos ni pendientes del inventario | 339 aprobaciones y 365 rechazos esperados por modo, normal y `-O` |
| Metadatos de distribución | Los seis archivos pasan `twine check --strict`; `pip check` satisfactorio | Comprobación privada; no hay upload |
| Par núcleo/benchmark | Auditoría offline satisfactoria | Puertas públicas bloqueadas deliberadamente |
| Dependencias públicas exactas | 103 versiones auditadas, cero vulnerabilidades conocidas | Entorno Windows nuevo; no es un examen del código privado ni de versiones futuras |

`tools/revalidate_eda_contracts.py` amplía el namespace identificado por la
revisión. Sus literales sintéticos cubren metadatos, ocho validadores y cuatro
APIs con sus parámetros; las APIs usan Arrow real y una migración de dos motores
con esperado Decimal independiente. El catálogo se sella antes de ejecutar y
se comprueba el wheel instalado. El primer fixture Arrow omitía dos campos de
ArtifactRef: ese intento se conserva. Completar esos metadatos requeridos no
cambió los casos ni los esperados del catálogo. El catálogo final normal/`-O`
tiene SHA-256 `83970910419204f09aa6dd75b4e4510e025f401db02d67a674e4e590963de1b1`.
La evidencia no acredita resultados científicos ni todos los posibles datos.

## Inventario ampliado y distancia al 90 %

Se mantienen las 8.438 obligaciones raíz, incluidas las 8.385 originales y 53
adiciones A14. Se añaden explícitamente las 704 de `equiframe.eda`, cuyos IDs
son distintos. En el inventario SDK ampliado son **6.905/9.142 = 75,530518 %**;
quedan **2.237 obligaciones técnicas** de la raíz. Las repeticiones normal/`-O`
no suman obligaciones. Otros componentes del monorepo tienen sus propias pruebas
y no se presentan como inventariados por este contador SDK.

Con [90 puntos técnicos + 10 manuales](A14_TECHNICAL_90_METHOD_20261013.md), sin
crédito manual nuevo, esta trazabilidad aporta **67,977467/100**. Faltan
**22,022533 puntos técnicos** para su 90 %. La raíz conserva su medición
6.201/8.438: no se reescribe como si siempre hubiese incluido EDA.

El [recibo posterior de contextos](A14_ROOT_CONTEXT_REVALIDATION_20261013.md)
acredita 222 obligaciones raíz adicionales en ambos modos con estos mismos
bytes. Su inventario ampliado queda en 7.127/9.142, con 2.015 pendientes;
los conteos anteriores identifican el corte previo y se conservan.

El promedio general A14 de los siete rubros requiere evaluar todos sus criterios.
La distancia histórica es 16,44 puntos desde 73,56 %; para los ocho indicadores,
14,18 desde 75,82 %. Ninguno se renombra como promedio A14.

## Artefactos identificados

| Archivo | SHA-256 |
|---|---|
| equiframe-0.12.0a14-py3-none-any.whl | `dd12cc78988114a7bba1cbe14952afeca2e54ce69b8deacb659963fd7ad8a901` |
| equiframe-0.12.0a14.tar.gz | `38cc2876549c8d63e2bd255580bbdd9ddcd9930a39c832ba90610953af4e6d51` |
| equiframe_benchmark-0.12.0a14-py3-none-any.whl | `c02171903298f06b214dd2421cd9aeff91554a0f1c3c666920d02d4af4689c31` |
| equiframe_benchmark-0.12.0a14.tar.gz | `882c038040a0ade9dd2c1b5792682930f3bf5ad127fef61c1d0a793fc4f1726d` |
| equiframe_data-0.1.0a14-py3-none-any.whl | `620a84667ffb3ba89b79dd7501bbf5aed4e7ed36ed22f3c850944532ae051851` |
| equiframe_data-0.1.0a14.tar.gz | `9676f4f48bb39bb30a13053f80e1279eaf6b11815851294f7dec321b4fafd58a` |

Los recibos nuevos están fuera de Git en `a14_review_fixes_20261013`, incluidos
`linux-receipts-v2`, `data-gateway-artifact-v3.xml`, los dos
`trace-artifact-*-37e0ea7-v1/result.json`, los dos
`eda-contract-*-v4/result.json`, `sca-windows-public-37e0ea7-v1.json` y
`pypi-preparation-packet-37e0ea7-v1.json`. La instalación Linux comprueba todos
los miembros del wheel antes de las suites; el manifiesto de fuente también se
verifica después. Los hashes identifican archivos, no autentican revisores.

El piloto SERCOP se preparó y verificó otra vez en Linux con estos mismos wheels:
216 ejecuciones y sus perfiles/R/comparaciones recalculados, fuente original
inalterada, `technical_preparation=PASS`, `scientific_ready=false`.
La [preparación anterior](A14_SERCOP_EXPERIMENT_PREPARATION_20261013.md) se conserva.
Faltan normalidad aprobada, etiquetas finales, calibración/test independientes
y soporte confirmado `N_fit > 10.000` por modelo/familia.

Alpha privada A14 continúa; no se declara cerrado el 90 % general ni Beta.
No se usó Codex Security, no se abrieron agentes, no se publicó en PyPI/TestPyPI,
no se modificó el Word ni se interrumpieron los servicios de la tutora.
