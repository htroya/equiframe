# Consolidación privada posterior a la revisión global

Base verificada: `c4be1c5a29d9f58b2628882bd986de2bb5ca4184`, revisada el
2026-10-06. Rama dedicada: `consolidation/private-product-20261006`. El trabajo
continúa privado, sin publicación PyPI/TestPyPI, cambios de licencia/visibilidad,
servicios desplegados ni aceptación de producción o científica. La rama se
entrega para revisión; no hay autorización de merge a main para esta fase.

## Diagnóstico inicial priorizado

| Categoría | Base real y consecuencia |
|---|---|
| Implementado/comprobado históricamente | Comparación/diff/assert/reportes, captura, ejecución nativa, migración, Verify, ingestión/workflows, snapshots y bundles; no crear otros frameworks |
| Calidad histórica verificable | 2.949 casos core, 561 benchmark, 12 raíz; 12 celdas Linux del candidato previo. Las cuatro distribuciones conservadas coinciden byte a byte con el recibo anterior. Son evidencia histórica, no ejecuciones nuevas |
| Implementado con límites | IR nativo acotado, tipos por etapa, presupuestos cooperativos, fuente externa con cliente inyectado, formatos versionados; no promesa universal de motores/tipos/volúmenes |
| Brecha de producto | 351 exports sin una entrada española progresiva y solo tres recetas de instalación; faltaban ocho recorridos completos y una integración SQL externa transaccional |
| Brecha de arquitectura | Evidencia/reporte/modelos consumían I/O privado de perfiles; Verify consumía validación física privada del migrador |
| Brecha de automatización | Matrices costosas bajo disparo explícito, sin una capa rápida automática para cambios/PR |
| Pendiente/no acreditado | Auditoría de seguridad de código interrumpida, pilotos humanos, diagnóstico de cinco minutos, plataformas restantes, corpus y aceptación DW reales |
| Fuera del núcleo | Cliente/servicio/snapshots operativos e infraestructura de José; políticas/modelo/carga y aceptación DW de Jhair; decisiones del dueño sobre licencia/publicación |

## Cambios de arquitectura y producto

- Se reutilizan todas las entradas existentes. El [inicio español](../packages/equiframe/docs/inicio.md)
  guía hacia cinco operaciones habituales y la [elección de API](../packages/equiframe/docs/choosing-api.md)
  separa comparación, captura, ejecución, migración, Verify y orquestación
- Los [resultados operativos](../packages/equiframe/docs/outcome-gates.md) rechazan
  `bool(...)` en lugar de aprobar por existencia. Se conserva el significado de
  estados/campos y las comprobaciones opcionales usan `is not None`; es un cambio
  observable de Python explicado en la guía de actualización
- `_document_io` y `_physical` extraen responsabilidades genéricas idénticas,
  manteniendo aliases. No unifican serializaciones distintas, huellas ni formatos
- El [control de arquitectura](../packages/equiframe/tools/check_architecture.py)
  incluye imports absolutos/relativos y expone ciclos estáticos locales/de tipos,
  sin llamar acíclico al grafo completo ni afirmar cubrir carga dinámica
- El [productor SQLite externo](../packages/equiframe/docs/sqlite-snapshots.md)
  usa los puertos vigentes y una transacción de lectura propia. Se demuestra
  consistencia ante un commit WAL entre lecturas, bytes desacoplados, Decimal/NULL
  fieles, identidad fijada y fallos visibles. No es el servicio de José
- [A–H](../packages/equiframe/docs/journeys.md) tienen datos pequeños sintéticos,
  esperado literal independiente, aceptación correcta/negativa y evidencia
  reproducible. La publicación C es Parquet local, no publicación del paquete
- Los scripts se incluyen de forma explícita en el wheel, sin cachés generadas.
  El verificador de payloads y la vinculación de dependencias locales incorporan
  esos bytes; el mismo número de versión no permite aceptar código viejo
