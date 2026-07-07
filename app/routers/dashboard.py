from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.jinja import templates
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.database import get_db
from app.models import (
    ClienteBPO, ContaPagar, ContaRecorrente, DivergenciaConciliacao,
    StatusContaPagar, TarefaRotina, Usuario, PerfilUsuario,
)
from app.services.alertas_service import _proximo_vencimento

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    hoje = date.today()

    # Resolve cliente ativo do cookie
    cliente_ativo_id: int | None = None
    raw = request.cookies.get("cliente_ativo", "")
    if raw:
        try:
            cliente_ativo_id = int(raw)
        except ValueError:
            pass

    if usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor):
        contexto = _dashboard_coordenador(db, hoje, cliente_ativo_id)
    else:
        contexto = _dashboard_funcionario(db, hoje, usuario, cliente_ativo_id)

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "usuario": usuario, "hoje": hoje, **contexto},
    )


def _alertas_recorrentes(db: Session, hoje: date, ids_clientes: list) -> list:
    """Retorna contas recorrentes cujo vencimento está dentro da janela de aviso."""
    if not ids_clientes:
        return []
    contas = db.query(ContaRecorrente).filter(
        ContaRecorrente.cliente_id.in_(ids_clientes),
        ContaRecorrente.ativo == True,
    ).all()

    alertas = []
    for conta in contas:
        vencimento = _proximo_vencimento(conta.dia_vencimento, hoje)
        alerta_a_partir = vencimento - timedelta(days=conta.dias_antecedencia)
        if alerta_a_partir <= hoje <= vencimento:
            dias = (vencimento - hoje).days
            alertas.append({
                "conta": conta,
                "vencimento": vencimento,
                "dias_restantes": dias,
                "urgente": dias <= 2,
            })

    return sorted(alertas, key=lambda x: x["dias_restantes"])


def _dashboard_coordenador(db: Session, hoje: date, cliente_ativo_id: int | None = None) -> dict:
    # ── Visão focada num cliente específico ──────────────────────────
    if cliente_ativo_id:
        cliente_foco = db.query(ClienteBPO).filter(
            ClienteBPO.id == cliente_ativo_id, ClienteBPO.ativo == True
        ).first()
        if cliente_foco:
            contas_vencendo = db.query(ContaPagar).filter(
                ContaPagar.cliente_id == cliente_ativo_id,
                ContaPagar.vencimento <= hoje,
                ContaPagar.status == StatusContaPagar.pendente,
            ).order_by(ContaPagar.vencimento.asc()).all()

            total_divergencias = db.query(DivergenciaConciliacao).filter(
                DivergenciaConciliacao.cliente_id == cliente_ativo_id,
                DivergenciaConciliacao.resolvida == False,
            ).count()

            tarefas_hoje = db.query(TarefaRotina).filter(
                TarefaRotina.cliente_id == cliente_ativo_id,
                TarefaRotina.data == hoje,
            ).all()
            tarefas_concluidas = sum(1 for t in tarefas_hoje if t.concluida)

            alertas_recorrentes = _alertas_recorrentes(db, hoje, [cliente_ativo_id])

            return {
                "modo": "foco",
                "cliente_foco": cliente_foco,
                "cliente_ativo_id": cliente_ativo_id,
                "contas_vencendo": contas_vencendo,
                "total_vencendo": len(contas_vencendo),
                "total_divergencias": total_divergencias,
                "total_tarefas": len(tarefas_hoje),
                "tarefas_concluidas": tarefas_concluidas,
                "tarefas_pendentes": len(tarefas_hoje) - tarefas_concluidas,
                "alertas_recorrentes": alertas_recorrentes,
                "funcionarios": [],
                "resumo_clientes": [],
            }

    # ── Visão geral (sem cliente selecionado) ────────────────────────
    total_clientes = db.query(ClienteBPO).filter(ClienteBPO.ativo == True).count()
    total_tarefas  = db.query(TarefaRotina).filter(TarefaRotina.data == hoje).count()
    total_vencendo = db.query(ContaPagar).filter(
        ContaPagar.vencimento <= hoje, ContaPagar.status == StatusContaPagar.pendente,
    ).count()
    total_divergencias = db.query(DivergenciaConciliacao).filter(
        DivergenciaConciliacao.resolvida == False,
    ).count()

    funcionarios_db = db.query(Usuario).filter(
        Usuario.ativo == True,
        Usuario.perfil.in_([PerfilUsuario.funcionario, PerfilUsuario.editor]),
    ).all()

    funcionarios = []
    for func in funcionarios_db:
        clientes_ativos = db.query(ClienteBPO).filter(
            ClienteBPO.funcionario_id == func.id, ClienteBPO.ativo == True,
        ).all()
        ids_clientes = [c.id for c in clientes_ativos]

        tarefas_hoje = db.query(TarefaRotina).filter(
            TarefaRotina.funcionario_id == func.id, TarefaRotina.data == hoje,
        ).all()

        vencendo = db.query(ContaPagar).filter(
            ContaPagar.cliente_id.in_(ids_clientes),
            ContaPagar.vencimento <= hoje,
            ContaPagar.status == StatusContaPagar.pendente,
        ).count() if ids_clientes else 0

        divergencias = db.query(DivergenciaConciliacao).filter(
            DivergenciaConciliacao.cliente_id.in_(ids_clientes),
            DivergenciaConciliacao.resolvida == False,
        ).count() if ids_clientes else 0

        concluidas = sum(1 for t in tarefas_hoje if t.concluida)
        funcionarios.append({
            "nome": func.nome,
            "clientes_ativos": clientes_ativos,
            "total_tarefas": len(tarefas_hoje),
            "tarefas_concluidas": concluidas,
            "tarefas_pendentes": len(tarefas_hoje) - concluidas,
            "vencendo": vencendo,
            "divergencias": divergencias,
        })

    todos_ids = [c.id for c in db.query(ClienteBPO).filter(ClienteBPO.ativo == True).all()]
    alertas_recorrentes = _alertas_recorrentes(db, hoje, todos_ids)

    return {
        "modo": "geral",
        "cliente_foco": None,
        "cliente_ativo_id": None,
        "total_clientes": total_clientes,
        "total_tarefas": total_tarefas,
        "total_vencendo": total_vencendo,
        "total_divergencias": total_divergencias,
        "funcionarios": funcionarios,
        "alertas_recorrentes": alertas_recorrentes,
        "contas_vencendo": [],
        "resumo_clientes": [],
    }


