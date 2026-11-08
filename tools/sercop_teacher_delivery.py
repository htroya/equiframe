"""Prepare a public, byte-preserving SERCOP dataset delivery, without EDA."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


def prepare(root, output, archive_path):
    root = root.resolve(strict=True)
    require(not output.exists() and not archive_path.exists(), "Preserve prior deliveries")
    require(output.resolve().is_relative_to(root), "Delivery must stay inside local dataset")
    require(not archive_path.resolve().is_relative_to(output.resolve()), "Archive outside delivery")
    catalog_path = root / "03_metadatos/organized-exports.json"
    catalog = json.loads(catalog_path.read_text("utf-8"))
    files = catalog["files"]
    csv_records = [item for item in files if item["kind"] == "csv"]
    require(len(csv_records) == 104, "Require all eight CSV tables for all thirteen periods")
    require({item["month"] for item in csv_records} == set(range(13)), "Annual/month coverage differs")
    output.mkdir(parents=True)
    payloads, tables, acquisitions = [], [], []

    def copy(source, target, expected):
        require(source.is_file() and not source.is_symlink(), "Regular public source required")
        require(source.resolve().is_relative_to(root), "Source outside public dataset")
        require(digest(source) == expected, "Source hash differs: " + source.name)
        destination = output / target
        require(destination.resolve().is_relative_to(output.resolve()), "Destination outside delivery")
        destination.parent.mkdir(parents=True, exist_ok=True)
        require(not destination.exists(), "Repeated delivery path")
        shutil.copyfile(source, destination)
        require(digest(destination) == expected and digest(source) == expected, "Byte copy changed")
        payloads.append({"file": target, "bytes": destination.stat().st_size, "sha256": expected})

    for month in range(13):
        period = "anual" if month == 0 else f"mensual/{month:02d}"
        for kind in ("json", "csv", "xlsx"):
            original = root / f"01_fuentes_originales/consulta_20261012/sercop_2025_mes{month:02d}_{kind}.zip"
            receipt = json.loads(original.with_name(original.name + ".receipt.json").read_text("utf-8"))
            require(receipt["status"] == "PASS" and receipt["selection"] == {"format": kind, "method": "all", "month": month, "year": 2025}, "Official selection differs")
            target = "originales/" + original.name
            copy(original, target, receipt["sha256"])
            acquisitions.append({"file": target, "format": kind, "year": 2025, "month": month, "method": "all", "source_url": receipt["url"], "retrieved_at_utc": receipt["retrieved_at_utc"], "sha256": receipt["sha256"], "bytes": receipt["bytes"]})
        for item in [item for item in csv_records if item["month"] == month]:
            projection = item["projection"]
            require(projection["full_readback_verified"] is True, "Prepared table must have full readback evidence")
            name = Path(item["file"]).name
            csv_target = f"dataset/{period}/csv/{name}"
            parquet_target = f"dataset/{period}/parquet/{Path(projection['file']).name}"
            copy(root / item["file"], csv_target, item["sha256"])
            copy(root / projection["file"], parquet_target, projection["parquet_sha256"])
            tables.append({"period": period, "month": month, "csv": csv_target, "parquet": parquet_target, "rows": projection["rows"], "columns": projection["columns"], "physical_types": projection["physical_types"], "empty_value": "", "csv_sha256": item["sha256"], "parquet_sha256": projection["parquet_sha256"], "logical_row_sha256": projection["source_row_sha256"], "csv_parquet_full_readback_verified_before_delivery": True, "source_archive_sha256": item["source_archive_sha256"]})
        spreadsheet = next(item for item in files if item["kind"] == "xlsx" and item["month"] == month)
        copy(root / spreadsheet["file"], f"dataset/{period}/excel/sercop_2025_mes{month:02d}.xlsx", spreadsheet["source_sha256"])
        print(json.dumps({"month": month, "status": "copied_and_sha256_verified"}), flush=True)

    references = json.loads((root / "03_metadatos/reference-acquisition.json").read_text("utf-8"))
    reference_index = []
    for item in references:
        target = "referencias/" + Path(item["file"]).name
        copy(root / item["file"], target, item["sha256"])
        reference_index.append({"file": target, "source_url": item["url"], "sha256": item["sha256"], "bytes": item["bytes"], "retrieved_at_utc": item["retrieved_at_utc"]})
    (output / "metadata").mkdir()
    write(output / "metadata/fuentes.json", acquisitions)
    write(output / "metadata/tablas-y-diccionario.json", tables)
    write(output / "metadata/referencias.json", reference_index)
    readme = """SERCOP 2025 — Dataset para consulta de la tutora

