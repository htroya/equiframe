# Perfiles y preprocesamiento (paso 5)

Implementación de ingeniería `equiframe 0.5.0`, fórmulas y formatos `1.0`.
Corresponde a §3.6, Tabla 13, del borrador `TFM_EquiFrame_ACTUAL.docx`.
Las columnas concretas siguen siendo una elección del piloto que debe fijarse
antes del ajuste. Los ejemplos son sintéticos, no perfiles del DW ni resultados
del benchmark. El documento de tesis no se modifica.

## Uso y separación de responsabilidades

```python
from pathlib import Path
import equiframe as ef

run = ef.ExecutionResult.model_validate_json(Path("run.json").read_bytes())
spec = ef.ProfileSpec.model_validate_json(Path("profile-spec.json").read_bytes())
profile = ef.profile_execution(run, spec=spec, work_dir=Path("equiframe-runs"))
print(profile.complete, profile.vector.observations)
```

Solo requiere el extra `arrow`. No reejecuta transformaciones, evalúa R, consulta
O ni utiliza otra salida de motor. Verifica hashes, tamaños, conteos y metadatos
físicos de las entradas/salida de la captura. Contrato inválido, referencia no
declarada o familia incompatible se rechazan antes de perfilar; fallos de ejecución,
integridad, capacidad y recursos producen observaciones `not_evaluable`.

`ProfileSpec` enumera un orden fijo de `ProfileFeature`. Cada feature selecciona
una fórmula cerrada y sus tablas/columnas, no expresiones arbitrarias ni valores
de metadatos. La huella incluye familia, versión, orden, fórmulas, columnas,
denominadores y políticas suplementarias. Los IDs y revisiones del contrato
quedan fuera de esa huella: cambiar únicamente procedencia no cambia la matriz.
Cambiar la definición o el orden invalida el preprocesador anterior.

`ProfileResult.metadata` conserva IDs de ejecución, huella de contrato/captura,
referencias a artefactos y recibos de conversión. `ProfileResult.vector` conserva
las definiciones y observaciones estadísticas. `FeatureMatrix.values` contiene
solo filas numéricas: no recibe IDs, motor, mutación, etiqueta ni partición.
Los nombres de columnas que definen una tasa no son valores de identificadores
inyectados en la matriz. No se mezclan automáticamente plantillas con distintos
nombres, columnas o significados, aunque pertenezcan a la misma familia.

## Fórmulas y denominadores

| Métrica | Cálculo | Familias |
|---|---|---|
| `log_filas` | `ln(1 + n_salida)`; cero para salida vacía | Todas |
| `razon_salida_entrada` | Filas de salida / filas de la entrada explícita | Uniones, duplicados/orden, agregaciones |
| `tasa_nulos` | Ausencias capturadas de una columna / filas de salida | Nulos/tipos, uniones, agregaciones |
| `tasa_nan` | NaN de una columna numérica / filas de salida | Nulos/tipos |
| `prop_duplicados` | `(filas_clave_completa - claves_completas_distintas) / filas_clave_completa` | Duplicados/orden, uniones |
| `cardinalidad_rel` | Valores distintos informados de una columna clave / valores informados | Uniones, duplicados/orden, agregaciones |
| `expansion_union` | Filas de salida / filas de entrada izquierda explícita | Uniones |
| `claves_sin_pareja` | Filas izquierdas sin pareja / filas izquierdas | Uniones |
| `conversiones_fallidas` | Intentos fallidos / valores presentes sometidos a conversión, según recibo | Nulos/tipos, fechas |
| `fechas_invalidas` | Valores temporales presentes no interpretables o inválidos según política / presentes examinados | Fechas |

Numeradores y denominadores se conservan como enteros, sin pérdida de precisión;
el valor estadístico de la tasa es float64. Los decimales originales nunca se
convierten a float para contar distintos o claves. Se conservan multiplicidades;
las uniones cuentan filas, no solamente claves distintas. NULL y NaN hacen una
clave incompleta. Los ámbitos de una clave compuesta deben incluirse en `columns`.
NULL no empareja, conforme a Contract 1.0/A45; NaN tampoco empareja. Tipos físicos
distintos entre las claves de ambos lados quedan no evaluables, sin cast implícito.

Las tasas de nulos cuentan la ausencia capturada y excluyen NaN, cadena vacía y
cero, tal como exige la Tabla 13, incluso si el comparador permite equivalencias
entre esas categorías. `FeatureSupport` conserva sus conteos separados. Una
columna no numérica produce `tasa_nan` no aplicable; un NaN de entrada no equivale
a ausencia. La cardinalidad excluye NULL y NaN, pero incluye cadena vacía y cero.
No se deduplica ni repara el contenido. `expansion_union` y la razón de filas se
rechazan como variables duplicadas si tienen exactamente los mismos operandos.

