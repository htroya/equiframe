# EquiFrame 0.1.0 — contratos semánticos

El paso 1 implementa una biblioteca instalable para definir, validar y serializar
contratos estrictos. Funciona localmente con Python 3.12 x64. No necesita VM,
datos reales, cliente remoto, DW, motores tabulares ni ML. La matriz CI prueba
Windows Server 2022 y Ubuntu 24.04; ARM64 y otras versiones de Python no se
declaran soportadas. Licencia y publicación externa pendientes; no hay paquete en PyPI.

## Instalación reproducible

Desde la raíz del repositorio, con Python 3.12 instalado (Windows):

```powershell
python -m venv .tools
.\.tools\Scripts\python.exe -m pip install --no-deps uv==0.11.6
Set-Location packages/equiframe
$uvEquiframe = (Resolve-Path ..\..\.tools\Scripts\uv.exe).Path
& $uvEquiframe sync --locked --python 3.12
& $uvEquiframe run --locked equiframe contract validate examples/nulls_types.json
```

`uv.lock` fija versiones y hashes, incluidos los marcadores de plataforma.
`sync` crea `.venv` editable para desarrollo; `--no-dev` instala solo ejecución.
No se reutiliza Anaconda como entorno de dependencias; puede proporcionar
el intérprete base. `.tools` solo contiene el gestor uv fijado.

Ubuntu, desde la raíz, con `python3.12` instalado:

```bash
python3.12 -m venv .tools
.tools/bin/python -m pip install --no-deps uv==0.11.6
cd packages/equiframe
../../.tools/bin/uv sync --locked --python 3.12
../../.tools/bin/uv run --locked equiframe contract validate examples/nulls_types.json
```

Los comandos siguientes usan `uv` en PATH; en Windows puede sustituirse por
`& $uvEquiframe`, y en Ubuntu por `../../.tools/bin/uv`.

## API pública

Desde `packages/equiframe`, con el paquete instalado:

```python
from pathlib import Path
from equiframe import (
    ContractValidationError,
    canonical_contract_bytes,
    contract_fingerprint,
    contract_json_schema,
    read_contract,
    validate_contract,
    write_contract,
)

contract = read_contract("examples/aggregations.json")
assert validate_contract(canonical_contract_bytes(contract)) == contract
print(contract.contract_id, contract.revision, contract_fingerprint(contract))
Path(".cache").mkdir(exist_ok=True)
write_contract(contract, ".cache/contract.json")
schema = contract_json_schema()

try:
    validate_contract('{"schema_version":"99.0"}')
except ContractValidationError as error:
    for issue in error.issues:
        print(issue.path, issue.code, issue.message)
```

`validate_contract` acepta texto JSON, bytes UTF-8 o un mapping compatible con
JSON. Los constructores aceptan tipos Python declarados: tuplas para colecciones
inmutables, `Decimal` o texto decimal exacto; booleanos/enteros no se convierten
desde cadenas. Se rechazan campos desconocidos, miembros duplicados de JSON,
versiones desconocidas, números JSON NaN/Infinity y decimales desde números.
`equiframe.__all__` enumera la API explícita; `py.typed` declara tipado.

Tipos lógicos: booleano, entero (8/16/32/64 bits y signo), cadena, decimal
(precisión 1–76 y escala 0–precisión), float (32/64), día y timestamp
(s/ms/us/ns, zona opcional). El límite decimal es una decisión del formato;
no garantiza soporte de ese intervalo por un futuro adaptador.

Los esquemas declaran claves/ámbito (`table`, `global`, `columns`), claves
incompletas, multiplicidad y orden. `preserve` conserva multiplicidad;
`distinct` declara semántica de conjunto. `significant` declara columnas,
dirección, posición de ausencias y empates. El validador comprueba coherencia
y referencias; no verifica datos ni unicidad real.

Ausencia, NaN, cadena vacía y cero son distintos. Equivalencias vacío/cero con
ausencia o NaN con ausencia requieren política explícita, columna nullable y
justificación. NaN solo es válido en floats. Columnas numéricas requieren unidad
y comparación explícitas; decimal siempre exacto. Tolerancias aproximadas:
límites no negativos, unidad coincidente y justificación. Redondeo decimal:
modo y motivo explícitos; no se aplica al validar ni serializar.

Timestamps: texto ISO hasta nueve dígitos fraccionarios, offset y zona IANA
separada, sin float ni truncamiento a microsegundos. No se admiten leap seconds
ni offset desconocido `-00:00`. Se validan calendario, granularidad, offset/zona,
intervalos y política de timestamps sin offset. Asignar zona exige resolución
explícita de horas ambiguas; huecos DST se rechazan. Fechas siguen siendo días.
`allowed_values` declara restricciones tipadas, no tablas de prueba.

