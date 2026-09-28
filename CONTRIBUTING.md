# Colaboración

Cada integrante clona <https://github.com/htroya/equiframe> usando su propia cuenta. No compartir token ni entorno virtual. José y Jhair se invitarán cuando Hernán disponga de sus usuarios; no hay invitaciones emitidas todavía.

Ramas sugeridas: `hernan/step-01-foundations`, `jose/data-access`, `jhair/dw-model`. Crear una rama por cambio coherente. Los cambios que afecten interfaces se acuerdan en PR con los responsables de ambos lados.

## Flujo

1. Leer la arquitectura y el paso asignado; indicar alcance en el issue.
2. Actualizar rama desde `main` y trabajar en el paquete propio.
3. Implementar comportamiento, pruebas necesarias y documentación del resultado real.
4. Ejecutar controles locales y CI existentes; registrar comandos y resultados.
5. Abrir PR con problema, comportamiento resultante, validación y límites. Otro integrante revisa antes de integrar cuando esté disponible.

Esta es una convención de equipo. La protección técnica de ramas/reviews depende del plan GitHub y se configurará/verificará cuando estén los colaboradores; no se declara habilitada.

## Archivos

Versionar código, configuración no secreta, documentación, manifests sin datos sensibles y fixtures sintéticos pequeños. Excluir snapshots reales, bases, modelos binarios, resultados privados, documentos de tesis, entornos y credenciales.

Decisiones del piloto se registran en `docs/DECISIONS.md`; cambios de requisitos también en `docs/THESIS_TRACEABILITY.md`. Si una API descrita aún no existe, indicar especificación. No añadir funciones vacías para mostrar avance.

## Permisos

GitHub distingue propietario y colaboradores en repositorios personales. Los colaboradores pueden leer/escribir y gestionar PR/issues; el propietario conserva ajustes administrativos. Para tres administradores se requiere una organización. Referencia: [permisos oficiales](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository).

No publicar en PyPI ni redistribuir datos sin la decisión correspondiente de los autores.
