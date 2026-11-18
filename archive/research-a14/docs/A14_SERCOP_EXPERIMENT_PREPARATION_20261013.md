# Preparación técnica del experimento SERCOP

Se preparó y verificó un expediente privado desde el archivo original anual
`sercop_2025_mes00_json.zip`, SHA-256
`80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3`.
La fuente mantiene sus bytes y no se publica en Git. Se leyeron 190.619 releases
y 183.891 awards. Hay 176.665 publicaciones de 2025 y 13.954 de 2026; no se
presenta el conjunto como una cohorte aprobada exclusivamente de 2025.

La selección piloto fija los primeros 12 OCIDs elegibles en el orden de la
fuente antes de ejecutar resultados. Para cada unidad se preparan tres familias
—ausencias/tipos, joins y agregaciones— con tres motores nativos y dos variantes,
control y mutación: **216 ejecuciones**, 108 por variante. Los esperados provienen
de la fuente y operaciones stdlib independientes del motor. Un acuerdo entre
motores no actúa como oráculo de corrección ni como etiqueta humana.

Se propuso comparar valores físicos sin pérdida e ignorar exclusivamente el
índice de transporte porque OCID y award_id son columnas explícitas. La propuesta
queda registrada antes de las variantes. No constituye aprobación metodológica.
R, perfiles y comparaciones se recalcularon para los 216 registros; 108 controles
equivalentes y 108 mutaciones diferentes, con archivos y hashes verificados antes
y después. El verificador no vuelve a ejecutar los callbacks nativos ni a leer
el ZIP original: esos pasos tienen su propio recibo de preparación.

Los escenarios comparten plantillas y OCIDs. La agrupación conservadora conecta
los 36 escenarios en un solo grupo. La asignación sin partir ese grupo deja 12
escenarios por familia en entrenamiento y ninguno en calibración/test. No se
declara una partición final válida ni se inventa independencia para llenar conjuntos.

Hay 216 fichas ciegas con identidades opacas y dos hojas de revisión, A y B, con
revisor, fecha, etiqueta y motivo vacíos. Los motores, variantes y resultados de
detectores permanecen en coordinación privada. No hay casos confirmados normales,
entrenamientos M/B acreditados ni `N_fit > 10.000`; el oráculo humano queda pendiente.

## Herramientas y recibos

- `tools/prepare_sercop_experiment.py`: preparación local, selección explícita,
  ejecuciones nativas y fichas ciegas; máximo 32 unidades por paquete para conservar
  el presupuesto cerrado de archivos. Un corpus mayor requiere paquetes particionados.
- `tools/thesis_packet_io.py`: archivos locales regulares, inventario cerrado,
  límites de tamaño/estructura y rechazo de claves JSON repetidas, números no
  finitos, enlaces, puntos reparse y referencias que salen del expediente.
- `tools/check_thesis_packet.py`: integridad, contratos, esperados, perfiles/R,
  comparación completa y separación de las etiquetas. Devuelve 3 cuando la
  preparación técnica pasa pero la aceptación científica continúa pendiente.
- `tests/test_thesis_packet_preparation.py`: 29 pruebas de rechazo aprobadas y
  una omisión de permisos de symlink en Windows, sin producir etiquetas ficticias.

Expediente original: `a14_revalidation_20261013/sercop-experiment-proposal-v1`,
7.628 archivos y 76.991.687 bytes. Manifiesto de preparación SHA-256
`485fad7601f38873ba979c3740d5a0b45c65c3aac894766ed2121169413f039e`.
La verificación está en `sercop-experiment-verification-v1/verification.json`,
`technical_preparation=PASS`, `scientific_ready=false`.

Este expediente se creó con los artefactos privados del commit `835b9db` y el
preparador identificado allí por SHA-256
`d96897560a69e1c13075a65a9f68c44e2f63ebe8d5abcedeb04e54c22191e3ea`.
El límite posterior de 32 unidades no cambia sus 12 unidades ni sus archivos;
el nuevo código no hereda automáticamente el recibo del preparador anterior.
Las correcciones posteriores de EDA/lector requieren artefactos y verificaciones propias.

La metodología, normalidad, cohortes, etiquetas/arbitraje y aceptación final
siguen en [requisitos humanos](HUMAN_REQUIREMENTS_20261012.md). Los controles
técnicos que necesitan esos insumos continúan pendientes; esta preparación no
acredita por sí sola el 90 % del rubro tesis ni resultados científicos finales.
