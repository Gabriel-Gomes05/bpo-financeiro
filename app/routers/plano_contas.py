import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import requer_coordenador
from app.database import get_db
from app.jinja import templates
from app.models import ClienteBPO, PlanoConta, Usuario

router = APIRouter(prefix="/admin")


def _slugificar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or "conta"


def _voltar(cliente_id: int, mensagem: str = "") -> RedirectResponse:
    sufixo = f"&{mensagem}" if mensagem else ""
    return RedirectResponse(url=f"/admin/plano-contas?cliente_id={cliente_id}{sufixo}", status_code=303)


@router.get("/plano-contas", response_class=HTMLResponse)
async def pagina_plano_contas(request: Request, cliente_id: Optional[int] = None,
    db: Session = Depends(get_db), usuario: Usuario = Depends(requer_coordenador)):
    clientes = db.query(ClienteBPO).filter(ClienteBPO.ativo == True).order_by(ClienteBPO.nome).all()
    ids_clientes = {cliente.id for cliente in clientes}
    if cliente_id not in ids_clientes:
        cliente_id = clientes[0].id if clientes else None
    padrao = db.query(PlanoConta).filter(PlanoConta.cliente_id.is_(None), PlanoConta.ativo == True).order_by(PlanoConta.codigo.asc(), PlanoConta.nome.asc()).all()
    personalizadas = db.query(PlanoConta).filter(PlanoConta.cliente_id == cliente_id, PlanoConta.ativo == True).order_by(PlanoConta.codigo.asc(), PlanoConta.nome.asc()).all() if cliente_id else []
    contas = [*padrao, *personalizadas]
    return templates.TemplateResponse("admin/plano_contas.html", {
        "request": request, "usuario": usuario, "clientes": clientes, "cliente_id": cliente_id,
        "cliente": next((c for c in clientes if c.id == cliente_id), None),
        "receitas": [c for c in contas if c.tipo == "receita"],
        "despesas": [c for c in contas if c.tipo == "despesa"],
        "total_padrao": len(padrao), "total_personalizadas": len(personalizadas),
    })


@router.post("/plano-contas")
async def criar_plano_conta(cliente_id: int = Form(...), tipo: str = Form(...),
    grupo: str = Form(...), nome: str = Form(...), codigo: Optional[str] = Form(None),
    db: Session = Depends(get_db), usuario: Usuario = Depends(requer_coordenador)):
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id, ClienteBPO.ativo == True).first()
    tipo, grupo, nome = tipo.strip().lower(), grupo.strip(), nome.strip()
    if not cliente or tipo not in ("receita", "despesa") or not grupo or not nome:
        return _voltar(cliente_id, "erro=dados_invalidos")
    conta = PlanoConta(tipo=tipo, grupo=grupo, nome=nome, codigo=(codigo or "").strip() or None,
        chave="pendente", cliente_id=cliente_id, ativo=True)
    db.add(conta)
    db.flush()
    conta.chave = f"cliente_{cliente_id}_{_slugificar(nome)}_{conta.id}"
    db.commit()
    return _voltar(cliente_id, "sucesso=criado")


@router.post("/plano-contas/{conta_id}/editar")
async def editar_plano_conta(conta_id: int, cliente_id: int = Form(...), grupo: str = Form(...),
    nome: str = Form(...), codigo: Optional[str] = Form(None), db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador)):
    conta = db.query(PlanoConta).filter(PlanoConta.id == conta_id, PlanoConta.cliente_id == cliente_id).first()
    grupo, nome = grupo.strip(), nome.strip()
    if conta and grupo and nome:
        conta.grupo, conta.nome, conta.codigo = grupo, nome, (codigo or "").strip() or None
        db.commit()
        return _voltar(cliente_id, "sucesso=editado")
    return _voltar(cliente_id, "erro=dados_invalidos")


@router.post("/plano-contas/{conta_id}/excluir")
async def excluir_plano_conta(conta_id: int, cliente_id: int = Form(...), db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador)):
    conta = db.query(PlanoConta).filter(PlanoConta.id == conta_id, PlanoConta.cliente_id == cliente_id).first()
    if conta:
        conta.ativo = False
        db.commit()
    return _voltar(cliente_id, "sucesso=excluido")
