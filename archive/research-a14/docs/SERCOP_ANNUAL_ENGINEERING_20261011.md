# SERCOP anual: datos reales, verificaciones y dimensión observada

Se leyó completamente el export público ya adquirido de SERCOP y se ejecutaron
recorridos reales con el wheel original **EquiFrame 0.12.0a13** instalado fuera
del checkout. Se cotejaron sus 127 archivos de payload. Los datos y las capturas
permanecen fuera de Git; el Word conserva su hash original.

Hay dos resultados distintos y ambos se conservan:

- [Ensayo del comparador SDK](SERCOP_ANNUAL_ENGINEERING_RESULT_20261011.json):
  **54 comprobaciones completas equivalentes** en prefijos de 100/1.000/10.000
  adjudicaciones; la primera comparación del conjunto completo terminó
  **`not_evaluable` por `max_disk_bytes`**. La aceptación esperada no se cumplió:
  55 checks ejecutados, 54 aprobados, uno no evaluable y 26 no ejecutados de los
  81 planificados. No se cambió su protocolo ni se reinterpretó como equivalencia.
- [Complemento de salidas nativas completas](SERCOP_FULL_NATIVE_ORACLE_RESULT_20261011.json):
  **9/9 salidas positivas y 9/9 alteraciones declaradas** coinciden exactamente
  con los esperados independientes correspondientes sobre todas las
  adjudicaciones. Es una comprobación del consumidor con valores tipados y
  multiplicidades; no reemplaza la comparación completa pendiente del SDK.

## Corpus y perfilado

Fuente: [portal de datos abiertos del SERCOP](https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos/).
La [adquisición original](SERCOP_PUBLIC_RESULT_20261011.json) conserva fechas,
selector y hashes; no se afirma una nueva descarga. Selección `year=2025`,
`month=0`, `method=all`; ZIP 160.929.006 bytes, JSON 1.721.952.248 bytes;
SHA-256 `9ee4e5f94f44e42c89ade804d00ed69cd24604d246ad6450a4a43b2bd42e3632`.
La lectura completa verificó CRC, un único miembro y paquetes/identidades sin
ambigüedad. No extrae ni ejecuta contenidos del ZIP.

| Observación del export | Resultado |
|---|---:|
| Paquetes / releases / OCID únicos | 190.619 |
| Adjudicaciones / identidades `(ocid, award.id)` únicas | 183.891 |
| Adjudicaciones con importe y moneda USD presentes | 183.887 |
| Adjudicaciones con campo `value` ausente | 4 |
| Importes cero / negativos observados | 1 / 0 |
| Releases con año textual de publicación 2025 / 2026 | 176.666 / 13.953 |
| Representación monetaria exacta admitida | Decimal128, precisión 38, escala 7 |

Los números JSON, incluidos enteros, se decodifican como `Decimal`. Se conserva
el signo de cero antes de admitir valores; se rechazan dinero no finito, cero
negativo y valores que no quepan exactamente después de reescalar. Ausente,
nulo y presente conservan flags distintos; un objeto inválido no se repara como
nulo. Los cuatro casos sin `value` se identificaron como **ausentes**, sin
importe imputado. Un cero o la ausencia no se etiquetan como anomalía financiera.

La selección 2025 incluye fechas de publicación 2026. No se infiere cohorte
temporal ni fecha de adjudicación. Las categorías textuales de procedimiento
inventariadas tampoco acreditan todas las modalidades de contratación. Se
mantiene la atribución a SERCOP y la declaración CC BY 3.0 Ecuador observada en
los paquetes; no implica respaldo de SERCOP ni resuelve derechos del software.

## Ejecución nativa y esperados

Pandas, Polars y DuckDB ejecutan por separado proyección de tipos/ausencias,
left join de adjudicaciones con texto/presencia de fecha de release y conteos
por moneda. Los esperados se construyen con datos crudos Python antes de los
motores. No hay deduplicación de adjudicaciones, sumas entre monedas, conversión
de dinero a float ni salidas de un motor usadas para simular otro.

Cada prefijo tiene nueve comprobaciones contra esperados y nueve entre parejas
de motores. Comparten observaciones y no son muestras científicas independientes.
Solo se ignora explícitamente el RangeIndex generado por pandas.

El complemento se habilitó **después** del límite observado y congeló otro
protocolo, ligado por hash al check/manifiesto y causa exacta originales. Reusa
los tres Arrow esperados crudos preparados antes de los motores del primer
ensayo. Su lookup de releases contiene las fechas/presencias consistentes de
los OCID relevantes para adjudicaciones; no valida releases sin adjudicaciones.

