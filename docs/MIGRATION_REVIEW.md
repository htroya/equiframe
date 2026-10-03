# Revisión de EquiFrame Migrate

Entrega anterior al paso 11, solicitada por Hernán. Versiones: núcleo **0.10.0**,
benchmark **0.10.1**. Fecha: 2026-10-03 UTC. Base: merge del PR 21,
`abae7fd1d9928b4c1f95a4f42487d145a513e7cc`.

## Resultado y alcance

El migrador está dentro de la biblioteca genérica. Un IR relacional cerrado se
compila a operaciones nativas Pandas/Polars/DuckDB. Origen y destino reciben la
misma captura aislada; cada adaptador ejecuta su propia transformación. La
comparación observada y las dos comprobaciones contra un esperado opcional
tienen resultados separados. El esperado no entra en perfiles ni detectores.

La [guía de uso](MIGRATION.md) describe las interfaces, códigos y límites; el
[plan previo](MIGRATION_DESIGN.md) registra las decisiones antes de programar.
Hay API Python, CLI migration validate/run/verify y cinco esquemas nuevos 1.0.
El registro explícito de compiladores/adaptadores permite extensiones confiables;
no transforma callbacks arbitrarios ni carga plugins desde JSON.

La versión del benchmark fija la dependencia en el núcleo 0.10.0. Los formatos
previos conservan su versión; los dos esquemas de detectores y los cuatro del
benchmark que contienen `DetectorVersions` amplían enum/default para el nuevo
emisor y mantienen los productores anteriores. No cambia el algoritmo M/B/H.

## Comprobaciones locales

| Control | Resultado |
|---|---|
| Ruff núcleo, tests, tools y ejemplo nuevo | Aprobado |
| Mypy núcleo y tools | 47 archivos, sin errores |
| Activos sintéticos/esquemas núcleo | 47 activos comprobados |
| Lock núcleo | 50 paquetes, comprobación offline aprobada |
| Ruff benchmark | Aprobado |
| Mypy benchmark y tools, con el wheel núcleo instalado | 29 archivos, sin errores |
| Esquemas benchmark | 37 comprobados |
| Lock benchmark | 46 paquetes, comprobación offline aprobada |
| Suite completa del núcleo instalado desde el sdist | 836 aprobadas en 305,14 s |
| Suite completa del benchmark instalado desde wheel | 437 aprobadas, 2 omitidas, 643,07 s |
| Extras/base núcleo instalados fuera del checkout | Base y seis extras aprobados; importación ligera |
| Ejemplo monetario del wheel, seis direcciones | Todas equivalentes al esperado literal independiente |
| Snippet de la guía | Ejecución aprobada y lectura de evidencia idéntica, con el wheel instalado |
| Reconstrucción sdist → wheel núcleo | Bytes idénticos |
| Reconstrucción sdist → wheel benchmark | Bytes idénticos |
| Consumidor externo del núcleo con tipos estrictos | Aprobado, un archivo sin errores |
| Piloto y ejemplos benchmark instalados | Integración/evaluación y regeneración de seis tablas aprobadas; estado científico pendiente conservado |

Las cuatro suites específicas del migrador contienen **110 casos distintos**:
44 de runner/CLI, 47 de IR/backends y 19 de evidencia física. La ronda final
runner+física aprobó 63 casos en 101,07 s; IR/backends aprobó 47 en 30,21 s.
La suite de distribución completa los ejercitó contra `site-packages`.
Los tiempos describen pruebas técnicas locales y no son mediciones del estudio.

La comprobación del wheel crea consumidores temporales fuera del repositorio,
sin PYTHONPATH ni instalación editable. Verifica base y cada extra, ejecuta
ejemplos, reconstruye el wheel desde el sdist y prueba el paquete instalado.
El benchmark se comprueba con ambos wheels fijados. La validación corresponde
a Windows x64/Python 3.12.4; no acredita la matriz de otras plataformas.
En total aprobaron **1.273 pruebas**. Las dos omitidas corresponden a controles
de rechazo de enlaces simbólicos: esta cuenta Windows no permite crearlos.
El inventario de fuentes de los tests se suministró explícitamente, separado
de las importaciones instaladas. Ambos verificadores de distribución finalizaron
con código 0.

