# Calidad verificable de paquete: 80 % — A13

**16/20 controles PASS; 4 BLOCKED; 0 FAIL.** Cada control vale cinco puntos.
Rúbrica propia `PACKAGE-QUALITY-RP-20-v1`, inspirada en
[How to Evaluate the Quality of Python Packages, Real Python](https://realpython.com/python-package-quality/).
El artículo propone señales cualitativas; no define este porcentaje ni una certificación.
Se evalúa el par privado núcleo/benchmark `0.12.0a13` y el consumidor `0.1.15`.

El 45 % de la captura carecía de numerador, denominador y recibo identificados.
**No se afirma un aumento medido de 35 puntos.** La medida actual conserva
los veinte controles y pesos del [plan previo](PACKAGE_QUALITY_PLAN_20261010.md).
La ampliación documentada del candidato exige A13 al encontrarse un defecto de A12.

Último cambio del código runtime probado: `5e1465aa038a8fd463f83c8684768c4d9dc612e1`.
Corte de fuente de pruebas instaladas y trazabilidad: `96769ad15d0807a501e6141725c8d4198d7715b0`.
Ajuste posterior de formato de una prueba: `801194d440c6e2f7773930229a2a21f092d4acc2`.
SHA-256 de las veinte definiciones y sus pesos: `6a7c9d55d57199647d546d86848dc02a04490747d18d4228a0997857e5ffedb1`.
Los bytes y huellas de los wheels identifican el candidato; la versión sola no basta.

## Cinco pasos realizados

1. Revisar la fuente, comprobar Git y congelar veinte controles con igual peso.
2. Verificar metadatos, documentación y dependencias; corregir identidad de productores.
3. Incorporar un auditor de wheel previo a instalar, sin extraer ni ejecutar su contenido.
4. Ejecutar controles estáticos, suites completas, instalación aislada, consumidor y reversión.
5. Entregar código e informe en Git, respaldo privado y kit manual; retirar temporales propios.

## Qué cambió y para qué sirve

- A12 emitía nuevos detectores con `versions.equiframe=0.12.0a11`. A13 emite
  A13 y admite identidades explícitas A12/A13. Los algoritmos R/M/B/H/O,
  entrenamiento, umbrales, parámetros, etiquetas y formatos se conservan.
  Los productores, catálogos y recibos históricos no se reescriben.
- Se regeneraron los esquemas actuales del productor y se revisaron sus dos
  huellas experimentales. `generate_assets --check` rechaza ahora un inventario
  desactualizado antes de las suites largas; nunca aprueba huellas por reescritura automática.
- Versiones, locks, pins núcleo/benchmark y guías actuales usan A13; el consumidor
  permanece en otro repositorio con expectativas matemáticas independientes.
- El [auditor offline](OFFLINE_WHEEL_AUDIT.md) verifica SHA-256 antes de analizar
  el ZIP; revisa rutas cerradas, METADATA, inventario RECORD, tamaños, bytes y
  destinos locales de enlaces Markdown. Sus 21 casos adversariales prueban
  corrupción, rutas inseguras, duplicados, Unicode, límites y recibos ocupados,
  incluyendo Python optimizado. El SHA esperado requiere un canal confiable separado.
  Se comprobaron 231 referencias Markdown locales del núcleo; diez referencias
  externas/anclas quedaron fuera de esta verificación. El wheel del benchmark
  no incluye archivos Markdown, por lo que no se le atribuyen esas 231 referencias.
- Dos anotaciones heterogéneas corrigen errores de mypy del arnés de trazabilidad.
- La prueba del supervisor captura identidades de procesos antes de su limpieza
  real para evitar una carrera al leer un archivo que el trabajador no alcanzó a escribir.
  Se comprueba que todos los descendientes capturados terminan; el supervisor no cambió.
- La observación del CLI normaliza representaciones Enum/valor entre Python y
  dependencias diferentes. Compara todavía opciones, obligatoriedad y defaults
  declarados; un texto desconocido se conserva y provoca diferencia. El CLI no cambió.

## Controles y pendientes

| Control | Estado | Evidencia o pendiente |
|---|---|---|
| Q01: README de ambos paquetes: propósito, límites y estado privado | PASS | README.md; packages/equiframe/README.md; packages/equiframe-benchmark/README.md; metadata-coherence.json |
| Q02: Primer uso ejecutado: equivalente, diferente y no evaluable | PASS | workflow-final/workflows.json; vm-receipts/workflows-final.json |
| Q03: Requires-Python/classifiers coherentes; instalación A12 en Windows y Linux ARM64, con versiones observadas | PASS | installed-identity.json; vm-receipts/installed-identity-final.json; metadata-coherence.json |
| Q04: Alpha explícito, sin afirmar Production/Stable | PASS | audit-equiframe.json; audit-equiframe-benchmark.json |
| Q05: Changelog vigente y diferencias frente al candidato anterior | PASS | packages/equiframe/CHANGELOG.md; packages/equiframe-benchmark/CHANGELOG.md |
| Q06: Autor y URL del repositorio identificados en ambos METADATA | PASS | metadata-coherence.json; github-state.json |
| Q07: Documentación local del wheel con destinos Markdown resolubles, sin depender de abrir el checkout | PASS | audit-equiframe.json; audit-equiframe-benchmark.json |
| Q08: Distribuciones públicas verificadas en PyPI con identidad controlada | BLOCKED | Public publication and controlled PyPI identity are pending; private artifacts do not satisfy this check. |
| Q09: Dependencias declaradas iguales a METADATA; resolución normal y pip check satisfactorios | PASS | metadata-coherence.json; final-build.json; pip-check.log; vm-receipts/pip-check-final.log |
| Q10: Consumidor técnico separado: pruebas independientes contra el wheel suministrado | PASS | workflow-final/consumer-normal/summary.json; workflow-final/consumer-optimized/summary.json; consumer-tests.xml |
| Q11: Dependientes externos reales, ajenos a los laboratorios del equipo | BLOCKED | No external dependents outside the controlled validation projects are demonstrated. |
| Q12: Interés externo observado: comunidad/usuarios; no crear estrellas, forks o descargas artificiales | BLOCKED | Real community/users remain unverified; no synthetic stars, forks or downloads were created. |
| Q13: Actividad Git real: historial y PR integrados recientes | PASS | github-state.json; github-merged-prs.json |
| Q14: Instrucciones para contribuir, reportar fallos y revisar cambios; límites de respuesta explícitos | PASS | CONTRIBUTING.md; SECURITY.md; .github/ISSUE_TEMPLATE/bug_report.md; .github/pull_request_template.md |
| Q15: Suites completas núcleo y benchmark sin fallos: fuente y wheel fuera del checkout | PASS | source-core-a13-final/tests.xml; source-benchmark-a13-final/tests.xml; installed-core/receipt.json; installed-benchmark/receipt.json; vm-receipts/posix-complete.xml |
| Q16: Ruff, formato, mypy y activos generados de ambos paquetes satisfactorios | PASS | source-core-a13-final/commands.json; source-benchmark-a13-final/commands.json; static-final-fixed/commands.json |
| Q17: Wheel/sdist y payload identificados; reconstrucción desde sdist y rechazos de alteración | PASS | final-build.json; cli-test-build.json; final-artifacts.json; audit-equiframe.json; packages/equiframe/tests/test_offline_wheel_audit.py |
| Q18: Actualización/reversión aisladas A11–A12 con versiones y bytes comprobados; notas de migración | PASS | lifecycle-final/commands.json; packages/equiframe/docs/upgrading.md |
| Q19: Comandos privados exactos, verificación SHA-256 por canal separado antes de instalar; import base ligero | PASS | docs/OFFLINE_WHEEL_AUDIT.md; packages/equiframe/docs/installed-private.md; installed-identity.json |
| Q20: Titularidad y licencia aprobadas; permisos, condiciones y restricciones adecuados | BLOCKED | Ownership and distribution license have not been approved by the holders. |

Los cuatro pendientes son publicación pública con identidad controlada (Q08),
dependientes externos reales (Q11), comunidad/usuarios demostrados (Q12) y licencia
aprobada por los titulares (Q20). Q10 acredita un consumidor técnico del equipo;
no acredita adopción externa. GitHub se observó privado, sin licencia declarada y
con cero estrellas, forks y subscribers. No se creó actividad artificial.

**El 80 % no autoriza publicar en PyPI.** STEP10, revisión global, titularidad,
licencia, decisiones de publicación y aceptación humana siguen pendientes.

## Validaciones ejecutadas

| Suite Windows | Recogidos | PASS | SKIP | FAIL |
|---|---:|---:|---:|---:|
| source-core | 8077 | 8052 | 25 | 0 |
| source-benchmark | 627 | 620 | 7 | 0 |
| installed-core | 8077 | 8052 | 25 | 0 |
| installed-benchmark | 627 | 620 | 7 | 0 |

- Ruff, formato, mypy y activos generados de ambos paquetes satisfactorios.
  Los cuatro controles del núcleo se repitieron después de la última edición de pruebas.
- Instalación aislada con resolución normal, `pip check`, METADATA y los 162 miembros
  de payload correctos (127 núcleo, 35 benchmark); import base sin cargar motores ni ML.
- Seis distribuciones wheel/sdist comprobadas con `twine check --strict` y reconstruidas
  byte a byte desde los sdists entregados en Windows. No se afirma reproducibilidad
  entre OS ni desde otro checkout con distintos finales de línea.
- Doce primeros usos reales: dos perfiles, tres estados y ejecución normal/optimizada;
  los códigos de salida 0, 1 y 3 corresponden a equivalente, diferente y no evaluable.
- Consumidor instalado: 19 pruebas y 15 subtests; 72 casos distintos en cada modo
  normal y `-O`, con 24 PASS y 48 EXPECTED_REJECTION, sin FAIL. Son los mismos
  casos repetidos en otro modo, no 144 casos únicos. Hubo 144 intentos nativos por
  modo y seis controles de fallos adicionales. Los tres motores ejecutaron implementaciones nativas.
- Reversión aislada A12–A13–A12–A13: versiones y bytes correctos, sin payload obsoleto,
  decimales, claves y ausencias conservados; tres estados semánticos y `pip check`
  correctos. Volver a A12 prueba el mecanismo y no elimina su defecto de procedencia.
- VM 157.137.227.1, Linux ARM64/Python 3.10.12: instalación, auditorías negativas
  con `-O`, imports, payload y primeros usos satisfactorios; 98 regresiones de identidad,
  detectores, CLI e inventario y los siete casos POSIX omitidos en Windows, todos PASS.

La suite fuente del núcleo inició antes de la normalización portable del observador CLI.
Ese cambio posterior pasó 22 comprobaciones focalizadas en Windows, las 98 de la VM
y la suite completa instalada desde el sdist corregido. La edición posterior de formato
sólo une dos f-strings adyacentes de esa prueba; no cambia el payload SDK ni su significado.
No se presenta esa ejecución fuente anterior como una suite iniciada desde el commit posterior.

Las 25 omisiones del núcleo en Windows permanecen identificadas y no se acreditan
como PASS. La VM cierra los siete casos POSIX del benchmark, no toda la matriz
de Python/OS ni todas las omisiones del núcleo. Versiones efectivas y nombres de
omisiones constan en el [resultado estructurado](PACKAGE_QUALITY_RESULT_20261010.json).

### Fallos e intentos conservados

- A12 fuente e instalado: cada suite tuvo 8.048 PASS, 25 SKIP y 1 FAIL de 8.074.
  La identidad de nuevo productor era A11. Se corrigió el emisor y se preparó A13.
- A13 provisional fuente e instalado: cada suite tuvo 8.050 PASS, 25 SKIP y 1 FAIL
  de 8.076 por huellas de esquemas actuales desactualizadas. Se revisaron las dos
  huellas y se añadió un control temprano y una regresión; el candidato final es otro wheel.
- Benchmark A13 fuente inicial: 619 PASS, 7 SKIP y 1 FAIL por la carrera del fixture.
  La corrección preservó los bytes del supervisor; las suites completas se repitieron.
- VM del SDK final, observador CLI previo: 97 PASS y 1 FAIL de 98 por Enum/texto.
  El mismo wheel pasó las 98 pruebas con el observador portable corregido.
- Una comprobación de formato detectó un ajuste en esa prueba; se corrigió y los
  cuatro controles estáticos finales pasaron. Los intentos originales reciben cero crédito.

No se relajaron resultados científicos, esperados matemáticos o gates para alcanzar la meta.
Los XML, logs, recibos y distribuciones de diagnóstico se conservan fuera de Git.

## Trazabilidad actual, medida separada

A13: **4,298/8,385 = 51.26 %**, con 3,445 casos distintos.
Normal y optimizado coinciden: 1.743 obligaciones PASS, 2.555 EXPECTED_REJECTION,
4.087 NOT_RUN y 0 FAIL; 1.668 casos PASS y 1.777 de rechazo esperado.
El alcance es construcción, serialización y validación de metadatos del núcleo;
no demuestra efectos nativos de todas las opciones.

El catálogo nuevo conserva los 3.443 casos anteriores, cambia explícitamente el default
en la copia A13 según el requisito de identidad y agrega dos literales A12/A13.
La expectativa se define por el requisito, no se copia del resultado de la implementación.
Los IDs, commit, denominador y wheel se vuelven a vincular antes de ejecutar.
El catálogo y manifest A12 congelados conservan sus bytes y porcentaje histórico.
Catálogo A13 SHA-256: `9eaa56aa71b803d901b07b56da0a89eb3cb610a44dc67a78513b553288ab59e1`.
Denominador A13 SHA-256: `22308238f613b50aefc0d5bb876e743443b3585c69f5f92d2ce9c22a5c2c3de1`.

## Artefactos privados identificados

| Archivo | Bytes | SHA-256 |
|---|---:|---|
| equiframe-0.12.0a13-py3-none-any.whl | 461570 | `c4fe192d3032ac0dcd9adf40dde46b6023e9956cd6a85bf4a74972a78ee32f23` |
| equiframe-0.12.0a13.tar.gz | 1524480 | `164b70270344343094dc0a688bf8dbfe20a27112f7227e2f7fe318f085b71935` |
| equiframe_benchmark-0.12.0a13-py3-none-any.whl | 127142 | `fb843318d044a36a7ba4efab7d7d997d45798e12d16df7a9aa1b472b2c6359d8` |
| equiframe_benchmark-0.12.0a13.tar.gz | 434163 | `4f8c47a00a8724b234e87c0a7147e193092122c77772e9169bd954744dd6e9c7` |
| equiframe_consumer_lab-0.1.15-py3-none-any.whl | 28249 | `be82d4f7422dc98bbfbd978746eca5051280b1935b1191cb6fb566c61337838e` |
| equiframe_consumer_lab-0.1.15.tar.gz | 28302 | `ebecd34b85d9922bc015421842f64ff980329660f33b41af1a93e7408f087393` |

Los artefactos están en `respaldo_equiframe_20261010/distribuciones-final-a13/`
fuera del repositorio. Kit manual e instrucciones:
`respaldo_equiframe_20261010/calidad-final-a13/manual-kit-a13.zip` y su `LEEME.md`.
El respaldo privado de evidencia Windows se entrega separado, con inventario y hashes.
No se agregan a Git entornos, cachés, modelos, datasets ni outputs privados.

Los recibos de la tabla se encuentran bajo `a13-final/` del respaldo Windows,
salvo las suites fuente `source-core-a13-final/` y `source-benchmark-a13-final/`,
situadas en la raíz del mismo archivo. El inventario del respaldo identifica cada entrada.

En la VM queda `/home/hernan/equiframe-calidad-final-a13-20261010/kit/`.
Los temporales finales fueron retirados tras verificar:
`/home/hernan/equiframe-respaldo-20261010/calidad-final-a13-evidencia.zip`.
SHA-256 del respaldo VM: `eb70afb6570ab1b133c986e2562f5a4c785d4197e3f83688cd2626dcb9e2221f`.
Los despliegues y kits anteriores se conservaron. La VM se usó para QA manual
de compatibilidad Linux; no se instaló un servicio público nuevo.

No se ejecutaron Actions ni se crearon recursos de pago. Este índice no mide
aceptación científica, satisfacción humana, seguridad certificada, cobertura
de líneas ni Universalidad del 100 %.
