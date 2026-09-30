# Plan de Hernán: diez pasos de implementación

Toda la implementación de este plan se encomienda a Sol. El repositorio inicial solo prepara el diseño. Este plan cubre el trabajo de Hernán; no delega en Sol la VM/conector de José ni la construcción del DW de Jhair. El prompt del paso 1 se entrega en el chat y no se guarda aquí.

Cada paso produce código funcional para su alcance, pruebas significativas, documentación y un cambio revisable. No se crean APIs vacías para anticipar pasos posteriores. Los pasos 1 a 8 funcionan con datos sintéticos/locales; 9 y 10 incorporan las entregas reales del equipo.

## Paso 1. Fundaciones Python, contratos y tipos públicos

**Objetivo:** crear una base instalable y estricta, capaz de expresar y validar contratos semánticos sin necesitar la VM.

**Trabajo:** implementar `packages/equiframe` con `pyproject.toml`, estructura `src`, tipado, versiones, errores, modelos inmutables de tipos/contratos y referencias mínimas a artefactos; esquemas JSON generados, políticas explícitas, serialización canónica y validación cruzada. Definir los Protocols de integración que ya puedan expresarse con tipos completos. Añadir un comando real `equiframe contract validate`, entorno aislado, bloqueo reproducible de dependencias de desarrollo y CI Windows/Linux. Crear ejemplos sintéticos de contratos para las cinco familias; no calificarlos como casos científicos revisados.

**Aceptación:** instalar wheel en entorno limpio; importar sin motores/ML; validar ejemplos; rechazar claves inexistentes, esquemas/versiones inválidos, precisión/escala inconsistente, campos desconocidos y coerciones con pérdida. Roundtrip exacto de decimales/tiempo y versiones; hashes estables de metadatos canónicos. Pruebas, tipado, estilo y empaquetado pasan. README contiene comandos realmente ejecutados y soporte comprobado. No ejecutar transformaciones, entrenar modelos ni implementar componentes de compañeros.

## Paso 2. Ejecución y adaptadores nativos

**Objetivo:** ejecutar transformaciones registradas con Pandas, Polars y DuckDB sobre entradas idénticas, como biblioteca general importable mediante `import equiframe as ef` desde otro proyecto.

**Trabajo:** puertos de datos/artefactos locales, registro explícito, `ExecutionPlan/Result`, contexto aislado, capacidades, importación opcional, conversiones fieles y materialización de salidas. Crear transformaciones sintéticas independientes, no conversiones de una salida común. Capturar tiempos/estados y cerrar recursos en fallos. Base útil, extras por motor, intercambio local explícito, salida observada separada del contrato y ejemplos genéricos de dos dominios. Documentar precisión, índices, bases temporales y controles cooperativos/exigibles.

**Aceptación:** cada motor ejecuta código propio; preserva decimal/null/NaN/tiempo o informa incompatibilidad; entradas no se alteran; dos corridas aisladas no mezclan artefactos; fallo, cancelación y ausencia de extra generan diagnóstico verificable. Sin conexiones globales.

## Paso 3. Normalización y comparación exacta

**Estado:** implementación funcional en 0.3.0, con API, pruebas, ejemplos y consumo
del wheel fuera del checkout. [Semántica](COMPARISON.md) y
[verificación de entrega](STEP_03_REVIEW.md). La revisión científica O sigue pendiente.

**Objetivo:** comprobar contenido completo y localizar diferencias autorizando solo equivalencias del contrato.

**Trabajo:** igualdad de esquema, alineación por clave comprobada, comparación de multiconjuntos y secuencias, tolerancias justificadas, decimales, ausencias y tiempo. Estrategia por lotes/particiones con spill y límites; evidencia de diferencias.

**Aceptación:** detecta intercambio de montos conservando total, pérdida de duplicados y cambios de zona; acepta permutaciones solo cuando corresponde; no declara igualdad por hashes/muestra; informa comparación incompleta por recursos. Pruebas por propiedades y esperados independientes cubren las cinco familias.

## Paso 4. Reglas operativas R y catálogo de contratos

**Objetivo:** disponer de una línea base determinista separada del comparador.

**Trabajo:** registro de reglas de esquema, claves, cardinalidad, ausencias, conversiones y reconciliación seleccionada por contrato. Condiciones de aplicabilidad, evidencia observada/esperada y agregación de decisiones. Formalizar contratos de transformaciones antes de generar mutantes finales.

**Aceptación:** R funciona sobre una ejecución sin otro motor/etiquetas; controles correctos difíciles no fallan indebidamente; reglas faltantes/no evaluables no se convierten en éxito; cada alerta localiza causa. Congelar y registrar revisiones de R usadas por el benchmark.

## Paso 5. Perfiles por familia y preprocesamiento

**Objetivo:** producir features reproducibles con denominadores y soporte explícitos.

**Trabajo:** implementar fórmulas de sección 3.6 por columna/familia, indicadores de no aplicabilidad, metadatos separados, orden fijo y preprocesador ajustado solo con entrenamiento normal. Comprobar ausencia de fuga e incompatibilidades de feature version.

**Aceptación:** vacíos/cero/NaN/ausencia se distinguen; denominadores correctos; imputación se mantiene al puntuar; no hay etiquetas, IDs, mutación, motor ni partición dentro de la matriz; M/B reciben exactamente el mismo preprocesamiento. Ningún perfil usa otra salida de motor.

