# Recorrido del arquitecto de datos

[Inicio](inicio.md) · [Instalación](installed-private.md) · [Científico](cientifico.md) · [API](api.md)

## Qué resuelve y qué instalar

Compara la salida de tu código Python o una consulta SQL con un esperado revisado,
guarda el diagnóstico y detén la tarea si difiere o no puede evaluarse. El
orquestador actual conserva transporte, secretos, reintentos y cuotas. No hace
falta desplegar otro servicio, usar el benchmark o conocer todos los modelos.

Instala un wheel identificado con `[duckdb]` para este ejemplo; usa
`[engines]` para las seis direcciones. Los consumidores anteriores conservan
su pin de candidato y sus propios recibos. Sigue la receta
normal de pip y el ensayo separado con lock completo de [installed-private](installed-private.md).
El candidato vigente declara Python 3.10–3.13. Usa el recibo real de tu minor y
plataforma; el objetivo ARM64 no se acredita con un ensayo Linux x86_64.
No uses el antiguo wheel 0.11.1 de la receta histórica ni un homónimo público.

Para empezar sin copiar el script, sigue [primer uso por perfil](first-use.md):
`python -I -m equiframe doctor --extra duckdb` y
`python -I -m equiframe demo --role architect --output sql-good`.
La guía completa siguiente sirve para integrar tu propio código y pytest.

## Python y SQL: evidencia antes de rechazar

Guarda lo siguiente como `integracion.py` fuera del checkout. Los datos son
sintéticos: la consulta buena tiene A=10, B=20; la variante cambia B a 21.
El esperado es literal y no lo calcula DuckDB. La suma por sí sola no es el gate.

```python
import argparse
from pathlib import Path

import equiframe as ef
import pyarrow as pa

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--case", choices=("good", "different"), default="good")
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
expected = pa.table({"id": ["A", "B"], "quantity": [10, 20]})
# SQL del propio consumidor, fijo y confiable; valores enlazados, no interpolados.
snapshot = ef.capture_duckdb(
    "SELECT 'A' AS id, 10::BIGINT AS quantity UNION ALL SELECT 'B', $quantity::BIGINT",
    parameters={"quantity": 20 if args.case == "good" else 21},
    work_dir=args.output / "capture",
)
declaration = ef.infer_diff_contract(expected.schema, keys=["id"])
result = ef.diff(
    snapshot,
    ef.ArrowInput(expected),
    contract=declaration,
    work_dir=args.output / "private",
)
report = ef.write_comparison_report(result, args.output / "report")
print(report.to_text())
# Solo este fixture sintético autoriza mostrar nombres, clave y valores.
detail = ef.write_comparison_report(
    result,
    args.output / "synthetic-detail",
    options=ef.ReportOptions(include_values=True, include_metadata=True),
)
print(detail.to_text())
# No capturar esta excepción para continuar una publicación o hacer verde el CI.
ef.assert_equivalent(result, report_path=args.output / "report" / "report.html")
```

Ejecuta `python -I integracion.py --output sql-good` y luego
`python -I -O integracion.py --case different --output sql-different`.
La primera termina con 0; la segunda con una excepción `EquivalenceDifferentError`
y salida no cero, después de guardar ambos reportes. Conserva el retorno real.
La conexión propia ya está cerrada cuando se compara su snapshot desacoplado.
Un reporte no tiene `assert_equivalent()` ni `summary()`; usa las funciones de la
[API](api.md). `ComparisonReport.to_text()`, `.to_html()` y `._repr_html_()` sí
existen; el objeto ComparisonResult se acepta con `ef.assert_equivalent`.

Para CI local, conserva el script junto con este test `test_integracion.py`:

```python
from pathlib import Path
import subprocess
import sys


def test_sql_regression(tmp_path):
    script = Path(__file__).with_name("integracion.py")
    subprocess.run(
        [sys.executable, "-I", str(script), "--output", str(tmp_path / "sql")],
        check=True,
    )
```

`python -m pytest -q test_integracion.py` comprueba la ruta de integración actual.
Para un proyecto real sustituye la consulta/esperado por versiones autorizadas;
una regresión real debe hacer fallar el test. Este comando es una prueba local,
no un job remoto de GitHub Actions. No modifiques el esperado para aprobar el fallo.

## Fijar datos externos y migrar

- Ya tienes DataFrames eager/Arrow: `diff`; inspecciona el contrato inferido y
  declara unidades, nulabilidad, claves y tolerancias justificadas del dominio
- Ya tienes artefactos: `compare` con contrato y `reference="expected"`
- Necesitas SQL confiable: `capture_duckdb`; no acepta cualquier statement ni
  acredita consistencia entre sistemas diferentes
- Necesitas un snapshot externo fijo: [G](journeys.md#g-external-snapshot-integration)
  usa `SnapshotDataSource` y cliente inyectado; [SQLite](sqlite-snapshots.md)
  añade un productor DB-API transaccional. El transporte/permiso/retención sigue
  en el consumidor. El mock no acredita el servicio de José
- Necesitas comparar migración: `check_migration` antes de `migrate`; consulta
  [IR](migration-ir.md) por motor. Los seis pares ordenados se conservan en el
  consumidor existente. No traduce Python/SQL arbitrarios ni convierte una
  única salida para aparentar dos ejecuciones nativas
- Necesitas cargar localmente: [C](journeys.md#c-retail-csvjson-etl-and-local-parquet)
  muestra esquema, quarantine y checkpoints. En producción, una exclusión
  necesita autorización de dominio; el ejemplo no la concede

El consumidor independiente 0.1.9, distribuido aparte con sus datos permitidos,
provee los programas `reconciliation`, `refactor`, `migration`, `preparation`.
Su README contiene instalación y CLI exactos. `run --all` verifica 72 casos:
24 aceptaciones y 48 rechazos esperados si todo coincide. El cero del arnés
no acepta los casos defectuosos. Los recibos distinguen cada artefacto y repetición.

## Repetición, publicación y recuperación

Una repetición usa nueva carpeta de evidencia; nunca sobreescribe la entrada.
El destino Parquet local de un solo escritor publica una versión y puntero
atómico. Misma petición admitida puede ser idempotente; no es una transacción
remota, concurrencia del DW ni garantía de durabilidad frente a corte eléctrico.

Antes del commit, un fallo de validación/escritura conserva la versión anterior.
Después de cambiar el puntero, un fallo de escritura del recibo puede dejar los
datos publicados y la aplicación incompleta: consulta el puntero/recibos,
conserva el fallo y reconcilia el estado antes de reintentar. No declares rollback
ni éxito por no haber llegado un recibo. El consumidor 0.1.10 documenta y conserva
`committed_application_incomplete` cuando puede escribir ese diagnóstico.

El diagnóstico minimizado no borra los datos de `private/`, capturas ni bundles.
Comparte únicamente vistas revisadas y autorizadas. Para incidencias, aporta
versión/hashes/lock, entorno, caso sintético, contrato, esperado y observado;
[maintenance](maintenance.md) distingue las incidencias públicas de los reportes
privados de seguridad y confirma al mantenedor responsable. No se promete SLA.
