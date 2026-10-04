# Ingestión, workflows y publicación local

Estas API del núcleo son independientes del dominio. Los módulos no importan
Pandas, Polars, DuckDB ni Arrow al importar EquiFrame; Arrow se carga al acceder
a datos. El ejemplo completo requiere el extra `engines` y Python 3.12.

```bash
cd packages/equiframe
uv run --locked --all-extras python examples/etl_local.py --output retail-etl
```

El consumidor sintético de comercio conserva `001` como texto, calcula importes
Decimal por moneda en Pandas/Polars y renombra una salida en DuckDB/Pandas. Sus
dos checkpoints tienen esperados de construcción manual separados del IR. Luego
Verify inspecciona salidas y esperado, el destino valida staging y publica
Parquet. No son datos SERCOP ni evidencia científica O; O queda `not_requested`.
Reejecutar crea otra versión y conserva las anteriores.

## Ingestión explícita

`IngestionSpec` declara formato CSV/JSON/JSONL, encoding, delimitador, cabecera o
fieldnames, extracción, campos adicionales, política de registros inválidos y
presupuestos. `FieldMapping` declara cada `ColumnSpec`, ruta, ámbito, tokens de
NULL, campos faltantes, separadores decimales, tokens booleanos y formato de día.
No hay inferencia que apruebe un contrato. Los strings no convierten números a
identificadores; no se recortan espacios, cambian mayúsculas o pierden ceros.

```python
from pathlib import Path
from equiframe.ingestion import FieldMapping, IngestionSpec, ingest_file

spec = IngestionSpec(format="csv", fields=(
    FieldMapping(column=id_column_spec, path=("id",)),
    FieldMapping(column=money_column_spec, path=("amount",),
                 decimal_separator=",", thousands_separator="."),
))
result = ingest_file(Path("source.csv"), spec=spec, work_dir=Path("evidence"))
assert result.state == "completed"
```

`id_column_spec` y `money_column_spec` son `ColumnSpec` aprobados por el consumidor.
Los importes se parsean con Decimal y rango/escala comprobados, sin float ni
redondeo automático. La agrupación de miles exige bloques de tres dígitos.
Booleanos no se aceptan como números. Float32 exige representabilidad exacta;
los especiales NaN/Infinity de importadores quedan rechazados, aunque las API
Arrow existentes pueden conservarlos bajo contratos explícitos.

NULL JSON, token CSV autorizado y campo inexistente quedan distintos en los
recibos. Campo faltante exige `missing="null"` para convertirse en NULL. Vacío y
cero no son NULL salvo tokens declarados; una cadena vacía numérica inválida no
se repara. Cabeceras duplicadas, miembros JSON duplicados y NaN JSON se rechazan.
Un documento JSON vacío o compuesto solo de espacios es inválido y no publica
una tabla. Una colección JSON explícita `[]` con `records_path=("*",)` y un
stream JSONL de cero registros sí pueden producir una tabla vacía válida.

Fechas ISO o `date_format` declarado producen días. Timestamps ISO conservan
nanosegundos cuando la unidad los admite. Un tipo con zona exige offset explícito
y coherente con IANA; un tipo sin zona exige timestamp sin offset. No se asume
zona ni se resuelve DST por conveniencia. Desbordamiento o pérdida de unidad se
rechaza o pone en cuarentena según `invalid_records`. Los ticks se comprueban
contra el rango int64 de Arrow antes de materializar la tabla; los límites
exactos son válidos. La semántica temporal adicional del contrato sigue en los validadores
y Verify; la ingestión no acredita por sí sola todas las reglas de negocio.

JSON anidado requiere `records_path` explícito, por ejemplo
`("records", "*", "awards", "*")`. Cada `*` expande exactamente un array y
cambia el grano de forma registrada. `scope="ancestor", ancestor_levels=2`
consulta el objeto dos saltos anteriores (el objeto padre si el último salto
cruza un array); `root` consulta la raíz. Las rutas de campo no expanden arrays.
El consumidor debe mantener claves y puentes; el núcleo no adivina OCDS ni
repite montos al expandir proveedores/ítems.

