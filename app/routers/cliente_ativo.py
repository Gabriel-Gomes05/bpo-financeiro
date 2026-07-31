from typing import Optional
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual, tem_acesso_geral
from app.database import get_db
from app.models import ClienteBPO, Usuario
from app.security import secure_cookie_for

router = APIRouter()


@router.post("/cliente/selecionar")
async def selecionar_cliente(
    request: Request,
    cliente_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    referer = request.headers.get("referer", "/")
    parsed = urlparse(referer)
    if parsed.netloc and parsed.netloc != request.url.netloc:
        dest = "/"
    else:
        dest = urlunparse(parsed._replace(scheme="", netloc="", query="", fragment="")) or "/"

    response = RedirectResponse(url=dest, status_code=303)
    cliente_id_int = int(cliente_id) if cliente_id and cliente_id.isdigit() else None
    autorizado = False
    if cliente_id_int:
        query = db.query(ClienteBPO.id).filter(
            ClienteBPO.id == cliente_id_int,
            ClienteBPO.ativo.is_(True),
            ClienteBPO.deleted_at.is_(None),
        )
        if not tem_acesso_geral(usuario):
            query = query.filter(ClienteBPO.funcionario_id == usuario.id)
        autorizado = query.first() is not None

    if autorizado:
        response.set_cookie(
            "cliente_ativo",
            str(cliente_id_int),
            max_age=60 * 60 * 24 * 30,
            samesite="strict",
            httponly=True,
            secure=secure_cookie_for(request),
            path="/",
        )
    else:
        response.delete_cookie("cliente_ativo", path="/")
    return response
