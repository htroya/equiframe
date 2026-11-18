# Entregas humanas y publicación

Estado del 12 de octubre de 2026. El propietario declaró pendientes titulares,
licencia, revisión independiente y resultados científicos aprobados. No se
generan firmas, aprobaciones ni etiquetas en nombre de otra persona. Cada
entrega debe identificar persona, fecha, candidato/commit, alcance, evidencia
revisada y decisión; los documentos privados permanecen fuera de Git.

## Personas necesarias para cerrar madurez y Beta

1. **Titulares y derechos (M09).** Confirmar quién posee los derechos del núcleo,
   benchmark, consumidor, documentación y aportes del equipo; identificar
   condiciones universitarias/institucionales aplicables. Acordar licencia o
   condiciones de distribución privada y sus destinatarios. Entregar decisión
   escrita aprobada por quienes puedan conceder esos derechos. `authors` no
   demuestra por sí solo titularidad y una propuesta de licencia no la concede.
2. **Responsables y suplentes (M15).** Personas concretas aceptan mantenimiento,
   revisión de cambios, releases, soporte por Python/plataforma, incidencias y
   recuperación. Acordar canal, plazos realistas, soporte legado y procedimiento
   de retiro/actualización; no inventar SLA. Entregar aceptación de roles.
3. **Revisor humano independiente (M16).** Una persona que no sea el agente IA
   reproduce instalación/recorridos desde los artefactos identificados, revisa
   límites, fallos, contratos, resultados y pendientes; emite un dictamen con
   comandos, entorno, hashes y observaciones. Las condiciones originales de
   cierre siguen vigentes; una revisión parcial se registra como parcial.
4. **Lectores reales (U12/D19).** Arquitecto/científico o usuarios representativos
   siguen las guías sin instrucciones ocultas del autor. Se requieren tres
   proyectos reales independientes (refactor, SQL y CI), representación de
   arquitectura/ciencia, consentimiento e independencia. Registrar ayuda,
   intentos, interpretación y utilidad, con el reloj fijado antes de la sesión:
   tres primeros diagnósticos en hasta 300 segundos, sin instrucción esencial
   fuera de la guía ni práctica previa contada como primer uso. Observar un
   cambio real posterior y una integración retenida por proyecto; conservar
   también resultados desfavorables. Esto mide experiencia humana; enlaces y
   pruebas automatizadas no sustituyen esa observación.
5. **Piloto privado.** Nombrar destinatarios autorizados, casos de uso, plataforma,
   límites, período de prueba y persona que acepta/rechaza cada recorrido.
   Registrar incidencias y aceptación de la versión exacta. Instalación local
   por el agente demuestra funcionamiento técnico, no adopción humana.

## Personas necesarias para la tesis

6. **Dominio y cohorte (T04).** Jhair o el responsable de dominio valida grano,
   compilación OCDS, identificadores, monedas, decimales, ausencias, estados y
   fechas. Acordar fecha de cohorte, exclusiones y tratamiento de publicaciones
   posteriores. Entregar contrato/diccionario aprobado y reconciliación desde
   el snapshot original. El selector oficial `year=2025` no basta como cohorte.
7. **Normalidad y protocolo (T03/T06/T15/T16/T18).** Equipo y tutor aprueban
   selección de ejecuciones normales, características/familias, dependencias,
   ajuste/calibración/prueba, reglas, mutaciones, parámetros y freeze previo a
   la prueba final. Acreditar `N_fit > 10.000` por modelo/familia con soporte y
   exclusiones; las filas de adjudicación o de prueba no son ese número.
8. **Oráculo independiente (T07).** Dos personas revisan los casos a ciegas y
   registran sus decisiones por separado; un tercero resuelve desacuerdos.
   Conservar cegamiento, autoría, conflictos, razones y arbitraje. Si un árbitro
   es autor de la variante, resolver el conflicto metodológico antes de declarar
   independencia. No reemplazar estas decisiones por IA o por pandas.
9. **Integración del DW (T13).** Jhair entrega esquema/DDL versionados, grano
   adjudicación, puente sin monto, unicidad, integridad y reconciliación por
   moneda/estado sobre su DW real; incluye acceso o evidencia ejecutable.
10. **Servicio y publicación de snapshots (T14).** José/Jhair entregan y
    demuestran preparación, carga repetida, idempotencia, concurrencia,
    interrupción/reinicio y conservación de la versión vigente ante fallo en
    sus componentes reales. Un destino sintético local no acredita su servicio.
11. **Resultados científicos (T19/T20).** Equipo/tutor revisan soportes pareados
    R/M/B/H frente a O confirmado, coberturas, denominadores, incertidumbre por
    grupos y costos. Entregar corpus/etiquetas/versiones y métricas regenerables,
    con aceptación o correcciones explícitas, sin seleccionar parámetros en test.
12. **Reproducción por otro integrante (T21).** Otra persona ejecuta el expediente
    congelado sin usar resultados ocultos del autor y registra comandos,
    diferencias, hashes y decisiones. La revisión IA «mi dot» sigue siendo IA.

