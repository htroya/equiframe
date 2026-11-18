# Documentación profesional: 18/20 = 90 %

Rúbrica propia **DOC-PRO-20-v1**, fijada en el [plan previo](DOCUMENTATION_PLAN_20261010.md).
Seis controles ausentes/parciales se completaron; los doce controles existentes
se conservaron. **12/20 → 18/20, de 60 % a 90 %** dentro de esta misma rúbrica.
Cada control completo vale 5 puntos; pendientes valen cero y permanecen en el
denominador. No es una certificación externa ni una encuesta. La cifra antigua
85 % no tenía método/artefacto identificable y no se compara con esta medición.

Base auditada: `cc6b168a9e6c0fd0c48fe1d4d6e037b0b2b24069`.
Implementación de guías/herramientas: `3a10ac4238555bb8acaf9f201dd80fb2034b7fcb`;
el commit posterior completa este recibo y ajusta el patrón de versión del
benchmark para excluir el punto de cierre de la frase. No cambia código del SDK.
Pareja privada core/benchmark `0.12.0a13`.

## Cambios útiles para el lector

1. [Portal por tareas](README.md): primer uso, arquitectura, análisis, extensión,
   diagnóstico, contribución e investigación, con recibos históricos separados.
2. Encabezados de [arquitectura](ARCHITECTURE.md), [API](API_CONTRACTS.md) e
   [integración](TEAM_INTEGRATION.md) conciliados con A13. Se conservan las
   secciones de evolución, responsabilidades y pendientes científicos reales.
3. [Glosario bilingüe](DOCUMENTATION_GLOSSARY.md): contrato, referencia, snapshot,
   multiplicidad, estados, hashes y versiones con enlaces canónicos.
4. [Recorrido de pipeline](DOCUMENTATION_WORKFLOW.md): evidencia antes del gate,
   equivalencia aceptada, diferencia rechazada y referencia inválida rechazada.
5. [Política de mantenimiento](DOCUMENTATION_MAINTENANCE.md): comandos manuales,
   inventarios de alcance/ejemplos y reglas para no atribuir recibos viejos a
   nuevos artefactos. Los controles no se convierten en Actions.

## Criterios completos y pendientes

| ID | Resultado | Evidencia principal |
|---|---|---|
| D01 | PASS, nuevo | Portal `docs/README.md`, entrada en README raíz |
| D02 | PASS, existente | Primer uso y guías por rol del manual |
| D03 | PASS, corregido | README, arquitectura, API y controles de versión contra ambos pyproject |
| D04 | PASS, existente | Instalación privada, quick start y dependencias |
| D05 | PASS, existente | Primer uso, quick start y recetas sintéticas |
| D06 | PASS, existente | Referencia de API y selección de servicio |
| D07 | PASS, existente | CLI, códigos de salida y gates explícitos |
| D08 | PASS, existente | Semántica, contratos y políticas de tipos/ausencias/claves |
| D09 | PASS, existente | Extensiones, fuentes, snapshots SQLite y límites nativos |
| D10 | PASS, existente | Benchmark separado y trazabilidad de tesis |
| D11 | PASS, existente | Recuperación, mantenimiento y diagnóstico |
| D12 | PASS, nuevo | Glosario bilingüe enlazado |
| D13 | PASS, existente | Contribución y propiedad de componentes |
| D14 | PASS, existente | Compatibilidad, changelogs y releases/recuperación |
| D15 | PASS, corregido | Integración actual A13, VM de validación y entregas pendientes diferenciadas |
| D16 | PASS, existente | Seguridad, privacidad, recursos y auditoría offline |
| D17 | PASS, nuevo | Control manual: archivos/anclas, inventario y diez declaraciones de versión |
| D18 | PASS, nuevo | Cuatro bloques exactos del texto, ocho ejecuciones desde wheel instalado |
| D19 | BLOCKED | Falta una persona independiente que siga la guía y registre dificultades |
| D20 | BLOCKED | Falta documentación pública de esta distribución con derechos aprobados |

Para el detalle de las guías existentes y condiciones de aceptación consulta el
plan fijo. El [resumen JSON](DOCUMENTATION_RESULT_20261010.json) incluye los IDs,
estados, hashes de bloques, intentos finales y límites; no contiene datos reales
ni credenciales. D19/D20 no se cierran mediante simulaciones o aprobaciones
inventadas. El siguiente avance requiere esos hechos externos.

## Validación ejecutada

