# Estado consolidado de las ocho áreas vigentes

El propietario retiró un área del tablero el 11 de octubre de 2026. Las ocho
áreas vigentes conservan sus criterios, denominadores y candidatos; la
[matriz histórica de nueve áreas](PROJECT_STATUS_MATRIX_20261011_GLOBAL75.md)
permanece como registro anterior. El núcleo y benchmark siguen siendo
**0.12.0a13, Alpha privada**.

| Área | Medición respaldada | Meta vigente |
|---|---:|---:|
| Usabilidad | **91,67 % — 11/12, A12** | Reevaluación A13 pendiente |
| Universalidad | **80 % — 48/60, A11** | 90 % solicitado; reevaluación A13 pendiente |
| Preparación PyPI | **80 % — 16/20, A13** | 90 % |
| Documentación | **90 % — 18/20, repositorio sobre A13** | Pendientes humanos y públicos conservados |
| Trazabilidad | **71,25 % — 5.974/8.385, A13** | **≥85 %**, faltan 1.154 IDs |
| Calidad del paquete, rúbrica propia | **80 % — 16/20, A13** | 85 % |
| Madurez | **31,25 % — 5/16, A13** | **≥80 %**, faltan 8 criterios completos |
| Cumplimiento de requisitos de tesis | **40,91 % — 9/22, A13** | **≥80 %**, faltan 9 requisitos completos |

El corte actualizado del 12 de octubre conserva los siete porcentajes anteriores.
El promedio exacto de las ocho áreas es **70,6340038353 %, redondeado 70,63 %**.
La [matriz JSON](PROJECT_STATUS_MATRIX_20261011_EIGHT.json) vincula cada cifra a
su fuente y hash; el [recibo del promedio](GLOBAL_EIGHT_RESULT_20261011.json)
conserva su fracción exacta. No es comparable como incremento técnico con el
66,43 % anterior, cuyo promedio incluía nueve áreas. El cambio de alcance y
las 74 obligaciones de tipos, 42 de fronteras, 40 de configuración y 32 de
propiedades se registran por separado.

El [plan actual](TARGET_80_85_PLAN_20261011.md) define desarrollo, validación,
evidencias externas y entrega a `main`. La
[ampliación de tipos públicos](OPTION_PUBLIC_TYPES_RESULT_20261011.md) y las
[fronteras exactas de fixtures originales](OPTION_SEED_BOUNDS_RESULT_20261012.md)
y la [admisión de configuración opcional](OPTION_CONFIGURATION_RESULT_20261012.md)
y la [lectura de propiedades públicas](OPTION_PROPERTIES_RESULT_20261012.md)
están ejecutadas y verificadas. El [ensayo anual completo de SERCOP en la VM](SERCOP_ANNUAL_VM_20261011.md)
terminó con 81 comprobaciones aprobadas, incluidas 27 sobre todas las
adjudicaciones. Sus repeticiones no añaden puntos automáticos a estas rúbricas.

El [kit M13 sellado](M13_PREPARATION_20261012.md) está preparado localmente;
la transferencia específica y ejecución ARM64 siguen pendientes de autorización.
La colección de pruebas y preparación del kit no suman criterios cumplidos.

Las versiones A11/A12 conservan sus porcentajes históricos. Los pendientes de
derechos, responsabilidades, otras plataformas y revisiones humanas no se
reemplazan por revisores IA. Las comparaciones técnicas de SERCOP no acreditan
corpus efectivo de aprendizaje, oráculo humano ni aceptación científica.

`tesis_corregda_v1.docx` mantiene SHA-256
`883b187f08221b9b4abab775430d9a2c87b6d92f503494317f3e1fec214d0f3c`.
No se publica en PyPI/TestPyPI, no se ejecutan Actions ni se crean recursos de pago.
