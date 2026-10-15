"""Regras do gestor de tarefas: visibilidade, permissões, módulos e links."""
import calendar
from datetime import date, timedelta
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.auth import tem_acesso_geral
from app.models import ClienteBPO, Tarefa, Usuario

# Módulos que uma tarefa de cliente pode apontar: chave -> (rótulo, caminho)
MODULOS_TAREFA: dict[str, tuple[str, str]] = {
    "lancamentos": ("Contas a receber — Lançamentos", "/lancamentos"),
    "lancamentos_novo": ("Contas a receber — Incluir", "/lancamentos/novo"),
    "conciliacao_cartao": ("Conciliação cartão", "/conciliacao"),
    "conciliacao_banco": ("Conciliação banco", "/conciliacao/banco"),
    "importacoes": ("Importações", "/importacoes"),
    "contas_pagar": ("Contas a pagar — Lançamentos", "/contas-pagar"),
    "contas_pagar_novo": ("Contas a pagar — Incluir", "/contas-pagar/novo"),
    "aprovacao": ("Contas a pagar — Aprovação", "/fechamento"),
    "fechamento_mensal": ("Fechamento mensal", "/fechamento/mensal"),
    "rotinas": ("Rotinas", "/rotinas"),
    "gestao_receitas": ("Gestão — Receitas", "/gestao/receitas"),
    "gestao_despesas": ("Gestão — Despesas", "/gestao/despesas"),
    "gestao_orcamento": ("Gestão — Orçamento", "/gestao/orcamento"),
    "gestao_dre": ("Gestão — DRE", "/gestao/dre"),
}


def eh_admin(usuario: Usuario) -> bool:
    """Admin cria tarefas para qualquer pessoa da equipe e vê todas as tarefas."""
    return tem_acesso_geral(usuario)


def link_interno(valor: Optional[str]) -> bool:
    return bool(valor) and valor.startswith("/") and not valor.startswith("//") and "\\" not in valor


def normalizar_link(valor: Optional[str]) -> Optional[str]:
    """Aceita caminho interno ("/contas-pagar") ou URL http/https; rejeita o resto."""
    valor = (valor or "").strip()
    if not valor:
        return None
    if len(valor) > 500:
        raise ValueError("Link muito longo.")
    if link_interno(valor):
        return valor
    parsed = urlparse(valor)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return valor
    raise ValueError("Link inválido. Use um endereço http(s) ou um caminho do sistema iniciado por /.")


def clientes_permitidos(db: Session, usuario: Usuario) -> list[ClienteBPO]:
    query = db.query(ClienteBPO).filter(ClienteBPO.ativo.is_(True), ClienteBPO.deleted_at.is_(None))
    if not tem_acesso_geral(usuario):
        query = query.filter(ClienteBPO.funcionario_id == usuario.id)
    return query.order_by(ClienteBPO.nome).all()


def tarefas_visiveis(db: Session, usuario: Usuario):
    query = db.query(Tarefa).options(
        joinedload(Tarefa.cliente), joinedload(Tarefa.responsavel),
    ).filter(Tarefa.deleted_at.is_(None))
    if not eh_admin(usuario):
        query = query.filter(or_(Tarefa.responsavel_id == usuario.id, Tarefa.criado_por_id == usuario.id))
    return query


def ordenar(query):
    # Pendentes primeiro, prazos mais próximos antes, sem prazo por último.
    return query.order_by(
        Tarefa.concluida.asc(), Tarefa.prazo.is_(None), Tarefa.prazo.asc(), Tarefa.id.desc(),
    )


def pendentes_pessoais(db: Session, usuario: Usuario) -> list[Tarefa]:
    """Tarefas sem cliente atribuídas ao usuário — exibidas no painel geral."""
    return ordenar(tarefas_visiveis(db, usuario).filter(
        Tarefa.responsavel_id == usuario.id,
        Tarefa.cliente_id.is_(None),
        Tarefa.concluida.is_(False),
    )).all()


