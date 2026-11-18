# Plan de usabilidad verificable U01–U12

Congelación inicial: 2026-10-07, antes de nuevas pruebas de este plan.
Base remota comprobada: `a9f4813f33341ca9bf5f744bcc7de4f50877e15c`;
árbol `beecbec19268761cfbcfbbbc6125e9b8193b4a3e`.
Rama: `product/usability-20261007`. La recuperación local tiene otro commit
legítimo, `e1736c90e159e97be0779a76d069bf6d8af19eef`, con el mismo árbol;
no se atribuye a esa copia la historia remota original.

## Alcance fijo

El índice mide doce criterios binarios de este alcance, no satisfacción ni
cobertura universal. No existe una línea base porcentual anterior válida.
Los subcriterios y su evidencia se registran en [la matriz](USABILITY_MATRIX.md).
Una declaración de soporte o una prueba escrita no acredita ejecución.

- Producto privado: núcleo y benchmark 0.12.0a7; consumidor independiente 0.1.9
- Entornos observados: Debian 13, Linux x86_64, CPython 3.12.14 y 3.13.5.
  Se conservan los extremos mínimos-directos compatibles y recientes-permitidos
  ya ejecutados, con locks distintos por perfil/entorno. Los perfiles base,
  arrow, pandas, polars, duckdb, engines, ml y all del núcleo y base, engines,
  ml, resources y all del benchmark siguen visibles. No se ejecuta de nuevo
  esa matriz si código, metadatos de dependencias y artefacto siguen iguales
- Windows x64, macOS Intel/Apple Silicon, ARM64, otros intérpretes y cualquier
  combinación no medida permanecen sin verificar. Sus instrucciones preparadas
  no se presentan como ejecución. No se retiran tras observar un fallo
- Recorridos: comparación y reporte; integración Python/SQL-DuckDB y pytest
  local; migración nativa en las seis direcciones pandas/Polars/DuckDB;
  CSV y JSON/JSONL según admisión, checkpoints y Parquet local;
  preparación con IDs, ausencias, Decimal y timestamps
- Ejemplos publicables: sintéticos, de 2–4 filas. Se reutilizan los A–H y
  las cuatro aplicaciones del consumidor. Los 219 registros congelados del
  consumidor permanecen fuera de Git y se usan solo con su procedencia/permiso
- APIs: diff, read_diff_contract, comparison_report, write_comparison_report,
  assert_equivalent, capture_duckdb, DataSource/SnapshotDataSource, migrate,
  ingest_file, run_workflow y ParquetDestination. Sin una segunda API
- ML/perfiles y benchmark científico son rutas separadas: no se entrenan modelos,
  cambian hipótesis/particiones ni se mezclan R/M/B/H/O. No es auditoría de
  seguridad, inventario exhaustivo de opciones, aceptación del servicio/DW,
  publicación PyPI/TestPyPI ni ejecución de Actions

## Diagnóstico y bloques priorizados

1. P1/P2, orientación/instalación: journeys.md mezcla una receta histórica
   0.11.1 con el candidato A7 y --no-deps; aclarar la receta vigente y mantener
   la histórica identificada. Reusar instalación normal y lock completo
2. P2, roles/diagnóstico: completar entradas españolas para arquitecto y
   científico. Usar firmas existentes; el reporte se guarda antes de rechazar.
   Probar los fragmentos completos fuera del checkout, también con Python -O
3. P2, alcance coherente: corregir el límite temporal demasiado general del
   recorrido E y las cabeceras actuales que aún dicen 0.11.1. No reescribir
   secciones históricas ni ampliar las capacidades reales de los compiladores
4. P1 si una prueba revela un recorrido roto; P0 si revela aceptación falsa o
   pérdida/corrupción: preservar la observación, reducir un caso permitido,
   corregir mínimamente y repetir controles afectados sobre artefactos finales
5. Enlazar recibos compatibles U02–U11 y ejecutar solo brechas documentadas.
   La matriz completa del consumidor significa exactamente 72 casos, no muestra