- La [capa rápida](../packages/equiframe/docs/fast-ci.md) usa acciones fijadas,
  permisos de lectura y ejecución local. Por petición posterior del dueño, todos
  los workflows quedan bajo disparo manual; ningún push o PR inicia Actions.
  La configuración no demuestra que una comprobación remota haya pasado

### Decisión posterior sobre GitHub Actions

El dueño autorizó retirar los disparadores automáticos de push/pull request para
no consumir minutos de Actions durante este trabajo. `workflow_dispatch` permanece
disponible; activarlo manualmente en GitHub sí consume sus minutos. La misma
selección y las comprobaciones completas se ejecutan en la nube de trabajo.
El primer run automático falló antes de ejecutar pasos y se conserva como fallo;
su causa de arranque no está verificada y no se atribuye a falta de minutos.
No se redujeron pruebas, permisos o condiciones de aprobación para ocultarlo.

## Resultados y evidencia de esta fase

El recibo final externo a la fuente identifica commit/árbol, estado de cada
comando, versiones resueltas, hashes de wheel/sdist, instalación aislada y celdas
realmente ejecutadas. Cada intento fallido de desarrollo queda distinguido de los
controles del código congelado. Repeticiones y escenarios de una suite no se
cuentan como nuevos casos distintos; no se reutiliza un total histórico como
resultado del candidato nuevo. La evidencia final acompaña la rama privada.

Ruff, formato, mypy, esquemas, propiedades/regresiones, pruebas completas,
construcción/Twine y consumidores externos deben pasar para el cierre técnico.
La matriz ejecutable conserva seis direcciones nativas y separa captura,
comparación, ejecución y migración. No se declaran Windows/macOS/ARM ni otros
entornos por el mero hecho de que un workflow los configure.

## Medición y límites

La herramienta [de medición acotada](../packages/equiframe/tools/measure_bounded.py)
reutiliza el supervisor existente, perfiles pequeños y resultados esperados.
Incluye diferencia final, muchas diferencias, duplicados, texto ancho, evidencia
de disco y suplemento Decimal. El suplemento separa costos adicionales de
captura/conversión/hash/persistencia del `diff` completo: no suma tiempos solapados
como si fueran un desglose interno. No hay muestreo para certificar igualdad.

Se conservan repeticiones, entorno, identidad de código y campos de observaciones
faltantes. El host compartido y el muestreo final de I/O denegado impiden convertir
los valores en cuotas duras o una comparación porcentual controlada. No se hizo
una optimización de velocidad ni se anuncia una mejora porcentual. El caso de
disco es un volumen acotado, no agotamiento deliberado del equipo; la falta de
espacio se comprueba mediante fallo sintético controlado del escritor.

## Cobertura de seguridad pendiente

No se retomó la auditoría detenida mediante otra herramienta ni una revisión
manual equivalente. Continúan pendientes la observación de archivos especiales
en bundles y la clasificación del límite de captura; no se afirma corrección,
severidad confirmada ni aceptación tácita. Los cambios de esta fase son de
funcionalidad/arquitectura y no completan esa evaluación.

La lectura fresca de fuentes oficiales para CVE-2026-25087 se conserva separada
del inventario y escaneo históricos. Apache excluye los bindings Python porque
la funcionalidad C++ afectada no está expuesta por ellos; eso no valida todas las
rutas de EquiFrame ni convierte otras alertas o versiones en limpias. Los SBOM
nuevos son inventarios offline ligados a artefactos; no un nuevo escaneo global.
Véase [seguridad y límites](../packages/equiframe/docs/security.md).

## Conservación y siguientes decisiones

La tesis, formatos históricos, imports/aliases y separación R/M/B/H/O se
conservan. Pandas no es un oráculo; acuerdo nativo no prueba verdad del dominio.
La hoja de ruta reforzada permanece fuera de Git y la histórica no se elimina.

Quedan sujetos a evidencia/autorización separada: revisión de la rama y eventual
merge, cierre de seguridad, participantes humanos, soporte de plataformas,
servicios/DW reales y decisión de licencia/publicación. Ninguno impide completar
las correcciones privadas independientes descritas aquí.
