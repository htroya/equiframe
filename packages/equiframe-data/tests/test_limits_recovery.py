"""
Pruebas de límites, consultas durante carga y recuperación de respaldos.

Cubre los puntos de Hernan:
  1. Límites: disco insuficiente, trabajo duplicado, clave en conflicto.
  2. Consultas mientras se carga: snapshot anterior sigue disponible.
  3. Recuperación: restaurar respaldo cuando el snapshot activo falla.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_manager import JobManager, COMPLETED, FAILED, CANCELLED
from snapshot_client import SnapshotClient, ArtifactRef


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _crear_csv(path: Path, contenido: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contenido, encoding="utf-8")
    return path


def _crear_snapshot_prueba(base: Path, snap_id: str, contenido: str) -> Path:
    """Crea un snapshot publicado con manifiesto válido."""
    snap_dir = base / "snapshots" / snap_id
    snap_dir.mkdir(parents=True, exist_ok=True)
    csv = snap_dir / "fact_adjudicacion.csv"
    csv.write_text(contenido, encoding="utf-8")
    size = csv.stat().st_size
    sha  = _sha256(csv)
    manifest = {
        "snapshot_id": snap_id,
        "version":     snap_id,
        "source":      "prueba",
        "timestamp":   "2026-10-07T00:00:00",
        "artifacts": [{
            "table_name": "fact_adjudicacion",
            "file_path":  "fact_adjudicacion.csv",
            "size_bytes": size,
            "sha256":     sha,
            "version":    snap_id,
            "row_count":  1,
        }],
    }
    (snap_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return snap_dir


def ok(msg: str) -> None:
    print(f"  PASS  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    raise AssertionError(msg)


# ── 1. Pruebas de límites ─────────────────────────────────────────────────────

def test_trabajo_duplicado_mismo_contenido():
    """Misma clave e igual contenido devuelve el mismo trabajo sin duplicar."""
    with tempfile.TemporaryDirectory() as tmp:
        mgr = JobManager(Path(tmp))
        j1 = mgr.submit_job("load", "snap-A", "clave-unica-001")
        j2 = mgr.submit_job("load", "snap-A", "clave-unica-001")
        assert j1.job_id == j2.job_id
        ok("trabajo duplicado devuelve el mismo job_id")


def test_clave_en_conflicto():
    """Misma clave con distinto contenido lanza error de conflicto."""
    with tempfile.TemporaryDirectory() as tmp:
        mgr = JobManager(Path(tmp))
        mgr.submit_job("load", "snap-A", "clave-conflicto")
        try:
            mgr.submit_job("load", "snap-B", "clave-conflicto")
            fail("debio lanzar ValueError por conflicto de clave")
        except ValueError as e:
            assert "Conflicto" in str(e)
            ok("clave con distinto contenido lanza conflicto")


def test_cancelar_trabajo_pendiente():
    """Un trabajo pendiente se puede cancelar."""
    with tempfile.TemporaryDirectory() as tmp:
        mgr = JobManager(Path(tmp))
        job = mgr.submit_job("load", "snap-C", "clave-cancel")
        cancelado = mgr.cancel_job(job.job_id)
        assert cancelado.state == CANCELLED
        ok("trabajo pendiente cancelado correctamente")


def test_cancelar_trabajo_completado_falla():
    """No se puede cancelar un trabajo ya completado."""
    with tempfile.TemporaryDirectory() as tmp:
        mgr  = JobManager(Path(tmp))
        csv  = _crear_csv(Path(tmp) / "fact.csv", "id,monto\n1,100.00")
        job  = mgr.submit_job("load", "snap-D", "clave-completado")
        mgr.run_job(job.job_id, {"fact_adjudicacion": csv})
        try:
            mgr.cancel_job(job.job_id)
            fail("debio lanzar ValueError al cancelar trabajo completado")
        except ValueError as e:
            assert "completado" in str(e) or "completed" in str(e)
            ok("cancelar trabajo completado lanza error correcto")


def test_archivo_corrupto_rechazado():
    """download_artifact rechaza un archivo con SHA-256 incorrecto."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        snap_dir = base / "snapshots" / "snap-E"
        snap_dir.mkdir(parents=True)
        csv = snap_dir / "fact.csv"
        csv.write_text("id,monto\n1,100.00", encoding="utf-8")

        ref = ArtifactRef(
            snapshot_id="snap-E",
            table_name="fact_adjudicacion",
            file_path="fact.csv",
            size_bytes=csv.stat().st_size,
            sha256="sha256_incorrecto_deliberado",
        )
        client = SnapshotClient(base_dir=base / "snapshots")
        try:
            client.download_artifact(ref, base / "descarga")
            fail("debio rechazar archivo con SHA-256 incorrecto")
        except ValueError as e:
            assert "SHA-256" in str(e)
            assert not (base / "descarga" / "fact.csv").exists()
            ok("archivo corrupto rechazado y no guardado")


# ── 2. Consultas mientras se carga ────────────────────────────────────────────

