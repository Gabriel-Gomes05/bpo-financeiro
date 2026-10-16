from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.database import get_db
from app.models import (
    Atendimento, ClienteBPO, ContaPagar, DivergenciaConciliacao,
    FechamentoDiario, StatusConciliacao, StatusContaPagar, Usuario, PerfilUsuario,
)
from app.services import tarefas_service

router = APIRouter()

STATUS_PAGAR_EM_ABERTO = [
    StatusContaPagar.pendente, StatusContaPagar.aguardando_aprovacao, StatusContaPagar.agendado,
]


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

    permitidos = db.query(ClienteBPO).filter(
        ClienteBPO.ativo.is_(True), ClienteBPO.deleted_at.is_(None),
    )
    if usuario.perfil not in (PerfilUsuario.coordenador, PerfilUsuario.editor):
        permitidos = permitidos.filter(ClienteBPO.funcionario_id == usuario.id)
    clientes = permitidos.order_by(ClienteBPO.nome).all()
    if cliente_ativo_id and cliente_ativo_id not in {c.id for c in clientes}:
        return RedirectResponse("/painel", status_code=303)

    if usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor):
        contexto = _dashboard_coordenador(db, hoje, cliente_ativo_id)
    else:
        contexto = _dashboard_funcionario(db, hoje, usuario, cliente_ativo_id)

    contexto.update(tarefas_service.contexto_minhas_tarefas(
        db, usuario, request.query_params.get("visao"), request.query_params.get("mes"),
    ))
    contexto["tarefas_cliente"] = (
        tarefas_service.pendentes_do_cliente(db, usuario, cliente_ativo_id) if cliente_ativo_id else []
    )

    contexto["medias"] = _medias_mensais(
        db, hoje, [cliente_ativo_id] if cliente_ativo_id else [c.id for c in clientes], 3,
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "usuario": usuario, "hoje": hoje, **contexto, "clientes": clientes},
    )


