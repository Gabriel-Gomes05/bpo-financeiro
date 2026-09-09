import re
import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, HTTPException
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


def _contexto_cliente(request: Request, db: Session) -> Optional[int]:
    raw = request.cookies.get("cliente_ativo", "")
    if not raw:
        return None
    if not raw.isdigit() or not db.query(ClienteBPO.id).filter(
        ClienteBPO.id == int(raw), ClienteBPO.ativo.is_(True),
        ClienteBPO.deleted_at.is_(None),
    ).first():
        raise HTTPException(status_code=400, detail="Selecione uma empresa no painel geral.")
    return int(raw)


def _voltar(cliente_id: Optional[int], mensagem: str = "") -> RedirectResponse:
    sufixo = f"?{mensagem}" if mensagem else ""
    return RedirectResponse(url=f"/admin/plano-contas{sufixo}", status_code=303)


@router.get("/plano-contas", response_class=HTMLResponse)
async def pagina_plano_contas(request: Request, cliente_id: Optional[int] = None,
    db: Session = Depends(get_db), usuario: Usuario = Depends(requer_coordenador)):
    clientes = db.query(ClienteBPO).filter(ClienteBPO.ativo == True, ClienteBPO.deleted_at.is_(None)).order_by(ClienteBPO.nome).all()
    cliente_id = _contexto_cliente(request, db)
    padrao = db.query(PlanoConta).filter(PlanoConta.cliente_id.is_(None), PlanoConta.ativo == True).order_by(PlanoConta.codigo.asc(), PlanoConta.nome.asc()).all()
    personalizadas = db.query(PlanoConta).filter(PlanoConta.cliente_id == cliente_id, PlanoConta.ativo == True).order_by(PlanoConta.codigo.asc(), PlanoConta.nome.asc()).all() if cliente_id else []
    if cliente_id is None:
        personalizadas = db.query(PlanoConta).filter(
            PlanoConta.cliente_id.in_([c.id for c in clientes]), PlanoConta.ativo.is_(True),
        ).order_by(PlanoConta.codigo, PlanoConta.nome).all()
    contas = [*padrao, *personalizadas]
    return templates.TemplateResponse("admin/plano_contas.html", {
        "request": request, "usuario": usuario, "clientes": clientes, "cliente_id": cliente_id,
        "cliente": next((c for c in clientes if c.id == cliente_id), None),
        "receitas": [c for c in contas if c.tipo == "receita"],
        "despesas": [c for c in contas if c.tipo == "despesa"],
        "total_padrao": len(padrao), "total_personalizadas": len(personalizadas),
        "nomes_clientes": {c.id: c.nome for c in clientes},
    })


@router.post("/plano-contas")
async def criar_plano_conta(request: Request, tipo: str = Form(...),
    grupo: str = Form(...), nome: str = Form(...), codigo: Optional[str] = Form(None),
    disponibilidade: str = Form("todos"), clientes_ids: list[int] = Form([]),
    db: Session = Depends(get_db), usuario: Usuario = Depends(requer_coordenador)):
    cliente_id = _contexto_cliente(request, db)
    tipo, grupo, nome = tipo.strip().lower(), grupo.strip(), nome.strip()
    if tipo not in ("receita", "despesa") or not grupo or not nome:
        return _voltar(cliente_id, "erro=dados_invalidos")
    destinos = [cliente_id]
    if cliente_id is None:
        if disponibilidade == "selecionados":
            destinos = sorted(set(clientes_ids))
            validos = {c.id for c in db.query(ClienteBPO.id).filter(
                ClienteBPO.id.in_(destinos), ClienteBPO.ativo.is_(True),
                ClienteBPO.deleted_at.is_(None),
            ).all()}
            if not destinos or set(destinos) != validos:
                return _voltar(None, "erro=selecione_clientes")
        elif disponibilidade != "todos":
            return _voltar(None, "erro=dados_invalidos")
    for destino in destinos:
        conta = PlanoConta(tipo=tipo, grupo=grupo, nome=nome, codigo=(codigo or "").strip() or None,
            chave="pendente", cliente_id=destino, ativo=True)
        db.add(conta)
        db.flush()
        conta.chave = f"{'cliente_' + str(destino) if destino else 'padrao'}_{_slugificar(nome)}_{conta.id}"
    db.commit()
    return _voltar(cliente_id, "sucesso=criado")


@router.post("/plano-contas/{conta_id}/editar")
async def editar_plano_conta(request: Request, conta_id: int, grupo: str = Form(...),
    nome: str = Form(...), codigo: Optional[str] = Form(None), db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador)):
    cliente_id = _contexto_cliente(request, db)
    if cliente_id is None:
        raise HTTPException(status_code=403, detail="Contas padrao protegidas.")
    conta = db.query(PlanoConta).filter(PlanoConta.id == conta_id, PlanoConta.cliente_id == cliente_id).first()
    grupo, nome = grupo.strip(), nome.strip()
    if conta and grupo and nome:
        conta.grupo, conta.nome, conta.codigo = grupo, nome, (codigo or "").strip() or None
        db.commit()
        return _voltar(cliente_id, "sucesso=editado")
    return _voltar(cliente_id, "erro=dados_invalidos")


@router.post("/plano-contas/{conta_id}/excluir")
async def excluir_plano_conta(request: Request, conta_id: int, db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador)):
    cliente_id = _contexto_cliente(request, db)
    if cliente_id is None:
        raise HTTPException(status_code=403, detail="Contas padrao protegidas.")
    conta = db.query(PlanoConta).filter(PlanoConta.id == conta_id, PlanoConta.cliente_id == cliente_id).first()
    if conta:
        conta.ativo = False
        db.commit()
    return _voltar(cliente_id, "sucesso=excluido")
