# Preparar y entregar un release manual

[Portal](README.md) · [Plan PYPI-PREP-20-v1](PYPI_PREPARATION_PLAN_20261010.md) ·
[Política vigente del paquete](../packages/equiframe/docs/releasing.md)

Corte auditado de este runbook: pareja privada **0.12.0a13**, sin licencia de distribución aprobada.
El código actual es [A14](EDA_IMPLEMENTATION_20261012.md); sus artefactos y
comprobaciones propios no sustituyen los hashes del manifiesto A13 siguiente.
El [manifiesto separado A14](../tools/pypi_candidate_a14.json), SHA-256
`31ba467c50e5bf7cbc428aa4720d725a825bd723d073e9e81ab0e4ed457e5ba3`,
también pasó la auditoría offline contra sus cuatro archivos exactos.
Los pasos de derechos, cuentas y publicación permanecen pendientes.
Este runbook prepara controles y la entrega futura. Las herramientas no suben
archivos, buscan tokens, firman aprobaciones ni habilitan publicación. El modo
de trabajo acordado es manual, sin Actions y sin nuevos recursos de pago.

## 1. Identificar el candidato

Conserva los cuatro archivos originales: wheel/sdist del núcleo y wheel/sdist
del benchmark. El consumidor y corpus tienen repositorios y permisos separados;
no pertenecen a esa entrega pública. No uses `dist/*` o archivos encontrados al
azar. Revisa versiones exactas, hashes, origen, contenido, dependencia del
benchmark y los recibos realmente ejecutados. Un commit de documentación nuevo
no reetiqueta el corte del código que produjo un wheel anterior.

El [manifiesto A13](../tools/pypi_candidate_a13.json) identifica esos cuatro
artefactos y 21 fixtures Arrow históricos que coinciden con los bytes de Git.
Su hash debe recibirse por un canal confiable distinto de los archivos. Calcular
el hash de un manifiesto recibido de una fuente desconocida no autentica al autor.
Ejemplo de control **offline**, sustituyendo rutas/digest por valores confiables:

```text
python tools/prepare_pypi.py --artifact-root /absolute/original-artifacts --manifest /absolute/reviewed-manifest.json --sha256 TRUSTED_64_HEX_DIGEST --output /absolute/new/preparation.json
```

Código **3**: los cuatro archivos pasaron la auditoría y la publicación sigue
bloqueada. Código **2**: el control no pudo aceptar entradas/escribir el recibo.
No interpretes 3 como permiso de subir. El comando no requiere credenciales ni
red; no ejecuta el código del candidato ni extrae el tar. El hash y la revisión
del manifiesto son responsabilidades del canal de entrega. El inventario de
rutas no demuestra ausencia de todo secreto incrustado en texto.

## 2. Validar metadatos y funcionamiento

Usa herramientas fijadas en el lock. Con los cuatro nombres exactos:

```text
python -m twine check --strict /absolute/core.whl /absolute/core.tar.gz /absolute/benchmark.whl /absolute/benchmark.tar.gz
```

Los nombres anteriores representan los archivos completos reales; no son
descargas ni nombres válidos para copiar literalmente. Twine valida metadatos
y renderización, no licencia aprobada, titularidad, independencia científica,
cuentas ni corrección del software. Sigue los controles de
[contribución](../CONTRIBUTING.md) para construir, reconstruir desde sdist e
instalar fuera del checkout. Comprueba `pip check`, identidad/payload, los extras
prometidos y casos equivalentes, diferentes, no evaluables y de fallos.
Si cambian licencia, README, versión o archivos empaquetados, son nuevos bytes:
construye artefactos y recibos nuevos; no heredes automáticamente los PASS de A13.

Consulta nombres mediante `python tools/probe_pypi_names.py --output /absolute/new/names.json`.
Solo consulta las APIs públicas de PyPI/TestPyPI. 404 significa ficha no visible;
errores/red/restricciones son UNKNOWN. Ninguna respuesta reserva el nombre,
prueba control de cuenta ni autoriza reclamar otro proyecto.

## 3. Completar los requisitos externos

Antes de cualquier subida pública, revisar hechos verificables:

- Titulares y régimen de distribución acordados, licencia/notices/metadata
  presentes en ambos formatos; documentación/datos/modelos con permisos propios.
- Cuenta y acceso publicador autorizados, 2FA/recuperación y roles comprobados
  separadamente en PyPI y TestPyPI; nombre/versión y responsables de release.