def _medias_mensais(db: Session, hoje: date, ids_clientes: list[int], meses: int) -> dict:
    fim = hoje.replace(day=1)
    indice = fim.year * 12 + fim.month - 1 - meses
    inicio = date(indice // 12, indice % 12 + 1, 1)
    recebido = db.query(func.sum(Atendimento.valor_liquido)).filter(
        Atendimento.cliente_id.in_(ids_clientes),
        Atendimento.status_conciliacao == StatusConciliacao.conciliado,
        Atendimento.data_credito >= inicio, Atendimento.data_credito < fim,
    ).scalar() or Decimal("0")
    pago = db.query(func.sum(ContaPagar.valor)).filter(
        ContaPagar.cliente_id.in_(ids_clientes), ContaPagar.status == StatusContaPagar.pago,
        ContaPagar.data_pagamento >= inicio, ContaPagar.data_pagamento < fim,
    ).scalar() or Decimal("0")
    return {
        "meses": meses, "inicio": inicio, "fim": fim - timedelta(days=1),
        "recebido": _brl(recebido / meses), "pago": _brl(pago / meses),
        "saldo": _brl((recebido - pago) / meses), "saldo_negativo": recebido < pago,
    }


AVISO_MAXIMO_DIAS = 30


def _alertas_recorrentes(db: Session, hoje: date, ids_clientes: list) -> list:
    """Contas a pagar recorrentes em aberto cujo vencimento está dentro da janela de aviso
    configurada no lançamento (aviso_dias_antes; padrão de 3 dias)."""
    if not ids_clientes:
        return []
    contas = db.query(ContaPagar).filter(
        ContaPagar.cliente_id.in_(ids_clientes),
        ContaPagar.recorrencia_grupo_id.isnot(None),
        ContaPagar.status.in_(STATUS_PAGAR_EM_ABERTO),
        ContaPagar.vencimento >= hoje,
        ContaPagar.vencimento <= hoje + timedelta(days=AVISO_MAXIMO_DIAS),
    ).all()

    alertas = []
    for conta in contas:
        vencimento = conta.vencimento
        aviso = conta.aviso_dias_antes if conta.aviso_dias_antes is not None else 3
        if vencimento - timedelta(days=aviso) <= hoje:
            dias = (vencimento - hoje).days
            alertas.append({
                "conta": conta,
                "vencimento": vencimento,
                "dias_restantes": dias,
                "urgente": dias <= 2,
            })

    return sorted(alertas, key=lambda x: x["dias_restantes"])


def _brl(v) -> str:
    return f"{float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _blocos_processo(db: Session, hoje: date, ids_clientes: list) -> list:
    """Resumo por módulo/processo (Contas a Receber, Contas a Pagar, Conciliação, Fechamento)."""
    if not ids_clientes:
        return []

    inicio_mes = hoje.replace(day=1)

    pendentes_receber = db.query(Atendimento).filter(
        Atendimento.cliente_id.in_(ids_clientes),
        Atendimento.status_conciliacao != StatusConciliacao.conciliado,
    ).count()
    recebido_mes = db.query(func.sum(Atendimento.valor_liquido)).filter(
        Atendimento.cliente_id.in_(ids_clientes),
        Atendimento.status_conciliacao == StatusConciliacao.conciliado,
        Atendimento.data_credito >= inicio_mes,
        Atendimento.data_credito <= hoje,
    ).scalar() or Decimal("0")

    vencendo_pagar = db.query(ContaPagar).filter(
        ContaPagar.cliente_id.in_(ids_clientes),
        ContaPagar.vencimento <= hoje,
        ContaPagar.status.in_(STATUS_PAGAR_EM_ABERTO),
    ).count()
    pago_mes = db.query(func.sum(ContaPagar.valor)).filter(
        ContaPagar.cliente_id.in_(ids_clientes),
        ContaPagar.status == StatusContaPagar.pago,
        ContaPagar.data_pagamento >= inicio_mes,
        ContaPagar.data_pagamento <= hoje,
    ).scalar() or Decimal("0")

    total_divergencias = db.query(DivergenciaConciliacao).filter(
        DivergenciaConciliacao.cliente_id.in_(ids_clientes),
        DivergenciaConciliacao.resolvida == False,
    ).count()

    total_clientes_escopo = len(ids_clientes)
    fechados_hoje = db.query(FechamentoDiario.cliente_id).filter(
        FechamentoDiario.cliente_id.in_(ids_clientes),
        FechamentoDiario.data == hoje,
    ).distinct().count()

    return [
        {
            "titulo": "Contas a Receber",
            "linha1": f"{pendentes_receber} pendente(s) de conciliação",
            "linha2": f"R$ {_brl(recebido_mes)} recebido no mês",
            "link": "/lancamentos",
        },
        {
            "titulo": "Contas a Pagar",
            "linha1": f"{vencendo_pagar} vencendo/vencida(s)",
            "linha2": f"R$ {_brl(pago_mes)} pago no mês",
            "link": "/contas-pagar",
        },
        {
            "titulo": "Conciliação",
            "linha1": f"{total_divergencias} divergência(s) aberta(s)",
            "linha2": "",
            "link": "/conciliacao/banco",
        },
        {
            "titulo": "Fechamento",
            "linha1": f"{fechados_hoje} de {total_clientes_escopo} cliente(s) fechado(s) hoje",
            "linha2": "",
            "link": "/fechamento",
        },
    ]


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
                ContaPagar.status.in_(STATUS_PAGAR_EM_ABERTO),
            ).order_by(ContaPagar.vencimento.asc()).all()

            total_divergencias = db.query(DivergenciaConciliacao).filter(
                DivergenciaConciliacao.cliente_id == cliente_ativo_id,
                DivergenciaConciliacao.resolvida == False,
            ).count()

            tarefas_hoje = tarefas_service.com_prazo_em(db, hoje, cliente_ids=[cliente_ativo_id])
            tarefas_concluidas = sum(1 for t in tarefas_hoje if t.concluida)

            alertas_recorrentes = _alertas_recorrentes(db, hoje, [cliente_ativo_id])
            blocos_processo = _blocos_processo(db, hoje, [cliente_ativo_id])

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
                "blocos_processo": blocos_processo,
                "funcionarios": [],
                "resumo_clientes": [],
            }

    # ── Visão geral (sem cliente selecionado) ────────────────────────
    total_clientes = db.query(ClienteBPO).filter(ClienteBPO.ativo == True).count()
    total_tarefas = len(tarefas_service.com_prazo_em(db, hoje))
    total_vencendo = db.query(ContaPagar).filter(
        ContaPagar.vencimento <= hoje, ContaPagar.status.in_(STATUS_PAGAR_EM_ABERTO),
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

        tarefas_hoje = tarefas_service.com_prazo_em(db, hoje, responsavel_id=func.id)

        vencendo = db.query(ContaPagar).filter(
            ContaPagar.cliente_id.in_(ids_clientes),
            ContaPagar.vencimento <= hoje,
            ContaPagar.status.in_(STATUS_PAGAR_EM_ABERTO),
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
    blocos_processo = _blocos_processo(db, hoje, todos_ids)

    return {
        "modo": "geral",
        "cliente_foco": None,
        "cliente_ativo_id": None,
        "total_clientes": total_clientes,
        "total_tarefas": total_tarefas,
        "total_vencendo": total_vencendo,
        "blocos_processo": blocos_processo,
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

    tarefas_hoje = tarefas_service.com_prazo_em(db, hoje, cliente_ids=ids_filtro, responsavel_id=usuario.id)
    tarefas_concluidas = sum(1 for t in tarefas_hoje if t.concluida)

    # Contas vencendo — retorna objetos reais quando tem cliente em foco
    contas_vencendo_q = db.query(ContaPagar).filter(
        ContaPagar.cliente_id.in_(ids_filtro),
        ContaPagar.vencimento <= hoje,
        ContaPagar.status.in_(STATUS_PAGAR_EM_ABERTO),
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
            ContaPagar.status.in_(STATUS_PAGAR_EM_ABERTO),
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
    blocos_processo = _blocos_processo(db, hoje, ids_filtro)

    return {
        "meus_clientes": meus_clientes,
        "cliente_foco": cliente_foco,
        "cliente_ativo_id": cliente_ativo_id,
        "blocos_processo": blocos_processo,
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
