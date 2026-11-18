# Usabilidad vigente para arquitectura y ciencia de datos

Fecha: 2026-10-10. Candidato privado core/benchmark **0.12.0a12**.

**Resultado técnico: 11/12 criterios completos = 91,67 %. Objetivo >=90 % cumplido.**
Se conservan los doce criterios indivisibles y las 72 subcomprobaciones de
[la rúbrica existente](USABILITY_MATRIX.md). Cada criterio pesa uno; parcial o
bloqueado pesa cero. Las 64 subcomprobaciones técnicas están acreditadas y las
ocho de U12 humano siguen bloqueadas. Su cantidad no cambia el peso de cada
criterio. Es un índice propio de cumplimiento técnico, no satisfacción medida.

La tabla del chat con 80 % no identifica rúbrica, candidato o recibos: no permite
acreditar ese punto de partida. Git ya conservaba **11/12** para A7 el 2026-10-07.
Ese resultado histórico no se traslada a A12. La revisión inicial de main A11
encontró recetas activas A10, referencias antiguas por rol y metadatos del entorno
de desarrollo 0.11.1 junto a código A11. No se inventa un porcentaje inicial A11
ni un incremento medido de diez puntos. Se corrigieron esas brechas, se desarrolló
un primer uso más breve y se acreditó de nuevo el alcance técnico del candidato.

[Plan ejecutado](USABILITY_CURRENT_PLAN_20261010.md) ·
[Resultado y mapa de evidencia JSON](USABILITY_CURRENT_RESULT_20261010.json) ·
[Primer uso](../packages/equiframe/docs/first-use.md)

## Cinco pasos completados

| Paso | Implementación y utilidad |
|---|---|
| 1. Auditar | Misma rúbrica U01–U12; historia A7 separada; estados, identidades y límites actuales verificables |
| 2. Instalar | Versiones core/benchmark A12 y consumidor 0.1.14 coherentes; guías vigentes, extras mínimos, locks y seis distribuciones privadas identificadas |
| 3. Diagnosticar | `equiframe doctor`: Python, identidad código/metadatos, dependencias del extra, siguiente acción y JSON; sin instalar ni usar la red |
| 4. Completar tareas | `equiframe demo`: SQL/DuckDB para arquitecto y preparación Decimal/UTC/ID/NULL para científico, con esperado independiente y tres desenlaces; reportes guardados antes del gate |
| 5. Validar y entregar | Pruebas de API/CLI, semántica, datos históricos, reportes, instalaciones externas, consumidor y VM; documentación de evidencia e integración manual a main |

Los reportes de consola, HTML y notebook ponen motivo y siguiente acción antes
de las políticas extensas. Conservan estado, completitud, conteos, clave, columna,
tipos, límites y hechos del resultado. La vista minimizada permanece separada del
detalle sintético. Repetir una salida se rechaza y conserva el reporte anterior.

Ambos comandos nuevos están clasificados **experimentales**. `doctor` confirma
disponibilidad por metadatos, no prueba DLL, rangos de dependencias o ejecución
nativa. `demo` usa fixtures pequeños sintéticos, no traduce un pipeline arbitrario
ni acredita calidad científica de un dataset real.

## Criterios actuales

| Criterio | Alcance conservado | Estado | Evidencia del JSON |
|---|---|---|---|
| U01 | Entradas por rol y elección de API | CUMPLIDO | E_DOC, E_WIN |
| U02 | Instalación externa, extras, identidad y hashes | CUMPLIDO | E_DIST, E_WIN, E_VM |
| U03 | Gate y significado de los datos | CUMPLIDO | E_TEST, E_WIN, E_FAULT, E_CONSUMER |
| U04 | Causa, testigos y siguiente acción en tres vistas | CUMPLIDO | E_TEST, E_WIN, E_QA |
| U05 | Fallos, presupuestos y repetición segura | CUMPLIDO | E_TEST, E_FAULT, E_WIN, E_VM |
| U06 | Seis direcciones nativas del recorrido admitido | CUMPLIDO | E_TEST, E_CONSUMER |
| U07 | Ingestión, checkpoints y publicación local tras gate | CUMPLIDO | E_TEST, E_FAULT, E_DOC |
| U08 | Consumidor Python/SQL y pytest local | CUMPLIDO | E_TEST, E_WIN, E_CONSUMER, E_DOC |
| U09 | Preparación con ID, ausencias, Decimal y fechas | CUMPLIDO | E_TEST, E_WIN, E_VM, E_DOC |
| U10 | Coherencia, diagnóstico, actualización e historia | CUMPLIDO | E_DIST, E_DOC, E_WIN, E_LIFE |
| U11 | Consumidor independiente y matriz completa | CUMPLIDO | E_CONSUMER, E_DELTA |
| U12 | Personas, proyectos, consentimientos y retención reales | BLOQUEADO | E_HUMAN |

U11 conserva la aplicación independiente y sus cuatro programas. `0.1.9` en la
definición histórica es su etiqueta A7; la misma línea de consumidor llega a
0.1.14. La comparación con 0.1.13 comprueba sus ocho módulos Python iguales tras
sustituir solamente etiquetas de versión y finales de línea. No se reimplementó
el esperado con EquiFrame ni con un motor como oráculo.

## Comprobaciones actuales y límites

- **1.109 nodeids distintos del núcleo aprobados**, contando una vez cada caso:
  CLI/guías, comparación/contratos, reportes, migraciones, ingesta, checkpoints,
  snapshots y compatibilidad histórica. Son controles pertinentes a la rúbrica;
  no se anuncia una nueva ejecución de toda la suite del proyecto.
