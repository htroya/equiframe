# Dataset SERCOP 2025 entregado para consulta

**Actualización 13 de octubre:** la [ruta compartida y el origen HTTPS](SERCOP_SHARED_ACCESS_20261013.md)
ahora usan `/var/tmp/equiframe-public-sercop-2025/entrega-20261012-v1`.
El enlace de la tutora se conservó y la entrega antigua del home se eliminó
después de verificar la copia y los 286 enlaces. El recibo del 12 de octubre
siguiente conserva su corte histórico.

La [carpeta pública](https://garlic-comments-semiconductor-assume.trycloudflare.com/)
permite leer/descargar los datos sin cuenta. La entrega permanece en
`/home/hernan/public-sercop-2025/entrega-20261012-v1`, con archivos 0444 y
directorios 0555. La copia Windows está en
`local-data/sercop/2025/08_entrega_tutora/20261012-v1`, excluida de Git.

El [recibo comprobado](SERCOP_PUBLIC_DELIVERY_RESULT_20261012.json) registra
287 archivos: 39 descargas oficiales JSON/CSV/XLSX, 104 tablas CSV y 104
Parquet, 13 copias Excel legibles, referencias oficiales, procedencia,
diccionario, índice y manifiesto. El payload pesa 1.224.573.458 bytes sin el
manifiesto. Su SHA-256 es
`712022f8470428f25fa12b307e301ad6ef6fb0f9c59634ab8b90569380ac279c`.
No se publicó el SDK privado, credenciales ni validación privada.

| Tabla anual | Filas exportadas |
|---|---:|
| Publicaciones/releases | 190.619 |
| Planificación | 37.821 |
| Licitaciones | 185.536 |
| Adjudicaciones | 183.891 |
| Proveedores | 183.888 |
| Contratos | 180.465 |

Las seis tablas suman 962.220 filas; no son procesos únicos. Las exportaciones
mensuales y anual se mantienen separadas por solapamiento. La selección oficial
es `year=2025, method=all`, capturada el 12 de octubre de 2026; no aprueba por sí
sola las fechas/cohorte científica. CSV y Parquet conservan columnas de texto y
vacíos como cadenas vacías. El JSON original permite revisar ausencias y números
sin atribuirles conversiones hechas por el exportador.

Se verificaron todos los miembros instalados mediante hashes, 286 enlaces
HTTPS mediante HEAD y cuatro descargas completas. Tres HEAD omiten legalmente
Content-Length y esos tamaños no se declaran medidos. POST/PUT/PATCH/DELETE
devuelven 405. Opera Neon QA mostró correctamente el índice y los enlaces.
La entrega contiene **dataset, procedencia y diccionario; no EDA ni reflexión**.

## Continuidad del enlace

El origen escucha sólo en `127.0.0.1:8080`; un Quick Tunnel sale desde la VM.
Los dos servicios de usuario están habilitados y `Linger=yes`, por lo que no
dependen de mantener abierta la sesión SSH. No se necesitó contraseña sudo.
El [Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
es temporal, sin garantía de disponibilidad; un reinicio de su proceso puede
producir otro hostname. No existe una caducidad fija configurada. Para revisar:

```bash
systemctl --user status equiframe-sercop-2025.service equiframe-sercop-https.service
journalctl --user -u equiframe-sercop-https.service --no-pager -n 40
```

Si realmente falla, el propietario puede reiniciar los servicios de usuario,
consultar el nuevo enlace en el journal y comunicarlo a la tutora. No se
promete que el hostname anterior siga funcionando. Hosting estable/dominio
requiere una decisión del propietario; no se crearon cuentas ni recursos pagos.
No se reinicia el servicio como parte de análisis posteriores.

El [depósito ampliado local](SERCOP_LOCAL_REPOSITORY_20261012.md) conserva además
capturas históricas, JSON sin comprimir y evidencia privada. Su tamaño anterior
de 9.506.267.980 bytes, aproximadamente 8,85 GiB, no obliga a duplicar todo ese
material en una carpeta pública. La captura oficial completa se conserva en
los ZIP JSON entregados sin pérdidas.
