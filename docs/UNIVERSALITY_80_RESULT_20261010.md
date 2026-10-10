# Universalidad: avance técnico al 80 % — 2026-10-10

**Resultado observado: 48/60 = 80 %**, frente al [corte anterior 41/60 =
68,3 %](UNIVERSALITY_TECHNICAL_PROGRESS_20261010.md). Se cerraron los siete
puntos previstos en el [plan de cinco pasos](UNIVERSALITY_80_PLAN_20261010.md).
Ambos cortes usan `UV-TECH-A11-60-v1`, idénticas sesenta definiciones y pesos,
y los mismos bytes A11 del núcleo/benchmark. Avance: **7 comprobaciones y
11,67 puntos porcentuales**; reducción de pendientes de 19 a 12.

Es un índice propio de ingeniería con alcance finito. No representa cobertura
de todos los datos/operaciones/entornos, resultado científico de la tesis ni
cierre de los doce criterios íntegros del plan histórico. El 25 % A9 usa otra
escala y permanece histórico. El [JSON](UNIVERSALITY_80_RESULT_20261010.json)
conserva las sesenta definiciones, puntos, motivos, inventario de versiones,
fechas y hashes de las evidencias privadas.

## Plan ejecutado en cinco pasos

1. **Python:** A11 instalado fuera del checkout en Windows CPython 3.10.21,
   3.11.16 y 3.13.15. Cada versión aprobó 121 pruebas nativas: **363 en total,
   cero fallos y omisiones**. Se comprobaron metadatos, bytes instalados,
   dependencias, ejemplo correcto y rechazos por discrepancia/corrupción,
   incluida corrupción bajo `-O`. Se conserva la evidencia A11 de Python 3.12.
2. **Perfiles:** ocho del núcleo (`base`, `arrow`, `pandas`, `polars`, `duckdb`,
   `engines`, `ml`, `all`) y cinco del benchmark (`base`, `engines`, `ml`,
   `resources`, `all`), en Windows x64 y Linux ARM64/Python 3.12:
   **26 perfiles aprobados**. Instalaciones aisladas con resolución normal,
   inventario real, API positiva/negativa y ejemplos apropiados. La
   [herramienta manual](../tools/universality/README.md) permite reproducirlos.
3. **Consumidor externo:** aplicación privada `equiframe-consumer-lab 0.1.13`
   instalada desde wheel con el A11 exacto, fuera de ambos checkouts.
   **19 pruebas aprobadas por plataforma**: extensión externa, productor
   SQLite y fallos de evidencia/publicación. Linux ARM64 aprobó **72 casos
   del corpus congelado, 144 ejecuciones nativas, 24 aceptaciones y
   48 rechazos esperados**. Cada caso conserva entradas intactas y verifica
   el bundle sin su origen nativo. El corpus Windows también aprobó 72/72: 144 ejecuciones, 24 aceptaciones y 48 rechazos esperados; controles de fallos bajo `-O` aprobados.
4. **Dominios:** nueva matriz sintética de finanzas, comercio y telemetría,
   tres variantes por seis direcciones. **54 casos por plataforma**,
   72 ejecuciones nativas y 18 aceptaciones por plataforma. Se preservan
   importes Decimal grandes, IDs con ceros, nulos, unidades y fechas UTC
   declarados. Los 18 inválidos por plataforma cambian tipos físicos y
   se rechazan antes de ejecutar motores; no agotan un presupuesto para
   simular invalididad. Los 18 discrepantes por plataforma no publican.
