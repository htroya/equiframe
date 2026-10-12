# Kit ARM64: ejecución y devolución de un candidato identificado

El manifiesto de cada kit privado identifica sus seis artefactos y el corpus
congelado. El candidato actual propuesto usa núcleo/benchmark **0.12.0a13** y
consumidor **0.1.15**; conservar el nombre no acredita haber ensamblado o
ejecutado un kit nuevo. La edición anterior A10/0.1.12 conserva sus recibos.

`candidate.json` identifica commits/árboles, tooling_source, seis artefactos,
hashes y versiones requeridas. El ensamblador mantiene por defecto el esquema
de universalidad v2, con **3.10, 3.11, 3.12, 3.13**. La opción explícita
`--scope original-m13-arm` produce una expedición separada v1 para el requisito
original M13: **ARM64 3.10 y 3.12**, con todos los controles y tres paquetes.
No reduce la matriz v2 ni cierra otras plataformas o M14 automáticamente.
Ambos alcances vinculan los tres `test-manifests` con los archivos originales
de sus sdists, identidades JUnit exactas y versiones de pytest/Hypothesis.
`SHA256SUMS` identifica los miembros; los kits anteriores no se sobrescriben.

Al preparar un kit nuevo, `assemble_kit.py` exige `--core-test-manifest`, `--benchmark-test-manifest` y `--consumer-test-manifest`, además de los recuentos reales. El runner rechaza kits sin estos tres manifiestos antes de crear entornos. La revisión histórica conserva el alcance original de kits anteriores.

## 1. Preparación

Use exclusivamente el Codex local que ya dispone del acceso SSH autorizado. La nube de dot no reintenta SSH. Necesita Python 3.10+ y OpenSSH ya disponibles localmente, su llave existente y el known_hosts confiado. No cree llaves nuevas ni cambie configuraciones globales.

Verifique el SHA-256 externo del ZIP suministrado con esta edición, antes de cualquier extracción. Extraiga a un directorio nuevo mediante un procedimiento que rechace rutas absolutas/traversal, enlaces y miembros inesperados. El helper revisado `transport_vm.py` realiza además una inspección cerrada antes del transporte y la extracción en VM. Un hash incluido dentro del propio ZIP no establece confianza externa.

El servidor esperado es maestria-vnic, usuario hernan/uid 1003, Linux aarch64.
El pin Ed25519 confiado es `SHA256:f8cEqNHs2kOMivOwAqSawhz7JyEm59LkLpFT6b8fB7M`.
Cada versión requerida por el manifiesto debe tener un intérprete real con venv
funcional; se admiten rutas privadas explícitas. No se cambia el Python global,
usuarios, servicios, firewall ni DW.

## 2. Transporte desde Windows

Desde el directorio extraído de esta edición, sustituya cada valor indicado por el real:

```powershell
$KitPath = 'C:\laboratorio con espacios\KIT_DE_ESTA_EDICION.zip'
$ZipSha256 = 'SHA256_EXTERNO_DE_ESTA_EDICION'
(Get-FileHash -LiteralPath $KitPath -Algorithm SHA256).Hash
& .\run_from_windows.ps1 -KitPath $KitPath -KitSha256 $ZipSha256 `
  -KeyPath 'RUTA_LOCAL_DE_LA_LLAVE_EXISTENTE' `
  -KnownHostsPath 'RUTA_LOCAL_KNOWN_HOSTS_CONFIADO' `
  -OutputPath 'C:\laboratorio con espacios\devolucion-nueva' `
  -Operator 'NOMBRE REAL / IDENTIFICADOR DE TAREA CODEX' `
  -SshHost 'HOST_YA_AUTORIZADO' -SshUser 'hernan' -PythonPath 'python'
```

El launcher verifica el ZIP/pin, transfiere, ejecuta **las versiones exigidas
por ese manifiesto**, recoge evidencia y devuelve un código no cero ante fallo.
KeyPath solo se usa por SSH local y nunca se copia. Conserva la confianza del
host y no instala componentes globales. Los tests simulados de transporte no
equivalen a una ejecución Windows/SSH real.

## 3. Ejecución directa en la VM, si el Codex autorizado realiza el transporte

Desde la raíz del kit de esta edición, este es el comando completo:

```bash
/usr/bin/python3.12 scripts/run_vm_lab.py \
  --kit "$PWD" \
  --executor "NOMBRE REAL / IDENTIFICADOR DE TAREA CODEX" \
  --python310 /usr/bin/python3.10 \
  --python311 /usr/bin/python3.11 \
  --python312 /usr/bin/python3.12 \
  --python313 /usr/bin/python3.13 \
  --lab-parent /home/hernan
