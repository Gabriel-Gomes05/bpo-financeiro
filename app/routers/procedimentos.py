from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import requer_coordenador
from app.database import get_db
from app.jinja import templates
from app.models import ClienteBPO, PlanoConta, ServicoCadastro, Usuario

router = APIRouter(prefix="/admin")


def _cliente_ativo(request: Request, db: Session) -> Optional[int]:
    raw = request.cookies.get("cliente_ativo", "")
    if not raw:
        return None
    if not raw.isdigit() or not db.query(ClienteBPO.id).filter(
        ClienteBPO.id == int(raw), ClienteBPO.ativo.is_(True),
        ClienteBPO.deleted_at.is_(None),
    ).first():
        raise HTTPException(400, "Selecione uma empresa no painel geral.")
    return int(raw)


def _voltar(mensagem: str = "") -> RedirectResponse:
    return RedirectResponse(f"/admin/servicos{'?' + mensagem if mensagem else ''}", 303)


def _voltar_contas(mensagem: str = "") -> RedirectResponse:
    sufixo = f"&{mensagem}" if mensagem else ""
    return RedirectResponse(f"/admin/servicos?aba=contas-padrao{sufixo}", 303)


@router.get("/procedimentos")
async def redirecionar_procedimentos():
    return RedirectResponse("/admin/servicos", 303)


@router.get("/servicos", response_class=HTMLResponse)
async def pagina_servicos(request: Request, db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador)):
    clientes = db.query(ClienteBPO).filter(
        ClienteBPO.ativo.is_(True), ClienteBPO.deleted_at.is_(None),
    ).order_by(ClienteBPO.nome).all()
    cliente_id = _cliente_ativo(request, db)
    padrao = db.query(ServicoCadastro).filter(
        ServicoCadastro.cliente_id.is_(None), ServicoCadastro.ativo.is_(True),
    ).order_by(ServicoCadastro.codigo, ServicoCadastro.nome).all()
    exclusivos = db.query(ServicoCadastro).filter(
        ServicoCadastro.cliente_id == cliente_id, ServicoCadastro.ativo.is_(True),
    ).order_by(ServicoCadastro.codigo, ServicoCadastro.nome).all() if cliente_id else []
    if cliente_id is None:
        exclusivos = db.query(ServicoCadastro).filter(
            ServicoCadastro.cliente_id.isnot(None), ServicoCadastro.ativo.is_(True),
        ).order_by(ServicoCadastro.codigo, ServicoCadastro.nome).all()
    planos = db.query(PlanoConta).filter(
        PlanoConta.tipo == "receita", PlanoConta.ativo.is_(True),
        (PlanoConta.cliente_id.is_(None) if cliente_id is None else
         ((PlanoConta.cliente_id.is_(None)) | (PlanoConta.cliente_id == cliente_id))),
    ).order_by(PlanoConta.codigo, PlanoConta.nome).all()
    contas_gerais = db.query(PlanoConta).filter(
        PlanoConta.tipo == "despesa", PlanoConta.cliente_id.is_(None),
        PlanoConta.ativo.is_(True),
    ).order_by(PlanoConta.codigo, PlanoConta.nome).all()
    contas_exclusivas = db.query(PlanoConta).filter(
        PlanoConta.tipo == "despesa", PlanoConta.cliente_id == cliente_id,
        PlanoConta.ativo.is_(True),
    ).order_by(PlanoConta.codigo, PlanoConta.nome).all() if cliente_id else []
    return templates.TemplateResponse("admin/procedimentos.html", {
        "request": request, "usuario": usuario, "clientes": clientes,
        "cliente_id": cliente_id, "cliente": next((c for c in clientes if c.id == cliente_id), None),
        "servicos": [*padrao, *exclusivos], "total_padrao": len(padrao),
        "total_exclusivos": len(exclusivos), "nomes_clientes": {c.id: c.nome for c in clientes},
        "planos": planos,
        "contas_padrao": [*contas_gerais, *contas_exclusivas],
        "total_contas_gerais": len(contas_gerais),
        "total_contas_exclusivas": len(contas_exclusivas),
        "aba": request.query_params.get("aba", "servicos"),
    })


@router.post("/contas-padrao")
async def criar_conta_padrao(request: Request, nome: str = Form(...), codigo: Optional[str] = Form(None),
    grupo: Optional[str] = Form(None), db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador)):
    nome = nome.strip()
    if not nome:
        return _voltar_contas("erro=dados_invalidos")
    cliente_id = _cliente_ativo(request, db)
    db.add(PlanoConta(
        tipo="despesa", grupo=(grupo or "Despesas padrão").strip() or "Despesas padrão",
        chave=f"conta_padrao_{uuid4().hex}", codigo=(codigo or "").strip() or None,
        nome=nome, cliente_id=cliente_id, ativo=True,
    ))
    db.commit()
    return _voltar_contas("sucesso=criado")


