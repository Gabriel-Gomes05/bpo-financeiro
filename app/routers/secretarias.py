"""Cadastro de secretárias (perfil vinculado a um único cliente) por coordenador e editor."""
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import hash_senha, normalizar_email, validar_senha_nova, ve_todos_os_clientes
from app.authorization import Permission, require_permission
from app.database import get_db
from app.jinja import templates
from app.models import ClienteBPO, PerfilUsuario, Usuario
from app.services.log_service import registrar as _log

router = APIRouter(prefix="/admin/secretarias")
require_secretarias = require_permission(Permission.SECRETARIAS)


def _meus_clientes(db: Session, usuario: Usuario):
    """Clientes ativos que o usuário enxerga: todos (coordenador) ou os designados a ele (editor)."""
    query = db.query(ClienteBPO).filter(ClienteBPO.ativo.is_(True), ClienteBPO.deleted_at.is_(None))
    if not ve_todos_os_clientes(usuario):
        query = query.filter(ClienteBPO.funcionario_id == usuario.id)
    return query


def _clientes_ativos(db: Session, usuario: Usuario):
    return _meus_clientes(db, usuario).order_by(ClienteBPO.nome).all()


def _cliente_valido(db: Session, usuario: Usuario, cliente_id: str) -> Optional[ClienteBPO]:
    if not str(cliente_id or "").isdigit():
        return None
    return _meus_clientes(db, usuario).filter(ClienteBPO.id == int(cliente_id)).first()


def _secretarias(db: Session, usuario: Usuario):
    query = db.query(Usuario).filter(Usuario.perfil == PerfilUsuario.secretaria, Usuario.deleted_at.is_(None))
    if not ve_todos_os_clientes(usuario):
        query = query.filter(Usuario.cliente_id.in_(_meus_clientes(db, usuario).with_entities(ClienteBPO.id)))
    return query


def _secretaria(db: Session, usuario: Usuario, usuario_id: int) -> Optional[Usuario]:
    return _secretarias(db, usuario).filter(Usuario.id == usuario_id).first()


def _email_em_uso(db: Session, email: str, exceto_id: Optional[int] = None) -> bool:
    query = db.query(Usuario.id).filter(Usuario.email == email)
    if exceto_id:
        query = query.filter(Usuario.id != exceto_id)
    return query.first() is not None


@router.get("", response_class=HTMLResponse)
async def pagina_secretarias(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_secretarias),
):
    secretarias = _secretarias(db, usuario).order_by(Usuario.ativo.desc(), Usuario.nome).all()
    return templates.TemplateResponse("admin/secretarias.html", {
        "request": request,
        "usuario": usuario,
        "secretarias": secretarias,
        "clientes_ativos": _clientes_ativos(db, usuario),
    })


@router.post("")
async def criar_secretaria(
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    cliente_id: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_secretarias),
):
    nome, email = nome.strip(), normalizar_email(email)
    if not nome or not email or "@" not in email:
        return RedirectResponse(url="/admin/secretarias?erro=dados_invalidos", status_code=303)
    if not validar_senha_nova(senha):
        return RedirectResponse(url="/admin/secretarias?erro=senha_curta", status_code=303)
    cliente = _cliente_valido(db, usuario, cliente_id)
    if not cliente:
        return RedirectResponse(url="/admin/secretarias?erro=cliente_obrigatorio", status_code=303)
    if _email_em_uso(db, email):
        return RedirectResponse(url="/admin/secretarias?erro=email_duplicado", status_code=303)

    nova = Usuario(
        nome=nome, email=email, senha_hash=hash_senha(senha),
        perfil=PerfilUsuario.secretaria, cliente_id=cliente.id, ativo=True,
    )
    db.add(nova)
    db.commit()
    _log(db, "Secretária criada", "admin", usuario_id=usuario.id, usuario_nome=usuario.nome,
         cliente_id=cliente.id, cliente_nome=cliente.nome, detalhes=f"{nova.nome} — {nova.email}")
    return RedirectResponse(url="/admin/secretarias?sucesso=criada", status_code=303)


@router.post("/{usuario_id}/editar")
async def editar_secretaria(
    usuario_id: int,
    nome: str = Form(...),
    email: str = Form(...),
    cliente_id: str = Form(""),
    senha: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_secretarias),
):
    alvo = _secretaria(db, usuario, usuario_id)
    if not alvo:
        return RedirectResponse(url="/admin/secretarias?erro=usuario_nao_encontrado", status_code=303)
    nome, email, senha = nome.strip(), normalizar_email(email), (senha or "").strip()
    if not nome or not email or "@" not in email:
        return RedirectResponse(url=f"/admin/secretarias?erro=dados_invalidos&editar={usuario_id}", status_code=303)
    if senha and not validar_senha_nova(senha):
        return RedirectResponse(url=f"/admin/secretarias?erro=senha_curta&editar={usuario_id}", status_code=303)
    cliente = _cliente_valido(db, usuario, cliente_id)
    if not cliente:
        return RedirectResponse(url=f"/admin/secretarias?erro=cliente_obrigatorio&editar={usuario_id}", status_code=303)
    if _email_em_uso(db, email, exceto_id=usuario_id):
        return RedirectResponse(url=f"/admin/secretarias?erro=email_duplicado&editar={usuario_id}", status_code=303)

    mudou_cliente = alvo.cliente_id != cliente.id
    alvo.nome, alvo.email, alvo.cliente_id = nome, email, cliente.id
    if senha:
        alvo.senha_hash = hash_senha(senha)
    if senha or mudou_cliente:
        alvo.auth_version += 1  # encerra a sessão atual: ela entra de novo já no cliente/senha novos
    db.commit()
    _log(db, "Secretária editada", "admin", usuario_id=usuario.id, usuario_nome=usuario.nome,
         cliente_id=cliente.id, cliente_nome=cliente.nome,
         detalhes=f"{alvo.nome} — {alvo.email}" + (" — senha alterada" if senha else ""))
    return RedirectResponse(url="/admin/secretarias?sucesso=editada", status_code=303)


@router.post("/{usuario_id}/toggle")
async def alternar_secretaria(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_secretarias),
):
    alvo = _secretaria(db, usuario, usuario_id)
    if not alvo:
        return RedirectResponse(url="/admin/secretarias?erro=usuario_nao_encontrado", status_code=303)
    if not alvo.ativo and not _cliente_valido(db, usuario, str(alvo.cliente_id or "")):
        return RedirectResponse(url=f"/admin/secretarias?erro=cliente_obrigatorio&editar={usuario_id}", status_code=303)
    alvo.ativo = not alvo.ativo
    if not alvo.ativo:
        alvo.auth_version += 1
    db.commit()
    _log(db, "Secretária ativada" if alvo.ativo else "Secretária desativada", "admin",
         usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=alvo.cliente_id, detalhes=alvo.nome)
    return RedirectResponse(url="/admin/secretarias?sucesso=" + ("ativada" if alvo.ativo else "desativada"),
                            status_code=303)
