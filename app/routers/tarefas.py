from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.database import get_db
from app.jinja import templates
from app.models import Tarefa, Usuario
from app.security import secure_cookie_for
from app.services import tarefas_service as svc
from app.services.log_service import registrar as _log

router = APIRouter()


def _destino_seguro(voltar: Optional[str]) -> str:
    return voltar if svc.link_interno(voltar) else "/tarefas"


def _redirecionar(voltar: Optional[str], mensagem: str, erro: bool = False) -> RedirectResponse:
    destino = _destino_seguro(voltar)
    separador = "&" if "?" in destino else "?"
    chave = "erro_tarefa" if erro else "ok_tarefa"
    return RedirectResponse(f"{destino}{separador}{chave}={quote_plus(mensagem)}", status_code=303)


def _obter(db: Session, usuario: Usuario, tarefa_id: int) -> Tarefa:
    tarefa = svc.tarefas_visiveis(db, usuario).filter(Tarefa.id == tarefa_id).first()
    if not tarefa:
        raise HTTPException(404, "Tarefa não encontrada.")
    return tarefa


def _dados_validados(
    db: Session, usuario: Usuario, titulo: str, responsavel_id: Optional[int],
    cliente_id: Optional[int], modulo: Optional[str], link: Optional[str],
) -> dict:
    titulo = (titulo or "").strip()
    if not titulo or len(titulo) > 200:
        raise ValueError("Informe um título com até 200 caracteres.")

    if svc.eh_admin(usuario) and responsavel_id:
        responsavel = db.query(Usuario.id).filter(
            Usuario.id == responsavel_id, Usuario.ativo.is_(True), Usuario.deleted_at.is_(None),
        ).first()
        if not responsavel:
            raise ValueError("Responsável inválido.")
    else:
        # Quem não é admin só cria tarefas para si mesmo.
        responsavel_id = usuario.id

    if cliente_id:
        if cliente_id not in {c.id for c in svc.clientes_permitidos(db, usuario)}:
            raise ValueError("Cliente inválido.")
    else:
        cliente_id = None

    modulo = (modulo or "").strip() or None
    if modulo and (modulo not in svc.MODULOS_TAREFA or not cliente_id):
        raise ValueError("Módulo inválido para esta tarefa.")

    return {
        "titulo": titulo, "responsavel_id": responsavel_id, "cliente_id": cliente_id,
        "modulo": modulo, "link": svc.normalizar_link(link),
    }