- **10 pruebas del benchmark** con la pareja final A12; alias conservados y
  esquema histórico con su SHA original. Ruff/formato/assets y mypy estricto
  completados: 96 archivos fuente de core comprobados por mypy.
- Windows x64 **Python 3.12.4 y 3.13.16**: 12 ejercicios CLI y 20 casos de guías
  completas por entorno, normales y `-O`. Los 127 miembros del paquete instalado
  coinciden exactamente con el wheel final. Las 24 repeticiones CLI rechazan la
  sobrescritura y conservan bytes. Resolución normal y locks completos con hashes,
  comprobación de dependencias e imports externos al checkout; sin editable,
  cambios de sys.path o `--no-deps` como evidencia del consumidor.
- Consumidor 0.1.14 instalado: **19 tests del runner**, **72 casos distintos**,
  **24 aceptaciones**, **48 rechazos esperados**, **cero fallos** y **144 ejecuciones
  nativas**. Cuatro programas, tres fuentes públicas permitidas y 219 registros
  crudos fijados; esperado stdlib independiente. Seis controles de fallo adicionales
  pasan bajo `-O`. Esta nueva matriz corresponde a Windows/Python 3.12; no se
  acredita otra matriz completa por extrapolación.
- VM existente Linux ARM64 **Python 3.12.15**: mismo SHA del wheel, instalación,
  salud, diagnóstico, 12 ejercicios y 12 repeticiones rechazadas. Se usó para
  comprobar instalación y primer uso nativo de ambos perfiles. Su entorno temporal
  fue retirado después de verificar un archivo de evidencia de unos 312 KiB;
  los servicios y el Python del sistema se conservaron.
- Actualización A11→A12, reversión a A11 identificado, desinstalación y reinstalación
  A12 en un entorno temporal Windows/Python 3.13: equivalencia acepta, diferencia
  y límite rechazan, también bajo `-O`. No es una prueba de todos los upgrades.
- Sdist final: **481 archivos tracked** vinculados con el commit; los finales de
  línea ordinarios se identifican explícitamente cuando difieren. Los fixtures
  históricos se comparan por bytes, sin normalización. **31 guías** son iguales
  entre wheel y sdist. Build de wheel desde sdist y Twine estricto de los seis
  artefactos; ningún archivo fue publicado en PyPI.
- Opera Neon con perfil QA dedicado, loopback y zoom inicial 75 %: identidad
  del reporte, veredicto, causa, acción y valores Decimal comprobados; se abrió
  el testigo del notebook. Sin desbordamiento horizontal ni errores finales de
  consola en desktop/móvil. Las tablas de siete columnas parten palabras en móvil:
  no se declara una experiencia móvil optimizada ni una sesión real de Jupyter.

87 módulos Python de core mantienen bytes exactos respecto al wheel A11. Cambian
versión/inventario/CLI/presentación y se añaden dos helpers; los comparadores,
contratos, compiladores y formatos persistidos no se modifican. Los recibos A11
revisados por hash se conservan como historia, no como ejecuciones A12.

## Fallos conservados y recuperación

Los intentos intermedios quedan en la evidencia privada, incluidos la mezcla
inicial de versiones durante una ejecución, el tmp de pytest con ACL insuficiente,
una instalación editable de desarrollo incompleta, dos comandos de ensayo con
nombres/firma incorrectos y una expectativa antigua del orden del reporte.
Los controles definitivos cubren las rutas corregidas; la ejecución parcial del
consumidor sobre el wheel anterior no se cuenta como matriz del wheel final.

Se recuperaron 16 fixtures históricos cuyo checkout Windows había cambiado LF
a CRLF. Se guardaron los bytes previos y se restauraron los blobs originales de
Git, sin reescribir procedencia o hashes. **386 casos de compatibilidad histórica**
pasan y están incluidos en los 1.109. Se conserva la regla `-text` anterior para
todo ese corpus y se añade una excepción precisa para el esquema SnapshotManifest
del benchmark. Tras esas correcciones, el wheel mantiene exactamente sus bytes;
los hashes del sdist final son independientes de los intentos descartados.

Un 404 de favicon del envoltorio local de QA se resolvió en ese servidor; no era
un fallo del resultado de comparación. La revisión móvil conserva la limitación
de tablas densas. No se omiten observaciones desfavorables para cerrar U12.

## Pendiente

U12 requiere tres proyectos independientes reales (refactor, SQL y CI), al menos
una persona de cada perfil, consentimientos y revisión humana de independencia,
ayuda/errores/interpretación observados, tres primeros diagnósticos <=300 segundos
con protocolo previo y un cambio posterior con integración retenida. No hay
observaciones humanas acreditadas. Los tiempos automáticos no aportan ese punto.

No se acreditan macOS, Linux x64 A12, Python 3.10/3.11 A12, todos los extremos de
dependencias, seguridad integral, SLA, licencia aprobada o servicio/DW productivo.
El 80 % de Universalidad sigue siendo el corte A11 y su rúbrica separada; este
trabajo no lo recalifica. Todo se ejecutó manualmente, sin Actions, infraestructura
nueva, servicios de pago o publicación pública.

La evidencia compacta y los seis artefactos privados se conservan fuera de Git.
El [JSON](USABILITY_CURRENT_RESULT_20261010.json) publica commit, definiciones,
selecciones de pruebas, hashes y límites sanitizados para revisar el cálculo.
