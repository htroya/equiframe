# Aserciones, pytest y pipelines existentes

STEP4 del candidato privado 0.11.1. La integración es una llamada sobre un
`ComparisonResult` ya calculado. No requiere plugin pytest, un runner propio,
un conector dbt, acceso de red ni repetir la transformación.

## Gate de aceptación

```python
import equiframe as ef

result = ef.diff(candidate, expected, keys=["id"])
ef.assert_equivalent(result)
```

La aserción retorna `None` únicamente cuando el resultado es `equivalent`, el
recorrido requerido está completo, los conteos son finales y la garantía
`observed_contract` satisface la política del consumidor. Una referencia esperada
inválida conserva `not_evaluable`, incluso con `complete=True`, y siempre falla.
No existe `allow_partial`, muestreo aprobado ni aceptación por falta de alertas.

La garantía es equivalencia de las capturas dentro del esquema de salida y sus
políticas declaradas. Puede incluir una tolerancia o normalización expresamente
autorizada: no se convierte en igualdad exacta ni equivalencia universal de
programas. Tampoco certifica la corrección o independencia del esperado. Reglas
R, perfiles, anomalías M/B/H y aceptación científica permanecen separadas.

```python
policy = ef.EquivalencePolicy(
    required_reference="expected",
    required_contract_sha256=reviewed_contract_hash,
    required_spec_sha256=reviewed_spec_hash,
)
ef.assert_equivalent(result, policy=policy)
```

Los hashes deben proceder de un contrato/spec previamente revisado por el
consumidor. Copiarlos del resultado recién recibido solo comprueba tautología.
Se revalida el modelo completo, incluidas sus huellas y consistencia. En un
resultado completo con metadatos `source.table`, los conteos finales deben
coincidir con las filas de la captura. Esta validación compartida adicional
rechaza manifiestos contradictorios aunque antes fueran estructuralmente
aceptados; no se aplica como total final a recorridos parciales. Se rechazan
`dict`, `ComparisonReport` y objetos malformados como entradas del gate: una vista
JSON filtrada es para diagnóstico, no sustituye el resultado y su contrato.
La validación de un objeto no autentica quién lo produjo ni reevalúa los datos.

## Evidencia exigida explícitamente

```python
from pathlib import Path

private_root = Path("private-comparisons")
result = ef.diff(candidate, expected, keys=["id"], work_dir=private_root)
ef.assert_equivalent(
    result,
    policy=ef.EquivalencePolicy(require_persisted_evidence=True),
    evidence_root=private_root,
)
```

Por defecto no hay lectura de archivos. Exigir persistencia requiere tanto la
política como una raíz explícita `Path`; una raíz sin la política, o la política
sin raíz, es configuración inválida. La inspección acotada existente verifica
`comparison.json` finalizado, su identidad exacta con el resultado suministrado y
el tamaño, hash, contenido y estructura de todas las diferencias registradas.
Rechaza referencias fuera de la raíz, traversal, symlinks, archivos ausentes o
corruptos y presupuestos insuficientes. No lee fuentes originales, ejecuta SQL,
descarga datos ni convierte hashes en autenticación del productor.

