# Revisión de aportes y actualización preparatoria de la tesis

Fecha: 11 de octubre de 2026. Documentos privados de trabajo: base
`tesis_corregda_v1.docx` y alternativa `tesis_corregda_v_alterna.docx`.
El Word se entrega en su carpeta original, fuera de Git. Los originales y el
control detallado quedan respaldados en `revision_95_20261011/originales`.

## Comparación y decisiones

La inspección encontró 635 párrafos y 20 tablas en la base frente a 504 párrafos
y 17 tablas en la alternativa. El alineamiento textual produjo 58 bloques de
diferencias; esa unidad es un bloque de edición, no una contribución aprobada.
Ambas versiones comparten 145 textos distintos de párrafos no vacíos.

| Aporte o diferencia de la alternativa | Dictamen | Incorporación en la base |
|---|---|---|
| Explicaciones de casos conocidos, propiedades y relaciones metamórficas | Correctas si la propiedad corresponde a la operación; muchas ya estaban presentes | Se conservan 2.2.3 y sus ejemplos, sin duplicarlos |
| Mutaciones y variantes válidas | Útiles; cambiar código no equivale a producir divergencia | Se precisa que la etiqueta depende del efecto frente a contrato y esperado independiente |
| Niveles de pruebas | Útiles, requieren distinguir aceptación humana de automatización | Se precisan los cinco niveles de ISTQB y su uso preparatorio en 2.2.3 |
| Grano de adjudicación y relación con proveedores | Compatibles cuando conservan moneda, multiplicidad y grano | Se conservan las explicaciones ya presentes y la Tabla 12; no se suman montos a través del puente de proveedores |
| Perfil, puntuación de Isolation Forest, MAD y falsos positivos | Aprovechables como explicación; no constituyen evidencia experimental | Se mantienen las aclaraciones existentes sobre puntuación, calibración, observabilidad y soporte pareado |
| Cinco familias principales y predominio de dos parejas | Incompatibles con la base vigente | Se conservan tres parejas, tres familias principales y nueve estratos; duplicados/orden y fechas quedan transversales |
| Cuotas de sesenta escenarios y partición 30/10/20 | No justificadas por inventario actual y distintas del protocolo | No se incorporan cuotas inventadas ni se acredita N de aprendizaje por número de filas |
| Comparar el costo de todo O con M como si fuera C | Comparación de tareas y soportes diferentes | Se mantiene el contraste acotado C frente a perfil e inferencia y se registra aparte el costo completo de O |
| Sufijos de referencias de scikit-learn | No intercambiables entre las bibliografías | Se preserva la correspondencia de la base: c, GroupShuffleSplit; d, IsolationForest |
| Capítulos 3–5 de la alternativa | Fuera de la entrega solicitada | No se importan desarrollo, resultados ni conclusiones |

## Investigación y enriquecimiento

Se consultaron fuentes primarias para precisar capacidades y fundamentos:
[PEP 544](https://peps.python.org/pep-0544/),
[flujo PyPA](https://packaging.python.org/en/latest/flow/),
[pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/),
[SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final),
[ISTQB CTFL 4.0.1](https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf)
y [backends de Pandera](https://pandera.readthedocs.io/en/stable/supported_libraries.html).
Consulta: 11 de octubre de 2026. SSDF 1.1 se usa como marco publicado de prácticas,
sin atribuir certificación. Se explicita el soporte PyArrow anunciado en Pandera
0.33.0 sin trasladarlo a versiones previas.

Se añadió 2.1.7 sobre extensibilidad y distribución en el ecosistema Python;
2.2.9–2.2.12 sobre contratos de extensión, obligaciones de prueba, identidad de
paquetes y límites de confianza. La interpretación del diseño de EquiFrame se
distingue de las capacidades declaradas por las fuentes.

El anexo B conserva los controles históricos con sus versiones y fecha. B.5–B.10
incorporan la entrega A13, hashes, alcance de operaciones, uso y documentación,
preparación de paquetes, organización de evidencias, VM ARM64, resultados
consolidados, pendientes y plan. No se atribuyen a la tesis resultados de eficacia,
aprendizaje, etiquetas independientes ni dictamen institucional.

## Fidelidad y cumplimiento

El documento actualizado tiene 148 páginas. Se conservan Times New Roman 12,
doble espacio, tema, geometría A4, dos secciones, portada, encabezados, 20 tablas,
18 recursos gráficos y todas las leyendas. Los índices se actualizaron con Word
16. Las 148 páginas fueron renderizadas y revisadas; los controles intermedios
son privados. Se verificaron además tema, fuentes, geometría, textos de tablas
y leyendas respecto del original.

El usuario confirmó pendientes licencia/titulares y revisión independiente o
resultados científicos aprobados. **Esta edición no acredita 95 % de cumplimiento
científico de la tesis.** T01–T22 conservan su evidencia y aceptación requeridas.
No se transforma preparación editorial en evaluación científica. Véase el
[plan de cierre](IMPLEMENTATION_95_PLAN_20261011.md) y la
[trazabilidad de tesis](THESIS_TRACEABILITY.md).

Identidades originales SHA-256:

- Base: `365af93cdd4bbf7e665145d0e4597eb1391678f5dcb16ce25423b5802c249ac2`.
- Alternativa: `0a9a64b1bbbc76a770ce0966a944a87ce55830628f434ee08877d96bd4d01e4a`.
- Word entregado: `883b187f08221b9b4abab775430d9a2c87b6d92f503494317f3e1fec214d0f3c`.
