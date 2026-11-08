# Preparación para publicar en PyPI: resultado verificable

**Resultado: 16/20 = 80 %** en la rúbrica propia **PYPI-PREP-20-v1**, fijada en
el [plan](PYPI_PREPARATION_PLAN_20261010.md) antes del desarrollo. Cada control
completo vale 5 puntos; bloqueado, parcial o desconocido vale cero y permanece
en el denominador. Es un índice interno, no una certificación PyPA ni permiso
de publicación. La meta solicitada de 90 % aún no es acreditable.

Diagnóstico inicial con la misma rúbrica: **11/20 = 55 %**. Se cerraron cinco
carencias técnicas: **25 puntos porcentuales**. El 60 % del chat no identificaba
criterios, corte ni pruebas; no se usa como base comparable. Los otros aspectos
y sus recibos históricos conservan sus mediciones propias.

Fecha local: 2026-10-10, America/Guayaquil; consultas/pruebas también registradas
en UTC del 2026-10-11. Base: `a5a2f9812812118159c57f93615c4345e0adb096`.
Plan previo: `7de7e45`. Herramientas/pruebas nuevas:
`946f9bb9a93d1b6619cb597a77aa1c62db2e6de5`. Este resultado y portal son seguimiento
documental de ese código, no el código que produjo los wheels A13.
El [recibo estructurado](PYPI_PREPARATION_RESULT_20261010.json) conserva controles,
hashes y límites; la evidencia cruda queda fuera de Git en
`respaldo_equiframe_20261010`, separada de entornos temporales.

## Qué se implementó y para qué sirve

- [Auditoría conjunta offline](../tools/prepare_pypi.py): identifica exclusivamente
  wheel/sdist del núcleo y benchmark, verifica hashes/tamaños, RECORD, metadata
  idéntica por distribución y pin exacto del núcleo. Revisa el tar en memoria
  con límites, sin extracción ni ejecución del candidato.
- [Manifiesto A13](../tools/pypi_candidate_a13.json): cuatro originales y 21
  fixtures Arrow históricos permitidos por ruta/hash, coincidentes con Git.
  No admite por excepción todo el directorio. Rechaza rutas privadas/de entorno/
  credenciales y datos/modelos binarios ajenos al inventario; no es un escaneo
  completo de secretos incrustados en texto.
- [Observador de nombres](../tools/probe_pypi_names.py): cuatro consultas JSON
  públicas fechadas, sin autenticación. Una ficha ausente nunca acredita reserva
  ni disponibilidad; errores se mantienen como UNKNOWN.
- [Guía manual de entrega](PYPI_MANUAL_RELEASE.md): archivos exactos, índices
  separados, hashes, subida parcial/conflicto, promoción y recuperación.
  El [README propuesto](PYPI_README_DRAFT.md) tiene un ejemplo ejecutado desde
  su texto; el borrador no modifica el README contenido en A13.
- [Regresiones del proceso](../tests/test_pypi_preparation.py): adulteración,
  rutas peligrosas, links, presupuestos, tamaños inválidos, aprobaciones falsas,
  recibos existentes y estados locales de entrega.

La auditoría devuelve **3** cuando la integridad pasa y la publicación sigue
bloqueada; entrada/recibo rechazado devuelve **2**. No tiene modo de subida ni
argumento para habilitar la política. `publication_ready`, `published` y
`upload_available` permanecen **false**. La [política vigente y sus siete
decisiones](../packages/equiframe/tools/release-policy.json) conservan el bloqueo.

## Archivos realmente comprobados

El par sigue siendo **0.12.0a13**, Alpha privada. No se reconstruyeron ni
modificaron originales. Código empaquetado:
`5e1465aa038a8fd463f83c8684768c4d9dc612e1`; pruebas A13 anteriores:
`96769ad15d0807a501e6141725c8d4198d7715b0`.

