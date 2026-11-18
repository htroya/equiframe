# EquiFrame revisión del candidato de madurez

Informe privado para Hernán. Corte de revisión del 8 de octubre de 2026. Se entrega un candidato Alpha reproducible para revisar y probar, con trabajo técnico comprobado y cierre incompleto. No se anuncia soporte completo, versión estable, certificación, producción ni publicación.

## Resultado y alcance

1/16 criterios íntegramente cumplidos = 6,25 % de cierre de este plan. Nueve criterios están PARCIAL y seis BLOQUEADO. Este índice estricto cuenta criterios completos, no pruebas individuales ni porcentaje de calidad del software. El 65 % anterior no tiene rúbrica verificable localizada y no permite calcular avance ni retroceso. El 6,25 % tampoco significa que el resto de las funciones falle: cuenta obligaciones completas, incluidas puertas externas, con una regla de todo o nada. La matriz conserva las dieciséis condiciones, todas las versiones y plataformas comprometidas.

El alcance es núcleo privado, benchmark y consumidor. La entrega de usabilidad se preservó (U01–U11 completos; U12 humano pendiente). El servicio/DW real, aceptación científica, derechos, operación productiva y publicación tienen puertas propias. No se modificaron infraestructura de José, DW de Jhair, sistema global ni main.

## Identidad del candidato

- Rama local: maturity/python310-313-20261007
- Fuente producto: c4f6a903f580f5e98d63db6e225e0a042221f4ec
- Árbol producto: a43aa2c8af0e07540195252d2b38abd37404f7f0
- Consumidor: 28cd3d7d43f79466270378c4752c5ef50560e5e0
- Herramientas revisadas: 07a9923730de5b124b86cb77c1f1d4b93a36a62d (scripts distintos de la fuente producto c4)
- Base remota verificada: 876033ce111fd38123799db4e4c40bd0202ec8df, árbol 3a8ec2c938ccc716d33b4d0954ca00d56f83bebc
- El historial local recuperado conserva el mismo árbol base pero no se presenta como el historial remoto original
- Versiones: equiframe 0.12.0a8; equiframe-benchmark 0.12.0a8; equiframe-consumer-lab 0.1.10
- Manifiesto original c4: faeb19c57cb23f751a097997e08f21f010a5499f6d30be007956de8696e7f99d

Los seis artefactos se mantienen inmutables. El kit standalone revisado declara por separado el commit y hashes de sus herramientas en candidate.json. Su nuevo manifiesto sustituye solo el expediente de handoff para nuevas ejecuciones; no cambia los artefactos c4. Los recibos históricos conservan el manifiesto contra el que realmente corrieron. No se mezclan scripts entre ZIPs.

| Artefacto | SHA-256 |
|---|---|
| equiframe_benchmark-0.12.0a8.tar.gz | 5d426e541f9226411bd7d3ba8974e4072fabc3e0b3c23b1c332705d7afc8a4d7 |
| equiframe_benchmark-0.12.0a8-py3-none-any.whl | b94bdcb7ec3c8303f0d55f52f39b85a2912719851681f00c8211a994a66d23c5 |
| equiframe_consumer_lab-0.1.10.tar.gz | 0ed13fa8d78daeb44912ff8261f7b078be7bae726e32b5b2c86b4d26b04a0ab2 |
| equiframe_consumer_lab-0.1.10-py3-none-any.whl | e2a8ed772e257ae2f6015dafb183040b6c47e264d2d92a881270619d7764415e |
| equiframe-0.12.0a8.tar.gz | 23b13cfca75d2425dd27092fbdfecca42d4144615e86c5141de1a3f5991fc97d |
| equiframe-0.12.0a8-py3-none-any.whl | a7fec910282857912f1d22d1e5ffefaf8ac71182f3acfa22b3e4154fef2d1194 |

## Cambios concretos y efecto

1. Se sustituyeron sintaxis PEP 695 y APIs posteriores a 3.10 por equivalentes tipados, conservando alias nombrados, genéricos y contratos. El backport del núcleo está declarado; el benchmark todavía necesita su declaración directa y lock coherente.
2. Se corrigieron fallos reales de fechas ISO con Z/fracciones y contexto Decimal en 3.10, preservando nanosegundos, precisión y contexto del llamador. El ensayo previo con 42 fallos y las regresiones corregidas se conservan.
3. Los arneses observan y propagan el intérprete real. El consumidor tipado conserva --strict y utiliza la versión del Python de su entorno; el error real de stubs NumPy en el intento 3.12 sigue registrado.
4. Las guías, perfiles, recetas, metadatos y workflows manuales reflejan el objetivo 3.10–3.13. La adaptación de junctions conserva el rechazo por reparse tag; no se presenta una simulación como ejecución Windows.
5. Se separó identidad instalada del consumidor de un commit histórico incrustado. Los recibos actuales se vinculan al payload y al manifiesto externo del candidato.
6. El handoff revisado comprueba los resultados individuales de los 72 casos consumidores, los tres resultados nativos desde sdist bajo -O, la permanencia de los pins runtime y la identidad Python/arquitectura. Un fallo de medición se conserva y no impide recoger pruebas independientes; nunca se transforma en pase.

