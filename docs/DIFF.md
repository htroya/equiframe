# Entrada directa y contratos de comparación

STEP2, candidato privado 0.11.1. La nueva fachada `ef.diff` conserva el núcleo,
los estados y los formatos 1.0 de `compare`. No ejecuta transformaciones, SQL ni
planes lazy. `ComparisonResult` sigue siendo el resultado; no añade métodos
`summary`, `to_html` o `assert_equivalent`.

## Una llamada e inspección

```python
from pathlib import Path
import equiframe as ef
import pyarrow as pa

expected = pa.table({"id": ["A", "B"], "quantity": [10, 20]})
candidate = pa.table({"id": ["B", "A"], "quantity": [21, 10]})
result = ef.diff(candidate, expected, keys=["id"], work_dir=Path("evidence"))
print(result.state, result.complete, result.counts)
declaration = ef.read_diff_contract(result)
print(declaration.model_dump_json(indent=2))
for difference in ef.iter_differences(result.differences):
    print(difference.code, difference.key, difference.column)
```

El esperado está a la **derecha** y `reference="expected"` es el default de
`diff`. El default de la API previa `compare` sigue siendo `"peer"`. Un esperado
inválido produce `not_evaluable / invalid_expected` aunque el recorrido termine.
La coincidencia no acredita independencia ni corrección del esperado.

Sin `keys`, se usa multiconjunto: se ignora el orden de filas y se conserva su
multiplicidad. `keys` declara una clave única de tabla, posiblemente compuesta;
no se infiere identidad de muestras. El núcleo comprueba todas las filas,
claves crudas y normalizadas, ausencia y unicidad global. Si no puede usar esa
clave, conserva su fallback a bolsa/matching y sus infracciones. No inventa
filas modificadas por un alineamiento ambiguo. `incomplete="allow"` en un
constructor autoriza ausencias de clave, no elimina la comprobación de unicidad.

## Constructores e inferencia

- `bag_contract(columns, ...)`: multiconjunto, `multiplicity="preserve"`
- `keyed_contract(columns, keys=[...], incomplete="reject", ...)`: clave explícita
- `sequence_contract(columns, by=[SortSpec(...)], ties="preserve", ...)`: orden
  significativo y validado, exactamente como el contrato existente; no ordena
  datos ni inventa una modalidad de secuencia sin criterio de orden
- `infer_diff_contract(schema, keys=..., column_overrides=..., ...)`: usa un
  `pyarrow.Schema` de referencia y políticas conservadoras
- `DiffContract.from_contract(contract, ...)`: conserva un contrato existente

Los constructores devuelven `DiffContract`: `spec` es el `ComparisonSpec`
existente, `reference` define el papel de la derecha y `provenance` identifica
el origen de cada campo hoja mediante JSON Pointer. Se puede consultar
`provenance_for(path)` y serializar/validar con `model_dump_json` y
`DiffContract.model_validate_json`. Los modelos son inmutables y rechazan
campos extra. Los esquemas están en `packages/equiframe/schemas`.
`DiffInput` ofrece el union preciso para typing estático. Su alias en runtime
usa `object` para tipos opcionales, evitando importarlos; no debe utilizarse
como validador de admisión. La captura comprueba las clases reales.

`diff(..., contract=declaration)` reutiliza exactamente esas decisiones.
No admite sobrescribir `keys`, `policy` o `reference` de un `DiffContract`:
construya uno nuevo. Con un `Contract` previo puede pasar `policy` y `reference`,
pero no `keys`. Los `ColumnSpec` explícitos son la ruta profesional para
nulabilidad, unidades, tolerancias, ausencias, valores permitidos y tiempo.

La inferencia automática consulta únicamente el esquema de la captura derecha,
antes de comparar. Nunca modifica políticas para acomodar discrepancias:

- Nombres, familia física, ancho/signo de enteros, precisión/escala Decimal y
  unidad/zona temporal proceden de metadatos de la referencia
- `nullable=True` es un default visible; no se concluye no nulabilidad por no
  haber visto NULL ni por la muestra
- Solo NULL representa ausencia; NaN se mantiene distinto de NULL
- Los números usan igualdad exacta con `unit="unspecified"`: etiqueta explícita
  de escala sin interpretación de negocio. No se infiere moneda, unidad física
  ni conversión. Unidades de dominio y tolerancias requieren política explícita
- Timestamp naive conserva wall time; timestamp zoned conserva unidad y zona
  IANA y compara instantes. No se adivina zona ni se redondea precisión
- Tipo `null` sin dominio, Decimal de escala negativa, tipos anidados,
  diccionarios/categorías y tipos ajenos al contrato no se convierten a otro
  tipo para obtener un veredicto. Se exige un tipo/política explícito cuando
  existe una representación admitida; otros casos permanecen no soportados

Una tolerancia explícita conserva la fórmula simétrica del núcleo y el matching
máximo de bolsa; no se aprende del par ni se usa para definir claves. Decimal
permanece exacto. `multiplicity="distinct"` exige ausencia de duplicados, no
autoriza deduplicación. [Semántica completa](COMPARISON.md).

## Entradas, materialización y fidelidad

