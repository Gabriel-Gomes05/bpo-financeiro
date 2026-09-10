from types import SimpleNamespace
from uuid import uuid4

import fakeredis.aioredis
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.security as security
from app.auth import (
    criar_token,
    decodificar_token,
    get_token_da_requisicao,
    hash_senha,
    validar_senha_nova,
    verificar_senha,
)
from app.authorization import Permission, has_permission
from app.config import APP_URL
from app.main import app
from app.models import PerfilUsuario
from app.routers.rotinas import _render_li
from app.database import Base, get_db
from app.security import _origem_permitida, client_ip


def _request(
    *,
    path: str = "/",
    client: tuple[str, int] = ("127.0.0.1", 50000),
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers or [],
            "client": client,
            "server": ("testserver", 80),
        }
    )


def test_password_hash_and_policy():
    password = "abc123"
    password_hash = hash_senha(password)
    assert validar_senha_nova(password)
    assert not validar_senha_nova("curta")
    assert not validar_senha_nova("á" * 5)
    assert validar_senha_nova("á" * 6)
    assert validar_senha_nova("a" * 72)
    assert not validar_senha_nova("a" * 73)
    assert not validar_senha_nova("á" * 37)
    assert password not in password_hash
    assert verificar_senha(password, password_hash)
    assert not verificar_senha("OutraSenhaForte!2026", password_hash)


def test_jwt_has_lifecycle_claims_and_does_not_accept_url_token():
    token = criar_token({"sub": "42"}, auth_version=3)
    payload = decodificar_token(token)
    assert payload
    assert payload["sub"] == "42"
    assert payload["ver"] == 3
    assert {"jti", "iat", "nbf", "exp", "iss", "aud"} <= payload.keys()

    request = _request(path=f"/?access_token={token}")
    assert get_token_da_requisicao(request) is None


def test_bearer_header_takes_precedence_over_cookie():
    request = _request(
        headers=[
            (b"authorization", b"Bearer header-token"),
            (b"cookie", b"access_token=cookie-token"),
        ]
    )
    assert get_token_da_requisicao(request) == "header-token"


def test_permission_matrix_is_centralized():
    coordinator = SimpleNamespace(perfil=PerfilUsuario.coordenador)
    secretary = SimpleNamespace(perfil=PerfilUsuario.secretaria)
    assert all(has_permission(coordinator, permission) for permission in Permission)
    assert has_permission(secretary, Permission.LANCAMENTOS)
    assert not has_permission(secretary, Permission.CONCILIACAO)
    assert not has_permission(secretary, Permission.ADMIN_USUARIOS)


def test_proxy_headers_are_only_trusted_from_configured_network():
    untrusted = _request(
        client=("8.8.8.8", 1234),
        headers=[(b"x-forwarded-for", b"10.0.0.7")],
    )
    trusted = _request(
        client=("192.168.0.250", 1234),
        headers=[(b"x-forwarded-for", b"203.0.113.20")],
    )
    assert client_ip(untrusted) == "8.8.8.8"
    assert client_ip(trusted) == "203.0.113.20"


def test_origin_allowlist_is_exact():
    allowed = _request(headers=[(b"origin", APP_URL.encode())])
    reflected_subdomain = _request(
        headers=[(b"origin", f"{APP_URL}.attacker.invalid".encode())]
    )
    assert _origem_permitida(allowed)
    assert not _origem_permitida(reflected_subdomain)


def test_secure_cookie_is_disabled_only_for_explicit_private_host(monkeypatch):
    monkeypatch.setattr(security, "HTTPS_ONLY", True)
    monkeypatch.setattr(
        security,
        "_INSECURE_PRIVATE_NORMALIZED",
        frozenset({"http://192.168.0.102:8888"}),
    )
    private = _request(
        headers=[
            (b"host", b"192.168.0.102:8888"),
            (b"origin", b"http://192.168.0.102:8888"),
        ]
    )
    public = _request(
        headers=[
            (b"host", b"flic.docconcierge.com.br"),
            (b"origin", b"https://flic.docconcierge.com.br"),
        ]
    )
    spoofed = _request(
        headers=[
            (b"host", b"flic.docconcierge.com.br"),
            (b"origin", b"http://192.168.0.102:8888"),
        ]
    )

    assert not security.secure_cookie_for(private)
    assert security.secure_cookie_for(public)
    assert security.secure_cookie_for(spoofed)


def test_rotina_partial_escapes_user_controlled_html():
    task = SimpleNamespace(
        id=7,
        concluida=False,
        concluida_em=None,
        descricao='<img src=x onerror="alert(1)">',
        funcionario=SimpleNamespace(nome="<script>alert(2)</script>"),
        horario_previsto='"><svg onload=alert(3)>',
    )
    rendered = _render_li(task, pode_reverter=False)
    assert "<script>" not in rendered
    assert "<img" not in rendered
    assert "<svg" not in rendered
    assert "&lt;img" in rendered


@pytest.fixture
def isolated_http(monkeypatch):
    """Isola Redis e banco, preservando as regras reais de autenticação e rate limit."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for module in ("app.rate_limit", "app.main", "app.auth"):
        monkeypatch.setattr(f"{module}.redis_async", lambda: redis)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = test_db
    monkeypatch.setattr("app.routers.auth.LOGIN_RATE_LIMIT_ACCOUNT", 5)
    monkeypatch.setattr("app.routers.auth.LOGIN_RATE_LIMIT_IP", 20)
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        engine.dispose()


def test_public_endpoints_and_security_headers(isolated_http):
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert health.headers["x-frame-options"] == "DENY"
        assert health.headers["x-content-type-options"] == "nosniff"

        version = client.get("/version")
        assert version.status_code == 200
        assert {"app", "version", "environment"} <= version.json().keys()

        query_token = client.get("/?access_token=fake", follow_redirects=False)
        assert query_token.status_code == 303
        assert query_token.headers["location"] == "/login"


def test_login_rate_limit_is_per_account_and_message_is_generic(isolated_http):
    email = f"inexistente-{uuid4().hex}@example.invalid"
    with TestClient(app) as client:
        responses = [
            client.post(
                "/login",
                data={"email": email, "senha": "SenhaInvalida!2026"},
                headers={"Origin": APP_URL},
            )
            for _ in range(6)
        ]
        other_account = client.post(
            "/login",
            data={"email": "outra@example.invalid", "senha": "SenhaInvalida!2026"},
            headers={"Origin": APP_URL},
        )
    assert other_account.status_code == 400
    assert int(responses[-1].headers["Retry-After"]) > 0
    assert [response.status_code for response in responses] == [400, 400, 400, 400, 400, 429]
    assert email not in responses[-1].text
    assert "credenciais informadas" in responses[-1].text
