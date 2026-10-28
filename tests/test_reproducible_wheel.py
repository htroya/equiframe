"""Host metadata cannot change artifact identity or executable payload bytes."""

import hashlib
import importlib.util
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def test_cross_host_zip_metadata_has_one_hash_and_preserves_record(tmp_path):
    hook = Path(__file__).parents[1] / "tools/reproducible_wheel.py"
    spec = importlib.util.spec_from_file_location("reproducible_wheel", hook)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = {
        "package/a.py": b"print('exact')\n",
        "package/data.txt": b"a\r\nb\n",
        "package.dist-info/RECORD": b"package/a.py,sha256=example,15\n",
    }
    paths = []
    for creator in (0, 3):
        path = tmp_path / f"host-{creator}.whl"
        with ZipFile(path, "w") as archive:
            for name, data in files.items():
                info = ZipInfo(name, (2020, 2, 2, 0, 0, 0))
                info.create_system = creator
                info.external_attr = 0o100644 << 16
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, data)
        module.canonicalize_wheel(path)
        with ZipFile(path) as archive:
            assert {name: archive.read(name) for name in archive.namelist()} == files
            assert all(info.create_system == 3 for info in archive.infolist())
            assert all(info.external_attr == 0o100644 << 16 for info in archive.infolist())
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        module.canonicalize_wheel(path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
        paths.append(path)
    assert paths[0].read_bytes() == paths[1].read_bytes()
