# Plan de implementación y verificación de las metas revisadas

Corte: 11 de octubre de 2026. Sustituye la meta anterior de 95 % por las metas
solicitadas de 90/90/80/85/90/90/50. El núcleo y benchmark siguen en
`0.12.0a13`, Alpha privada. Los porcentajes se obtienen del cierre de obligaciones
originales; no se rebajan denominadores ni se sustituyen criterios pendientes.

| Área | Meta | Umbral de la rúbrica conservada | Trabajo y aceptación |
|---|---:|---:|---|
| Universalidad | 90 % | 54 de 60 | Reejecutar perfiles sobre los artefactos A13; completar plataformas, extremos de dependencias, operaciones/tipos y recuperación; revisar cada una de las 60 obligaciones antes de trasladar cifras históricas de A11. |
| Preparación PyPI | 90 % | 18 de 20 | Conservar los 16 controles técnicos; cerrar dos de P17–P20 con decisiones y evidencias reales de derechos, cuentas, documentación pública y ensayo de distribución. |
| Trazabilidad | 80 % | 6.708 de 8.385 | Congelar entradas y oráculos independientes antes de ejecutar; añadir obligaciones todavía no comprobadas, verificar la unión sin duplicados y repetir normal/`-O` y plataformas disponibles sin sumar las repeticiones. |
| Calidad propia | 85 % | 17 de 20 | Conservar los 16 controles del paquete; cerrar uno de Q08/Q11/Q12/Q20 con distribución, dependientes, comunidad o derechos reales. |
| Madurez | 90 % | Al menos 15 de 16: 93,75 % | Reevaluar M01–M16 completos sobre A13; completar paquetes, matriz nativa, recursos, seguridad, recuperación y revisión humana/gobierno. Un subensayo no cierra un criterio de mayor alcance. |
| Cumplimiento tesis | 90 % | Al menos 20 de 22: 90,91 % | Evaluar T01–T22 sin editar el Word. Separar cobertura de ingeniería del corpus, ajuste/calibración, particiones, O, soportes pareados, incertidumbre y reproducción humana. |
| Preparación seguridad | 50 % | 10 de 20 | Usar SEC-PREP-20-v1 congelada; comprobar inventarios y avisos, cadena de construcción y controles. Completar cobertura del análisis, resolver el hallazgo y obtener las decisiones de responsables exigidas. |

La usabilidad conserva su medición de A12 y la documentación su medición sobre
el repositorio A13. No se define una media general entre estas rúbricas.

## Secuencia ejecutable

1. Identificar el checkout, los cuatro artefactos A13 y los recibos anteriores.
   Conservar hashes de distribución y del Word. Separar fuente del repositorio,
   payload instalado, corpus público y documentación de medición.
2. Ampliar el ejecutor de perfiles para aceptar una versión explícita y rechazar
   parejas núcleo/benchmark mezcladas **antes de instalar**. Ejecutar los trece
   perfiles aislados con las dependencias fijadas y guardar comandos, salidas,
   identidad de payload, `pip check` y resultados nativos.
3. Preparar un catálogo incremental de límites, valores finitos y omisiones de
   argumentos. Revisar validadores y serializers antes de admitir un caso.
   Para las omisiones, bloquear la entrada al cuerpo operativo y comprobar la
   invocación Python real. Un error inesperado permanece `FAIL`.
4. Ejecutar y revisar el catálogo congelado normal y `-O`. Rechazar IDs ajenos,
   ya aprobados o repetidos. Mantener separados casos únicos, repeticiones,
   rechazos esperados y obligaciones pendientes. Registrar el déficit exacto
   respecto a 6.708, sin declarar que un caso de metadatos prueba operaciones.
5. Generar inventarios de dependencias de los artefactos, validar los cuatro
   CycloneDX con esquemas locales y cotejar lock, metadatos y hashes. Congelar
   listas de nombres/versiones públicos y planes de consulta antes de consultar
   avisos. No enviar nombres de paquetes privados ni código a los proveedores.
6. Ejecutar en la VM ARM64 las pruebas POSIX omitidas en Windows y el catálogo
   en Python 3.10/3.12, únicamente tras resolver la autorización concreta de
   transferencia. Conservar el rechazo automático mientras siga pendiente;
   no inferir ejecución ni cerrar M02/M13 con un archivo preparado.
7. Reevaluar madurez, tesis y seguridad criterio por criterio. La revisión de
   `mi_dot` es una revisión por agente IA; no sustituye personas, tutor,
   árbitros, titulares ni responsables operativos.
8. Publicar en `main` herramientas, pruebas y resúmenes verificables. Conservar
   recibos completos en un expediente privado con hashes; excluir Word, corpus,
   credenciales, entornos y cachés de Git. Verificar el commit remoto. No ejecutar
   Actions ni publicar en PyPI/TestPyPI como parte de este corte.

## Dependencias para cerrar las metas

Las decisiones de licencia/titulares y las revisiones humanas fueron declaradas
pendientes por el usuario. Una propuesta redactada por IA no es su aprobación.
P17–P20 y Q08/Q11/Q12/Q20 requieren hechos externos; añadir más pruebas no los
cierra. Las plataformas sin runner, las restricciones de datos y la auditoría
incompleta conservan su alcance y estado.

Para T03 se necesita `N_fit` efectivo por familia/modelo, con grupos y exclusiones;
el número de adjudicaciones públicas descargadas no lo sustituye. T07 requiere
revisión ciega A/B y arbitraje real. T19/T20 requieren O confirmado y soportes
regenerables. El piloto técnico SERCOP sirve para comprobar recorridos nativos;
no constituye esos resultados científicos. El Word se conserva intacto.

Cada nuevo cambio de payload exige nuevos artefactos, hashes y comprobaciones
del candidato afectado. No se atribuyen al wheel A13 cambios de herramientas o
documentación posteriores a su construcción.