Antes de las nuevas ejecuciones se construyen multisets positivos y alterados
independientes. Se exige tipo numérico Arrow exacto, valores, columnas y
multiplicidad. Los dos anchos de offsets UTF8 se permitieron explícitamente en
este protocolo; los textos deben coincidir exactamente. Esta comprobación tiene
ese alcance propio y no se denomina `ComparisonResult` del SDK.

Los controles cambian deliberadamente salidas nativas: un importe en +1, una
fecha por `0001-01-01` y un conteo de moneda en +1. El complemento verifica los
nueve resultados alterados contra sus esperados alterados y distintos de los
positivos. No son rechazos de entrada ni fallos inyectados en el export original.

## Dimensión y límites observados

Windows 11 AMD64, CPython 3.12.4; pandas 3.0.6, Polars 1.44.2, DuckDB 1.5.6,
PyArrow 25.0.1, psutil 7.2.2. Un hilo configurado por motor, procesos secuenciales.
Presupuestos del supervisor: 2 GiB RSS, 3 GiB de salida y 2.400 s, con mínimo
3 GiB RAM / 5 GiB disco libres. Son límites observados por muestreo, con posible
sobrepaso entre muestras; no cuotas duras OS/container ni evidencia S09 completa.

| Medición | Comparador SDK | Complemento nativo |
|---|---:|---:|
| Tiempo total observado | 757,916 s | 56,874 s |
| Pico RSS muestreado del proceso hijo y descendientes | 675.778.560 bytes | 1.088.425.984 bytes |
| Salida final conservada | 117.674.385 bytes | 8.916 bytes |
| Resultado del alcance planificado | Incompleto por límite de disco de una comparación | 18/18 controles nativos aprobados |

La primera comparación completa duró 158,572 s y diagnosticó
`resource_exhausted / ResourceLimitError / max_disk_bytes`, lado derecho,
con presupuesto de **256 MiB por comparación**. No fue un timeout ni una
diferencia de valores. Sus contadores parciales no acreditan comparación
completa ni ausencia de diferencias. Su supervisor terminó sin errores de
medición/limpieza, sin superar su propio presupuesto y sin cambios de fuentes.

Los dos tiempos totales describen trabajos diferentes y no permiten afirmar
una aceleración del comparador. El complemento registra carga y transformación
por motor, comprobación exacta y controles separadamente. Las duraciones por
etapa del primer driver no se persistieron al quedar incompleto; se conservan
las duraciones por check, recursos y recibos, sin reconstruir tiempos ausentes.
Es una ejecución por protocolo, sin intervalos de confianza ni ley de escalado.

## Pruebas, evidencia y siguiente trabajo

Las **21 pruebas distintas** de la herramienta pasan en modo normal y optimizado,
con Ruff/formato aprobados. Incluyen dinero no representable, claves JSON
duplicadas, ausencia/nulo, cambios nativos y lectura con evidencia alterada.
Cuatro controles del verificador complementario comprueban offsets UTF8
prepermitidos, multiplicidad extra, rechazo de dinero convertido a float y de
campos alterados. «mi dot» revisó ambos protocolos/código en modo IA; no es una
revisión humana independiente.

Expediente local `sercop_dimension_20261011`: protocolos con hash, supervisores,
scripts, logs, 342 archivos del ensayo original y manifest con hashes, capturas
y esperados privados, controles complementarios y revalidación de recibos. Los
ZIP originales siguen en `avance_95_20261011`; no se modificó el corpus ni el Word.

Falta completar la comparación SDK anual con un protocolo nuevo que dimensione
su disco de trabajo y presupuesto de tiempo; el límite original se conserva.
También faltan contrato/cohorte de dominio, perfiles efectivos de aprendizaje,
grupos y particiones sin fuga, normalidad revisada, ajuste/calibración,
oráculo humano y evaluación científica. El DW y servicio de los compañeros
mantienen sus responsables.

No se entrenó ningún modelo, no hay etiquetas humanas acreditadas ni nuevos
criterios u obligaciones puntuados por estos recorridos. Tesis sigue en **9/22**.
La recomputación de las nueve fuentes conserva **66,43 % global**; el
[plan de las áreas hacia el 60 %](RUBRIC_FLOOR60_PLAN_20261011.md) sigue condicionado
a cinco cierres adicionales completos en cada área rezagada. No se publicaron
paquetes, ejecutaron Actions ni crearon recursos de pago.