def pendentes_do_cliente(db: Session, usuario: Usuario, cliente_id: int) -> list[Tarefa]:
    """Tarefas pendentes do cliente — exibidas ao entrar no cliente."""
    query = tarefas_visiveis(db, usuario).filter(
        Tarefa.cliente_id == cliente_id, Tarefa.concluida.is_(False),
    )
    return ordenar(query).all()


MESES_PT = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
            "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")


def mes_referencia(valor: Optional[str], hoje: Optional[date] = None) -> date:
    """Converte "AAAA-MM" no primeiro dia do mês; inválido ou vazio vira o mês atual."""
    try:
        ano, mes = (int(p) for p in (valor or "").split("-"))
        return date(ano, mes, 1)
    except ValueError:
        return (hoje or date.today()).replace(day=1)


def montar_calendario(query, referencia: date, hoje: Optional[date] = None) -> dict:
    """Grade mensal (domingo a sábado) com as tarefas posicionadas no dia do prazo."""
    hoje = hoje or date.today()
    semanas = calendar.Calendar(firstweekday=6).monthdatescalendar(referencia.year, referencia.month)
    inicio, fim = semanas[0][0], semanas[-1][-1]
    por_dia: dict[date, list[Tarefa]] = {}
    for tarefa in ordenar(query.filter(Tarefa.prazo >= inicio, Tarefa.prazo <= fim)).all():
        por_dia.setdefault(tarefa.prazo, []).append(tarefa)
    anterior = (referencia - timedelta(days=1)).replace(day=1)
    proximo = (referencia + timedelta(days=32)).replace(day=1)
    return {
        "titulo": f"{MESES_PT[referencia.month - 1]} de {referencia.year}",
        "anterior": anterior.strftime("%Y-%m"),
        "proximo": proximo.strftime("%Y-%m"),
        "atual": hoje.strftime("%Y-%m"),
        "semanas": [[{
            "data": dia,
            "no_mes": dia.month == referencia.month,
            "hoje": dia == hoje,
            "tarefas": por_dia.get(dia, []),
        } for dia in semana] for semana in semanas],
    }


def do_usuario(db: Session, usuario: Usuario):
    """Tarefas em que o usuário é o responsável (pessoais e de clientes)."""
    return tarefas_visiveis(db, usuario).filter(Tarefa.responsavel_id == usuario.id)


def contexto_minhas_tarefas(db: Session, usuario: Usuario, visao: Optional[str], mes: Optional[str]) -> dict:
    """Dados da seção "Minhas tarefas" (painel e dashboard geral) em lista ou calendário."""
    visao = "calendario" if visao == "calendario" else "lista"
    hoje = date.today()
    return {
        "visao_tarefas": visao,
        "tarefas_pessoais": pendentes_pessoais(db, usuario) if visao == "lista" else [],
        "calendario_tarefas": (
            montar_calendario(do_usuario(db, usuario), mes_referencia(mes, hoje), hoje)
            if visao == "calendario" else None
        ),
        "eh_admin": eh_admin(usuario),
        "modulos": MODULOS_TAREFA,
        "hoje": hoje,
    }


def pendentes_por_cliente(db: Session, usuario: Usuario, ids_clientes: list[int]) -> dict[int, int]:
    """Quantidade de tarefas pendentes do usuário em cada cliente (selo no painel geral)."""
    if not ids_clientes:
        return {}
    linhas = db.query(Tarefa.cliente_id, func.count(Tarefa.id)).filter(
        Tarefa.deleted_at.is_(None), Tarefa.concluida.is_(False),
        Tarefa.responsavel_id == usuario.id, Tarefa.cliente_id.in_(ids_clientes),
    ).group_by(Tarefa.cliente_id).all()
    return dict(linhas)


def pode_editar(usuario: Usuario, tarefa: Tarefa) -> bool:
    return eh_admin(usuario) or tarefa.criado_por_id == usuario.id


def pode_concluir(usuario: Usuario, tarefa: Tarefa) -> bool:
    return eh_admin(usuario) or tarefa.responsavel_id == usuario.id


def atrasada(tarefa: Tarefa, hoje: Optional[date] = None) -> bool:
    return bool(tarefa.prazo and not tarefa.concluida and tarefa.prazo < (hoje or date.today()))
