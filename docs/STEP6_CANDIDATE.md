# STEP6 — Estabilidad y compatibilidad del candidato

Cierre técnico: 2026-10-06. Candidato privado 0.11.1, identificado por commit y
hashes de artefactos. Este paso se conserva en la rama candidata; main queda
reservada para después de los pasos 6–10. No publica paquetes ni acredita
aceptación humana, certificación externa o ejecución de CI remota.

## Compromiso implementado

- [Clasificación y deprecación](COMPATIBILITY.md): inventario explícito de
  343 exports, 20 comandos y 55 esquemas, con API/CLI/formatos/evidencia separados
- Retirada estable: al menos dos releases minor y 90 días de aviso, ambas
  condiciones. Excepciones documentadas para rechazo de entradas inseguras,
  corruptas o capaces de producir falsa equivalencia. No hay nuevas deprecaciones
- [Adaptadores](ADAPTER_CAPABILITIES.md): captura, comparación, ejecución y
  migración diferenciadas; condiciones, pérdidas conocidas y mantenimiento
  individual sin asignar. Conformidad limitada al corpus propio identificado
- Fixtures históricas inmutables de contratos, estados, reportes, DiffContract,
  eventos, diferencias y expedientes portátiles, con productores de commits
  previos identificados. Se rechazan versiones futuras también anidadas
- Lectura verificada de environment.json exige formato 1.0; rehashear una versión
  futura no la vuelve compatible. Los lectores históricos utilizan resúmenes y
  verificadores HTML v1 congelados, conservando controles semánticos y de integridad
- Polars rechaza pérdida de dimensiones durante captura y conversión; no crea
  una salida completada tras perder filas. El test de ML verifica paridad con el
  sklearn instalado y rechazo de bosques sin splits, sin cambiar los algoritmos
- Python admitido por metadatos: >=3.12,<3.14. Locks ampliados para 3.13 sin cambiar
  versiones resueltas. La admisión no equivale a cada SO/arquitectura o combinación
  posible dentro de todos los rangos

## Método de verificación

Un único wheel se mantiene en todos los consumidores. Las celdas iniciales crean
venvs limpios fuera del checkout, resuelven pins con hashes desde los requisitos
del wheel y registran import/versiones/comandos/logs. Una corrección exclusiva
de colección de tests en el sdist y sus revalidaciones offline se identifican
por separado. La comprobación del payload instalado es por bytes; no se utilizan
imports editables en los consumidores de artefactos.

Perfiles: base, arrow, pandas, polars, duckdb, engines, ml y all. minimum utiliza
lowest-direct: mínimos directos mutuamente resolubles con ruedas binarias para
el intérprete y transitivas recientes compatibles. latest utiliza highest con
refresh dentro de los rangos del wheel. Las versiones resueltas y la fecha están
en cada recibo. No son todos los cruces ni las transitivas mínimas históricas.
Cada instalación parcial ejercita su corpus público/API/CLI y ejemplos nativos;
all añade la suite completa. Un skip/xfail no cuenta como conformidad aprobada.

## Controles finales

| Control | Núcleo | Benchmark |
|---|---:|---:|
| Etapas vinculadas a fuente/runtime | 9/9 | 9/9 |
| Suite completa de fuente | 2361 passed | 456 passed |
| Suite completa instalada | 2361 passed | 456 passed |
| Wheel reconstruido idéntico desde sdist | Sí | Sí |

Cero fallos, skips o xfails en estas suites finales. Hay 505 pruebas nuevas del
núcleo frente a STEP5; las repeticiones no son pruebas distintas. Las cuatro
combinaciones all ejecutaron 2361 tests cada una contra el sdist final, sin omisiones.
Consumidor técnico independiente: 81 comprobaciones públicas y 779 pruebas
focalizadas instaladas, con seis joins N:M/NULL, estados, Decimal, multiplicidad
y lectores históricos. Es una revisión técnica automatizada, no observación humana.

## Matriz local ejecutada

Debian 13/Linux x86_64, CPython 3.12.14 y 3.13.5. Las 32 de 32 celdas locales
solicitadas cuentan con recibos exitosos del mismo wheel. Los controles comenzaron
el 2026-10-05 y las 13 celdas restantes se completaron el 2026-10-06 tras la
continuación autorizada. Los intentos fallidos/interrumpidos se conservan.

