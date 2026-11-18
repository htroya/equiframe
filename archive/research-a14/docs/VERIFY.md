# Verify de resultados existentes

`verify` inspecciona una o varias salidas materializadas con un contrato, sin
reescribir ni ejecutar la ETL externa. Recibe `ArtifactRef`, `ExecutionResult`
o `PipelineResult`. El extra `arrow` permite inspección y lectura; los motores
no se importan para verificar artefactos existentes. `verify_migration` adapta
un expediente de migración íntegro sin volver a ejecutar sus transformaciones.

```python
from pathlib import Path
import equiframe as ef

report = ef.verify(
    {"source": source_ref, "target": target_ref},
    contract=contract,
    expected=expected_ref,
    require_expected=True,
    work_dir=Path("evidence"),
)
print(report.agreement.state, [c.state for c in report.expected])
print(report.operational_state, report.independent_review.state)
saved = ef.read_verification(Path("evidence") / report.verification_id)
```

`source_ref`, `target_ref`, `expected_ref` y `contract` son artefactos/contrato
del consumidor. El ejemplo autocontenido `examples/verify_generic.py` crea
artefactos sintéticos de inventario y demuestra el error compartido: acuerdo
aprobado, esperado incumplido, publicación bloqueada. Los totales iguales no
sustituyen la inspección de claves y filas completas.

| Dimensión | Significado y límite |
|---|---|
| `inputs` | Contrato de salida completo y, cuando están capturadas, entradas contra sus propios esquemas; restricciones de valores/claves/multiplicidad |
| `technical` | Estados de ejecución aportados; un artefacto externo deja esta dimensión no solicitada |
| `integrity` | Capturas verificadas por SHA-256/tamaño, metadatos físicos e identidades de entradas |
| `agreement` | Todas las parejas solicitadas; un solo resultado deja acuerdo no solicitado |
| `expected` | Una comparación completa por salida contra el mismo esperado fijado |
| `rules` | R por ejecución con sus entradas; artefactos sin entradas no permiten afirmar R |
| `coverage` | Salidas/comparaciones solicitadas e inspeccionadas; nunca se presentan muestras como equivalencia total |
| `independent_review` | O científico opcional, ligado a contrato/snapshots/plan/salida/esperado |

Estados: `passed`, `failed`, `not_evaluable`, `not_requested`, `pending_review`.
`operational_state` y `publishable` resumen los requisitos automáticos conservando
todas las dimensiones. O no bloquea por defecto una corrida operacional.
`require_expected=True` impide aprobación automática sin esperado;
`require_rules=True` impide aprobación sin R evaluable. Un esperado ausente
deja comparación no solicitada o no evaluable según el requisito; nunca acredita
corrección. Códigos de resultado: 0 aprobado operacionalmente, 1 incumplimiento,
3 no evaluable. Errores de configuración levantan una excepción.

Para artefactos externos, `require_rules=False` limita la aprobación al alcance
automático inspeccionado y deja R `not_requested`, aun si el contrato contiene
reglas marcadas obligatorias. Para exigirlas al publicar, el consumidor debe
usar `require_rules=True` y aportar la ejecución y sus entradas. Las ejecuciones
nativas evalúan las reglas del contrato automáticamente. Los snapshots externos
son opcionales: la cobertura completa describe salidas y comparaciones
solicitadas, mientras `input_execution_evidence_available` declara si existen
entradas de ejecución para todas las implementaciones.

El manifiesto `verification.json` incluye cada comparación, ejecución capturada,
reglas, identidad, procedencia y cobertura. JSON/HTML conservan motores/versiones,
políticas, tiempos, conteos, ejemplos y referencia al JSONL completo. La lectura
contrasta inventario cerrado, tablas, registros, reportes y decisiones derivadas.
Cada pareja y cada esperado conserva las identidades concretas comparadas y el
contrato, la política y el presupuesto solicitados en el expediente.
No interpreta código obtenido de JSON.

## Independencia y puente científico