- Navegación offline: 44 documentos actuales, sus destinos locales y anclas de
  encabezados; **0 errores** en el intento final. Diez comprobaciones explícitas
  de versión concordantes con los metadatos del núcleo y benchmark. El recibo
  privado de navegación conserva cada documento/hash y el conteo exacto de
  enlaces; los destinos remotos quedan listados sin ser consultados.
- Herramientas: **16 pruebas distintas**, todas PASS tanto normal como `-O`.
  Incluyen archivo/ancla ausentes, versión equivocada, ruta fuera del repo,
  registro vacío/duplicado, fence mal cerrado, código ficticio dentro de otro
  bloque, salida esperada obligatoria y prohibición de sobrescribir recibos.
- Ruff y formato de las tres fuentes nuevas: PASS; `git diff --check`: PASS;
  `pip check` del consumidor instalado: PASS.
- Cuatro bloques completos registrados: README raíz, quick start, pipeline de
  tres estados y lectura del manual instalado. Se extraen sin reescribir su
  código, con hash LF por bloque. **4 × 2 modos = 8 intentos PASS**, salida 0 y
  marcadores independientes de `assert`, con `-I -X utf8` y `-O` cuando procede.
- Entorno observado: Windows AMD64, Python 3.12.4, Arrow 25.0.1, Pydantic 2.13.5,
  Typer 0.27.2. No se extrapola a otras combinaciones OS/Python.

Wheel del núcleo utilizado:
`c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23`.
El auditor offline verifica el hash confiable, inventario/RECORD e identidad
antes de los ejemplos. **127 miembros del paquete instalado** coinciden en
bytes con ese wheel y la importación queda fuera del checkout. No se reconstruyó
ni cambió el wheel para hacer pasar la documentación.

| Bloque | SHA-256 del código extraído con LF | Normal / `-O` |
|---|---|---|
| README | `6ac2087fb7336ea2758ab33c2e52573a91a6fc7350620657d31a93ab8aa1fdcf` | PASS / PASS |
| Quick start | `79febc903940cca52c76bcb0876388fc84e5160d3bd36d552bbef3f052b6fa52` | PASS / PASS |
| Pipeline tres estados | `a29992f7abab0dc31ee5fffd735109116dcfcf25eed1eed4c0fc5da7cbc87304` | PASS / PASS |
| Lectura del manual | `a9deed567052cae3359aa2298d3813d4304118b5c1a18d5065bc8fd77b533a06` | PASS / PASS |

## Fallos encontrados y corregidos

La primera ejecución del tutorial usó clave duplicada en el candidato y esperó
`not_evaluable`: el resultado real fue `different` contra una referencia válida.
Se corrigió la explicación y el ejemplo para usar una **referencia esperada
inválida**, sin cambiar políticas, algoritmos ni esperados históricos. Dos
intentos iniciales fallidos se conservan, junto con los dos finales PASS.

La lectura del manual instalado falló dos veces al imprimir Unicode bajo salida
redirigida Windows cp1252. El control ahora ejecuta y captura UTF-8 explícito;
la política explica `-X utf8` para esa situación. El texto empaquetado permanece
intacto. El intento inicial tuvo 4 PASS / 4 FAIL; el final tuvo 8 PASS / 0 FAIL.
Un control ampliado capturó el punto de cierre como parte de la versión A13:
se corrigió ese patrón del manifiesto; no era un cambio de versión del paquete.

## Alcance, entrega y límites

Las herramientas nuevas pertenecen al repositorio. Los enlaces, headings y
ejemplos seleccionados se comprueban manualmente; no es validación general de
HTML, todos los fragmentos de código, disponibilidad remota, accesibilidad
visual o satisfacción humana. No se ejecutaron navegadores en esta tarea.
Los informes fechados anteriores conservan sus datos y no entran en el recorrido
de enlaces actual, aunque sí se comprueba que sus destinos enlazados existan.

No cambia ningún archivo bajo `packages/`: código, manual empaquetado, esquemas,
locks, fixtures y distribución A13 permanecen iguales. Por eso se ejecutaron los
controles específicos de documentación y sus ejemplos reales; no se anuncia
una nueva repetición de las suites completas del SDK/benchmark. Universalidad,
trazabilidad, calidad de paquete y usabilidad humana conservan sus recibos y
denominadores independientes. No se modifica un porcentaje de otro aspecto.

El despliegue de esta mejora es la integración privada del código y guías en
`main`; no requiere un servidor documental. La VM 157.137.227.1 y sus kits y
backups anteriores quedan intactos: esta tarea se validó en Windows, sin crear
un servicio ni alegar una nueva prueba en la VM. Se archivan recibos y salidas
privadas antes de retirar el entorno temporal. Sin Actions, PyPI, sitio público
nuevo ni recursos de pago.
