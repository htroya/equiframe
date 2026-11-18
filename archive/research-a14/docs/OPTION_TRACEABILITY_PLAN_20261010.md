# Plan de trazabilidad por opción: objetivo 50 %

Fecha: 2026-10-10. Núcleo privado A12, sin alterar algoritmos, formatos,
fixtures históricos, decisiones científicas ni dependencias de ejecución.

1. **Congelar el inventario completo.** Ejecutar `option_inventory.py` contra el
   wheel A12 instalado fuera del checkout, verificar sus bytes y conservar todas
   las obligaciones, incluyendo las que permanezcan NOT_RUN. El 5,16 % de la
   captura no tiene aquí una matriz identificada; no se atribuye una mejora
   comparable a ese valor sin localizar su numerador y denominador.
2. **Crear casos explícitos y reproducibles.** Añadir fixtures sintéticos de
   metadatos y un catálogo por campo, default, valor finito, omisión y clase.
   Cada caso declara entrada, expectativa y las filas exactas a las que aporta.
   Rechazar entradas incorrectas cuenta como EXPECTED_REJECTION; nunca como
   procesamiento exitoso de datos. Descubrimiento, harvesting y tests ajenos
   sin enlace no cuentan como prueba de una opción.
3. **Implementar ejecución y recibos.** Una herramienta independiente comprueba
   identidad del wheel, ejecuta casos, conserva observado/esperado, hash del
   catálogo y estados. Denominador inmutable; duplicados y repeticiones en otras
   plataformas no aumentan el numerador. Publicar también fallos y pendientes.
4. **Validar y desplegar de forma privada.** Ejecutar en Windows x64 y Linux ARM64
   de la VM existente 157.137.227.1, sin Actions ni recursos de pago. El despliegue
   consiste en instalar el wheel identificado y la herramienta manual en un
   entorno privado aislado; no crea servicios ni administra el DW del equipo.
5. **Entregar e integrar.** Documentar resultado calculado, alcance, comandos,
   hashes y pendientes. Revisar cambios, ejecutar controles y subir a `main`.

La meta es al menos `ceil(0.5 * todas_las_obligaciones_del_núcleo)` filas con
recibo PASS o EXPECTED_REJECTION, no 50 % de líneas ni 50 % de combinaciones.
Los casos de construcción, serialización y rechazo de metadatos se identifican
como tales: no prueban automáticamente el efecto de esos campos en cada motor.
Benchmark, productos de opciones e instalaciones adicionales se informan
separadamente; no quedan cubiertos por una repetición de los mismos casos.
