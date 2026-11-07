# Corte verificable para revisión independiente de A14

EquiFrame y benchmark siguen en **Alpha privada 0.12.0a14**. El núcleo, el
benchmark y `equiframe-data` se reconstruyeron en privado por autorización
explícita del propietario. TestPyPI continúa limitado a su configuración.
La revisión independiente comprueba este corte sin sustituir las entregas
pendientes del [10 % reservado](A14_TECHNICAL_90_METHOD_20261013.md).

## Resultados nuevos observados

- Núcleo instalado: **8.107 aprobadas, 25 omisiones de Windows, cero fallos**.
  Suite completa, 8.132 casos, 37 minutos y 13 segundos. Repite el candidato
  posterior a las correcciones de catálogo/fixtures del informe anterior.
- Benchmark instalado: **620 aprobadas, 7 omisiones, cero fallos**.
  Suite completa, 627 casos, 11 minutos y 24 segundos.
- Cliente/gateway actuales: **98 aprobadas, una omisión**. Incluye la nueva
  prueba que impide suplantar `safe_io` al ejecutar el extractor como fuente.
- Ejemplos extraídos de cuatro textos actuales: **ocho ensayos aprobados**,
  normal y `-O`. Se corrigió el registro documental que todavía exigía A13.
- Trazabilidad: **5.230 casos por modo**, normal y `-O`, todos con el esperado
  satisfecho. Vinculan **6.201 obligaciones de 8.438**; **2.237 siguen sin
  ejecución en este corte**. Se conserva el inventario original de 8.385 y se
  identifican 53 adiciones A14. Repeticiones no añaden obligaciones.
- Runtimes Windows nuevos: base mínima 3.10/3.11/3.13 y perfiles de motores,
  ML y recursos comprobados. Sus recibos delimitan cada entorno; no acreditan
  plataformas inaccesibles ni la matriz cartesiana completa.
- Los seis archivos wheel/sdist del núcleo, benchmark y cliente pasaron
  `twine check --strict`; comprobación de dependencias instalada satisfactoria.
  El auditor offline verificó el par núcleo/benchmark y conservó las puertas
  de publicación bloqueadas.
- El enlace de la tutora respondió 200 en índice, manifiesto e instrucciones.
  El manifiesto mantiene el SHA-256
  `712022f8470428f25fa12b307e301ad6ef6fb0f9c59634ab8b90569380ac279c`.
  Ambos servicios siguen activos y la copia antigua del home está ausente.

## Identidad de los artefactos privados reconstruidos

Los cuatro archivos siguientes se construyeron desde el código del commit
`835b9db4cabd1c4b89f72469d3fead41b2f5ad42`. No son los primeros archivos A14
ni los kits A9/A10; compartir versión no iguala bytes.

| Archivo | SHA-256 |
|---|---|
| equiframe-0.12.0a14-py3-none-any.whl | `620c217c644e41d1220ed9c78f43777a886cfefaa3d52f4e24160e1612a98b75` |
| equiframe-0.12.0a14.tar.gz | `0f46af4d4387cf5554714b78f76529c9b153848649a3af3f5f889ba22d29809d` |
| equiframe_benchmark-0.12.0a14-py3-none-any.whl | `ec03d68ca3c7660a4cca4e868760305e0d0f71fd9f32783bb4555921f0b6ef3c` |
| equiframe_benchmark-0.12.0a14.tar.gz | `9351555589f0f855fc0e3ade2a8bd2dce904d5f53c5d256e45ec4ea43cb1379a` |

La evidencia privada está en `a14_revalidation_20261013`, fuera del repositorio.
Los archivos principales son `core-installed-full-v1.xml`,
`benchmark-installed-full-v1.xml`, `data-gateway-current-v1.xml`,
`trace-artifact-normal-v1/result.json`,
`trace-artifact-optimized-v1/result.json`,
`documentation-examples-v1/examples.json`,
`pypi-preparation-manifest-v1.json` y `pypi-preparation-packet-v1.json`.
Los hashes anteriores identifican distribuciones; no autentican por sí mismos
los recibos ni a sus revisores.

## Trabajo que sigue activo

El propietario pidió preparar el corpus/particiones/verificador y fichas
humanas del experimento sobre SERCOP. Es trabajo en curso. Todavía no hay
etiquetas humanas confirmadas, normalidad aprobada, `N_fit > 10.000`
acreditado por modelo/familia, DW/servicio aceptados ni resultados científicos
aprobados. El Word sigue intacto.

**No se acredita aún el 90 % en todos los rubros.** La matriz histórica y el
método prospectivo se conservan. Hay obligaciones técnicas pendientes además
de las entregas humanas. No se utilizó Codex Security ni se delegó a agentes.
No se ejecutaron Actions ni publicación en PyPI/TestPyPI.
