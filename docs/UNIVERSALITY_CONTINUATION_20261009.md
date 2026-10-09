# Continuación local de universalidad A10

Base GitHub comprobada el 2026-10-09: `c9ded729835490a99d9d2110b05682c0c611e154`.
Esta continuación conserva el denominador de doce criterios y veinte celdas de
`UNIVERSALITY_PLAN.md`. A10 es un candidato privado en validación; no acredita
100 %, publicación, aceptación humana ni resultados científicos.

## Cambios en revisión

- Captura DuckDB: cerrar el writer Arrow antes de sincronizar por el descriptor
  writable original, incluyendo el footer en el presupuesto. Corrige el fallo
  de fsync al reabrir en modo lectura en Windows.
- Medición: implementación y contratos explícitos por plataforma; contadores
  ausentes siguen indisponibles. No se inventan límites duros ni SLO.
- Laboratorio: intérprete solicitado, instalación del par exacto, perfiles y
  extremos, optimización observada, aislamiento y recuperación verificables.
- Controladores Actions: candidato único y hashes, veinte celdas nativas,
  inventario completo de evidencia y agregación que rechaza celdas ausentes.
- Fixtures históricos: Git preserva bytes, sin conversiones automáticas EOL.
- Cancelación Windows: terminar el árbol del proceso propio; la ruta POSIX
  conserva su grupo privado. No se usa killpg en Windows.
- Tests del arnés: separar modos normal/optimizado y usar rutas de fixtures
  válidas en el sistema anfitrión. Los controles de Bash/AlmaLinux se ejecutan
  únicamente en POSIX; no acreditan un instalador Bash nativo de Windows.

## Evidencia inicial ejecutada

Controles de estilo, formato, tipado y assets del core/benchmark pasan. El tipado
estricto revisó 92 archivos de core, 36 de benchmark y cinco controladores.
Los controladores tienen 25 tests y 46 subcasos aprobados. Las herramientas de
handoff tienen 78 tests y 30 subcasos aprobados. El foco de recursos tiene
84 tests aprobados y cinco omisiones explícitas de comportamientos POSIX/Linux
en Windows, con sus sustitutos Windows comprobados por la suite.

Los inventarios de dependencias ligados a los seis artefactos locales tienen
134 consultas core y 124 benchmark completas a PyPI/OSV, cero consultas
desconocidas y cero avisos conocidos. Se verificaron offline contra artefactos,
locks y entornos registrados. Este resultado corresponde a Windows CPython
3.12 y versiones exactas; no cubre otros entornos, bibliotecas nativas incluidas
ni sustituye la decisión de licencia del propietario.

La ejecución histórica A9 de OCI terminó con código 1. Sus recibos se conservan.
Los intentos locales previos de A10 tampoco se relabelan como éxitos: quedaron
detenidos por inventario de tests desactualizado y diferencias del contrato
entre el colector y el controlador local. Los intentos corregidos usan salidas
nuevas y los mismos hashes de distribuciones, sin cambiar expectativas de datos.

## Configuración externa pendiente para las veinte celdas

La lectura de GitHub encontró solamente `htroya/equiframe` como repositorio
EquiFrame. No hay variables de universalidad ni el secreto de lectura requerido.
La matriz requiere repositorios privados separados para el consumidor y el
corpus congelado, sus commits exactos y:

| Configuración | Valor o condición |
|---|---|
| `UNIVERSALITY_CONSUMER_REPOSITORY` | Repositorio privado del consumidor independiente |
| `UNIVERSALITY_DATA_REPOSITORY` | Repositorio privado del corpus congelado autorizado |
| `UNIVERSALITY_VALIDATION_REF` | `refs/heads/universalidad/remediacion-100-20261009` |
| `UNIVERSALITY_READ_TOKEN` | Acceso de lectura a contents de esos dos repositorios |

No se incorpora una credencial existente de alcance mayor. El workflow mantiene
su preflight: la falta de configuración es un bloqueo, no una celda aprobada.
La creación/publicación de esos repositorios y la provisión del acceso quedan
separadas de las pruebas locales y de OCI. La revisión final registrará recibos
efectivos y criterios cerrados; preparar YAML no acredita sus ejecuciones.
