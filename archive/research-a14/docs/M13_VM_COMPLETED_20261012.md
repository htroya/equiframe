# M13: laboratorio ARM64 concluido y devuelto

El [resultado](M13_VM_COMPLETED_RESULT_20261012.json) acredita ejecución real
en `maestria-vnic`, Linux ARM64, Python 3.10.12 y 3.12.15, sobre artefactos
originales Alpha A13 y consumidor 0.1.15. El segundo intento r2 terminó con
salida cero a las 22:46:47 UTC del 12 de octubre: **115 comandos y 52 perfiles**,
regresión fuente, reconstrucción wheel/sdist, consumidor normal/optimizado,
fallos, recuperación y medición de recursos. No cambia el alcance de M04.

El expediente completo de **234.999 archivos** se devolvió y verificó por
SHA-256 y lectura ZIP, junto con 17 envolventes de supervisión y revisión.
Su archivo pesa 486.344.558 bytes y tiene SHA-256
`1027b8166416d831ac07bdb8e3b390dd2448734a68cc9863ed830b94739b8802`.
El intento original fallido también se devolvió íntegramente y conserva su fallo.

El lector congelado encontró un desacuerdo JUnit: pytest 9.1.1 cuenta 19 tests
padre y 15 eventos subtest como 34. Se verificaron las identidades, logs y
código original; un [adaptador separado y acotado](../tools/maturity_lab/scripts/consumer_subtest_addendum.py)
interpreta ese caso sin reescribir evidencias. Sus siete guardias pasan normal
y `-O`. La revisión final del lector congelado con el adaptador pasa.

El ejecutor fue el agente IA mediante SSH local autorizado y host fijado.
La revisión «mi dot» es IA; ninguna de estas acciones acredita revisión humana
independiente, aceptación científica o el DW/servicio de los compañeros.
La [evaluación tras M13](MATURITY_HANDOFF_RESULT_20261012.json) conserva
la anterior y añade únicamente ese cierre: 6/16 = 37,50 % en ese corte.