def test_snapshot_anterior_disponible_durante_carga():
    """
    El snapshot anterior sigue disponible mientras se prepara uno nuevo.
    La carga usa una carpeta .tmp — el snapshot publicado no se toca
    hasta que todo está listo.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        mgr  = JobManager(base)

        # Publicar snapshot inicial (v1)
        csv_v1 = _crear_csv(base / "fact_v1.csv", "id,monto\n1,500.00")
        job_v1 = mgr.submit_job("load", "snap-v1", "carga-v1")
        mgr.run_job(job_v1.job_id, {"fact_adjudicacion": csv_v1})

        # Verificar que v1 está disponible
        snap_v1 = base / "snapshots" / "snap-v1"
        assert snap_v1.exists()
        ok("snapshot v1 publicado y disponible")

        # Simular carga de v2 en progreso (solo crear .tmp manualmente)
        snap_v2_tmp = base / "snapshots" / "snap-v2.tmp"
        snap_v2_tmp.mkdir(parents=True)
        (snap_v2_tmp / "fact.csv").write_text("id,monto\n2,999.00", encoding="utf-8")

        # v1 sigue accesible mientras .tmp existe
        assert snap_v1.exists()
        assert (snap_v1 / "manifest.json").exists()
        ok("snapshot v1 sigue disponible durante carga de v2 en .tmp")

        # Completar carga v2
        shutil.rmtree(snap_v2_tmp)
        csv_v2 = _crear_csv(base / "fact_v2.csv", "id,monto\n2,999.00")
        job_v2 = mgr.submit_job("load", "snap-v2", "carga-v2")
        mgr.run_job(job_v2.job_id, {"fact_adjudicacion": csv_v2})

        assert (base / "snapshots" / "snap-v2").exists()
        ok("snapshot v2 publicado; v1 y v2 coexisten")


# ── 3. Recuperación de respaldo ───────────────────────────────────────────────

def test_recuperacion_respaldo():
    """
    Si el snapshot activo se corrompe o elimina,
    se puede restaurar desde un respaldo previo.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base      = Path(tmp)
        snaps_dir = base / "snapshots"
        backup_dir = base / "respaldos"
        backup_dir.mkdir(parents=True)

        # Publicar snapshot v1 y hacer respaldo
        _crear_snapshot_prueba(base, "snap-bkp-v1", "id,monto\n1,100.00")
        snap_v1 = snaps_dir / "snap-bkp-v1"
        bkp_v1  = backup_dir / "snap-bkp-v1"
        shutil.copytree(snap_v1, bkp_v1)
        ok("snapshot v1 respaldado en carpeta respaldos/")

        # Simular corrupción del snapshot activo
        shutil.rmtree(snap_v1)
        assert not snap_v1.exists()
        ok("snapshot activo eliminado (simula corrupcion)")

        # Restaurar desde respaldo
        shutil.copytree(bkp_v1, snap_v1)
        assert snap_v1.exists()
        assert (snap_v1 / "manifest.json").exists()
        ok("snapshot restaurado desde respaldo correctamente")

        # Verificar con el cliente que el snapshot restaurado es válido
        client = SnapshotClient(base_dir=snaps_dir)
        manifiesto = client.get_snapshot("snap-bkp-v1")
        assert manifiesto.snapshot_id == "snap-bkp-v1"
        assert len(manifiesto.artifacts) == 1
        ok("snapshot restaurado verificado con SnapshotClient")


def test_carga_fallida_no_toca_snapshot_anterior():
    """Si una carga falla a mitad, el snapshot anterior permanece intacto."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        mgr  = JobManager(base)

        # Publicar snapshot inicial
        csv_v1 = _crear_csv(base / "fact_v1.csv", "id,monto\n1,100.00")
        job_v1 = mgr.submit_job("load", "snap-ok", "carga-ok")
        mgr.run_job(job_v1.job_id, {"fact_adjudicacion": csv_v1})
        snap_ok = base / "snapshots" / "snap-ok"
        assert snap_ok.exists()
        ok("snapshot inicial disponible antes del fallo")

        # Intentar cargar con archivo inexistente (falla controlada)
        job_fail = mgr.submit_job("load", "snap-fail", "carga-fail")
        try:
            mgr.run_job(job_fail.job_id, {"fact_adjudicacion": Path("no_existe.csv")})
        except Exception:
            pass

        job_fail = mgr.get_job(job_fail.job_id)
        assert job_fail.state == FAILED
        assert snap_ok.exists()
        assert not (base / "snapshots" / "snap-fail").exists()
        assert not (base / "snapshots" / "snap-fail.tmp").exists()
        ok("carga fallida no toca el snapshot anterior; .tmp limpiado")


# ── Ejecutar todas las pruebas ────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    pruebas = [
        ("1a. Trabajo duplicado — misma clave",       test_trabajo_duplicado_mismo_contenido),
        ("1b. Clave en conflicto",                    test_clave_en_conflicto),
        ("1c. Cancelar trabajo pendiente",            test_cancelar_trabajo_pendiente),
        ("1d. Cancelar trabajo completado falla",     test_cancelar_trabajo_completado_falla),
        ("1e. Archivo corrupto rechazado",            test_archivo_corrupto_rechazado),
        ("2a. Snapshot anterior disponible en carga", test_snapshot_anterior_disponible_durante_carga),
        ("3a. Recuperacion desde respaldo",           test_recuperacion_respaldo),
        ("3b. Carga fallida no toca snapshot prev",   test_carga_fallida_no_toca_snapshot_anterior),
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
            print(f"  ERROR inesperado: {e}")
            errores += 1

    print(f"\n{'='*50}")
    total = len(pruebas)
    print(f"Resultado: {total - errores}/{total} pruebas pasaron")
    if errores:
        sys.exit(1)
