# Reporte común de comparación

STEP3, candidato privado 0.11.1. `ComparisonResult` conserva su formato 1.0 y
su juicio. El nuevo `ComparisonReport` 1.0 es una vista separada: JSON, texto,
HTML independiente y notebook consumen exactamente sus datos ya filtrados.
No vuelve a comparar, no consulta los orígenes y no ejecuta callbacks o SQL.

## Uso mínimo

```python
import equiframe as ef

result = ef.diff(candidate, expected, keys=["id"])
report = ef.comparison_report(result)
print(report.to_text())
html = report.to_html()
report  # En un notebook, _repr_html_ muestra la misma vista
```

Esta ruta solo utiliza el resultado validado y sus ejemplos en memoria. No
abre archivos. El valor predeterminado oculta valores, nombres de columnas,
tipos físicos/nativos aportados por el productor, mensajes de excepción,
justificaciones libres y rutas. Conserva tipos escalares, políticas operativas,
estado, alcance, cobertura, motivos y siguiente acción. Las columnas tienen
alias `column_1`, etc. Las huellas identifican el contrato y el spec; no son
firma, prueba de autenticidad ni aprobación del esperado.

Las posiciones son índices **desde cero** en cada captura. Para una referencia
`peer` se muestran lados izquierdo/derecho; para `expected`, candidato/esperado.
Una infracción en la derecha nunca se presenta como posición del candidato.

## Detalle verificado y divulgación explícita

```python
from pathlib import Path

root = Path("comparison-evidence") / result.comparison_id
report = ef.comparison_report(
    result,
    evidence_root=root,
    options=ef.ReportOptions(
        mode="detail",
        include_values=True,
        include_metadata=True,
        redact_columns=("email",),
        max_examples=10,
        require_exhaustive=True,
    ),
)
```

El ejemplo presupone que `result` se creó con
`work_dir=Path("comparison-evidence")` y que `email` es una columna declarada.
`evidence_root` debe ser un directorio de evidencia autorizado explícitamente;
también puede ser un directorio contenedor. No se descubre leyendo una URI
arbitraria. Se comprueban el manifiesto propio, el JSONL, tamaño, SHA-256,
registros, prefijo de ejemplos, dimensiones y alineación registrada. No se
abren snapshots ni rutas de ejecución para construir una vista.

`include_values` permite los escalares de los testigos; `include_metadata`
permite nombres y tipos físicos/nativos. Son permisos separados.
`redact_columns` también protege claves, claves con ámbito y testigos de
infracciones. Las justificaciones y los mensajes libres no se copian al
reporte. El objeto filtrado no guarda el selector de redacción, valores
ocultos ni referencias a los artefactos brutos. No debe confundirse esta
omisión del reporte con borrar los datos originales.

Los valores visibles conservan etiquetas exactas: `Decimal("100.00")`, NULL,
NaN, cadenas entre comillas, enteros y floats textuales, fechas y timestamps
con entero de época, unidad y zona. No se convierten a float ni se pierden
nanosegundos. Un valor que exceda `max_value_chars` se omite entero con
`disclosure="omitted"`; nunca se muestra un número truncado como si fuera fiel.
El mismo límite omite campos de nombres, tipos o políticas demasiado extensos;
`metadata_withheld` también lo declara cuando afecta metadatos.

## Recuentos y cobertura

- `difference_records` cuenta registros de diagnóstico, no filas distintas
- `added_rows`, `removed_rows` y `modified_rows` solo se calculan con alineación
  por clave globalmente validada o por posición de una secuencia
- En bolsa/matching se muestran excesos de ocurrencias por lado, conservando
  multiplicidad. No se inventan celdas o filas modificadas
- Un recuento no calculado tiene `value=null` y `precision="unknown"`. Las
  observaciones parciales son cotas inferiores; nunca totales definitivos
- `precision="estimate"` tiene representación distinta en el contrato, pero
  este constructor no produce estimaciones
- Si los ejemplos en memoria contienen todos los registros y la evaluación es
  completa, pueden derivarse recuentos exactos sin IO. El manifiesto sigue
  indicando `result_only`: eso no verifica archivos persistidos
- `max_examples` limita exclusivamente la vista. La inspección autorizada
  recorre toda la evidencia dentro de su presupuesto y puede calcular totales
  exactos aunque solo se muestre un ejemplo

Una interrupción conserva `not_evaluable`, cobertura parcial y diferencias
observadas. Un esperado inválido conserva `not_evaluable` aunque el recorrido
sea completo. Ningún límite ni redacción convierte uno de esos estados en éxito.
El reporte mantiene separado el juicio sobre los datos de la aceptación de la
evidencia solicitada.

## Tres modos y retención

| Modo | Qué conserva la nueva salida | Condición visible |
|---|---|---|
| `diagnostic` | Vista mínima con los ejemplos disponibles y políticas filtradas | Puede construirse sin IO; no acredita integridad de originales |
| `detail` | Vista controlada con inspección de diferencias y recuentos derivados | Sin inspección completa, aceptación de evidencia `not_satisfied` |
| `reproduction` | Vista más exportación explícita de capturas y contexto admitidos | Requiere valores/metadatos autorizados, sin redacción de columnas, y exportación exitosa |

