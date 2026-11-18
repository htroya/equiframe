# Estado consolidado tras la validación VM autorizada

Corte: 11 de octubre de 2026. **Núcleo/benchmark 0.12.0a13, Alpha privada**.
El [resultado estructurado](PROJECT_STATUS_MATRIX_20261011_VM.json) conserva
versiones, rúbricas y hashes. Las metas solicitadas siguen pendientes; el
[plan](IMPLEMENTATION_PLAN_TARGETS_20261011.md) conserva sus umbrales.

| Aspecto | Meta solicitada | Medición respaldada |
|---|---:|---|
| Usabilidad técnica | Sin cambio en esta petición | **91,67 % — 11/12, A12** |
| Universalidad técnica | 90 % | **80 % — 48/60, A11**; reevaluación completa A13 pendiente |
| Preparación PyPI | 90 % | **80 % — 16/20, A13** |
| Documentación profesional | Sin cambio en esta petición | **90 % — 18/20, repositorio A13** |
| Trazabilidad por opción | 80 % | **65,78 % — 5.516/8.385, A13** |
| Calidad propia del paquete | 85 % | **80 % — 16/20, A13** |
| Madurez: cierre estricto M01–M16 | 90 % | **25 % — 4/16, A13** |
| Cumplimiento de requisitos de tesis | 90 % | **40,91 % — 9/22, A13** |
| Preparación técnica en seguridad | 50 % | **35 % — 7/20, A13** |

La autorización específica resolvió el bloqueo del envío a la VM. Los
[32 casos POSIX y cuatro recorridos del catálogo](VM_TARGET_FOLLOWUP_20261011.md)
pasaron; se cotejaron los IDs omitidos en Windows y los mismos resultados del
catálogo. Eso cierra M02 y lleva la [madurez](MATURITY_VM_RESULT_20261011.json)
de 3/16 a 4/16. No suma puntos de trazabilidad por repetir.

La [ampliación completa en ARM64](VM_FULL_VALIDATION_20261011.json) obtuvo
8.077 PASS del núcleo y 625 PASS aplicables del benchmark. Quedan dos pruebas
propias de Windows; tres omisiones de configuración fuente se resolvieron con
la pareja original de sdists y sus expectativas intactas.

Faltan **1.192 obligaciones adicionales** para trazabilidad 80 %. Universalidad
requiere reevaluar los 60 criterios y completar plataformas, perfiles/extremos
y condiciones externas. PyPI necesita dos cierres reales entre derechos,
cuentas, documentación pública y distribución; calidad necesita uno entre
distribución, dependientes, comunidad y derechos.

Madurez conserva su alcance integral: para ≥90 % requiere 15/16 = 93,75 %.
Tesis requiere 20/22 = 90,91 % y conserva los pendientes científicos/humanos;
su porcentaje no representa calidad editorial ni aprobación académica.
Seguridad requiere 10/20 para 50 %: la auditoría sigue parcial, con un hallazgo
bajo Windows abierto y puertas de responsables/revisión humana pendientes.

No se calcula un promedio de estas rúbricas. Las cifras A11/A12 se conservan
como históricas y no se trasladan automáticamente a A13. La [matriz previa](PROJECT_STATUS_MATRIX_20261011_FOLLOWUP.md)
y su evidencia permanecen identificadas.

El Word no se editó. No se ejecutaron Actions, se crearon recursos de pago ni
se publicó el paquete en PyPI/TestPyPI. La revisión IA no sustituye personas.
