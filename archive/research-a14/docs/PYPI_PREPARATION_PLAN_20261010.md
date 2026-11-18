# Preparación para PyPI: plan PYPI-PREP-20-v1

Base: `a5a2f9812812118159c57f93615c4345e0adb096`, pareja privada A13. La cifra
60 % de la tabla histórica no identifica rúbrica, corte ni evidencias. Se fija
antes de implementar esta rúbrica propia de **20 controles, 5 puntos cada uno**.
Solo completo vale PASS; parcial, desconocido o bloqueado vale cero y permanece
en el denominador. El índice mide preparación; nunca autoriza una publicación.

## Criterios fijados y diagnóstico inicial

| ID | Condición para PASS | Inicial | Evidencia / carencia |
|---|---|---|---|
| P01 | Núcleo y benchmark independientes, con alcance/base/extras explícitos | PASS | Pyprojects y READMEs del par A13 |
| P02 | Identidades y versiones del par coherentes entre fuentes y artefactos | PASS | Recibo de calidad A13, hashes y metadatos |
| P03 | Backend/herramientas de construcción fijados y comandos repetibles | PASS | `hatchling==1.28.0`, locks, guías de construcción |
| P04 | Metadata técnica, Python, extras y entry points válidos | PASS | Pyprojects, METADATA, pruebas de distribución; licencia se mide en P17 |
| P05 | Dependencias de instalación sin rutas del autor/repos privados | PASS | Requires-Dist; benchmark exige exactamente el núcleo A13 |
| P06 | Auditoría conjunta wheel/sdist: inventario cerrado, metadata consistente, sin extracción ni ejecución y fixtures binarios explícitos | GAP | Auditor del wheel existente; falta auditoría conjunta del par y de sdists |
| P07 | Archivos y hashes del par identificados y conservados para entrega | PASS | Artefactos privados finales A13 y recibo de calidad |
| P08 | `twine check --strict` realmente ejecutado sobre esos cuatro archivos | PASS | Recibo de calidad A13; se repetirá el control específico |
| P09 | Reconstrucción desde sdist comparada con los mismos wheels en entorno identificado | PASS | Recibo A13: reconstrucción exacta Windows, no extrapolada a otros OS |
| P10 | Instalación base fuera del checkout y ausencia de motores/ML al importar | PASS | Recibo A13, 162 miembros de payload verificados |
| P11 | Extras/ejemplos prometidos comprobados en entornos observados, con límites de matriz explícitos | PASS | Recibos A13 Windows/Linux ARM64 y consumidor nativo; matriz global sigue abierta |
| P12 | Manual autocontenido distribuido y ejemplos básicos ejecutados desde texto | PASS | Manual A13 y DOC-PRO-20-v1, cuatro bloques/ocho intentos |
| P13 | Expediente manual distingue integridad de preparación/autorización y rechaza artefactos/configuración incorrectos | GAP | Falta expediente conjunto del par con los nuevos controles de contenido |
| P14 | Runbook manual de entrega exacta, sin Actions, glob indiscriminado ni credenciales en fuentes | GAP | Proceso existente orienta a workflow futuro; falta ruta manual completa |
| P15 | Ensayo local de validación fallida, subida parcial, duplicado y retirada/reversión con estados honestos | GAP | Hay rollback instalado; falta ensayo del proceso de publicación parcial |
| P16 | Consulta fechada de ambos nombres en PyPI/TestPyPI y sus límites | GAP | No hay observación actual del índice vinculada a esta preparación |
| P17 | Titulares y licencia aprobados, archivos/notices/metadata incluidos en nuevas distribuciones | BLOCKED | El usuario indicó que todavía no dispone de esa decisión |
| P18 | Acceso publicador/roles/2FA y estrategia de nombre acreditados en ambos índices | BLOCKED | No hay recibo de cuenta/control; una consulta no reserva nombres |
| P19 | Documentación y canal de incidencias públicos para esta distribución, con permisos aprobados | BLOCKED | Repositorio privado; links actuales requieren acceso |
| P20 | Par realmente subido a TestPyPI e instalado desde ese índice con hashes coincidentes | BLOCKED | No existe publicación de ensayo ni autorización/licencia que la habilite |

Inicial: **11/20 = 55 %** bajo esta rúbrica. Aspiración solicitada: 90 %.
Con los cuatro requisitos externos no acreditados, el máximo comprobable de
esta tarea es **16/20 = 80 %**. No se eliminarán esos criterios para anunciar
90 %. Llegar a 18/20 requiere completar al menos dos de P17–P20; cualquier
publicación sigue requiriendo todos los gates aplicables del roadmap.

## Cinco pasos

1. Revalidar normas oficiales PyPA/PyPI y consultar nombres sin autenticarse,
   guardar solo estado público y fecha, nunca tratar 404 como reserva disponible.
2. Crear auditoría offline conjunta del par A13 con hashes confiables, wheel y
   sdist cerrados y fixtures sintéticos binarios identificados por ruta/hash.
3. Preparar expediente y README de publicación propuesto, más un runbook manual
   con separación de índices, archivos exactos y recuperación de subida parcial.
4. Ejecutar pruebas negativas del expediente/proceso y Twine sobre los bytes
   originales; conservar pruebas instaladas anteriores como históricas, sin
   fingir una nueva construcción, instalación remota ni cierre de ciencia/seguridad.
5. Publicar los cambios revisables en el repo privado y fusionar a `main` dentro
   de la autorización vigente. Archivar recibos y retirar temporales propios.

No se elige licencia, asigna titular, crea cuenta, busca tokens, hace público el
repo, usa Actions ni sube a TestPyPI/PyPI en esta tarea de preparación. Se deja
lo no encontrado como pendiente, conforme a la instrucción del usuario.
STEP10, revisión global, seguridad, responsabilidades y aprobación del artefacto
exacto conservan sus gates; el porcentaje no los sustituye.

Fuentes: [empaquetado PyPA](https://packaging.python.org/en/latest/tutorials/packaging-projects/),
[formato sdist](https://packaging.python.org/en/latest/specifications/source-distribution-format/),
[TestPyPI](https://packaging.python.org/en/latest/guides/using-testpypi/),
[cuentas/nombres de PyPI](https://pypi.org/help/).
