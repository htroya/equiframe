# Recorrido del científico de datos

[Inicio](inicio.md) · [Instalación](installed-private.md) · [Arquitecto](arquitecto.md) · [Semántica](semantics.md)

## Qué comprobar antes de usar un dataset preparado

Una optimización no debe cambiar IDs, cobertura, ausencias, precisión o fechas
sin un requisito explícito. Compara la preparación candidata con valores
esperados independientes; guarda diferencias y rechaza los casos no evaluables.
Equivalencia no demuestra ausencia de sesgo, calidad del modelo o validez científica.

Este script necesita un wheel identificado con el extra `[arrow]`.
La [instalación vigente](installed-private.md) usa resolución normal y `pip check`;
no requiere pandas, ML, benchmark ni otro orquestador. Las rutas A–H y el
consumidores identificados por sus propios pins y recibos amplían el ejercicio
a motores nativos y datos permitidos.

Puedes empezar sin copiar código: [primer uso por perfil](first-use.md) explica
`python -I -m equiframe doctor --extra arrow` y
`python -I -m equiframe demo --role scientist --output prep-good`.
El script siguiente permite integrar y modificar una preparación propia.

## Preparación pequeña, precisa e inspeccionable

Guarda como `preparacion.py` fuera del checkout. El origen sintético conserva
IDs textuales, milisegundos decimales y fechas UTC; la transformación expresa
segundos exactos. El esperado usa literales Decimal e instantes enteros,
independientes del cálculo y parser de la preparación.

```python
import argparse
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import equiframe as ef
import pyarrow as pa

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument(
    "--case",
    default="good",
    choices=(
        "good",
        "different",
        "dropped_row",
        "changed_id",
        "time_shift",
        "missing_changed",
        "invalid_expected",
        "not_evaluable",
    ),
)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
source = [
    ("0001", "1250", "1970-01-01T00:00:00+00:00"),
    ("0002", None, "1970-01-01T00:00:01+00:00"),
    ("0003", "1000000001", None),
]
prepared = [
    {
        "sample_id": identifier,
        "duration_s": Decimal(ms) / Decimal("1000") if ms is not None else None,
        "observed_at": datetime.fromisoformat(at) if at is not None else None,
    }
    for identifier, ms, at in source
]
if args.case == "different":
    prepared[0]["duration_s"] = Decimal("1.251")
elif args.case == "dropped_row":
    prepared = prepared[:2]
elif args.case == "changed_id":
    prepared[0]["sample_id"] = "1"
elif args.case == "time_shift":
    prepared[0]["observed_at"] += timedelta(hours=1)
elif args.case == "missing_changed":
    prepared[1]["duration_s"] = Decimal("0.000")
expected = pa.table(
    {
        "sample_id": ["0001", "0002", "0003"],
        "duration_s": pa.array(
            [Decimal("1.250"), None, Decimal("1000000.001")], type=pa.decimal128(16, 3)
        ),
        "observed_at": pa.array([0, 1000000, None], type=pa.timestamp("us", tz="UTC")),
    }
)
if args.case == "invalid_expected":
    expected = expected.take([0, 1, 0])  # Clave duplicada: referencia inválida.
candidate = pa.Table.from_pylist(prepared, schema=expected.schema)
duration = ef.ColumnSpec(
    name="duration_s",
    logical_type=ef.DecimalType(precision=16, scale=3),
    nullable=True,
    null_policy=ef.NullPolicy(representations=("null",)),
    numeric_policy=ef.NumericPolicy(comparison="exact", unit="seconds"),
)
declaration = ef.infer_diff_contract(
    expected.schema,
    keys=["sample_id"],
    column_overrides=(duration,),
)
result = ef.diff(
    candidate,
    expected,
    contract=declaration,
    work_dir=args.output / "private",
    options=ef.ComparisonOptions(max_rows=1 if args.case == "not_evaluable" else 100),
)
report = ef.write_comparison_report(result, args.output / "report")
# Solo los datos sintéticos de este ejercicio autorizan esta segunda vista.
detail = ef.write_comparison_report(
    result,
    args.output / "synthetic-detail",
    options=ef.ReportOptions(include_values=True, include_metadata=True),
)
print(detail.to_text())
print(
    "Estado:", result.state, "completo:", result.complete, "conteos finales:", result.counts.final
)
print("Contrato declarado/inferido:", declaration.model_dump_json())
ef.assert_equivalent(result, report_path=args.output / "report" / "report.html")
```

