# Seguimiento técnico de la meta del 95 %

Se ejecutó el trabajo que podía avanzar con el acceso disponible, sin modificar
`tesis_corregda_v1.docx`, conceder licencias en nombre del equipo ni convertir
revisores IA en personas. El núcleo/benchmark siguen siendo A13 privados. Este
seguimiento **no acredita 95 % en las nueve áreas**; la
[matriz vigente](PROJECT_STATUS_MATRIX_20261011.md) conserva cada cifra y versión.

| Pendiente consultado | Trabajo realizado | Condición que sigue abierta |
|---|---|---|
| 1. Licencia basada en la tesis | [Propuesta MIT y separación software/manuscrito/datos](LICENSE_PROPOSAL_20261011.md) | Confirmar titulares, acuerdos institucionales/contribuciones y aprobación real; la IA no concede derechos |
| 2. Revisor «mi dot» | [Segunda lectura automatizada](AUTOMATED_REVIEW_20261011.md), detección/corrección de cobertura duplicada e identidades | U12, D19, M16, O ciego y tutor requieren personas y evidencia real |
| 3. Evidencia con datos SERCOP | Exportaciones oficiales anual/enero congeladas, inventario y 18 checks nativos equivalentes | Compilación/cohorte, N_fit efectivo, grupos/splits, etiquetas, calibración, resultados pareados y aceptación; [detalle](SERCOP_PUBLIC_PILOT_20261011.md) |
| 4. Trazabilidad | 146 obligaciones adicionales verificadas, denominador fijo | 3.522 adicionales para ≥95 %; interacciones/CLI/modelos y efectos nativos restantes no se infieren |
| 5. Validaciones técnicas | Windows x64 3.12 y Linux ARM64 3.10/3.12, normal/-O; controles de nuevos verificadores y workflow | Plataformas/Python restantes, mínimos/máximos completos, recuperación y reproducción externa; WSL solo ofreció docker-desktop, sin runner adicional disponible |
| 6. Seguridad local/VM | Standard registrado sobre copia aislada, consultas OSV por entorno y actualizaciones aisladas de pip/setuptools | Hallazgo de contención Windows, cobertura/validación restante, SBOM ligado al lock/artefacto, responsables/canal y revisión humana |

## Implementación y pruebas

`tools/option_operations.py` exige el wheel A13 de SHA-256
`c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23`, compara los
127 archivos instalados fuera del checkout, verifica commit/conjunto de 8.385
IDs y el resultado anterior de 4.298 obligaciones. La matriz de descubrimiento
no se presenta como un resultado ejecutado. Los casos fijan entradas, esperados,
ubicaciones/códigos de error y efecto nativo antes de ejecutarse. IDs ya
verificados, repetidos, desconocidos, casos duplicados o JSON ambiguo se rechazan.

Los 141 casos ejecutados incluyen 139 nuevos distintos y dos regresiones:
27 PASS y 114 rechazos esperados. Se añaden 31 PASS y 115 EXPECTED_REJECTION al
denominador; una ejecución puede probar más de un ID revisado. Las ocho
ejecuciones normal/-O entre Windows y VM —incluidas dos repeticiones tras
actualizar setuptools— se conservan separadas, sin sumar cobertura por repetir.

`tools/sercop_inventory.py` conserva tokens decimales, limita el tamaño de
paquetes leídos, verifica el ZIP/hash/CRC y produce únicamente inventario. Sus
pruebas rechazan datos ambiguos/truncados y prueban que las ocurrencias repetidas
no se convierten en adjudicaciones únicas ni perfiles de aprendizaje. No es un
validador completo OCDS ni un compilador del dominio.

Diez pruebas nuevas y 7 subcasos pasaron en normal/-O. La suite raíz completa
pasó con 82 casos: 73 PASS y 9 SKIP identificados, además de 55 subcasos, en ambos modos.
Ruff comprobó los dos verificadores y sus pruebas con objetivo Python 3.10. Las
suites completas anteriores del núcleo/benchmark conservan sus recibos y bytes;
no se vuelven a contar como obligaciones nuevas.

El productor JUnit declara `tests=137`, pero contiene 82 elementos `testcase`;
los 55 eventos de subcasos se informan separados. Ese contador agregado no se
publica como 137 pruebas distintas. El verificador de la meta escribe sus
recibos con LF y los atributos fijan LF para `.gitattributes`; se comprobó que
los hashes de las fuentes coincidan con los blobs Git que se entregan. La suite
raíz se repitió tras ese ajuste del verificador, con los mismos pases/omisiones.

