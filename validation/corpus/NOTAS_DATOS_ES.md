# Datos públicos: nueva captura parcial, 7 de octubre de 2026

Estado: NEW_CAPTURE_PARTIAL. Los archivos están congelados para reproducción offline. Este respaldo no certifica todavía la ejecución del consumidor ni la validación final de EquiFrame. No reproduce las 381 filas históricas cuyos bytes se perdieron.

## Contenido y selección

- Finanzas: FiscalData del Departamento del Tesoro, 17 tasas de interés promedio con fecha 2025-12-31. El JSON y su metadato se conservan completos. Leer las tasas como Decimal directamente de texto, sin conversión intermedia a float. Son porcentajes, no importes monetarios. La identidad declarada es (record_date, security_type_desc, security_desc). Incluye filas Total: las tasas no son aditivas.
- Geofísica: catálogo USGS, 150 eventos de magnitud >= 4 ordenados por tiempo. La consulta pidió 1–8 de enero de 2025 y alcanzó el límite de 150: la captura llega solamente hasta 2025-01-03T16:20:17.862Z. No representa una semana completa. Conservar id, net, time UTC y mag.
- Demografía: Census NST-EST2025-ALLDATA, Vintage 2025, publicado en enero de 2026. El CSV original tiene 66 filas y se conserva completo. population.csv selecciona las 52 filas SUMLEV=040, ordenadas por STATE: 50 estados, DC y Puerto Rico. population_start corresponde a POPESTIMATE2024 (1 de julio de 2024); population_end a POPESTIMATE2025 (1 de julio de 2025), ambos de la misma edición. STATE conserva ceros iniciales y REGION conserva X para Puerto Rico.

Total efectivo de entrada: 219 registros (17 + 150 + 52); originales descargados: 233 registros (17 + 150 + 66). Estos recuentos tienen ámbitos distintos.

## Origen, condiciones y límites

provenance.json registra URL, instante UTC, edición, selección exacta, esquema, recuentos y SHA-256. conditions.json contiene las fuentes primarias y límites de verificación. USGS solicita crédito; Census favorece reutilización y cita. La política oficial indexada de FiscalData describe los datos abiertos como gratuitos para uso y descarga, pero sus páginas completas de API/acerca/política devolvieron HTTP 403: no se afirma haber verificado la redacción íntegra vigente. Los términos de TreasuryDirect no se trasladan automáticamente a FiscalData. No se crearon cuentas, claves ni acuerdos nuevos.

La API de Census devolvió HTML «Missing Key», aunque HTTP fuera 200. Ese cuerpo se conserva en failed-attempts/census-api-missing-key.html, con cero filas válidas. El CSV exitoso se ofrece por separado en la página oficial de descargas; no se eludió la exigencia de clave de la API. Los encabezados Set-Cookie se omiten de los recibos por higiene de credenciales; los cuerpos de datos no fueron modificados.

Las cifras reales no aportan etiquetas de verdad del negocio. La igualdad entre motores y las invariantes aritméticas prueban contratos declarados, no la verdad independiente de estimaciones o eventos. No hay mutaciones en este conjunto; deben crearse fuera de él. No subir estos datos al Git del proyecto.

## Reproducción

Copiar el directorio completo. Verificar manifest.json y sus SHA-256 antes de consumir. Para regenerar la selección, ejecutar con la biblioteca estándar: python derive_population.py raw/population.csv /ruta/nueva/population.csv. El destino debe no existir. No hace consultas de red ni invoca EquiFrame.