## Paso 6. Oráculo, catálogo y particiones independientes

**Objetivo:** disponer de un benchmark trazable antes de ajustar detectores.

**Trabajo:** crear distribución `equiframe-benchmark`; catálogo de cinco familias, resultados esperados independientes, mutaciones candidatas, controles correctos, registro de revisión ciega y estados pendientes. Construir grupos por dependencias transitivas, splits por grupos y validación de fuga. Meta 60 escenarios/300 perfiles sujeta a evidencia; desarrollar equivalentes por motor necesarios.

**Aceptación:** etiquetas no proceden de detectores; mutante sin efecto reconocido; revisores/autores controlados; ningún grupo cruza particiones. Mostrar cantidad real por familia/partición y pendientes, sin inventar aprobaciones. Catálogo técnico puede completarse mientras las revisiones humanas siguen pendientes; el cierre científico requiere esas revisiones.

## Paso 7. Isolation Forest, MAD, calibración e híbrido

**Objetivo:** implementar M, B y H con estados estadísticos y técnicos correctos.

**Trabajo:** ajuste normal por familia, soporte/variación, bundles compatibles, score M con signo definido, MAD y casos MAD=0, cuantiles sin interpolación, alpha explícito y tabla completa H. Persistencia segura y versionada; no entrenar/calibrar con prueba.

**Aceptación:** score igual al restaurar bundle; umbral calculado exactamente; igualdad con umbral no alerta; umbral infinito MAD informa no estimable; nueve combinaciones de H correctas; desajuste de features/versiones rechazado. Alpha y tamaño de calibración no se presentan como garantía empírica sin soporte.

## Paso 8. Orquestación completa, evidencia y CLI

**Objetivo:** ofrecer una experiencia coherente para scripts, notebooks y automatización.

**Trabajo:** integrar ejecución/R/perfil/M/B/H y comparación opcional; manifiestos append-only, logs estructurados, reporte JSON/HTML, códigos de salida y comandos de benchmark. Reductor de casos con presupuesto y preservación de precondiciones/fallo. Documentar ejemplos y API extensible.

**Aceptación:** una corrida se explica desde sus artefactos; errores dejan evidencia sin éxito falso; HTML escapa entradas; secretos excluidos; relanzar no sobrescribe corrida anterior; reducción informa límite y no afirma mínimo global. Ejemplos usan paquetes instalados.

## Paso 9. Integración real con José y Jhair

**Objetivo:** conectar EquiFrame con snapshots y transformaciones reales manteniendo responsabilidades.

**Trabajo de Hernán:** adaptador consumidor del cliente de José, escenarios SERCOP basados en contratos de Jhair, ejecución comparable entre motores y reportes de reconciliación. Probar esquemas/hashes/versiones/cancelación y comparar outputs del DW sin administrar el servicio ni cambiar su modelo unilateralmente.

**Dependencias:** cliente autenticado y snapshots de José; DDL, entradas/salidas/mapeos y reconciliación de Jhair. Si faltan, completar pruebas locales de conformidad y registrar el bloqueo de integración real; no simular que se probó la VM.

**Aceptación:** misma entrada verificable para tres motores; monto único por adjudicación, monedas separadas y claves/fechas según contrato; evidencia real de incompatibilidades; publicación del DW sigue bajo controles de Jhair/José. Se verifica lectura estable durante carga con las pruebas del servicio, no se atribuye esa funcionalidad al núcleo.

## Paso 10. Congelación, evaluación y entrega reproducible

**Objetivo:** entregar software utilizable y evidencia defendible para la tesis.

**Trabajo:** preparar distribución pública: licencia acordada, nombre de paquete disponible o bajo control del equipo, metadatos completos, versiones soportadas y publicación verificable en PyPI con autorización expresa de los autores. Resolver decisiones metodológicas, congelar manifests, ejecutar R/M/B/H en prueba, métricas pareadas/cobertura, incertidumbre por grupos si procede, costos controlados y tablas regenerables. Medir recursos, revisar API/documentación, construir distribuciones y bundle de reproducción; repetición independiente por compañero.

**Aceptación:** comparación principal usa misma intersección evaluable; métricas indefinidas explícitas; no se ajusta con prueba; resultados negativos se conservan; otro integrante reproduce contenido y decisiones. Wheel/sdist y dependencias exactas comprobados; soporte ARM64 solo si probado. Release etiquetado y publicación pública verificable después de acordar licencia/nombre y autorización; un consumidor instala la versión publicada con pip y ejecuta ejemplos. Hasta entonces no se afirma que pip install equiframe obtenga el paquete del equipo. Capítulos 4/5 se redactan con resultados reales.

## Dependencias entre pasos

Desde el paso 3, cada incremento verifica consumidores externos del wheel local.
En el paso 10 se mantiene la aceptación pública final: `pip install equiframe`
desde PyPI e `import equiframe as ef`, sin acceso al repositorio privado y dentro
del soporte documentado. Pendientes: licencia, control del nombre, metadatos públicos
y ampliación de versiones Python respaldada por CI; actualmente `>=3.12,<3.13`.

`1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10` es el orden de entrega. Las revisiones humanas del catálogo y las entregas de compañeros deben coordinarse antes del paso 9; los metadatos de evidencia se introducen desde el paso 1 y se completan en 8. Ajustes del borrador se registran durante el piloto y no requieren rehacer infraestructura si se respetan las interfaces.
