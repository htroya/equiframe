# Revalidación de contextos pendientes del núcleo A14

Se acreditan **222 obligaciones raíz adicionales** sobre el wheel privado
`dd12cc78988114a7bba1cbe14952afeca2e54ce69b8deacb659963fd7ad8a901`,
construido desde `37e0ea76250787761645a48719bc3bf6e4b14b0e`.
El [resumen verificable](A14_ROOT_CONTEXT_RESULT_20261013.json) conserva sus
identificadores, hashes y categorías pendientes. No modifica los recibos
anteriores de 6.201/8.438 ni las 704 adiciones explícitas de EDA.

| Inventario | Verificadas | Total | Pendientes |
|---|---:|---:|---:|
| Raíz A14, antes de estos contextos | 6.201 | 8.438 | 2.237 |
| Raíz A14, con los contextos nuevos | 6.423 | 8.438 | 2.015 |
| EDA, namespace añadido por separado | 704 | 704 | 0 |
| SDK ampliado, IDs distintos | **7.127** | **9.142** | **2.015** |

El SDK ampliado alcanza **77,958871 % técnico**. Con el
[reparto autorizado](A14_TECHNICAL_90_METHOD_20261013.md), sin crédito manual,
aporta **70,162984/100**. Faltan **19,837016 puntos** para el 90 % de este
inventario. Quedan 1.355 parámetros, 158 campos, 128 APIs, 70 propiedades,
55 métodos, 34 comandos, 175 opciones CLI, 18 perfiles de dependencias y
22 requisitos de presencia/ausencia de paquetes. No se trasladan estos
pendientes a los diez puntos manuales.

## Cómo se verificó

`tools/revalidate_root_contexts.py` parte del catálogo literal original
inmutable y del recibo raíz A14 vinculado al nuevo wheel. Antes de ejecutar,
fija los contextos complementarios de cada caso y su JSON esperado completo.
Por ejemplo, omitir una columna en `WindowMeasure` requiere `row_number`;
una decisión no evaluable conserva su motivo; una fase omitida no conserva
una migración aprobada. Se comprueban además redondeo, ausencias, precisión,
límites, multiplicidad, políticas de tiempo, perfiles y divulgación de informes.

Son **pruebas de contratos y metadatos**. Las referencias sintéticas y las
decisiones hipotéticas de estos casos no son nuevas ejecuciones nativas,
entrenamientos ni evidencia científica. Los recibos declaran expresamente
`scientific_credit=false`.

El catálogo final, idéntico en ambos modos, tiene SHA-256
`c411417ffe0e973c4b2602ae59df00d5e93dfbec5a5bd0caca903d951f4b9d78`.
Cada ejecución produjo **201 PASS y 21 EXPECTED_REJECTION**, sin fallos ni
exclusiones de los casos seleccionados. Se compararon íntegramente los
recibos normal y `-O`, incluidos los observados; no se suman repeticiones.
El consolidado verificó que los 222 IDs pertenecían al conjunto NOT_RUN
original y que no coincidían con IDs acreditados ni con EDA.

Los controles de entrada del verificador rechazan enlaces y reparse points,
archivos superiores a 64 MiB, JSON ambiguo o no finito y estructuras excesivas.
Se fija el SHA-256 permitido de cada baseline, se comprueba el SDK instalado
frente a su fuente y se conservan salidas anteriores. Diez pruebas adversarias
pasaron en Windows; una se omitió por falta de permiso para crear un symlink.
Ruff comprobó el código y su formato. El catálogo y los 222 observados también
coincidieron en Linux ARM64 3.12.15, normal y `-O`; sus recibos tienen SHA-256
`056c63c3e842734ed1cfc4b3de28666b77ecc229b44a9f9e819372649a94eff5` y
`42ac1ee093ea91755a01a4fb8d1c6c97aff92b331f675eb8bf8bca7432e5ff61`.
Estas pruebas y plataformas no añaden obligaciones al contador.

Los intentos anteriores de preparación permanecen privados: se corrigieron
un contexto de deduplicación incompleto, el manejo de rutas relativas en el
lector y dos clases de límite de timeout. Ningún fallo previo se convierte
retroactivamente en pase. El contador final usa exclusivamente los recibos
`root-coupled-normal-v9/result.json` y
`root-coupled-optimized-v9/result.json`, fuera de Git en
`a14_review_fixes_20261013`; sus hashes están en el resumen público.

Para reproducir, usar un entorno privado con el wheel identificado, el
catálogo `revision_95_20261011/trace_inputs/catalog-a13.json` conservado y
el baseline `trace-artifact-normal-37e0ea7-v1/result.json`:

```text
python -I tools/revalidate_root_contexts.py --catalog <catalogo-privado> --baseline <baseline-privado> --output <directorio-privado-nuevo>
python -I -O tools/revalidate_root_contexts.py --catalog <catalogo-privado> --baseline <baseline-privado> --output <otro-directorio-privado-nuevo>
```

Las rutas de salida deben estar fuera del repositorio. Los catálogos privados
se entregan mediante kits identificados, sin credenciales ni datos reales.

## Corrección adicional del cargador SERCOP

En una reproducción privada se confirmó que un objeto `release` con `id`,
`ocid` y `awards` se insertaba como una adjudicación con el ID del release,
monto NULL y moneda NULL. El cargador ahora rechaza el grano ambiguo antes de
escribir. Sólo acepta adjudicaciones normalizadas y un envoltorio cerrado
`{"awards": [...]}`; debe normalizarse un release explícitamente para conservar
sus campos y asociaciones. No se cambió el DDL ni se escribió en el DW real.

También se rechazan enlaces en los archivos/directorios de entrada y de la
base. Las consultas de dimensiones se seleccionan entre textos SQL fijos y
usan parámetros para valores. Una prueba con `DROP TABLE` en un valor conservó
ese valor como texto y la tabla de snapshots intacta; los identificadores
fuera de la lista permitida se rechazaron antes de ejecutar SQL. Bandit 1.9.4
terminó sin hallazgos en este cargador y el verificador, sin reglas suprimidas.
El análisis anterior con tres avisos sobre consultas dinámicas se conserva.

La suite conjunta del cargador y el lector seguro terminó con **41 aprobadas
y tres omisiones por permiso de symlink en Windows**, y **44 aprobadas sin
omisiones en Linux ARM64**. Los XML son `dw-root-context-v3.xml` y
`linux-receipts-v2/dw-root-safety-linux-v1.xml`. La ejecución Linux verificó los
hashes de los siete archivos del overlay antes y después; conservó la fuente
original y los servicios. El cargador es un prototipo fuera de los seis
artefactos SDK ya identificados; esta corrección no cambia sus bytes.

El promedio A14 de los siete rubros sigue pendiente de una evaluación completa.
Alpha privada continúa, y la nueva solicitud de revisión independiente externa
a Robot queda pendiente de acreditar el 90 % en todos los rubros y subir el
corte exacto a GitHub, conforme a la condición del propietario. No se publicó
en PyPI/TestPyPI ni se ejecutaron Actions. No se usó Codex Security ni agentes.