| Python | Perfil | Mínimo directo | Reciente permitido |
|---|---|---|---|
| 3.12.14 | base | Aprobado | Aprobado |
| 3.12.14 | arrow | Aprobado | Aprobado |
| 3.12.14 | pandas | Aprobado | Aprobado |
| 3.12.14 | polars | Aprobado | Aprobado |
| 3.12.14 | duckdb | Aprobado | Aprobado |
| 3.12.14 | engines | Aprobado | Aprobado |
| 3.12.14 | ml | Aprobado | Aprobado |
| 3.12.14 | all | Aprobado | Aprobado |
| 3.13.5 | base | Aprobado | Aprobado |
| 3.13.5 | arrow | Aprobado | Aprobado |
| 3.13.5 | pandas | Aprobado | Aprobado |
| 3.13.5 | polars | Aprobado | Aprobado |
| 3.13.5 | duckdb | Aprobado | Aprobado |
| 3.13.5 | engines | Aprobado | Aprobado |
| 3.13.5 | ml | Aprobado | Aprobado |
| 3.13.5 | all | Aprobado | Aprobado |

### Dependencias de las cuatro suites completas

| Python/extremo | Pydantic | Typer | tzdata | Arrow | pandas | Polars | DuckDB | NumPy | sklearn |
|---|---|---|---|---|---|---|---|---|---|
| 3.12.14/minimum | 2.12.0 | 0.20.0 | 2025.2 | 20.0.0 | 2.2.2 | 1.30.0 | 1.5.6 | 2.0.0 | 1.7.0 |
| 3.12.14/latest | 2.13.5 | 0.27.2 | 2026.5 | 25.0.1 | 3.0.6 | 1.44.2 | 1.5.6 | 2.5.3 | 1.9.1 |
| 3.13.5/minimum | 2.12.0 | 0.20.0 | 2025.2 | 20.0.0 | 2.2.3 | 1.30.0 | 1.5.6 | 2.1.0 | 1.7.0 |
| 3.13.5/latest | 2.13.5 | 0.27.2 | 2026.5 | 25.0.1 | 3.0.6 | 1.44.2 | 1.5.6 | 2.5.3 | 1.9.1 |

Los locks completos incluyen hashes y transitivas. Python 3.12/pandas solo
resuelve un mínimo anterior al conjunto all; con NumPy 2/ML, el mínimo conjunto
requiere pandas 2.2.2. En 3.13, las ruedas disponibles elevan el mínimo a pandas
2.2.3/NumPy 2.1.0. No se anuncia el producto cartesiano de esta tabla.

### Consumidores del benchmark

| Python | Extremo del núcleo | packaging | psutil | Suite instalada |
|---|---|---|---|---:|
| 3.12.14 | minimum | 26.3 | 7.2.2 | 456 passed |
| 3.13.5 | minimum | 26.3 | 7.2.2 | 456 passed |
| 3.12.14 | latest | 26.3 | 7.2.2 | 456 passed |
| 3.13.5 | latest | 26.3 | 7.2.2 | 456 passed |
| 3.12.14 | minimum | 26.0 | 7.2.2 | 456 passed |
| 3.13.5 | minimum | 26.0 | 7.2.2 | 456 passed |

Los cuatro consumidores con packaging 26.3 siguen los extremos del núcleo y la
resolución reciente de herramientas. Los dos adicionales cubren el mínimo directo
propio packaging 26.0 en ambos Python; psutil 7.2.2 es exacto por metadata. Todos
mantienen los pins runtime del núcleo y verifican ambos wheels antes/después.
La metodología científica y la condición experimental del benchmark no cambian.

## Incidencias conservadas y recuperación

- Errores de conexión al índice oficial y cancelaciones del flujo de autorización
  interrumpieron los primeros intentos. Se preservaron recibos parciales, sin
  contar running/blocked como éxito. El usuario autorizó continuar las descargas
  en la nube el 2026-10-06; se cerraron las 13 celdas y el benchmark mínimo pendiente
- Una primera prueba benchmark tuvo 454 passed y dos skips porque faltaba el
  inventario read-only de ambos sdists en el harness. Se corrigió ese consumidor;
  las repeticiones aprobaron 456 sin skips y sin cambiar el artefacto
