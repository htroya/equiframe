# Estado de la revisión de seguridad del seguimiento

Esta página es una referencia de estado del repositorio; los resultados y
evidencia de Codex Security se conservan mediante sus herramientas en su
almacenamiento administrado. No sustituye su informe canónico ni concede una
nota de seguridad al producto completo.

El fallo del [intento anterior](SECURITY_SCAN_BLOCKER_20261011.md) persiste para
el Git anidado: el resolver trata el `.git` ancestral de `C:\` como raíz
protegida. No se borró ese directorio, no se retiraron protecciones ni se
modificó el plugin. La alternativa soportada fue una copia no-Git aislada de
fuentes autorizadas, sin entornos, Word, claves ni datos SERCOP.

La auditoría Standard se registró como
`c90b443b-0f84-4716-9ba1-febea05c8dbb`. Su snapshot contiene 698 archivos,
11.166.948 bytes y digest autoritativo
`d17f61673ca2b11e57392e26b37112bc94420bc48a2a223e3062883daefa240a`.
Excluye 122 fixtures históricos; el origen es HEAD
`40a8d8dd82229fe1dbe1f21d22939522502a61b6` más los tres archivos nuevos presentes
al copiar. Es una identidad de snapshot, no un commit limpio ni los bytes de
todo el seguimiento posterior. La última corrección del verificador, workflow,
documentación y atributos de checkout posteriores quedan fuera de esa auditoría.

El registro incorpora modelo de amenazas, revisión independiente automatizada
y arquitectura con contexto nuevo. Se identificó estáticamente un hallazgo de
gravedad baja/confianza media, `path-confinement.windows-report-junction`,
CWE-22: `_report_io.py` admite ancestros que son uniones de directorio Windows.
Un artefacto con bytes/hash/tamaño conocidos puede atravesar esa unión al
exportar reproducción explícitamente autorizada. No se demostró lectura de
secretos desconocidos, ejecución remota ni explotación dinámica. El hallazgo
permanece abierto: debe rechazarse el reanálisis/unión en ancestros y probarse
la contención de entradas/destinos con material sintético antes de construir y
revalidar un candidato nuevo. No se alteró el payload A13 en este seguimiento.

El fallo de argumentos en el paso opcional de avisos del workflow fue una
observación de integración separada, que fallaba cerrado antes de consultar.
La corrección posterior y su validación local están en el
[seguimiento técnico](FOLLOWUP_95_RESULT_20261011.md); no se ejecutaron Actions.

Las comprobaciones OSV corresponden a entornos medidos, no a un inventario
ligado al lock. Tras actualizar pip solo en el venv Windows y setuptools solo
en el venv ARM64/3.10, los paquetes públicos consultados no presentaron avisos
conocidos. Las versiones privadas, source audit, entornos restantes y un SBOM
artifact-bound no se consideran cubiertos por ese resultado.

El almacenamiento administrado del scan está bajo
`C:\Users\Usuario\.codex\state\plugins\codex-security\scans\equiframe-source-snapshot-20261011\unversioned_20261011T184015Z_2xofrd39`.
La evidencia de origen tiene hash
`1d5765c7e628eefdc956c303eb94f65992bd5041d24f0f7a34c9b756c84003de`; la revisión
de arquitectura,
`60093e86c8c4c673714c8d7b2928c27c6bdb02face60a0a2db5bd1b9b9a9a57d`.
El scan quedó completado y sellado a las **19:24:57 UTC del 11 de octubre de
2026**, tras corregir un rechazo de esquema del checkpoint: `resolvedDeferred`
solo se admite en el borrador terminal. El cierre final fue aceptado y completion
se ejecutó una sola vez. El host confirmó `reportAvailable=true`: existen
`report.md`, `scan-manifest.json`, `findings.json`, `coverage.json`,
`threatmodel.md` y `exports/results.sarif` en ese directorio. No se redactó el
informe canónico por shell ni se atribuye hash de report/manifest que la API no
expone. [Metadatos de referencia y digests](SECURITY_FOLLOWUP_METADATA_20261011.json).

La cobertura conservada es **parcial: 319/698 archivos** mediante lectura
completa o auditoría estructural completa de datos. Dentro del snapshot se
revisó producción del núcleo/benchmark, herramientas, CLI y CI. Los 379
archivos restantes están enumerados: 144 pruebas, 67 ejemplos y 168
documentos/metadatos. La tarea genérica se cerró con esas exclusiones; no se
convierten búsquedas en lectura completa ni ausencia de pendientes genéricos en
cobertura total. El rehash de los 698 archivos no cambió. El hallazgo canónico
`csf_d92dc83dfa946f8126a9de46` continúa abierto y validado estáticamente.

La propuesta `SECURITY-PREP-20-v1` se conserva en el almacenamiento administrado,
sin sustituir una evaluación aplicada al producto completo. Los 319 archivos no
son una nota de preparación. El host declaró uso de tokens no disponible, con
`scan_thread_unavailable`; no se inventó una estimación.

La habilidad aplicada es `codex-security:security-scan`, con su política de
almacenamiento: «For a full scan, obtain the authoritative scanId before creating
artifacts». Aquí existe ese ID; el diagnóstico anterior no lo tenía. Las
habilidades están en
`C:\Users\Usuario\.codex\plugins\cache\openai-curated-remote\codex-security\0.1.32\skills\security-scan\SKILL.md`
y `../../references/artifact-storage.md` respecto de esa habilidad. Esta política explica la
separación entre esta referencia Git y los resultados administrados del scan.
Responsables/canal/SLA, revisión humana y remediación verificada siguen abiertos.
