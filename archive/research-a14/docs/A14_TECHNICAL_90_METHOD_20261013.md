# Meta A14: 90 % técnico y 10 % humano

El propietario fija el 13 de octubre de 2026 este reparto por área:

`avance = 90 × fracción técnica acreditada + 10 × fracción humana acreditada`.

Las tareas de [HUMAN_REQUIREMENTS_20261012.md](HUMAN_REQUIREMENTS_20261012.md),
incluidas las decisiones y operaciones públicas de PyPI/TestPyPI, pesan en
conjunto **10 puntos por área donde correspondan**. Su preparación por el agente
no acredita la aprobación, la ejecución humana ni la publicación.

El 90 % solicitado exige completar los controles técnicos de cada área con el
candidato A14 exacto. Un control fallido, parcial, no ejecutado o sin evidencia
recibe cero. El promedio no compensa un área pendiente. Las mediciones binarias
originales A11/A13 se conservan; este reparto nuevo no se presenta como una
mejora comparable ni cambia sus numeradores.

| Área | Trabajo técnico que debe comprobarse | Bloque humano (10 puntos) |
|---|---|---|
| Universalidad | Entradas genéricas, tres motores nativos, interfaces, recorridos por rol, perfiles privados y rechazos explícitos en los entornos disponibles | Operadores/acceso a plataformas restantes, experiencia y aceptación independiente |
| Preparación PyPI | Par wheel/sdist A14, metadatos, contenido seguro, instalación privada limpia, CLI/API, reconstrucción e instrucciones reproducibles | Titulares/licencia, cuentas/roles/nombres, hosting aprobado, ensayo TestPyPI y autorización PyPI |
| Documentación | Guías concordantes con código, enlaces locales, ejemplos ejecutados sobre A14, integración del cliente y límites | Lector independiente y aprobación de publicación de documentación |
| Trazabilidad | Inventario identificado, casos y esperados independientes, recibos normales/optimizados ligados a bytes A14, IDs únicos y pendientes explícitos | Revisión independiente del expediente; no sustituye casos técnicos faltantes |
| Calidad del paquete | Controles originales técnicos aplicables, tipado, estilo, comportamiento, instalación y compatibilidad comprobada | Licencia, adopción externa, comunidad y aceptación pública |
| Madurez | Criterios técnicos originales, incluidos integridad/recuperación, consumidor, dependencia/SAST/SCA y perfiles ejecutables | Derechos, roles/soporte, revisión independiente y operadores de plataformas restantes |
| Requisitos de tesis | Automatización y expediente reproducible de datos, particiones, contratos, independencia R/M/B/H/O, entrenamiento/evaluación y reproducción técnica | Cohorte/normalidad/protocolo aprobados, etiquetas ciegas/arbitraje, aceptación DW/servicio, revisión de resultados y reproducción por otro integrante |

Para la tesis se distinguen **preparación técnica** y **cumplimiento científico**.
Un ensayo sintético o provisional puede comprobar código, pero no acredita
normalidad real, etiquetas confirmadas, independencia humana ni resultados
científicos. Si falta un dato aprobado necesario para ejecutar un control,
éste continúa pendiente; no se convierte automáticamente en los 10 puntos humanos.

Este método fija la meta y las reglas; no declara todavía 90 % obtenido. Los
resultados se deben vincular a hashes de fuente/artefactos, comandos, fallos y
omisiones observados. Alpha privada A14 continúa hasta su cierre explícito;
no se publica ni se cambia a Beta por este documento.
