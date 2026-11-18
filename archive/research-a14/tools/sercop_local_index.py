"""Finalize a complete local SERCOP archive with portable indexes and hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
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


def read(path):
    return json.loads(path.read_text("utf-8"))


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(
            value, output, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        )
        output.write("\n")


def member(root, name):
    relative = Path(name)
    require(
        not relative.is_absolute() and relative.parts and ".." not in relative.parts,
        "Unsafe local reference",
    )
    for index in range(1, len(relative.parts) + 1):
        require(
            not (root / Path(*relative.parts[:index])).is_symlink(),
            "Linked local member",
        )
    path = root / relative
    require(
        path.resolve().is_relative_to(root) and path.is_file(),
        "Local member missing or outside archive",
    )
    return path


def finalize(root):
    root = root.resolve()
    require(
        root.is_dir() and not root.is_symlink(), "Existing local repository required"
    )
    catalog_path = root / "03_metadatos/local-index-v1.json"
    report_path = root / "03_metadatos/local-result-v1.json"
    readme_path = root / "README.md"
    require(
        not any(path.exists() for path in (catalog_path, report_path, readme_path)),
        "Preserve previous indexes",
    )
    acquisitions = read(root / "03_metadatos/current-acquisition.json")
    require(
        len(acquisitions) == 39
        and all(
            row["status"] == "PASS" and row["zip_crc_verified"] for row in acquisitions
        ),
        "Incomplete 2025 acquisition",
    )
    require(
        {
            (row["selection"]["month"], row["selection"]["format"])
            for row in acquisitions
        }
        == {(month, kind) for month in range(13) for kind in ("json", "csv", "xlsx")},
        "Periods or formats differ",
    )
    exports = read(root / "03_metadatos/organized-exports.json")
    files = exports["files"]
    require(len(files) == 130, "Incomplete organized originals")
    csv = [row for row in files if row["kind"] == "csv"]
    require(
        len(csv) == 104
        and all(row["projection"]["full_readback_verified"] for row in csv),
        "Incomplete CSV projections",
    )
    snapshots = []
    for identity in (
        "9ee4e5f94f44e42c89ade804d00ed69cd24604d246ad6450a4a43b2bd42e3632",
        "80201404465d6c212e4ad53c60e6a928ceebf0eadfb57a0e200805b49a1894a3",
    ):
        path = root / "02_tablas" / identity[:16] / "catalog.json"
        snapshot = read(path)
        require(
            snapshot["source_sha256"] == identity
            and snapshot["full_readback_verified"]
            and snapshot["duplicates_dropped"] is False
            and snapshot["source_numbers_converted_to_float"] is False,
            "Incomplete snapshot or identity drift",
        )
        snapshots.append(
            {
                "catalog": path.relative_to(root).as_posix(),
                "catalog_sha256": digest(path),
                "source_sha256": identity,
                "packages": snapshot["packages"],
                "releases": snapshot["releases"],
                "award_occurrences": snapshot["award_occurrences"],
                "collection_count": snapshot["collection_count"],
                "occurrence_rows": snapshot["total_occurrence_rows"],
                "scalar_occurrences": snapshot["scalar_occurrences"],
                "tables": snapshot["tables"],
            }
        )
    references = read(root / "03_metadatos/reference-acquisition.json")
    require(
        len(references) == 21 and all(row["status"] == "PASS" for row in references),
        "Reference acquisition incomplete",
    )
    expected = {}
    for row in acquisitions + references:
        expected[row["file"]] = row["sha256"]
    for row in files:
        if row["kind"] == "xlsx":
            require(row["original_bytes"] is True, "Original XLSX bytes required")
            expected[row["file"]] = row["source_sha256"]
        else:
            expected[row["file"]] = row["sha256"]
        if "projection" in row:
            expected[row["projection"]["file"]] = row["projection"]["parquet_sha256"]
    for snapshot in snapshots:
        for row in snapshot["tables"]:
            expected[row["file"]] = row["sha256"]
    consumer_path = root / "04_evidencias/consumidor-local-20261012-v1/result.json"
    comparison_path = (
        root / "04_evidencias/comparacion-capturas-anuales-20261012-v1/result.json"
    )
    example_path = root / "07_ejemplos/agrupacion-anual-normal-v1/result.json"
    consumer, comparison, example = (
        read(path) for path in (consumer_path, comparison_path, example_path)
    )
    require(
        consumer["all_expected"]
        and len(consumer["native_full_readbacks"]) == 312
        and all(row["status"] == "PASS" for row in consumer["native_full_readbacks"])
        and len(consumer["sdk_summary_comparisons"]) == 9
        and all(row["status"] == "PASS" for row in consumer["sdk_summary_comparisons"]),
        "Native full readback or summary comparison incomplete",
    )
    require(
        example["all_expected"]
        and len(example["sdk_comparisons"]) == 7
        and all(
            row["status"] == "PASS" and row["complete"]
            for row in example["sdk_comparisons"]
        ),
        "Award example incomplete",
    )
    require(
        comparison["all_packages_checked"]
        and comparison["counts"]["package_positions"] == 190619,
        "Snapshot comparison incomplete",
    )
    inventory = []
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "Linked archive member")
        if path.is_file():
            name = path.relative_to(root).as_posix()
            observed = digest(path)
            require(
                name not in expected or observed == expected[name],
                "Recorded source/table/reference changed: " + name,
            )
            inventory.append(
                {"file": name, "bytes": path.stat().st_size, "sha256": observed}
            )
    require(
        set(expected) <= {row["file"] for row in inventory},
        "Recorded archive member missing",
    )
    annual = {
        Path(row["member"]).stem.removesuffix("_2025"): row["projection"]["rows"]
        for row in csv
        if row["month"] == 0
    }
    index = {
        "schema": "equiframe.sercop-local-index.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": inventory,
        "original_exports": files,
        "json_snapshots": snapshots,
        "references": references,
        "verified_recorded_hashes": len(expected),
        "new_data_transferred_to_vm": False,
        "word_modified": False,
        "git_tracked": False,
    }
    write(catalog_path, index)
    report = {
        "schema": "equiframe.sercop-local-result.v1",
        "candidate": "0.12.0a13",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "acquisitions": {
            "responses": len(acquisitions),
            "compressed_bytes": sum(row["bytes"] for row in acquisitions),
            "member_bytes": sum(
                item["bytes"] for row in acquisitions for item in row["members"]
            ),
            "annual_and_monthly": True,
            "formats": ["json", "csv", "xlsx"],
            "selector_method": "all",
            "zip_crc_verified": True,
        },
        "organized_originals": {
            "json": 13,
            "csv": 104,
            "xlsx": 13,
            "total": len(files),
        },
        "csv_projections": {
            "tables": len(csv),
            "rows_including_annual_monthly_overlap": sum(
                row["projection"]["rows"] for row in csv
            ),
            "full_source_readback_verified": True,
            "all_columns_utf8": True,
            "annual_rows_by_export": annual,
        },
        "json_snapshots": [
            {key: value for key, value in row.items() if key != "tables"}
            for row in snapshots
        ],
        "references": len(references),
        "complete_snapshot_comparison": {
            "receipt_sha256": digest(comparison_path),
            "counts": comparison["counts"],
            "comparison_alignment": "source array/package positions; not OCID-keyed semantic change attribution",
        },
        "native_consumer": {
            "receipt_sha256": digest(consumer_path),
            "result": consumer,
        },
        "award_example": {
            "receipt_sha256": digest(example_path),
            "annual_rows": example["annual_award_records"],
            "currency_groups": example["currency_groups"],
            "sdk_comparisons": 7,
            "all_expected": True,
        },
        "custody": {
            "file_inventory": catalog_path.relative_to(root).as_posix(),
            "file_inventory_sha256": digest(catalog_path),
            "files_checked": len(inventory),
            "bytes_checked": sum(row["bytes"] for row in inventory),
            "recorded_source_table_reference_hashes_checked": len(expected),
        },
        "new_data_transferred_to_vm": False,
        "git_tracked": False,
        "word_modified": False,
        "automatic_rubric_points": 0,
        "scientific_approval": False,
        "limits": [
            "Annual/monthly and collection occurrence totals contain overlaps; no deduplication or unique-process claim.",
            "All original formats preserved; XLSX cell-by-cell semantic readback is not claimed.",
            "Native full CSV table checks differ from SDK comparisons of summary rows and currency aggregates.",
            "Positional snapshot inequality is not proof that that many unique procurements changed.",
            "OCDS schemas captured, not complete extension/domain or approved cohort validation.",
            "No real DW, normal training cohort, human labels or thesis hypothesis approval inferred.",
        ],
    }
    write(report_path, report)
    rows = "\n".join(f"| {name} | {count:,} |" for name, count in annual.items())
    contents = f"""# SERCOP 2025: depósito local completo para EquiFrame A13

