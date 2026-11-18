# Doce defaults de campos con esperados originales

La trazabilidad aumenta de 6.254 a **6.266/8.385 = 74,73 %** por doce defaults
pendientes y distintos. Normal y `-O` pasan los doce casos; el segundo modo
acredita cero IDs adicionales. El [agregado verificable](OPTION_MODEL_DEFAULTS_RESULT_20261012.json)
conserva catálogo previo, fuentes, recibos, revisión IA y custodia.

| Modelo | Defaults comprobados |
|---|---|
| `Arithmetic` | `rounding` |
| `Deduplicate` | `by`, `ties` |
| `EquiJoin` | `cardinality` |
| `ComparisonSpec` | `policy` |
| `ExecutionPlan` | `options` |
| `MigrationSpec` | `execution_options`, `comparison_options`, `rule_options`, `profile_options`, `options` |
| `ComparisonPolicy` | `justification` |

Cada caso omite únicamente su campo objetivo y conserva los literales del
catálogo original. `ComparisonPolicy` usa el literal estricto anidado de
`ComparisonSpec`; no reutiliza el seed independiente que necesita justificación.
La validación JSON real se observa por código, clase raíz y llamador; el JSON
enviado y `model_fields_set` prueban la ausencia del campo.

Se coteja todo el JSON esperado con tipos recursivos exactos. Los serializers
históricos omiten cuatro atributos; por ello se comprueban también directamente
`rounding='exact'`, `by=()`, `ties='reject'` y `cardinality='many_to_many'`.
Los siete casos de fábrica verifican su clase declarada, clase resultante,
JSON completo y una segunda instancia distinta. Son doce casos sobre once
combinaciones de modelo/input, no doce datasets independientes.

El crédito corresponde a IDs `field:…:default`. Las firmas descriptivas de
Pydantic no se convierten en obligaciones de parámetros ni se vuelven a contar
APIs. Los cuatro contraejemplos estrictos compartidos ya fueron comprobados
en ambos modos; tampoco aportan cobertura adicional.

La revisión «mi dot» fue de **IA y solo lectura**. La custodia privada
`trace85_defaults_modelos_20261012.zip` contiene diez archivos, 1.721.086 bytes,
incluye la custodia anterior y verifica todos los miembros al leerlos de nuevo.
SHA-256: `c9db99ec443817efb2a8d57c5aa34dfd2de6a71b6935ccef21fd675a528f927e`.

Quedan **2.119 `NOT_RUN`**, 1.281 IDs para ≥90 % y 862 para el umbral anterior
de ≥85 %. No se modifica el SDK ni el Word, ni se acredita aceptación humana.
