# Contribuir a EquiFrame

El repositorio es privado. Cada colaborador utiliza su propia cuenta de GitHub y
un clon local; el propietario administra el acceso en **Settings → Collaborators**.

## Preparar el entorno

Instale Git, Python 3.12 y un editor. Autentíquese en GitHub con su propia cuenta,
clone el repositorio y abra la carpeta que contiene `.git`.
Las instrucciones de entorno y los controles del paquete están en su
[README](packages/equiframe/README.md#instalación-reproducible).

La rama principal `main` contiene la API disponible. Cree las ramas de trabajo
desde su versión actualizada; indique en el PR cualquier dependencia de otro cambio
aún no integrado.

## Proponer un cambio

1. Describa el problema y el alcance en un issue o PR.
2. Actualice la rama base y cree una rama por cambio, por ejemplo
   `feat/snapshot-reader` o `fix/decimal-transport`.
3. Implemente comportamiento real, documentación y las pruebas apropiadas.
4. Ejecute los controles del componente afectado. Para el núcleo: Ruff, mypy,
   assets, pytest, build y verificación del wheel/sdist.
5. Suba la rama y abra un PR con el problema, el resultado del cambio, la
   validación y los límites relevantes. Solicite revisión antes de integrar.

Los cambios de interfaces compartidas se acuerdan con los responsables de ambos
componentes. La [distribución de componentes](docs/TEAM_INTEGRATION.md) evita
implementar infraestructura o reglas de dominio dentro del núcleo.

La CI vigente se inicia manualmente con `workflow_dispatch` y requiere activar
`run_platform_matrix` de forma explícita. Una subida de rama o un PR no ejecuta
la matriz. Los recibos de controles locales identifican los bytes comprobados;
no sustituyen un job remoto ni la revisión de otro integrante. Las pruebas
del servicio/DW real necesitan el entorno compartido y sus entregas.

## Documentación y archivos

Versione código, configuración no secreta, esquemas, documentación técnica y casos
sintéticos pequeños. Mantenga bases, datos reales, modelos binarios, resultados
privados, entornos y credenciales fuera de Git. `.env.example` puede contener
nombres y valores ficticios; nunca credenciales válidas.

Describa las APIs previstas como especificaciones hasta que estén implementadas y
comprobadas. Registre decisiones técnicas en `docs/DECISIONS.md`. Los cambios
metodológicos requieren también actualizar `docs/THESIS_TRACEABILITY.md`.

Cada cambio de dependencias exige actualizar el lock y repetir sus controles.
No publique paquetes ni redistribuya datos sin la decisión correspondiente de los autores.

## Revisión y permisos

El flujo de PR es una convención del equipo. A la fecha de esta revisión, el
repositorio privado utiliza GitHub Free y no tiene protección técnica de ramas:
GitHub exige Pro o Team para proteger ramas de repositorios privados.
[Disponibilidad de protección](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

La administración completa corresponde al propietario en un repositorio personal;
los colaboradores tienen acceso según los permisos concedidos.
[Permisos de repositorios personales](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository).
