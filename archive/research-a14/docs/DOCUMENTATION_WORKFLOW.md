# Integrar una comparación en un pipeline

[Portal](README.md) · [Instalación privada](../packages/equiframe/docs/installed-private.md) ·
[Elegir API](../packages/equiframe/docs/choosing-api.md)

Este recorrido usa datos sintéticos y el núcleo privado **0.12.0a13** con el extra
`arrow`. No necesita benchmark, detector, VM ni servicio. Instala primero el
wheel identificado y dependencias revisadas; comprueba `pip check` y
`python -I -m equiframe doctor --extra arrow`. Ejecuta fuera del checkout.

## Ejecutar el código completo

Guarda el bloque como `pipeline_comparison.py` en una carpeta de trabajo nueva.
La comparación usa la tabla de la derecha como esperado, permite reordenar filas
y exige la clave única `id`. Primero persiste el reporte y después aplica el
gate. No reduce tipos, borra duplicados, amplía tolerancias ni usa `if result`.

```python
from pathlib import Path

import equiframe as ef
import pyarrow as pa

expected = pa.table({"id": ["A", "B"], "quantity": [10, 20]})
cases = {
    "equivalent": (pa.table({"id": ["B", "A"], "quantity": [20, 10]}), expected),
    "different": (pa.table({"id": ["B", "A"], "quantity": [21, 10]}), expected),
    "not_evaluable": (expected, pa.table({"id": ["A", "A"], "quantity": [10, 10]})),
}
for expected_state, (candidate, reference) in cases.items():
    folder = Path("pipeline-evidence") / expected_state
    result = ef.diff(candidate, reference, keys=["id"], work_dir=folder / "private")
    report = ef.write_comparison_report(result, folder / "report")
    print(expected_state, result.state, result.complete)
    print(report.to_text())
    if result.state != expected_state:
        raise RuntimeError("Unexpected comparison state")
    try:
        ef.assert_equivalent(result)
    except ef.EquivalenceDifferentError:
        if expected_state != "different":
            raise
        print("REJECT different")
    except ef.EquivalenceNotEvaluableError:
        if expected_state != "not_evaluable":
            raise
        print("REJECT not_evaluable")
    else:
        if expected_state != "equivalent":
            raise RuntimeError("Unsafe acceptance")
        print("ACCEPT equivalent")
```

En PowerShell, usando el intérprete del entorno instalado:

```powershell
& .venv\Scripts\python.exe -I pipeline_comparison.py
$LASTEXITCODE
```

En POSIX, desde la carpeta de trabajo:

```bash
.venv/bin/python -I pipeline_comparison.py
```

El script completo debe terminar con **0** porque comprueba y captura los dos
rechazos esperados. En un pipeline real no captures esas excepciones como éxito:
deja que bloqueen la entrega o tradúcelas a un estado explícito de rechazo.
Una segunda ejecución usa otra carpeta de trabajo: los reportes no sobrescriben
destinos existentes. Para probar `-O`, usa también una carpeta nueva.

## Interpretar los tres casos

| Entrada | Resultado requerido | Acción del gate |
|---|---|---|
| Mismos valores, distinto orden | `equivalent` | `ACCEPT equivalent` |
| Cantidad de B pasa de 20 a 21 | `different` | `REJECT different` |
| Referencia esperada con clave A duplicada bajo clave única | `not_evaluable` | `REJECT not_evaluable` |

La referencia inválida no sirve para concluir equivalencia; no se deduplica A
para aparentarla. Duplicar la clave solo en el candidato, con una referencia
válida, produce `different`: son dos situaciones distintas. La salida muestra
`complete`, pero el gate usa el resultado
semántico completo. El HTML/texto/JSON del reporte son vistas del mismo resultado.
Las vistas minimizan datos; las capturas bajo `private/` siguen existiendo y
deben conservarse/retirarse conforme a la política del proyecto consumidor.

## Pasar de la muestra al proyecto real

Sustituye las tablas por salidas ya materializadas y fijadas de tu pipeline.
Define tipos, claves, unidades, zona horaria, ausencias y orden antes de aceptar
datos. Para un contrato más explícito usa [compare](../packages/equiframe/docs/api.md);
para capturar SQL confiable usa el [recorrido del arquitecto](../packages/equiframe/docs/arquitecto.md).
Captura y ejecución son servicios diferentes; no se ejecuta SQL/lazy implícito
al llamar `diff`. Conserva versión de contrato, esperado revisado, hash de los
artefactos y recibo de entorno. No declares correcto un esperado por coincidir
con otro motor. Consulta [diagnóstico](../packages/equiframe/docs/upgrading.md)
si falta una dependencia, falla la escritura o el resultado no puede evaluarse.