Los cambios de esquemas son seis ampliaciones de productor a8/default, con formatos y productores históricos conservados. R, M, B, H = R OR M y O mantienen sus fronteras; no se cambiaron metodología, etiquetas, particiones ni esperados para mejorar resultados.

## Validación realmente ejecutada

Plataforma de nube: Linux x86_64, kernel 6.18.44, glibc 2.41. Los recibos identifican ejecutables y dependencias. Ninguna de estas ejecuciones acredita maestria-vnic ARM64.

| Python real | Candidato y resultado observado | Lo que sigue pendiente |
|---|---|---|
| 3.10.21 | Núcleo c4: 9/9 etapas con exit 0; 4484 pruebas fuente y 4484 instaladas; base/extras fuera del checkout, API/CLI, consumidor tipado, instalación y reconstrucción idéntica wheel/sdist | Resto de la matriz de extremos, benchmark completo y consumidor externo por celda |
| 3.10.21 benchmark | Primer intento preliminar: 595 pases. Intento c4 final: 581 pases, 7 fallos y 7 errores por admisión de disco | Guardias 2 GiB + 256 MiB del ensayo preservadas; no se rebajaron para conseguir un pase |
| 3.11.16 | 4466 pruebas de fuente en candidato preliminar; tipado/refinamientos registrados | El gate integral de todos los bytes c4 y paquetes/perfiles no se ha completado |
| 3.12.14 | Preliminar af74ff2: 4474 fuente y 4474 instaladas; gate final de consumidor tipado falló. Recorrido offline c4 de actualización/rollback posterior sí aprobado | Corrección del arnés no convierte aquel intento completo en pase; faltan controles finales de la celda |
| 3.13.5 | Preliminar 8c524d2: 9/9 etapas, 4480 fuente y 4480 instaladas. c4: 955 pruebas seleccionadas y controles focalizados | El wheel c4 solo cambia 5 guías y RECORD respecto de ese wheel anterior; payload Python/METADATA idénticos. Se reutiliza ese alcance preciso, no un pase integral de todos los bytes finales |
| ARM64 3.10.12 / 3.12.15 | Versiones comunicadas por el titular, sin ejecución del candidato desde esta tarea | Revalidar en VM, ejecutar ambos entornos y devolver recibos; no afirmar soporte probado |
| Windows x64; macOS Intel/ARM64 3.12 | Sin runner autorizado disponible | Celdas conservadas y abiertas |

Los 34 tests focalizados del handoff revisado pasan con 3.10 y 3.12, además de Ruff y formato con la configuración del proyecto. Son fixtures sintéticos de herramientas; no sustituyen laboratorio VM ni revisión humana. Se conserva un intento inicial fallido con Python standalone sin packaging y un lint lanzado sin la configuración explícita del proyecto; los reintentos correctos usaron dependencias ya existentes y la configuración versionada, sin nuevos ignores.

### Actualización y recuperación

A7 → c4 → A7, más recuperación A7 en otro venv nuevo, ejecutados en Linux x64/Python 3.12.14 con pip normal --no-index y un wheelhouse local verificado. Los 42 comandos observaron el exit esperado. En cada fase: pip check, payload exacto, cuatro estados H bajo -O, recorrido de fallos del consumidor y ayuda de benchmark. Los 235 archivos de evidencia anterior permanecen idénticos. Se retiraron solo los dos venvs nuevos de este ensayo después de guardar sus pruebas. Las instalaciones antiguas cuya eliminación se consultó permanecen intactas.

Es una prueba acotada de recuperación, no el cierre de toda M11 ni una prueba de upgrade en ARM64. M11 sigue parcial por ausencia de evidencia del resto del alcance; no se observó un fallo en los 42 comandos de recuperación ejecutados. A7 conserva su admisión original 3.12/3.13; no se fuerza su instalación en 3.10/3.11.

### Recursos

Se ejecutaron 100 y 1000 filas, tres repeticiones de cada tamaño, con presupuesto fijado antes: un hilo, 120 s, RSS 512 MiB y disco 64 MiB. Las seis comparaciones dieron el resultado correcto; un límite deliberadamente pequeño produjo not_evaluable. El almacenamiento observado fue overlay, no tmpfs.