Este directorio está dentro del repositorio y excluido de Git. No se ha
transferido a la VM. Se conserva el selector oficial `method=all`, anual y
doce meses, en JSON, CSV y XLSX: 39 respuestas originales con SHA-256 y CRC.

## Qué abrir

- [Índice portable, esquemas, filas y hashes](03_metadatos/local-index-v1.json).
- [Recibo consolidado de preparación y validación](03_metadatos/local-result-v1.json).
- [Originales organizados y CSV/Parquet por período](03_metadatos/organized-exports.json).
- [Procedencia de 21 referencias oficiales](03_metadatos/reference-acquisition.json).
- [Comparación completa entre capturas anuales](04_evidencias/comparacion-capturas-anuales-20261012-v1/result.json).
- [Lecturas completas nativas y comparaciones de resúmenes](04_evidencias/consumidor-local-20261012-v1/result.json).
- [Ejemplo ejecutado: adjudicaciones por moneda](07_ejemplos/agrupacion-anual-normal-v1/result.json).

## Organización

`01_fuentes_originales` conserva las respuestas y la captura histórica.
`02_tablas/<SHA16>` contiene las 28 colecciones anidadas completas de cada
captura anual JSON, con posiciones, padres, payload y tipos exactos.
`03_metadatos` guarda catálogos e inventarios. `04_evidencias` conserva las
validaciones actuales y los dos archivos completos históricos devueltos de
la VM. `05_exports/consulta_20261012/mesNN` contiene los JSON, los ocho CSV
y el XLSX original por período. `06_referencias` contiene políticas, licencia
declarada y esquemas. `07_ejemplos` contiene resultados de uso reproducible.

