# Paso 10: protocolo sellado, evaluación y reproducción

Implementación: núcleo `equiframe 0.9.0`, distribución experimental
`equiframe-benchmark 0.10.0`. La aceptación técnica y la aceptación científica
se registran por separado en [la revisión](STEP_10_REVIEW.md). No se publica en
PyPI ni se certifica ARM64 por disponer de un workflow.

## Alcance y relación con la tesis

La configuración del experimento se fija antes de ejecutar sus casos de prueba.
La evaluación consume decisiones R/M/B/H independientes y etiquetas de EquiFrame
Verify, O, con la procedencia que ya exige el paso 6. No recibe etiquetas durante
perfilado o inferencia, no aprende umbrales con prueba y no toma Pandas como verdad.
La API nueva `detect_component(..., method="isolation_forest")` mide M sin ejecutar
MAD. Su resultado se liga a perfiles, preprocesamiento y modelo congelado.

La ausencia de corpus SERCOP, cliente productivo, DDL/mapeos y revisiones humanas
impide cerrar el experimento de la tesis. Esos requisitos no se reemplazan por
fixtures ni por números de pruebas de software. Los capítulos 4/5 científicos
permanecen pendientes; las tablas de conformidad sintética llevan `mode=pilot`.

## Congelación

`FreezeDefinition` conserva:

- catálogo y particiones transitivas reproducibles; cada escenario ocupa un grupo
  indivisible y los casos programados pertenecen exclusivamente a prueba;
- contrato, reglas, features, motor nativo, implementación y migración explícita;
- las cinco familias, incluyendo familias sin modelo con una razón de no soporte;
- selecciones normales de entrenamiento/calibración, capturas/perfiles originales,
  auditoría de grupos, modelo, preprocesador y umbrales ya fijados;
- doce decisiones: cohorte, tiempo, decimal, claves incompletas, alpha, independencia
  de revisores, reglas antes de variantes, features antes de prueba, independencia
  de grupos, ausencia de ajuste con prueba, licencia de datos y control del entorno;
- archivos locales con SHA/tamaño, versiones de paquetes/Python, revisión del código
  y protocolos de evaluación y coste.

La auditoría vuelve a leer los artefactos reales, coteja su hash/tamaño y comprueba
Arrow, contratos, reglas y features. Rehace la selección admisible a partir de su
evidencia y comprueba preprocesador, matriz, MAD y calibración desde el ajuste
congelado. No reentrena Isolation Forest. Una huella no autentica al revisor ni
prueba por sí sola cómo se entrenó el bosque; estas son obligaciones del productor.

Los hashes de los protocolos excluyen el futuro hash del sello para evitar una
referencia circular. El sello liga esos protocolos, catálogo, split y modelos.
Un lector reaudita las fuentes físicas; no basta cambiar `ready` en un JSON.

`technical_ready` significa ausencia de fallos de integridad; `scientific_ready`
significa ausencia de todos los bloqueos. En modo piloto puede emitirse un sello
técnico con bloqueos científicos visibles. En modo final cualquier bloqueo impide
sellar/ejecutar. Un piloto no abre ni sustituye la prueba científica final.
No se impone un mínimo inventado de 60 escenarios o 300 perfiles como sustituto
de soporte, potencia o independencia justificados.

## Ejecución y conservación de fallos

`run_study` recibe un sello y un registro de transformaciones confiable inyectado.
Cada caso ejecuta su ETL nativa con los mismos inputs declarados. Usa el modelo
previo de su familia y el esperado independiente. No entrena ni modifica el sello.
La evidencia conserva capturas, reglas, perfiles, decisiones, comparación, tiempos,
entorno y fallos; se vuelve a auditar el sello al finalizar.

Reutilizar la etiqueta de una salida revisada exige comprobar que la ejecución
nueva produce una salida equivalente al candidato revisado, además de conservar
implementación y entradas. Una salida cambiada o no comparable pierde la etiqueta
evaluable; se conserva su vínculo con O y el motivo. Ningún fallo se vuelve
`no_alert`. Una ejecución ausente permanece en el total con cuatro componentes no
evaluables. Si R produjo evidencia válida y falla M, se conserva R y su soporte
propio. H puede alertar parcialmente y seguir fuera de la comparación principal.

El manifiesto final se publica después de la evidencia. `read_study` comprueba
inventarios cerrados y sus vínculos sin ejecutar callbacks ni repetir ETL. Un
expediente íntegro pero incompleto es verificable; el resumen conserva esa condición.