Fuente y atribución: Servicio Nacional de Contratación Pública del Ecuador (SERCOP).
Portal: https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos/
Selección oficial: year=2025, method=all; anual month=0 y meses 1–12.
Captura descargada el 12 de octubre de 2026; conserva retrospectivamente
la publicación ofrecida por el portal, no una captura tomada durante 2025.
Licencia declarada por la fuente: Creative Commons Atribución 3.0 Ecuador.
https://creativecommons.org/licenses/by/3.0/ec/

originales/: las 39 respuestas oficiales originales JSON, CSV y XLSX.
dataset/anual/: ocho CSV y sus ocho Parquet, más el XLSX anual legible.
dataset/mensual/01–12/: las mismas tablas y XLSX por cada mes.
metadata/tablas-y-diccionario.json: columnas, tipos, filas, hashes y procedencia.
metadata/fuentes.json: URLs oficiales, fecha de descarga y selección exacta.
referencias/: copias de documentación oficial y esquemas, con índice de fuentes.

Uso: elegir el archivo anual O una selección de meses. No concatenar el anual
y sus meses para evitar duplicar datos. Las filas son registros publicados;
los conteos por tabla no equivalen a un número único de procesos o de personas.
No se eliminan duplicados ni se corrigen registros de la fuente.
CSV UTF-8 y Parquet mantienen todas las columnas como texto y los vacíos como
cadena vacía. Identificadores y monedas se conservan exactamente. Importes
y fechas necesitan una conversión explícita para un uso posterior.
Los JSON completos están en los ZIP originales; no se publica aquí una
proyección parcial como sustituto. Los XLSX se conservan por copia exacta,
sin afirmar una comprobación semántica de cada celda. Guardar los esquemas
OCDS no certifica por sí solo todos los registros ni sus extensiones.

Lectura Python: pandas.read_csv(ruta, dtype=str, keep_default_na=False),
pandas.read_parquet(ruta), polars.read_parquet(ruta), o DuckDB read_parquet.
En Excel, importar CSV como UTF-8 y fijar identificadores como texto; también
se proporciona el XLSX original. El manifiesto permite verificar cada archivo.