`ingest_file` conserva `source.original`, SHA-256/tamaño/URI y `source.json`;
`ingestion.json` guarda especificación, conteos, recibos por campo y registros
invalidos con su ruta. Estado `rejected` no publica la tabla parcialmente
aceptada. `quarantined` publica solo aceptados pero conserva cobertura incompleta.
`FileInput.load` exige `completed`: el consumidor decide explícitamente si usar
un artefacto con cuarentena después de revisar su recibo.

El archivo se copia con comprobación de bytes antes de parsing. La implementación
actual materializa texto, estructuras JSON, recibos y salida Arrow; no anuncia
streaming limitado en RSS. `max_source_bytes` se comprueba durante copia;
`max_records` durante procesamiento del grano expandido. JSON puede haber
expandido estructuras antes del control de registros. Los controles de contexto
son cooperativos, sin interrupción de cualquier llamada Python bloqueada.

## Workflow y checkpoints

`WorkflowSpec` contiene etapas ordenadas `WorkflowStage`. Cada una usa un
`MigrationSpec` existente y enlaces `InputBinding(name, source, stage=None,
output="target")`. Enlaces externos usan nombres del `DataSource`; enlaces con
`stage` identifican exactamente el nombre de salida de una etapa anterior.
Se rechazan duplicados, ciclos, referencias futuras y cobertura incorrecta de
entradas. Varias etapas admiten varias entradas y salidas.

`run_workflow(spec, source=..., expected={stage_id: artifact}, work_dir=...)`
captura las fuentes externas una sola vez y copia esperados antes de ejecutar.
Cada migración vuelve a fijar esos mismos artefactos para sus dos motores,
usando el runner existente. Una etapa divergente/incumplida/no evaluable bloquea
sus dependientes; etapas independientes pueden continuar. Nunca genera un
resultado exitoso de una etapa saltada. `first_divergent_stage` identifica el
primer checkpoint con comparación/esperado divergente; no atribuye el origen
del error a una operación interna que no fue observada.

Cada checkpoint representa una correspondencia semántica declarada entre las
dos implementaciones de una salida. El DAG relacional interno no constituye un
workflow. Implementaciones externas continúan usando registros/adaptadores
confiables explícitos; no se descubren plugins ni se ejecuta código en JSON.
`resume=True` se rechaza; no hay reutilización de checkpoints en esta versión.

`WorkflowResult.complete` exige todas las etapas aprobadas; `outputs` solo expone
las etapas aprobadas. `exit_code`: 0 aprobación completa, 1 incumplimiento
semántico/reglas observado, 3 fallo técnico/no evaluable/saltado. El JSON
`workflow.json` conserva especificación, fuentes y expedientes de cada etapa.
`read_workflow` verifica inventario cerrado, hashes, referencias y cada migración
hija sin ETL. Los bundles usan el exportador general de evidencia y conservan
la separación entre integridad del expediente y aprobación semántica.

## Semántica IR ampliada