`ExpectedProvenance` registra método, autores, autores de implementaciones,
dependencias de motores e independencia declarada. `derived_from_engines`
conserva si el esperado fue construido por un motor bajo prueba. Esa dependencia
impide establecer O aunque los valores coincidan.
Si `expected` es un `ExecutionResult`, Verify registra automáticamente
`expected_source_engine` y añade ese motor a la procedencia aportada; la
conversión a artefacto nunca elimina la dependencia observada.

`VerificationBinding` fija hashes de contrato, snapshots, plan, outputs y
esperado. `IndependentReviewEvidence` vincula un output, el paquete ciego,
documento científico de origen, asignación previa, dos revisiones y resolución
ante desacuerdo. Revisión incompleta o falta de arbitraje permanece pendiente.
La independencia exige personas declaradas distintas de autores, esperado
declarado independiente y decisiones compatibles con comparación completa.

El benchmark proporciona `oracle_verification_bridge` y
`OracleVerificationBridge`: valida `Scenario`, `Candidate` y `OracleResult`
existentes; conserva sus decisiones y hashes, y recibe explícitamente hash del
plan y dependencia del esperado. `evaluate_oracle`, `OracleResult` y el módulo
`oracle` conservan compatibilidad. El núcleo no importa el benchmark.

Los nombres en JSON no autentican personas, firmas ni autoría. Los hashes
acreditan integridad frente a una referencia, no veracidad. La declaración de
independencia conserva responsabilidad humana; el software no la inventa.
R/M/B/H mantienen sus entradas y algoritmos. Verify no entrena detectores ni
envía esperados, revisiones o salidas de otros motores a M/B.

## Evidencia portable

```python
bundle = ef.export_bundle(Path("evidence") / migration.migration_id, Path("portable"))
ef.import_bundle(Path("portable"), Path("relocated"))
checked = ef.read_bundle(Path("relocated"))
```

Soporta expedientes finalizados de migración, Verify y workflow. Copia los bytes
históricos bajo `operation/`, con manifiesto `bundle.json`, inventario relativo
cerrado, SHA-256/tamaños y mapa de URI históricas a miembros capturados. Verifica
de nuevo después de copiar. No reescribe manifiestos ni reportes anteriores.
El resolver temporal sólo admite miembros inventariados y restaura su contexto
incluso ante error. Rechaza traversal, enlaces simbólicos/junctions, archivos
adicionales, corrupción y referencias sin captura dentro del bundle.

`read_bundle(..., expected_sha256=...)` permite fijar externamente el hash de
`bundle.json`. Sin una referencia externa confiable, reemplazar todo el bundle
y su manifiesto por otro expediente coherente no se detecta como falsificación
de autoría. Las URI de procedencia externas sólo se vinculan si existe dentro
del expediente una captura de idéntico SHA/tamaño; nunca se descargan al leer.

Limitaciones: materialización local, presupuestos de comparación cooperativos,
sin cuotas RSS duras ni sandbox para código externo. No prueba equivalencia de
programas arbitrarios, transitividad con tolerancia ni independencia humana.
Verificar un bundle íntegro conserva su resultado semántico, incluido fallo.

## CLI

La solicitud `VerificationRequest` contiene contrato, salidas nombradas,
esperado opcional, snapshots, procedencia y requisitos. Su validación es de
metadatos; no inspecciona bytes ni ejecuta ETL.

```text
equiframe verify validate request.json
equiframe verify run request.json --output evidence
equiframe verify migration migration_run --output evidence
equiframe verify inspect evidence/verify_ID
equiframe bundle export migration_run portable
equiframe bundle import portable relocated
equiframe bundle verify relocated --sha256 SHA_DEL_BUNDLE_JSON
```

`verify run/migration`: 0 aprobado, 1 incumplimiento, 2 solicitud inválida,
3 no evaluable. `verify inspect` y `bundle verify`: 0 expediente íntegro,
3 corrupto; el JSON conserva su resultado semántico y no declara aprobación
por devolver 0. Export/import retornan 0 al copiar y comprobar, 2 por entrada
inválida y 3 por fallo operativo. Los lectores nunca vuelven a ejecutar motores.
