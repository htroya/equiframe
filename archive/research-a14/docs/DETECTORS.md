# Detectores M B y decisión híbrida

Disponible en `equiframe 0.7.0`, Python 3.12. M es Isolation Forest; B es MAD
sin factor de escala; H combina exclusivamente R y M. Las anomalías no
confirman divergencias: esa decisión corresponde al oráculo independiente.

## Instalación y ejemplo ejecutable

Desde `packages/equiframe`:

```bash
python -m pip install ".[ml]"
python examples/detectors_local.py --bundle detectors.json
python examples/detectors_local.py --bundle detectors.json --restore-only
```

Un consumidor con los wheels del equipo ya construidos puede instalar por nombre:

```bash
python -m pip install --find-links /ruta/a/wheels "equiframe[ml]==0.7.0"
```

`ml` incluye sklearn/NumPy para ajustar M. El paquete base lee y aplica bundles
declarativos sin ML ni motores. Obtener perfiles de capturas requiere además
`arrow` o un extra de motor; para ambas tareas, use `.[ml,engines]`.
El ejemplo usa perfiles sintéticos, no demuestra normalidad ni utilidad en SERCOP.
La distribución pública `pip install equiframe` sigue pendiente de licencia,
control del nombre y publicación verificable en PyPI.

## Ajuste calibración e inferencia

El benchmark proporciona selecciones normales revisadas con procedencia
verificada. Un consumidor externo es responsable de acreditar normalidad y
evitar fuga. Sobre objetos ya obtenidos de una sola familia:

```python
import equiframe as ef

fit = ef.fit_detectors(
    training,  # NormalTrainingProfiles
    spec=spec,
    config=ef.IsolationForestConfig(random_state=7),
    support=ef.DetectorSupport(
        min_training_rows=20,
        min_calibration_rows=10,
        rationale="Mínimos técnicos de este ejemplo; revisar con el piloto",
    ),
)
bundle = ef.calibrate_detectors(fit, calibration, alpha="0.05")
result = ef.detect(bundle, profiles_to_score)
hybrid = ef.combine_decisions(rule_evaluation, result.m[0].result)
```

Los mínimos y alpha del ejemplo no fijan el protocolo de tesis. La semilla
es obligatoria; 200 árboles y submuestra máxima 256 son el arranque revisable
de §3.6. Se registra la submuestra efectiva. `fit_detectors` ajusta las medianas
una sola vez; ambos métodos usan las mismas columnas, indicadores, filas y hash
de matriz. `score_detectors` entrega scores sin umbrales; `detect` usa los
umbrales del bundle. Ninguna operación de inferencia reajusta parámetros.

M exporta árboles de sklearn y calcula `-score_samples`; mayor significa más
anomalía. Convierte features a float32, como sklearn, rechazando desbordamiento
y declarando no estimable si desaparece toda la variación. Si la tolerancia
numérica del árbol impide cualquier división, M informa `no_isolation_splits`.
B usa los valores
originales de la misma matriz: mediana, MAD sin escala y máximo de desviaciones
normalizadas. MAD=0 aporta 0 si el valor coincide y `"+infinity"` en otro caso.
Un desbordamiento de un cociente finito produce error, no se disfraza de MAD cero.

Alpha es una cadena decimal entre 0 y 1, hasta 18 decimales. Se calcula exactamente
`k = ceil((1-alpha)*n)` con fracciones; el umbral es la posición k ordenada desde
uno, sin interpolación. Solo `score > threshold` alerta. Se guardan scores de
calibración, n, k, alpha, umbral y hashes.

| Situación | Resultado |
|---|---|
| Ajuste insuficiente, sin variables o sin variación | M/B no estimables, razón explícita |
| Perfil fallido, familia, versión u orden incompatibles | Excepción; sin decisión ficticia |
| Calibración insuficiente | No estimable; inferencia conserva score si existe |
| Umbral MAD infinito | B no estimable, aunque M pueda estar listo |
| Score MAD infinito y umbral finito | Alerta |
| Score igual al umbral | No alerta |

Las filas no equivalen a grupos independientes; repetir motores, variantes o
semillas no aumenta independencia. Alpha configurado no demuestra control
poblacional de falsas alarmas.

## Tabla de H

| R | M | H |
|---|---|---|
| alerta | alerta | alerta |
| alerta | no alerta | alerta |
| alerta | no evaluable | alerta parcial |
| no alerta | alerta | alerta |
| no alerta | no alerta | no alerta |
| no alerta | no evaluable | no evaluable |
| no evaluable | alerta | alerta parcial |
| no evaluable | no alerta | no evaluable |
| no evaluable | no evaluable | no evaluable |

`complete` exige ambos componentes completos. Una alerta de R con otras reglas
no evaluables también se conserva como parcial. `combine_decisions` acepta
`RuleEvaluation` o `ComponentDecision` para R. El llamador debe asociar R y M
a la misma ejecución; el manifiesto de esa asociación se integra en el paso 8.
B no interviene en H.

## Persistencia y límites

```python
from pathlib import Path

fingerprint = ef.write_detector_bundle(bundle, Path("detectors.json"))
restored = ef.read_detector_bundle(Path("detectors.json"), expected_sha256=fingerprint)
assert ef.detect(bundle, profiles_to_score) == ef.detect(restored, profiles_to_score)
```

El hash identifica JSON semántico canónico, no bytes/espaciado del archivo;
debe conservarse en un manifiesto externo confiable. No demuestra autoría.
Publicación exclusiva: una ruta existente da error. Lectura/escritura hasta
64 MiB; validación de claves duplicadas, versiones, dimensiones, topología,
muestras y cuantiles. No se carga pickle/joblib ni se reconstruyen objetos
sklearn. Se registran versiones del productor; la inferencia usa el formato
`equiframe-if-mad-1.0`, sin requerir sklearn. Otro entorno de entrenamiento
puede producir otro ajuste; no se promete identidad binaria entre plataformas.

El evaluador JSON prioriza transporte declarativo verificable. Sus tiempos/RSS
se medirán en el paso 10 sin asumir rendimiento idéntico a sklearn. Reportes
integrados, congelación final y validación SERCOP permanecen en sus pasos.
