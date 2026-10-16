"""Contas fixas recorrentes do cliente ativo (avisos de vencimento no dashboard e por e-mail)."""
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import tem_acesso_geral
from app.authorization import Permission, require_permission
from app.database import get_db
from app.jinja import templates
from app.models import ClienteBPO, ContaRecorrente, PerfilUsuario, Usuario
from app.services.log_service import registrar as _log

router = APIRouter()
require_contas_pagar = require_permission(Permission.CONTAS_PAGAR)
CAMINHO = "/contas-pagar/recorrentes"


def _cliente_ativo(request: Request, db: Session, usuario: Usuario) -> ClienteBPO:
    raw = request.cookies.get("cliente_ativo", "")
    query = db.query(ClienteBPO).filter(
        ClienteBPO.id == (int(raw) if raw.isdigit() else -1),
        ClienteBPO.ativo.is_(True), ClienteBPO.deleted_at.is_(None),
    )
    if not tem_acesso_geral(usuario):
        query = query.filter(ClienteBPO.funcionario_id == usuario.id)
    cliente = query.first()
    if not cliente:
        raise HTTPException(400, "Selecione uma empresa no painel geral.")
    return cliente


def _exigir_coordenador(usuario: Usuario) -> None:
    if usuario.perfil != PerfilUsuario.coordenador:
        raise HTTPException(403, "Apenas o coordenador gerencia contas recorrentes.")


def _obter(db: Session, cliente: ClienteBPO, rec_id: int) -> ContaRecorrente:
    rec = db.query(ContaRecorrente).filter(
        ContaRecorrente.id == rec_id, ContaRecorrente.cliente_id == cliente.id,
    ).first()
    if not rec:
        raise HTTPException(404, "Conta recorrente não encontrada.")
    return rec


def _voltar(mensagem: str, erro: bool = False) -> RedirectResponse:
    return RedirectResponse(f"{CAMINHO}?{'erro' if erro else 'sucesso'}={mensagem}", status_code=303)


@router.get(CAMINHO, response_class=HTMLResponse)
async def listar_recorrentes(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    cliente = _cliente_ativo(request, db, usuario)
    contas = db.query(ContaRecorrente).filter(
        ContaRecorrente.cliente_id == cliente.id,
    ).order_by(ContaRecorrente.dia_vencimento.asc()).all()
    return templates.TemplateResponse("contas_recorrentes.html", {
        "request": request, "usuario": usuario, "cliente": cliente, "contas_recorrentes": contas,
        "pode_gerenciar": usuario.perfil == PerfilUsuario.coordenador,
    })


@router.post(CAMINHO)
async def criar_recorrente(
    request: Request,
    descricao: str = Form(...),
    email_destino: str = Form(...),
    dia_vencimento: int = Form(...),
    dias_antecedencia: int = Form(3),
    fornecedor: Optional[str] = Form(None),
    valor: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    _exigir_coordenador(usuario)
    cliente = _cliente_ativo(request, db, usuario)
    descricao, email_destino = descricao.strip(), email_destino.strip()
    if not descricao or "@" not in email_destino or not 1 <= dia_vencimento <= 31:
        return _voltar("dados_invalidos", erro=True)
    valor_dec = None
    if valor:
        try:
            valor_dec = Decimal(str(valor).replace(",", "."))
        except InvalidOperation:
            return _voltar("dados_invalidos", erro=True)
    db.add(ContaRecorrente(
        cliente_id=cliente.id,
        descricao=descricao,
        fornecedor=(fornecedor or "").strip() or None,
        valor=valor_dec,
        dia_vencimento=dia_vencimento,
        dias_antecedencia=max(1, min(30, dias_antecedencia)),
        email_destino=email_destino,
    ))
    db.commit()
    _log(db, "Conta recorrente criada", "contas_pagar", usuario_id=usuario.id, usuario_nome=usuario.nome,
         cliente_id=cliente.id, detalhes=descricao)
    return _voltar("criada")


@router.post(CAMINHO + "/{rec_id}/toggle")
async def alternar_recorrente(
    rec_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    _exigir_coordenador(usuario)
    rec = _obter(db, _cliente_ativo(request, db, usuario), rec_id)
    rec.ativo = not rec.ativo
    db.commit()
    return _voltar("ativada" if rec.ativo else "pausada")


@router.post(CAMINHO + "/{rec_id}/excluir")
async def excluir_recorrente(
    rec_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    _exigir_coordenador(usuario)
    rec = _obter(db, _cliente_ativo(request, db, usuario), rec_id)
    db.delete(rec)
    db.commit()
    return _voltar("excluida")
