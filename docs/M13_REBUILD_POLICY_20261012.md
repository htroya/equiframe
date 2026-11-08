# Reconstrucción portátil del consumidor para el nuevo ensayo M13

El propietario autorizó el 12 de octubre de 2026 la transferencia y ejecución
del kit original `c33e581011bae4077aafccb478a7e678af9ea2cf8ff381d5f3a3bec4d6adab03`.
La transferencia se verificó y el ensayo comenzó en la VM Linux ARM64.
El documento [de preparación original](M13_PREPARATION_20261012.md) conserva
su corte histórico anterior a esa autorización.

Durante el ensayo, la reconstrucción Linux del wheel consumidor 0.1.15
produjo un SHA diferente del original. La inspección identificó la diferencia
en doce bytes `create_system` del directorio central ZIP: formato de atributos
Unix (`3`) frente al formato original DOS/FAT (`0`). Los doce miembros
descomprimidos coincidieron y el sdist reconstruido conservó el SHA original.
El formato de atributos ZIP no identifica el sistema operativo físico que
construyó el archivo. El primer ensayo conserva su fallo de identidad binaria;
sus otros resultados no lo convierten en un ensayo M13 aprobado.

## Regla explícita para un candidato nuevo

`assemble_kit.py --consumer-wheel-rebuild-policy
consumer-wheel-central-creator-system-zero-v1` declara la regla antes de la
ejecución. Sin ese argumento, el procedimiento conserva su comportamiento
anterior. Los seis artefactos originales y sus versiones no se modifican.

El nuevo procedimiento reconstruye el wheel desde el sdist, conserva ese
wheel bruto y genera otro archivo que cambia únicamente el byte de formato
de atributos de cada entrada central de `3` a `0`. No cambia datos comprimidos,
miembros, nombres, permisos, marcas de tiempo ni otros bytes. Solo admite
ZIP ordinarios, acotados y con formato original o Unix. Antes de escribir
exige que el SHA-256 **completo** del wheel normalizado coincida con el wheel
original. Un contenido distinto sigue produciendo un rechazo.

El recibo registra ambos hashes, las posiciones cambiadas y la conservación
del wheel bruto. El revisor recalcula la máscara y vincula el comando a la
ruta exacta del kit y a sus archivos de entrada, salida y recibo. La expresión
correcta es «wheel reconstruido normalizado idéntico al original»; el wheel
bruto Linux sigue siendo distinto. El sdist debe seguir coincidiendo byte a
byte sin normalización.

## Validación y alcance

Las herramientas tienen contrapruebas para contenido diferente, archivos
previos, ZIP incompletos, formato desconocido y rutas de evidencia ajenas o
duplicadas. El suplemento revisa las mediciones originales de 100 y 1.000
filas, sus tres repeticiones, nueve contadores Linux, presupuestos, archivos
brutos, finalizaciones y recuperaciones del consumidor. No concede puntos
automáticamente ni sustituye un ensayo real o aceptación humana.

La revisión IA «mi dot» comprobó estáticamente estos vínculos. El nuevo kit
debe conservar una identidad propia y ejecutar íntegramente los perfiles,
pruebas, recorridos y reconstrucciones del alcance M13 ARM64 Python 3.10/3.12.
Las otras plataformas y versiones de universalidad conservan sus requisitos.

M13 permanece pendiente hasta recuperar y revisar un ensayo completo del
nuevo candidato. No se modifica el Word ni se publica en PyPI/TestPyPI.
