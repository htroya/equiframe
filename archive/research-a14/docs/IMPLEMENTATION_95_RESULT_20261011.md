# Resultado de la implementación y validación hacia el 95 por ciento

Fecha: 11 de octubre de 2026. Candidato privado núcleo/benchmark `0.12.0a13`.
**La meta de 95 % en las nueve áreas no está acreditada.** Se completaron la
edición preparatoria del Word, el plan por criterio, un validador de brechas,
la corrección del workflow manual y las comprobaciones técnicas siguientes.
El usuario confirmó pendientes derechos y revisión independiente/resultados
científicos aprobados. Se conservan las cifras originales y sus versiones.

## Qué cambió

La [revisión de aportes](THESIS_CONTRIBUTIONS_REVIEW_20261011.md) documenta la
selección de la alternativa, correcciones y fundamentos añadidos a la tesis.
El Word solicitado, de 148 páginas, conserva su modelo y no añade desarrollo
ni resultados científicos. Se entrega en su carpeta original y queda fuera de
Git, con respaldo y controles privados.

El [plan](IMPLEMENTATION_95_PLAN_20261011.md) fija umbrales originales, backlog,
responsables por confirmar, evidencias y dependencias. `tools/target_95.py`
verifica hashes, versiones, conteos de fuentes, aritmética y presencia de las
nueve áreas. El [informe de brechas](TARGET_95_GAP_20261011.json) conserva una
medición ausente como null y A11/A12 como históricos. Exit 1 al exigir la meta
es el resultado esperado; no se atribuye un 95 % por generar el informe.

Se corrigieron 15 referencias a artefactos A10 en el workflow manual de release,
ahora ligadas a A13. Los gates optativos y permisos de lectura se conservan.
No se ejecutó Actions. SDK, benchmark y distribuciones originales no cambian.

## Comprobaciones nuevas

| Control | Resultado y alcance |
|---|---|
| Suite completa del núcleo instalado | 8052 PASS, 25 SKIP, 0 fallos; 8077 nodeids distintos |
| Suite completa del benchmark instalado | 620 PASS, 7 SKIP, 0 fallos; 627 nodeids distintos |
| Herramientas de raíz | 63 PASS y 9 SKIP en normal; los mismos controles en optimizado; 16 pruebas nuevas del validador incluidas |
| Estática de archivos Python nuevos | Ruff, formato y mypy estricto del validador: PASS |
| Ejemplos del texto documental | 4 ejemplos distintos, 8 intentos normal/optimizado: PASS |
| Navegación documental | PASS; documentos, destinos, anclas, versiones y alcance identificados en el recibo JSON |
| Consumidor privado 0.1.15 | 54 casos sintéticos de finanzas/retail/telemetría, 72 ejecuciones nativas, 18 casos aceptados; controles de fallos: PASS |
| Identidad instalada | Payloads exactos de los tres wheels comprobados; versiones 0.12.0a13/0.12.0a13/0.1.15 |
| Preparación de distribución | Auditoría de los cuatro artefactos y twine estricto: PASS; exit 3 del preparador conserva publicación bloqueada |
| Entorno aislado | Windows x64, Python 3.12.4; dependencias permitidas resueltas; pip check: PASS |
| Word | Tema, fuente, dos secciones, 20 tablas, 18 recursos gráficos y leyendas conservados; índices actualizados; 148 páginas revisadas |

Se repitió el catálogo A13 en normal y optimizado: 3.445 casos únicos y
4.298/8.385 obligaciones verificadas (51,26 %). No añade cobertura. Recibos
de metadatos no prueban operaciones nativas ni sus interacciones; la suite y
los casos del consumidor no se asignan automáticamente a esas obligaciones.

Los [resultados JSON](IMPLEMENTATION_95_RESULT_20261011.json) conservan conteos,
hashes, versiones y límites. Los stdout, stderr, JUnit, corpus, inventarios de
entorno, Word y QA quedan privados en `revision_95_20261011`, fuera del repositorio.
Se conservan los artefactos identificados y se retiran los dos entornos temporales
creados para esta validación después de completar sus comprobaciones.
Los intentos iniciales no se borran ni se cuentan como suites completas aprobadas.

## Fallos conservados y límites

Dos intentos del núcleo se interrumpieron sin JUnit final. El segundo diagnosticó
la espera en `tempfile.mkstemp` de la caché de constantes de Hypothesis. La
ejecución final usa una carpeta propia mediante `HYPOTHESIS_STORAGE_DIRECTORY`,
semilla `20261011` y temporales nuevos, sin cambiar aserciones ni excluir casos.

El primer intento de herramientas con `-I` perdió el import del módulo local
`tools`. El intento normal detectó el defecto real de nombres A10 del workflow;
se corrigió y las pruebas normal/optimizada pasaron. La auditoría de dependencias
contra `uv.lock` rechazó el entorno porque sus versiones resueltas permitidas
difieren del lock. Se conserva el inventario de entorno, sin presentarlo como
SBOM ligado al lock ni como consulta actual de vulnerabilidades.

El [intento de seguridad](SECURITY_SCAN_BLOCKER_20261011.md) no inició revisión
del código: resolver Git del plugin y cobertura de cero archivos. No significa
ausencia de vulnerabilidades. La seguridad sigue sin porcentaje acreditado.

## Estado por área y continuación

| Área | Última medición conservada | Pendiente para acreditar la meta |
|---|---|---|
| Usabilidad | 91,67 % A12 | Revisión completa A13 y U12 humano |
| Universalidad | 80 % A11 | Revisión A13, plataformas/matriz/semántica y aceptación pendientes |
| PyPI | 80 % A13 | Derechos, cuentas/roles, documentación pública y ensayo real |
| Documentación | 90 % repositorio sobre A13 | D19 lector independiente o D20 público con derechos aprobados |
| Trazabilidad | 51,26 % núcleo A13 | Al menos 3.668 obligaciones adicionales realmente verificadas |
| Calidad | 80 % A13 | Distribución, adopción, comunidad y licencia pendientes |
| Madurez | Sin evaluación vigente A13 | Aplicar M01–M16; 15/16 es 93,75 %, no 95 % |
| Tesis | Sin porcentaje científico acreditado | T01–T22 con corpus, perfiles, revisores, experimentos y aceptación académica |
| Seguridad | Sin porcentaje acreditado | Resolver plugin, auditoría completa, dependencias y responsable/canal/revisión |

Estas ejecuciones no constituyen reevaluación integral de las nueve rúbricas.
La integración autorizada en main publica código y documentación privados;
no publica en PyPI/TestPyPI ni concede derechos o aceptación científica.
No se modificó la VM ni se crearon recursos de pago. No hay promedio global.
