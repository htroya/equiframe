# EquiFrame Benchmark

El README forma parte de los metadatos del wheel/sdist. Los enlaces al monorepo
pueden requerir acceso al repositorio privado. Los ejemplos, tests, herramientas
y JSON Schema completos se incluyen en el **sdist**; el wheel contiene la API,
CLI y recursos runtime. Hasta resolver licencia y acceso público, use artefactos
identificados del equipo y `--no-index --find-links` para evitar paquetes ajenos.

Distribución experimental `equiframe-benchmark 0.11.0`, Python 3.12. Catálogo,
EquiFrame Verify (validación independiente de equivalencia), grupos transitivos,
particiones y evaluación para `equiframe 0.11.0`. El núcleo no importa este paquete.

El paso 8 incorpora `equiframe-benchmark validate`, `split` y `pilot`, y usa
la orquestación operacional en las quince ejecuciones nativas del piloto.
[Comandos y límites](../../docs/ORCHESTRATION.md#benchmark-separado).

El paso 9 añade snapshots verificados, `run_integration`/`read_integration`,
conciliación exacta de adjudicaciones y CLI `integrate`/`verify-integration`.
La conexión al cliente/DW reales permanece pendiente. [Diseño y límites](../../docs/STEP_09_DESIGN.md).

## Instalar y ejecutar

Desde la raíz del repositorio, con acceso al código:

```bash
python -m pip install "./packages/equiframe[engines]" ./packages/equiframe-benchmark
python -m equiframe_benchmark.pilot --output ./tmp/pilot-step6
```

El destino debe ser nuevo. También se instala el comando
`equiframe-benchmark-pilot --output ./tmp/otro-piloto`.
La base requiere Arrow; el extra `engines` agrega Pandas, Polars y DuckDB.
No está publicado en PyPI. Con los dos wheels construidos y dependencias
disponibles se puede instalar por nombre:

```bash
python -m pip install packages/equiframe/dist/equiframe-0.11.0-py3-none-any.whl packages/equiframe-benchmark/dist/equiframe_benchmark-0.11.0-py3-none-any.whl
```

El piloto genera 5 escenarios, 35 candidatos, 15 perfiles y 4 grupos. Las
35 revisiones permanecen pendientes. Las 15 mutaciones son inyecciones sobre
artefactos; las 15 transformaciones de control sí son ejecuciones nativas.
Son pruebas técnicas sintéticas, no los 60 escenarios/300 perfiles de la tesis.

## API de revisión

```python
from pathlib import Path
import equiframe_benchmark as eb

catalog = eb.load_document(eb.Catalog, Path("tmp/pilot-step6/catalog.json"))
splits = eb.load_document(eb.SplitManifest, Path("tmp/pilot-step6/splits.json"))
eb.validate_splits(catalog, splits)
print(eb.split_counts(catalog, splits))

scenario = catalog.scenarios[0]
candidate = eb.load_document(
    eb.Candidate, Path("tmp/pilot-step6/nulls_types/pandas-candidate.json")
)
packet = eb.review_packet(scenario, candidate, directory=Path("tmp/revision"))
pending = eb.evaluate_oracle(scenario, candidate, packet=packet, work_dir=Path("tmp/oracle"))
assert pending.status == "pending" and pending.label is None
```

Entregar al revisor solo la carpeta del paquete ciego. Conservar aparte catálogo,
candidatos, alertas y decisiones de los otros revisores. Registrar previamente
`ReviewAssignment` con dos revisores y un árbitro independientes y `assigned_at`
UTC. Después guardar cada `Review` como documento nuevo, con hash del paquete,
persona, decisión, razón, `recorded_at` UTC y `blind_attestation=True`.
Pasar esos documentos a `evaluate_oracle(..., assignment=..., reviews=(a, b))`;
`resolution=...` se permite solo ante desacuerdo y con el árbitro asignado.
No autogenerar decisiones humanas a partir del resultado del comparador.

## Entrenamiento del paso 7

```python
selection = eb.select_normal_training(
    catalog,
    splits,
    candidates=candidates_by_id,
    oracles=oracles_by_id,
    executions=executions_by_id,
    profiles=profiles_by_id,
)
eb.save_document(selection, Path("training-selection.json"))
import equiframe as ef

bundle = ef.fit_preprocessor(selection.training, spec=selection.training.profiles[0].spec)
```

Los cuatro mapas deben contener los mismos IDs de candidato, una sola familia
y definición de features, y exclusivamente casos normales confirmados de
entrenamiento. El piloto pendiente no es admisible. Los hashes aseguran
integridad/trazabilidad, no identidad humana ni veracidad de un productor hostil.

## Desarrollo y verificación

Desde `packages/equiframe-benchmark`, con `uv` en PATH:

```bash
uv sync --locked --all-extras
uv run --locked --all-extras ruff check .
uv run --locked --all-extras ruff format --check .
uv run --locked --all-extras mypy
uv run --locked --all-extras python tools/generate_assets.py --check
uv run --locked --all-extras pytest -q
uv run --locked --all-extras python -m build --no-isolation
uv run --locked --all-extras python tools/verify_distribution.py
```

La última comprobación requiere el wheel de `equiframe 0.11.0` construido en
`../equiframe/dist`. Instala ambos paquetes por nombre con pip fuera del checkout,
comprueba imports ligeros, ejecuta la suite y piloto instalados, y reconstruye
el wheel desde sdist. La matriz de cinco plataformas está disponible solo mediante
despacho manual autorizado; permanece desactivada por la cuota de Actions.

Arquitectura, límites y decisiones: `docs/STEP_06_DESIGN.md` en el repositorio.
IF/MAD/H están disponibles desde el núcleo 0.7.0. No hay métricas científicas finales, integración productiva SERCOP/DW
ni aprobaciones científicas en esta distribución. La licencia y publicación pública permanecen pendientes.

## Selección normal de calibración y soporte por grupos

`select_normal_calibration` recibe los mismos argumentos nombrados que
`select_normal_training`, pero exige la partición de calibración. Conserva
las comprobaciones de O normal confirmado, captura exacta, artefactos íntegros
y una sola familia. Entrega `CalibrationSelection.calibration` al núcleo.

Antes de ajustar, audite ambas selecciones:

```python
audit = eb.audit_detector_selections(
    training_selection,
    calibration_selection,
    min_training_groups=3,
    min_calibration_groups=2,
    rationale="Mínimos del ejemplo; deben justificarse antes de congelar",
)
if audit.state != "eligible":
    raise ValueError("Grupos insuficientes: ampliar el piloto antes de ajustar")
fit = ef.fit_detectors(
    training_selection.training,
    spec=training_selection.training.profiles[0].spec,
    config=ef.IsolationForestConfig(random_state=7),
    support=ef.DetectorSupport(
        min_training_rows=20,
        min_calibration_rows=10,
        rationale="Mínimos técnicos del ejemplo, sin garantía inferencial",
    ),
)
bundle = ef.calibrate_detectors(fit, calibration_selection.calibration, alpha="0.05")
```

La auditoría exige igual catálogo/split, features compatibles y ausencia de
escenarios, grupos, ejecuciones o perfiles compartidos. Devuelve cantidades de
grupos y `eligible`/`not_estimable`; el llamador debe conservarla y respetarla.
La biblioteca general no puede autenticar declaraciones de normalidad o grupos.
Ningún umbral de ejemplo es aprobación del protocolo científico. El piloto
original conserva sus 35 revisiones pendientes; no se usa para producir un
modelo científico ni se amplía con revisiones automáticas.

## Integración del paso 9

`SnapshotDataSource` recibe un ID de publicación y un cliente confiable inyectado.
`run_integration` ejecuta las tres implementaciones registradas, verifica sus
entradas y compara las tres parejas. Un esperado opcional se fija antes de las
corridas; conservar un `ExecutionResult` conserva también sus precondiciones.

```bash
equiframe-benchmark integrate integration.json --snapshot-id snapshot-2026-01 \
  --client mi_cliente:create_client --registry mis_etl:create_registry \
  --output integration-runs --expected expected.arrow
equiframe-benchmark verify-integration integration-runs/integration_ID
```

Los factories se importan y ejecutan por solicitud explícita: deben ser código
confiable. El JSON no define callbacks ni contiene credenciales. Los códigos
0/1/2/3 siguen la completitud y alertas del resultado; verificar correctamente
un expediente incompleto devuelve 0 y conserva `complete=false` en el resumen.

El ejemplo `examples/integration_local.py` usa datos sintéticos, tres motores
reales y decimales por moneda. Comprueba resultados esperados e inventarios;
conserva una alerta parcial de Pandas por su precisión decimal nativa. La
comparación lossless no desactiva esa regla de contrato. `reconcile_awards`
comprueba grano e importes exactos con columnas configuradas y no genera O.
Cliente productivo, snapshots representativos del DW, DDL/mapeos y aceptación OCI
siguen pendientes. El consumidor público acotado actual está en
[caso SERCOP](https://github.com/htroya/equiframe/blob/main/docs/SERCOP_EXAMPLE.md).

## Evaluación y reproducción del paso 10

`FreezeDefinition` fija catálogo, particiones por grupos, casos de prueba, cinco
familias, selecciones/modelos previos, doce decisiones metodológicas, archivos
con SHA/tamaño, versiones y protocolos de evaluación/coste. Un sello de piloto
verifica integridad y conserva los bloqueos científicos. Un sello final exige
resolverlos; no genera revisiones ni ajusta modelos con prueba.

```bash
equiframe-benchmark freeze definition.json --output freeze.json
equiframe-benchmark verify-freeze freeze.json
equiframe-benchmark run-study freeze.json --registry mis_etl:create_registry --output studies
equiframe-benchmark verify-study studies/study_ID
equiframe-benchmark evaluate studies/study_ID --output evaluation.json
equiframe-benchmark tables studies/study_ID --output regenerated-tables
equiframe-benchmark bundle-study studies/study_ID --output portable-study
equiframe-benchmark reproduce-study portable-study --expected-sha256 SHA_DEL_BUNDLE_JSON
```

La comparación principal exige O confirmado y R/M/B/H completos sobre los mismos
casos. Se conservan soporte propio, alertas parciales, fallos y exclusiones.
Precisión, recall, F1 y FPR indefinidos quedan vacíos con un motivo explícito.
AP requiere dos clases y una misma familia/modelo. El bootstrap remuestrea grupos
enteros, conserva réplicas indefinidas y requiere una justificación previa de
independencia. Los seis CSV contienen los denominadores y se regeneran desde
registros íntegros; editar un CSV y recalcular su hash no altera la evidencia válida.

`costs spec.json --bundle detector.json --output costs-runs` compara perfil+M
aislado con comparación exhaustiva sobre capturas existentes. Hace un calentamiento
y cinco repeticiones por método, alterna el orden y registra tiempo, CPU y RSS.
No incluye ETL inicial ni llama al detector MAD al medir M. Instalar el extra
`resources` habilita psutil; un monitor fallido conserva medidas ausentes y motivos.
RSS es máximo absoluto muestreado, no asignación neta ni límite duro de memoria.
`cost-table costs-runs/cost_ID --output costs.csv` conserva las doce observaciones
crudas, sus unidades y motivos; no las suma ni las convierte en réplicas independientes.

`run-study` devuelve 1 ante alertas de un estudio completo y 3 si queda incompleto;
`costs` devuelve 3 si la medición queda incompleta. Los lectores `verify-*` devuelven
0 al verificar correctamente un expediente incompleto y conservan sus estados.

Los bundles copian bytes originales, capturas y fuentes congeladas sin reescribir
sus manifiestos. `reproduce-study` verifica el inventario y regenera tablas desde
decisiones capturadas. La repetición de ETL por un compañero es un criterio externo
pendiente; este comando no inventa su ejecución ni su aprobación. No hay todavía
corpus científico cerrado, métricas finales ni resultados para capítulos 4/5.

El paso 10 inventaría licencia, nombre, metadatos, dependencias y tipado; no reserva
un nombre ni publica en PyPI. Ver [diseño](../../docs/STEP_10_DESIGN.md),
[evaluación](../../docs/STEP_10_EVALUATION.md) e
[inventario de distribución](../../docs/STEP_10_DISTRIBUTION.md).

## Puente de Verify 0.11.0

`OracleVerificationBridge` y `oracle_verification_bridge` vinculan los tipos
históricos `Scenario`, `Candidate`, `OracleResult` con `VerificationBinding`,
procedencia del esperado y revisiones del núcleo. `evaluate_oracle` conserva su
API. El plan y la dependencia del esperado se suministran explícitamente; no se
infieren revisores reales ni se autentican nombres JSON. El núcleo puede usar
Verify sin instalar este paquete.

Se fijó `equiframe==0.11.0`; extras y locks reflejan esa pareja. Twine se incorpora
al entorno de desarrollo. La CI es manual y la matriz remota del candidato no fue
ejecutada. [Candidato, controles y pendientes](https://github.com/htroya/equiframe/blob/main/docs/RELEASE_CANDIDATE.md).
