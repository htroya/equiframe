# Infraestructura — José

Espacio reservado para documentación/configuración reproducible de la VM y servicio. Nunca versionar claves privadas, tokens, contraseñas ni estado que contenga secretos.

El núcleo de EquiFrame debe poder desarrollarse y probarse localmente sin esta infraestructura.

---

## VM activa — EquiFrame Data Warehouse

| Campo | Valor |
|---|---|
| Proveedor | Oracle Cloud Infrastructure (OCI) — Always Free |
| Región | Bogotá (sa-bogota-1) |
| IP pública | 157.137.227.1 |
| Nombre | maestria-vnic |
| Sistema operativo | Ubuntu 22.04.5 LTS |
| Arquitectura | aarch64 (ARM) |
| Python | 3.10.12 |
| RAM total | 11 GB |
| RAM disponible | ~11 GB |
| Disco total | 45 GB |
| Disco usado | 4.6 GB (11%) |
| Disco disponible | 41 GB |

### Entorno Python

- Ruta del entorno virtual: `/home/ubuntu/venv`
- Activar: `source ~/venv/bin/activate`
- Paquetes instalados: `polars 1.44.2`, `duckdb 1.5.6`

### Estructura de carpetas

| Carpeta | Ruta | Contenido |
|---|---|---|
| Datos | `/home/ubuntu/datos/` | `releases_2025.json` (1.6 GB — OCDS SERCOP 2025) |
| Resultados | `/home/ubuntu/resultados/` | Salidas del ETL y consultas DuckDB |
| Respaldos | `/home/ubuntu/respaldos/` | Snapshots y copias del DW |
| ETL | `/home/ubuntu/cargar_json.py` | Script ETL: JSON → Polars DataFrames |

### Usuarios

| Usuario | Rol |
|---|---|
| ubuntu | Administrador principal |
| jair | Colaborador |
| hernan | Colaborador |

### Conexión SSH

```bash
ssh -i <llave_privada.key> <usuario>@157.137.227.1
```

### Nota sobre capacidad OCI ARM (Ampere A1)

Se intentó crear la VM en Ashburn con A1 Flex (ARM) pero OCI respondió
`Out of host capacity` en todos los dominios y configuraciones de RAM (2–12 GB).
La VM actual es AMD en región Bogotá. Ver `docs/OCI_INTEGRATION.md` para
el historial completo de intentos.

### Pendiente

- Instalar Python 3.12 (actualmente 3.10.12)
- Construir el archivo DuckDB del DW (`dw.duckdb`) en `/home/ubuntu/resultados/`
- Configurar respaldo automático a `/home/ubuntu/respaldos/`