Esta entrega **no modifica la retención del comparador**: los snapshots y
`differences.jsonl` originales permanecen intactos, sujetos a sus presupuestos
previos. El reporte minimizado tiene contrato/esquema propio; no reemplaza el
formato de comparación. No añade eliminación automática ni almacenamiento
bruto obligatorio a los reportes diagnósticos o de detalle.

`require_exhaustive=True` exige que la evaluación haya concluido y que toda
la evidencia original de diferencias pueda verificarse. Es independiente del
número de ejemplos divulgados. Si no se cumple, `evidence.acceptance` es
`not_satisfied` y `unmet_requirements` explica el motivo, aunque el juicio de
los datos ya estuviera decidido. La evidencia exhaustiva así verificada sigue
en el directorio original, no queda incorporada por implicación al reporte.

`max_evidence_bytes` limita lectura/verificación y exportación; `max_records`
limita registros y estructuras de alineación; existen límites de línea y
manifiesto. Son límites cooperativos, no una cuota dura de memoria del proceso.
Un presupuesto agotado al inspeccionar conserva el resultado con requisito
insatisfecho. Corrupción, rutas inválidas, datos ausentes y configuraciones
inválidas producen excepciones explícitas. No se convierten en una vista
verificada. `max_report_bytes` limita cada salida JSON/texto/HTML y puede lanzar
`ResourceLimitError`; se debe ampliar explícitamente o reducir la divulgación.

## Guardar y leer una vista

```python
report = ef.write_comparison_report(result, Path("private-report"))
restored = ef.read_comparison_report(Path("private-report/report.json"))
assert restored == report
```

El destino debe ser nuevo. Se escriben `report.json`, `report.txt`,
`report.html` y al final `evidence-manifest.json`, con inventario, tamaños y
SHA-256. Un fallo de escritura se lanza al llamante; pueden quedar archivos
parciales sin recibo de publicación completa. No interprete su existencia
como éxito. No se reemplazan reportes previos.

El lector de la vista rechaza JSON duplicado/no estándar, impone un límite de
bytes y revalida el modelo. No sigue rutas ni verifica el inventario de una
exportación; el manifiesto y hashes permiten esa comprobación independiente.
La vista puede renderizarse sin Arrow, pandas, Polars ni dependencias notebook.

## Reproducción acotada

```python
replay_report = ef.write_comparison_report(
    result,
    Path("private-replay"),
    evidence_root=root,
    options=ef.ReportOptions(
        mode="reproduction", include_values=True, include_metadata=True,
        require_exhaustive=True,
    ),
)
```

La subcarpeta `reproduction` contiene únicamente capturas copiadas y verificadas,
índices conservados cuando proceden, `context.json` y un inventario cerrado.
El contexto incluye spec, opciones, papel de referencia, versiones y metadatos
mínimos necesarios de tablas; añade la declaración de `diff` si existe y pasa
las comprobaciones de vínculo. Sus referencias son nombres relativos, sin
rutas de los orígenes. Se comprueban tamaño y hash de cada captura al copiar.

El alcance es volver a comparar **salidas materializadas** en un entorno
compatible, no reproducir la transformación original, SQL, credenciales o
servicios. Guardar todas las diferencias por sí solo no lo permite. Las
comparaciones incompletas y las fuentes `ExecutionResult`, cuyo contexto de
entradas puede estar fuera del directorio, no admiten esta exportación y fallan
explícitamente. Un esperado inválido completo puede conservarse para repetir
su diagnóstico; eso no lo convierte en aceptable.

El reporte independiente inicialmente indica `requires_verified_export`.
Solo una publicación exitosa cambia a `exported_materialized_inputs`; todos
los medios guardados registran el mismo estado de evidencia. No se añaden
comandos que reejecuten automáticamente el expediente.

## Privacidad y HTML

El reporte y sus capturas pueden ser sensibles aun con redacción. La retención
es hasta que el consumidor los borre. No hay envío de red, cifrado, control de
usuarios, anonimización estadística ni garantía contra reidentificación por
recuentos. El destino local y su acceso son responsabilidad del consumidor.
Se solicitan permisos POSIX 0700 para el nuevo directorio y 0600 para archivos;
Windows necesita sus ACL habituales. No son una política de acceso remoto.

HTML escapa los datos, no crea enlaces a rutas/URLs del productor, no incluye
scripts ni recursos remotos y conserva la defensa CSP del reporte de pipeline.
La vista notebook es un fragmento escapado sin ejecución; la política CSP del
notebook anfitrión pertenece a su aplicación. El texto hace visibles controles
ANSI/bidireccionales y saltos incluidos en valores para evitar inyección visual.
El reporte de pipeline existente permanece independiente y compatible.

Los esquemas `comparison-report`, `report-options`, `report-evidence-manifest`
y `report-publication-manifest` 1.0 se generan con el control de assets.
`examples/report_local.py` ejecuta datos sintéticos; `--render-only` prueba el
consumidor base instalado sin dependencias tabulares/notebook. Los recibos del
candidato identifican la revisión y los controles realmente ejecutados.
