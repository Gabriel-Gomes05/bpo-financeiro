from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
    Atendimento, ClienteBPO, ContaPagar,
    FechamentoDiario, StatusConciliacao, StatusContaPagar
)


def calcular_fechamento(db: Session, cliente_id: int, data: date, saldo_conta: Decimal) -> dict:
    """
    Calcula totais do dia e retorna um dicionário com os valores e texto para o cliente.
    Não salva no banco — apenas calcula.
    """
    # Receitas: atendimentos conciliados com data_credito = data
    receitas = db.query(Atendimento).filter(
        Atendimento.cliente_id == cliente_id,
        Atendimento.data_credito == data,
        Atendimento.status_conciliacao == StatusConciliacao.conciliado,
    ).all()
    total_receitas = sum(a.valor_liquido or a.valor_servico for a in receitas)

    # Despesas: contas pagas neste dia
    despesas = db.query(ContaPagar).filter(
        ContaPagar.cliente_id == cliente_id,
        ContaPagar.data_pagamento == data,
        ContaPagar.status == StatusContaPagar.pago,
    ).all()
    total_despesas = sum(d.valor for d in despesas)

    # Contas pendentes para alertar
    contas_pendentes = db.query(ContaPagar).filter(
        ContaPagar.cliente_id == cliente_id,
        ContaPagar.vencimento <= data,
        ContaPagar.status == StatusContaPagar.pendente,
    ).all()
    total_pendente = sum(c.valor for c in contas_pendentes)

    saldo_final = Decimal(str(saldo_conta)) - total_pendente + total_receitas

    return {
        "total_receitas_dia": total_receitas,
        "total_despesas_dia": total_despesas,
        "saldo_conta": Decimal(str(saldo_conta)),
        "saldo_provisorio_final": saldo_final,
        "receitas": receitas,
        "despesas": despesas,
        "contas_pendentes": contas_pendentes,
        "total_pendente": total_pendente,
    }


def gerar_texto_cliente(cliente: ClienteBPO, data: date, dados: dict, observacao: str = "") -> str:
    """Gera o texto formatado para enviar ao cliente via WhatsApp/e-mail."""

    def fmt(valor):
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    linhas = [
        f"📊 *Fechamento Diário — {data.strftime('%d/%m/%Y')}*",
        f"🏥 *{cliente.nome}*",
        "",
        f"💰 *Receitas do dia:* {fmt(dados['total_receitas_dia'])}",
        f"💸 *Despesas pagas:* {fmt(dados['total_despesas_dia'])}",
        f"⏳ *Contas pendentes:* {fmt(dados['total_pendente'])}",
        "",
        f"🏦 *Saldo atual em conta:* {fmt(dados['saldo_conta'])}",
        f"📈 *Saldo provisório final:* {fmt(dados['saldo_provisorio_final'])}",
    ]

    if observacao:
        linhas += ["", f"📝 *Obs:* {observacao}"]

    if dados["contas_pendentes"]:
        linhas += ["", "⚠️ *Contas a vencer/vencidas:*"]
        for c in dados["contas_pendentes"][:5]:  # máximo 5 no texto
            linhas.append(f"  • {c.descricao}: {fmt(c.valor)} ({c.vencimento.strftime('%d/%m')})")

    return "\n".join(linhas)


def salvar_fechamento(
    db: Session,
    cliente_id: int,
    data: date,
    dados: dict,
    observacao: str,
    gerado_por_id: int,
) -> FechamentoDiario:
    """Persiste o fechamento no banco. Substitui se já existir para o mesmo dia."""
    existente = db.query(FechamentoDiario).filter(
        FechamentoDiario.cliente_id == cliente_id,
        FechamentoDiario.data == data,
    ).first()

    if existente:
        fechamento = existente
    else:
        fechamento = FechamentoDiario(cliente_id=cliente_id, data=data)
        db.add(fechamento)

    fechamento.total_receitas_dia = dados["total_receitas_dia"]
    fechamento.total_despesas_dia = dados["total_despesas_dia"]
    fechamento.saldo_conta = dados["saldo_conta"]
    fechamento.saldo_provisorio_final = dados["saldo_provisorio_final"]
    fechamento.observacao = observacao
    fechamento.gerado_por_id = gerado_por_id
    db.commit()
    db.refresh(fechamento)
    return fechamento
