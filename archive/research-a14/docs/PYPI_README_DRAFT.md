# EquiFrame: propuesta de presentación en PyPI

**Borrador de preparación**, no metadata del wheel A13 ni publicación pública.
La licencia, acceso publicador, enlaces públicos y ensayo siguen pendientes.
Este texto no afirma que el paquete del equipo pueda instalarse desde PyPI.

EquiFrame compara resultados tabulares mediante contratos explícitos y produce
evidencia de diferencias en valores, tipos, claves, multiplicidad y orden. El
núcleo funciona como biblioteca Python; los motores y ML son dependencias
opcionales. El benchmark es otra distribución con un pin exacto del núcleo.

## Instalación e identidad

El candidato actual es **0.12.0a13**, Alpha privada. Recibe el wheel y hashes por
el canal autorizado e instálalo en un entorno limpio con resolución normal de
dependencias. La base contiene contratos/modelos; `arrow` permite el ejemplo
siguiente. `duckdb` añade captura SQL; `engines` permite las rutas compatibles
de Pandas, Polars y DuckDB; `ml` se usa solo con los detectores opcionales.

El comando público de instalación y los enlaces de documentación/incidencias
solo se incorporarán tras demostrar una release accesible y aprobar los
derechos. Antes de usar datos, comprueba versión, origen de import y `pip check`.
La versión sola no identifica los bytes de un candidato privado.

## Comparación mínima

Tras instalar el wheel identificado con `arrow`, en un directorio nuevo:

```python
from pathlib import Path

import equiframe as ef
import pyarrow as pa

expected = pa.table({"id": ["A", "B"], "quantity": [10, 20]})
candidate = pa.table({"id": ["B", "A"], "quantity": [21, 10]})
result = ef.diff(candidate, expected, keys=["id"], work_dir=Path("private-evidence"))
ef.write_comparison_report(result, Path("comparison-report"))
try:
    ef.assert_equivalent(result)
except ef.EquivalenceDifferentError:
    print("Expected difference rejected")
else:
    raise RuntimeError("Difference incorrectly accepted")
```

La referencia es la tabla de la derecha: B cambia de 20 a 21 y se rechaza.
El reporte se guarda antes del gate; sus vistas minimizan datos pero no borran
las capturas privadas. Cada intento usa un destino nuevo. Los errores de
entrada/escritura/dependencia no son éxito.

## Alcance y compatibilidad

`equivalent` significa satisfacer el contrato evaluado sobre datos capturados;
no certifica corrección empresarial ni equivalencia de programas arbitrarios.
`different` y `not_evaluable` bloquean la aceptación. `complete=True` solo no
acepta; no uses `if result`. Los contratos conservan decimales, zonas horarias,
ausencias y duplicados bajo políticas declaradas y límites explícitos.

El candidato admite por metadata Python 3.10–3.13. Los recibos A13 observados
identifican Windows/Python 3.12 y Linux ARM64/Python 3.10; la matriz completa
permanece abierta. No se afirma certificación de todos los OS/minors ni madurez
de producción. Los presupuestos del núcleo son cooperativos, no aislamiento
duro del SO; callbacks/SQL/plugins confiables pueden tener efectos externos.

El wheel lleva manual, ejemplos y esquemas. Una instalación identificada puede
localizar el manual con `importlib.resources.files("equiframe").joinpath("docs")`.
No requiere OCI, DW, SERCOP o el benchmark para comparar tablas.

## Licencia, soporte y enlaces públicos pendientes

No se ha aprobado el régimen de distribución del proyecto ni una responsabilidad
de soporte/SLA. El repositorio y sus URLs de documentación son privados. Este
borrador identifica esas carencias y no contiene enlaces de usuario ficticios.
El responsable deberá completar licencia/notices y documentación/canal de
incidencias públicos antes de incorporar este texto a nuevos artefactos.

Los ejemplos son sintéticos. Las pruebas técnicas y el acuerdo entre motores
no son resultados científicos aceptados de la tesis. Los originales A13 y sus
recibos permanecen separados de un futuro candidato con este README.
