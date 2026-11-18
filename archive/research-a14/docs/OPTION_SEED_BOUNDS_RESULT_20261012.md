# Fronteras exactas de fixtures originales A13

Se acreditaron **42 obligaciones pendientes**, mediante **22 fixtures originales**:
33 fronteras inferiores exactas y nueve valores miembros de tuplas homogéneas.
La trazabilidad acumulada queda en **5.902/8.385 = 70,3875968992 %, 70,39 %**.
Faltan **1.226 IDs** para el umbral de 7.128 requerido por la meta del 85 %.
El [recibo agregado](OPTION_SEED_BOUNDS_RESULT_20261012.json) conserva todas
las identidades y enlaza el [corte anterior](OPTION_PUBLIC_TYPES_RESULT_20261011.json).

Cada caso valida y serializa el JSON completo contra el esperado literal del
catálogo A13 original. Se mantuvieron intactas las invariantes coordinadas de
cada modelo. Los esperados provienen del catálogo congelado, no de una llamada
al SDK. `member:0` identifica el tipo del miembro de una colección homogénea;
el valor que alcanza la frontera puede estar en cualquier posición real.
`union:0` identifica una rama concreta, respaldada por el tipo del literal.

Los 22 casos del nuevo catálogo son aserciones adicionales sobre las mismas
22 entradas originales: **no añaden datos independientes**. Repetirlas con
`-O` no añade otras 42 obligaciones. Este alcance acredita construcción y
serialización; no demuestra el cálculo de una operación nativa ni resultados
científicos.

La revisión técnica IA «mi dot» cotejó las semillas completas, esperados,
IDs y ramas antes de ejecutar. La guardia inicial del plan suponía 23 fixtures;
se detuvo sin dar crédito. El listado contenía 22, y ese primer log se conserva.
También se corrigió antes del ensayo la guardia que debía distinguir una
frontera exacta de un valor inmediatamente fuera de ella. Las contrapruebas
rechazan esa confusión, booleanos como cero numérico, diferencias en otro campo
del JSON y excepciones inesperadas.

El lote completo pasó en Windows CPython 3.12, normal y `-O`; sus recibos son:

| Ejecución | SHA-256 de `result.json` |
|---|---|
| Normal | `54cf08ad5f0630465aade2056c7cda1b4cd4d3f1df73204e6a52b1662a2b5772` |
| Optimizada | `50167f6a52b75c59f9bee159617eb38c6b2a3dcb1a7dc102c51d8256a5fa8e9b` |

La identidad del wheel completo y de los tres verificadores cargados se
comprueba antes de ejecutar y se conserva en el recibo. La biblioteca mantiene
sus bytes y versión **0.12.0a13**. El revisor IA no representa aprobación humana.
