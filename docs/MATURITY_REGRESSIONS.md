# Regresiones de compatibilidad y formatos

Los fallos observados se conservan en el expediente; no se han retirado tests o perfiles para elevar el resultado.

| Riesgo observado | Corrección | Esperado independiente / regresión |
|---|---|---|
| Sintaxis PEP 695 y tipos posteriores a 3.10 | TypeVar y TypeAliasType de typing_extensions | Importación real, introspección de alias, validación de modelos y suite semántica |
| localcontext(capitals=...) no disponible en 3.10 | Asignar capitals dentro del contexto local | Decimal exacto, contexto del consumidor inalterado, sin reducción de precisión |
| ISO temporal con Z/fracciones en fromisoformat 3.10 | Parseo compatible para validar calendario y offset, preservando literal y nanosegundos | Nueve longitudes de fracción, fecha bisiesta, offset desconocido y fechas inválidas |
| Path.is_junction no disponible en 3.10/3.11 | Inspección del reparse tag en Windows | Contrato de tags, errores propagados, sin fallback universal False; ejecución Windows real sigue pendiente |
| Arneses fijaban Python 3.12 o el objetivo mypy 3.10 en entornos más nuevos | Propagar y consultar el intérprete real, seleccionar el objetivo de tipos correspondiente | Ocho casos del gate completo y seis del consumidor instalado; --strict y alcance completo preservados |
| Recetas de primer uso retenían identidad/locks antiguos | Recetas y locks por minor, resolución normal | Recorridos instalados, casos positivos y rechazos 1/3, pytest negativos |
| Recibo consumidor atribuía un commit A7 constante | Usar metadatos reales del paquete y digest RECORD; vincular commit/artefactos desde el manifiesto externo | No atribuir origen Git desconocido a una instalación nueva |

## Cambio de esquemas por productor a8

El archivo de evidencia schema-delta.json compara estructuralmente los JSON anteriores y nuevos. Las seis diferencias son la ampliación del enum de productor con 0.12.0a8 y el default de productor de esta versión. No cambian los campos, estados, restricciones o versiones de formato que leen los consumidores. Los productores históricos siguen admitidos y sus fixtures permanecen inmutables.

No se ajustaron resultados semánticos para ocultar una ruptura. La huella del esquema debe cambiar cuando cambia el enum/default de productor; la explicación de ese cambio acompaña los hashes. Las pruebas de lectura de formatos históricos y rechazo de versiones desconocidas siguen activas.

## Alcance de reutilización

Un pase de un commit anterior no se transfiere por nombre de versión. Para cualquier prueba reutilizada se compara el payload exacto afectado y se conserva el recibo original con su candidato. Las correcciones exclusivamente de herramientas/pruebas cambian el sdist aunque el wheel de runtime permanezca idéntico. Los artefactos preliminares están separados de los que se congelen para la entrega final.
