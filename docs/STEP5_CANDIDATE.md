# STEP5: tres recetas y primer uso

Fecha: 2026-10-05. Candidato privado 0.11.1. Base:
[`7b60992826ba2c97b386e4ce15a98662f13ed42f`](https://github.com/htroya/equiframe/commit/7b60992826ba2c97b386e4ce15a98662f13ed42f).

## Entrega

- [Inicio rápido autocontenido](../packages/equiframe/examples/first_use/README.md)
- Refactor pandas: clave explícita, entero exacto, valor/tipo/política localizables,
  corrección y extensión de multiconjunto sin inventar identidad
- Migración nativa pandas → DuckDB con IR acotado, entrada común y esperado
  literal separado; Decimal exacto, NULL, cero, multiplicidad y contexto fijados
- Receta pytest/CI existente incorporada al kit con reporte redactado finalizado
  antes del fallo; diferencias y no evaluabilidad conservan fallos reales
- Kit privado verificable con wheel identificado, pins/hashes del lock y cuatro
  scripts; no checkout, datos externos ni descargas ocultas
- [Interpretación](../packages/equiframe/examples/first_use/INTERPRETATION.md) y
  [protocolo de observación](../packages/equiframe/examples/first_use/OBSERVATION.md)

## Puertas de validación técnica

Verificación técnica local completada en Linux x86_64/Python 3.12.14.
Locks, versiones y Python soportado permanecen intactos.

| Etapa | Núcleo | Benchmark |
|---|---:|---:|
| Sync bloqueado con todos los extras | Aprobado | Aprobado |
| Ruff check / format | Aprobados | Aprobados |
| mypy estricto | Aprobado | Aprobado |
| Assets en modo check | Aprobado | Aprobado |
| Suite completa sobre fuente | 1856 passed | 456 passed |
| Build sin aislamiento | Aprobado | Aprobado |
| Twine estricto wheel/sdist | Aprobado | Aprobado |
| Consumidores externos y distribución | Aprobado | Aprobado |
| Suite instalada desde distribución | 1856 passed | 456 passed |

Nueve etapas por paquete, cero fallos y omisiones en estas ejecuciones finales.
Hay 60 pruebas nuevas del núcleo. Las repeticiones instaladas no duplican
el número de pruebas distintas. Ambos wheels se reconstruyeron byte a byte desde
sus sdists. El gate del kit instala 24 dependencias fijadas con hashes, verifica
el import/payload del wheel y ejecuta clave/bolsa, las tres rutas migradas y
script/pytest CI con sus códigos/reporte esperados, manteniendo el kit intacto.

Un primer recorrido de fuente pasó 1855 pruebas, pero un ajuste de diagnóstico
introducido durante esa ejecución hizo que el guard de fuente lo rechazara.
Ese recibo fue descartado como validación final; se repitieron las nueve etapas
sobre la fuente congelada, incluida la regresión del ajuste.

### Bytes de fuente comprobados

Algoritmo `sha256-git-worktree-v1`:

- Núcleo, 224 archivos: `f02332e9468d4d5ec13bd4768904fa7e6026f1ad4aa60d31576af3861aa68632`
- Cierre benchmark + núcleo, 324 archivos: `e39ffa72788e2ddeb0ab5f928179a42d3307b50b9a2f25794a4858f3aa0f2669`

### Artefactos privados comprobados

| Archivo | Bytes | SHA-256 |
|---|---:|---|
| equiframe-0.11.1-py3-none-any.whl | 231462 | `056f6d90a627b10a43ab99bbe24c59b4c6211b102d136887706a46b0b4b1ebbc` |
| equiframe-0.11.1.tar.gz | 622891 | `d6f6949e58130188a9858226d65324688cc6cf2e50c20676df174389d56c5291` |
| equiframe_benchmark-0.11.1-py3-none-any.whl | 104148 | `69757c679cc05c2c9dd43f7572deb0a76ef8a8c2f32d815edd1f32024334e2ac` |
| equiframe_benchmark-0.11.1.tar.gz | 310085 | `f8bbc7ea430c4f28861a3fca5e74857be18a1804bb17abd933d62ca0cced0da3` |

Los recibos finales separados vinculan esos controles y artefactos al commit
limpio de la rama candidata y al consumidor técnico independiente. No son firmas ni evidencia
de una sesión humana o un job remoto. El ZIP de entrega conserva kit ejecutable,
logs seguros, inventario y recibos, sin notas internas ni capturas privadas.

## Corpus mínimo de seguridad semántica

La suite de primer uso exige clave única y completa, multiplicidad sin clave,
cambio de tipo sin coerción, entero exacto, Decimal de gran magnitud/escala,
NULL frente a cero, presupuesto insuficiente, esperado inválido aun completo,
truth testing rechazado y evidencia publicada antes de fallar. El caso migrado
comprueba acuerdo entre motores separado de cumplimiento frente al esperado.
Se ejecuta además toda la suite semántica existente del núcleo; las recetas no
reemplazan cobertura previa ni acreditan todas las combinaciones de tipos/motores.

## Aceptación humana pendiente

**La meta de un diagnóstico en cinco minutos permanece sin validar.**
No se realizó ni se inventa una sesión de una persona nueva. La prueba del
consumidor técnico independiente usa la guía y el artefacto instalado; no es un
participante humano ni una medición de usabilidad. El registro entregado conserva
pendientes tiempo, ayuda recibida, errores, plataforma y comprensión de estados.
Corregir bloqueos observados antes de ampliar el catálogo sigue siendo requisito.

## Límites

No cambia el comparador, API ni semántica IR. No se entrega un traductor arbitrario
ni entrada directa de relación DuckDB. Los ejemplos prueban capturas concretas,
no equivalencia universal, corrección de negocio o independencia científica.
Los reportes mínimos no reproducen toda transformación y los originales son
privados/temporales salvo retención explícita. Los hashes no autentican autores.

Se conserva Python 3.12 y locks; no se amplía matriz, licencia, PyPI, infraestructura,
servicio/DW o protocolo experimental. La CI remota se consulta para el SHA exacto;
controles locales no se presentan como jobs remotos. La hoja de ruta reforzada no
se versiona y `THESIS_TRACEABILITY.md` permanece byte a byte por instrucción.

## Integración diferida por la secuencia solicitada

La última instrucción del usuario exige completar los pasos 5, 6, 7, 8, 9 y 10
secuencialmente y subir el conjunto a main al final. STEP5 se conserva como
commit inmutable en la rama candidata y PR borrador; este documento no acredita
pasos posteriores ni integración a main. El recibo externo identifica SHA y
árbol exactos, kit, controles y el estado observado de la rama remota.