Para fechas se utiliza la política temporal explícita de `target`: días ISO o
timestamps estrictos, nanosegundos, zona, tratamiento de timestamps sin offset,
DST y límites abiertos/cerrados. No se inventa una ventana de cohorte; una fecha
fuera de 2025 puede ser válida si no contradice el rango de validez declarado.
Para estudiar validez general, `target` no debe imponer una ventana de selección.

## Conversiones instrumentadas

Un NULL de salida no demuestra conversión fallida (decisión A47). La API acepta
`conversions=(ConversionReceipt(...),)` con nombre de feature, columna fuente,
hashes de entrada y salida, política destino, versión del productor y posiciones
únicas de intentos/fallos. Los fallos deben ser un subconjunto de los intentos;
estos no pueden apuntar a NULL ni a posiciones inexistentes. Cadena vacía es
presente. Cero intentos produce una tasa no definida, no cero.

El recibo lo instrumenta la transformación confiable; el núcleo verifica su
vinculación y coherencia, pero no puede probar retrospectivamente que el productor
registró todos los intentos reales. No ejecuta callbacks de recibos. Sin recibo,
la medida queda `not_evaluable`, nunca se reemplaza por una prueba hipotética de
conversión. Esta API suplementaria no altera ExecutionResult ni Contract 1.0.

## Estados, ajuste e inferencia

| Estado de medida | Valor | Tratamiento |
|---|---|---|
| `available` | Finito, con conteos | Usar valor |
| `undefined` | `None`, denominador 0, motivo `empty_denominator` | Mediana de entrenamiento e indicador |
| `not_applicable` | `None`, motivo explícito | Mediana e indicador si la variable tenía soporte en ajuste; retirar si nunca aplica |
| `not_evaluable` | `None`, diagnóstico técnico | Rechazar ajuste/inferencia; no imputar un fallo |

```python
# La selección proviene del benchmark o del consumidor, antes de llamar al núcleo.
selection = ef.NormalTrainingProfiles(
    purpose="normal_training",
    selection_manifest_sha256=manifest_sha256,
    profiles=tuple(normal_training_vectors),
)
bundle = ef.fit_preprocessor(selection, spec=spec, empty_policy="drop")
ef.write_preprocessor(bundle, Path("preprocessor.json"))
restored = ef.read_preprocessor(Path("preprocessor.json"))
matrix = ef.transform_profiles(restored, tuple(inference_vectors))
```

La selección debe contener exclusivamente entrenamiento normal. El tipo rechaza
otros propósitos, etiquetas y columnas extra; no conoce O ni puede certificar la
normalidad o la ausencia de fuga de un manifiesto externo mediante un hash. Esas
comprobaciones científicas corresponden al paquete experimental del paso 6.

El ajuste calcula la mediana por variable con los valores válidos de esa familia
y especificación: en muestras pares, promedio de los dos centrales. Conserva
medianas, soporte, hash de la selección, hash de perfiles y política de retiro.
Inferencia no recalcula ninguna mediana. Por cada variable retenida se emiten,
en orden, `nombre`, `nombre.undefined`, `nombre.not_applicable`.
Las variables sin valores de entrenamiento se retiran con motivo para ambos
detectores (`drop`) o hacen el componente no estimable (`not_estimable`).
Si no queda ninguna variable, el preprocesador siempre es no estimable.

M y B deberán consumir este mismo `FeatureMatrix`, con su huella de preprocesador;
no existe una ruta de imputación distinta por detector. M/B se implementan en el
paso 7. `ready` aquí significa que se puede preparar una matriz; no prueba que
existan variación, grupos independientes o soporte suficiente para estimar M/B.
No se entrena ni calibra ningún detector en este paso.

## Evidencia, recursos y ejemplos

Cada llamada publica `profile_<uuid>/profile.json` en un directorio nuevo. Lectores
rechazan miembros JSON duplicados, versiones desconocidas, valores no finitos,
huellas inconsistentes y conteos que contradicen sus tasas. El bundle es JSON,
sin pickle ni código ejecutable, y su escritura rechaza sobrescritura.

El perfilado carga las tablas capturadas completas. `ProfileOptions` limita
filas totales, bytes de artefactos/decodificados, trabajo y claves distintas, además
de timeout/cancelación cooperativos. No es streaming, spill, cuota RSS ni timeout
duro; Arrow puede asignar memoria antes del control posterior. Límites excedidos
producen `not_evaluable`. Esta limitación debe incluirse al medir H3 en el paso 10.

```bash
python examples/profiles_from_run.py ruta/run.json examples/profiles/nulls_types.json
python examples/preprocess_profiles.py --training ruta/profile.json --selection-manifest seleccion.json --score ruta/prueba/profile.json --output preprocessor.json
```

Se distribuyen cinco especificaciones sintéticas en `examples/profiles/`.
`tools/verify_distribution.py` prueba todas con el extra Arrow desde wheel fuera
del checkout, restaura un preprocesador y prepara la matriz. `execute_native.py`
perfila además las ejecuciones Pandas, Polars y DuckDB de sus cinco familias:
cada perfil recibe exclusivamente su propia captura.
