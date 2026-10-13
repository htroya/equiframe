# Instrucciones para ejecutar ejemplo_awards.py

## Dónde se ejecuta

**En la VM** (157.137.227.1), no desde tu computadora local.
El archivo `awards_2025.parquet` vive en la VM dentro de la carpeta
de snapshots que publica Hernan. Para ejecutarlo desde tu computadora
necesitarías montar la carpeta de la VM por red, lo cual no está
configurado. Lo más simple es conectarte a la VM por SSH y correr
el script ahí.

---

## 1. Conectarse a la VM

```bash
ssh equiframe-vm
```

O si usas la clave directamente:

```bash
ssh -i "C:\Users\user\Documents\tesis maestria\oracle Virtual Machine\private\equiframe-vm.key" ubuntu@157.137.227.1
```

---

## 2. Activar el entorno Python en la VM

```bash
cd /home/ubuntu
source venv312/bin/activate
```

---

## 3. Instalar dependencias (solo la primera vez)

```bash
pip install polars
```

Verifica que ya esté instalado:

```bash
python -c "import polars; print(polars.__version__)"
```

---

## 4. Ubicarse en la carpeta del componente

```bash
cd /home/ubuntu/equiframe/packages/equiframe-data
```

---

## 5. Ejecutar el ejemplo

```bash
python ejemplo_awards.py /home/ubuntu/datos/dw/snapshots
```

> Reemplaza `/home/ubuntu/datos/dw/snapshots` por la ruta real
> que confirme Hernan donde publica sus snapshots.

---

## Qué muestra en pantalla

```
Snapshots disponibles : ['20261001', '20260601']
Usando version        : 20261001
Timestamp del snapshot: 2026-10-13T12:00:00+00:00
Tablas en el snapshot :
  - dataset/anual/parquet/awards_2025.parquet  (183.891 filas, ...)

Descargando dataset/anual/parquet/awards_2025.parquet ...
OK  awards_2025: awards_2025.parquet (...bytes, SHA-256 verificado)

--- awards_2025.parquet ---
Filas    : 183.891
Columnas : N

Nombres de columnas:
  ocid       (String)
  award_id   (String)
  ...

Primeras 3 filas:
...
```

---

## Dónde quedan los resultados

El archivo descargado se guarda en:

```
/home/ubuntu/equiframe/packages/equiframe-data/descargados/awards_2025.parquet
```

Esta carpeta está en `.gitignore` — no aparece en GitHub.

Para guardar los resultados del análisis usa la carpeta:

```
/home/ubuntu/equiframe/eda-resultados/
```

También está en `.gitignore` y es para uso local en la VM.

---

## Si algo falla

| Error | Causa | Solución |
|---|---|---|
| `No hay snapshots publicados` | Hernan no ha publicado datos aún | Coordinarse con Hernan |
| `Artefacto 'dataset/...' no encontrado` | La ruta en el manifiesto es diferente | Revisar con Hernan el nombre exacto del archivo |
| `FileNotFoundError: Snapshot '...' no encontrado` | La ruta base es incorrecta | Verificar la ruta con Hernan |
| `SHA-256 incorrecto` | El archivo se corrompió en la descarga | Volver a correr el script |
| `ModuleNotFoundError: polars` | Polars no instalado | `pip install polars` |
