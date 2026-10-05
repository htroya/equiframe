# Primer uso: tres recetas reproducibles

Candidato privado EquiFrame 0.11.1, **Python 3.12 únicamente**. No instale el
nombre desde PyPI: el paquete del equipo no está publicado allí. Este kit
contiene el wheel exacto, cuatro scripts (tres recetas y su fixture pytest),
dependencias fijadas con hashes y estas guías. No necesita el checkout.
Los datos son sintéticos, pequeños y definidos en los scripts. No hay descargas
de datos, SQL remoto, credenciales, servicios, notebooks ni cambios al sistema.

**Meta por validar:** un primer diagnóstico útil en cinco minutos. La ejecución
automatizada por un consumidor técnico independiente no demuestra usabilidad
humana. Registre el primer uso real en `OBSERVATION.md`; no invente una medición.

## 1. Obtener y verificar el kit

Use el kit privado preparado del candidato, recibido por el canal autorizado.
Descomprímalo en una carpeta nueva llamada `kit`, fuera del repositorio, y abra
una terminal allí. Mantenga esa carpeta intacta: entorno, resultados y registro
de observación se guardan en carpetas hermanas. Necesita Python 3.12 instalado. Compare el SHA-256 del ZIP con el recibo
recibido por separado antes de extraerlo si necesita comprobar su procedencia.
El manifiesto interno detecta cambios de archivos, no autentica al remitente.

```bash
python3.12 --version
python3.12 verify_kit.py
python3.12 -m venv ../first-use-env
```

En Windows use `py -3.12` en lugar de `python3.12`. Active el entorno:

- Linux/macOS: `source ../first-use-env/bin/activate`
- PowerShell: `..\first-use-env\Scripts\Activate.ps1` (si la política local lo impide,
  use directamente `..\first-use-env\Scripts\python.exe`; no cambie políticas de seguridad)

Instale en ese entorno limpio:

```bash
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
python -m pip install --no-index --no-deps --force-reinstall wheels/equiframe-0.11.1-py3-none-any.whl
python -m pip check
python -c "import equiframe, sys; print(sys.version); print(equiframe.__file__)"
```

La primera instalación **descarga explícitamente dependencias de su índice pip
configurado**; no descarga datasets. Los pins/hashes proceden del `uv.lock` del
candidato. La segunda usa únicamente el wheel verificado. Para una instalación
sin red, prepare antes un wheelhouse de esos mismos pins y añada
`--no-index --find-links /ruta/wheelhouse` al primer comando. No se incluyen
binaries de dependencias en el kit. No retire hashes ni fuerce otras versiones
para superar un error. Si no hay wheel para su plataforma, registre el bloqueo;
esta entrega no certifica una matriz de plataformas nueva.

Si solo dispone del código fuente y de un wheel construido, el mantenedor puede
preparar el mismo kit con `python tools/build_first_use_kit.py --output /ruta/nueva`
desde `packages/equiframe`. Sus controles de distribución prueban la instalación
copiada fuera del checkout. Para el primer uso siga desde aquí solo el kit.

## 2. Diagnosticar un refactor pandas

Después de instalar, cree una carpeta hermana nueva para todos los resultados:

```bash
python -c "from pathlib import Path; Path('../first-use-work').mkdir()"
cd ../first-use-work
```

Los comandos siguientes se ejecutan desde `first-use-work`. `../kit` permanece
inalterado y se puede verificar otra vez con `python ../kit/verify_kit.py`.
Guarde el formulario de observación completado en esta carpeta de trabajo,
no dentro del kit original.

```bash
python -I ../kit/refactor_comparison.py --output refactor-different
```

**Salida esperada: código 1**, deliberado. El reporte muestra:

- `different`, evaluación y cobertura completas, estrategia `key`
- Clave `id="B"`, columna `total_cents`
- Candidato `integer(2001)` frente a esperado `integer(2000)`; ambos `int64`
- Política numérica `exact`, unidad declarada `USD_cent`; una fila modificada

