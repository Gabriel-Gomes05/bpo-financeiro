from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.database import get_db
from app.models import ClienteBPO, ContaPagar, ContaRecorrente, StatusContaPagar, TarefaRotina, Usuario, PerfilUsuario
from app.utils import cliente_ativo as _ca
from app.services.log_service import registrar as _log

router = APIRouter()


# ---------------------------------------------------------------------------
# HTML inline retornado pelo HTMX (sem Jinja2)
# ---------------------------------------------------------------------------

_BTN_EXCLUIR = (
    '<button hx-post="/rotinas/{id}/excluir" hx-target="#tarefa-{id}" hx-swap="outerHTML"'
    ' hx-confirm="Excluir esta tarefa?"'
    ' class="flex-shrink-0 text-gray-300 hover:text-red-400 transition-colors p-1" title="Excluir">'
    '<svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
    '<path stroke-linecap="round" stroke-linejoin="round"'
    ' d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M8 7V5a1 1 0 011-1h6a1 1 0 011 1v2"/>'
    "</svg></button>"
)

_LI_PENDENTE = """
<li id="tarefa-{id}" class="flex items-center gap-4 px-5 py-3 transition-colors hover:bg-gray-50">
  <button hx-post="/rotinas/{id}/toggle" hx-target="#tarefa-{id}" hx-swap="outerHTML"
          class="flex-shrink-0 w-6 h-6 rounded-full border-2 border-gray-300 hover:border-blue-400 flex items-center justify-center transition-colors"
          title="Concluir"></button>
  <div class="flex-1 min-w-0">
    <p class="text-sm font-medium text-gray-800">{descricao}</p>
    <p class="text-xs text-gray-400">{funcionario}</p>
  </div>
  <span class="text-xs text-gray-400 flex-shrink-0">{horario}</span>
  {btn_excluir}
</li>
"""

_LI_CONCLUIDA_COORD = """
<li id="tarefa-{id}" class="flex items-center gap-4 px-5 py-3 transition-colors bg-green-50">
  <button hx-post="/rotinas/{id}/toggle" hx-target="#tarefa-{id}" hx-swap="outerHTML"
          class="flex-shrink-0 w-6 h-6 rounded-full bg-green-500 border-2 border-green-500 text-white flex items-center justify-center transition-colors"
          title="Desfazer"><span class="text-xs font-bold">&#10003;</span></button>
  <div class="flex-1 min-w-0">
    <p class="text-sm font-medium line-through text-gray-400">{descricao}</p>
    {horario_concluida}
  </div>
  <span class="text-xs text-gray-400 flex-shrink-0">{horario}</span>
  {btn_excluir}
</li>
"""

_LI_CONCLUIDA_LOCK = """
<li id="tarefa-{id}" class="flex items-center gap-4 px-5 py-3 transition-colors bg-green-50">
  <div class="flex-shrink-0 w-6 h-6 rounded-full bg-green-500 border-2 border-green-500 text-white flex items-center justify-center"
       title="Concluída — apenas o coordenador pode reverter">
    <span class="text-xs font-bold">&#10003;</span>
  </div>
  <div class="flex-1 min-w-0">
    <p class="text-sm font-medium line-through text-gray-400">{descricao}</p>
    {horario_concluida}
  </div>
  <span class="text-xs text-gray-400 flex-shrink-0">{horario}</span>
</li>
"""


