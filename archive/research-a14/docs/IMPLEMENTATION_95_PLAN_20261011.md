# Plan de implementación y validación hacia el 95 por ciento

Fecha: 11 de octubre de 2026, America/Guayaquil. Base: `dc11cb249d90c0599163fae53b1403c747fd5363`, par privado `0.12.0a13`. Solicitud del usuario: mejorar las nueve áreas y entregar los cambios en `main`. El usuario confirmó que licencia/titulares y revisión independiente/resultados científicos continúan pendientes. La publicación pública no forma parte de la entrega Git.

## Objetivo y regla de aceptación

El objetivo es alcanzar **al menos 95 % en cada rúbrica original**, manteniendo sus pesos, denominadores, estados pendientes y versión evaluada. No se sustituye una rúbrica por otra más favorable. No se obtiene un promedio global ni se cuenta documentación, planificación o repetición de pruebas como ejecución nueva. Cuando cambia un wheel, se congela su nueva identidad y se repiten los controles afectados antes de asignarle resultados.

| Área | Última evidencia | Mínimo para 95 % | Dependencias de cierre |
|---|---|---|---|
| Usabilidad | A12, 11/12 | 12/12 = 100 % | Revalidar U01–U11 sobre el candidato actual y ejecutar U12 con personas independientes |
| Universalidad | A11, 48/60 | 57/60 = 95 % | Nueve comprobaciones adicionales en las mismas definiciones; revisar las sesenta para el candidato actual |
| PyPI | A13, 16/20 | 19/20 = 95 % | Al menos tres de P17–P20, incluidos derechos/control/documentación/ensayo real según sus definiciones |
| Documentación | Repositorio sobre A13, 18/20 | 19/20 = 95 % | D19, lector independiente, o D20, manual público con derechos aprobados |
| Trazabilidad | A13, 4.298/8.385 | 7.966/8.385 = 95,003 % | 3.668 obligaciones adicionales con casos observados y esperados independientes |
| Calidad | A13, 16/20 | 19/20 = 95 % | Tres de los cuatro criterios externos pendientes: distribución/adopción/comunidad/licencia |
| Madurez | Sin medición A13 | 16/16 = 100 % | Reevaluación integral M01–M16; 15/16 solo es 93,75 % |
| Tesis | Sin porcentaje científico | No definido | Aplicar T01–T22 con evidencia y aceptación académica; no equiparar la edición de capítulos 1–2 con tesis final |
| Seguridad | Sin rúbrica aplicada | No definido | Auditoría de fuente, dependencias actuales y decisiones de responsables/canal; fijar criterios antes de medir |

## Orden de ejecución

1. **Congelar alcance y evidencia.** Conservar originales Word, hashes de artefactos A11/A12/A13, commit y recibos previos. Registrar faltantes por criterio, sin imputar cero a áreas sin medición ni transferir resultados entre versiones.
2. **Conciliar la tesis.** Comparar los dos Word completos, distinguir aportes nuevos de contenidos ya presentes, validar afirmaciones con fuentes primarias y registrar aceptación/corrección/exclusión. Editar `tesis_corregda_v1.docx` con su fuente, estilos, tema, secciones, figuras e índices. Mantener capítulos 1–2, referencias y anexos preparatorios; actualizar campos, renderizar y revisar páginas. El Word queda en la carpeta de tesis; Git recibe la trazabilidad y los hashes, sin el documento académico privado.
3. **Revalidar ingeniería.** Ejecutar controles del núcleo y benchmark apropiados al cambio, suites desde fuentes y recorridos del wheel identificado, en normal y optimizado cuando intervengan rechazos/gates. Preservar fallos y reintentos. Las pruebas nuevas deben comprobar efectos nativos y errores reales; construir o serializar metadatos no prueba automáticamente ejecución.
4. **Cerrar trazabilidad por opción.** Recuperar inventario y catálogo A13 sin alterar sus 8.385 obligaciones. Trabajar por API/familia: casos positivos, negativos y estados no evaluables, con obligaciones exactas. Verificar integridad, contar cada obligación una sola vez y mantener separados casos únicos, plataformas y repeticiones. No asignar a cada parámetro de una firma una prueba que solo importó la función.
5. **Completar plataformas y dependencias.** Ejecutar las celdas originales pendientes de Python/OS/arquitectura y bandas de dependencia, con instalaciones aisladas y hashes. Windows y Linux ARM64 no acreditan macOS ni Linux x64. La VM existente se usa solo con transporte disponible/autorizado y recibos verificables; no crear recursos de pago. Documentar las celdas no ejecutables.
6. **Seguridad y preparación de distribución.** Completar una auditoría Standard y validar hallazgos contra fuente; corregir los validados y probar su regresión. Inventariar dependencias de cada entorno realmente evaluado y consultar avisos primarios actuales. Con decisión de titulares, agregar licencia/notices y reconstruir candidatos. Con cuenta/nombres/roles acordados y tarea explícita de distribución, ejecutar ensayo real y verificar bytes instalados. Los scripts preparados no cuentan como subida a TestPyPI.
7. **Aceptaciones externas y ciencia.** Ejecutar recorridos con lectores/revisores humanos; registrar identidad elegible, dificultades y dictamen. Para la tesis, inventariar corpus, suficiencia real por modelo, grupos/splits, esperado independiente, doble revisión y arbitraje; congelar protocolo y evaluar sobre soportes pareados. Es una fase posterior a este Word sin desarrollo: no insertar resultados inexistentes ni ampliar el alcance científico para sumar puntos.
8. **Consolidar y entregar en Git.** Publicar una matriz actual con fuentes, criterios pendientes y límites de cada medición. Ejecutar navegación documental, pruebas afectadas y `git diff --check`. Hacer commits revisables, subir y verificar `origin/main` y árbol limpio. No ejecutar Actions ni crear servicios como sustituto de validaciones pendientes.

