# Alpha A13 instalada: Windows Python 3.10–3.13

El [recibo](ALPHA_WINDOWS_INSTALLED_RESULT_20261012.json) identifica cuatro
entornos aislados Windows AMD64: Python 3.10.21, 3.11.16, 3.12.4 y 3.13.15.
Se instalaron los wheels originales A13 con dependencias fijadas y hashes,
sin modificar Python predeterminado ni reconstruir el SDK.

El addendum v3 ejecuta 24 ejemplos bajo aislamiento `-I`, normal y `-O`, y
comprueba el origen real de módulos/ejemplos y sus payloads. Sus 432 intentos
comprenden **408 comparaciones completas y 24 rechazos `invalid_input`
esperados**. Hay seis fuentes y tres motores en la receta sintética; no se
atribuye por ello compatibilidad universal ni validación científica.

Las primeras versiones del instrumento y sus fallos se conservan. El archivo
de custodia pesa 8.790.440 bytes y tiene SHA-256
`8555c9203b69988582e9084602b35978cae7d88b2b1d2c712cfd88a1c4953ff2`.
Estas repeticiones añaden cero IDs al inventario de 8.385 obligaciones.
La evidencia cubre un perfil de dependencias por versión; no las restantes
plataformas/macOS ni todas las bandas de dependencias comprometidas.
