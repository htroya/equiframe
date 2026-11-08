# Preparación de Trusted Publishing en TestPyPI

Alcance autorizado el 13 de octubre de 2026: preparar la identidad del
publicador. No construir otro paquete, subirlo, instalarlo desde TestPyPI ni
ejecutar GitHub Actions. Alpha privada sigue en `0.12.0a14`.

En el formulario [Add a new pending publisher](https://test.pypi.org/manage/account/publishing/)
de TestPyPI, escoger GitHub e introducir exactamente:

| Campo del formulario | Valor |
|---|---|
| TestPyPI Project Name | `equiframe` |
| Propietario / Owner | `htroya` |
| Nombre de repositorio / Repository name | `equiframe` |
| Nombre del flujo de trabajo / Workflow name | `publish-testpypi.yml` |
| Environment name | `testpypi` |

El nombre del workflow es solamente el archivo, sin `.github/workflows/`.
El archivo preparado está en
[publish-testpypi.yml](../.github/workflows/publish-testpypi.yml); su trabajo
actual comprueba la configuración con
[check_testpypi_publisher.py](../tools/check_testpypi_publisher.py).
Su ejecución es manual y no se ha iniciado. No contiene construcción, subida,
instalación de paquetes, secretos ni permisos OIDC. El código de envío se
añadirá cuando se autorice esa fase; registrar esta identidad no inicia una
publicación ni crea o reserva todavía el proyecto.

Crear o confirmar el entorno `testpypi` en
[Settings → Environments](https://github.com/htroya/equiframe/settings/environments),
limitado a `main`. Configurar revisores y evitar autoaprobación cuando el plan
de GitHub permita esas protecciones. La cuenta de TestPyPI y el entorno de
GitHub todavía requieren configuración del titular; no se han dado por
existentes ni aprobados. TestPyPI es independiente de PyPI.

La [configuración versionada](../tools/testpypi_publisher.json) mantiene
`publication_enabled: false`, igual que la política de publicación existente.
Para el futuro envío, PyPI documenta la acción de PyPA con `id-token: write`
limitado al trabajo de publicación y `repository-url:
https://test.pypi.org/legacy/`. Esa fase no está habilitada en esta entrega.
El paquete opcional `equiframe-benchmark` requiere otra identidad de proyecto
si se decide publicarlo; esta preparación cubre únicamente `equiframe`.

Estas operaciones humanas pertenecen al bloque del 10 % descrito en
[el método A14](A14_TECHNICAL_90_METHOD_20261013.md) y
[los requisitos humanos](HUMAN_REQUIREMENTS_20261012.md).

Fuentes oficiales: [crear un proyecto con Trusted Publishing](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/),
[configurar la identidad de GitHub](https://docs.pypi.org/trusted-publishers/adding-a-publisher/),
[publicar mediante OIDC](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
y [administrar entornos de GitHub](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
