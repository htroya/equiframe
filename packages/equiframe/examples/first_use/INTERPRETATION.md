# Interpretar antes de aceptar

## Tres estados, más completitud y evidencia

- **equivalent:** comparación completa sin diferencias bajo el contrato
  declarado y los datos capturados. No demuestra corrección de negocio,
  independencia del esperado ni equivalencia universal de programas
- **different:** comparación completa con diferencias o incumplimientos.
  Localice clave/posición, columna, ambos valores y tipos, política y razón
- **not_evaluable:** no puede emitirse el juicio requerido. Puede haber diferencias
  ya observadas. `complete=False` indica recorrido incompleto, pero una referencia
  inválida puede producir este estado aun con `complete=True`

No deduzca éxito de `complete`, ausencia de ejemplos, ausencia de anomalías,
objeto retornado, exportación válida ni salida 0 de un lector de evidencia.
`ef.assert_equivalent` es el gate; `ef.equivalence_decision(result).accepted`
es la decisión explícita. Reporte y evidencia tienen además aceptación propia.

## Diagnóstico mínimo correcto del refactor

B / total_cents: 2001 frente a 2000, enteros de 64 bits y política exacta en
centavos USD. El defecto es un centavo añadido; el reordenamiento no importa
porque el contrato ignora orden y valida clave única. Relajar tipos o tolerancia
para ocultar ese centavo cambiaría el requisito, no corregiría el refactor.
Sin clave no hay identidad: el reporte conserva multiplicidad y muestra
ocurrencias sobrantes; no puede afirmar cuál fila de negocio se modificó.

## Semántica que no se debe borrar

- Una clave duplicada no se resuelve tomando «la primera»; invalida la identidad
- El número de registros de diagnóstico no equivale necesariamente a filas
- Decimal conserva precisión/escala; entero no se convierte a float para coincidir
- NULL, NaN, vacío y cero no son intercambiables sin política explícita
- Una suma de un grupo de NULL debe conservar `empty_sum` declarado; cero puede
  ser un error aunque dos motores coincidan en cero
- Índices significativos, orden y multiplicidad requieren política, no limpieza
  implícita. El RangeIndex trivial de la receta no representa identidad
- Conteos parciales son cotas, no totales. Ejemplos limitados no reducen recorrido
- R/M/B/H y anomalías son señales separadas, no evidencia de equivalencia ni O

La puerta técnica de entrega ejecuta estas recetas, el corpus semántico del
núcleo y la suite instalada. Los tests sintéticos no sustituyen datos reales,
revisión humana, servicio/DW, certificación de plataforma ni estudio científico.

## Evidencia mínima y retención

Los scripts generan exclusivamente datos sintéticos. Refactor muestra valores
por defecto para que pueda aprender a localizar el fallo; las otras dos recetas
redactan por defecto. Un reporte filtrado no borra originales. Por defecto los
scripts crean capturas temporales, exportan su reporte y eliminan esas capturas
al terminar. Con `--work-dir` retiene originales bajo su responsabilidad.
El reporte sigue legible después de limpiar originales o cerrar el motor,
pero no se puede reproducir toda la transformación a partir de una vista mínima.

Mantenga el artefacto CI pequeño y con inventario cerrado. Hashes verifican
consistencia, no autoría. No comparta muestras sensibles solo porque exista un
manifiesto. Revise autorización, nombres, claves, rutas y valores antes de activar
`include_values`/`include_metadata` sobre datos reales.

## Comprobación de comprensión

Explique con sus palabras por qué falla B; por qué la migración puede coincidir
entre motores y fallar frente al esperado; por qué `not_evaluable` no es un pase;
y cómo guardaría el reporte antes de fallar sin subir las capturas privadas.
Registre respuesta, tiempo y ayuda observados en `OBSERVATION.md`.