| Operación | Semántica/condiciones | Motores/direcciones | Prueba |
|---|---|---|---|
| Project/renombrado | Expresiones sobre entrada; nombres y orden declarados | Los tres/seis | `test_arithmetic_coalesce_conditional_and_projection_expected`, `test_etl_expression_all_six_migration_directions` |
| Arithmetic integer | Suma/resta signed; multiplicación operandos <=32 bits; promoción exacta antes de operar; rango salida rechazado | Los tres/seis en fixture | `test_integer_overflow_is_failure_not_wrapped_success` |
| Arithmetic decimal | Suma/resta; mismo tipo/unidad/escala; salida con al menos un dígito adicional; entrada precisión <=37 | Los tres | `test_decimal_guard_digit_addition_is_exact` |
| Coalesce | Primer valor no NULL; NaN no es NULL; tipos/unidades idénticos | Los tres/seis en fixture | `test_etl_expression_all_six_migration_directions` |
| Conditional | Predicate TRUE elige then; FALSE/NULL elige otherwise; ramas mismo tipo/unidad | Los tres/seis en fixture | `test_etl_expression_all_six_migration_directions` |
| Concatenate | Esquemas ordenados idénticos incluido nullable/unidad; UNION ALL conserva duplicados | Los tres | `test_concatenate_preserves_and_dedup_requires_explicit_all_columns` |
| Deduplicate | Criterio explícito todas las columnas; solo filas idénticas; NULL equal; sin float | Los tres | La prueba anterior incluye rechazo de clave parcial |
| Semi/anti join | Existencia/no existencia; conserva multiplicidad izquierda; política NULL equal/never | Los tres | `test_native_semi_anti_keep_left_multiplicity` |
| Right/full | Rechazado con diagnóstico de capacidad | Ninguno | `check` del compilador |
| Timestamps IR/división/decimal multiply | Pendiente y rechazado en IR común | Ninguno | Restricciones del validador |

La aritmética que puede fallar no se admite dentro de Conditional, Coalesce o
lógica booleana, porque los motores difieren en evaluación anticipada de ramas.
DuckDB rechaza operaciones posteriores a Project con aritmética salvo Sort:
su optimizador podría podar el error. Se exige checkpoint materializado antes
de filtros/proyecciones que oculten posibles errores. No se presentan esos
rechazos deliberados como fallos del código.

## Destino Parquet

`Destination` es un puerto; `ParquetDestination(root)` implementa almacenamiento
local. `publish(tables, run_id=..., verifications=..., policy="create")` exige un
gate de Verify por tabla. Acepta rutas a expedientes o resultados persistidos;
relee el expediente cerrado y comprueba que el SHA-256 publicado pertenece a las
salidas realmente inspeccionadas y que `publishable` está aprobado. El resultado
completed de una ejecución no basta. O humano no es requisito automático.

Los nombres de tablas deben ser distintos también al ignorar mayúsculas: no
se admite publicar simultáneamente `Table` y `table`, porque sus archivos
colisionan en filesystems como el Windows comprobado. La API rechaza el caso
antes de crear staging o cambiar el previo; `LoadReceipt` impone la misma
restricción al leer. Se rechazan las colisiones, sin renombrar ni unir tablas.

Se escriben todas las tablas en `.staging`, se leen y comparan completamente bajo
el contrato/política de Verify, se publica una versión inmutable y se sustituye
`current.json` mediante `os.replace`. El único punto de visibilidad es ese puntero
en el mismo filesystem local. Los lectores usan `current()` y verifican hashes,
inventario y conteos Parquet. Los lectores que abren directamente staging no
cumplen ese contrato.

`create` rechaza un destino publicado; `replace` conserva todas las versiones
previas. Repetir `run_id` con los mismos bytes devuelve el mismo recibo sin
duplicar filas; con bytes distintos se rechaza. Un retry antiguo tampoco cambia
una versión más nueva. Si cayó la escritura del puntero después de publicar la
versión, el retry puede completar esa publicación cuando el previo aún coincide.

La exclusión usa `.publication.lock` y admite un escritor cooperante. La
garantía es sustitución atómica de visibilidad local, sin afirmar transacción
distribuida ni durabilidad ante corte eléctrico. Excepciones controladas limpian
staging, dejan el puntero previo y producen error. Una caída del proceso puede
dejar lock/staging/versión huérfana; inspeccionar antes de retirar el lock.
No hay escritores de DW ni varios escritores DuckDB compartidos.

`LoadReceipt` conserva identidad, policy, previo, SHA-256 fuente/Parquet, filas
y gate de Verify. La prueba `test_failure_halfway_loading_multiple_tables_keeps_previous`
inyecta fallo en la segunda escritura; `test_idempotent_load_versions_create_replace_and_row_counts`
comprueba repetición y conservación. Otros controles rechazan esperado fallido,
hash de salida distinto y evidencia alterada.
