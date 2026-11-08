# Trazabilidad del parser CLI de Alpha A13

El lote ejecutado suma **92 obligaciones únicas**: 30 ayudas explícitas
aprobadas y 62 rechazos esperados atribuidos al parser. La unión pasa de
6.045 a **6.137/8.385 = 73,1902206321 %**. La repetición normal/optimizada
acredita los mismos IDs; no suma otros 92. Este es el corte anterior al
siguiente lote de constructores, si éste se acredita.

Los esperados se congelaron antes de ejecutar. La identidad del wheel A13
instalado fuera del checkout y sus 127 archivos de payload se cotejó antes
y después. La dependencia real es **Typer 0.27.2** y el recibo conserva los
hashes de su parser y núcleo; el inventario histórico usó 0.27.3 y no se
atribuye a esa versión esta ejecución nueva.

Para cada ayuda se observa entrada real en `Context.exit(0)` con el contexto
exacto y su salida renderizada. Los rechazos observan `BadOptionUsage` o
`MissingParameter` en el código exacto del parser, con comando y opción o
parámetro concordantes. El callback de hoja no entró. Las cinco omisiones
posicionales que dejan argumentos posteriores ausentes se declaran así y
acreditan únicamente el parámetro cuya ausencia causa el rechazo observado.

Los dos intentos v1 fallidos se conservan con su fuente original y **cero IDs
nuevos acreditados**. Cuatro guardias por modalidad comprueban contraejemplos
de comando, parámetro, opción, salida, entrada al callback y desplazamiento
posicional. La revisión de «mi dot» es de un agente IA de solo lectura;
no sustituye revisión humana ni acredita operaciones nativas de los comandos.

El [agregado JSON](OPTION_CLI_PARSER_RESULT_20261012.json) enlaza todos los
recibos y sus fuentes. El respaldo privado tiene 30 archivos y lectura
completa comprobada, SHA-256
`79079e71a3481bf72e99e1310879bbbcc3621acc6c940fcf5c35c176cb7a198a`.
Madurez y requisitos de tesis no ganan puntos automáticos por este lote.
