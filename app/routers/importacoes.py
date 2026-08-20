from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.database import get_db
from app.jinja import templates
from app.models import Usuario
from app.routers.conciliacao import clientes_do_usuario

router = APIRouter()


@router.get("/importacoes", response_class=HTMLResponse)
async def pagina_importacoes(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    return templates.TemplateResponse("importacoes.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
    })
