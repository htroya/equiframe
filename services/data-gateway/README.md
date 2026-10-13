# Servicio de datos — José

API privada implementada y comprobada localmente. Se instala el wheel privado
`equiframe-data==0.1.0a14` junto con las dependencias de `requirements.txt`.
El despliegue operativo del DW permanece bajo José; no está activado por esta guía.

Antes de iniciar se requieren estas variables, fuera de Git:

| Variable | Contenido |
|---|---|
| `EQUIFRAME_GATEWAY_DATA_DIR` | Estado privado, controlado por el operador |
| `EQUIFRAME_GATEWAY_INPUT_DIR` | Carpeta de entrada existente y distinta del estado |
| `EQUIFRAME_GATEWAY_TOKEN_SHA256` | SHA-256 de un token de operación aleatorio de al menos 256 bits |
| `EQUIFRAME_GATEWAY_READ_TOKEN_SHA256` | SHA-256 de otro token para lectura; opcional |

Los tokens se generan con `secrets.token_urlsafe(32)`, se entregan por el canal
privado del equipo y se almacenan en un gestor de secretos o archivo protegido.
El servidor conserva sólo sus resúmenes y compara en tiempo constante.
No usar contraseñas humanas como tokens. No hay cuentas con contraseña ni
sesiones/cookies en esta API; si se agregan, deben incorporar Argon2/bcrypt y
cookies HttpOnly/Secure/SameSite. Rotar/revocar requiere cambiar el resumen y
reiniciar el gateway. Las credenciales de lectura y operación deben ser distintas.

Envíe `Authorization: Bearer <token>` únicamente sobre HTTPS. Las llamadas de
negocio rechazan HTTP. Use un terminador TLS revisado y Uvicorn en loopback:

```bash
uvicorn --app-dir services/data-gateway main:app --host 127.0.0.1 --port 8001 \
  --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-access-log
```

El proxy debe ser el único cliente de ese puerto y negociar TLS 1.3 según la
configuración de despliegue. [FastAPI documenta la confianza limitada en el proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).
No confiar en encabezados reenviados desde cualquier dirección.

Lectura: `GET /jobs`, `GET /jobs/{id}`. Operación: `POST /jobs`,
`POST /jobs/{id}/run`, `DELETE /jobs/{id}`. `/health` devuelve sólo estado.
No se ofrecen rutas de documentación/OpenAPI públicas.

`POST /jobs` acepta sólo `operation="load"`, un snapshot explícito y una clave
de idempotencia acotada. `run` acepta `{ "archivos": { "items": "items.parquet" } }`:
las rutas se resuelven exclusivamente dentro de la entrada autorizada. No acepta
SQL, comandos ni rutas absolutas del servidor.

JSON estricto sin campos adicionales; máximo 64 KiB, 256 archivos, cuatro
solicitudes activas y 120 solicitudes/minuto por proceso. El servicio controla
un escritor de filesystem entre procesos; las cuotas HTTP son por proceso y el
proxy debe fijar el límite agregado si se amplían workers. Los errores HTTP son
genéricos y los logs internos sólo registran IDs, clases de error y estado de
commit, sin tokens, claves de idempotencia, rutas de entrada ni valores.

Respuestas JSON con `nosniff`, `no-store`, CSP y HSTS bajo HTTPS. Los reportes
HTML del núcleo/EDA escapan datos por separado. Para entradas sensibles se
requieren volúmenes y backups cifrados en el entorno real: permisos privados y
SHA-256 no son cifrado. Esa configuración no se declara ejecutada aquí.

Las [garantías del equipo](../../docs/TEAM_INTEGRATION.md), contratos de dominio,
aceptación humana, backups y controles de producción conservan su validación propia.
