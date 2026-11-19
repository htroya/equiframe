# Fiabilidad: comparación exacta y señales de anomalía

EquiFrame ayuda a comprobar que cambiar un archivo, una consulta o un motor de
procesamiento conserve las condiciones declaradas para los datos. Antes de
comparar hay que definir esas condiciones: claves, valores, repeticiones, tipos,
ausencias, orden y tolerancias admitidas.

| Resultado | Qué permite concluir |
| --- | --- |
| Comparación completa `equivalent` | Las dos entradas examinadas cumplen la igualdad definida por el contrato. |
| `different` | Se encontró una diferencia relevante para ese contrato; los detalles permiten localizarla. |
| `not_evaluable` o comparación incompleta | No se puede aceptar equivalencia. Hay que resolver la causa o completar la comprobación. |
| Alerta de Isolation Forest | El perfil resulta inusual frente al modelo ajustado. Hace falta examinarlo. |
| Ausencia de alerta de Isolation Forest | El detector no alertó; esto no acredita equivalencia. |

## Elegir el servicio adecuado

Para decidir equivalencia, usa `compare` o `diff` y exige una evaluación completa.
`assert_equivalent` rechaza tanto una diferencia como una evaluación que no permite
aceptar equivalencia. La comparación no utiliza una puntuación de Isolation Forest
para sustituir valores o decidir si dos tablas coinciden.

Por ejemplo, conservar el total de 300 unidades no basta si una entidad debía
tener 100 y otra 200. Una salida de 101 y 199 conserva el total, pero una
comparación por la clave de entidad detecta ambas asignaciones incorrectas.
Si el contrato autoriza una tolerancia, el resultado corresponde a esa tolerancia;
elige igualdad exacta cuando el requisito sea conservar centésimas monetarias.

Los perfiles y `detect_component(..., method="isolation_forest")` proporcionan
diagnósticos separados. La combinación OR `combine_decisions` es una política de
alertas. `ReviewedDecision.accepted` describe la finalización de los controles
operativos solicitados sin alertas; no es una etiqueta científica de corrección.
Una alerta estadística puede mantener un caso en revisión aunque las tablas
coincidan. Para conocer la equivalencia, consulta el resultado de comparación.

## Qué significa comprobar la fiabilidad

Las pruebas deben incluir tablas iguales, diferencias reales, claves repetidas,
ausencias frente a cero, importes exactos, límites y datos no evaluables. Un
resultado parcial no se convierte en aceptación. Los artefactos y sus huellas
permiten vincular una conclusión con las entradas y políticas examinadas; una
huella por sí sola no reemplaza la comparación de valores.

No se promete ausencia universal de defectos del software ni cero falsas alarmas
u omisiones de un detector estadístico. Esas tasas se miden y publican. La
[evaluación con datos públicos](public-spending-evaluation.md) muestra tanto
detecciones adicionales como fallos del detector y un control exacto más fuerte.
La fiabilidad exige conservar esa evidencia y usar cada resultado con su alcance.