Los nueve SKIP de Windows corresponden al contrato del instalador POSIX. Se
ejecutaron en ARM64 con Python 3.10/3.12 normal/-O: los nueve casos y tres
subcasos pasaron en los cuatro recorridos, usando un uv simulado, sin instalar
el producto. El primer intento falló por CRLF del checkout Windows; se conserva
su log. Se añadió `*.sh text eol=lf` a `.gitattributes` y se restauraron los bytes
LF exactos que ya tenía el blob Git del script. No se modificó su lógica. Estos
controles no acreditan una instalación real en AlmaLinux ni toda la suite raíz
en Linux. [Recibos técnicos](TECHNICAL_VALIDATION_FOLLOWUP_20261011.json).

Se corrigió `.github/workflows/release-candidate.yml`: el paso opcional de avisos
exige las dos listas públicas exactas revisadas, construye planes offline y pasa
`--public-allowlist`/`--request-plan` a los dos comandos de consulta. Los inputs
se pasan por variables de entorno entrecomilladas. Las listas vacías fallan antes
del egress; no se generan listas de nombres privados automáticamente. La
validación local comprobó YAML, sintaxis Bash y los cuatro CLI reales rechazando
un inventario ausente antes de consultar. No acredita una ejecución de Actions
ni un escaneo artifact-bound exitoso. Los dos controles manuales siguen false.

## Entornos, seguridad y custodia

Se usaron venvs propios, sin modificar Python global o laboratorios anteriores.
En Windows se detectaron seis IDs únicos de avisos en pip 24.0 (doce registros,
no doce vulnerabilidades distintas); pip pasó a 26.2.1. En ARM64/3.10 se
detectaron cuatro IDs únicos en setuptools 59.6.0 (ocho registros); pasó a 84.0.0.
Las consultas posteriores de los entornos medidos no encontraron avisos conocidos
en los paquetes públicos consultados. No es prueba de ausencia de vulnerabilidades
ni un SBOM del lock; las distribuciones privadas requieren su revisión separada.
La [auditoría estática](SECURITY_FOLLOWUP_20261011.md) quedó sellada con identidad
propia, cobertura parcial 319/698 archivos y un hallazgo bajo abierto. El cierre
del informe no convierte su snapshot anterior en una auditoría de todos los
bytes posteriores de esta entrega.

Las exportaciones, scripts/protocolo de piloto, logs, capturas y resultados de
VM permanecen en `avance_95_20261011`, fuera de Git. El corpus anual tiene hash
`9ee4e5f94f44e42c89ade804d00ed69cd24604d246ad6450a4a43b2bd42e3632`; enero,
`54bebc10082131fd417559902fc608070650a59086134d8229858a7f7635be6d`.
El archivo de VM inicial tiene hash
`7a9f7b4807dcb6d265b746769fd2168e53071e07c2feea5f851131308623065b` y el posterior,
`599c85f487d87c645a9f7f99735d73169bd2091c7e79bc6fe78919d858b34bec`.

El archivo privado `avance_95_20261011_evidencia.zip` conserva 235 entradas,
CRC y hashes individuales verificados, SHA-256
`6ad48df1f3ff543bbe4e192538f5e0e14abbbc8920e4bce6353e8de3ed0636d8`.
Sus metadatos anteriores a la precisión JUnit y a la fijación LF se conservan
como históricos; el addendum `avance_95_20261011_evidencia_addendum.zip` y su
recibo local contienen las identidades finales y la aclaración de los contadores,
sin agregar cobertura por repetir. El archivo POSIX tiene SHA-256
`166d5068d7ee3c79d69214bad75b14dff95f00a749a4ecb9f05ec10779523b59`.
Tras verificar las evidencias se retiraron únicamente el venv Windows de este
seguimiento y los dos venvs propios de la VM; los archivos fuente, resultados,
distribuciones originales y laboratorios anteriores se conservaron.

El Word conserva SHA-256
`883b187f08221b9b4abab775430d9a2c87b6d92f503494317f3e1fec214d0f3c`.
No se ejecutaron Actions, no se crearon recursos de pago y no se publicó en
PyPI/TestPyPI. La entrega Git incorpora verificadores, corrección manual y
documentación/recibos agregados; no incorpora Word ni datos personales del corpus.