```

No use `--cloud-validation` para esta ejecución: el revisor lo rechaza como evidencia ARM64. El runner crea un laboratorio privado nuevo bajo /home/hernan y verifica las identidades observadas. Los cuatro Python se recorren secuencialmente; no se sustituyen por el controlador 3.12.

## 4. Etapas, recursos y fallos

Para cada Python se instalan por ruta los wheels privados exactos y dependencias públicas de la celda, con hashes/locks y pip check. Se prueban base, arrow, pandas, polars, duckdb, engines, ml y all; benchmark base/engines/ml/resources/all. Cada perfil tiene extremos mínimo/reciente resueltos, sin presentar un rango completo como medido.

Se incluyen API/CLI, motores y seis direcciones, suite instalada del núcleo, benchmark, consumidor externo y sus puertos/SQLite, casos negativos y -O, históricos, integridad, medición, recuperación, reconstrucción byte a byte e instalación desde sdist. Todas las identidades de pruebas congeladas deben aparecer una sola vez. En Linux, núcleo y consumidor no admiten omisiones; benchmark exige exactamente las dos pruebas exclusivas de Windows con sus motivos declarados. Un fallo, xfail, cambio de motivo u omisión adicional invalida la suite. El corpus público conserva 219 registros y 72 casos con esperados independientes; sus condiciones están en consumer-data/conditions.json. No se crean revisores, adopción humana ni resultados científicos.

Planifique varias horas. El transporte tiene timeout predeterminado de 24 h, configurable con -TimeoutSeconds. Presupuesto de planificación: hasta 2 CPU, objetivo 6 GiB de RAM y 10 GiB temporales; no es una reserva ni cuota dura. Revalide recursos y convivencia antes de iniciar. Se mantienen la guardia de 6 GiB libres del laboratorio, 4 GiB del consumidor y las del benchmark. Si no hay margen, conserve el bloqueo; no reduzca guardias ni borre entornos antiguos.

La limpieza automática se limita a venvs/cachés NUEVOS propios que completaron controles y dejaron recibos, locks e inventarios. `--keep-successful-venvs` conserva esos entornos. Los fallos/entornos incompletos se retienen. Una medición parcial no se transforma en éxito y no evita los controles independientes. Si hay interrupción o desconexión, conserve el directorio remoto y transport.json; no relance sobre la misma salida ni atribuya éxito a scp/SSH.

## 5. Qué devolver

Devuelva **evidence.zip, result.json y transport.json** por la conversación privada. Conserve el directorio remoto hasta revisión. No adjunte llaves, venvs o cachés. Complete OPERATOR_RECEIPT_TEMPLATE.json únicamente con hechos observados, incluyendo operador/tarea y transferencia reales. Los hashes no autentican a una persona.

Si el transporte fue manual, conserve el inventario y todos los archivos listados en evidence-inventory.json; el helper `pack_evidence` empaqueta ese conjunto sin venvs/cachés. La revisión offline usa el mismo kit/manifiesto que se ejecutó:

```bash
python3.12 scripts/validate_vm_receipts.py \
  --kit /ruta/al/kit-exacto-ejecutado \
  --evidence /ruta/a/evidencia-extraida \
  --output /ruta/nueva/revision-vm.json
```

El revisor exige las cuatro versiones, perfiles, etapas, resultados negativos, fuentes, scripts, artefactos, locks, datos, inventarios y logs. Aceptar su consistencia técnica no cierra automáticamente M13/M16, universalidad, usabilidad ni ciencia.

## 6. Ediciones documentales e historia

Una edición que solo corrige esta guía mantiene los seis artefactos y scripts idénticos, pero tiene un manifest/ZIP propio y una relación explícita con su predecesor. Si ya inició el laboratorio con el kit anterior, conserve sus bytes/manifiesto y termine con esa identidad: no cambie de kit a mitad. Una corrección exclusivamente documental no exige repetir su evidencia técnica.

`HISTORICO_GUIA_A8_NO_EJECUTAR.md` conserva instrucciones antiguas, solo como antecedente. No utilice sus comandos ni afirmaciones sobre c4 para A9. Los recibos históricos de dos Python siguen siendo válidos únicamente para su alcance de esquema 1; no prueban el laboratorio A9 de cuatro versiones.