RSS muestreado cercano a 232–233 MB y ocupación muestreada de archivos hasta aproximadamente 1,56 MB son observaciones locales, no garantías ni máximos duros. psutil devolvió AccessDenied para contadores I/O y la medición completa terminó PARCIAL con exit 3. La caché del SO y otras cargas del host no estaban controladas. No hay SLO aceptado ni extrapolación a producción o VM.

## Matriz M01 a M16

La matriz canónica está en MATURITY_MATRIX.md y el detalle legible por máquina en evidence/maturity-assessment-20261008.json. Solo M01 cierra íntegramente en este corte; el resto conserva su brecha concreta. No hay “100 % técnico”.

## Parche pendiente del benchmark

pending/benchmark-direct-backport.patch contiene únicamente la declaración runtime typing-extensions>=4.14,<5, su changelog y la regresión de metadatos fuente/instalados. No forma parte de los wheels/sdists c4 ni está certificado por sus pases. La dependencia instalada observada es 4.16.0, actualmente transitiva del núcleo. Una mención previa a 4.15 no identifica este entorno.

La operación de lock fue detenida porque podría transmitir metadatos privados a PyPI. No se reintentó por otra vía ni se regeneró offline. Una vez autorizado el destino/datos: resolver el lock, verificar la regresión en la distribución instalada, generar nuevos artefactos/manifiesto sin sobrescribir c4 y repetir solo controles afectados. No usar ese parche como si ya fuera un candidato completo.

## Decisiones y bloqueos precisos

- Autorización de consulta OSV con nombres/versiones públicos; el intento c4 rechazado y la revisión de fuente previamente detenida no tienen pase. Las 74 consultas históricas sin avisos conocidos cubrían un inventario 3.11 anterior, no todo el candidato.
- Autorización de la operación de lock PyPI, con posible transmisión de nombre/versión/metadatos EquiFrame. No incluye código, datos, credenciales ni llaves. La pregunta sigue sin respuesta.
- Espacio: el consumidor mantiene 4 GiB libres como condición. Los tres venvs antiguos consultados no se borran sin permiso. No se sustituyó disco por tmpfs ni se cambió seguridad/montajes.
- VM: ejecutar desde el entorno Codex con acceso ya autorizado, identificar ejecutor/transporte y devolver ambos recibos ARM64. Solo después de revisar se reconsideran M13 y criterios vinculados. No se requiere ni incluye una llave nueva en el kit.
- M09: decisión real del titular sobre derechos/condiciones; M15: responsables y soporte aceptados, incluido Python 3.10 legado; M16: reproducción/revisión humana independiente.
- Toda publicación de rama, push directo o merge a main permanece sin realizar. Un push directo/merge a main requiere autorización nueva expresa después de la revisión. Tampoco se activaron Actions, PyPI/TestPyPI o despliegues.

## Preparación de José y puertas externas

J01 bloqueado por conectividad desde esta nube; J02 venv/pip VM no ejecutado; J03 parcial por intérpretes reales de nube, sin atribuir entrega a José; J04 directorios VM no creados; J05 DNS/HTTPS ARM64 no probado; J06 recursos VM pendientes de revalidación; J07 sin recibo real de preparación; J08 integración gateway/DW fuera del alcance de biblioteca y no ejecutada. La lista de directorios/entornos creados por esta tarea en maestria-vnic está vacía.

Derechos/distribución privada: decisión pendiente. Publicación pública: no autorizada. Aceptación científica: pendiente de corpus/protocolo/revisión correspondientes. Integración real de servicio/DW: no acreditada y fuera de esta implementación. Operación productiva: no acreditada. Usabilidad humana U12 y revisión independiente M16: pendientes distintos, ninguno firmado por una automatización.

## Uso del expediente

El ZIP revisado es standalone: leer LEEME_REVISION_ES.md, luego README_VM_ES.md. Ejecutar su propio scripts/run_vm_lab.py con su candidate.json; no copiar scripts al kit original. Incluye los seis artefactos, fuente recuperable, herramientas identificadas, dependencias/locks observados, matriz, recibos y parche pendiente. La llave y el ZIP privado de entrada están excluidos.

Las rutas absolutas que aparecen en logs son observaciones históricas del ejecutor, no instrucciones para acceder al equipo de Hernán. No se incluyeron venvs, caches, datos de trabajo ajenos ni bases compartidas. Los hashes comprueban integridad; no autentican autor, operador ni aceptación humana.
