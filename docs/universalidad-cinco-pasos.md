# EquiFrame más universal en cinco pasos

[Inicio](inicio.md) · [Fuentes](universal-sources.md) · [Extensiones](extending.md)

EquiFrame 0.12.2 permite cambiar la entrada conservando un
contrato y un plan nativo común. El siguiente recorrido utiliza datos sintéticos
y un esperado literal independiente. No necesita benchmark, servicios remotos,
credenciales, GitHub Actions ni recursos de pago.

1. **Entradas y contrato común.** CSV, JSON/JSONL, Parquet y Arrow reutilizan los
   adaptadores existentes. `SQLiteInput` añade consultas locales parametrizadas
   de solo lectura. `StreamInput` recibe respuestas binarias de un cliente
   proporcionado por el consumidor. Las columnas, tipos, claves, ausencias,
   monedas, fechas y duplicados siguen siendo decisiones explícitas del contrato.
2. **Operaciones nativas.** Se reutilizan filtros, proyecciones, conversiones
   exactas admitidas, agregaciones, ordenamientos y seis tipos de join. El nuevo
   `Window` añade numeración y valores anteriores/siguientes por partición o
   sobre toda la entrada: `row_number`, `lag` y `lead`, con offset declarado.
   Pandas, Polars y DuckDB ejecutan cada uno su implementación nativa.
3. **Significado de los datos.** Las ventanas conservan tipos y unidades, valores
   extremos, precisión Decimal, NULL/NaN y zonas horarias admitidas. Los empates
   se rechazan para impedir elecciones arbitrarias. Un tipo incompatible o una
   capacidad no admitida se explica antes de ejecutar; un fallo nunca aprueba.
4. **Extensiones y límites.** `CompositeDataSource` vincula proveedores externos
   a nombres lógicos. `RecordBatchInput` verifica esquemas Arrow explícitos y
   límites acumulados. SQLite comprueba cancelación y tiempo durante consultas
   largas. Un nuevo proveedor implementa `table_names` y `resolve`; un nuevo
   input local implementa `load(context)`. No necesita modificar el núcleo.
5. **Primer uso completo.** El ejemplo instalado compara seis entradas bajo el
   mismo contrato y plan en los tres motores: 18 ejecuciones por caso. Guarda
   capturas, comprobaciones, reportes y un recibo; distingue coincidencia,
   discrepancia e integridad fallida.

## Instala y ejecuta el ejemplo

Usa un wheel identificado por revisión y SHA-256. El código propio tiene
licencia MIT; los componentes de terceros conservan sus términos. La publicación
pública sigue pendiente. Desde una carpeta nueva fuera del checkout:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install 'C:\ruta\equiframe-0.12.2-py3-none-any.whl[engines]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m equiframe.examples.integrations.universal_first_use --output caso-correcto
.\.venv\Scripts\python.exe -m equiframe.examples.integrations.universal_first_use --case different --output caso-distinto
.\.venv\Scripts\python.exe -m equiframe.examples.integrations.universal_first_use --case corrupt --output caso-danado
```

En Linux/macOS sustituye el intérprete por `python3.12` y el ejecutable del
entorno por `.venv/bin/python`. Son instrucciones de uso; cada entorno requiere
su propia ejecución registrada. No presupongas validación nativa de macOS.

Los directorios de salida deben ser nuevos. El caso correcto termina con código
0 y 18 comparaciones equivalentes. `different` altera únicamente SQLite de
12.30 a 12.31: produce discrepancias en los tres motores y termina con código 1.
`corrupt` declara un digest incorrecto para la respuesta de API: rechaza esa
entrada en los tres motores, no compara sus resultados y termina con código 3.
Cada caso conserva un `receipt.json`; los casos evaluados también conservan
reportes bajo cada combinación de motor y fuente. El cliente API del ejemplo
es una respuesta en memoria explícitamente sintética.

## Cambia únicamente la configuración de entrada

```python
source = ef.LocalDataSource({"input": ef.FileInput(csv_path, csv_spec)})
# La alternativa usa las mismas columnas declaradas con formato JSONL:
source = ef.LocalDataSource(
    {
        "input": ef.SQLiteInput(
            database,
            "SELECT id, sequence, amount FROM entries WHERE cohort = ?",
            jsonl_spec,
            ("demo",),
        )
    }
)
```

El contrato y el plan no cambian. La especificación de lectura sí declara el
formato, los campos y las conversiones. No se infieren monedas ni se convierten
SQL REAL a Decimal exacto. Para un API real, pasa un context manager de respuesta
a `StreamInput`; tu cliente controla autenticación y timeouts. Para otro motor
SQL, implementa el puerto con tipos e identidad explícitos y comprueba su
consistencia; este candidato no incluye adaptadores PostgreSQL/MySQL.

## Límites comprobables

El IR y las ventanas admitidas forman parte del contrato estable; los proveedores,
las fuentes extendidas y la orquestación conservan su alcance experimental.
Las capacidades exactas y las
restricciones de ventanas están en [migration-ir](migration-ir.md) y en
`get_adapter_capabilities()`. DuckDB materializa y comprueba la ventana antes de
filtros o proyecciones posteriores, para que no oculten sus errores. No hay
frames arbitrarios ni agregaciones de ventana admitidos.

Los lotes reducen y controlan la lectura; las tablas finales y los recibos de
ingestión todavía se materializan. Los límites son cooperativos, no una cuota
dura de RAM ni procesamiento distribuido. Los bloqueos de transporte requieren
timeouts del cliente. Combinar proveedores no crea una transacción común entre
bases o APIs. Los contratos admiten dominios distintos, pero un ejemplo
sintético no acredita adopción real en salud, finanzas ni producción.

Los cinco pasos de implementación no son un porcentaje de Universalidad
UV01–UV12 ni una declaración de compatibilidad universal al 100 %. Windows,
Linux y macOS, versiones de Python y arquitecturas requieren recibos del mismo
candidato. La matriz histórica, licencias, revisión humana y publicación no se
cierran mediante estas mejoras técnicas.