El Word permanece intacto por instrucción vigente. Estas entregas se preparan
en expedientes separados; no implican añadir desarrollo/resultados al borrador.

## Qué debe hacer una persona para publicar en PyPI

13. **Autorizar divulgación y licencia (P17/Q20).** Resolver titulares/licencia,
    aprobar textos, notices y archivos que se distribuirán; determinar si se
    publican núcleo, benchmark y/o consumidor. Las dependencias y activos de
    terceros deben revisarse con sus obligaciones reales. Sólo después se
    incorporan la expresión SPDX y los archivos de licencia aprobados.
14. **Crear o confirmar cuentas separadas.** Identificar las cuentas del titular
    en PyPI y TestPyPI, verificar correos y habilitar 2FA y recuperación. Guardar
    claves/códigos en los medios privados elegidos; no compartirlos en Git/chat.
    TestPyPI exige su propia cuenta y no reserva el nombre de producción.
15. **Elegir y controlar nombres (P18).** Comprobar `equiframe` y
    `equiframe-benchmark` en ambos índices; acordar nombres alternativos si hay
    conflictos. Registrar propietario real. Una consulta que no encuentra un
    nombre no lo reserva ni autoriza usarlo. No crear proyectos ficticios.
16. **Asignar Owner/Maintainer y suplente.** Definir quién administra el proyecto
    y colaboradores y quién publica. Cada persona usa su identidad. La
    administración del repositorio GitHub no concede propiedad automática en
    PyPI; una organización de pago no es un requisito de este plan.
17. **Elegir el mecanismo de subida.** Configurar publicación manual con token
    acotado al proyecto, o Trusted Publishing con repositorio, workflow y entorno
    exactos. La configuración humana debe separar TestPyPI y PyPI. Usar Actions
    requiere una autorización nueva de ejecución; esta entrega no los activa.
18. **Aprobar documentación pública (P19/D20).** Elegir hosting/visibilidad y
    revisar README, guía de instalación, ejemplos, API, limitaciones, changelog,
    contacto e incidencias. Quitar secretos/datos/resultados privados. Un enlace
    a un repositorio privado no equivale a documentación accesible públicamente.
19. **Revisar el candidato publicable.** Persona responsable revisa versión,
    commit/tag, metadatos, dependencias, licencia, pruebas, soporte y manifiesto
    de hashes. La Beta privada no cumple por sí sola la autorización pública.
20. **Autorizar el ensayo TestPyPI (P20).** Aprobar destino, versión y hashes
    concretos. Tras la subida real, comprobar instalación limpia, origen de
    dependencias, `pip check`, API/CLI y mismos hashes. Corregir y repetir si
    cambian bytes; conservar la evidencia. TestPyPI también es público.
21. **Autorizar la publicación final.** Aprobar explícitamente PyPI y los
    artefactos exactos después de resolver las puertas vigentes. No reconstruir
    silenciosamente entre validación y subida. Verificar instalación desde PyPI
    fuera del repositorio y registrar quién publicó y qué recibió el consumidor.
22. **Aceptar mantenimiento público (Q11/Q12 y paso 20).** Definir soporte y
    recuperación, observar usuarios externos reales y reunir evidencia de uso.
    No crear usuarios, descargas, estrellas o reseñas para aumentar porcentajes.

## Acceso y continuidad que requieren decisión del propietario

23. **Plataformas restantes (M04).** Proporcionar acceso a entornos nativos
    autorizados del alcance comprometido todavía sin evidencia, o nombrar un
    operador que ejecute el kit y devuelva recibos completos con arquitectura,
    Python, dependencias, comandos, hashes y fallos/omisiones. El laboratorio
    ARM y esta máquina Windows no permiten acreditar por sustitución macOS o
    Linux x64. Los perfiles técnicos que puedan ejecutarse en los entornos
    existentes siguen siendo trabajo técnico; conceder acceso no los aprueba.
24. **Enlace fijo del dataset, si se necesita.** Elegir responsable y hosting/
    dominio estable o aceptar y gestionar el enlace temporal ya entregado.
    El Quick Tunnel arranca con servicios de usuario, pero cambiará de hostname
    si su proceso reinicia. La persona responsable debe consultar el journal y
    comunicar el enlace vigente a la tutora. No se necesita compartir contraseña
    ni publicar claves; el dato público y sus manifiestos permanecen respaldados.

## Fuentes de los requisitos de los índices

La [guía oficial de empaquetado](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
describe metadatos, licencia, construcción y distribución. La
[guía de TestPyPI](https://packaging.python.org/en/latest/guides/using-testpypi/)
explica la cuenta separada y el ensayo. PyPI documenta
[roles de proyecto](https://docs.pypi.org/organization-accounts/roles-entities/),
[retención de nombres](https://docs.pypi.org/project-management/name-retention/)
y [Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/).
Los requisitos de tesis y equipo provienen de
[T01–T22](THESIS_CURRENT_RESULT_20261011.json),
[M01–M16](MATURITY_MATRIX.md) y [responsabilidades](TEAM_INTEGRATION.md).
