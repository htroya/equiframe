"""Authenticated private gateway. Importing this module creates no data or credentials."""

import hashlib
import json
import logging
import os
import secrets
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from equiframe_data.job_manager import (
    JobManager,
    SnapshotConflictError,
    WriterBusyError,
)
from equiframe_data.safe_io import (
    _constant,
    _members,
    digest,
    identifier,
    safe_error_frames,
)
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("equiframe.gateway")
MAX_BODY = 64 * 1024


class SubmitRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    operation: Literal["load"]
    snapshot_id: Annotated[
        str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    ]
    idempotency_key: Annotated[str, Field(min_length=1, max_length=256)]


class RunRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    archivos: Annotated[dict[str, str], Field(min_length=1, max_length=256)]


class SecureBoundary:
    def __init__(self, app):
        self.app = app
        self._requests = deque()
        self._rate_lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(4)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-content-type-options", b"nosniff"),
                    (b"cache-control", b"no-store"),
                    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
                    (b"referrer-policy", b"no-referrer"),
                ]
                if scope.get("scheme") == "https":
                    message["headers"].append((b"strict-transport-security", b"max-age=31536000"))
            await send(message)

        async def reject(status, message):
            await JSONResponse({"detail": message}, status_code=status)(scope, receive, secure_send)

        now = time.monotonic()
        with self._rate_lock:
            while self._requests and self._requests[0] < now - 60:
                self._requests.popleft()
            limited = len(self._requests) >= 120
            if not limited:
                self._requests.append(now)
        if limited:
            await reject(429, "Límite de solicitudes alcanzado.")
            return
        if scope.get("path") != "/health":
            if scope.get("scheme") != "https":
                await reject(400, "Se requiere HTTPS.")
                return
            headers = scope.get("headers", [])
            authorization = [v for k, v in headers if k.lower() == b"authorization"]
            if len(authorization) != 1 or len(authorization[0]) > 512:
                await reject(401, "Autenticación requerida.")
                return
            header = authorization[0]
            if not header.startswith(b"Bearer ") or not 32 <= len(header[7:]) <= 256:
                await reject(401, "Credencial inválida.")
                return
            candidate = hashlib.sha256(header[7:]).hexdigest()
            settings = scope["app"].state.settings
            operator = secrets.compare_digest(candidate, settings["operator_digest"])
            reader = secrets.compare_digest(candidate, settings["reader_digest"])
            if not (operator or reader):
                await reject(401, "Credencial inválida.")
                return
            if scope["method"] not in ("GET", "HEAD") and not operator:
                await reject(403, "Permiso insuficiente.")
                return
        if not self._slots.acquire(blocking=False):
            await reject(503, "Servicio ocupado.")
            return
        try:
            headers = dict(scope.get("headers", []))
            length = headers.get(b"content-length", b"0")
            if not length.isdigit() or int(length) > MAX_BODY:
                await reject(413, "Solicitud demasiado grande.")
                return
            payload = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                block = message.get("body", b"")
                if len(payload) + len(block) > MAX_BODY:
                    await reject(413, "Solicitud demasiado grande.")
                    return
                payload.extend(block)
                if not message.get("more_body", False):
                    break
            if payload:
                if (
                    headers.get(b"content-type", b"").lower().split(b";", 1)[0].strip()
                    != b"application/json"
                ):
                    await reject(415, "Se requiere JSON.")
                    return
                try:
                    json.loads(
                        payload.decode("utf-8"),
                        object_pairs_hook=_members,
                        parse_constant=_constant,
                    )
                except (ValueError, UnicodeError, RecursionError):
                    await reject(400, "Documento JSON inválido.")
                    return
            consumed = False

            async def bounded_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": bytes(payload), "more_body": False}
                return await receive()

            await self.app(scope, bounded_receive, secure_send)
        finally:
            self._slots.release()


def _public(job):
    result = job.to_dict()
    result.pop("idempotency_key")
    return result


def _perform(call):
    try:
        return call()
    except FileNotFoundError:
        raise HTTPException(404, "Recurso no encontrado.") from None
    except (SnapshotConflictError, WriterBusyError):
        raise HTTPException(409, "Conflicto; vuelva a consultar el estado.") from None
    except ValueError:
        raise HTTPException(400, "Entrada o estado inválido.") from None
    except Exception as exc:  # noqa: BLE001 -- HTTP boundary must redact unexpected failures.
        logger.error(
            "operation_failed kind=%s frames=%s", type(exc).__name__, safe_error_frames(exc)
        )
        raise HTTPException(503, "Ocurrió un error; intente más tarde.") from None


def create_app(*, base_dir=None, input_dir=None, token_sha256=None, read_token_sha256=None):
    @asynccontextmanager
    async def lifespan(application):
        configured_base = base_dir or os.environ.get("EQUIFRAME_GATEWAY_DATA_DIR")
        configured_input = input_dir or os.environ.get("EQUIFRAME_GATEWAY_INPUT_DIR")
        operator = token_sha256 or os.environ.get("EQUIFRAME_GATEWAY_TOKEN_SHA256")
        reader = read_token_sha256 or os.environ.get("EQUIFRAME_GATEWAY_READ_TOKEN_SHA256")
        if not configured_base or not configured_input or not operator:
            raise RuntimeError("Configure las carpetas y el resumen de credencial del gateway.")
        operator = digest(operator)
        reader = digest(reader) if reader else "0" * 64
        if reader == operator:
            raise RuntimeError("Las credenciales de lectura y operación deben ser distintas.")
        state_root = Path(configured_base).resolve()
        input_root = Path(configured_input).resolve()
        if state_root.is_relative_to(input_root) or input_root.is_relative_to(state_root):
            raise RuntimeError("Las carpetas de entrada y estado no deben solaparse.")
        application.state.settings = {"operator_digest": operator, "reader_digest": reader}
        application.state.manager = JobManager(configured_base, input_dir=configured_input)
        yield

    application = FastAPI(
        title="EquiFrame private data gateway",
        version="1.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.add_middleware(SecureBoundary)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request, _error):
        return JSONResponse({"detail": "Entrada inválida."}, status_code=422)

    def manager(request: Request):
        return request.app.state.manager

    @application.get("/health")
    def health():
        return {"status": "ok"}

    @application.post("/jobs", status_code=201)
    def submit(req: SubmitRequest, mgr: Annotated[JobManager, Depends(manager)]):
        return _perform(
            lambda: _public(mgr.submit_job(req.operation, req.snapshot_id, req.idempotency_key))
        )

    @application.get("/jobs")
    def list_jobs(mgr: Annotated[JobManager, Depends(manager)]):
        return _perform(lambda: [_public(j) for j in mgr.list_jobs()])

    @application.get("/jobs/{job_id}")
    def get_job(job_id: str, mgr: Annotated[JobManager, Depends(manager)]):
        return _perform(lambda: _public(mgr.get_job(identifier(job_id))))

    @application.post("/jobs/{job_id}/run")
    def run_job(job_id: str, req: RunRequest, mgr: Annotated[JobManager, Depends(manager)]):
        # Strings remain relative until confined by JobManager; no arbitrary server paths.
        return _perform(lambda: _public(mgr.run_job(identifier(job_id), req.archivos)))

    @application.delete("/jobs/{job_id}")
    def cancel_job(job_id: str, mgr: Annotated[JobManager, Depends(manager)]):
        return _perform(lambda: _public(mgr.cancel_job(identifier(job_id))))

    return application


app = create_app()
