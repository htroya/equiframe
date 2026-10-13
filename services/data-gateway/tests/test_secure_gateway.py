"""Authenticate, authorize, bound input and protect internal diagnostics."""

import asyncio
import hashlib
import importlib.util
import secrets
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

source = Path(__file__).resolve().parents[1] / "main.py"
spec = importlib.util.spec_from_file_location("equiframe_private_gateway", source)
gateway = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gateway
spec.loader.exec_module(gateway)


@pytest.fixture
def api(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "table.csv").write_text("id,value\n1,10\n")
    operator, reader = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    app = gateway.create_app(
        base_dir=tmp_path / "state",
        input_dir=inputs,
        token_sha256=hashlib.sha256(operator.encode()).hexdigest(),
        read_token_sha256=hashlib.sha256(reader.encode()).hexdigest(),
    )
    with TestClient(app, base_url="https://localhost") as client:
        yield (
            client,
            {"Authorization": "Bearer " + operator},
            {"Authorization": "Bearer " + reader},
        )


def test_health_hides_paths(api):
    client, _, _ = api
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"


def test_unauthenticated_calls_rejected(api):
    client, _, _ = api
    assert client.get("/jobs").status_code == 401
    assert (
        client.get(
            "/jobs", headers={"Authorization": "Bearer " + "invalid" * 10}
        ).status_code
        == 401
    )


def test_anonymous_requests_cannot_exhaust_operator_or_health_budget(api):
    client, operator, reader = api
    responses = [client.get("/jobs").status_code for _ in range(120)]
    assert set(responses) <= {401, 429}
    assert 429 in responses
    assert client.get("/jobs", headers=operator).status_code == 200
    assert client.get("/jobs", headers=reader).status_code == 200
    assert client.get("/health").status_code == 200


def test_health_never_receives_bodies_or_occupies_business_slots():
    async def exercise():
        async def application(scope, receive, send):
            raise AssertionError(
                "Health must be handled without the business application"
            )

        boundary = gateway.SecureBoundary(application)
        for _ in range(4):
            assert boundary._slots.acquire(blocking=False)

        async def receive():
            raise AssertionError("Health must not await a body")

        for method, expected in (("GET", 200), ("HEAD", 200), ("POST", 405)):
            messages = []

            async def send(message, captured=messages):
                captured.append(message)

            await boundary(
                {
                    "type": "http",
                    "method": method,
                    "path": "/health",
                    "scheme": "https",
                    "headers": [],
                },
                receive,
                send,
            )
            assert messages[0]["status"] == expected
        for _ in range(4):
            boundary._slots.release()

    asyncio.run(exercise())


def test_incomplete_authenticated_body_times_out_and_releases_slot(monkeypatch):
    monkeypatch.setattr(gateway, "MAX_BODY_IDLE_SECONDS", 0.02)
    monkeypatch.setattr(gateway, "MAX_BODY_SECONDS", 0.05)

    async def exercise():
        token = b"test-opaque-credential-with-at-least-32-bytes"
        app = type(
            "Application",
            (),
            {
                "state": type(
                    "State",
                    (),
                    {
                        "settings": {
                            "operator_digest": hashlib.sha256(token).hexdigest(),
                            "reader_digest": "0" * 64,
                        }
                    },
                )()
            },
        )()

        async def application(scope, receive, send):
            raise AssertionError("An incomplete request must not reach the application")

        boundary = gateway.SecureBoundary(application)
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/jobs",
            "scheme": "https",
            "headers": [(b"authorization", b"Bearer " + token)],
            "app": app,
        }

        async def receive():
            await asyncio.Future()

        async def request():
            messages = []

            async def send(message):
                messages.append(message)

            await boundary(scope, receive, send)
            assert messages[0]["status"] == 408

        await asyncio.gather(*(request() for _ in range(4)))
        for _ in range(4):
            assert boundary._slots.acquire(blocking=False)
        for _ in range(4):
            boundary._slots.release()

    asyncio.run(exercise())


def test_reader_can_read_but_cannot_submit(api):
    client, _, reader = api
    assert client.get("/jobs", headers=reader).status_code == 200
    assert (
        client.post(
            "/jobs",
            headers=reader,
            json={"operation": "load", "snapshot_id": "v1", "idempotency_key": "key"},
        ).status_code
        == 403
    )


def test_operator_quota_does_not_exhaust_reader_or_health(api):
    client, operator, reader = api
    assert all(
        client.get("/jobs", headers=operator).status_code == 200 for _ in range(120)
    )
    assert client.get("/jobs", headers=operator).status_code == 429
    assert client.get("/jobs", headers=reader).status_code == 200
    assert client.get("/health").status_code == 200


