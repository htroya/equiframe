# Antecedente A8/c4: no ejecutar con el kit A9

Documento histórico del laboratorio anterior. Sus comandos de dos Python y su referencia al parche pendiente del benchmark corresponden exclusivamente a A8/c4. NO son instrucciones vigentes y NO deben copiarse para A9. Para A9 use únicamente README_VM_ES.md y su candidate.json. Se conserva el texto sin reinterpretar resultados históricos.

# Laboratorio ARM64 de EquiFrame: ejecución pendiente

Este kit contiene el candidato privado y herramientas de prueba. No contiene
la llave privada ni acredita que la VM haya ejecutado nada. No publica paquetes,
activa Actions, despliega servicios, cambia Python global ni toca el DW.

## Antes de ejecutar

- Usar el entorno de Codex que ya tenga acceso autorizado a maestria-vnic
- Registrar operador real, tarea Codex y fecha; conservar aparte el recibo de
  conexión/identidad y la transferencia del ZIP con su SHA-256
- Verificar el SHA-256 externo del ZIP antes de extraerlo en una carpeta privada
- Comprobar usuario hernan, hostname maestria-vnic y Linux aarch64
- Disponer de /usr/bin/python3.10 y /usr/bin/python3.12 con venv funcional
- Revalidar recursos y convivencia con José. El runner necesita 6 GiB libres al
  preparar el laboratorio y conserva la guardia de 4 GiB del consumidor. Usa
  un hilo y ensayos secuenciales; no establece cuotas duras del sistema
- La salida HTTPS a PyPI debe estar autorizada/disponible. No desactivar TLS,
  usar sudo, cambiar firewall ni sustituir el candidato por un paquete homónimo

Los hashes y locks preparan una reproducción; una resolución previa para otra
arquitectura nunca cuenta como prueba ARM64. Los resultados nuevos registran
intérprete, arquitectura, paquetes, comandos, código de salida y artefactos.

## Comando en la VM

Desde el kit extraído, usando el intérprete 3.12 observado y el nombre real de
quien ejecuta o identifica la tarea Codex:

```bash
/usr/bin/python3.12 scripts/run_vm_lab.py \
  --kit "$PWD" \
  --executor "NOMBRE REAL / IDENTIFICADOR DE TAREA CODEX" \
  --python310 /usr/bin/python3.10 \
  --python312 /usr/bin/python3.12 \
  --lab-parent /home/hernan
```

El programa crea un directorio nuevo privado equiframe-maturity-... bajo ese
home. No usa credenciales ni abre archivos de otros usuarios. Cada versión tiene
entornos separados. Los venvs completados pueden eliminarse después de guardar
su evidencia; --keep-successful-venvs los conserva. Los entornos fallidos y sus
recibos se retienen. La lista exacta de altas/bajas queda en receipt.json.

La instalación de herramientas se limita al venv del laboratorio. pip se prepara
con ensurepip y, donde hace falta su informe JSON, con la versión explícita del
procedimiento. Las dependencias del candidato se resuelven/registran con hashes;
el núcleo/benchmark/consumidor siempre vienen de los artefactos privados exactos.

El recorrido comprueba perfiles, extremos seleccionados de dependencias, gates
API/CLI, históricos, suite instalada, benchmark, consumidor, fallos bajo -O,
recuperación local y reconstrucción/instalación desde sdist. Un código no cero
esperado significa rechazo correcto; nunca aceptación de datos. Un timeout o
fallo impide el cierre de la celda. No se crean personas/revisiones ficticias.

## Entrega y revisión

Conservar el directorio de evidencia indicado por el programa y su inventario.
Transferirlo por el canal autorizado sin venvs/cachés ni credenciales. Mantener
logs, JSON, locks, informes de instalación, matrices y casos que respaldan cada
resultado, incluidos fallos. Los datos del consumidor son la captura pública
congelada de 219 registros efectivos; conditions.json conserva sus límites de
procedencia/licencia y no otorga derechos sobre el software.

La validación al recibirlo se ejecuta fuera de la fuente:

```bash
python3.12 scripts/validate_vm_receipts.py \
  --kit /ruta/al/kit \
  --evidence /ruta/al/laboratorio-recibido \
  --output /ruta/nueva/revision-vm.json
```

El validador coteja identidad, hashes, comandos, Python 3.10/3.12 ARM64 y resultados
obligatorios. No autentica al operador ni reemplaza la revisión de los logs y del
recibo de transporte. M13 y los criterios vinculados permanecen pendientes hasta
recibir y revisar evidencia real. La revisión humana independiente de M16 y los
acuerdos de derechos/mantenimiento conservan sus propias puertas.

No usar --cloud-validation para reclamar evidencia de la VM: esa opción está
reservada al ensayo del runner y el validador la rechaza como prueba ARM64.

## Preparación y trazabilidad del ejecutor

OPERATOR_RECEIPT_TEMPLATE.json es un formulario vacío. Solo se completa con
observaciones reales. Vincula la revisión J01–J07, la tarea/operador de Codex,
la transferencia autorizada y los recibos del laboratorio. No atribuye una
entrega a José por el simple hecho de disponer de acceso.

El pin público recibido para el servidor es
SHA256:f8cEqNHs2kOMivOwAqSawhz7JyEm59LkLpFT6b8fB7M. La verificación del transporte
corresponde al ejecutor que ya tiene acceso. Este kit no incorpora ni necesita
leer una llave privada y no configura SSH.

El runner conserva observaciones de memoria del host y, cuando son legibles,
límites/uso cgroup. Los límites no disponibles permanecen desconocidos. No
modifica mounts, quotas, cgroups ni permisos de otros usuarios. El consumo de
recurso medido corresponde al almacenamiento realmente usado; no intercambiar
un ensayo tmpfs por capacidad de disco. Un resultado parcial conserva sus fallos.

Los locks de controlador provienen de PyPI con hashes de los wheels aptos.
Cada celda resuelve además su propio runtime y conserva ese lock con hashes,
inventario instalado y payload de los wheels. Los pins x64 entregados como
referencia no deben confundirse con una instalación ARM64 ejecutada.

## Edición revisada de herramientas

La entrega standalone revisada conserva exactamente los seis artefactos de c4.
`candidate.json` distingue `source` (fuente de esos artefactos) de
`tooling_source` (commit de scripts/documentación revisados) y registra el
manifiesto predecesor. La evidencia nueva debe vincular el SHA-256 del
`candidate.json` de este kit revisado. No sobrescribir scripts ni manifestar
que un recibo antiguo corrió contra esta revisión del arnés.

El benchmark c4 aún no contiene el parche de declaración directa del backport;
el parche se entrega solo para revisión. Su reconstrucción y nuevo lock siguen
pendientes. Ejecutar este kit no elimina esa brecha de metadatos.

El runner conserva pins exactos del runtime al instalar la pareja y al consumir
sdists. Comprueba tres resultados consumidores nativos desde sdist bajo -O;
conserva la guardia de 4 GiB. Una medición incompleta queda fallida/parcial y no
se convierte en aceptación, aunque continúen los controles independientes.
El validador coteja los 72 casos individuales del consumidor, sus logs y
resultados nativos, no solo los totales declarados en el resumen.
