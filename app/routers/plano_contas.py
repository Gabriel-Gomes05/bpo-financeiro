import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import requer_coordenador
from app.database import get_db
from app.jinja import templates
from app.models import PlanoConta, Usuario

router = APIRouter(prefix="/admin")


def _slugificar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or "conta"


@router.get("/plano-contas", response_class=HTMLResponse)
async def pagina_plano_contas(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador),
):
    contas = db.query(PlanoConta).filter(
        PlanoConta.cliente_id.is_(None),
        PlanoConta.ativo == True,
    ).order_by(PlanoConta.tipo.desc(), PlanoConta.grupo.asc(), PlanoConta.nome.asc()).all()
    receitas = [c for c in contas if c.tipo == "receita"]
    despesas = [c for c in contas if c.tipo == "despesa"]
    return templates.TemplateResponse("admin/plano_contas.html", {
        "request": request,
        "usuario": usuario,
        "receitas": receitas,
        "despesas": despesas,
    })


@router.post("/plano-contas")
async def criar_plano_conta(
    tipo: str = Form(...),
    grupo: str = Form(...),
    nome: str = Form(...),
    codigo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador),
):
    tipo = tipo.strip().lower()
    if tipo not in ("receita", "despesa"):
        return RedirectResponse(url="/admin/plano-contas", status_code=303)

    conta = PlanoConta(
        tipo=tipo,
        grupo=grupo.strip(),
        nome=nome.strip(),
        codigo=(codigo or "").strip() or None,
        chave="",
        cliente_id=None,
    )
    db.add(conta)
    db.flush()
    base = _slugificar(nome)
    chave = f"pc_{base}"
    if db.query(PlanoConta).filter(PlanoConta.chave == chave, PlanoConta.cliente_id.is_(None)).first():
        chave = f"pc_{conta.id}"
    conta.chave = chave
    db.commit()
    return RedirectResponse(url="/admin/plano-contas", status_code=303)


@router.post("/plano-contas/{conta_id}/editar")
async def editar_plano_conta(
    conta_id: int,
    grupo: str = Form(...),
    nome: str = Form(...),
    codigo: Optional[str] = Form(None),
    ativo: bool = Form(True),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador),
):
    conta = db.query(PlanoConta).filter(PlanoConta.id == conta_id, PlanoConta.cliente_id.is_(None)).first()
    if conta:
        conta.grupo = grupo.strip()
        conta.nome = nome.strip()
        conta.codigo = (codigo or "").strip() or None
        conta.ativo = ativo
        db.commit()
    return RedirectResponse(url="/admin/plano-contas", status_code=303)


@router.post("/plano-contas/{conta_id}/excluir")
async def excluir_plano_conta(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador),
):
    conta = db.query(PlanoConta).filter(PlanoConta.id == conta_id, PlanoConta.cliente_id.is_(None)).first()
    if conta:
        conta.ativo = False
        db.commit()
    return RedirectResponse(url="/admin/plano-contas", status_code=303)
