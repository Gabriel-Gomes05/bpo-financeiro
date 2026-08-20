import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual, tem_acesso_geral
from app.database import get_db
from app.jinja import templates
from app.models import PlanoConta, Usuario

router = APIRouter(prefix="/admin")


def _slugificar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or "procedimento"


@router.get("/procedimentos", response_class=HTMLResponse)
async def pagina_procedimentos(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not tem_acesso_geral(usuario):
        return RedirectResponse(url="/lancamentos", status_code=303)

    procedimentos = db.query(PlanoConta).filter(
        PlanoConta.tipo == "receita",
        PlanoConta.cliente_id.is_(None),
        PlanoConta.ativo == True,
    ).order_by(PlanoConta.nome).all()

    return templates.TemplateResponse("admin/procedimentos.html", {
        "request": request,
        "usuario": usuario,
        "procedimentos": procedimentos,
    })


@router.post("/procedimentos")
async def criar_procedimento(
    nome: str = Form(...),
    codigo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not tem_acesso_geral(usuario):
        return RedirectResponse(url="/lancamentos", status_code=303)

    nome = nome.strip()
    if not nome:
        return RedirectResponse(url="/admin/procedimentos?erro=nome_obrigatorio", status_code=303)

    procedimento = PlanoConta(
        tipo="receita",
        grupo="RECEITAS",
        nome=nome,
        codigo=(codigo or "").strip() or None,
        chave="",
        cliente_id=None,
    )
    db.add(procedimento)
    db.flush()
    base = _slugificar(nome)
    chave = f"pc_{base}"
    if db.query(PlanoConta).filter(PlanoConta.chave == chave, PlanoConta.cliente_id.is_(None)).first():
        chave = f"pc_{procedimento.id}"
    procedimento.chave = chave
    db.commit()
    return RedirectResponse(url="/admin/procedimentos?sucesso=1", status_code=303)


@router.post("/procedimentos/{procedimento_id}/editar")
async def editar_procedimento(
    procedimento_id: int,
    nome: str = Form(...),
    codigo: Optional[str] = Form(None),
    ativo: bool = Form(True),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not tem_acesso_geral(usuario):
        return RedirectResponse(url="/lancamentos", status_code=303)

    procedimento = db.query(PlanoConta).filter(
        PlanoConta.id == procedimento_id,
        PlanoConta.tipo == "receita",
        PlanoConta.cliente_id.is_(None),
    ).first()
    nome = nome.strip()
    if procedimento and nome:
        procedimento.nome = nome
        procedimento.codigo = (codigo or "").strip() or None
        procedimento.ativo = ativo
        db.commit()
    return RedirectResponse(url="/admin/procedimentos?sucesso=1", status_code=303)


@router.post("/procedimentos/{procedimento_id}/excluir")
async def excluir_procedimento(
    procedimento_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if not tem_acesso_geral(usuario):
        return RedirectResponse(url="/lancamentos", status_code=303)

    procedimento = db.query(PlanoConta).filter(
        PlanoConta.id == procedimento_id,
        PlanoConta.tipo == "receita",
        PlanoConta.cliente_id.is_(None),
    ).first()
    if procedimento:
        procedimento.ativo = False
        db.commit()
    return RedirectResponse(url="/admin/procedimentos?sucesso=1", status_code=303)
