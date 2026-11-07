# Comparación anual completa de SERCOP en Linux ARM64

El ensayo concluyó el **11 de octubre de 2026, 23:36 de Ecuador**
(12 de octubre, 04:36 UTC): **81 comprobaciones PASS**, todas completas.
El núcleo instalado conserva la identidad original **0.12.0a13**. El
[recibo agregado](SERCOP_ANNUAL_VM_RESULT_20261011.json) conserva protocolos,
versiones, hashes, recursos observados y separación de intentos.

| Tamaño de adjudicaciones | Equivalencias contra esperado y entre motores | Diferencias deliberadas | Total |
|---|---:|---:|---:|
| 100 | 18 | 0 | 18 |
| 1.000 | 18 | 0 | 18 |
| 10.000 | 18 | 0 | 18 |
| 183.891, corpus completo | 18 | 9 | 27 |
| Total | 72 | 9 | 81 |

Las tres familias son proyección de tipos/ausencias, unión por identificadores
y agregación por moneda. pandas, Polars y DuckDB producen salidas nativas;
el esperado se calcula separadamente con Python. Las diferencias deliberadas
modifican un monto, una fecha o un conteo. Se verifica tanto el estado como
los registros completos de diferencias al volver a leer cada resultado.
Los 54 recorridos de prefijos son repeticiones del protocolo anterior;
las 81 comprobaciones no representan 81 muestras independientes.

Antes del ensayo se respaldaron diez directorios propios de temporales de
pytest y cachés. Se retiraron 247.955.526 bytes lógicos; el espacio libre
observado aumentó 471.478.272 bytes. Los artefactos, entornos, fuentes y
recibos anteriores permanecen conservados. El respaldo de temporales tiene
SHA-256 `c2d8b5af4372d66209d887b6e2f144aed77d013fdd6072cc0095e19a1c4cebd0`.

El [intento anterior de Windows](SERCOP_ANNUAL_ENGINEERING_20261011.md)
conserva el resultado no evaluable por `max_disk_bytes=256 MiB`.
La primera repetición ARM64 amplió disco a 1 GiB y plazo por comparación a
300 segundos: aprobó 60 comprobaciones, pero la unión anual alcanzó
`max_work=50.000.000`. Sus 180 segundos observados son una duración, no el
diagnóstico de un timeout. Ese fallo se conserva completo.

La segunda repetición fijó antes de ejecutarse `max_work=100.000.000` y
un plazo global de 4.800 segundos; las demás políticas, claves, tipos,
multiplicidades y esperados permanecen iguales. Concluyó en
3.244,47 segundos, con pico de RSS muestreado de 951.996.416 bytes y pico
de salidas de 1.988.928.634 bytes. La supervisión es muestreada y los
presupuestos del SDK son cooperativos; estos valores no son cuotas duras
ni una distribución estadística de rendimiento.

Ambos respaldos completos, con capturas Arrow y diferencias, se descargaron
al expediente privado local. Se verificaron todos los miembros y referencias:

| Intento | Miembros verificados | SHA-256 del respaldo |
|---|---:|---|
| Primero, conservado FAIL | 391 | `0c8e5ec45a0c918a2f243fda5e101fa5eb856eb40f00b2a252165a2abd530568` |
| Segundo, PASS | 512 | `c45a15148a7789948f520d49854881f38f91ad6bfd0650bb76381dee58cf8212` |

El corpus contiene 190.619 releases y 183.891 adjudicaciones. La selección
2025 del portal también contiene publicaciones de 2026; no se declara una
cohorte científica aprobada. Las adjudicaciones no equivalen a ejecuciones
normales efectivas de aprendizaje. Este ensayo no aporta etiquetas humanas
O, aprobación científica, aceptación del DW ni puntos automáticos a las
rúbricas ya cumplidas. Los requisitos abiertos conservan su denominador.

El Word permanece intacto. No se ejecutaron Actions, publicaciones en índices
de paquetes ni recursos de pago.
