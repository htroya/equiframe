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
| Python | 3.10.12 (sistema) / 3.12.15 (entorno venv312) |
| RAM total | 11 GB |
| RAM disponible | ~11 GB |
| Disco total | 45 GB |
| Disco usado | 4.6 GB (11%) |
| Disco disponible | 41 GB |

### Entorno Python

- Entorno Python 3.10: `/home/ubuntu/venv` — `source ~/venv/bin/activate`
- Entorno Python 3.12: `/home/ubuntu/venv312` — `source ~/venv312/bin/activate` (recomendado)
- Paquetes instalados en venv312: `polars 2.0.0`, `duckdb 1.5.6`

### Estructura de carpetas

| Carpeta | Ruta | Contenido |
|---|---|---|
| Datos | `/home/ubuntu/datos/` | `releases_2025.json` (1.6 GB — OCDS SERCOP 2025) |
| Resultados | `/home/ubuntu/resultados/` | Salidas del ETL y consultas DuckDB |
| Respaldos | `/home/ubuntu/respaldos/` | Snapshots y copias del DW |
| ETL | `/home/ubuntu/cargar_json.py` | Script ETL: JSON → Polars DataFrames |

### Usuarios y permisos

| Usuario | Grupo | Rol | datos/ | resultados/ | respaldos/ |
|---|---|---|---|---|---|
| ubuntu | equiframe | Administrador — carga datos | leer + escribir | leer + escribir | leer + escribir |
| jair | equiframe | Colaborador | solo leer | leer + escribir | solo leer |
| hernan | equiframe | Colaborador | solo leer | leer + escribir | solo leer |

Solo `ubuntu` puede cargar o modificar datos en `datos/` y `respaldos/`.
Todos los colaboradores pueden guardar resultados en `resultados/`.

### Conexión SSH

Cada usuario se conecta con su propia llave privada (nunca compartir llaves entre personas):

```bash
# Administrador
ssh -i <llave_ubuntu.key> ubuntu@157.137.227.1

# Colaborador Jair
ssh -i <jair.key> jair@157.137.227.1

# Colaborador Hernan
ssh -i <hernan.key> hernan@157.137.227.1
```

Las llaves privadas se entregan individualmente y se guardan fuera del repositorio.
Nunca versionar archivos `.key`, `.pem` ni contraseñas en Git.

### Qué puede hacer cada usuario al conectarse

```bash
# Ver datos disponibles (todos)
ls ~/datos/

# Ejecutar el ETL (todos)
source ~/venv312/bin/activate
python ~/cargar_json.py --entrada ~/datos/releases_2025.json

# Guardar resultados (todos)
# Escribir en ~/resultados/

# Cargar nuevos datos (solo ubuntu)
# Copiar archivos a ~/datos/ o ~/respaldos/
```

### Nota sobre capacidad OCI ARM (Ampere A1)

Se intentó crear la VM en Ashburn con A1 Flex (ARM) pero OCI respondió
`Out of host capacity` en todos los dominios y configuraciones de RAM (2–12 GB).
La VM actual es AMD en región Bogotá. Ver `docs/OCI_INTEGRATION.md` para
el historial completo de intentos.

### Instalación de EquiFrame y ejecución de ejemplos en Ubuntu

```bash
# Activar entorno Python 3.12
source ~/venv312/bin/activate

# Instalar uv
pip install uv

# Clonar el repo (si no está clonado)
git clone https://github.com/htroya/equiframe.git ~/equiframe

# Crear carpeta de práctica
mkdir -p ~/practica-equiframe/jose-comparacion-01

# Instalar equiframe con extra arrow y ejecutar compare_local.py
cd ~/equiframe/packages/equiframe
uv run --locked --extra arrow python -I examples/compare_local.py \
    --work-dir ~/practica-equiframe/jose-comparacion-01
```

Resultado esperado: `different 2` — el ejemplo detecta 2 valores intercambiados a propósito.

### Pendiente

- ~~Instalar Python 3.12~~ ✓ instalado (3.12.15, entorno venv312)
- Construir el archivo DuckDB del DW (`dw.duckdb`) en `/home/ubuntu/resultados/`
- Configurar respaldo automático a `/home/ubuntu/respaldos/`
