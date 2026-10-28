# First use by role / Primer uso por perfil

[Install an identified artifact](installed-private.md) · [Arquitecto](arquitecto.md) ·
[Científico](cientifico.md) · [API](api.md)

For **0.12.2**, use the identified wheel and its reviewed
dependencies. Run these commands with the Python of that environment, outside
the source checkout. On Windows, replace `python` with `.venv\Scripts\python.exe`;
on Linux use `.venv/bin/python`. Activation is optional.

## Español: instalar, comprobar, ejecutar e interpretar

1. Sigue [la instalación offline](installed-private.md), comprueba el SHA-256
   recibido por un canal de confianza y ejecuta `python -m pip check`.
   Para arquitecto instala `[duckdb]`; para científico basta `[arrow]`.
   No necesitas ML, benchmark, OCI, una cuenta nueva ni un servicio adicional.
2. Comprueba el intérprete antes de preparar datos:

   ```text
   python -I -m equiframe doctor --extra duckdb
   python -I -m equiframe doctor --extra arrow --json
   ```

   `Metadata ready: True` comprueba identidad de versión y disponibilidad local;
   no prueba rangos, DLL, ejecución nativa ni corrección de datos. El JSON conserva
   esa distinción. Una dependencia ausente o metadatos de otra versión devuelven
   **3** y una acción de recuperación. El comando no instala ni usa la red.
3. Elige **uno** de estos ejercicios, con una carpeta de salida nueva:

   ```text
   python -I -m equiframe demo --role architect --output sql-good
   python -I -m equiframe demo --role scientist --output prep-good
   ```

   Arquitecto: consulta DuckDB local con valores enlazados y esperado literal.
   Científico: IDs con ceros iniciales, Decimal exacto en segundos, NULL y
   timestamps UTC. Las tablas son sintéticas, pequeñas y autocontenidas.
4. Comprueba que también detecta problemas:

   ```text
   python -I -O -m equiframe demo --role scientist --case different --output prep-different
   python -I -O -m equiframe demo --role architect --case not-evaluable --output sql-limit
   ```

   `equivalent` acepta y devuelve **0**; `different` rechaza y devuelve **1**;
   `not_evaluable` rechaza y devuelve **3**. Los errores de argumentos devuelven
   **2**; fallo de escritura, dependencia o carpeta ya existente devuelve **3**.
   Conserva `$LASTEXITCODE` en PowerShell o `$?` en Linux. No conviertas un rechazo
   esperado del ejercicio en aceptación de datos de tu pipeline.
5. Abre el archivo HTML indicado por la salida. `report/report.html` minimiza
   datos; `synthetic-detail/report.html` muestra la clave, columna y valores del
   ejercicio sintético. Se guardan antes del gate. Ambas vistas representan el
   mismo resultado. Las capturas completas permanecen en `private/`: ocultar
   valores en una vista no borra el original. Repetir la misma salida se rechaza;
   elige otra carpeta y conserva la anterior si necesitas comparar intentos.

Para sustituir los datos sintéticos por tu pipeline, sigue la guía larga de tu
perfil y usa `diff` → `write_comparison_report` → `assert_equivalent`. No existe
una traducción automática de SQL/Python arbitrario ni un servicio desplegado.
`--help` describe los parámetros reales. Ambos comandos nuevos son experimentales.

## English: a short installed route

Install the identified wheel with `[duckdb]` for the architect or `[arrow]`
for the scientist. Run `python -m pip check`, then `doctor --extra duckdb` or
`doctor --extra arrow`. A metadata-ready diagnosis is not native validation.

Run `demo --role architect --output sql-good` or
`demo --role scientist --output prep-good` through `python -I -m equiframe`.
Use `--case different` or `--case not-evaluable` and a **new** output directory to
inspect rejection. Exit meanings are 0 accepted, 1 different, 2 invalid CLI usage,
3 unavailable/failure. `-O` does not disable the gate. Reports are persisted before
the verdict and never replace an existing destination. Full synthetic detail is
separate from the default redacted report; raw evidence remains private.

Use the role guide for integration with your own Python/SQL and local pytest.
No automated runtime measurement is presented as a five-minute human observation.
The independent human-adoption protocol remains [pending](adoption.md).