Se corrigió el entorno de comprobación inicial del benchmark, que no tenía el
núcleo instalado, y se regeneraron los esquemas con el emisor actualizado.
Los controles finales utilizan los wheels/versiones declarados, sin atribuir
esas fallas de preparación al comportamiento del migrador.

## Propiedades ejercitadas

- Las tres parejas en ambas direcciones y llamadas reales a cada adaptador;
  proveedores resueltos una vez y buffers separados del consumidor.
- Esperado capturado antes de ETL; caso donde origen/destino coinciden pero
  ambos difieren del esperado. Sin esperado no se declara corrección independiente.
- NULL/NaN, lógica de tres estados, multiplicidad, joins many-to-many, grupos,
  sumas vacías, Decimal/moneda, tipos exactos, overflow y orden.
- Capacidades y dependencias rechazadas antes de ETL; date64 no transportable
  a Polars impide que Pandas ejecute primero. Índices significativos no se pierden.
- Cancelación, timeout total, opciones efectivas por hijo y límites que incluyen
  esperado y buffers de índice. Un fallo conserva resultados parciales.
- Perfil/M/B/H reutilizados sin aprendizaje durante migración ni contaminación
  por el esperado. R requerida por defecto u opcional explícitamente, con sus
  estados originales y alertas disponibles conservados.
- Integridad del inventario, journal y reportes; referencias externas rechazadas
  antes de decodificar; metadatos físicos y conteos de diferencias contrastados.
  Reescribir JSON y recalcular un hash no basta para ocultar una contradicción.
- IPC y Parquet: conteos/buffers físicos coherentes con independencia del tamaño
  de lote de comparación. Lectores sin reejecución de ETL.
- Publicación final fallida sin `migration.json` exitoso; inspección genérica
  reconoce operaciones finalizadas e interrumpidas; CLI distingue integridad
  de resultado semántico.

Una revisión independiente reprodujo y corrigió cuatro casos de compilación:
Sort→Project y Aggregate→Project eliminables por optimización DuckDB se rechazan;
Decimal extremo genera diagnóstico controlado; NUL dentro de un literal de texto
se conserva. Polars SUM usa una cota conservadora dependiente de datos, documentada
en la guía. Esas restricciones delimitan el soporte inicial.

## Artefactos

| Distribución | SHA-256 |
|---|---|
| Wheel núcleo 0.10.0 | `92879230e98873f6a569234dd84a12e9d92ee26438c6bcd85d8c31af407974f3` |
| Sdist núcleo 0.10.0 | `bad2b8583c6d06652129a649aecfb418b102146619312f05fd88e4c1a815f6c7` |
| Wheel benchmark 0.10.1 | `4fae0cbf61f6188108363e48e364dae3fafe704eb1d1ab4ece262530c684e7fc` |
| Sdist benchmark 0.10.1 | `8447220b123bcfb6738fef0a41d9ce99ad4aff0e743d33317583138de83e2815` |

Los artefactos se construyen localmente y se mantienen fuera de Git, junto con
capturas, resultados y documentación privada. La entrega del Word final está
verificada por separado en [la revisión del tutor](THESIS_TUTOR_REVIEW_20261003.md).

## Pendientes explícitos

La integración cliente/DW y el snapshot SERCOP reales aún no existen en este
entorno. El requisito de más de 10.000 registros reales de aprendizaje, las
etiquetas revisadas y la aceptación del tutor siguen pendientes. Las tres parejas
y tres familias principales se mantienen en la tesis; las cinco capacidades
genéricas de perfiles no añaden estratos científicos obligatorios.

La igualdad respecto a un esperado aportado no autentica su revisión humana.
La evidencia del migrador contiene URI locales y no es automáticamente portátil.
Los límites cooperativos no son cuotas duras ni aislamiento de plugins. El
registro de un motor no acredita compatibilidad semántica universal.

GitHub Actions permanece deshabilitado por cuota; los controles son locales.
No se publica en PyPI ni se inicia el paso 11. La preparación de wheels no
resuelve por sí sola licencia, titularidad del nombre o publicación pública.