| Archivo | Bytes | SHA-256 |
|---|---:|---|
| equiframe-0.12.0a13-py3-none-any.whl | 461570 | `c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23` |
| equiframe-0.12.0a13.tar.gz | 1524480 | `164b70270344343094dc0a688bf8dbfe20a27112f7227e2f7fe318f085b71935` |
| equiframe_benchmark-0.12.0a13-py3-none-any.whl | 127142 | `fb843318d044a36a7ba4efab7d7d997d45798e12d16df7a9aa1b472b2c6359d8` |
| equiframe_benchmark-0.12.0a13.tar.gz | 434163 | `4f8c47a00a8724b234e87c0a7147e193092122c77772e9169bd954744dd6e9c7` |

SHA-256 del manifiesto con LF, idéntico al blob del commit de herramientas:
`d33ccdb807b855fa048ea6eb55ddd5730595b20c79e99210088e0d2510f9b7cc`.
El recibo inicial de desarrollo usó CRLF (`c4746517…`); se conserva separado.
Normalizar comprobó igualdad de valores JSON, sin alterar los artefactos.

Se verificaron **170 miembros RECORD** (131 núcleo, 39 benchmark), **616 archivos
sdist** (492/124) y **21 fixtures binarios** del núcleo. Los 127 archivos de
payload instalado del núcleo excluyen metadata; no son el inventario RECORD.
La licencia no está aprobada y estos artefactos no contienen License-Expression/
License-File. Corregirla exige nuevos bytes y nuevos recibos.

## Validaciones actuales y evidencia histórica

| Control ejecutado ahora | Resultado y alcance |
|---|---|
| Pruebas nuevas normales | 22 métodos distintos, todos PASS, cero fallos |
| Mismos métodos con `-O` | 22 PASS; 44 ejecuciones entre ambos modos, no 44 casos distintos |
| Ruff y formato, tres archivos Python nuevos | PASS |
| `twine check --strict`, cuatro originales | Cuatro PASS, salida 0 |
| Auditoría con manifiesto definitivo, normal y `-O` | Dos salidas nativas 3; integridad PASS y publicación bloqueada |
| Recuperación local | ABSENT, PARTIAL, COMPLETE_OBSERVATION, CONFLICT y ausencia tras retirada simulada; inventario conservado, autorización falsa |
| Ejemplo del README propuesto, normal y `-O` | Un bloque, dos PASS; B cambia de 20 a 21 y el gate rechaza |
| Instalación temporal del wheel local con Arrow | Windows/Python 3.12.4, Arrow 25.0.1; 127 archivos idénticos al wheel fuera del checkout; `pip check` PASS |
| Comparación de paquetes/workflows con main anterior | Sin cambios en `packages/` ni `.github/` |

Recuperación usa **observaciones locales suministradas**: no es una subida,
consulta autenticada, yank real ni rollback instalado. El rollback
A12→A13→A12→A13 es evidencia histórica separada del
[recibo de calidad](PACKAGE_QUALITY_RESULT_20261010.md), junto a las suites
completas, reconstrucción sdist→wheel, import base y extras Windows/Linux ARM64
ligados a estos mismos hashes. No se afirma una nueva ejecución de las suites
completas ni toda la matriz. Manual distribuido y cuatro bloques/ocho intentos
anteriores: [recibo documental](DOCUMENTATION_RESULT_20261010.md). Los dos
intentos del borrador nuevo son adicionales. La navegación del ámbito ampliado
y sus conteos figuran en el recibo estructurado.

Un fixture de wheel válido omitía `py.typed`: produjo cuatro fallos y un error
antes de corregir **el fixture**, sin relajar el auditor ni modificar A13.
Se corrigieron orden de imports, tipo del rechazo JSON y tamaño obligatorio.
Los diagnósticos se conservaron; el resultado final es posterior a esas correcciones.

## Consulta pública de índices

