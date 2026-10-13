# Plan pendiente de Beta privada

Encargo del propietario: maximizar el avance comprobable, preparar e implementar
una Beta privada, organizar SERCOP 2025 localmente y entregar a `main`.
La versión activa sigue siendo **núcleo y benchmark 0.12.0a13 (Alpha privada)**.
Por instrucción del propietario, primero se debe agotar el trabajo comprobable
para llevar Alpha al 100 %. La Beta está aplazada. El identificador `0.12.0b1`
es una propuesta futura: no hay artefactos Beta construidos, instalados ni
publicados en esta entrega. Los cambios de identidad preparados se conservaron
fuera de Git y se retiraron de la fuente activa. No se publica en
PyPI/TestPyPI, no se ejecutan Actions, no se crean recursos de pago, no se
reanuda el trabajo cancelado y no se modifica el Word.

## Alcance y aceptación

El orden obligatorio empieza por el
[plan de maximización de Alpha](ALPHA_MAXIMIZATION_PLAN_20261012.md).
Antes de retomar esta propuesta se debe comprobar su lista técnica, conservar
cada resultado fallido o pendiente y explicar cuáles cierres dependen de
personas o infraestructura. No se declara 100 % con criterios parciales, ni se
usa el cambio de etapa como sustituto de un cierre. La preparación de este
plan y de una herramienta de instalación no activa una Beta.

La Beta es un piloto de ingeniería de las API implementadas: contratos,
comparación, ejecución nativa, Verify, migración, evidencias y benchmark.
La admisión declarada conserva Python 3.10–3.13; cada plataforma y perfil se
anuncia como comprobado únicamente después de su ejecución real. Las celdas
Linux/macOS pendientes se conservan. La licencia, aceptación humana, servicio/DW
del equipo y evaluación científica tienen cierres propios.

Cambiar el sufijo de versión no demuestra madurez. La activación local exige
identidad de versiones, artefactos íntegros, instalación independiente, pruebas
aplicables, recorridos normales y optimizados, y recuperación comprobada. Un
artefacto que falle permanece como intento fallido y no se activa como válido.

| Fase | Implementación | Evidencia exigida |
|---|---|---|
| 0. Maximizar Alpha | Ejecutar primero todo lo viable del plan Alpha y registrar los pendientes externos | Lista de cierres con recibos, fallos conservados y causas verificadas; fase todavía abierta |
| 1. Conservar A13 | Mantener sus seis artefactos, recibos y fuentes originales | SHA-256 originales; ninguna sustitución |
| 2. Identidad Beta | Versiones/pins alineados, productor de detectores compatible con historial, changelog y diagnóstico de etapa | Metadatos, lock y regresiones de identidades antiguas/nuevas |
| 3. Distribución privada | Construir wheel/sdist desde fuente Git identificada; catálogo privado de archivos y dependencias | Hashes, RECORD, metadatos y reconstrucción comprobados |
| 4. Instalación y uso | Entorno aislado fuera de fuente, API/CLI, tres motores nativos y benchmark | `pip check`, rutas instaladas, esperados previos, estados y lectura de resultados |
| 5. Regresión | Suites completas aplicables y comprobaciones optimizadas | JUnit, logs, omisiones justificadas y hashes de artefactos |
| 6. Recuperación | Actualizar/reinstalar sin cambiar evidencia anterior; fallo deja vigente la instalación validada | Recibos de transición y readback de contenidos |
| 7. Datos locales | Organizar todas las fuentes SERCOP 2025 y proyecciones completas en `local-data/sercop/2025` | Procedencia, hashes, conteos, esquema, ausencias y precisión |
| 8. Porcentajes | Ejecutar nuevos casos, unir IDs únicos, revisar cierres completos y recalcular | Fuentes por candidato; ninguna transferencia automática A13→Beta |
| 9. Entrega | Publicar código/documentación/agregados en `main` | Commit remoto coincidente y worktree limpio; datos/entornos privados excluidos |

## Aumentar las mediciones

El corte A13 actual es 11/16 en madurez, 9/22 en requisitos de
tesis y 6.309/8.385 en trazabilidad. Para ≥90 % hacen falta 15/16, 20/22 y
7.547/8.385. Para 100 % debe cerrarse cada obligación original.
Los nuevos ensayos sólo suman tras ejecutarse y cumplir su criterio completo.

Queda M04 de compatibilidad por plataformas/perfiles restantes. Los cierres
M05/M07/M11/M12/M13/M14 tienen recibos concretos actuales. Las 2.076
obligaciones de trazabilidad pendientes requieren observación y esperados
independientes; no basta anotación, repetición o configuración de una matriz.

El trabajo científico genera preparación y ensayos explícitos. No sustituye
etiquetas humanas, aprobación de cohorte/normalidad, decisiones de dominio ni
reproducción de otro integrante. Los requisitos que necesitan esas evidencias
permanecen pendientes hasta recibirlas realmente.

## Estado de la VM

M13 terminó y su expediente completo se devolvió y verificó. La
[entrega SERCOP pública](SERCOP_PUBLIC_DELIVERY_20261012.md) fue autorizada
y está disponible en lectura. Los [pendientes reales](VM_PENDING_WORK_20261012.md)
conservan las plataformas, ciencia y componentes del equipo aún abiertos.

El kit r2 local conserva SHA-256
`354c704a5d760b8295031a1a966c135c3e41d111327cce97ad10180799d87e63`.
Ese kit verifica **A13**; no acredita la futura Beta. La Beta requiere un
expediente distinto, con sus propias versiones, artefactos y recibos.

Las listas de decisiones y evidencias externas se desarrollan en
[requisitos humanos](HUMAN_REQUIREMENTS_20261012.md).
