# Universalidad R2: universo fijado antes de ampliar pruebas

Fecha: 2026-10-09 UTC. Base remota observada: `479838316111cc47287153ca315d3f69b5c00d7f`, árbol `06654c9e90f34f257b3ed2a8844b6c8b64a18d2a`.
La integración de A8 ya ocurrió. Esta rama conserva esa historia y prepara A9; no atribuye a los nuevos bytes los recibos A8.

## Denominador fijo

Doce criterios completos UV01–UV12. Índice = 100 × CUMPLIDOS / 12; PARCIAL, BLOQUEADO y NO_EJECUTADO suman cero. La referencia previa 55 % carece de numerador/denominador reproducibles en los informes disponibles. El 65 % histórico de madurez pertenece a otro eje; no se calcula un salto retrospectivo desde ninguno.

## Matriz comprometida

Cinco plataformas nativas por cuatro CPython = veinte celdas, sin retirar combinaciones después de observar resultados.

| Plataforma | Python requeridos | Estado inicial |
|---|---|---|
| Linux x64 | 3.10, 3.11, 3.12, 3.13 | NO_EJECUTADO para A9 |
| Linux ARM64 | 3.10, 3.11, 3.12, 3.13 | NO_EJECUTADO para A9 |
| Windows x64 | 3.10, 3.11, 3.12, 3.13 | NO_EJECUTADO para A9 |
| macOS Intel | 3.10, 3.11, 3.12, 3.13 | NO_EJECUTADO para A9 |
| macOS Apple Silicon | 3.10, 3.11, 3.12, 3.13 | NO_EJECUTADO para A9 |

En cada celda: wheel/sdist del núcleo, benchmark y consumidor externo, imports/API/CLI, perfiles aplicables, pip check, identidad de intérprete/bibliotecas y conducta negativa. Perfil base y arrow/pandas/polars/duckdb/engines/ml/all; benchmark base/engines/ml/resources/all. Las suites completas se concentran en all; perfiles individuales ejecutan conformidad específica. Mínimos y recientes se fijan por resolución efectiva, con hashes: ambas variantes en Linux x64/ARM64 para cuatro Python, y las celdas representativas 3.12 de Windows/macOS; otras versiones nativas no heredan esa evidencia.

Tres motores nativos y seis direcciones; contratos y esperado independiente. Dominios: finanzas, comercio y telemetría/ciencia, con equivalente, diferente e inválido. Se conservan puertos, registros explícitos, productor SQLite y consumidor externo, sin agregar un framework/gateway. El corpus público de 219 registros/72 casos se identifica por su manifest privado; no se copia a Git.

## Secuencia y límites

1. Dependencia directa del benchmark, identidad A9 y resolución pública mínima/local privada
2. Ampliar el laboratorio existente y revisión estricta a cuatro Python; conservar esquema histórico de dos
3. Congelar seis artefactos, tests/hashes/locks; entregar kit ARM64 sin llaves y continuar Linux x64
4. Revisar evidencia nativa y correcciones; conservar Windows/macOS pendientes sin emulación
5. Reconciliar main y repetir controles afectados antes de integrar la ampliación completa

No cambia R/M/B/H/O, H = R OR M, tolerancias, políticas ni ciencia. No se afirma traducción arbitraria, rango completo de dependencias, independencia humana o aceptación del DW/servicio. Manual workflows no se disparan. Guardias de disco 6 GiB lab, 4 GiB consumidor y benchmark permanecen; ejecución secuencial con presupuesto planificado 2 CPU/6 GiB RAM/10 GiB temporal, revalidado antes de cada etapa.

Las fronteras Decimal/tiempo nativas existentes no se reclasifican como transformaciones exitosas. Capacidad requerida pero no implementada queda parcial. Madurez 1/16 y usabilidad 11/12 son antecedentes con puertas propias; integración Git no los cierra.