@router.post("/contas-padrao/{conta_id}/editar")
async def editar_conta_padrao(request: Request, conta_id: int, nome: str = Form(...),
    codigo: Optional[str] = Form(None), grupo: Optional[str] = Form(None),
    db: Session = Depends(get_db), usuario: Usuario = Depends(requer_coordenador)):
    cliente_id = _cliente_ativo(request, db)
    conta = db.query(PlanoConta).filter(
        PlanoConta.id == conta_id, PlanoConta.tipo == "despesa",
        (PlanoConta.cliente_id.is_(None) if cliente_id is None else PlanoConta.cliente_id == cliente_id),
        PlanoConta.ativo.is_(True),
    ).first()
    if not conta or not nome.strip():
        return _voltar_contas("erro=dados_invalidos")
    conta.nome = nome.strip()
    conta.codigo = (codigo or "").strip() or None
    conta.grupo = (grupo or "Despesas padrão").strip() or "Despesas padrão"
    db.commit()
    return _voltar_contas("sucesso=editado")


@router.post("/contas-padrao/{conta_id}/excluir")
async def excluir_conta_padrao(request: Request, conta_id: int, db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador)):
    cliente_id = _cliente_ativo(request, db)
    conta = db.query(PlanoConta).filter(
        PlanoConta.id == conta_id, PlanoConta.tipo == "despesa",
        (PlanoConta.cliente_id.is_(None) if cliente_id is None else PlanoConta.cliente_id == cliente_id),
        PlanoConta.ativo.is_(True),
    ).first()
    if conta:
        conta.ativo = False
        db.commit()
    return _voltar_contas("sucesso=excluido")


@router.post("/servicos")
async def criar_servico(request: Request, nome: str = Form(...), plano_conta_id: int = Form(...),
    codigo: Optional[str] = Form(None),
    disponibilidade: str = Form("todos"), clientes_ids: list[int] = Form([]),
    db: Session = Depends(get_db), usuario: Usuario = Depends(requer_coordenador)):
    cliente_id = _cliente_ativo(request, db)
    nome = nome.strip()
    if not nome:
        return _voltar("erro=dados_invalidos")
    destinos = [cliente_id]
    if cliente_id is None and disponibilidade == "selecionados":
        destinos = sorted(set(clientes_ids))
        validos = {row.id for row in db.query(ClienteBPO.id).filter(
            ClienteBPO.id.in_(destinos), ClienteBPO.ativo.is_(True),
        ).all()}
        if not destinos or set(destinos) != validos:
            return _voltar("erro=selecione_clientes")
    elif cliente_id is None and disponibilidade != "todos":
        return _voltar("erro=dados_invalidos")
    plano = db.query(PlanoConta).filter(
        PlanoConta.id == plano_conta_id, PlanoConta.tipo == "receita",
        PlanoConta.ativo.is_(True), PlanoConta.cliente_id.is_(None),
    ).first()
    if not plano:
        if len(destinos) != 1 or destinos[0] is None:
            return _voltar("erro=plano_invalido")
        plano = db.query(PlanoConta).filter(
            PlanoConta.id == plano_conta_id, PlanoConta.tipo == "receita",
            PlanoConta.ativo.is_(True), PlanoConta.cliente_id == destinos[0],
        ).first()
    if not plano:
        return _voltar("erro=plano_invalido")
    for destino in destinos:
        db.add(ServicoCadastro(cliente_id=destino, codigo=(codigo or "").strip() or None,
            nome=nome, plano_conta_id=plano.id, ativo=True))
    db.commit()
    return _voltar("sucesso=criado")


@router.post("/servicos/{servico_id}/editar")
async def editar_servico(request: Request, servico_id: int, nome: str = Form(...),
    plano_conta_id: int = Form(...), codigo: Optional[str] = Form(None), db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador)):
    cliente_id = _cliente_ativo(request, db)
    servico = db.query(ServicoCadastro).filter(
        ServicoCadastro.id == servico_id,
        (ServicoCadastro.cliente_id.is_(None) if cliente_id is None else
         ((ServicoCadastro.cliente_id.is_(None)) | (ServicoCadastro.cliente_id == cliente_id))),
    ).first()
    plano_cliente_permitido = None if servico and servico.cliente_id is None else cliente_id
    plano = db.query(PlanoConta).filter(
        PlanoConta.id == plano_conta_id, PlanoConta.tipo == "receita", PlanoConta.ativo.is_(True),
        (PlanoConta.cliente_id.is_(None) if plano_cliente_permitido is None else
         ((PlanoConta.cliente_id.is_(None)) | (PlanoConta.cliente_id == plano_cliente_permitido))),
    ).first()
    if not servico or not plano or not nome.strip():
        return _voltar("erro=dados_invalidos")
    servico.nome, servico.codigo, servico.plano_conta_id = (
        nome.strip(), (codigo or "").strip() or None, plano.id,
    )
    db.commit()
    return _voltar("sucesso=editado")


@router.post("/servicos/{servico_id}/excluir")
async def excluir_servico(request: Request, servico_id: int, db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador)):
    cliente_id = _cliente_ativo(request, db)
    servico = db.query(ServicoCadastro).filter(
        ServicoCadastro.id == servico_id,
        (ServicoCadastro.cliente_id.is_(None) if cliente_id is None else
         (ServicoCadastro.cliente_id == cliente_id)),
    ).first()
    if servico:
        servico.ativo = False
        db.commit()
    return _voltar("sucesso=excluido")