## Métricas y tablas

La comparación principal usa la intersección de casos con O confirmado y los
cuatro componentes completos. Cada método informa además su soporte propio,
cobertura, alertas parciales, fallos y exclusiones. Los denominadores no se mezclan.
El cálculo conserva precisión, recall, F1 y FPR indefinidos y sus razones; AP solo
compara scores homogéneos. H1/H2 usan diferencias pareadas en la misma intersección.
El bootstrap remuestrea grupos enteros y conserva réplicas indefinidas.

`EvaluationReport` recalcula estratos y métricas al validar JSON. `write_tables`
publica seis CSV UTF-8 con salto de línea fijo: cobertura, métricas, AP, incrementos,
bootstrap y casos. Incluye familias vacías y razones de no estimabilidad. Su lector
regenera cada byte desde el informe, además de comprobar hashes y un inventario
sin extras. Un CSV editado no se acepta aunque se recalculen sus metadatos.
Estas tablas corresponden a detección; los recursos/costes se conservan por
observación en sus recibos propios, con calentamientos separados.

## Coste operacional H3

Se comparan perfil+M aislado y comparación exhaustiva sobre capturas YA materializadas.
Quedan fuera lectura inicial del DW, ETL y captura. No se usa tiempo de toda la
tubería como si fuera el coste de detectar. Las lecturas Arrow, verificaciones y
publicación realizadas dentro de cada operación sí forman parte de su tiempo.
No se resta retrospectivamente un coste estimado de E/S.

Hay un calentamiento y cinco repeticiones por método; el orden alterna y su primera
posición depende de una semilla previa. Se declaran caché, hilos, otras cargas,
intervalo de muestreo y presupuesto cooperativo de memoria. Las repeticiones de
coste no aumentan el número de casos independientes de detección.

El tiempo de pared cubre callback y validación de su resultado; excluye verificaciones
externas del protocolo, preparación del monitor y publicación de su recibo final.
CPU es diferencia de contadores del proceso alrededor del muestreo y abarca la
actividad de su hilo; excluye subprocesos. RSS es el máximo absoluto observado,
una cota inferior del pico real, con baseline separado y resolución declarada.
Una lectura fallida conserva CPU/RSS ausentes; no elimina la operación ni inventa
ceros. El presupuesto cooperativo no es una cuota dura del sistema operativo.

## Bundle y reproducción

`create_bundle` copia un inventario cerrado de archivos ordinarios con límites
de bytes/cantidad y comprobación SHA/tamaño; rechaza rutas ambiguas, enlaces,
reparse points, duplicados y extras. La publicación es atómica y exclusiva.
`bundle_artifact` cambia únicamente URI después de encontrar un vínculo exacto
con el artefacto original. No reescribe ni falsifica hashes de padres.

`bundle_study` incluye evidencia del estudio, capturas, fuentes del catálogo y
archivos congelados, junto con configuración, split, etiquetas, decisiones y
contenido completo de los seis CSV. Los decimales y monedas permanecen en Arrow;
no se verifica una tabla únicamente por cantidad de filas o suma global.

`reproduce-study` comprueba el bundle portable y recalcula informes/CSV desde
decisiones capturadas. Es reproducción determinista de las tablas, no repetición
de ETL ni revisión humana de otro integrante. `reproduce-bundle` admite un
regenerador confiable explícito para otros contenidos; el JSON nunca importa código.
Para cerrar la aceptación externa, un compañero debe conservar su entorno,
ejecuciones independientes y comparación de contenido/decisiones con el expediente
fijado. Ese acto sigue pendiente hasta que exista una evidencia auténtica.

## Distribución y verificaciones

Se inventarían metadatos, licencia pendiente, control del nombre pendiente,
dependencias, lock, `py.typed`, fuentes y metadatos del wheel. Un 404 de PyPI no
reserva un nombre. Build/install locales y matriz de plataformas son evidencias
separadas del inventario. Detalles en [distribución](STEP_10_DISTRIBUTION.md).

La cuenta agotó Actions. El workflow quedó desactivado remotamente y su configuración
permite solo despacho manual con confirmación explícita de consumo. No se ejecuta
CI para esta versión ni se atribuyen a ella resultados históricos de 0.8.1/0.9.0.
Las comprobaciones locales incluyen software instalado fuera del checkout, ejemplos
nativos, esquemas, tipado, corrupción, límites y reconstrucción idéntica desde sdist.
La publicación pública corresponde al paso 19, después de revisión 11–18.
