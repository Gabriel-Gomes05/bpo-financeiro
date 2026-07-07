from typing import Optional
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.config import HTTPS_ONLY

router = APIRouter()


@router.post("/cliente/selecionar")
async def selecionar_cliente(
    request: Request,
    cliente_id: Optional[str] = Form(None),
):
    referer = request.headers.get("referer", "/")
    parsed = urlparse(referer)
    if parsed.netloc and parsed.netloc != request.url.netloc:
        dest = "/"
    else:
        dest = urlunparse(parsed._replace(scheme="", netloc="", query="", fragment="")) or "/"

    response = RedirectResponse(url=dest, status_code=303)
    if cliente_id and cliente_id.isdigit():
        response.set_cookie(
            "cliente_ativo",
            cliente_id,
            max_age=60 * 60 * 24 * 30,
            samesite="strict",
            httponly=True,
            secure=HTTPS_ONLY,
            path="/",
        )
    else:
        response.delete_cookie("cliente_ativo", path="/")
    return response