Esta entrega contiene únicamente el dataset y su documentación de procedencia.
No incluye EDA, reflexión, Word, credenciales, código privado ni resultados
de validación científica. Los datos pertenecen a su fuente; no se atribuye
una licencia de EquiFrame a este dataset. Acceso HTTP de consulta y descarga.
"""
    (output / "LEEME.txt").write_text(readme, encoding="utf-8")
    annual = [item for item in tables if item["month"] == 0]
    annual_rows = "".join(f'<tr><td>{html.escape(Path(item["csv"]).name)}</td><td>{item["rows"]:,}</td><td><a href="{item["csv"]}">CSV</a> · <a href="{item["parquet"]}">Parquet</a></td></tr>' for item in annual)
    monthly = "".join(f'<li><a href="dataset/mensual/{month:02d}/">Mes {month:02d}</a></li>' for month in range(1, 13))
    original_links = "".join(f'<li><a href="{item["file"]}">{Path(item["file"]).name}</a> ({item["bytes"] / 1024**2:.2f} MiB)</li>' for item in acquisitions)
    page = f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Dataset SERCOP 2025</title><style>body{{font:17px/1.6 system-ui,sans-serif;max-width:980px;margin:40px auto;padding:0 24px;color:#172b3b;background:#fafcfd}}h1,h2{{line-height:1.25}}a{{color:#075b9a}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #d6e0e8}}.note{{background:#eaf3f8;padding:16px;border-radius:8px}}@media(max-width:600px){{body{{margin:24px auto;font-size:15px}}td,th{{padding:6px}}}}</style><h1>Dataset SERCOP 2025</h1><p>Entrega de datos para consulta de la tutora. Fuente: Servicio Nacional de Contratación Pública del Ecuador. Captura del 12 de octubre de 2026, selector oficial <code>year=2025, method=all</code>.</p><p class="note">Acceso de lectura y descarga. El archivo anual y los meses se ofrecen separadamente. Elegir uno de esos soportes para evitar duplicar registros. Los datos se conservan sin limpieza ni exclusiones.</p><p><a href="LEEME.txt">Leer instrucciones y alcance</a> · <a href="metadata/tablas-y-diccionario.json">Diccionario y conteos</a> · <a href="metadata/fuentes.json">Procedencia</a> · <a href="manifest.json">SHA-256 de los archivos</a></p><h2>Dataset anual completo</h2><table><thead><tr><th>Tabla</th><th>Registros publicados</th><th>Descargas</th></tr></thead><tbody>{annual_rows}</tbody></table><p><a href="dataset/anual/excel/sercop_2025_mes00.xlsx">Descargar Excel anual original</a></p><h2>Dataset mensual</h2><ul>{monthly}</ul><h2>Los 39 archivos oficiales originales</h2><p>JSON completo comprimido, exportación CSV y XLSX, para el año y cada mes. Los formatos se conservan tal como los ofreció la fuente.</p><details><summary>Ver todas las descargas originales</summary><ul>{original_links}</ul></details><h2>Formato y procedencia</h2><p>CSV UTF-8 y Parquet: todas las columnas permanecen como texto; los vacíos se conservan como cadenas vacías. Identificadores y monedas se preservan. Los conteos corresponden a registros de exportación, no a personas o procesos únicos.</p><p>Licencia declarada por la fuente: <a href="https://creativecommons.org/licenses/by/3.0/ec/">CC BY 3.0 Ecuador</a>. Atribución: SERCOP. <a href="https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos/">Portal oficial</a> · <a href="metadata/referencias.json">Referencias y esquemas</a>.</p><p>Este directorio contiene el dataset y su documentación. No incluye EDA ni reflexión. El Word de la tesis no forma parte de la entrega.</p></html>'''
    (output / "index.html").write_text(page, encoding="utf-8")
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.relative_to(output).as_posix() not in {item["file"] for item in payloads}:
            payloads.append({"file": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)})
    manifest = {"schema": "equiframe.sercop-public-dataset-delivery.v1", "created_at_utc": datetime.now(timezone.utc).isoformat(), "source": "SERCOP Ecuador", "source_catalog_sha256": digest(catalog_path), "tool_sha256": digest(Path(__file__)), "scope": "Dataset only; no EDA or reflection", "official_archives": 39, "csv_tables": 104, "parquet_tables": 104, "xlsx_readable_copies": 13, "annual_release_records": 190619, "annual_award_records": 183891, "annual_and_monthly_overlap": True, "source_bytes_unchanged": True, "all_files_verified_after_copy": True, "files": sorted(payloads, key=lambda item: item["file"])}
    write(output / "manifest.json", manifest)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "x", strict_timestamps=False) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                compression = zipfile.ZIP_STORED if path.suffix in (".zip", ".parquet", ".xlsx") else zipfile.ZIP_DEFLATED
                archive.write(path, path.relative_to(output).as_posix(), compress_type=compression, compresslevel=6)
    with zipfile.ZipFile(archive_path) as archive:
        require(archive.testzip() is None, "Delivery ZIP CRC differs")
        for item in payloads:
            value = hashlib.sha256()
            size = 0
            with archive.open(item["file"]) as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    value.update(block)
                    size += len(block)
            require(value.hexdigest() == item["sha256"] and size == item["bytes"], "Delivery archive readback differs")
    result = {"schema": "equiframe.sercop-public-dataset-package.v1", "status": "PASS", "delivery": str(output), "archive": str(archive_path), "archive_sha256": digest(archive_path), "archive_bytes": archive_path.stat().st_size, "manifest_sha256": digest(output / "manifest.json"), "files_including_manifest": len(payloads) + 1, "payload_bytes_excluding_manifest": sum(item["bytes"] for item in payloads), "all_file_sha256_verified": True, "archive_full_readback_verified": True, "contains_eda": False, "contains_reflection": False}
    write(archive_path.with_suffix(".receipt.json"), result)
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.root, args.output, args.archive)


if __name__ == "__main__":
    main()
