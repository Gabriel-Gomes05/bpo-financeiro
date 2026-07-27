"""Middlewares HTTP defensivos, proxy confiável e limites de requisição."""
from __future__ import annotations

import ipaddress
import logging
import uuid
from urllib.parse import urlparse

from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from app.config import (
    ALLOWED_ORIGINS,
    GLOBAL_RATE_LIMIT_REQUESTS,
    GLOBAL_RATE_LIMIT_WINDOW_SECONDS,
    HTTPS_ONLY,
    MAX_REQUEST_BODY_BYTES,
    TRUSTED_PROXY_CIDRS,
)
from app.rate_limit import consume

logger = logging.getLogger(__name__)
_TRUSTED_NETWORKS = tuple(ipaddress.ip_network(item, strict=False) for item in TRUSTED_PROXY_CIDRS)
_ALLOWED_NORMALIZED = frozenset()


def _normalizar_origem(valor: str) -> str:
    try:
        parsed = urlparse(valor)
        port = f":{parsed.port}" if parsed.port else ""
    except (TypeError, ValueError):
        return ""
    return f"{parsed.scheme.lower()}://{(parsed.hostname or '').lower()}{port}"


_ALLOWED_NORMALIZED = frozenset(_normalizar_origem(item) for item in ALLOWED_ORIGINS)


def _is_trusted_proxy(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in _TRUSTED_NETWORKS)


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else ""
    if peer and _is_trusted_proxy(peer):
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            candidate = forwarded.split(",", 1)[0].strip()
            try:
                return str(ipaddress.ip_address(candidate))
            except ValueError:
                pass
    try:
        return str(ipaddress.ip_address(peer))
    except ValueError:
        return "unknown"


def _origem_permitida(request: Request) -> bool:
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    authorization = request.headers.get("authorization", "")
    if origin:
        return _normalizar_origem(origin) in _ALLOWED_NORMALIZED
    if referer:
        return _normalizar_origem(referer) in _ALLOWED_NORMALIZED
    return authorization.lower().startswith("bearer ")


class MaxBodySizeMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        raw_length = headers.get(b"content-length")
        if raw_length:
            try:
                if int(raw_length) > MAX_REQUEST_BODY_BYTES:
                    response = PlainTextResponse("Requisição muito grande.", status_code=413)
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = PlainTextResponse("Content-Length inválido.", status_code=400)
                await response(scope, receive, send)
                return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_REQUEST_BODY_BYTES:
                    raise ValueError("request_body_too_large")
            return message

        try:
            await self.app(scope, limited_receive, send)
        except ValueError as exc:
            if str(exc) != "request_body_too_large":
                raise
            response = PlainTextResponse("Requisição muito grande.", status_code=413)
            await response(scope, receive, send)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Aplica origem, rate limit global, request ID e headers defensivos."""

    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none';"
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", "")
        try:
            request_id = str(uuid.UUID(request_id))
        except (ValueError, TypeError):
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        ip = client_ip(request)

        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not _origem_permitida(request):
            return PlainTextResponse("Origem da requisição não permitida.", status_code=403)

        if request.url.path not in {"/health", "/ready"}:
            try:
                allowed, remaining, retry_after = await consume(
                    f"rate:global:{ip}",
                    GLOBAL_RATE_LIMIT_REQUESTS,
                    GLOBAL_RATE_LIMIT_WINDOW_SECONDS,
                )
            except RedisError:
                logger.exception("global_rate_limit_redis_failed", extra={"request_id": request_id})
                return PlainTextResponse("Serviço temporariamente indisponível.", status_code=503)
            if not allowed:
                return PlainTextResponse(
                    "Muitas requisições. Tente novamente mais tarde.",
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
        else:
            remaining = GLOBAL_RATE_LIMIT_REQUESTS

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), payment=(), usb=()"
        )
        response.headers["Content-Security-Policy"] = self.CSP
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        if HTTPS_ONLY:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response
