# Documentación profesional: verificación del 90 %

**18/20 controles = 90 %**, con la misma rúbrica propia
[DOC-PRO-20-v1](DOCUMENTATION_PLAN_20261010.md). El objetivo ya se alcanzó en el
[resultado anterior](DOCUMENTATION_RESULT_20261010.md), integrado mediante
[PR 34](https://github.com/htroya/equiframe/pull/34). Esta revisión mantiene esa
medición; no anuncia un segundo incremento ni compara con el 85 % del chat,
cuyo cálculo no estaba documentado. No es certificación externa ni encuesta.

Base revisada: `75c7de1bf81208bfa351be148f0944644cf14bbe`, después del PR 35 de
preparación de PyPI. Fecha local: 2026-10-10, America/Guayaquil. El
[recibo de esta revisión](DOCUMENTATION_RECHECK_20261010.json) identifica alcance,
resultados nuevos, evidencias históricas verificadas y pendientes.

Candidato observado: `equiframe 0.12.0a13` y `equiframe-benchmark 0.12.0a13`.
SHA-256 del wheel del núcleo conservado:
`c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23`.
Un commit nuevo de documentación no cambia el origen ni los bytes del wheel.

## Qué aporta esta revisión

1. El [portal](README.md) muestra directamente el 90 %, su denominador y dos
   pendientes, con acceso al resultado original y a esta verificación.
2. Se corrige una incoherencia del [alcance de navegación](../tools/documentation_scope.json)
   y la [política de mantenimiento](DOCUMENTATION_MAINTENANCE.md): las páginas
   de evaluación enumeradas explícitamente sí se recorren para validar enlaces.
   Los demás informes se comprueban como destinos, sin recorrerlos recursivamente.
   Revisar enlaces no reescribe resultados, hashes ni aprobaciones históricas.
3. Esta página entra en el inventario; su versión del núcleo y del benchmark
   se contrasta con cada `pyproject.toml`, junto a las declaraciones existentes.
4. Se ejecutan los controles documentales manuales y se comprueba que los cuatro
   bloques registrados y el wheel siguen coincidiendo con su evidencia conservada.

## Validaciones y límites de la evidencia

La navegación actual comprueba archivos, anclas y versiones del inventario
explícito, incluyendo las páginas de preparación de PyPI. Sus conteos, hashes
y resultado quedan en el recibo JSON. Se ejecutan las 16 regresiones del
comprobador/registro en Python normal y con `-O`; no se crearon pruebas vacías
para aumentar el número de casos. Los destinos remotos se listan sin consultarlos;
no se afirma revisión visual, accesibilidad o disponibilidad pública.

Los cuatro ejemplos de [registro](../tools/documentation_examples.json) son
README, quick start, pipeline de tres estados y lectura del manual instalado.
La revisión calcula sus hashes extraídos y los contrasta con el recibo original.
También comprueba el SHA-256/CRC del archivo privado que conserva los ocho
intentos aprobados y el hash exacto de su recibo de ejecución. El wheel original
conservado se verifica por SHA-256. Son **ocho ejecuciones históricas válidas
para los mismos bloques/artefacto**, no ocho nuevas ejecuciones en esta revisión.
No se reutiliza el PASS si cambia el código del bloque o el wheel.

El resultado anterior identifica Windows/Python 3.12.4, 127 archivos instalados
idénticos al wheel y normal/optimizado. Esta revisión no reconstruye el paquete,
crea una nueva instalación ni repite suites completas del SDK/benchmark. La
[preparación de PyPI](PYPI_PREPARATION_RESULT_20261010.md) conserva aparte el
ejemplo propuesto y su instalación verificada; no se confunden ambos recibos.

## Qué comprende el 90 %

D01–D18 siguen completos: entrada por tareas, guías por rol, versiones actuales,
instalación privada, primer uso, API, CLI/gates, semántica, extensiones, ciencia
separada, recuperación, glosario, contribución, compatibilidad, integración,
límites de seguridad, comprobador manual y ejemplos vinculados a ejecuciones.
Cada control vale 5 puntos; bloqueados conservan cero dentro del denominador.
El plan original contiene las condiciones completas, sin modificar la rúbrica.

| Pendiente | Condición para completarlo |
|---|---|
| D19 | Una persona distinta del autor sigue la guía y registra dificultades reales |
| D20 | Manual público de esta distribución, accesible y con derechos aprobados |

La ejecución automática no sustituye al lector humano. Un repositorio privado
y una guía preparada no sustituyen documentación pública con licencia/permisos.
No se inventaron participantes, titulares o aprobaciones. Esos dos pendientes
limitan el índice al 90 %; no bloquean conservar el objetivo solicitado.

La entrega consiste en documentación y registro de validación en el repo privado
y su integración a `main`. Conserva SDK, manual empaquetado, fixtures, política
de publicación e informes anteriores. No hay Actions, publicación PyPI, servicio
nuevo, recursos de pago ni cambios en la VM `157.137.227.1`. La evidencia se
archiva fuera de Git antes de retirar los temporales propios de esta revisión.