@router.get("/tarefas", response_class=HTMLResponse)
async def listar_tarefas(
    request: Request,
    status: str = "pendentes",
    vinculo: str = "todas",
    cliente: Optional[int] = None,
    responsavel: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    query = svc.tarefas_visiveis(db, usuario)
    if status == "pendentes":
        query = query.filter(Tarefa.concluida.is_(False))
    elif status == "concluidas":
        query = query.filter(Tarefa.concluida.is_(True))
    if vinculo == "pessoais":
        query = query.filter(Tarefa.cliente_id.is_(None))
    elif vinculo == "clientes":
        query = query.filter(Tarefa.cliente_id.isnot(None))
    if cliente:
        query = query.filter(Tarefa.cliente_id == cliente)
    if responsavel and svc.eh_admin(usuario):
        query = query.filter(Tarefa.responsavel_id == responsavel)

    equipe = []
    if svc.eh_admin(usuario):
        equipe = db.query(Usuario).filter(
            Usuario.ativo.is_(True), Usuario.deleted_at.is_(None),
        ).order_by(Usuario.nome).all()

    return templates.TemplateResponse("tarefas.html", {
        "request": request,
        "usuario": usuario,
        "painel_geral": True,
        "tarefas": svc.ordenar(query).all(),
        "clientes_tarefa": svc.clientes_permitidos(db, usuario),
        "equipe": equipe,
        "modulos": svc.MODULOS_TAREFA,
        "eh_admin": svc.eh_admin(usuario),
        "filtros": {"status": status, "vinculo": vinculo, "cliente": cliente, "responsavel": responsavel},
        "novo_cliente": cliente,
        "hoje": date.today(),
    })


@router.post("/tarefas")
async def criar_tarefa(
    titulo: str = Form(...),
    descricao: Optional[str] = Form(None),
    prazo: Optional[date] = Form(None),
    responsavel_id: Optional[int] = Form(None),
    cliente_id: Optional[int] = Form(None),
    modulo: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    voltar: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    try:
        dados = _dados_validados(db, usuario, titulo, responsavel_id, cliente_id, modulo, link)
    except ValueError as exc:
        return _redirecionar(voltar, str(exc), erro=True)
    tarefa = Tarefa(**dados, descricao=(descricao or "").strip() or None, prazo=prazo, criado_por_id=usuario.id)
    db.add(tarefa)
    db.commit()
    _log(db, "Tarefa criada", "tarefas", usuario_id=usuario.id, usuario_nome=usuario.nome,
         cliente_id=tarefa.cliente_id, detalhes=tarefa.titulo)
    return _redirecionar(voltar, "Tarefa criada.")


@router.post("/tarefas/{tarefa_id}/editar")
async def editar_tarefa(
    tarefa_id: int,
    titulo: str = Form(...),
    descricao: Optional[str] = Form(None),
    prazo: Optional[date] = Form(None),
    responsavel_id: Optional[int] = Form(None),
    cliente_id: Optional[int] = Form(None),
    modulo: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    voltar: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    tarefa = _obter(db, usuario, tarefa_id)
    if not svc.pode_editar(usuario, tarefa):
        raise HTTPException(403, "Apenas quem criou a tarefa ou o admin pode editá-la.")
    try:
        dados = _dados_validados(db, usuario, titulo, responsavel_id, cliente_id, modulo, link)
    except ValueError as exc:
        return _redirecionar(voltar, str(exc), erro=True)
    for campo, valor in dados.items():
        setattr(tarefa, campo, valor)
    tarefa.descricao = (descricao or "").strip() or None
    tarefa.prazo = prazo
    db.commit()
    return _redirecionar(voltar, "Tarefa atualizada.")


@router.post("/tarefas/{tarefa_id}/concluir")
async def alternar_conclusao(
    tarefa_id: int,
    voltar: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    tarefa = _obter(db, usuario, tarefa_id)
    if not svc.pode_concluir(usuario, tarefa):
        raise HTTPException(403, "Apenas o responsável ou o admin pode concluir a tarefa.")
    tarefa.concluida = not tarefa.concluida
    tarefa.concluida_em = datetime.now() if tarefa.concluida else None
    db.commit()
    return _redirecionar(voltar, "Tarefa concluída." if tarefa.concluida else "Tarefa reaberta.")


@router.post("/tarefas/{tarefa_id}/excluir")
async def excluir_tarefa(
    tarefa_id: int,
    voltar: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    tarefa = _obter(db, usuario, tarefa_id)
    if not svc.pode_editar(usuario, tarefa):
        raise HTTPException(403, "Apenas quem criou a tarefa ou o admin pode excluí-la.")
    tarefa.deleted_at = datetime.now(timezone.utc)
    db.commit()
    _log(db, "Tarefa excluída", "tarefas", usuario_id=usuario.id, usuario_nome=usuario.nome,
         cliente_id=tarefa.cliente_id, detalhes=tarefa.titulo)
    return _redirecionar(voltar, "Tarefa excluída.")


@router.get("/tarefas/{tarefa_id}/abrir")
async def abrir_tarefa(
    tarefa_id: int,
    request: Request,
    destino: str = "modulo",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    """Entra no cliente da tarefa (se houver) e leva ao módulo ou link interno."""
    tarefa = _obter(db, usuario, tarefa_id)
    if destino == "link" and svc.link_interno(tarefa.link):
        caminho = tarefa.link
    elif tarefa.modulo in svc.MODULOS_TAREFA:
        caminho = svc.MODULOS_TAREFA[tarefa.modulo][1]
    else:
        caminho = "/" if tarefa.cliente_id else "/tarefas"

    if not tarefa.cliente_id:
        return RedirectResponse(caminho, status_code=303)
    if tarefa.cliente_id not in {c.id for c in svc.clientes_permitidos(db, usuario)}:
        return _redirecionar("/tarefas", "Você não tem acesso ao cliente desta tarefa.", erro=True)

    response = RedirectResponse(caminho, status_code=303)
    response.set_cookie(
        "cliente_ativo", str(tarefa.cliente_id), max_age=60 * 60 * 24 * 30,
        samesite="strict", httponly=True, secure=secure_cookie_for(request), path="/",
    )
    return response