A las **2026-10-11 02:51:24 UTC** respondieron 404 las cuatro APIs JSON:
`equiframe` y `equiframe-benchmark` en PyPI y TestPyPI. Solo se observó ficha
no visible; no reserva, titularidad ni acceso publicador. PyPI indica que un
nombre sin ficha no necesariamente está disponible. [Ayuda de PyPI](https://pypi.org/help/).
GitHub confirmó repo **privado**, predeterminada `main` y `license=null`.
Eso no sustituye la decisión de derechos; las URLs actuales requieren acceso.

## Resultado de los 20 controles fijos

| ID | Control | Antes | Resultado |
|---|---|---|---|
| P01 | Núcleo/benchmark independientes y extras explícitos | PASS | PASS |
| P02 | Identidades/versiones coherentes | PASS | PASS |
| P03 | Backend/herramientas y construcción repetibles | PASS | PASS |
| P04 | Metadata técnica y entry points | PASS | PASS |
| P05 | Dependencias instalables sin rutas privadas | PASS | PASS |
| P06 | Auditoría conjunta y contenido binario explícito | GAP | PASS |
| P07 | Cuatro originales y hashes conservados | PASS | PASS |
| P08 | Twine estricto sobre originales | PASS | PASS |
| P09 | Reconstrucción sdist comparada | PASS | PASS histórico |
| P10 | Base fuera del checkout/import ligero | PASS | PASS histórico |
| P11 | Extras/entornos observados con límites | PASS | PASS histórico |
| P12 | Manual distribuido y ejemplos desde texto | PASS | PASS |
| P13 | Expediente que conserva gates y rechazos | GAP | PASS |
| P14 | Runbook manual de entrega exacta | GAP | PASS |
| P15 | Ensayo local de fallos/entrega/recuperación | GAP | PASS |
| P16 | Observaciones públicas fechadas y límites | GAP | PASS |
| P17 | Licencia/titulares/notices/metadata aprobados | BLOCKED | BLOCKED |
| P18 | Cuentas/roles/2FA/control de nombres | BLOCKED | BLOCKED |
| P19 | Documentación/incidencias públicas con derechos | BLOCKED | BLOCKED |
| P20 | Upload e instalación reales de TestPyPI | BLOCKED | BLOCKED |

## Lo que falta para el 90 % solicitado

Completar **al menos dos** de los cuatro pendientes lleva el índice a
18/20 = 90 %. Crear archivos o simularlos no cumple las condiciones:

1. **P17:** decisión real de titulares y régimen de distribución; incluir
   licencia/notices y metadata en ambos formatos, reconstruir y revalidar.
2. **P18:** acceso publicador autorizado, roles, 2FA/recuperación y estrategia
   de nombres acreditados separadamente en ambos índices.
3. **P19:** manual y canal de incidencias públicos con derechos aprobados y
   enlaces válidos desde las nuevas distribuciones.
4. **P20:** tras gates/autorización, subir el par a TestPyPI y comprobar
   descargas, hashes, instalación y funcionamiento realmente desde el índice.

Secuencia aconsejada: licencia/responsabilidades, acceso/nombres y canal público,
nuevo candidato, ensayo de TestPyPI y revisión final. **Todos los gates siguen
siendo obligatorios aunque el índice llegue a 90 %.** STEP10, revisión global/
independiente, dependencias/seguridad y aprobación de versión/hashes siguen
pendientes. Lo no encontrado se conserva como pendiente, según la instrucción
del usuario; no se inventaron titulares, licencia, cuentas ni aprobaciones.

La entrega es código/pruebas/documentación en el repo privado. No hubo subida a
PyPI/TestPyPI, Actions, recursos de pago nuevos ni cambios en la VM
`157.137.227.1`. Los temporales propios se retiran tras archivar/verificar
evidencia; el kit A13 previo de la VM conserva su estado.

Referencias: [tutorial PyPA](https://packaging.python.org/en/latest/tutorials/packaging-projects/),
[sdist](https://packaging.python.org/en/latest/specifications/source-distribution-format/),
[TestPyPI](https://packaging.python.org/en/latest/guides/using-testpypi/),
[yanking](https://docs.pypi.org/project-management/yanking/).
