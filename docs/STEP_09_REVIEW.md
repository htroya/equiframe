# Verificación técnica del paso 9 y dependencias externas

Fecha: 2026-10-02. Núcleo 0.8.1; benchmark 0.9.0.
El paso 8 se confirmó previamente en el PR #18, con la matriz CI completa.
Hernán confirmó la ausencia de las entregas de José/Jhair y autorizó continuar
EquiFrame. El alcance aceptable actual es software consumidor y conformidad
local; no se declara cerrado el recorrido real del DW.

## Implementación y controles de comportamiento

- Recibos estrictos e inmutables y consumidor compatible con `DataSource`,
  cliente inyectado, subconjunto de tablas y snapshot fijado una vez.
- Identidad/revisión, tamaños/hashes, filas y tipos comprobados antes de cargar;
  errores de transporte, cancelación y presupuestos explícitos.
- Tres ejecuciones nativas independientes; comparaciones principales/adicional,
  esperado fijado una vez, evidencia y verificación sin contactar al servicio.
- Reconciliación configurable de grano/importes/monedas/puente, decimal exacto,
  ausencias visibles y diferencias que conservan totales.
- API y CLI de integración, esquemas públicos y ejemplo sintético instalable.

El [diseño](STEP_09_DESIGN.md) registra decisiones y límites. Las pruebas no
usan datos reales ni identidades de revisores ficticios como aprobación. Las
reglas que detectan un tipo nativo incompatible mantienen su alerta; aceptar
una comparación lossless explícita no cambia el contrato ni R.

## Controles ejecutados

Verificación local en Windows x64, Python 3.12.4 y dependencias exactas del lock:

- Ruff y formato: 32 archivos; mypy estricto: 18 archivos de fuente/herramientas.
- 18 esquemas comprobados; lock verificado offline.
- **156 pruebas aprobadas** contra wheel instalado fuera del checkout (238,14 s).
  Incluyen 25 de snapshots, 24 de integración, 7 CLI y 12 de conciliación.
- Imports ligeros, `pip check`, piloto nativo y ejemplo de integración instalados;
  reconstrucción desde sdist con identidad de todos los bytes del wheel.
- El ejemplo obtiene USD 30,75/EUR 7,00 y seis comparaciones equivalentes,
  conservando R.Pandas en alerta/incompleto por el tipo decimal nativo. La
  integración devuelve `complete=false` y código 3; su comprobación de
  expectativas devuelve 0. No se oculta esa incompatibilidad del contrato.
- El piloto mantiene cinco escenarios, 35 candidatos, 15 perfiles, cuatro
  grupos, **cero etiquetas confirmadas y 35 pendientes**. No se ajustó un modelo.

Dos intentos previos se detuvieron tras 146 pruebas aprobadas por controles
temporales de Hypothesis (generación lenta y deadline variable). La estrategia
está acotada a 15 máscaras de siete bits; se desacopló únicamente el tiempo
del host, conservando todos los casos y aserciones sobre fuga/invariancia.
La suite instalada completa posterior y el verificador terminaron con código 0.

Registro local ignorado: `packages/equiframe-benchmark/.cache/step9-distribution.log`.
SHA-256 de las distribuciones verificadas:

| Artefacto | SHA-256 |
|---|---|
| Wheel 0.9.0 | `7dd0e6839a73ffe95678d86921a9e9492630ce1d6d906f909e01b1a6a372164f` |
| Sdist 0.9.0 | `d474b4b8c9c9e9f510b69dea48684bedae8a241b2af67edcde615a03e223864d` |

La matriz remota de cinco plataformas deberá vincularse al commit entregado;
la verificación local no se presenta como aprobación de OCI ni como resultado
de runners que todavía no terminaron.

## Pendientes para la aceptación real

Cliente y accesos de José, snapshot SERCOP original/versionado, DDL y mapeos de
Jhair, expected y políticas revisados, entorno OCI disponible y comprobaciones
de coordinación del servicio. No se recibió ni se implementó ese material.
La construcción de un wheel o un piloto local no acredita integración real,
publicación del DW, cohortes válidas, métricas científicas ni PyPI.
