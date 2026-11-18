# Tres perfiles ficticios para ensayar el protocolo

[Protocolo de adopción](adoption.md) · [Arquitecto](arquitecto.md) · [Científico](cientifico.md)

**SIMULADO.** Hernán autorizó preparar perfiles ficticios. No representan personas,
empresas o proyectos reales; no tienen consentimiento otorgado ni observaciones
humanas. No se introducen en el registro de pilotos como `human_pilot` y no suman
al índice U12. No se fabrican firmas, independencia, tiempos o satisfacción.

## Perfil ficticio A: arquitectura e integración SQL

- Rol ficticio: arquitecta de datos que integra una comprobación en un orquestador existente
- Proyecto simulado: comparar una consulta DuckDB de inventario sintético con un
  esperado literal por SKU, conservando clave compuesta y unidades
- Ruta: guía del arquitecto, captura propia SQL, reporte y aserción; ampliar con
  el recorrido G para fijación de snapshot local
- Decisiones a ensayar: elegir `[duckdb]`, distinguir snapshot fijado de servicio
  real, localizar B=21 frente a B=20 y detener el siguiente paso
- Escenario de seguimiento propuesto: una consulta posterior añade un filtro;
  el control debe permanecer. No se afirma que ese cambio haya ocurrido

## Perfil ficticio B: ciencia de datos y preparación

- Rol ficticio: científico de datos que conserva identidad y tiempo al preparar features
- Proyecto simulado: dataset sintético de tres muestras con IDs, Decimal y NULL
- Ruta: guía del científico; primero `good`, luego desplazamiento temporal,
  pérdida de fila y ausencia reemplazada por cero
- Decisiones a ensayar: interpretar la diferencia y la consecuencia en ventanas,
  cobertura y joins; mantener el esperado independiente y las ausencias
- Escenario de seguimiento propuesto: una revisión vectoriza la preparación sin
  cambiar semántica. No hay modelo entrenado ni utilidad científica observada

## Perfil ficticio C: mantenimiento de una regresión CI

- Rol ficticio: ingeniera que mantiene pruebas de regresión Python de un proyecto
- Proyecto simulado: comprobar totales sintéticos después de un refactor,
  conservar el reporte aunque falle pytest y mantener el retorno no cero
- Ruta: test local de la guía del arquitecto y recorrido A/H
- Decisiones a ensayar: distinguir cero del arnés que espera fallos del gate que
  acepta datos; usar carpeta nueva y separar una salida completa de equivalencia
- Escenario de seguimiento propuesto: otro commit cambia el cálculo; el test y
  diagnóstico siguen disponibles. No se ejecuta ni acredita CI remota

## Hoja vacía de ensayo, sin resultados humanos

Antes de ensayar, anotar guía/artefactos, propósito y escenario. Si se ejecutan
comandos, registrarlos como reproducción técnica sintética con sus resultados
reales. El tiempo automático solo mide comandos; no mide comprensión humana.
No llenar el consentimiento ni la independencia con valores ficticios positivos.

Para pasar de estos perfiles a U12 se requieren personas y proyectos reales,
consentimiento con alcance/lectores/retención, revisión humana de independencia,
interpretación y ayuda observadas, tres diagnósticos iniciales <=300 s con reloj
predeclarado e integración retenida tras un cambio real posterior. Todo ello
permanece pendiente. El permiso de ensayar perfiles no es permiso de contactar
personas, compartir datos o publicar resultados.
