"""Desfaz vínculos financeiros na transação do chamador, preservando extratos."""
from decimal import Decimal

from fastapi import HTTPException

from sqlalchemy import or_

from app.models import (
    Atendimento, ExtratoLinhaBancaria, MovimentacaoBancaria, PagamentoParcialContaPagar,
    StatusConciliacao, StatusContaPagar, StatusExtratoLinha,
    StatusMovimentacaoBancaria, StatusVendaCartao, TransferenciaCartao, VendaCartao,
)
from app.errors import erro


def exigir_confirmacao(confirmado):
    if confirmado is not True:
        raise erro("FLIC-CON-010")


def _mesmo_cliente(registro, cliente_id):
    if registro.cliente_id != cliente_id:
        raise erro("FLIC-CON-011")


def _reabrir_recebimento(atendimento):
    atendimento.status_conciliacao = StatusConciliacao.pendente
    atendimento.data_credito = None
    atendimento.movimentacao_grupo_id = None
    taxa = atendimento.taxa_cartao or Decimal("0")
    atendimento.valor_liquido = (atendimento.valor_servico * (1 - taxa / 100)).quantize(Decimal("0.01"))
    atendimento.valor_clinica = atendimento.valor_liquido - (atendimento.valor_medico or Decimal("0"))


def desfazer_movimento_recebimento(db, mov):
    """Solta o crédito do extrato e reabre todos os lançamentos que ele pagou (inclusive o grupo).

    Se o lançamento foi pago por vários créditos, os outros créditos também voltam a ficar pendentes.
    """
    lancamentos = db.query(Atendimento).filter(or_(
        Atendimento.movimentacao_grupo_id == mov.id, Atendimento.id == mov.conciliada_com_atendimento_id,
    )).all()
    for at in lancamentos:
        _mesmo_cliente(at, mov.cliente_id)
        _reabrir_recebimento(at)
    if lancamentos:
        for outro in db.query(MovimentacaoBancaria).filter(
            MovimentacaoBancaria.conciliada_com_atendimento_id.in_([a.id for a in lancamentos]),
            MovimentacaoBancaria.id != mov.id,
        ).all():
            _mesmo_cliente(outro, mov.cliente_id)
            outro.conciliada_com_atendimento_id = None
            outro.status = StatusMovimentacaoBancaria.importada
    mov.conciliada_com_atendimento_id = None
    mov.status = StatusMovimentacaoBancaria.importada


def desconciliar_recebimento(db, atendimento):
    for mov in db.query(MovimentacaoBancaria).filter(or_(
        MovimentacaoBancaria.conciliada_com_atendimento_id == atendimento.id,
        MovimentacaoBancaria.id == atendimento.movimentacao_grupo_id,
    )).all():
        _mesmo_cliente(mov, atendimento.cliente_id)
        desfazer_movimento_recebimento(db, mov)
    vendas = db.query(VendaCartao).filter(VendaCartao.atendimento_id == atendimento.id).all()
    for venda in vendas:
        _mesmo_cliente(venda, atendimento.cliente_id)
        if venda.lote_id:
            lote = db.get(TransferenciaCartao, venda.lote_id)
            _mesmo_cliente(lote, atendimento.cliente_id)
            for mov in db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.transferencia_cartao_id == lote.id).all():
                _mesmo_cliente(mov, atendimento.cliente_id)
                mov.transferencia_cartao_id = None
                mov.status = StatusMovimentacaoBancaria.importada
            for linha in db.query(ExtratoLinhaBancaria).filter(ExtratoLinhaBancaria.transferencia_id == lote.id).all():
                _mesmo_cliente(linha, atendimento.cliente_id)
                linha.transferencia_id = None
                linha.status = StatusExtratoLinha.importado
            for outra in db.query(VendaCartao).filter(VendaCartao.lote_id == lote.id).all():
                _mesmo_cliente(outra, atendimento.cliente_id)
                outra.lote_id = None
                outra.status = StatusVendaCartao.conciliado if outra.atendimento_id else StatusVendaCartao.pendente
                if outra.atendimento_id:
                    recebimento = db.get(Atendimento, outra.atendimento_id)
                    _mesmo_cliente(recebimento, atendimento.cliente_id)
                    recebimento.data_credito = None
            db.flush()
            db.delete(lote)
        venda.atendimento_id = None
        venda.status = StatusVendaCartao.pendente
    _reabrir_recebimento(atendimento)
    db.flush()


def desfazer_movimento_pagamento(db, mov, exceto_conta_id=None):
    """Remove os pagamentos feitos por este débito em todas as contas do grupo e recalcula cada uma."""
    from app.models import ContaPagar
    from app.services.regras_bancarias_service import recalcular_status_conta
    pagamentos = db.query(PagamentoParcialContaPagar).filter(PagamentoParcialContaPagar.movimentacao_id == mov.id).all()
    afetadas = {p.conta_pagar_id for p in pagamentos} - {exceto_conta_id}
    for pagamento in pagamentos:
        if pagamento.conta_pagar_id != exceto_conta_id:
            db.delete(pagamento)
    db.flush()
    for conta in db.query(ContaPagar).filter(ContaPagar.id.in_(afetadas)).all() if afetadas else []:
        _mesmo_cliente(conta, mov.cliente_id)
        recalcular_status_conta(db, conta)
    mov.conta_pagar_id = None
    mov.status = StatusMovimentacaoBancaria.importada


def desconciliar_pagamento(db, conta):
    for mov in db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.conta_pagar_id == conta.id).all():
        _mesmo_cliente(mov, conta.cliente_id)
        mov.conta_pagar_id = None
        mov.status = StatusMovimentacaoBancaria.importada
    for pagamento in conta.pagamentos_parciais:
        if pagamento.movimentacao:
            _mesmo_cliente(pagamento.movimentacao, conta.cliente_id)
            # Se o débito também pagou outras contas (grupo), elas são reabertas junto.
            desfazer_movimento_pagamento(db, pagamento.movimentacao, exceto_conta_id=conta.id)
    for linha in db.query(ExtratoLinhaBancaria).filter(ExtratoLinhaBancaria.conta_pagar_id == conta.id).all():
        _mesmo_cliente(linha, conta.cliente_id)
        linha.conta_pagar_id = None
        linha.status = StatusExtratoLinha.importado
    conta.pagamentos_parciais.clear()
    conta.status = StatusContaPagar.pendente
    conta.data_pagamento = None
    db.flush()
