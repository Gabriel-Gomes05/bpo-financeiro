"""Aba Tutorial: treinamento do FLIC de acordo com o perfil do usuário logado."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.routers.lancamentos import clientes_do_usuario
from app.auth import get_usuario_atual
from app.database import get_db
from app.jinja import templates
from app.models import Usuario
from app.tutorial import treinamento_do_perfil

router = APIRouter()


@router.get("/tutorial", response_class=HTMLResponse)
async def pagina_tutorial(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    return templates.TemplateResponse("tutorial.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes_do_usuario(db, usuario),
        **treinamento_do_perfil(usuario.perfil),
    })