Entradas directas: `pandas.DataFrame`, `polars.DataFrame` y `pyarrow.Table`
eager, con los tipos escalares admitidos por la captura vigente. Se copian las
capturas; la comparación conserva snapshots y notas de tipos y versiones de las
bibliotecas de captura. No se
importan motores al importar `equiframe`; cada ruta carga solo sus extras.

- pandas conserva NaN observado y máscaras NULL independientes cuando existen;
  una distinción perdida antes de llamar a la biblioteca no puede recuperarse
- Índice pandas trivial, sin nombre, `RangeIndex(0, n, 1)`: no añade significado
  al contrato. Índices significativos se capturan aparte y el default los
  rechaza. Para excluirlos se requiere
  `ComparisonPolicy(index="ignore", justification="...")`; para compararlos,
  el usuario puede promoverlos explícitamente a columnas antes de llamar
- Categorías/orden categórico, nombres de ejes de columnas, objetos heterogéneos
  y representaciones que pierden información se rechazan. Subclases nativas,
  subclases de escalares object y metadatos de dtype NumPy no declarados también
  se rechazan antes de convertir. Arrow con metadatos
  de esquema/campo no interpretados, incluido índice pandas embebido, también
  se rechaza en la entrada directa. No se declara igualdad de esos metadatos
- Polars `LazyFrame`, relaciones DuckDB y lectores consumibles no se ejecutan
  ni consumen implícitamente. Materialice deliberadamente usando su pipeline o
  [capture_duckdb](DUCKDB_CAPTURE.md) para un SELECT/WITH explícito con captura
  por lotes, o los adaptadores existentes; compare el snapshot con contrato
- `ArrowInput`, artefactos, `TableArtifact`, `ExecutionResult` y archivos locales
  Arrow IPC file/Parquet mantienen la ruta previa cuando se aporta contrato.
  Las garantías y límites de esos formatos no se amplían por envolverlos en
  `diff`. La inferencia sin contrato se limita a entradas eager y `ArrowInput`

El soporte de ejecución nativa DuckDB existente sigue disponible. Rechazar una
relación lazy en `diff` no significa que `DuckDBAdapter` deje de funcionar.
`physical_types="exact"` conserva la firma lógica del núcleo: por ejemplo,
las representaciones Arrow string/large_string/string_view pertenecen a la
misma familia string. No promete identidad del dtype nativo pandas/Polars ni
igualdad byte a byte de todo metadato; los tipos nativos quedan como evidencia.
La fachada no establece una transacción compartida ni snapshot simultáneo entre
fuentes. No modifique entradas concurrentemente durante su captura; después,
los snapshots locales fijan lo comparado.

## Coste, fallos y evidencia

`DiffCaptureOptions(max_rows=1_000_000, max_bytes=256*1024**2)` limita cada
entrada nativa eager: preflight sobre tamaño nativo y comprobación después de
la conversión, incluyendo índice. Es separado de `ComparisonOptions`, que
limita comparación, lotes, disco, matching y evidencia. Inspeccione/configure
ambos antes de ejecutar. No son una cuota dura de RSS ni un timeout capaz de
interrumpir una llamada nativa; copia y conversión pueden necesitar memoria
adicional. Para entradas grandes utilice snapshots de archivo y contrato.

Errores de configuración (`ValueError`/`pydantic.ValidationError` o
`InvalidExecutionInput`), inferencia
ambigua/no soportada (`CapabilityError`), dependencia ausente
(`MissingDependencyError`), límites de captura (`ResourceLimitError`) o
cancelación (`ExecutionCancelled`) antes de disponer de contrato pueden
lanzarse sin reporte. Una vez configurada la comparación, el núcleo conserva
sus diagnósticos `not_evaluable`, datos parciales y `counts.final=False`.
Crear o publicar evidencia puede lanzar `OSError`; no se promete un reporte
persistido para cualquier fallo. Un error nunca se convierte en equivalencia.

`ef.read_diff_contract(result)` encuentra el compañero `diff-contract.json` sin
que el consumidor tenga que reconstruir rutas. Valida formato, cobertura de
procedencia, identidad de comparación, contrato, política, referencia y hash
del spec. El compañero registra también las opciones de captura; no modifica
`comparison.json` ni sus esquemas anteriores. La procedencia es una declaración
del productor, no una firma ni prueba de autenticidad; el manifiesto anterior
no autentica sus etiquetas de origen. El lector no reejecuta datos/SQL ni
sustituye la verificación de toda la evidencia. `compare` por sí solo no genera
este compañero.
Su traslado a bundles anteriores no se incorpora en esta entrega: conserve
el directorio original si necesita consultar la procedencia suplementaria.

Snapshots, índices y diferencias pueden contener los datos aportados. Use una
carpeta autorizada y una política de acceso/retención adecuada. Esta entrega
no añade redacción, HTML, cifrado ni publicación remota.

## Reproducción

El ejemplo `packages/equiframe/examples/diff_local.py` comprueba diferencia
localizada por clave, procedencia, roundtrip y una comparación equivalente.
El verificador de distribución lo ejecuta fuera del checkout en los extras
Arrow/pandas/Polars y el perfil engines. Las suites prueban los constructores,
la captura, la paridad pública con el núcleo, claves globales, bolsa aproximada,
fallos, límites y cleanup. Consulte la ficha STEP2 para entorno y resultados
efectivamente ejecutados; no se promete todo el rango de versiones ni una
matriz remota por existir esos tests.