def _dashboard_funcionario(
    db: Session, hoje: date, usuario: Usuario, cliente_ativo_id: int | None = None
) -> dict:
    meus_clientes = db.query(ClienteBPO).filter(
        ClienteBPO.funcionario_id == usuario.id,
        ClienteBPO.ativo == True,
    ).all()
    ids_todos = [c.id for c in meus_clientes]

    # Filtra pelo cliente ativo se selecionado e pertence ao usuário
    if cliente_ativo_id and cliente_ativo_id in ids_todos:
        clientes_filtro = [c for c in meus_clientes if c.id == cliente_ativo_id]
        cliente_foco = clientes_filtro[0]
    else:
        clientes_filtro = meus_clientes
        cliente_foco = None

    ids_filtro = [c.id for c in clientes_filtro]

    tarefas_hoje = db.query(TarefaRotina).filter(
        TarefaRotina.funcionario_id == usuario.id,
        TarefaRotina.data == hoje,
        TarefaRotina.cliente_id.in_(ids_filtro),
    ).all()
    tarefas_concluidas = sum(1 for t in tarefas_hoje if t.concluida)

    # Contas vencendo — retorna objetos reais quando tem cliente em foco
    contas_vencendo_q = db.query(ContaPagar).filter(
        ContaPagar.cliente_id.in_(ids_filtro),
        ContaPagar.vencimento <= hoje,
        ContaPagar.status == StatusContaPagar.pendente,
    ).order_by(ContaPagar.vencimento.asc())

    contas_vencendo = contas_vencendo_q.all() if cliente_foco else []
    total_vencendo = len(contas_vencendo) if cliente_foco else contas_vencendo_q.count()

    total_divergencias = db.query(DivergenciaConciliacao).filter(
        DivergenciaConciliacao.cliente_id.in_(ids_filtro),
        DivergenciaConciliacao.resolvida == False,
    ).count()

    resumo_clientes = []
    for cliente in clientes_filtro:
        tarefas_cliente = [t for t in tarefas_hoje if t.cliente_id == cliente.id]
        conc_cliente = sum(1 for t in tarefas_cliente if t.concluida)

        vencendo = db.query(ContaPagar).filter(
            ContaPagar.cliente_id == cliente.id,
            ContaPagar.vencimento <= hoje,
            ContaPagar.status == StatusContaPagar.pendente,
        ).count()

        divergencias = db.query(DivergenciaConciliacao).filter(
            DivergenciaConciliacao.cliente_id == cliente.id,
            DivergenciaConciliacao.resolvida == False,
        ).count()

        resumo_clientes.append({
            "cliente": cliente,
            "total_tarefas": len(tarefas_cliente),
            "tarefas_concluidas": conc_cliente,
            "tarefas_pendentes": len(tarefas_cliente) - conc_cliente,
            "vencendo": vencendo,
            "divergencias": divergencias,
        })

    alertas_recorrentes = _alertas_recorrentes(db, hoje, ids_filtro)

    return {
        "meus_clientes": meus_clientes,
        "cliente_foco": cliente_foco,
        "cliente_ativo_id": cliente_ativo_id,
        "total_tarefas": len(tarefas_hoje),
        "tarefas_concluidas": tarefas_concluidas,
        "tarefas_pendentes": len(tarefas_hoje) - tarefas_concluidas,
        "total_vencendo": total_vencendo,
        "contas_vencendo": contas_vencendo,
        "total_divergencias": total_divergencias,
        "resumo_clientes": resumo_clientes,
        "alertas_recorrentes": alertas_recorrentes,
        "tarefas_hoje": tarefas_hoje,
    }