## Filas de la exportación anual CSV

| Exportación | Filas |
|---|---:|
{rows}

Las 104 tablas CSV/Parquet suman {report["csv_projections"]["rows_including_annual_monthly_overlap"]:,}
filas con solapamiento anual/mensual. Es una suma de registros de exportación,
no procesos únicos. Las tablas anidadas JSON son ocurrencias de colecciones,
tampoco procesos únicos. Las capturas tienen hashes distintos y se consultan
separadamente; no se sustituyen sus identidades.

## Uso desde la raíz del repositorio

```powershell
python -B -X utf8 tools/sercop_awards_example.py --help
python -B -X utf8 tools/sercop_local_consumer.py --help
python -B -X utf8 tools/sercop_awards_example.py --workspace .. --root local-data/sercop/2025 --output local-data/sercop/2025/07_ejemplos/mi-prueba-01
```

Los ejemplos reciben este directorio como `--root` y requieren las dependencias
del perfil de consumidor A13. Consultar sus argumentos antes de elegir una
carpeta nueva para `--output`: no sobrescriben ejecuciones anteriores.
En Python, las tablas CSV Parquet se leen mediante `pandas.read_parquet`,
`polars.read_parquet` o `DuckDB read_parquet`. Sus columnas son texto UTF-8;
los vacíos conservan `""`. No inferir números en identificadores ni sumar
importes entre monedas. Los JSON preservan texto Decimal exacto y columnas
`@type:` que distinguen ausencia, null y cada tipo de escalar.

El ejemplo anual carga las 183.891 adjudicaciones CSV y compara agrupaciones
de conteos por moneda con un oráculo independiente construido desde el CSV.
No convierte ese agregado en una comparación SDK de todas las filas brutas.

## Alcance científico y procedencia

Estos datos están preparados para un consumidor local. No sustituyen el DW
del equipo, una cohorte normal aprobada, etiquetas humanas ni resultados de
tesis. Guardar esquemas OCDS no es validar todas las extensiones o el dominio.
Los XLSX originales se preservan; no se afirma una revisión celda por celda.

Fuente: [portal oficial SERCOP](https://datosabiertos.compraspublicas.gob.ec/PLATAFORMA/datos-abiertos/).
La fuente declara [CC BY 3.0 Ecuador](https://creativecommons.org/licenses/by/3.0/ec/);
esa declaración no determina la licencia de EquiFrame. El Word permanece intacto.
"""
    with readme_path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(contents)
    print(
        json.dumps(
            {
                "status": "PASS",
                "files_checked": len(inventory),
                "recorded_hashes_checked": len(expected),
                "index_sha256": digest(catalog_path),
                "report_sha256": digest(report_path),
                "readme_sha256": digest(readme_path),
            }
        )
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.root)


if __name__ == "__main__":
    main()