def _render_li(tarefa: TarefaRotina, pode_reverter: bool) -> str:
    horario_concluida = (
        f'<p class="text-xs text-gray-400 mt-0.5">Concluída às {tarefa.concluida_em.strftime("%H:%M")}</p>'
        if tarefa.concluida_em else ""
    )
    funcionario = tarefa.funcionario.nome if tarefa.funcionario else ""
    btn_excluir = _BTN_EXCLUIR.format(id=tarefa.id) if pode_reverter else ""

    if not tarefa.concluida:
        return _LI_PENDENTE.format(
            id=tarefa.id,
            descricao=tarefa.descricao,
            funcionario=funcionario,
            horario=tarefa.horario_previsto or "",
            btn_excluir=btn_excluir,
        )
    if pode_reverter:
        return _LI_CONCLUIDA_COORD.format(
            id=tarefa.id,
            descricao=tarefa.descricao,
            horario_concluida=horario_concluida,
            horario=tarefa.horario_previsto or "",
            btn_excluir=btn_excluir,
        )
    return _LI_CONCLUIDA_LOCK.format(
        id=tarefa.id,
        descricao=tarefa.descricao,
        horario_concluida=horario_concluida,
        horario=tarefa.horario_previsto or "",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clientes_do_usuario(db: Session, usuario: Usuario):
    if usuario.perfil == PerfilUsuario.coordenador:
        return db.query(ClienteBPO).filter(ClienteBPO.ativo == True).all()
    return db.query(ClienteBPO).filter(
        ClienteBPO.funcionario_id == usuario.id,
        ClienteBPO.ativo == True,
    ).all()


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@router.get("/rotinas", response_class=HTMLResponse)
async def listar_rotinas(
    request: Request,
    cliente_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if usuario.perfil.value in ("secretaria", "medico"):
        return RedirectResponse(url="/", status_code=303)
    cliente_id = _ca(request, cliente_id)
    hoje = date.today()
    clientes = clientes_do_usuario(db, usuario)
    ids_clientes = [c.id for c in clientes]

    query = db.query(TarefaRotina).filter(
        TarefaRotina.data == hoje,
        TarefaRotina.cliente_id.in_(ids_clientes),
    )

    # Funcionários veem apenas suas próprias tarefas
    if usuario.perfil != PerfilUsuario.coordenador:
        query = query.filter(TarefaRotina.funcionario_id == usuario.id)

    if cliente_id and cliente_id in ids_clientes:
        query = query.filter(TarefaRotina.cliente_id == cliente_id)

    tarefas = query.order_by(TarefaRotina.horario_previsto.asc()).all()

    clientes_map = {c.id: c for c in clientes}
    grupos_map = {}
    for t in tarefas:
        if t.cliente_id not in grupos_map:
            grupos_map[t.cliente_id] = {
                "cliente_nome": clientes_map[t.cliente_id].nome,
                "tarefas": [],
                "concluidas": 0,
            }
        grupos_map[t.cliente_id]["tarefas"].append(t)
        if t.concluida:
            grupos_map[t.cliente_id]["concluidas"] += 1

    total = len(tarefas)
    concluidas = sum(1 for t in tarefas if t.concluida)

    funcionarios = []
    if usuario.perfil == PerfilUsuario.coordenador:
        funcionarios = db.query(Usuario).filter(Usuario.ativo == True).all()

    # Contas recorrentes visíveis para todos — já filtradas pelos clientes do usuário
    q_rec = db.query(ContaRecorrente).filter(ContaRecorrente.cliente_id.in_(ids_clientes))
    if cliente_id and cliente_id in ids_clientes:
        q_rec = q_rec.filter(ContaRecorrente.cliente_id == cliente_id)
    contas_recorrentes = q_rec.order_by(ContaRecorrente.dia_vencimento.asc()).all()

    # Contas a pagar pendentes/agendadas — aparecem automaticamente ao serem lançadas
    q_contas = (
        db.query(ContaPagar)
        .filter(
            ContaPagar.cliente_id.in_(ids_clientes),
            ContaPagar.status.in_([
                StatusContaPagar.pendente,
                StatusContaPagar.aguardando_aprovacao,
                StatusContaPagar.agendado,
            ]),
        )
        .order_by(ContaPagar.vencimento.asc())
    )
    if cliente_id and cliente_id in ids_clientes:
        q_contas = q_contas.filter(ContaPagar.cliente_id == cliente_id)
    contas_pagar = q_contas.all()

    return templates.TemplateResponse("rotinas.html", {
        "request": request,
        "usuario": usuario,
        "hoje": hoje,
        "clientes": clientes,
        "tarefas_por_cliente": list(grupos_map.values()),
        "total": total,
        "concluidas": concluidas,
        "cliente_selecionado": cliente_id,
        "funcionarios": funcionarios,
        "pode_reverter": usuario.perfil == PerfilUsuario.coordenador,
        "contas_recorrentes": contas_recorrentes,
        "contas_pagar": contas_pagar,
    })


@router.post("/rotinas")
async def criar_rotina(
    cliente_id: int = Form(...),
    funcionario_id: int = Form(...),
    data: date = Form(...),
    descricao: str = Form(...),
    horario_previsto: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if usuario.perfil != PerfilUsuario.coordenador:
        return RedirectResponse(url="/rotinas", status_code=303)

    db.add(TarefaRotina(
        cliente_id=cliente_id,
        funcionario_id=funcionario_id,
        data=data,
        descricao=descricao,
        horario_previsto=horario_previsto or None,
    ))
    db.commit()
    _log(db, "Tarefa de rotina criada", "rotinas", usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id, detalhes=f"{descricao} — {data.strftime('%d/%m/%Y')}")
    return RedirectResponse(url=f"/rotinas?cliente_id={cliente_id}", status_code=303)


@router.post("/rotinas/{tarefa_id}/toggle", response_class=HTMLResponse)
async def toggle_tarefa(
    tarefa_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    tarefa = db.query(TarefaRotina).filter(TarefaRotina.id == tarefa_id).first()
    if not tarefa:
        return HTMLResponse("<li>Tarefa não encontrada.</li>", status_code=404)

    pode_reverter = usuario.perfil == PerfilUsuario.coordenador

    # Não-coordenador tentando acessar tarefa de outro funcionário
    if not pode_reverter and tarefa.funcionario_id != usuario.id:
        return HTMLResponse("<li>Acesso negado.</li>", status_code=403)

    # Não-coordenador tentando desfazer tarefa já concluída → bloqueia
    if tarefa.concluida and not pode_reverter:
        return HTMLResponse(_render_li(tarefa, pode_reverter=False))

    # Alterna estado
    tarefa.concluida = not tarefa.concluida
    tarefa.concluida_em = datetime.now() if tarefa.concluida else None
    db.commit()

    return HTMLResponse(_render_li(tarefa, pode_reverter))


@router.post("/rotinas/{tarefa_id}/excluir", response_class=HTMLResponse)
async def excluir_tarefa(
    tarefa_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if usuario.perfil != PerfilUsuario.coordenador:
        return HTMLResponse("", status_code=403)

    tarefa = db.query(TarefaRotina).filter(TarefaRotina.id == tarefa_id).first()
    if tarefa:
        db.delete(tarefa)
        db.commit()

    # Retorna string vazia — o HTMX remove o <li> do DOM via outerHTML swap
    return HTMLResponse("")


# ---------------------------------------------------------------------------
# Contas Recorrentes
# ---------------------------------------------------------------------------

@router.post("/rotinas/recorrentes")
async def criar_recorrente(
    cliente_id: int = Form(...),
    descricao: str = Form(...),
    fornecedor: Optional[str] = Form(None),
    valor: Optional[str] = Form(None),
    dia_vencimento: int = Form(...),
    dias_antecedencia: int = Form(3),
    email_destino: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if usuario.perfil != PerfilUsuario.coordenador:
        return RedirectResponse(url="/rotinas", status_code=303)

    from decimal import Decimal, InvalidOperation
    valor_dec = None
    if valor:
        try:
            valor_dec = Decimal(str(valor).replace(",", "."))
        except InvalidOperation:
            pass

    db.add(ContaRecorrente(
        cliente_id=cliente_id,
        descricao=descricao,
        fornecedor=fornecedor or None,
        valor=valor_dec,
        dia_vencimento=max(1, min(31, dia_vencimento)),
        dias_antecedencia=max(1, dias_antecedencia),
        email_destino=email_destino,
    ))
    db.commit()
    return RedirectResponse(url="/rotinas", status_code=303)


@router.post("/rotinas/recorrentes/{rec_id}/excluir")
async def excluir_recorrente(
    rec_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if usuario.perfil != PerfilUsuario.coordenador:
        return RedirectResponse(url="/rotinas", status_code=303)
    rec = db.query(ContaRecorrente).filter(ContaRecorrente.id == rec_id).first()
    if rec:
        db.delete(rec)
        db.commit()
    return RedirectResponse(url="/rotinas", status_code=303)


@router.post("/rotinas/recorrentes/{rec_id}/toggle")
async def toggle_recorrente(
    rec_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    if usuario.perfil != PerfilUsuario.coordenador:
        return RedirectResponse(url="/rotinas", status_code=303)
    rec = db.query(ContaRecorrente).filter(ContaRecorrente.id == rec_id).first()
    if rec:
        rec.ativo = not rec.ativo
        db.commit()
    return RedirectResponse(url="/rotinas", status_code=303)


