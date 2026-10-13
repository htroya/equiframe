# Contextos de constructores: 66 obligaciones nuevas de A13

El lote acredita **66 IDs nuevos y distintos** del inventario original de
8.385 obligaciones: **6.254/8.385 = 74,59 %**. Conserva 2.131 `NOT_RUN`; hacen
falta 1.293 IDs adicionales para ≥90 %, o 874 para el umbral anterior de ≥85 %.
El [recibo agregado](OPTION_CONTEXT_CONSTRUCTORS_RESULT_20261012.json) vincula
catálogo, herramienta, resultados, pruebas del verificador y custodia.

Son 22 casos sobre once clases instaladas desde el wheel A13 original, fuera
del checkout. Comprueban la entrada real a `__init__`, el enlace de argumentos
y todos los atributos almacenados. Los oráculos completos de los modelos
auxiliares proceden del catálogo literal original congelado; las variantes
se fijan antes de observar resultados del SDK. No se ejecutan reglas, cargas
de entradas ni transportes por el hecho de construir sus contextos.

| Obligación observada | IDs nuevos |
|---|---:|
| Representante admitido, explícito y no nulo | 46 |
| Default omitido con enlace/estado comprobado | 10 |
| Valor finito explícito, incluidos nulos declarados | 9 |
| Miembro `None` declarado de la tupla SQLite | 1 |

`LocalDataSource` y `CompositeDataSource` conservan mapas copiados con sus
referencias esperadas. Las tres fábricas de listas de `RunContext` se prueban
con dos instancias, vacías y distintas entre sí. Los números, booleanos,
contenedores, referencias nativas y modelos auxiliares se comparan con tipos
exactos y recursión completa; las rutas resueltas se cotejan por tipo y valor.

La revisión IA encontró que las listas literales JSON del primer instrumento
usaban igualdad Python interna. Aunque el lote original pasó, su instrumento
y resultados se conservaron **sin crédito**. La versión corregida incorpora
recursión estricta y un contraejemplo con `True`/`1` y `1.0`/`1` dentro de listas
y diccionarios anidados. Cuatro pruebas del verificador pasan en cada modo.
El mismo XML contiene cuatro pruebas SERCOP; estas no son obligaciones nuevas.

Normal y `-O` obtienen 22 PASS y los mismos 66 IDs. Los 108 enlaces de IDs se
reducen a 66; el segundo modo y las pruebas auxiliares suman cero cobertura.
«mi dot» revisó el lote como **agente IA de solo lectura**, sin aceptación humana.

La custodia privada `trace85_contextos_20261012.zip` conserva 20 archivos,
1.697.657 bytes y lectura completa verificada, SHA-256
`36714b617dd6bede4a59de66b9573bb5efd42c0ec6685a9ec66fe693d7dc65ed`.
Incluye el archivo previo de constructores y sus identidades. No modifica el
SDK, el Word ni las mediciones históricas de A11/A12.
