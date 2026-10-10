# Usabilidad para arquitectura y ciencia de datos: revisión vigente

Fecha: 2026-10-10. Base: `dcb35d52d86a5dac0ead324824ed265ff729c8e2`.

La tabla del chat no identifica candidato, rúbrica ni recibos y no permite
acreditar un 80 %. Git conserva una evaluación técnica A7 de **11/12 = 91,67 %**,
con U12 humano pendiente. Ese resultado histórico no es automáticamente una
evaluación de A11 ni de los nuevos bytes. No se inventa un incremento de 80 a 90.

## Medición y aceptación antes de implementar

Se conservan los doce criterios y las 72 subcomprobaciones de
[USABILITY_MATRIX](USABILITY_MATRIX.md). Cada criterio completo vale un punto;
parcial, pendiente o bloqueado vale cero. Objetivo: al menos **11/12 (91,67 %)**,
porque esta rúbrica no tiene un escalón de exactamente 90 %. No se cambian pesos,
no se elimina U12 y no se atribuyen porcentajes de satisfacción humana.

La revisión distingue evidencia histórica por identidad, comprobaciones nuevas
del candidato y comprobaciones pendientes. Los entornos nuevos son Windows x64
Python 3.12 y, si la conexión y el intérprete existente lo permiten, Linux ARM64
en la VM ya disponible. No se atribuyen nuevas ejecuciones Linux x64, macOS,
otras versiones Python ni todos los extremos de dependencias. El porcentaje
U01–U12 es de tareas técnicas; esas plataformas conservan su propia matriz.

Brechas confirmadas antes de editar: README e instalación remiten a A10 mientras
main entrega A11; las guías por rol aún remiten a candidatos/consumidores antiguos;
no hay comando para diagnosticar el entorno ni para ejecutar un primer ejercicio
por rol sin copiar un bloque largo. El entorno de desarrollo conserva metadatos
0.11.1 aunque importa código A11: hay que detectar y corregir esa confusión.

## Cinco pasos

1. **Auditar y fijar evidencia.** Conservar la evaluación A7 y contrastar sus
   criterios con código, guías, recibos A11 y pruebas actuales. Publicar estados
   sin trasladar resultados entre artefactos por compartir número de versión.
2. **Hacer coherente la instalación.** Alinear los documentos vigentes, la pareja
   core/benchmark y sus locks con el nuevo candidato privado. Verificar wheel y
   sdist e instalación normal y con hashes fuera del checkout. Conservar las
   secciones históricas y sus hashes; no publicar en PyPI.
3. **Diagnosticar sin configurar.** Añadir `equiframe doctor` para comprobar el
   minor Python, identidad código/metadatos y disponibilidad de las dependencias
   del extra elegido. Mostrar siguiente acción y JSON utilizable. Sin instalar,
   red, importación de motores o certificación de compatibilidad binaria.
4. **Acortar los dos recorridos.** Añadir `equiframe demo` con SQL para arquitecto
   y preparación Decimal/UTC/ID/NULL para científico. Casos equivalente, diferente
   y no evaluable; esperado literal independiente, reportes antes del gate,
   salida 0/1/3 y rechazo de sobrescritura también con Python `-O`. Incluir una
   guía breve en español e inglés y las recetas largas como integración real.
5. **Validar y entregar.** Ejecutar controles afectados de API/CLI/semántica,
   documentación, distribución y consumidores; revisar HTML con Opera Neon
   cuando conecte. Publicar resultado con evidencia y límites e integrar en
   main, según la autorización del usuario. No usar Actions ni recursos de pago.

## Pendiente que no se puede sustituir por desarrollo

U12 exige tres proyectos independientes, personas reales de ambos roles,
consentimientos, observación de primer diagnóstico en <=300 s y retención tras
un cambio posterior. No se rellena con perfiles ficticios ni tiempos automáticos.
No se crean obligaciones de soporte, licencias o aceptaciones de servicio/DW.
Las pruebas usan datos sintéticos y sus salidas privadas quedan fuera de Git.
Se conservará evidencia compacta y se retirarán entornos descartables propios al
terminar para no deshacer la limpieza anterior.
