"""
Pruebas del componente de acceso a datos — SnapshotClient.

Cubre los tres requisitos del punto 1:
  A. Seleccionar una versión de los datos     → list_snapshots / get_snapshot
  B. Consultar qué tablas contiene            → manifest.artifacts
  C. Obtener archivos verificando los hashes  → download_artifact
"""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from snapshot_client import SnapshotClient, ArtifactRef


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _crear_snapshot(base: Path, snap_id: str, tablas: dict[str, str]) -> None:
    """
    Crea un snapshot con manifiesto válido.
    tablas = {nombre_tabla: contenido_csv}
    """
    snap_dir = base / snap_id
    snap_dir.mkdir(parents=True, exist_ok=True)

    artifacts = []
    for tabla, contenido in tablas.items():
        archivo = snap_dir / f"{tabla}.csv"
        archivo.write_text(contenido, encoding="utf-8")
        artifacts.append({
            "table_name": tabla,
            "file_path":  f"{tabla}.csv",
            "size_bytes": archivo.stat().st_size,
            "sha256":     _sha256(archivo),
            "version":    snap_id,
            "row_count":  contenido.count("\n"),
        })

    manifiesto = {
        "snapshot_id": snap_id,
        "version":     snap_id,
        "source":      "prueba",
        "timestamp":   "2026-10-13T00:00:00+00:00",
        "artifacts":   artifacts,
    }
    (snap_dir / "manifest.json").write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ok(msg: str) -> None:
    print(f"  PASS  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    raise AssertionError(msg)


# ── A. Seleccionar versión ────────────────────────────────────────────────────

def test_listar_snapshots_vacio():
    """list_snapshots devuelve lista vacía si no hay snapshots publicados."""
    with tempfile.TemporaryDirectory() as tmp:
        client = SnapshotClient(base_dir=Path(tmp) / "snapshots")
        assert client.list_snapshots() == []
        ok("lista vacía cuando no hay snapshots")


def test_listar_snapshots_orden_descendente():
    """list_snapshots devuelve versiones de más reciente a más antigua."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for sid in ["20260101", "20260601", "20261001"]:
            _crear_snapshot(base, sid, {"fact_adjudicacion": "id,monto\n1,100"})

        client = SnapshotClient(base_dir=base)
        versiones = client.list_snapshots()
        assert versiones == ["20261001", "20260601", "20260101"]
        ok(f"versiones ordenadas descendente: {versiones}")


def test_listar_ignora_directorios_sin_manifiesto():
    """list_snapshots ignora carpetas que no tienen manifest.json."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _crear_snapshot(base, "20261001", {"fact_adjudicacion": "id,monto\n1,100"})
        (base / "carpeta_sin_manifiesto").mkdir()          # no debe aparecer
        (base / "20261001.tmp").mkdir()                    # carga en progreso, no aparece

        client = SnapshotClient(base_dir=base)
        versiones = client.list_snapshots()
        assert versiones == ["20261001"]
        ok("carpetas sin manifiesto no aparecen en la lista")


# ── B. Consultar tablas ───────────────────────────────────────────────────────

def test_consultar_tablas_de_snapshot():
    """get_snapshot devuelve el manifiesto con todas las tablas del snapshot."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _crear_snapshot(base, "20261001", {
            "fact_adjudicacion":     "id,monto\n1,100\n2,200",
            "dim_entidad":           "id,nombre\nE1,MinSalud",
            "adjudicacion_proveedor":"award_id,proveedor_id\n1,P1",
        })

        client = SnapshotClient(base_dir=base)
        manifiesto = client.get_snapshot("20261001")

        assert manifiesto.snapshot_id == "20261001"
        tablas = [a.table_name for a in manifiesto.artifacts]
        assert "fact_adjudicacion" in tablas
        assert "dim_entidad" in tablas
        assert "adjudicacion_proveedor" in tablas
        ok(f"tablas del snapshot: {tablas}")


def test_get_artifact_por_nombre():
    """SnapshotManifest.get_artifact devuelve la referencia correcta por nombre."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _crear_snapshot(base, "20261001", {
            "fact_adjudicacion": "id,monto\n1,500",
            "dim_fecha":         "fecha\n2026-01-01",
        })

        client = SnapshotClient(base_dir=base)
        manifiesto = client.get_snapshot("20261001")

        ref = manifiesto.get_artifact("fact_adjudicacion")
        assert ref is not None
        assert ref.table_name == "fact_adjudicacion"
        assert ref.size_bytes > 0
        ok("get_artifact devuelve referencia correcta por nombre de tabla")

        ref_inexistente = manifiesto.get_artifact("tabla_que_no_existe")
        assert ref_inexistente is None
        ok("get_artifact devuelve None para tabla inexistente")


def test_version_inexistente_lanza_error():
    """get_snapshot lanza FileNotFoundError si el snapshot no existe."""
    with tempfile.TemporaryDirectory() as tmp:
        client = SnapshotClient(base_dir=Path(tmp))
        try:
            client.get_snapshot("version_que_no_existe")
            fail("debio lanzar FileNotFoundError")
        except FileNotFoundError as e:
            assert "version_que_no_existe" in str(e)
            ok("versión inexistente lanza FileNotFoundError con mensaje claro")