- Un selector de fixtures dependía del orden del sistema de archivos: produjo
  2324 casos en fuente/matriz y 2327 en el gate instalado. Se corrigió para recorrer
  ambos layouts ordenados e incluir explícitamente el índice pandas. Ahora son
  2361 en todos. Solo cambió ese test en el sdist; no el wheel, metadata, tooling,
  ejemplos ni fixtures. Cuatro consumidores verificados repitieron el sdist final
  offline, con bindings antes/después; los gates fuente/instalado también se repitieron
- El reinicio de la nube restauró un snapshot antiguo. Se recuperaron el checkpoint
  Library, parche binario y recibos originales; se verificaron los 1453 miembros,
  los 414 blobs del commit base y las huellas de fuente/artefactos. El snapshot
  antiguo se preservó separado. No se inventaron ejecuciones ni recibos históricos
- La comprobación de todas las transitivas mínimas no obtuvo una suite satisfactoria:
  Pygments 2.6.0 choca con pytest>=8.4 y el ensayo con pytest 8.3.5 encontró un fallo
  de six 1.5.0/Hypothesis y _gdbm en ese intérprete. No se anuncia esa combinación;
  el endpoint mínimo aprobado es lowest-direct, explícitamente documentado

## Artefactos privados y fuente

| Artefacto | Bytes | SHA-256 |
|---|---:|---|
| equiframe_benchmark-0.11.1-py3-none-any.whl | 104267 | `9a51e7cea5dc39df83ecb6d601af3a4e368a4c2e2a9bf1b3d4b1487bc74f12b5` |
| equiframe-0.11.1-py3-none-any.whl | 250809 | `6eae4f32b8dbd8a670ddbe4f645a1f6a41b741abb2e5e3afeb127c19a4f2b388` |
| equiframe-0.11.1.tar.gz | 742611 | `0e33f17c347998148f708563ae296c9f8e9bb783b7a0912235e4c3d7c28ef973` |
| equiframe_benchmark-0.11.1.tar.gz | 323547 | `345ac1a0a0714ee35f3eaeded00774049cf5f629974fe9ea661eacea026f1c18` |

El sdist final del núcleo incluye 21 fixtures Arrow sintéticas históricas mediante
una inclusión acotada; un inventario cerrado comprueba sus bytes. La primera
versión del sdist tenía SHA-256 4c20e6b0cf22ff6b5ad308ceb6513da0543d036fa434bec7e0d126af3339ecc2;
la diferencia final es exclusivamente el test de colección descrito arriba.

Huellas sha256-git-worktree-v1 comprobadas:

- Núcleo, 348 archivos: `9c45d59eaca02d94bc7b53403c0899973a1a4362f4056ca984be0779ae9b4823`
- Cierre benchmark + núcleo, 448 archivos: `5203928f99a50ff128afdb7154250e98506cc6d2d49460e02a97c2b704957d1c`

El commit/árbol exactos y el readback remoto se registran en la evidencia externa.
Los hashes prueban igualdad frente a estas referencias, no identidad autenticada,
firma de release ni ejecución de GitHub Actions. El número privado 0.11.1 por sí
solo no identifica un candidato; reinstale el wheel exacto en un entorno limpio.

## Límites y decisiones externas

Windows x64, macOS Intel/Apple Silicon y Linux ARM64 no tuvieron ejecutor:
128 celdas adicionales de la matriz prevista permanecen sin verificar. No son
skips aprobados ni evidencia de soporte. Python 3.11/3.14, PyPy, free-threaded,
32-bit y plataformas no ensayadas no se anuncian como probadas. La configuración
manual de Actions y resultados históricos no sustituyen jobs del SHA actual.

El kit de primer uso sigue dirigido a Python 3.12; la meta humana de cinco minutos
continúa pendiente. Licencia, publicación pública, propietarios de adaptadores,
integración DW/OCI y evaluación científica conservan gates separados. No se
atribuyen entregas a terceros ni se certifica externamente un motor.

THESIS_TRACEABILITY.md permanece byte a byte; la hoja de ruta reforzada no se
versiona. STEP7 no forma parte de este cierre y main no se modifica en STEP6.