6. Preparar protocolo U12 y lista de decisiones externas U10. Sin inventar
   participantes, consentimientos, resultados, responsables, canales o SLA

## Presupuesto previo y preservación

Una ejecución de prueba por vez. VM observada: 9.7 GiB RAM, sin swap, 5.4 GiB
libres en disco al iniciar. Reserva mínima: 4 GiB disco y 2 GiB memoria disponible.
Objetivo por ejemplo: <100 filas, <64 MiB evidencia, límite externo 120 s;
por bloque acotado: 15 minutos y 512 MiB nueva evidencia. Instalaciones aisladas
pueden necesitar hasta 1.2 GiB adicionales: comprobar disponibilidad antes y
serializar. No ejecutar estrés, OOM, llenado de disco ni instalaciones globales.
Los límites internos de EquiFrame siguen siendo cooperativos.

Mantener entradas, logs, fallos y recibos fuera de Git. No limpiar entornos
ajenos; conservar artefactos/locks para reconstruir entornos descartables propios
solo tras recibo explícito de preservación. Cada cambio que afecte bytes crea
un artefacto identificado y reabre los controles afectados. No rebautizar un
pase histórico como ejecución nueva.

## Reutilización y revisión final

El A7 original está identificado por wheel SHA-256
`5d435e75a79754ab45c8a27f7d30ff513c006034bdddbff170ec9506816b9ff0`.
Se retienen 52 instalaciones, 8 suites normales, 4 grupos lifecycle, pruebas de
extras ausentes y 16 ensayos sdist/canal. El consumidor tiene 72 casos distintos,
576 ejecuciones principales y una repetición relocalizada de 72; 192 aceptaciones
principales y 384 rechazos esperados. Estos son hechos del artefacto original,
no pruebas humanas ni pases automáticos de futuros wheels.

La reutilización exige verificar hashes y ámbito exacto; los recibos nuevos
mostrarán qué contenido cambió. Si solo cambian guías empaquetadas, se puede
conservar la versión privada con una revisión documental de bytes distinta:
no mezclar ambos wheels del mismo nombre en un wheelhouse. Demostrar identidad
de todos los módulos/formatos/dependencias y verificar instalación, distribución
y ejemplos afectados del wheel final. Si cambia comportamiento o dependencias,
versionar núcleo/benchmark/consumidor cuando corresponda y repetir sus puertas.

## Pilotos y dependencias externas

U12 requiere tres proyectos reales independientes: refactor Python,
SQL/DuckDB y regresión CI; al menos una persona con tareas de arquitectura y
una con tareas de ciencia de datos. Hernán coordina permisos y participantes.
Se necesita consentimiento y revisión humana de independencia, intentos/ayuda,
interpretación correcta, utilidad y cambio posterior real con integración retenida.

El reloj se fija antes: preparar Python y obtener el kit se registran aparte;
desde iniciar la instalación hasta el primer diagnóstico correcto se incluyen
las descargas, reintentos y ayuda. Las tres primeras observaciones elegibles
requieren <=300 s y ninguna instrucción esencial fuera de la guía. Un fallo
permanece registrado; practicar no convierte un reintento en primer uso.
Revalidar primer uso requiere nuevas personas independientes. Tiempo automático
no es tiempo humano. El protocolo detallado se integra en adoption.md.

Responsables/respaldos/canales de soporte y posibles compromisos siguen bajo
aceptación del titular. No se asigna a nadie una obligación por aparecer como autor.
José conserva transporte, credenciales, cuotas/reintentos y gateway; Jhair
conserva DDL, semántica y carga del DW. No se simulan sus entregas reales.

Cierre: 100 × CUMPLIDOS / 12. PARCIAL, NO_EJECUTADO y BLOQUEADO aportan cero;
ningún criterio sale del denominador. Sin observaciones humanas U12 sigue abierto.
La instrucción posterior de Hernán autoriza integrar al final en main los cambios
validados; esta rama se revisa antes de esa integración. Actions siguen manuales.