def test_trickled_body_cannot_extend_total_deadline(monkeypatch):
    monkeypatch.setattr(gateway, "MAX_BODY_IDLE_SECONDS", 0.08)
    monkeypatch.setattr(gateway, "MAX_BODY_SECONDS", 0.05)

    async def exercise():
        token = b"test-opaque-credential-with-at-least-32-bytes"
        app = type(
            "Application",
            (),
            {
                "state": type(
                    "State",
                    (),
                    {
                        "settings": {
                            "operator_digest": hashlib.sha256(token).hexdigest(),
                            "reader_digest": "0" * 64,
                        }
                    },
                )()
            },
        )()

        async def application(scope, receive, send):
            raise AssertionError(
                "Unfinished trickled input must not reach the application"
            )

        boundary = gateway.SecureBoundary(application)
        blocks = []
        messages = []

        async def receive():
            await asyncio.sleep(0.01)
            blocks.append(1)
            return {"type": "http.request", "body": b" ", "more_body": True}

        async def send(message):
            messages.append(message)

        await asyncio.wait_for(
            boundary(
                {
                    "type": "http",
                    "method": "POST",
                    "path": "/jobs",
                    "scheme": "https",
                    "headers": [(b"authorization", b"Bearer " + token)],
                    "app": app,
                },
                receive,
                send,
            ),
            timeout=1,
        )
        assert messages[0]["status"] == 408
        assert blocks
        for _ in range(4):
            assert boundary._slots.acquire(blocking=False)
        for _ in range(4):
            boundary._slots.release()

    asyncio.run(exercise())


def test_plain_http_rejected(api):
    client, operator, _ = api
    assert client.get("http://localhost/jobs", headers=operator).status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"operation": "shell", "snapshot_id": "v1", "idempotency_key": "key"},
        {"operation": "load", "snapshot_id": "../secret", "idempotency_key": "key"},
        {"operation": "load", "snapshot_id": 42, "idempotency_key": "key"},
        {
            "operation": "load",
            "snapshot_id": "v1",
            "idempotency_key": "key",
            "admin": True,
        },
    ],
)
def test_strict_input_and_generic_errors(api, body):
    client, operator, _ = api
    response = client.post("/jobs", headers=operator, json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": "Entrada inválida."}


def test_real_job_flow(api):
    client, operator, reader = api
    body = {
        "operation": "load",
        "snapshot_id": "v1",
        "idempotency_key": "private-client-key",
    }
    first = client.post("/jobs", headers=operator, json=body)
    assert first.status_code == 201
    job = first.json()
    assert "idempotency_key" not in job
    assert (
        client.post("/jobs", headers=operator, json=body).json()["job_id"]
        == job["job_id"]
    )
    loaded = client.post(
        "/jobs/" + job["job_id"] + "/run",
        headers=operator,
        json={"archivos": {"table": "table.csv"}},
    )
    assert loaded.status_code == 200
    assert loaded.json()["state"] == "completed"
    assert (
        client.get("/jobs/" + job["job_id"], headers=reader).json()["state"]
        == "completed"
    )


def test_reader_never_receives_a_legacy_error_secret(api, tmp_path):
    client, operator, reader = api
    response = client.post(
        "/jobs",
        headers=operator,
        json={"operation": "load", "snapshot_id": "legacy", "idempotency_key": "key"},
    )
    job_id = response.json()["job_id"]
    manager = gateway.JobManager(tmp_path / "state")
    job = manager.get_job(job_id)
    job.state = "failed"
    job.error = "secret=legacy-private-value; /private/customer.csv"
    manager._save_job(job)
    result = client.get("/jobs/" + job_id, headers=reader)
    assert result.status_code == 200
    assert result.json()["error"] == "LOAD_FAILED"
    assert "legacy-private-value" not in result.text
    assert "customer.csv" not in result.text


@pytest.mark.parametrize(
    "name", ["../confidential.csv", "/etc/passwd", "C:/private.key"]
)
def test_server_paths_are_not_read(api, name):
    client, operator, _ = api
    job = client.post(
        "/jobs",
        headers=operator,
        json={"operation": "load", "snapshot_id": "v1", "idempotency_key": "key"},
    ).json()
    response = client.post(
        "/jobs/" + job["job_id"] + "/run",
        headers=operator,
        json={"archivos": {"table": name}},
    )
    assert response.status_code == 400
    assert name not in response.text
    assert (
        client.get("/jobs/" + job["job_id"], headers=operator).json()["state"]
        == "failed"
    )


def test_oversized_and_duplicate_json(api):
    client, operator, _ = api
    headers = {**operator, "Content-Type": "application/json"}
    assert (
        client.post(
            "/jobs", headers=headers, content=b"x" * (gateway.MAX_BODY + 1)
        ).status_code
        == 413
    )
    assert (
        client.post(
            "/jobs",
            headers=headers,
            content=b'{"operation":"load","operation":"shell"}',
        ).status_code
        == 400
    )


def test_unknown_job_hides_paths(api):
    client, operator, _ = api
    response = client.get("/jobs/unknown", headers=operator)
    assert response.status_code == 404
    assert response.json() == {"detail": "Recurso no encontrado."}


def test_missing_config_fails_closed(monkeypatch):
    for key in ("DATA_DIR", "INPUT_DIR", "TOKEN_SHA256", "READ_TOKEN_SHA256"):
        monkeypatch.delenv("EQUIFRAME_GATEWAY_" + key, raising=False)
    with pytest.raises(RuntimeError), TestClient(gateway.create_app()):
        pass
