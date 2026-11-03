"""Página de consulta dos códigos de erro (a "bíblia" dos erros)."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.auth import get_usuario_atual
from app.errors import AREAS, CATALOGO
from app.jinja import templates
from app.models import Usuario

router = APIRouter()


def erros_por_area() -> list[tuple[str, str, list]]:
    grupos = []
    for sigla, nome in AREAS.items():
        itens = [d for codigo, d in sorted(CATALOGO.items()) if codigo.split("-")[1] == sigla]
        if itens:
            grupos.append((sigla, nome, itens))
    return grupos


@router.get("/ajuda/erros", response_class=HTMLResponse)
async def codigos_de_erro(request: Request, usuario: Usuario = Depends(get_usuario_atual)):
    return templates.TemplateResponse("ajuda_erros.html", {
        "request": request,
        "usuario": usuario,
        "painel_geral": True,
        "grupos": erros_por_area(),
        "total": len(CATALOGO),
    })
