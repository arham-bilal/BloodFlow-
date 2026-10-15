from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from config import settings
from main import app
from security import limiter


def test_limiter_uses_configured_storage_uri():
    assert limiter._storage_uri == settings.RATE_LIMIT_STORAGE_URI


def test_proxy_middleware_uses_forwarded_ip_from_trusted_proxy():
    probe = FastAPI()
    probe.add_middleware(ProxyHeadersMiddleware, trusted_hosts="testclient")

    @probe.get("/")
    def get_client_ip(request: Request):
        return {"ip": get_remote_address(request)}

    with TestClient(probe) as client:
        response = client.get("/", headers={"X-Forwarded-For": "198.51.100.23"})

    assert response.json()["ip"] == "198.51.100.23"


def test_untrusted_client_cannot_spoof_forwarded_ip():
    probe = FastAPI()
    probe.add_middleware(ProxyHeadersMiddleware, trusted_hosts="192.0.2.10")

    @probe.get("/")
    def get_client_ip(request: Request):
        return {"ip": get_remote_address(request)}

    with TestClient(probe) as client:
        response = client.get("/", headers={"X-Forwarded-For": "198.51.100.23"})

    assert response.json()["ip"] == "testclient"


def test_main_app_trusts_only_configured_proxy_hosts():
    assert any(
        middleware.cls is ProxyHeadersMiddleware
        and middleware.kwargs["trusted_hosts"] == settings.FORWARDED_ALLOW_IPS
        for middleware in app.user_middleware
    )


def test_redis_storage_uri_is_supported():
    redis_limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="redis://localhost:6379/0",
    )

    assert type(redis_limiter._storage).__name__ == "RedisStorage"