La persistencia comprobada cubre el manifiesto y las diferencias, no la
reproducción íntegra de transformaciones o la publicación de una vista HTML.
Para conservar capturas reproducibles use por separado la exportación explícita
[del reporte](REPORTS.md#reproducción-acotada). `max_evidence_bytes` y `max_records`
son límites cooperativos; no son una cuota dura de memoria del proceso.

## Errores y decisión machine-readable

- `EquivalenceDifferentError`: hay diferencias completas
- `EquivalenceNotEvaluableError`: no se pudo establecer el juicio requerido
- `EquivalenceGuaranteeError`: hashes o referencia no satisfacen la política
- `EquivalenceEvidenceError`: la evidencia requerida no satisface integridad/persistencia
- `EquivalenceInputError`: tipos, modelos, política o combinación de argumentos inválidos

Los primeros cuatro derivan de `EquivalenceAssertionError`, que es
`AssertionError` y `EquiFrameError`. Configuración inválida deriva de `ValueError`
y `EquiFrameError`. Cada error expone un código estable; no analice su texto.

```python
decision = ef.equivalence_decision(result, policy=policy)
print(decision.model_dump_json())
if not decision.accepted:
    handle_failure(decision.code)
```

`EquivalencePolicy` y `EquivalenceDecision` tienen esquemas 1.0 separados:
[`equivalence-policy`](../packages/equiframe/schemas/equivalence-policy-1.0.schema.json)
y [`equivalence-decision`](../packages/equiframe/schemas/equivalence-decision-1.0.schema.json).
La decisión conserva estado, completitud, conteos finales, alcance, referencia y
huellas del resultado; añade aceptación y requisitos del consumidor. No crea un
segundo veredicto de comparación. Se validan campos desconocidos y versiones
futuras en lugar de interpretarlos parcialmente como éxito.

Códigos: `equivalent`, `different`, `not_evaluable`, `guarantee_mismatch`,
`evidence_missing`, `evidence_corrupt`, `evidence_path_rejected`,
`evidence_budget_exceeded` y `evidence_unreadable`.
La configuración inválida lanza `invalid_assertion_input` en vez de crear una
decisión aparentemente evaluada. Una diferencia o imposibilidad de evaluar tiene
prioridad como fallo primario; `guarantee_conforms` describe solo la conformidad
de hashes/referencia solicitados, no afirma equivalencia por sí solo; si se pidió evidencia, su estado/código sigue en
la decisión para no ocultar el problema adicional.

Los mensajes son breves, con motivos acotados y un siguiente paso. Omiten valores,
nombres, rutas y texto libre del productor. Para diagnóstico autorizado construya
un reporte con permisos de divulgación explícitos. `report_path=Path(...)` añade
solo la ruta que el propio consumidor decidió mostrar; no la abre ni verifica.
Las cadenas de excepciones internas se ocultan en el error público. Opciones de
pytest como `--showlocals` o plugins externos pueden mostrar variables del propio
test; no son un canal privado ni una garantía de redacción de todo el proceso.

## Cambio observable: no convertir resultados a bool

A partir de esta entrega, `bool(result)`, `if result:`, `assert result`, `not
result`, `any([result])` y `result or fallback` lanzan `TypeError` en los tres
estados de `ComparisonResult`. Antes comprobaban solo existencia del objeto y
podían aprobar accidentalmente `not_evaluable`. `EquivalenceDecision` exige usar
su campo explícito `accepted` por el mismo motivo.

Migración:

```python
# Una condición de aceptación:
ef.assert_equivalent(result)
# Inspección descriptiva, sin aceptar por existencia:
print(result.state, result.complete)
# Una comprobación de ausencia:
if result is not None:
    print(result.state)
```

El formato serializado `ComparisonResult` 1.0 no cambia. Las comparaciones
explícitas, contenedores, lectura JSON y reporte conservan su comportamiento.
No se añade conversión `False` que confunda diferencia con imposibilidad de evaluar.

## Guardar antes de fallar

```python
report_dir = Path("safe-artifacts/comparison")
ef.write_comparison_report(result, report_dir)  # Vista redactada por defecto
# Las capturas privadas permanecen fuera de safe-artifacts.
ef.assert_equivalent(result, report_path=report_dir / "report.html")
```

El destino debe ser nuevo. Solo `evidence-manifest.json` finalizado acredita que
se terminó la publicación local; un archivo parcial no basta. Un fallo de
escritura debe fallar el test/proceso, sin ignorarlo ni aprobar el resultado.
La receta ejecutable conserva además el estado de comparación en su diagnóstico
si la escritura falla. Ninguna aserción escribe reportes implícitamente.

## pytest y CI de mínimo acceso

La [receta ejecutable](../packages/equiframe/examples/assertion_ci.py) crea datos
sintéticos y salidas ya materializadas; no descarga datasets ni necesita secretos.
Las pruebas ejecutan los casos de éxito, diferencia e interrupción en procesos
reales y comprueban sus códigos, mensajes, inventario y contenido redactado.
La integración pytest usa fixtures y una aserción simple; no se añade dependencia
ni plugin que replique ese mecanismo.

Ejemplo de conservación en un job existente de GitHub Actions, después de
instalar el candidato identificado y las dependencias del proyecto:

```yaml
- name: Compare existing outputs
  run: python packages/equiframe/examples/assertion_ci.py --case different --output safe-artifacts/comparison --work-dir private-comparisons
- name: Verify finalized redacted inventory
  id: report_guard
  if: always()
  run: python -c "import sys; from pathlib import Path; sys.path.insert(0, 'packages/equiframe/examples'); from assertion_ci import verify_upload_directory; verify_upload_directory(Path('safe-artifacts/comparison'))"
- name: Keep sanitized diagnostics even when the gate fails
  if: always() && steps.report_guard.outcome == 'success'
  uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
  with:
    name: comparison-diagnostics
    path: |
      safe-artifacts/comparison/report.json
      safe-artifacts/comparison/report.txt
      safe-artifacts/comparison/report.html
      safe-artifacts/comparison/evidence-manifest.json
    if-no-files-found: error
    retention-days: 7
```

`different` falla intencionalmente; cambie a `equivalent` para un job verde o
sustituya la captura sintética por salidas de su pipeline. No use
`continue-on-error` como aceptación ni cargue todo el directorio de trabajo.
La lista cerrada excluye capturas Arrow, diferencias crudas, logs del entorno,
credenciales y detalles no autorizados. La redacción reduce divulgación pero no
anonimiza recuentos ni elimina responsabilidad sobre permisos/retención del
repositorio remoto. Revise el reporte antes de compartir datos reales.

Este YAML es una receta, no una ejecución remota acreditada. Los recibos STEP4
identifican las pruebas locales realmente ejecutadas; el conector disponible no
ofrece dispatch del workflow manual. La publicación de un artefacto en un job
remoto real sigue siendo un criterio externo pendiente hasta observar ese run.
No se cambian triggers, permisos de Actions, credenciales, cuota ni despliegues.

## CLI existente

`equiframe compare SPEC LEFT RIGHT [--expected] --output PRIVATE_DIRECTORY`
conserva un objeto JSON en stdout y usa stderr para diagnósticos seguros:

| Condición | Código |
|---|---:|
| `equivalent`, completo y válido | 0 |
| `different`, completo | 1 |
| Configuración inválida | 2 |
| Fallo de operación/persistencia o resultado final inválido/ausente | 3 |
| `not_evaluable`, incluido `invalid_expected` con recorrido completo | 3 |

Los errores de parseo del framework también terminan con código no cero. No
analice texto de stderr como contrato de máquina ni trate stdout vacío como
éxito. El JSON de comparación conserva `comparison_id`, `state` y `complete`, y añade
`accepted`, `code` y `evidence_status`. La CLI comprueba el manifiesto finalizado y
las diferencias bajo su directorio de salida antes de emitir éxito. Un juicio
`equivalent` con evidencia ausente/corrupta conserva ese estado descriptivo pero
tiene `accepted=false`, un código explícito y exit 3. Para otros requisitos de
garantía use la API y su esquema de decisión. No hay
una segunda CLI o aceptación automática por ausencia de anomalías.
