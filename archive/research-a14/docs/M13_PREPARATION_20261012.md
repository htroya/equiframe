# Preparación local del ensayo M13 original

El kit A13 está preparado y sellado localmente. **No se transfirió el ZIP ni
se inició el ensayo M13 en la VM**. El [recibo de preparación](M13_PREPARATION_RESULT_20261012.json)
registra identidades, alcance y estado de autorización. Este trabajo no añade
puntos a [madurez](MATURITY_MATRIX.md).

El ZIP privado `m13-kit.zip` contiene 50 archivos: los seis artefactos originales
del núcleo y benchmark 0.12.0a13 y consumidor 0.1.15, dos respaldos Git,
herramientas, manifiestos de pruebas y datos públicos de validación. Tiene
6.420.417 bytes y SHA-256
`c33e581011bae4077aafccb478a7e678af9ea2cf8ff381d5f3a3bec4d6adab03`.
Se verificaron por lectura del ZIP los hashes y tamaños de sus 48 archivos
declarados y la identidad del manifiesto candidato. No incluye Word ni
credenciales. Los artefactos originales no se reconstruyeron.

El candidato utiliza el commit `f9b4348e3ff51218f3a63494d7f13121cbda3a7d` del
repositorio, que desciende del `main` remoto observado. Esa identidad conserva
su instantánea aunque posteriormente se publiquen otros cambios. Los sdists
siguen ligados a sus propias fuentes originales.

| Suite original | Identidades de pruebas recogidas | Archivos de pruebas |
|---|---:|---:|
| Núcleo | 8.077 | 230 |
| Benchmark | 627 | 31 |
| Consumidor | 19 | 3 |

Estos números son la **colección local**, no pruebas aprobadas en la VM.
Los manifiestos fijan pytest 9.1.1 e Hypothesis 6.168.3. Los controles locales
de las herramientas de entrega pasaron en modo normal y optimizado: 54 pruebas
y 26 subpruebas, con una omisión documentada de Windows en cada modo.
Las repeticiones y subpruebas no se convierten en nuevos casos independientes.

El alcance explícito `M13-ARM-ORIGINAL-v1` conserva el criterio original ARM64
con Python 3.10 y 3.12. Exige identidad de intérprete, fuentes, scripts,
dependencias, datos y kit al terminar. El alcance predeterminado v2 mantiene
sus cuatro versiones de Python; no se reduce por ejecutar este ensayo.
Las demás plataformas, la matriz completa del consumidor M14 y los requisitos
científicos de tesis conservan sus pendientes.

La revisión automática de permisos rechazó el intento de transferencia porque
la autorización previa correspondía a otro archivo menor con cuatro
artefactos; este kit ampliado contiene seis, fuentes y datos de validación.
Se solicitó autorización explícita para este ZIP y destino. Sigue pendiente
su respuesta; el intento rechazado no se repitió por otra vía.

En la VM se creó solamente el directorio de entrada
`/home/hernan/equiframe-m13-kit-20261012-aec98a67`, con su subdirectorio de
laboratorios. El paso posterior a la autorización es cotejar el hash remoto,
extraer con el inventario cerrado, ejecutar ambos intérpretes en entornos
privados y devolver todos los recibos para validación estricta. Solo la
evidencia completa permitirá reevaluar M13.
