# Changelog

## 0.1.0 — 2026-09-28

- Primera API pública del paso 1: contratos semánticos estrictos, inmutables y versionados.
- Validación cruzada de esquemas, claves, tipos, políticas, intervalos y reglas declarativas.
- JSON canónico, SHA-256 de metadatos y esquemas JSON generados.
- CLI `equiframe contract validate`, con errores localizables y salidas documentadas.
- Fixtures sintéticos para cinco familias, pruebas por propiedades y distribución tipada.
- Bloqueo reproducible de desarrollo/ejecución y controles Windows/Ubuntu, Python 3.12 x64.
- Segunda revisión: hash independiente del contexto decimal, base IANA bloqueada,
  unidades/tipos coherentes en reglas y literales float32 exactos sin pérdida.
- Diagnósticos temporales y JSON duplicado específicos/localizables/imprimibles;
  errores de rutas inválidas y validación estricta de sintaxis de URI.
- Verificación ampliada de distribución: API/errores CLI instalada, consumidor
  mypy y batería completa contra wheel reconstruido desde sdist.

No incluye ejecución de reglas, adaptadores, comparador, modelos ni benchmark.
Los formatos del paso 1 usan `schema_version="1.0"`; cambios incompatibles requieren
nueva versión de esquema y migración expresa. No se hace migración automática.
