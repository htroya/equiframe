# Instrucciones de trabajo

Lee `README.md`, `docs/ARCHITECTURE.md`, `docs/API_CONTRACTS.md`, `docs/TEAM_INTEGRATION.md` y el paso aplicable de `docs/HERNAN_ROADMAP.md` antes de implementar.

- La tesis sigue en revisión. Distingue requisitos del borrador, decisiones de ingeniería y decisiones experimentales pendientes. Cambios metodológicos requieren registrar motivo, versión y consecuencias en `docs/DECISIONS.md` y `docs/THESIS_TRACEABILITY.md`.
- No presentes interfaces planificadas, datos sintéticos, modelos no entrenados o pruebas no ejecutadas como funcionalidad o evidencia existente.
- Mantén independientes R (reglas), M (Isolation Forest), B (MAD), H (R OR M) y O (oráculo). Detectores y perfiles no reciben etiquetas, mutaciones ni salidas de otro motor. Pandas no es el oráculo.
- No conviertas un fallo, una entrada inválida o un componente no estimable en ausencia de alerta.
- Conserva decimales, monedas, multiplicidad, claves, ausencias y fechas según el contrato. No normalices diferencias para hacer pasar una prueba.
- El núcleo no depende de OCI, del cliente de José ni del esquema SERCOP. Usa interfaces e inyección de dependencias. Cada motor conserva su ejecución nativa; no ejecutes una transformación una sola vez y conviertas su resultado para simular tres implementaciones.
- Respeta la propiedad de carpetas de `docs/TEAM_INTEGRATION.md`. No implementes infraestructura de José ni redefinas el DW de Jhair dentro de tareas de Hernán.
- No leas ni escribas un archivo DuckDB compartido con varios procesos escritores independientes. El servicio de datos es responsable de la coordinación.
- Prueba comportamiento y riesgos reales: casos esperados independientes, propiedades, estados no evaluables y errores. No inventes resultados o cobertura.
- No subas credenciales, datos reales, bases, modelos serializados, entornos ni resultados privados. No uses tokens incrustados en remotes, código o comandos documentados.
- No ejecutes callbacks, SQL, plugins o modelos obtenidos de fuentes no confiables. Esta biblioteca no es un sandbox.
- Cada paso termina con pruebas apropiadas, documentación de uso y límites, y un commit revisable. Publicar en PyPI o desplegar servicios requiere una tarea explícita; subir cambios a este repositorio está autorizado en la tarea inicial.
- `pip install equiframe` significa publicación pública en PyPI accesible a cualquier usuario. Solo se abordará después de completar el paso 10 y una nueva ronda de revisión indicada por Hernán. Instalar el paquete localmente o en CI no cumple ese objetivo ni es un entregable solicitado. No adelantar esa publicación ni instalaciones persistentes por este requisito.
- No generes métodos vacíos o retornos ficticios para aparentar implementación. Los Protocol y tipos declarativos son válidos; las implementaciones públicas deben tener comportamiento comprobable.
- Antes de subir, ejecuta los controles específicos del paquete afectado. En el paso 1 crea y verifica las comprobaciones CI reales; no anuncies comprobaciones que todavía no existen.