- Documentación y canal de incidencias accesibles a usuarios sin el repo privado.
  El [README propuesto](PYPI_README_DRAFT.md) todavía no cambia METADATA ni crea un sitio.
- Revisiones de dependencias/seguridad y gates aplicables de
  [STEP10 y la hoja de ruta](HERNAN_ROADMAP.md), revisión independiente y aprobación
  de la entrega exacta. Los porcentajes de preparación no sustituyen esos hechos.

Nada de esto se rellena automáticamente con la identidad del autor de Git o con
un JSON de aprobación aportado a la herramienta. No se solicitan ni guardan
credenciales en Git, chat, argumentos, recibos o este runbook.

## 4. Ensayo futuro en TestPyPI

TestPyPI es un índice público distinto, con cuentas y base de datos propias.
Una subida de ensayo necesita los permisos y la tarea explícita correspondientes;
**esta preparación no la ejecuta**. Una vez cumplidos los gates, el responsable
usa Twine manualmente con el endpoint explícito
`https://test.pypi.org/legacy/` y solo los archivos aprobados. Obtiene la
credencial de su almacén local autorizado; nunca la pone en el comando o un log.
No se crea un workflow OIDC/GitHub Actions para esta ruta manual.

Registrar código de salida, índice, nombre/versión, fecha y hashes aceptados. No
afirmar éxito del par si solo se aceptó un archivo o una distribución. Después,
consulta cada versión y compara **cada nombre de archivo y SHA-256** con el
manifiesto. Para un consumidor limpio, instala dependencias revisadas desde
PyPI y los candidatos exactos desde TestPyPI con `--no-deps`, sin mezclar índices
para resolver el núcleo del benchmark. Ejecuta `pip check`, identidad, payload,
ejemplos y regresiones; conserva el origen de cada descarga. La documentación
[oficial de TestPyPI](https://packaging.python.org/en/latest/guides/using-testpypi/)
explica que las cuentas/datos pueden purgarse: no sustituye conservar artefactos.

## 5. Publicación, subida parcial y recuperación

Publicar en PyPI requiere una tarea explícita posterior para el nombre, versión
y hashes aprobados; endpoint `https://upload.pypi.org/legacy/`. Promueve los
mismos bytes finales ensayados; no reconstruyas entre ensayo y producción para
afirmar que son idénticos. Revalida nombre/acceso y gates inmediatamente antes.

| Observación | Estado | Acción del responsable |
|---|---|---|
| Ningún archivo visible | ABSENT | Registrar intento/fallo; no afirmar publicación |
| Parte del par visible y coincide | PARTIAL | Congelar los bytes, identificar faltantes y revisar el fallo antes de reintentar solo esos archivos |
| Nombre/digest inesperado | CONFLICT | Detener promoción; no sobreescribir o aprobar un nuevo hash automáticamente |
| Los cuatro nombres/digests coinciden | COMPLETE_OBSERVATION | Aún falta confirmar origen, consumidores y aceptación; un mapping local no autentica el índice |

`reconcile()` en la herramienta nueva ensaya estas decisiones sobre observaciones
suministradas y mantiene autorización falsa. No ejecuta reintentos ni acciones
de índice. Las pruebas simulan esos estados; no se presentan como uploads reales.
Una respuesta de archivo existente no se convierte en PASS sin comprobar su
hash. No uses `--skip-existing` para ocultar conflictos o una entrega parcial.

Si una versión ya publicada tiene un defecto, registra alcance y diagnóstico,
deja de recomendar el hash afectado y prepara otro número de versión. La
retirada de selección (*yank*) y la eliminación son acciones diferentes que
requieren decisiones específicas del responsable. Un rollback de consumidor
no borra ni reescribe evidencia; usa entorno nuevo y versión segura revisada.
Consulta [releases y rollback](../packages/equiframe/docs/releasing.md) y
[yanking oficial](https://docs.pypi.org/project-management/yanking/).

## Estado del 90 % solicitado

La [rúbrica fija](PYPI_PREPARATION_PLAN_20261010.md) conserva P17–P20 con cero
crédito mientras falten los hechos externos. Completar dos requisitos elevaría
16/20 a 18/20 = 90 %, pero solo completar todos los gates habilitaría una entrega
pública. El [resultado](PYPI_PREPARATION_RESULT_20261010.md) registra el porcentaje
real logrado, los bytes comprobados y lo que queda pendiente.