# ── C. Descargar y verificar hashes ──────────────────────────────────────────

def test_descargar_y_verificar_hash_correcto():
    """download_artifact descarga el archivo y verifica tamaño + SHA-256."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _crear_snapshot(base, "20261001", {
            "fact_adjudicacion": "id,monto\n1,100\n2,200\n3,300",
        })

        client = SnapshotClient(base_dir=base)
        manifiesto = client.get_snapshot("20261001")
        ref = manifiesto.get_artifact("fact_adjudicacion")

        destino = base / "descargados"
        ruta_local = client.download_artifact(ref, destino)

        assert ruta_local.exists()
        assert ruta_local.stat().st_size == ref.size_bytes
        assert _sha256(ruta_local) == ref.sha256
        ok("archivo descargado y verificado (tamaño + SHA-256 correctos)")


def test_archivo_corrupto_rechazado_y_eliminado():
    """download_artifact rechaza un archivo con SHA-256 incorrecto y lo elimina."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        snap_dir = base / "snap-corrupto"
        snap_dir.mkdir(parents=True)
        csv = snap_dir / "fact.csv"
        csv.write_text("id,monto\n1,100", encoding="utf-8")

        ref = ArtifactRef(
            snapshot_id="snap-corrupto",
            table_name="fact_adjudicacion",
            file_path="fact.csv",
            size_bytes=csv.stat().st_size,
            sha256="hash_deliberadamente_incorrecto_0000000000000000000000000000",
        )

        client = SnapshotClient(base_dir=base)
        destino = base / "descargados"
        try:
            client.download_artifact(ref, destino)
            fail("debio rechazar el archivo corrupto")
        except ValueError as e:
            assert "SHA-256" in str(e)
            assert not (destino / "fact.csv").exists()
            ok("archivo con hash incorrecto rechazado y no guardado en destino")


def test_flujo_completo_seleccionar_consultar_descargar():
    """
    Flujo integrado:
      1. Listar versiones disponibles
      2. Seleccionar la más reciente
      3. Consultar sus tablas
      4. Descargar cada tabla y verificar integridad
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _crear_snapshot(base, "20260601", {"fact_adjudicacion": "id,monto\n1,100"})
        _crear_snapshot(base, "20261001", {
            "fact_adjudicacion":     "id,monto\n1,100\n2,200",
            "dim_entidad":           "id,nombre\nE1,MinSalud",
        })

        client = SnapshotClient(base_dir=base)

        # 1. Listar versiones
        versiones = client.list_snapshots()
        assert len(versiones) == 2
        ok(f"versiones disponibles: {versiones}")

        # 2. Seleccionar la más reciente
        mas_reciente = versiones[0]
        assert mas_reciente == "20261001"
        manifiesto = client.get_snapshot(mas_reciente)
        ok(f"snapshot seleccionado: {manifiesto.snapshot_id}")

        # 3. Consultar tablas
        tablas = [a.table_name for a in manifiesto.artifacts]
        assert "fact_adjudicacion" in tablas
        assert "dim_entidad" in tablas
        ok(f"tablas del snapshot: {tablas}")

        # 4. Descargar y verificar todas
        destino = base / "descargados"
        for artifact in manifiesto.artifacts:
            ruta = client.download_artifact(artifact, destino)
            assert ruta.exists()
            assert _sha256(ruta) == artifact.sha256
        ok("todas las tablas descargadas y verificadas correctamente")


# ── Ejecutar todas las pruebas ────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    pruebas = [
        ("A1. Listar snapshots — vacío",                  test_listar_snapshots_vacio),
        ("A2. Listar snapshots — orden descendente",      test_listar_snapshots_orden_descendente),
        ("A3. Ignorar dirs sin manifiesto",               test_listar_ignora_directorios_sin_manifiesto),
        ("B1. Consultar tablas del snapshot",             test_consultar_tablas_de_snapshot),
        ("B2. get_artifact por nombre",                   test_get_artifact_por_nombre),
        ("B3. Versión inexistente lanza error",           test_version_inexistente_lanza_error),
        ("C1. Descargar y verificar hash correcto",       test_descargar_y_verificar_hash_correcto),
        ("C2. Archivo corrupto rechazado y eliminado",    test_archivo_corrupto_rechazado_y_eliminado),
        ("C3. Flujo completo seleccionar-consultar-desc", test_flujo_completo_seleccionar_consultar_descargar),
    ]

    errores = 0
    for nombre, fn in pruebas:
        print(f"\n[{nombre}]")
        try:
            fn()
        except AssertionError as e:
            print(f"  ERROR: {e}")
            errores += 1
        except Exception as e:
            print(f"  ERROR inesperado: {type(e).__name__}: {e}")
            errores += 1

    print(f"\n{'='*55}")
    total = len(pruebas)
    print(f"Resultado: {total - errores}/{total} pruebas pasaron")
    if errores:
        sys.exit(1)
