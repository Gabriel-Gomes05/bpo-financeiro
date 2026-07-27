"""Autenticação, sessão JWT e revogação compartilhada."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jwt.exceptions import PyJWTError
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    SECRET_KEY,
)
from app.database import get_db
from app.models import PerfilUsuario, Usuario
from app.redis_client import redis_async, redis_sync

logger = logging.getLogger(__name__)


def normalizar_email(email: str) -> str:
    return email.casefold().strip()


def validar_senha_nova(senha: str) -> bool:
    tamanho = len(senha.encode("utf-8"))
    return 12 <= tamanho <= 72


def hash_senha(senha: str) -> str:
    if not validar_senha_nova(senha):
        raise ValueError("A senha deve ter entre 12 e 72 bytes.")
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            senha_plana.encode("utf-8"),
            senha_hash.encode("ascii"),
        )
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = bcrypt.hashpw(
    b"senha-inexistente-flic",
    bcrypt.gensalt(rounds=12),
).decode("ascii")


def verificar_senha_constante(
    senha_plana: str,
    senha_hash: str | None,
) -> bool:
    """Executa bcrypt mesmo quando o usuário não existe, reduzindo enumeração temporal."""
    return verificar_senha(senha_plana, senha_hash or _DUMMY_HASH)


def criar_token(data: dict, *, auth_version: int = 0) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        **data,
        "jti": uuid.uuid4().hex,
        "iat": agora,
        "nbf": agora,
        "exp": agora + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "typ": "access",
        "ver": auth_version,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "jti"]},
        )
        if payload.get("typ") != "access":
            return None
        return payload
    except PyJWTError:
        return None


def get_token_da_requisicao(request: Request) -> Optional[str]:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    return request.cookies.get("access_token")


def _revocation_key(jti: str) -> str:
    return f"auth:revoked:{jti}"


def token_revogado(jti: str) -> bool:
    try:
        return bool(redis_sync().exists(_revocation_key(jti)))
    except RedisError as exc:
        logger.error("redis_revocation_check_failed", exc_info=exc)
        raise HTTPException(status_code=503, detail="Serviço de autenticação indisponível.") from exc


async def token_revogado_async(jti: str) -> bool:
    try:
        return bool(await redis_async().exists(_revocation_key(jti)))
    except RedisError:
        logger.exception("redis_revocation_check_failed")
        return True


async def revogar_token(payload: dict) -> None:
    jti = str(payload.get("jti") or "")
    exp = int(payload.get("exp") or 0)
    ttl = max(exp - int(datetime.now(timezone.utc).timestamp()), 1)
    if jti:
        await redis_async().setex(_revocation_key(jti), ttl, "1")


def get_usuario_atual(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    token = get_token_da_requisicao(request)
    payload = decodificar_token(token) if token else None
    if not payload or token_revogado(str(payload.get("jti") or "")):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    try:
        usuario_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        ) from None

    usuario = db.query(Usuario).filter(
        Usuario.id == usuario_id,
        Usuario.ativo.is_(True),
        Usuario.deleted_at.is_(None),
    ).first()
    if not usuario or int(payload.get("ver", -1)) != usuario.auth_version:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    request.state.usuario_id = usuario.id
    db.info["actor_id"] = usuario.id
    db.info["request_id"] = getattr(request.state, "request_id", None)
    return usuario


def requer_coordenador(usuario: Usuario = Depends(get_usuario_atual)) -> Usuario:
    if usuario.perfil != PerfilUsuario.coordenador:
        raise HTTPException(status_code=403, detail="Acesso não permitido para este perfil.")
    return usuario


def tem_acesso_geral(usuario: Usuario) -> bool:
    return usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor)


class AuthMiddleware:
    """Bloqueia rotas privadas antes do parsing de formulários e uploads."""

    ROTAS_PUBLICAS = {"/login", "/favicon.ico", "/health", "/ready", "/version"}
    PREFIXOS_PUBLICOS = ("/static",)

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in self.ROTAS_PUBLICAS or any(path.startswith(p) for p in self.PREFIXOS_PUBLICOS):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        token = None
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        if not token:
            cookie = SimpleCookie()
            cookie.load(headers.get(b"cookie", b"").decode("latin-1"))
            morsel = cookie.get("access_token")
            token = morsel.value if morsel else None

        payload = decodificar_token(token) if token else None
        if not payload or await token_revogado_async(str(payload.get("jti") or "")):
            response = RedirectResponse(url="/login", status_code=303)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
