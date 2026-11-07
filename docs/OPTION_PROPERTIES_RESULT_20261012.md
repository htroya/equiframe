# Lectura comprobada de propiedades públicas A13

Se acreditaron **32 obligaciones nuevas** con 16 casos congelados y esperados
verificados antes de ejecutar el SDK instalado. La unión es **5.974/8.385 =
71,2462731067 %, redondeado 71,25 %**. Faltan **1.154 IDs** para llegar a
7.128 y cumplir el 85 %. El [recibo](OPTION_PROPERTIES_RESULT_20261012.json)
conserva fuentes, herramientas, catálogo y ambas ejecuciones; el
[corte de configuración](OPTION_CONFIGURATION_RESULT_20261012.json) queda intacto.

Se comprueban valores y tipos builtin exactos al leer los descriptores públicos:

- `CancellationToken.cancelled`, antes y después de cancelar un token real.
- `ExpectedProvenance.independently_constructed`, con declaración, solapamiento
  de autor y dependencia de motor representados en metadatos sintéticos.
- `TimestampValue.has_offset` y `fractional_digits`, con timestamps sin zona,
  con offset y con nueve decimales en UTC.
- `PreprocessorBundle.columns`, incluidos los indicadores de ausencia.
- `ComponentDetectionResult.complete`, con resultado completo e incompleto.
- Propiedades de estado, completitud y salidas de los fixtures originales
  de migración, pipeline, verificación y workflow.

Para cada modelo se coteja primero su JSON completo contra el oráculo literal.
Los siete fixtures complejos originales continúan siendo metadatos sintéticos;
leerlos no acredita nuevas ejecuciones nativas ni aprendizaje. La construcción
de las variantes también se coteja completa. Los getters deben devolver
exactamente el tipo builtin esperado: un entero uno no se acepta como booleano
ni un subtipo con el mismo nombre se acepta como el tipo exacto.

Tres casos son guardias sin IDs nuevos: dos negativos adicionales de procedencia
y el timestamp UTC de nueve decimales. Permanecen en el recibo, con cero crédito.
No se acreditan interfaces simuladas de `Protocol`, clases de salida no
disponible ni `exit_code`: estas últimas requieren su vínculo documentado con
la interfaz, que una lectura de metadatos no prueba.

`independently_constructed` verifica la coherencia de lo declarado en el
objeto; no confirma independencia humana. `VerificationResult.publishable`
es su getter operativo, no autorización de publicación ni aceptación
científica. `PipelineResult.complete` puede ser verdadero cuando el detector
no fue solicitado; no equivale a aprobar H. Estas diferencias permanecen
explícitas en la medición.

El catálogo SHA-256
`7cb93ec05d412d30a892d609de3f76b2416566d48bd016a6c70fb0a809f620ca`
precede a las ejecuciones. Los 16 casos pasaron en ambos modos:

| Ejecución | SHA-256 de `result.json` |
|---|---|
| Normal | `8c04f8a4dc05b0269418f4726ed09cc0027f5fe3a21264fc919ad55df88666df` |
| Optimizada | `f7497da36699cf0a48791c526155c832487f47f7abebd546f9f4ea488eb9d20a` |

Seis contrapruebas del arnés pasaron en cada modo. La revisión técnica IA
«mi dot» confirmó previamente los oráculos y la selección; no reemplaza una
revisión humana. El wheel A13 conserva sus bytes y las repeticiones suman cero
obligaciones adicionales.