Reglas/precondiciones: seis formas cerradas (`schema`, `key`, `cardinality`,
`join`, `order`, `aggregate`), con referencias verificadas, revisión, severidad,
obligatoriedad y aplicabilidad. No se ejecutan ni aceptan callbacks/SQL/expresiones.
Todavía no hay registro de reglas ejecutables.

`ArtifactRef` describe URI, SHA-256, formato, tamaño y esquema opcional. Rechaza
credenciales, query y fragmentos de URI. Solo declara metadatos: no descarga ni
verifica contenido. `ArtifactStore` es el único Protocol materializado, porque
sus tipos están completos. Snapshots, adaptadores, resultados, reglas
ejecutables, perfiles y detectores se definen en pasos posteriores.

## JSON canónico y huella

`equiframe-metadata-json-v1`: volcado JSON de modelos revalidados, todos los
campos/defaults/`null` incluidos, claves de objetos ordenadas por puntos de
código Unicode según Python, arrays en su orden declarado, UTF-8 sin BOM,
sin normalización Unicode, espacios ni salto final. No es RFC 8785/JCS.
Floats finitos usan `json.dumps` de Python 3.12; no se repara precisión perdida
antes de validar. La CLI usa la misma lógica que la API.

Decimal usa `str(Decimal)`: conserva signo (incluido cero negativo), dígitos y
exponente/escala. `"1.0"` y `"1.00"` pueden tener huellas distintas. Timestamps
mantienen texto, fracción, offset y zona, sin conversión a UTC. Valores
especiales etiquetados: `{"kind":"null"}`, `{"kind":"nan"}` y
`{"kind":"infinity","sign":"positive"}`; vacío y cero siguen separados.

`contract_fingerprint` es SHA-256 de los bytes canónicos e incluye ID/revisión.
El orden/espaciado de miembros del JSON original no cambia la huella; el orden
de arrays y las políticas sí forman parte de la representación. No compara
datos, prueba equivalencia tabular ni acredita revisión científica.

Los archivos `schemas/contract-1.0.schema.json` y
`schemas/artifact-ref-1.0.schema.json` se generan desde los modelos. JSON Schema
cubre estructura/tipos; referencias, zonas, DST y coherencia entre campos
requieren la API. Solo se admite versión de esquema `1.0`, obligatoria.
No hay migración automática.

## CLI y errores

```bash
uv run --locked equiframe contract validate examples/dates.json
uv run --locked python -m equiframe contract validate examples/joins.json
```

| Código | Significado de `contract validate` |
|---|---|
| 0 | Contrato válido; imprime ID/revisión y SHA-256 de metadatos |
| 2 | JSON, contrato, versión o argumentos inválidos |
| 3 | Fallo de lectura del archivo |

Errores a stderr con ruta JSON y código concreto. El comando no usa 1 porque
no evalúa alertas/diferencias. `ContractValidationError.issues` contiene ubicación,
código y mensaje; `SchemaVersionError` y `ContractParseError` son subclases.
`ContractIOError` identifica I/O fallida. Constructores directos usan
`pydantic.ValidationError`; los servicios públicos traducen errores de validación.

## Verificación y distribución

Desde `packages/equiframe`, después de `uv sync --locked`:

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked python tools/generate_assets.py --check
uv run --locked pytest -q
uv run --locked python -m build --no-isolation
uv run --locked python tools/verify_distribution.py
```

El backend y sus dependencias están en el lock; `--no-isolation` usa ese entorno.
Build produce `dist/equiframe-0.1.0-py3-none-any.whl` y
`dist/equiframe-0.1.0.tar.gz`. El verificador crea entornos temporales en el
proyecto, instala dependencias runtime del lock y el wheel sin editable,
comprueba `py.typed` e importación sin motores/ML/dev, valida cinco ejemplos por
CLI y reconstruye desde el sdist comparando todos los bytes del wheel.
Acepta `--uv /ruta/al/uv` si el gestor no está en PATH.

Regeneración intencional de esquemas/fixtures:

```bash
uv run --locked python tools/generate_assets.py
```

Cambiar dependencias exige resolver un nuevo lock y repetir CI. `pip install
dist/equiframe-0.1.0-py3-none-any.whl` funciona, pero solo el lock reproduce el
entorno comprobado. Los fixtures no fijan cohorte, escala monetaria real, alpha
ni tamaño del benchmark. La implementación se detiene en el paso 1.
