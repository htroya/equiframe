# EquiFrame Migrate

Desde `equiframe 0.10.0`, la biblioteca permite declarar una transformación,
ejecutarla nativamente en dos motores y comprobar las diferencias de sus
resultados. Pandas, Polars y DuckDB están disponibles en las seis direcciones de
las tres parejas. El contrato describe las propiedades exigidas; el plan
relacional describe las operaciones que ejecutan ambos compiladores.

El [diseño previo](MIGRATION_DESIGN.md) documenta la arquitectura. Las
comprobaciones de distribución y sus límites se registran en
[la revisión técnica histórica](MIGRATION_REVIEW.md). La extensión 0.11.0
incorpora [Verify](VERIFY.md), [workflows y operadores ETL](ETL.md) y
[bundles portátiles](VERIFY.md#evidencia-portable). La [matriz vigente](SEMANTIC_SUPPORT.md)
complementa las restricciones de la versión inicial descrita abajo. La validación
SERCOP acotada no constituye evaluación científica de la tesis.

## Instalar y ejecutar

Se requiere Python 3.12 y el wheel del equipo con `[engines]`, o los extras de
los dos motores elegidos. La publicación PyPI sigue pendiente. Importar
`equiframe` y validar metadatos no carga Arrow ni motores.

Este ejemplo declara una proyección identidad. La regla de esquema permite
exigir R; la política de índice autoriza expresamente ignorar el RangeIndex
generado por Pandas. El esperado literal se suministra por separado.

```python
from pathlib import Path
import equiframe as ef
import pyarrow as pa

schema = ef.TableSchema(
    columns=(ef.ColumnSpec(
        name="id", logical_type=ef.IntegerType(bits=64, signed=True),
        nullable=False, null_policy=ef.NullPolicy(representations=("null",)),
        numeric_policy=ef.NumericPolicy(comparison="exact", unit="identifier"),
    ),),
    keys=(), multiplicity="preserve", order=ef.IgnoredOrder(),
)
contract = ef.Contract(
    schema_version="1.0", contract_id="example.migration", revision=1,
    family="nulls_types",
    inputs=(ef.TableSpec(name="input", schema_spec=schema),),
    output=ef.TableSpec(name="result", schema_spec=schema),
    preconditions=(),
    rules=(ef.RuleSpec(
        rule_id="output_schema", revision=1, severity="error", required=True,
        specification=ef.SchemaCheck(table="result"),
    ),),
)
spec = ef.MigrationSpec(
    contract=contract, source_engine="pandas", target_engine="duckdb",
    ir=ef.RelationalPlan(nodes=(ef.Scan(node_id="scan", table="input"),), output="scan"),
    comparison_policy=ef.ComparisonPolicy(
        index="ignore", justification="Generated RangeIndex has no business identity.",
    ),
    options=ef.MigrationOptions(timeout_seconds=60.0, max_capture_rows=100),
)
result = ef.migrate(
    spec,
    source=ef.LocalDataSource({"input": ef.ArrowInput(pa.table({"id": [1, 2]}))}),
    expected=ef.ArrowInput(pa.table({"id": [1, 2]})),
    work_dir=Path("migration-runs"),
)
print(ef.migration_summary(result))
verified = ef.read_migration(Path("migration-runs") / result.migration_id)
assert verified == result
```

El [ejemplo de montos y monedas](../packages/equiframe/examples/migrate_native.py)
ejecuta las seis direcciones con Decimal exacto, grupos sin valores y conteos.
Su esperado es literal e independiente de los compiladores. Los datos son
sintéticos: sus resultados no sustituyen el corpus ni las revisiones de la tesis.

## Operaciones admitidas

El IR 1.0 contiene un DAG de `Scan`, `Project`, `Filter`, `Cast`, `EquiJoin`,
`Aggregate` y `Sort`. Las expresiones incluyen columnas, literales tipados,
comparaciones, booleanos de tres estados, negación, `IsNull` e `IsNaN`.
No permite referencias futuras, nodos huérfanos, SQL libre ni código Python en JSON.
Los modelos estrictos rechazan campos y coerciones no declarados.

| Aspecto | Política explícita |
|---|---|
| Join inner/left | Claves ausentes iguales o sin coincidencia; duplicados conservados |
| Agrupación | Retener o descartar grupos ausentes; suma vacía nula o cero |
| Dinero | Decimal hasta precisión 38; unidad preservada; overflow rechazado |
| Cast | Identidad o ensanchamiento exacto; pérdida rechazada |
| Orden | Dirección, posición de ausencias y tratamiento de empates |
| Float | Transporte, predicados y count_valid; claves, agrupaciones, sum/min/max y orden float fuera del IR inicial |
| Tiempo | Timestamp y operaciones temporales fuera del IR inicial; date64 tiene incompatibilidades de transporte declaradas |

NULL y NaN se mantienen distintos. Un tipo físico de entrada incorrecto no se
convierte para satisfacer el contrato. El adaptador conserva la procedencia
física; `engine_type` es metadato de procedencia, no una propiedad inferible de
los bytes Arrow. El IR no incorpora un índice Pandas significativo: debe
representarse como columnas antes de llamar al migrador. Incluso un índice
generado requiere una política explícita para ignorarlo en la comparación.

Los compiladores comprueban capacidades sin ejecutar ETL. En DuckDB se rechazan
planes cuya optimización pueda eliminar la comprobación declarada de un
Aggregate o la semántica de un Sort intermedio; los sufijos Sort admitidos
conservan sus controles. Los identificadores con NUL y los literales Decimal
no representables se rechazan; el NUL dentro de un literal de texto se conserva.
La intersección inicial es deliberadamente acotada.
Polars comprueba SUM con una cota conservadora basada en el máximo absoluto y
las filas del frame: puede rechazar un cálculo cuyo total final sería
representable por cancelación o separación de grupos. Los controles dependientes
de los valores se aplican también durante la ETL; el preflight no garantiza que
todos los cálculos futuros sean representables.

## Captura, comparación y decisiones

`check_migration(spec)` comprueba el IR y el contrato en ambos compiladores.
No lee fuentes ni acredita dependencias instaladas o capacidades de una tabla
concreta. `migrate` verifica esas condiciones antes de ejecutar cualquiera de
las transformaciones. Captura cada entrada una sola vez y separa sus buffers de
los del consumidor; los dos pipelines reciben esas capturas fijadas.

La comparación origen/destino distingue `equivalent`, `different` y
`not_evaluable`. Si se entrega `expected`, se captura antes de las ETL y cada
salida se compara contra ese mismo artefacto. `verification="correct"` significa
que ambas salidas resultaron equivalentes al esperado suministrado bajo la
política declarada. No acredita autoría independiente, revisión humana ni una
etiqueta O confirmada. Dos salidas iguales pueden compartir el mismo error.
Sin esperado, la comprobación independiente permanece no solicitada.

Los reportes nuevos nombran esa operación como comparación con el esperado
aportado. `migration_summary` conserva la clave histórica
`independent_verification` por compatibilidad y añade `expected_output_comparison`
con el mismo valor, junto con `comparisons.source_target`, `source_expected` y
`target_expected`: cada una conserva estado, completitud, ID y conteo de diferencias.
`equiframe_verify` identifica **EquiFrame Verify (O)** con estado
`not_established`: el migrador no recoge autoría independiente del esperado ni
dos revisiones humanas independientes. Ese estado tampoco equivale a una etiqueta
divergente. EquiFrame Verify establece si una salida cumple el contrato mediante
un resultado esperado independiente, comparación de contenido y revisión humana;
la comparación automática C es uno de sus componentes.
El lector acepta reportes históricos completos o el formato ampliado completo;
ambos conservan las verificaciones físicas, eventos e inventarios existentes.

Por defecto `require_rules=True` exige la completitud existente del pipeline,
incluida R. Un contrato sin reglas evaluables conserva su estado no evaluable.
Para un uso que requiera solo migración y comparación puede declararse
`require_rules=False`: la completitud del migrador exige ejecución y los
componentes solicitados de perfil/detección, además de las comparaciones.
Los resultados hijos mantienen su propia completitud, disponibilidad de R/H y
motivos; la opción no transforma un componente ausente en «sin alerta».
Las alertas disponibles siguen afectando el código de salida.

Un perfil explícito y un `detector_bundle` compatible reutilizan R/perfil/M/B/H.
La migración no entrena, recalibra ni introduce el esperado en las variables de
los detectores. Las salidas originales y las diferencias se conservan.

## Evidencia y límites

Cada operación crea un directorio nuevo. Contiene especificación, captura,
pipelines, comparaciones, eventos encadenados, reportes e inventario. El
manifiesto `migration.json` se publica al final. Una publicación fallida deja
evidencia parcial y no publica una finalización exitosa.

`read_migration(directory)` verifica hashes/tamaños, inventario cerrado, URI
locales dentro de la operación, metadatos físicos, conteos y ejemplos de
diferencias, eventos, configuraciones y resultados hijos. La verificación
física requiere Arrow; no reejecuta ETL ni compila planes. `verify=False` valida
solo el modelo JSON y no acredita integridad. Las URI actuales están vinculadas
al directorio original: este resultado no es por sí solo un bundle portátil.
`ef.inspect_evidence(directory)` reconoce también operaciones interrumpidas.

`MigrationOptions.max_capture_rows` suma las filas de entradas y esperado.
`max_capture_bytes` limita sus buffers y los del índice conservado. Los límites
se comprueban tras materialización y no constituyen
cuotas duras de RSS. El timeout total reduce los presupuestos de cada hijo;
cancelación y timeout se comprueban en puntos cooperativos. Un proveedor o
plugin síncrono que no devuelve control no puede ser interrumpido por esos
puntos. La ejecución DuckDB conserva la interrupción disponible en su adaptador.

## CLI y extensiones

```bash
equiframe migration validate spec.json
equiframe migration run request.json --output migration-runs
equiframe migration run request.json --output migration-runs --bundle detectors.json
equiframe migration verify migration-runs/migration_ID
```

`validate` recibe `MigrationSpec`. `run` recibe `MigrationRequest`, con nombres
de entrada exactos y referencias Arrow/Parquet; las referencias incluyen hash,
tamaño y formato. No descubre ni carga plugins desde el JSON.

| Comando | Código y significado |
|---|---|
| run | 0: requisitos completos sin diferencias/alertas; 1: completos con diferencias/alertas |
| run | 2: preflight o captura inválidos; 3: fallo operacional, cancelación, límite o no evaluable |
| validate | 0: soporte del plan; 2: entrada o capacidad inválida; 3: fallo de E/S |
| verify | 0: evidencia íntegra, incluso con resultado fallido; 3: integridad inválida |

Para otro motor, el consumidor registra explícitamente un `PlanCompiler` en su
`CompilerRegistry` e inyecta un `EngineAdapter`. El compilador entrega una
`Transformation`, huellas y diagnóstico; el adaptador ejecuta y captura el
resultado. Ambos son código confiable del consumidor, no un sandbox. La API
acepta `DataSource`, `RuleRegistry`, cancelación y bundle de detectores por
inyección. Añadir un motor exige probar sus capacidades semánticas; registrar
un nombre no demuestra compatibilidad universal ni traduce callbacks existentes.