Abra `refactor-different/report/report.html` o lea `report.txt`. El contrato
inspeccionable queda en `refactor-different/contract.json`. El refactor vectorizado
introdujo un centavo; las filas reordenadas no son el fallo porque su orden se
ignora y la clave única se valida. La referencia conserva la implementación
anterior y se contrasta además con los tres valores literales de esta fixture.
Esto no convierte pandas ni una referencia histórica en un oráculo universal.

Ejecute el caso corregido sin cambiar la política:

```bash
python -I ../kit/refactor_comparison.py --case equivalent --output refactor-equivalent
```

Código 0, `equivalent`. Extensión sin clave:

```bash
python -I ../kit/refactor_comparison.py --without-key --output refactor-bag
python -I ../kit/refactor_comparison.py --without-key --case equivalent --output refactor-bag-ok
```

Códigos 1 y 0. Sin identidad se comparan multiconjuntos: se conservan ocurrencias,
no se inventan filas modificadas. La primera diferencia se expresa como excesos
de filas por lado. No deduplicar para hacer pasar. Los tres enteros de la fixture
son pequeños; esta receta no promete aritmética int64 sin overflow para entradas
arbitrarias. No representa montos fraccionarios ni conversiones de moneda.

**Evidencia:** este script muestra únicamente sus valores sintéticos conocidos.
Use `--redacted` para ocultar valores y metadatos del reporte. Los originales
se eliminan al salir salvo que añada `--work-dir private-refactor` (fuera del
reporte). Esa opción conserva capturas privadas y diferencias completas; no las
suba automáticamente. El contrato adjunto contiene nombres/unidades sintéticos,
incluso en modo redactado; comparta solo `report/` si quiere la vista mínima.

## 3. Validar una migración acotada pandas → DuckDB

```bash
python -I ../kit/migrate_duckdb_recipe.py --case equivalent --output migration-ok
python -I ../kit/migrate_duckdb_recipe.py --case different --output migration-regression
python -I ../kit/migrate_duckdb_recipe.py --case not_evaluable --output migration-limited
```

Códigos 0, 1 y 3. Usa **`ef.migrate` real**, con un IR `Scan` + `Aggregate`,
no traduce programas Python ni SQL arbitrarios. Ambos motores ejecutan su propia
implementación sobre la misma captura; el esperado es literal y separado.
Tipos Decimal/escala, moneda, importes NULL, suma vacía y conteo se declaran antes
de ejecutar. El caso negativo cambia deliberadamente la semántica de suma vacía:
ambos motores pueden estar `equivalent` entre sí y aun así `verification=divergent`
frente al esperado conservado. No es una divergencia de motores inventada.

Cada salida contiene `source-target/`, `source-expected/` y `target-expected/`;
cada carpeta conserva `report.json`, `report.txt`, `report.html` y
`evidence-manifest.json`, verificados antes de anunciar la publicación.
`not_evaluable` limita cada comparación a una fila; sus conteos parciales no son
totales finales. No cambie el esperado para resolverlo.

`--show-synthetic-values` permite inspeccionar el esperado literal y ambas
salidas materializadas. Se esperan EUR: total NULL/2 filas, JPY: 0.00/1 fila y
USD: Decimal exacto 1000000000000000.03/3 filas. El negativo cambia únicamente
el total EUR a 0.00 en ambos motores; cada comparación contra el esperado
conserva una diferencia. Por defecto no se imprimen valores y los reportes
están redactados. Las capturas originales son temporales;
`--work-dir private-migration` conserva los inputs, esperado, ambas salidas,
configuración y evidencia. Nunca mezcle ese directorio con la salida compartible.

El adaptador DuckDB administra una conexión propia `:memory:` por ejecución,
con un hilo, límite DuckDB de 128 MB y zona de sesión UTC explícitos. Materializa
la salida y cierra la conexión antes de devolverla; la receta relee y verifica
`read_migration` después de esa devolución. No abre un fichero DuckDB compartido,
SQL externo ni descarga extensiones. El plan no usa valores temporales: fijar
UTC no prueba operaciones de fechas fuera del IR admitido. Se conservan los
tipos/políticas y versiones del entorno. Los presupuestos del runner son
cooperativos, no una cuota dura de RSS para el proceso. No se pasa una relación
DuckDB a `ef.diff`: esa entrada no es admitida. No se amplían operaciones IR ni
se prueba validez para todos los inputs.

