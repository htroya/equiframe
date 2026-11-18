# Verify reutilizable y evidencia portable — diseño previo

Fecha: 2026-10-03. Extensión compatible de ingeniería, sin cambiar R/M/B/H ni
los requisitos científicos de O. No representa etiquetas o revisiones reales.

| Problema y estado actual | Contrato esperado | Aceptación y evidencia |
|---|---|---|
| Migración conserva comparación y esperado, pero carece de verificación reutilizable | `verify` recibe artefactos o resultados existentes, uno o varios, sin ejecutar ETL | Un resultado, dos resultados, errores compartidos, claves incorrectas con totales iguales; manifiesto y comparaciones completas |
| Un booleano confunde acuerdo, ejecución, reglas e independencia | Estados tipados separados para entradas, técnica, integridad, acuerdo, esperado por salida, R, cobertura y O | Esperado ausente no acredita corrección; fallo/incompleto no permite publicación |
| El núcleo no puede depender del benchmark | Tipos de procedencia y revisión generales; puente explícito desde `OracleResult` | Identidades/hash de contrato, entradas, plan, salida y esperado; doble revisión/arbitraje existente preservados |
| Nombres declarados y hashes no autentican personas | Procedencia registra método/autores/dependencia del esperado; O exige independencia declarada y dos revisiones ciegas compatibles | Autor del esperado coincidente y esperado de motor bajo prueba impiden O; revisión incompleta permanece pendiente |
| URI absolutas impiden trasladar expedientes | Bundle copia bytes originales, inventario cerrado y mapa URI a miembro relativo | Copia a carpeta distinta, original inaccesible, misma lectura; corrupción/traversal/symlink/referencia externa rechazados |

La política automática de publicación exige completar las dimensiones solicitadas;
O permanece opcional y separado. Un artefacto externo acredita inspección completa
de su salida, no ejecución ni entradas no capturadas. R necesita una captura de
ejecución con sus entradas. Los reportes conservan diferencias completas, ejemplos
limitados y conteos. La lectura/importación de bundles nunca ejecuta callbacks,
plugins, SQL o motores.

Compatibilidad: APIs y formatos de migración/oracle existentes se conservan.
`verify_migration` adapta un expediente comprobado; no reescribe su historia.
La resolución portable se limita dinámicamente a un mapa cerrado y se restaura
al terminar. Los URI históricos siguen siendo procedencia, mientras las rutas
del inventario portable son relativas. Los hashes prueban integridad contra una
referencia; una referencia externa confiable sigue siendo necesaria ante un
adversario capaz de sustituir expediente y manifiesto juntos.
