"""
Pruebas de DWReader y DWWriter — acceso controlado al DW DuckDB.

  D1. DWReader lanza FileNotFoundError si el archivo no existe
  D2. DWWriter serializa: el segundo escritor recibe RuntimeError
  D3. DWWriter libera el lock aunque falle dentro del bloque
  D4. Tras el context manager, el lock queda liberado
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import duckdb
    _DUCKDB = True
except ImportError:
    _DUCKDB = False

from dw_access import DWReader, DWWriter


def ok(msg: str) -> None:
    print(f"  PASS  {msg}")


def skip(msg: str) -> None:
    print(f"  SKIP  {msg} (duckdb no instalado)")


# ── D1. Lectura con archivo inexistente ───────────────────────────────────────

def test_reader_archivo_inexistente():
    if not _DUCKDB:
        skip("DWReader lanza FileNotFoundError si DW no existe"); return
    with tempfile.TemporaryDirectory() as tmp:
        ruta_inexistente = Path(tmp) / "no_existe.duckdb"
        try:
            with DWReader(ruta_inexistente):
                pass
            raise AssertionError("debio lanzar FileNotFoundError")
        except FileNotFoundError as e:
            assert "no_existe.duckdb" in str(e)
            ok("DWReader lanza FileNotFoundError si el DW no existe")


# ── D2. Segundo escritor bloqueado ────────────────────────────────────────────

def test_writer_segundo_escritor_bloqueado():
    if not _DUCKDB:
        skip("Segundo escritor recibe RuntimeError"); return
    with tempfile.TemporaryDirectory() as tmp:
        dw_file  = Path(tmp) / "test.duckdb"
        jobs_dir = Path(tmp) / "jobs"

        # Primer escritor: adquiere lock manualmente para simular proceso concurrente
        lock = jobs_dir / "equiframe.lock.pid"
        jobs_dir.mkdir()
        lock.write_text("99999", encoding="utf-8")  # simula PID de otro proceso

        try:
            with DWWriter(dw_file, jobs_dir=jobs_dir):
                pass
            raise AssertionError("debio lanzar RuntimeError por lock ocupado")
        except RuntimeError as e:
            assert "99999" in str(e)
            ok("segundo escritor recibe RuntimeError cuando el lock está ocupado")
        finally:
            lock.unlink(missing_ok=True)


# ── D3. Lock se libera aunque falle dentro del bloque ─────────────────────────

def test_writer_lock_liberado_tras_excepcion():
    if not _DUCKDB:
        skip("Lock liberado tras excepcion interna"); return
    with tempfile.TemporaryDirectory() as tmp:
        dw_file  = Path(tmp) / "test.duckdb"
        jobs_dir = Path(tmp) / "jobs"
        lock     = jobs_dir / "equiframe.lock.pid"

        try:
            with DWWriter(dw_file, jobs_dir=jobs_dir):
                assert lock.exists(), "lock debe existir dentro del bloque"
                raise ValueError("error simulado dentro del writer")
        except ValueError:
            pass  # esperado

        assert not lock.exists(), "lock debe haberse liberado tras la excepcion"
        ok("lock liberado correctamente aunque ocurra una excepcion dentro del bloque")


# ── D4. Lock liberado al salir normalmente ────────────────────────────────────

def test_writer_lock_liberado_normalmente():
    if not _DUCKDB:
        skip("Lock liberado tras uso normal"); return
    with tempfile.TemporaryDirectory() as tmp:
        dw_file  = Path(tmp) / "test.duckdb"
        jobs_dir = Path(tmp) / "jobs"
        lock     = jobs_dir / "equiframe.lock.pid"

        with DWWriter(dw_file, jobs_dir=jobs_dir) as db:
            db.execute("CREATE TABLE prueba (id INTEGER, valor TEXT)")
            db.execute("INSERT INTO prueba VALUES (1, 'hola')")

        assert not lock.exists(), "lock debe haberse liberado al salir"
        ok("lock liberado correctamente tras uso normal del DWWriter")

        # Verificar que los datos se leen correctamente en modo lectura
        with DWReader(dw_file) as db:
            tablas = db.tables()
            assert "prueba" in tablas
            ok(f"DWReader puede leer la tabla recien creada: {tablas}")


# ── Ejecutar ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    pruebas = [
        ("D1. Reader — archivo inexistente",           test_reader_archivo_inexistente),
        ("D2. Writer — segundo escritor bloqueado",    test_writer_segundo_escritor_bloqueado),
        ("D3. Writer — lock liberado tras excepcion",  test_writer_lock_liberado_tras_excepcion),
        ("D4. Writer — lock liberado normalmente",     test_writer_lock_liberado_normalmente),
    ]

    errores = 0
    for nombre, fn in pruebas:
        print(f"\n[{nombre}]")
        try:
            fn()
        except AssertionError as e:
            print(f"  FAIL: {e}"); errores += 1
        except Exception as e:
            print(f"  ERROR inesperado: {type(e).__name__}: {e}"); errores += 1

    print(f"\n{'='*55}")
    total = len(pruebas)
    print(f"Resultado: {total - errores}/{total} pruebas pasaron")
    if errores:
        sys.exit(1)
