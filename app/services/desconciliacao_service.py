"""Desfaz vínculos financeiros na transação do chamador, preservando extratos."""
from decimal import Decimal

from fastapi import HTTPException

from app.models import (
    Atendimento, ExtratoLinhaBancaria, MovimentacaoBancaria,
    StatusConciliacao, StatusContaPagar, StatusExtratoLinha,
    StatusMovimentacaoBancaria, StatusVendaCartao, TransferenciaCartao, VendaCartao,
)


def exigir_confirmacao(confirmado):
    if confirmado is not True:
        raise HTTPException(409, "Tem certeza? Confirme a ação para desfazer a conciliação.")


def _mesmo_cliente(registro, cliente_id):
    if registro.cliente_id != cliente_id:
        raise HTTPException(409, "Vínculo financeiro inconsistente entre clientes.")


def desconciliar_recebimento(db, atendimento):
    for mov in db.query(MovimentacaoBancaria).filter(
        MovimentacaoBancaria.conciliada_com_atendimento_id == atendimento.id,
    ).all():
        _mesmo_cliente(mov, atendimento.cliente_id)
        mov.conciliada_com_atendimento_id = None
        mov.status = StatusMovimentacaoBancaria.importada
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
    atendimento.status_conciliacao = StatusConciliacao.pendente
    atendimento.data_credito = None
    taxa = atendimento.taxa_cartao or Decimal("0")
    atendimento.valor_liquido = (atendimento.valor_servico * (1 - taxa / 100)).quantize(Decimal("0.01"))
    atendimento.valor_clinica = atendimento.valor_liquido - (atendimento.valor_medico or Decimal("0"))
    db.flush()


def desconciliar_pagamento(db, conta):
    for mov in db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.conta_pagar_id == conta.id).all():
        _mesmo_cliente(mov, conta.cliente_id)
        mov.conta_pagar_id = None
        mov.status = StatusMovimentacaoBancaria.importada
    for pagamento in conta.pagamentos_parciais:
        if pagamento.movimentacao:
            _mesmo_cliente(pagamento.movimentacao, conta.cliente_id)
            pagamento.movimentacao.conta_pagar_id = None
            pagamento.movimentacao.status = StatusMovimentacaoBancaria.importada
    for linha in db.query(ExtratoLinhaBancaria).filter(ExtratoLinhaBancaria.conta_pagar_id == conta.id).all():
        _mesmo_cliente(linha, conta.cliente_id)
        linha.conta_pagar_id = None
        linha.status = StatusExtratoLinha.importado
    conta.pagamentos_parciais.clear()
    conta.status = StatusContaPagar.pendente
    conta.data_pagamento = None
    db.flush()
