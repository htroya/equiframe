# STEP4: aserciones e integración con pruebas/pipelines

Fecha: 2026-10-05. Candidato privado 0.11.1. Base:
[`511fb2627c7b1d968cae96c0b63f566cd790c640`](https://github.com/htroya/equiframe/commit/511fb2627c7b1d968cae96c0b63f566cd790c640).

## Entrega

- `assert_equivalent` y decisión versionada sobre resultados completos y consistentes
- Política de garantía observada, hashes/referencia fijables y persistencia explícita
- Tipos/códigos de diferencia, no evaluabilidad, configuración, garantía y evidencia
- Cambio documentado: resultados no tienen valor booleano; consumidores migrados
- CLI existente con códigos conservados, stdout JSON y diagnósticos stderr seguros
- Recetas de pytest y artefacto CI redactado, con reporte finalizado antes del fallo
- Comparaciones de salidas sintéticas materializadas Arrow/pandas/Polars/SQL
- Dependencias locales reinstaladas y bytes runtime vinculados a cada etapa

[Uso, privacidad y migración](ASSERTIONS.md) ·
[Decisiones A139–A143](DECISIONS.md#aserciones-e-integración-step4--2026-10-05)

## Verificación

Verificación técnica local completada en Linux x86_64/Python 3.12.14.
Se conservaron locks, rangos y versiones del candidato anterior. La revisión
independiente del código no encontró bloqueos; no sustituye revisión humana del
equipo ni aceptación científica. El inventario final se verifica antes del merge.

| Etapa | Núcleo | Benchmark |
|---|---:|---:|
| Sync bloqueado con todos los extras | Aprobado | Aprobado |
| Ruff check / format | Aprobados | Aprobados |
| mypy estricto | Aprobado | Aprobado |
| Assets en modo check | Aprobado | Aprobado |
| Suite completa sobre fuente | 1796 passed | 456 passed |
| Build sin aislamiento | Aprobado | Aprobado |
| Twine estricto wheel/sdist | Aprobado | Aprobado |
| Consumidores externos y distribución | Aprobado | Aprobado |
| Suite instalada desde distribución | 1796 passed | 456 passed |

Son nueve etapas por paquete, cero fallos y cero omisiones. Hay
193 pruebas nuevas del núcleo: 170 sobre aserciones, recetas,
CLI y truth testing, y 23 sobre vinculación runtime de
dependencias locales. La repetición instalada no duplica el número de
pruebas distintas. Las comprobaciones de presencia de comparaciones en el
benchmark conservan su comportamiento explícito.

Los consumidores verifican imports ligeros, API/CLI, typing, extras separados,
aserciones y evidencia persistida desde la base instalada sin motores. La receta
se ejecuta en Arrow, pandas, Polars y SQL DuckDB con esperado independiente;
comprueba códigos 0/1/3 en script. Pytest real comprueba éxito y los dos fallos
con códigos 0/1/1, conservando el reporte redactado finalizado antes de fallar.
El inventario autorizado contiene solo JSON/texto/HTML y su manifiesto. Ambos
wheels se reconstruyeron idénticos byte a byte desde sus sdists.

### Bytes de fuente comprobados

Algoritmo `sha256-git-worktree-v1`:

- Núcleo, 212 archivos: `35a524b393a74d6ca1c1df361a96fae126e51224aab146310e6728132197563e`
- Cierre benchmark + núcleo, 312 archivos: `447c2eeca81403b49639f01e16379a549347180a2980c68240301232d9f75622`

### Artefactos privados comprobados

| Archivo | Bytes | SHA-256 |
|---|---:|---|
| equiframe-0.11.1-py3-none-any.whl | 231098 | `6246596a2826665d8eb7623b2fe92e255886daa1ca6e5bb4fbc44cc192706a16` |
| equiframe-0.11.1.tar.gz | 590125 | `8bafc40d2180a88d3b0c121a84fce082724a25dc92bc82ba57d28f10d3980ebe` |
| equiframe_benchmark-0.11.1-py3-none-any.whl | 104148 | `69757c679cc05c2c9dd43f7572deb0a76ef8a8c2f32d815edd1f32024334e2ac` |
| equiframe_benchmark-0.11.1.tar.gz | 310085 | `f8bbc7ea430c4f28861a3fca5e74857be18a1804bb17abd933d62ca0cced0da3` |

Los recibos externos conservan comandos, fechas, cwd, exit codes y huellas
antes/después. Los manifiestos finales se vinculan al commit limpio de main y a
los artefactos después del merge, evitando una referencia circular. No son una
firma ni evidencia de CI remota.

## Límites confirmados

La equivalencia es observada dentro del contrato, no una prueba universal de
programas, corrección de negocio, independencia del esperado o aceptación
científica. La integridad comprueba consistencia con el manifiesto, no identidad
del productor. Persistencia de manifiesto/diferencias no implica reproducción
completa de transformaciones ni publicación remota.

El escenario de CI se ejecuta localmente con procesos de pytest y artefactos
reales redactados. El ejemplo de upload exige verificación de inventario
finalizado y usa una lista cerrada antes de compartir. La publicación en un job
GitHub Actions remoto real sigue pendiente: el conector disponible no permite
dispatch. Se consultan por separado los runs, checks y statuses de los SHA
exactos vía lectura autorizada de GitHub. No se acredita la matriz remota a
partir de controles locales. No se cambian triggers, permisos, credenciales o cuota.

Se conserva Python 3.12; no se amplía soporte de plataformas/versiones ni se
modifican dependencias, licencia, publicación PyPI, despliegue, protocolo
experimental o componentes de José/Jhair. No se implementan pasos 5–10.
La hoja de ruta original permanece fuera de Git y `THESIS_TRACEABILITY.md` se
preserva byte a byte por instrucción del usuario.
