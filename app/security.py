from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from app.config import ALLOWED_ORIGINS, HTTPS_ONLY

__all__ = ["ALLOWED_ORIGINS", "HTTPS_ONLY", "SecurityHeadersMiddleware"]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adiciona cabeçalhos de segurança HTTP a todas as respostas.

    CSP permite apenas os CDNs usados (Tailwind, HTMX). Ajuste se adicionar
    outros recursos externos.
    """

    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline'; "   # Tailwind injeta <style> inline
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "frame-ancestors 'none';"              # equivale a X-Frame-Options: DENY
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        """Valida a origem de mutações e aplica headers defensivos à resposta."""
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not _origem_permitida(request):
                return PlainTextResponse("Origem da requisicao nao permitida.", status_code=403)

        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), payment=()"
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


def _origem_permitida(request: Request) -> bool:
    """Compara Origin/Referer com a lista explícita de origens autorizadas."""
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")

    if origin:
        return _normalizar_origem(origin) in {_normalizar_origem(o) for o in ALLOWED_ORIGINS}

    if referer:
        return _normalizar_origem(referer) in {_normalizar_origem(o) for o in ALLOWED_ORIGINS}

    return True


def _normalizar_origem(valor: str) -> str:
    """Reduz uma URL a esquema, hostname e porta para comparação segura."""
    parsed = urlparse(valor)
    scheme = parsed.scheme
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{scheme}://{hostname}{port}"
