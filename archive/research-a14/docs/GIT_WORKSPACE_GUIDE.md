# Git de EquiFrame y repositorios temporales del workspace

Para trabajar sobre el código actual, abra la carpeta `equiframe` del checkout.
Su rama principal es `main`; la carpeta de la tesis contiene además copias
históricas, recibos privados y directorios de pruebas que no son entregables
del repositorio principal.

## Diagnóstico del contador 412 — 2026-10-10

Los registros Git del editor identificaron 303 repositorios del workspace.
La inspección de sus estados encontró exactamente **412 cambios**, todos en
repositorios sintéticos creados por pruebas: **112 modificaciones y 300 archivos
sin seguimiento**, repartidos en 120 repositorios temporales.

| Grupo de pruebas | Repositorios con cambios | Cambios |
|---|---:|---:|
| Seguimiento de release Windows, Python 3.10 | 30 | 103 |
| Seguimiento de release Windows, Python 3.11 | 30 | 103 |
| Validación nativa A10 Windows, Python 3.10 | 30 | 103 |
| Validación nativa A10 Windows, Python 3.11 | 30 | 103 |
| **Total** | **120** | **412** |

Las pruebas modifican deliberadamente paquetes sintéticos, agregan archivos o
dejan bytecode para comprobar rechazos, reinstalación y trazabilidad de fuentes.
Son cambios esperados de los fixtures temporales, no trabajo de EquiFrame
pendiente de subir. Las nueve copias de trabajo del código/consumidor/corpus
revisadas estaban limpias. Los archivos y recibos originales se conservaron.

## Configuración local del editor

En el workspace de la tesis se preparó un archivo local `.vscode/settings.json`
con profundidad de exploración uno, exclusión de las carpetas de pytest para
exploración/eventos y una lista explícita de los 296 repositorios temporales
detectados. La configuración y la lista de rutas locales no se suben a Git.
El contador de cambios legítimos continúa habilitado.

Para aplicar la exclusión a repositorios que el editor ya abrió, recargue la
ventana mediante `Developer: Reload Window`. La inspección de Git y el archivo
de configuración están comprobados; no se verificó visualmente el contador
después de recargar, porque el servicio de control de la ventana no estaba
disponible en esta sesión.

En otras máquinas, abrir directamente el checkout evita explorar los labs
adyacentes. Si debe abrir una carpeta de trabajo amplia, limite el escaneo y
excluya los repositorios temporales propios. No elimine los fixtures ni haga
commits masivos para reducir el contador. El `.gitignore` del repo principal
no gobierna repositorios independientes creados fuera de ese checkout.

El aviso de propiedad de Git se resuelve únicamente para carpetas conocidas
y revisadas mediante `safe.directory` con rutas explícitas. No se necesita
confiar en todas las carpetas con `*`. Para copias históricas de Windows con
rutas profundas, `git config --local core.longpaths true` permite distinguir
un límite de ruta de una eliminación real.

Los detalles y registros usados para este diagnóstico permanecen fuera de
Git. Este documento publica solo el resultado agregado y la solución local.