## 4. Detectar una regresión en pytest y CI

```bash
python -I ../kit/assertion_ci.py --case equivalent --output ci-ok
python -I ../kit/assertion_ci.py --case different --output ci-different
python -I ../kit/assertion_ci.py --case not_evaluable --output ci-limited
```

Códigos 0, 1 y 3. Se exporta y verifica el reporte **antes** de
`ef.assert_equivalent`. Los fallos conservan diagnóstico JSON/texto/HTML y
`evidence-manifest.json`. No use `assert result` ni `if result`: el truth testing
lanza `TypeError` en los tres estados.

Para ejecutar la fixture pytest real, cada comando utiliza una carpeta nueva:

```bash
python -I -B -m pytest -q -o addopts= -p no:cacheprovider ../kit/test_assertion_recipe.py -k equivalent
python -I -B -m pytest -q -o addopts= -p no:cacheprovider ../kit/test_assertion_recipe.py -k different
python -I -B -m pytest -q -o addopts= -p no:cacheprovider ../kit/test_assertion_recipe.py -k not_evaluable
```

Pytest sale 0/1/1 respectivamente: los dos últimos son tests deliberadamente
fallidos, no `xfail`. Encuentre los reportes en `ci-reports/<caso>/`. Para repetir,
use otro directorio de trabajo limpio que siga apuntando a los scripts del kit;
no sobrescriba evidencia. Añada `-B` a Python para no crear bytecode junto a la
fixture; los comandos anteriores ya lo usan.
En su pipeline real el fixture debe devolver candidato/esperado propios, no
seleccionar un caso sintético para simular validación.

Antes de publicar, verifique la lista cerrada con la función del script:

```bash
python -I -c "import runpy; from pathlib import Path; recipe = runpy.run_path('../kit/assertion_ci.py'); recipe['verify_upload_directory'](Path('ci-different'))"
```

Ejecute esa verificación aunque el test falle (`always()` o equivalente de su
sistema CI); suba solo `report.json`, `report.txt`, `report.html` y
`evidence-manifest.json` de ese directorio **si se verifica**. Conserve el código
de fallo del test. Una publicación/manifest fallidos nunca significan éxito.
No suba `--work-dir`, entornos, checkout, snapshots o JSONL crudos. El ejemplo
produce un artefacto local real; no afirma haber ejecutado un job remoto.

## 5. Revisar una referencia o contrato deliberadamente

No existe un botón «aceptar todo» ni actualización automática del esperado.
Ante un fallo, inspeccione tipos, valores, claves, cobertura y política, y
corrija el candidato cuando sea un error. Si cambió el requisito de negocio:

1. Conserve el reporte fallido, referencia anterior y sus hashes
2. Documente el cambio concreto, justificación, responsable y revisión
3. Cree una nueva revisión del contrato antes de comparar; modifique solamente
   la política aprobada. Para cambiar el baseline, genere/revise el esperado por
   una vía independiente, nunca copiando ciegamente el candidato fallido
4. Pruebe caso positivo, diferencia real, esperado inválido e interrupción
5. Versione el baseline autorizado y el contrato; revise el diff en un PR

`ef.read_diff_contract(result)` permite inspeccionar/persistir la declaración;
`ef.DiffContract.model_validate_json(...)` permite releerla, y
`ef.diff(candidate, expected, contract=declaration)` reutiliza exactamente esa
política. No mezcle este cambio revisado con un ajuste automático de tolerancias.
La receta no modifica ninguno de sus baselines externos.

## Si algo falla

Use Python 3.12, un entorno nuevo y los pins íntegros. Revise `pip check` y la
ruta de import; no añada `PYTHONPATH` ni use una instalación editable. El código 1
es esperado en las demostraciones negativas; 3 significa que no se estableció
el juicio necesario; 2 indica configuración/ejecución/publicación inválida.
Use directorios nuevos. Falta de permisos o disco y un reporte ausente no son
equivalencia. No publique tracebacks con datos/variables de entorno. Registre
bloqueos, ayuda y tiempo real en `OBSERVATION.md`.

Siga con `INTERPRETATION.md` para explicar los tres estados y los límites.
