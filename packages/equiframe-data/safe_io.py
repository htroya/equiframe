"""Validate identifiers and confine untrusted paths before opening files."""

import json
import os
import re
import stat
import tempfile
from pathlib import Path

MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 16 * 1024**3
MAX_ARTIFACTS = 256


def safe_error_frames(error):
    """Keep stack locations without exception text, source lines or local values."""
    frames, current = [], error.__traceback__
    while current is not None and len(frames) < 32:
        name = re.sub(r"[^A-Za-z0-9_]", "_", current.tb_frame.f_code.co_name)[:96]
        frames.append(f"{name}:{current.tb_lineno}")
        current = current.tb_next
    return tuple(frames)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise ValueError("Identificador inválido.")
    return value


def digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("SHA-256 inválido.")
    return value


def relative_path(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 1024:
        raise ValueError("Ruta relativa inválida.")
    parts = value.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10))
    if any(
        not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,254}", p)
        or p.endswith(".")
        or p.split(".")[0].upper() in reserved
        for p in parts
    ):
        raise ValueError("Ruta relativa inválida.")
    return Path(*parts)


def unsigned_integer(value, *, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Entero fuera del rango permitido.")
    return value


def confined(root, relative):
    root = Path(root).resolve(strict=True)
    path = root / relative_path(relative)
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("No se permiten enlaces ni puntos de redirección.")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Ruta fuera de la carpeta autorizada.")
    return path


def open_regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("Se requiere un archivo regular sin enlaces.")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("El archivo cambió durante la apertura.")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def _members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON con miembros duplicados.")
        result[key] = value
    return result


def _constant(_value):
    raise ValueError("JSON con número no finito.")


def read_json(path, *, maximum=MAX_MANIFEST_BYTES):
    with open_regular(path) as stream:
        payload = stream.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError("Documento demasiado grande.")
    try:
        return json.loads(
            payload.decode("utf-8-sig"), object_pairs_hook=_members, parse_constant=_constant
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Documento JSON inválido.") from exc


def atomic_json(path, document):
    payload = json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ValueError("Documento demasiado grande.")
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValueError("No se permiten enlaces en el destino.")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