Ejecuta `python -I preparacion.py --output prep-good`. Debe aceptar.
Repite con `--case time_shift --output prep-time`: debe rechazar después de
conservar el diagnóstico. Cada variante usa una carpeta nueva. También funciona
con `python -I -O`; el gate no es un `assert` de Python.

| Caso | Qué debe observarse | Consecuencia para el dataset |
|---|---|---|
| good | equivalent, completo, conteos finales, salida 0 | Conserva el contrato evaluado |
| different | different; 1.251 frente a 1.250 | Cambio de precisión/valor |
| dropped_row | different; falta 0003 | Pérdida de cobertura, incluso si era un valor grande |
| changed_id | different; 1 no es 0001 | Ruptura de identidad y posibles joins posteriores |
| time_shift | different; desplazamiento de una hora | Cambia ventana temporal y posibles features |
| missing_changed | different; NULL no es cero | Cambia significado de ausencia |
| invalid_expected | not_evaluable; clave duplicada | Reparar/revisar la referencia antes de aceptar |
| not_evaluable | not_evaluable; presupuesto de una fila | No hay evaluación completa; no usar recuentos parciales como totales |

Las siete variantes negativas terminan con excepción y retorno no cero. No se
capturan para aprobar datos. Orden de filas ignorado por clave verificada; si tu
tarea depende del orden usa `sequence_contract` con sus restricciones explícitas.
La inferencia no sabe qué IDs/unidades/ausencias son válidos en tu dominio:
inspecciona `.provenance` y sustituye los defaults con ColumnSpec/contrato revisados.
No relajes precisión, rellenes NULL o elimines duplicados tras ver el fallo.

## Consola, HTML y notebook

`report/` es la vista minimizada por defecto. `synthetic-detail/report.html` y
el texto mostrado contienen la misma decisión, clave/columna y valores del
fixture. En un notebook puedes ejecutar el mismo script con argumentos o
conservar `result` y mostrar `detail` como última expresión: `_repr_html_()`
renderiza el mismo modelo. No hace falta leer manualmente toda la evidencia JSON.

`difference_records` cuenta registros de diferencia, no siempre filas distintas.
Los ejemplos mostrados son acotados; las diferencias completas y capturas siguen
en evidencia privada. Si un conteo es parcial/desconocido no es cero definitivo.
Una vista minimizada no anonimiza ni elimina los originales. No actives la vista
detallada con datos reales sin permiso para la audiencia prevista.

## Continuar con evidencia existente

- [F](journeys.md#f-data-science-preparation-without-anomaly-claims): preparación
  pandas, pérdida de fila/cambio de ID y clipping indebido
- [E](journeys.md#e-telemetry-zones-missingness-duplicates-and-order): NULL distinto
  de NaN, multiplicidad, orden e instantes de nanosegundos. Captura/comparación
  no equivale a admisión de todo plan temporal por todos los motores
- Consumidor independiente 0.1.9: `run --program preparation --variant good
  --source pandas --target duckdb --data RUTA_DATOS --output CARPETA_NUEVA`;
  su variante `defect` desplaza una hora. Usa su README para instalarlo. Incluye
  datos USGS permitidos, esperado stdlib y seis direcciones, sin modelo entrenado

Perfiles/detectores, si los necesitas, requieren su propia definición de features,
normalidad/particiones, ajuste/calibración y soporte. Falta de soporte es
`not_estimable`/`not_evaluable`, nunca ausencia de alerta. R, M, B, H y O siguen
independientes y las salidas/etiquetas de otros motores no alimentan el detector.
Estos ejemplos no acreditan utilidad científica ni adopción humana; el
[protocolo](adoption.md) exige participantes reales y consentimiento.
