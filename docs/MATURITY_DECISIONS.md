# Decisiones pendientes del candidato de madurez

Documento para revisión privada. No registra aprobaciones ni asigna funciones.
El régimen de publicación sigue separado de la autorización para desarrollar y probar.

## M09: derechos y distribución

El titular debe confirmar por escrito quién puede autorizar el uso/distribución del código y qué régimen aplicará al candidato. Los campos de autor y la posesión del repositorio no prueban por sí solos esa facultad. No se ha elegido una licencia en nombre del titular ni se ha añadido una licencia ficticia.

Decisiones concretas:

1. Identificar al titular o titulares de derechos y el alcance de la autorización para los destinatarios privados del candidato
2. Aprobar el texto de licencia o condiciones privadas aplicables; después alinear metadatos, archivo de licencia y notices, con nueva identidad de artefacto si cambian sus bytes
3. Revisar el inventario de dependencias efectivo de cada entorno y las condiciones de redistribuir binarios o datos. Los metadatos de licencia son inventario técnico, no una opinión jurídica
4. Resolver la limitación documentada de condiciones del origen Treasury antes de ampliar su distribución. La consulta del texto completo falló; no se interpreta ese fallo como permiso

El conjunto de datos congelado es independiente del código y conserva su propia procedencia. Los ejemplos sintéticos no se presentan como datos humanos o resultados científicos.

## M15: mantenimiento y soporte

Ya existen procedimientos técnicos de defectos, versiones, deprecación y recuperación. Falta una organización de mantenimiento realmente aceptada.

El titular debe indicar:

- Responsable del código/candidato, suplente o forma aceptada de escalamiento
- Persona que revisará cambios y su independencia respecto de la implementación
- Responsable y canal privado autorizado para reportes sensibles; el canal de entrega existente permite devolver este expediente al titular, pero no acredita un servicio permanente de respuesta
- Cadencia aceptada de revisión de dependencias y política de excepciones. No hay SLA comprometido
- Decisión de mantener compatibilidad de EquiFrame con Python 3.10 legado. El mantenimiento upstream terminó en octubre de 2026; la compatibilidad de la biblioteca no amplía ese mantenimiento ni certifica parches del proveedor de la VM

No se atribuyen estas funciones automáticamente a Hernán, José o Jhair. La entrega de infraestructura y el modelo/ETL de dominio siguen fuera de la implementación de esta biblioteca.

## M13: reproducción ARM64

La condición actual admite ejecución desde el entorno Codex que ya tiene acceso. Se necesita una ejecución real del kit congelado en maestria-vnic, con Python 3.10 y 3.12, identificación del ejecutor y recibos íntegros devueltos para revisar. Los intentos desde esta nube no establecieron conexión. No hace falta generar otra identidad de acceso.

El importador comprueba identidad del candidato, integridad y completitud técnica. No autentica al operador mediante hashes ni da aceptación humana automática. Una celda fallida o pendiente conserva ese estado.

## M16: revisión independiente y cierre

Una persona independiente debe recibir el mismo candidato por commit y hashes, ejecutar el recorrido acordado, revisar los fallos y límites, y registrar su resultado real. No se rellenará este recibo con un perfil ficticio, otra ejecución del mismo autor o una respuesta automática de un agente.

La validación humana U12 anterior sigue pendiente y no se reutiliza como aceptación de este candidato nuevo. Una revisión parcial puede ser útil, pero no cierra todos los criterios.

## Aprobación de integración

Los cambios permanecen en una rama aislada para revisar. Se entregan commits y parches recuperables. Cualquier push directo o merge a main requiere autorización expresa posterior a la revisión del titular. No se ha solicitado ni obtenido una aprobación de publicación pública.