## Bloqueos que no se resuelven con código

P17 y los criterios de licencia no pueden aprobarse sin titulares/licencia. D19/U12 y la aceptación independiente no pueden aprobarse mediante otro agente automático. P18–P20 requieren hechos de distribución públicos y autorizados. T03/T07/T18–T21 exigen datos y validación científica; la instrucción de conservar el documento sin desarrollo limita esta entrega a preparación académica. Estos pendientes permanecen en los denominadores originales. El resultado de esta ejecución indicará lo que se logró, aunque no alcance la meta.

## Entregables verificables

Word solicitado actualizado y respaldo íntegro del original; informe de aportes con ubicación y fundamento; registro de fuentes primarias; controles reales con identidad de candidato; plan de cierre por criterio; matriz de resultados y pendientes; commits entregados en `main`. La calidad editorial del Word se mide por controles propios claramente separados del cumplimiento científico T01–T22.

## Backlog verificable de trazabilidad

El recibo A13 repetido conserva las 4.087 obligaciones sin ejecutar. Agrupadas
por prefijo de su ID: 1.754 parámetros, 1.551 campos, 238 opciones CLI,
226 exportaciones API, 152 métodos, 102 propiedades, 30 comandos CLI,
20 requisitos y 14 dependencias. Son cantidades de obligaciones, no estimaciones
de pruebas nuevas ni resultados positivos. El objetivo requiere verificar 3.668
de ellas manteniendo el inventario completo; los pendientes restantes conservan
su estado incluso si se alcanza el umbral.

| Trabajo de implementación | Obligaciones prioritarias | Evidencia que debe producir |
|---|---|---|
| Drivers revisados para API operativa | `verify` (59), `RunContext` (50), `diff` (48), `run_pipeline` (47), `migrate` (43) | Ejecutar entradas válidas/invalidas, defaults, valores discretos y límites; comprobar estados, conteos, contenido, presupuesto y persistencia con cada ID exacto |
| Contratos de resultados y políticas | `PublishedTable` (40), `ComponentDetectionResult` (38), `ComparisonOptions` (32), `LoadReceipt` (31) | Datos literales independientes y condiciones cruzadas; separar serialización/modelo del efecto de la política en una operación real |
| CLI y distribución | 238 opciones y 30 comandos | Subprocesos del wheel instalado con salida, stderr, exit code y ausencia/presencia de artefactos esperados; no basta que `--help` enumere la opción |
| Extensiones y superficies restantes | APIs, métodos, propiedades, requisitos y dependencias | Adaptador/consumidor revisado, inventario de métodos y perfiles sin extras; ninguna importación prueba por sí misma comportamiento |

El executor de catálogo existente cubre metadatos. Los drivers de operaciones
necesitan un catálogo revisado y recibos específicos antes de agregar su cobertura.
Los 54 casos sintéticos del consumidor ejecutados en esta entrega no se asignan
automáticamente a los parámetros del inventario. Tampoco el recuento de la suite
completa se convierte por inferencia en 95 % de trazabilidad.

## Responsables y dependencias

| Etapa | Responsable necesario | Condición previa | Cierre verificable |
|---|---|---|---|
| Código, herramientas y evidencia local | Equipo técnico del repositorio | Candidato y obligaciones congelados | Cambio revisable, tests apropiados y recibos de identidad |
| Celdas Linux x64 y macOS, Python y extremos de dependencias | Operador de cada entorno por designar | Acceso nativo y autorización del recurso | Misma distribución instalada, con recibo completo de cada celda |
| Derechos y distribución | Titulares y responsables de cuentas por confirmar | Decisión documentada de licencia y condiciones de terceros | P17–P20 y condiciones de publicación satisfechas según sus definiciones |
| Usabilidad, documentación y madurez | Revisor independiente por designar | Artefacto e instrucciones accesibles, consentimiento | U12, D19 y criterios originales de madurez con dictamen real |
| Seguridad | Responsable de seguridad por designar | Resolver Git del plugin corregido y alcance registrado | Análisis completo, hallazgos validados, correcciones y revisión de entrega |
| Experimento y tesis | Equipo investigador y tutor por confirmar | Corpus, derechos, revisores, perfiles y protocolo elegibles | T01–T22 con resultados reproducibles y aceptación académica |

La fecha de estas etapas depende de accesos y decisiones pendientes. No se fija
una fecha ficticia de publicación ni se asigna a una persona una aprobación que
no ha emitido. La autorización de subir cambios a `main` permite integrar esta
entrega técnica; no cierra las condiciones de distribución o de investigación.

## Gate manual de mediciones

En un entorno Python 3.10 o posterior, desde la raíz del repositorio:

```powershell
python tools/target_95.py --output target-gap-new.json --require-target
```

El archivo de salida debe ser nuevo. Exit 0 indica que los registros retenidos
de las nueve áreas alcanzan la meta para el candidato actual; exit 1 conserva un
informe válido que aún no acredita la meta; exit 2 rechaza una entrada o salida
inválida. El control verifica hashes, versiones, conteos y aritmética de las
fuentes originales. No ejecuta pruebas, reevalúa criterios ni otorga aprobación
humana. El informe puede verificarse de nuevo con otro nombre de salida; no se
sobrescribe un recibo previo. Las futuras evaluaciones necesitan nuevos registros
de candidato y fuentes que respeten los mismos contratos de medición.

Los ámbitos aún sin medición requieren definir y aprobar su contrato de
evaluación antes de extender el validador para aceptar sus fuentes numéricas.
El soporte actual de conteos se limita a los seis registros originales medidos;
no inventa un contrato porcentual para madurez, tesis o seguridad.
