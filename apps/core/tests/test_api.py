from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from juno.api import create_app, token_matches
from juno.config import (
    Settings,
    api_token_is_configured,
    is_loopback_bind_host,
    is_loopback_client_host,
    resolve_env_file,
    validate_serve_settings,
)

AUTH = {"Authorization": "Bearer test-token"}


def _client(settings) -> TestClient:
    return TestClient(create_app(settings))


def test_token_helpers_reject_defaults():
    assert api_token_is_configured("test-token")
    assert not api_token_is_configured("")
    assert not api_token_is_configured("change-me")
    assert not api_token_is_configured("CHANGE-ME")
    assert not token_matches("change-me", "change-me")
    assert token_matches("test-token", "test-token")
    assert not token_matches("nope", "test-token")
    assert not token_matches("test-token", "test-token-extra")


def test_resolve_env_file_walks_parents(tmp_path):
    nested = tmp_path / "apps" / "core"
    nested.mkdir(parents=True)
    env = tmp_path / ".env"
    env.write_text("JUNO_API_TOKEN=parent-token\n", encoding="utf-8")
    assert resolve_env_file(start=nested) == env.resolve()
    local = nested / ".env"
    local.write_text("JUNO_API_TOKEN=local-token\n", encoding="utf-8")
    assert resolve_env_file(start=nested) == local.resolve()


def test_loopback_host_helpers():
    assert is_loopback_bind_host("127.0.0.1")
    assert is_loopback_bind_host("::1")
    assert is_loopback_bind_host("localhost")
    assert not is_loopback_bind_host("0.0.0.0")
    assert not is_loopback_bind_host("192.168.1.10")
    assert is_loopback_client_host("testclient")
    assert is_loopback_client_host("::ffff:127.0.0.1")
    assert not is_loopback_client_host("8.8.8.8")


def test_serve_settings_refuse_default_token_and_non_loopback(settings):
    validate_serve_settings(settings)
    with pytest.raises(ValueError, match="JUNO_API_TOKEN"):
        validate_serve_settings(
            Settings(juno_data_dir=settings.juno_data_dir, juno_api_token="change-me")
        )
    with pytest.raises(ValueError, match="JUNO_API_HOST"):
        validate_serve_settings(
            Settings(
                juno_data_dir=settings.juno_data_dir,
                juno_api_token="test-token",
                juno_api_host="0.0.0.0",
            )
        )


def test_health_is_public(settings):
    client = _client(settings)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health", headers={"Authorization": "Bearer nope"}).json() == {
        "status": "ok"
    }


def test_openapi_docs_are_disabled(settings):
    client = _client(settings)
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


@pytest.mark.parametrize(
    "path,method",
    [("/status", "GET"), ("/search", "GET"), ("/ingest", "POST")],
)
def test_protected_routes_reject_bad_token(settings, path, method):
    client = _client(settings)
    kw: dict = {}
    if path == "/search":
        kw["params"] = {"q": "rust"}
    if path == "/ingest":
        kw["json"] = {"source_type": "api", "text": "hi"}

    missing = client.request(method, path, **kw)
    wrong = client.request(method, path, headers={"Authorization": "Bearer wrong"}, **kw)
    not_bearer = client.request(method, path, headers={"Authorization": "test-token"}, **kw)
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert not_bearer.status_code == 401
    assert missing.json()["detail"] == "Invalid or missing API token"


def test_default_example_token_never_authorizes(settings):
    app = create_app(
        Settings(
            juno_data_dir=settings.juno_data_dir,
            juno_inbox_dir=settings.juno_inbox_dir,
            juno_api_token="change-me",
            embedding_backend="stub",
        )
    )
    client = TestClient(app)
    resp = client.get("/status", headers={"Authorization": "Bearer change-me"})
    assert resp.status_code == 401


def test_status_ok_with_good_token(settings):
    resp = _client(settings).get("/status", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert "capture_paused" in body
    assert "modules" in body
    assert isinstance(body["modules"], list)


def test_ingest_without_pipeline_is_503_not_stub_success(settings):
    client = _client(settings)
    resp = client.post("/ingest", json={"source_type": "api", "text": "hi"}, headers=AUTH)
    assert resp.status_code == 503
    assert "pipeline" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_loopback_client_is_forbidden(settings):
    app = create_app(settings)
    transport = ASGITransport(app=app, client=("8.8.8.8", 12345))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        status = await client.get("/status", headers=AUTH)
    assert health.status_code == 403
    assert status.status_code == 403
    assert health.json()["detail"] == "Loopback only"