5. **Avisos:** inventario fijado de **33 entornos, 86 pares paquete/versión
   de 75 nombres**, incluidas herramientas efectivamente instaladas.
   **258 consultas completas**, tipos `reviewed`, `unreviewed` y `malware`,
   con paginación y **cero desconocidos**. No hubo coincidencias activas o
   retiradas para esos pares en esa base a la fecha 2026-10-10T17:16:37Z.
   El control de `requests@2.31.0` detectó tres avisos; el paquete ficticio
   devolvió cero. Se usa la [API oficial de avisos de GitHub](https://docs.github.com/en/rest/security-advisories/global-advisories).
   Los tres candidatos privados propios se identifican por hashes y se
   excluyen del ecosistema público de dependencias. Esto no certifica el
   código propio, Python/SO ni la ausencia general de vulnerabilidades.

## Los siete puntos nuevos

| ID | Evidencia que permite pasar de 0 a 1 |
|---|---|
| 02.1 | A11 instalado fuera del checkout en Windows CPython 3.10.21; 121 pruebas nativas, cero fallos/omisiones; positivo y negativos normales/optimizados. |
| 02.2 | A11 instalado fuera del checkout en Windows CPython 3.11.16; 121 pruebas nativas, cero fallos/omisiones; positivo y negativos normales/optimizados. |
| 02.4 | A11 instalado fuera del checkout en Windows CPython 3.13.15; 121 pruebas nativas, cero fallos/omisiones; positivo y negativos normales/optimizados. |
| 04.4 | Los ocho perfiles core y cinco benchmark aprobados individualmente en Windows x64 y Linux ARM64/CPython 3.12: 26 entornos con inventario, bytes instalados, resolución normal y positivos/negativos. |
| 07.5 | Consumidor independiente de repo 0.1.13 instalado sobre los mismos wheels A11; Linux ARM64 ejecuta corpus congelado de 72 casos/144 ejecuciones/24 aceptaciones/48 rechazos; extensión externa y productor SQLite aprobados. |
| 08.4 | 54 casos sintéticos por plataforma en finanzas/comercio/telemetría y seis direcciones; 18 aceptaciones, 18 discrepancias y 18 rechazos de tipo físico inválido antes de ejecución. No acredita adopción humana. |
| 11.2 | Alcance fijado de 33 entornos A11 y todas sus distribuciones externas instaladas: 86 pares paquete/versión, 258 consultas reviewed/unreviewed/malware con paginación, controles positivo/negativo y cero desconocidos. Sin coincidencias en esa base a esa fecha; no certificación de seguridad. |

## Comparación con la misma escala

| Área | Corte anterior | Corte actual |
|---|---:|---:|
| UV01 — Núcleo, contratos y entradas | 5/5 | 5/5 |
| UV02 — Versiones Python | 2/5 | 5/5 |
| UV03 — Plataformas nativas | 2/5 | 2/5 |
| UV04 — Dependencias y perfiles | 3/5 | 4/5 |
| UV05 — Operaciones y motores | 4/5 | 4/5 |
| UV06 — Preservación semántica | 4/5 | 4/5 |
| UV07 — Extensiones externas | 4/5 | 5/5 |
| UV08 — Diversidad de dominios | 3/5 | 4/5 |
| UV09 — Operación y recursos | 4/5 | 4/5 |
| UV10 — API, documentación y primer uso | 4/5 | 4/5 |
| UV11 — Procedencia, dependencias públicas y licencia | 2/5 | 3/5 |
| UV12 — Integración y reproducción | 4/5 | 4/5 |
| **Total** | **41/60 (68,3 %)** | **48/60 (80 %)** |

## Identidad, Git, VM y fallos conservados

El código A11 procede del [PR 28](https://github.com/htroya/equiframe/pull/28),
commit `eb3fd70ec1dc059c58d7c95699981231ba5e6f60`; `main` previo al plan
era `81f683773c7bf0a52669c941a6625a95fffcf736`. Este trabajo amplía su
evidencia y publica herramientas; no cambia sus versiones ni bytes.

| Artefacto A11 | SHA-256 |
|---|---|
| `equiframe-0.12.0a11-py3-none-any.whl` | `11cbae825f3b2ac4f6e9a6378d589bbb6f74be37587a3c40a591b64a7496a15e` |
| `equiframe-0.12.0a11.tar.gz` | `512ab8eb3e100f279aca4dfa2b6f65340817cf1c8ef620ccb9aa8b5a78c85831` |
| `equiframe_benchmark-0.12.0a11-py3-none-any.whl` | `f77d06012e92ea3bc72a1ada4d02938827880622d7560501ba0a251e132fc2b3` |
| `equiframe_benchmark-0.12.0a11.tar.gz` | `b775f5909c3122bb5313800ff49a22ab822b8bb922e55496289ae279ff903241` |

El [consumidor privado](https://github.com/htroya/equiframe-consumer-validation)
se integra mediante [PR 1](https://github.com/htroya/equiframe-consumer-validation/pull/1):
fuente `33a95293d6bc0b24252fb9448ee5883927d50463`, main
`e839520761d3fc30cdb3faef94970a6dea59fc76`, wheel `dec285132646d40d0be512535383ee8fa060ac800aed803ede4f40ef8b091e15`.
El contenido fuente queda ligado al commit con mapeo explícito CRLF del
checkout Windows frente a LF de Git; no se afirma reconstrucción idéntica
del archivo del consumidor en todas las plataformas. Las instalaciones
comparan sus bytes contra el wheel probado.

Se reutilizó la VM existente `157.137.227.1`, Linux ARM64, como segundo entorno
nativo para perfiles, consumidor y mediciones de 1000 filas. El laboratorio
privado nuevo `/home/hernan/equiframe-universality80-20261010-attempt2` conserva
entornos, paquetes, logs, corpus por referencia y recibos, sin sobrescribir
los laboratorios anteriores. Quedaban 8375877632 bytes
libres al comprobar los recibos; se exigieron 4 GiB antes de cada etapa.
Se reutilizaron las dependencias en caché y se descargó `psutil` para los
extras que no lo tenían. Las mediciones son técnicas, con muestreo y cargas
concurrentes declaradas; no benchmarks científicos ni cuotas duras.

Los intentos fallidos se conservan: caché incompleta, manejo de espacios de
constraints, carpeta padre de temporales ausente, expectativa incorrecta de
recursos en perfil base y `psutil` ausente en la caché ARM64. Se corrigió el
laboratorio y se repitieron las partes afectadas. No se cuentan como pases,
ni se borran para presentar una ejecución inicial sin errores. También se
conservan los tres fallos históricos de expectativas de compilador del corte
completo anterior; las baterías nuevas son focales, no una suite completa
final del núcleo. No se ejecutó Actions, publicó en PyPI ni crearon servicios
o recursos de pago. Datos y recibos permanecen fuera de Git.

## Los doce puntos que siguen pendientes

- **03.1**: Instalación y ejecución nativa de A11 en Linux x64, al menos en un Python declarado.
- **03.4**: Instalación y ejecución nativa de A11 en macOS Intel, al menos en un Python declarado.
- **03.5**: Instalación y ejecución nativa de A11 en macOS Apple Silicon, al menos en un Python declarado.
- **04.5**: Extremos mínimo/reciente de A11 y sus marcadores ejecutados en todas las celdas comprometidas.
- **05.5**: Producto completo de operaciones/tipos/políticas/direcciones y entornos cerrado; las capacidades requeridas no se sustituyen por rechazo.
- **06.5**: Semántica común completa entre motores para todas las operaciones exigidas de Decimal y tiempo, incluidas división y localización.
- **08.5**: Aceptación o adopción de A11 documentada por consumidores reales de dominios externos; no basta evidencia sintética.
- **09.5**: Cambio de versión A11→anterior→A11 y recuperación fresca cerrados en los entornos requeridos.
- **10.5**: Primer uso y recorridos completos de A11 en cinco plataformas por cuatro Python, con consumidor externo.
- **11.4**: Titulares y licencia/condiciones de EquiFrame aprobados y registrados.
- **11.5**: Condiciones de terceros y corpus resueltas para el alcance de redistribución, incluida la restricción Treasury.
- **12.5**: Toda la matriz nativa y obligaciones anteriores cerradas, con reproducción/aceptación independiente documentada.

En términos prácticos: Linux x64 y ambos macOS; extremos de dependencias y
matriz completa; operaciones/tipos/políticas y semántica Decimal/tiempo aún
incompletas; recuperación en todos los entornos; adopción humana; licencia
y condiciones de terceros/corpus. Estos pendientes no se eliminan por la
autorización de integrar a main. Se preservan R/M/B/H/O y el protocolo de tesis.
