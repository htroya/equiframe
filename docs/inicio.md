# Empieza con EquiFrame

Para cargar archivos con pocas opciones y elegir Pandas, Polars o DuckDB,
consulta [lectura y conversión](lectura-conversion.md). La
[revisión opcional con el lenguaje R](r_review.md) permite una segunda
comparación después de reglas e Isolation Forest, conservando sus decisiones.

[Arquitecto](arquitecto.md) · [Científico](cientifico.md) · [Manual](index.md) · [Elegir API](choosing-api.md) · [Ocho recorridos](journeys.md) ·
[Semántica de referencia](semantics.md) · [Compatibilidad](compatibility.md)

EquiFrame compara resultados tabulares completos y deja evidencia para explicar
las diferencias. Puedes usarlo desde tu Python, notebook, pytest u orquestador
actual. No necesitas adoptar el benchmark ni desplegar un servicio.

Para intercambiar CSV, SQL y otras entradas conservando un contrato, usa el
[recorrido de universalidad en cinco pasos](universalidad-cinco-pasos.md).

El alcance estable objetivo es **0.12.3**. Identifica los bytes de cada artefacto
por su revisión y SHA-256. El código propio usa MIT y el propietario autorizó
preparar y publicar manualmente en TestPyPI/PyPI sujeto a los
[gates de release](releasing.md); autorización no significa publicación terminada.
La adopción humana y la aceptación científica/DW real siguen separadas y pendientes.

## 1. Instala una copia identificada

Si prefieres ejecutar un ejemplo sin copiar código, usa
[primer uso por perfil](first-use.md): comprueba el entorno con `doctor` y ejecuta
`demo` para arquitectura SQL o preparación científica. Las guías largas siguen
disponibles para integrar tus propias tablas, contratos y tests.

Necesitas Python 3.10–3.13 y un artefacto identificado con dependencias revisadas.
Los [comandos de instalación](quickstart.md#1-install-the-artifact-you-were-given)
crean un entorno fuera del checkout y verifican que el import apunta a esa
instalación. El [kit reproducible](recipes.md) fija dependencias para
el minor seleccionado; no demuestra automáticamente compatibilidad con otro entorno.

Para este primer ejemplo basta el extra `arrow`. Para DataFrames pandas usa
`pandas`; para las ocho rutas usa `engines`. No hace falta `ml` para determinar
si una preparación de datos conservó sus filas y valores. `import equiframe`
no carga motores opcionales. La matriz [de compatibilidad](compatibility.md)
separa versiones admitidas de combinaciones realmente ejecutadas.

## 2. Detecta una regresión sin aprender la arquitectura

Después de la instalación, guarda este script en una carpeta privada. Todos sus
datos son sintéticos. Puede repetirse: cada ejecución crea un directorio nuevo.

```python
from pathlib import Path
from uuid import uuid4

import equiframe as ef
import pyarrow as pa

root = Path.cwd() / ("revision-" + uuid4().hex)
expected = pa.table({"id": ["A", "B"], "quantity": [10, 20]})
candidate = pa.table({"id": ["B", "A"], "quantity": [21, 10]})
result = ef.diff(candidate, expected, keys=["id"], work_dir=root / "evidence")
report = ef.write_comparison_report(result, root / "report")
print(result.state, result.complete)  # different True
print(report.to_text())
print("Evidencia privada:", root)

try:
    ef.assert_equivalent(result)
except ef.EquivalenceDifferentError:
    print("Regresión rechazada: B tiene 21 en vez de 20")
else:
    raise AssertionError("La discrepancia sintética no debe aprobarse")

corrected = ef.diff(expected, expected, keys=["id"], work_dir=root / "evidence")
ef.assert_equivalent(corrected)
print(corrected.state, corrected.complete)  # equivalent True
```

El ejemplo captura la excepción deliberada para mostrar ambas rutas. En un test
real deja que `ef.assert_equivalent(result)` falle: no captures el fallo para
continuar publicando datos. El reporte minimiza valores/nombres/rutas por defecto;
la evidencia original sigue conteniendo datos y necesita tu política de acceso.
La minimización del reporte no borra ni anonimiza las capturas originales.

## 3. Usa cinco operaciones habituales

1. `diff(candidate, expected)`: compara DataFrames eager/Arrow ya calculados
2. `read_diff_contract(result)`: inspecciona la política inferida o declarada
3. `comparison_report(result)`: explica el resultado sin escribir archivos
4. `write_comparison_report(result, directory)`: conserva un reporte nuevo
5. `assert_equivalent(result)`: rechaza diferencias y falta de evaluación

El esquema de referencia está a la derecha. Las claves declaradas se comprueban;
no se deduplican filas para hacerlas coincidir. Dinero usa Decimal exacto y unidad
explícita cuando el dominio la necesita. Un contrato inferido no inventa moneda,
reglas de negocio ni independencia del esperado. Consulta
[la elección de API](choosing-api.md) antes de ampliar el flujo.

## 4. Interpreta el resultado antes de actuar

- `equivalent`: la comparación completa satisface el contrato evaluado; aún debe
  satisfacer la garantía/evidencia que exige tu consumidor
- `different`: se encontraron diferencias o incumplimientos
- `not_evaluable`: no pudo establecerse el juicio requerido; también rechaza la
  aceptación, incluso si una inspección terminó con `complete=True`

`bool(result)` y `assert result` se rechazan. Una ejecución `completed`, dos
motores de acuerdo, un HTML generado o un lector de integridad con salida cero
no prueban corrección de negocio. Comparar con un esperado revisado es una
comprobación adicional; los hashes acreditan bytes contra una referencia, no
la identidad del autor ni la validez humana de ese esperado.

## 5. Continúa según tu problema

- Desarrollador: [A, regresión pandas](journeys.md), claves/duplicados y pytest
- Ingeniero: [B/C/H](journeys.md), migración nativa, ETL local y revisión portable
- Arquitecto: [G](journeys.md), [puertos](extending.md) y
  [snapshot SQLite](sqlite-snapshots.md), sin dependencia del servicio real
- Científico de datos: [D/E/F](journeys.md), exactitud monetaria, telemetría y
  preservación de variables; equivalencia y anomalías son preguntas distintas

Los ocho recorridos incluyen caso correcto, discrepancia y fallo/no evaluación,
con datos sintéticos, esperados literales, dependencias identificadas y aceptación
automatizada. Publicar Parquet en una carpeta local no publica el paquete ni
despliega servicios. Las [capacidades](compatibility.md) separan captura,
comparación, ejecución y migración: no extrapoles una etapa a otra.

La referencia técnica única de firmas/políticas es [API](api.md) y
[semántica](semantics.md). Este inicio es una ruta de lectura; no crea otra API ni
redefine formatos históricos. El objetivo de diagnóstico en cinco minutos y la
[adopción real](adoption.md) necesitan participantes con consentimiento y evidencia:
las ejecuciones automáticas no cuentan como pilotos humanos.
