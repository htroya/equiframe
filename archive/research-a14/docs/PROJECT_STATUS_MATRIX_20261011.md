# Estado consolidado tras el seguimiento del 11 de octubre

EquiFrame y benchmark siguen en **0.12.0a13, Alpha privada**. El
[resumen estructurado](PROJECT_STATUS_MATRIX_20261011.json) conserva las nueve
áreas, versiones, denominadores, fuentes y hashes. La
[consolidación anterior](PROJECT_STATUS_MATRIX_20261010.md) permanece histórica.
No hay una rúbrica de porcentaje global; **no se alcanzó 95 % en todas las áreas**.

| Aspecto | Última medición respaldada | Avance / límite de este seguimiento |
|---|---|---|
| Usabilidad técnica | **91,67 % — 11/12, A12** | U12 humano pendiente; no se transfiere la nota al A13 |
| Universalidad técnica | **80 % — 48/60, A11** | Nuevos casos A13 en Windows y ARM64; no reevalúan las 60 obligaciones completas |
| Preparación para PyPI | **80 % — 16/20, A13** | Propuesta de licencia y corrección del workflow; derechos, cuentas, documentación pública y ensayo TestPyPI pendientes |
| Documentación profesional | **90 % — 18/20, repositorio sobre A13** | Seguimiento y navegación técnica nuevos; lector humano y publicación con derechos siguen pendientes |
| Trazabilidad por opción | **53,00 % — 4.444/8.385, A13** | 146 obligaciones nuevas verificadas; [recibos](OPTION_TRACE_INCREMENTAL_20261011.json) |
| Calidad del paquete, rúbrica propia | **80 % — 16/20, A13** | No se acreditan publicación, usuarios externos, comunidad o licencia con revisores IA |
| Madurez | **Sin porcentaje de cierre vigente de A13** | Nueva evidencia técnica acotada; M01–M16 conservan condiciones de totalidad, derechos, gobierno y revisión humana |
| Cumplimiento de la tesis | **Sin porcentaje acreditado** | Corpus público y piloto real adquiridos; `N_fit`, O humano, evaluación y aprobación siguen pendientes |
| Preparación en seguridad | **Sin porcentaje acreditado para el producto completo** | Auditoría estática de snapshot y consultas de entorno; un hallazgo Windows abierto y alcance pendiente explícito |

La trazabilidad suma **1.774 PASS + 2.670 EXPECTED_REJECTION = 4.444**; quedan
**3.941 NOT_RUN**. Para alcanzar al menos 95 % con el mismo denominador se
necesitan 7.966 obligaciones verificadas: faltan **3.522 adicionales**. El
resultado combina 3.445 casos anteriores y 139 nuevos distintos; dos regresiones
y las repeticiones normal/optimizada/VM no incrementan la cobertura.

De las obligaciones añadidas, 128 son límites de metadatos y 18 corresponden a
operaciones nativas/API. No constituyen cobertura de líneas ni una prueba de
todas las interacciones. Las cuatro ejecuciones ARM64 y dos repeticiones tras
actualizar una herramienta de construcción coinciden con Windows; no acreditan
macOS, Linux x64, Python 3.11/3.13 ni extremos de todas las dependencias.

El [seguimiento](FOLLOWUP_95_RESULT_20261011.md) explica qué se ejecutó en cada
pendiente. La [propuesta de licencia](LICENSE_PROPOSAL_20261011.md) no concede
derechos, y la [segunda revisión automatizada](AUTOMATED_REVIEW_20261011.md) no
sustituye personas. El [piloto SERCOP](SERCOP_PUBLIC_PILOT_20261011.md) no ajustó
modelos ni modificó el Word. La [auditoría de seguridad](SECURITY_FOLLOWUP_20261011.md)
identifica el snapshot y los límites de sus resultados.
