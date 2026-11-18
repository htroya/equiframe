# SERCOP: adquisición pública y piloto técnico

Se adquirieron dos exportaciones desde el [portal oficial de datos abiertos](https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos/),
con selección `method=all`, sin credenciales. Las respuestas originales,
ZIP/CRC, fechas, URL y SHA-256 están en el expediente privado del seguimiento.
Se publican inventarios agregados y resultados técnicos; el Word no se modificó.

| Exportación seleccionada | ZIP / JSON descomprimido | Paquetes / releases | Ocurrencias de adjudicación |
|---|---|---:|---:|
| Año 2025, mes 0 (anual) | 160.929.006 / 1.721.952.248 bytes | 190.619 / 190.619 | 183.891 |
| Año 2025, mes 1 (enero) | 1.135.674 / 13.497.759 bytes | 2.186 / 2.186 | 2.135 |

La adquisición anual terminó el 2026-10-11 a las 18:21:21 UTC; enero, a las
18:20:28 UTC. Las URLs exactas están en el [recibo público agregado](SERCOP_PUBLIC_RESULT_20261011.json).
El formato es una lista de paquetes con `releases`, no una tabla de registros
OCDS compilados. El inventario abre el único miembro JSON sin extraerlo ni
ejecutarlo, rechaza claves duplicadas/no finitos y mantiene los números como
`Decimal`. No suma montos entre monedas o versiones.

En la selección anual hay **176.666 releases con fecha 2025 y 13.953 con fecha
2026**. Ocho mil trescientas cuarenta y dos no tienen `awards` o lo tienen nulo;
cuatro adjudicaciones no tienen un objeto de valor válido. Hay 190.619 OCID y
183.891 identidades `(ocid, award.id)` distintas en este snapshot. La selección
«2025» no acredita por sí sola una cohorte de adjudicación o publicación de ese
año; las actualizaciones/compilación y la regla temporal deben justificarse.

Todos los paquetes declaran [CC BY 3.0 Ecuador](https://creativecommons.org/licenses/by/3.0/ec/).
La fuente es el Servicio Nacional de Contratación Pública. Los inventarios y
transformaciones del piloto son derivados técnicos; no sugieren respaldo de
SERCOP ni sustituyen la licencia pendiente del software.

## Piloto consumidor de enero

El protocolo se escribió antes de ejecutar los motores y se identificó por
hash. Conservó el grano observado `(ocid, award.id)` y rechazó identidades
ambiguas, múltiples releases por paquete o montos no representables exactamente.
No construye el DW de Jhair ni el servicio de José.

Se ejecutaron tres operaciones de forma nativa en Pandas, Polars y DuckDB:
proyección de tipos/ausencias, unión izquierda de adjudicaciones con su fecha de
release, y conteo agrupado por moneda. El esperado provino de una construcción
Python independiente de las salidas de esos motores. La unión no utiliza
proveedores ni multiplica montos; la agregación es un conteo y no una suma de
dinero. Los montos se conservaron como Decimal128 de precisión 38 y escala 6,
sin redondeo ni conversión a float. Solo se ignoró explícitamente el RangeIndex
generado por Pandas, sin relajar tipos físicos, valores o multiplicidades.

**18/18 comprobaciones fueron equivalentes:** nueve contra el esperado literal
y nueve entre las tres parejas/familias. Las capturas y recibos conservan las
salidas reales. Estos son recorridos de integración del export mensual; no
validan todas las modalidades, estados, clases de ausencia o cuotas científicas.
No se promovieron a nuevas obligaciones del catálogo ni a adopción externa.

## Qué permite avanzar y qué sigue abierto

Se obtuvo un corpus bruto reproducible y un piloto real comprobable. Siguen
pendientes la compilación/contrato de dominio, cohorte, excepciones, perfiles de
aprendizaje por familia/modelo, grupos y particiones sin fuga, reglas fijadas,
etiquetas y doble revisión ciega humana, calibración/congelación, evaluación
pareada e incertidumbre, reproducción por otro integrante y dictamen del tutor.
Las 183.891 ocurrencias no acreditan `N_fit > 10.000`; no se ajustó ningún modelo
y el soporte efectivo acreditado permanece nulo.

El script/protocolo ejecutados y las exportaciones están en
`avance_95_20261011` fuera de Git; sus identidades y resultados agregados permiten
revisar lo entregado sin divulgar registros en el repositorio. No cambió
`tesis_corregda_v1.docx`. [Estado de las nueve áreas](PROJECT_STATUS_MATRIX_20261011.md).
