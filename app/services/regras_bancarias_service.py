"""Motor das regras de negócio bancárias (conciliação automática pela descrição do extrato).

Um único motor serve aos três momentos em que as regras rodam: importação de extrato,
movimentação manual e cadastro de regra (inclusive a aplicação retroativa ao histórico).

Garantias:
- Só movimentações não conciliadas, não arquivadas e sem vínculo financeiro são analisadas;
  conciliações existentes nunca são alteradas.
- Cada movimentação é conciliada dentro de um SAVEPOINT: se algo falhar nela, nada dela
  fica pela metade e as demais seguem.
- A busca percorre o histórico em lotes por ID (sem carregar tudo na memória) e trava as
  linhas do lote (FOR UPDATE) para que duas execuções simultâneas não concilie em dobro.
- Reexecutar é seguro: o que foi conciliado sai do filtro e a transferência é idempotente
  pelo identificador "regra-bancaria:<regra>:<movimento>".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import and_, exists, func, not_, or_
from sqlalchemy.orm import Session

from app.models import (
    Atendimento, CondicaoPagamento, ContaPagar, FormaPagamento, MovimentacaoBancaria, PagamentoParcialContaPagar,
    PlanoConta, RegraNegocioBancaria, StatusConciliacao, StatusContaPagar, StatusMovimentacaoBancaria, TipoContaPagar,
)

logger = logging.getLogger(__name__)

TAMANHO_LOTE = 500
ACOES = {"transferencia", "conciliar_receita", "conciliar_despesa"}
STATUS_CONTA_CONCILIAVEL = (StatusContaPagar.agendado, StatusContaPagar.pago_nao_conciliado)


@dataclass
class ResultadoRegras:
    analisados: int = 0
    conciliados: int = 0
    falhas: int = 0
    lotes: int = 0
    erros: list[str] = field(default_factory=list)

    @property
    def ignorados(self) -> int:
        return self.analisados - self.conciliados - self.falhas


# ------------------------------------------------------------------ baixas (compartilhadas com a manual)

def total_pago_conta(db: Session, conta_id: int) -> Decimal:
    total = db.query(func.coalesce(func.sum(PagamentoParcialContaPagar.valor), 0)).filter(
        PagamentoParcialContaPagar.conta_pagar_id == conta_id,
    ).scalar()
    return Decimal(str(total or 0))


def registrar_pagamento_conta(
    db: Session,
    conta: ContaPagar,
    valor: Decimal,
    data_pagamento: date,
    usuario_id: int | None,
    movimentacao_id: int | None = None,
    observacao: str | None = None,
) -> bool:
    valor = Decimal(str(valor))
    pago_antes = total_pago_conta(db, conta.id)  # lido uma vez: não depende de autoflush da sessão
    saldo = Decimal(str(conta.valor)) - pago_antes
    if valor <= 0 or valor > saldo:
        return False

    db.add(PagamentoParcialContaPagar(
        conta_pagar_id=conta.id,
        movimentacao_id=movimentacao_id,
        valor=valor,
        data_pagamento=data_pagamento,
        observacao=observacao,
        criado_por_id=usuario_id,
    ))
    novo_total = pago_antes + valor
    if novo_total >= Decimal(str(conta.valor)):
        conta.status = StatusContaPagar.pago
        conta.data_pagamento = data_pagamento
    else:
        conta.status = StatusContaPagar.agendado
        conta.data_pagamento = None
    return True


def vincular_recebimento(mov: MovimentacaoBancaria, at: Atendimento) -> None:
    """Concilia o recebimento do extrato com o lançamento (mesma baixa da conciliação manual)."""
    at.status_conciliacao = StatusConciliacao.conciliado
    at.data_credito = mov.data_movimento
    at.valor_liquido = mov.valor
    mov.status = StatusMovimentacaoBancaria.conciliada
    mov.conciliada_com_atendimento_id = at.id


def recalcular_status_conta(db: Session, conta: ContaPagar) -> None:
    """Depois de remover pagamentos: paga se quitada, senão volta para agendada."""
    pagos = db.query(PagamentoParcialContaPagar).filter(PagamentoParcialContaPagar.conta_pagar_id == conta.id)
    total = total_pago_conta(db, conta.id)
    if total >= Decimal(str(conta.valor)) and total > 0:
        conta.status = StatusContaPagar.pago
        conta.data_pagamento = max(p.data_pagamento for p in pagos)
    else:
        conta.status = StatusContaPagar.agendado
        conta.data_pagamento = None


class ConciliacaoAgrupadaInvalida(ValueError):
    """Seleção que não pode ser conciliada (soma diferente, item já conciliado, cliente errado...)."""


def _somar(valores) -> Decimal:
    return sum((Decimal(str(v)) for v in valores), Decimal("0")).quantize(Decimal("0.01"))


def conciliar_recebimentos_agrupados(db: Session, mov: MovimentacaoBancaria, lancamentos: list[Atendimento]) -> None:
    """Um crédito do extrato paga vários lançamentos a receber; a soma precisa bater exatamente."""
    if mov.sentido != "recebimento" or mov.status == StatusMovimentacaoBancaria.conciliada or mov.conciliada_com_atendimento_id:
        raise ConciliacaoAgrupadaInvalida("Movimentação indisponível para conciliação.")
    if len(lancamentos) < 2 or len({a.id for a in lancamentos}) != len(lancamentos):
        raise ConciliacaoAgrupadaInvalida("Selecione dois ou mais lançamentos diferentes.")
    for at in lancamentos:
        if at.cliente_id != mov.cliente_id or at.status_conciliacao == StatusConciliacao.conciliado or at.movimentacao_grupo_id:
            raise ConciliacaoAgrupadaInvalida(f"Lançamento #{at.id} indisponível.")
    if _somar(a.valor_servico for a in lancamentos) != _somar([mov.valor]):
        raise ConciliacaoAgrupadaInvalida("A soma dos lançamentos não bate com o valor do extrato.")
    for at in lancamentos:
        at.status_conciliacao = StatusConciliacao.conciliado
        at.data_credito = mov.data_movimento
        at.valor_liquido = at.valor_servico
        at.movimentacao_grupo_id = mov.id
    mov.status = StatusMovimentacaoBancaria.conciliada
    # O primeiro lançamento fica como vínculo principal: telas e relatórios que olham 1↔1 continuam valendo.
    mov.conciliada_com_atendimento_id = lancamentos[0].id


def conciliar_pagamentos_agrupados(db: Session, mov: MovimentacaoBancaria, contas: list[ContaPagar],
                                   usuario_id: int | None) -> None:
    """Um débito do extrato paga várias contas (quita o saldo de cada uma); a soma precisa bater."""
    if mov.sentido != "pagamento" or mov.status == StatusMovimentacaoBancaria.conciliada or mov.conta_pagar_id:
        raise ConciliacaoAgrupadaInvalida("Movimentação indisponível para conciliação.")
    if len(contas) < 2 or len({c.id for c in contas}) != len(contas):
        raise ConciliacaoAgrupadaInvalida("Selecione duas ou mais contas diferentes.")
    saldos = {}
    for conta in contas:
        if conta.cliente_id != mov.cliente_id or conta.status not in STATUS_CONTA_CONCILIAVEL:
            raise ConciliacaoAgrupadaInvalida(f"Conta #{conta.id} indisponível.")
        saldos[conta.id] = Decimal(str(conta.valor)) - total_pago_conta(db, conta.id)
        if saldos[conta.id] <= 0:
            raise ConciliacaoAgrupadaInvalida(f"Conta #{conta.id} já está quitada.")
    if _somar(saldos.values()) != _somar([mov.valor]):
        raise ConciliacaoAgrupadaInvalida("A soma das contas não bate com o valor do extrato.")
    for conta in contas:
        registrar_pagamento_conta(db, conta, saldos[conta.id], mov.data_movimento, usuario_id, movimentacao_id=mov.id,
                                  observacao="Pagamento conciliado em grupo com movimentação bancária")
    mov.status = StatusMovimentacaoBancaria.conciliada
    mov.conta_pagar_id = contas[0].id


# ------------------------------------------------------------------ seleção

def filtro_movimentos_elegiveis(cliente_id: int):
    """Movimentações que uma regra pode conciliar: do cliente, pendentes, não arquivadas e sem vínculo."""
    return and_(
        MovimentacaoBancaria.cliente_id == cliente_id,
        MovimentacaoBancaria.deleted_at.is_(None),
        MovimentacaoBancaria.status != StatusMovimentacaoBancaria.conciliada,
        MovimentacaoBancaria.arquivado_conciliacao_banco.is_(False),
        MovimentacaoBancaria.conciliada_com_atendimento_id.is_(None),
        MovimentacaoBancaria.conta_pagar_id.is_(None),
        MovimentacaoBancaria.transferencia_cartao_id.is_(None),
        # Compras da fatura do cartão (Contas a Pagar → cartão) têm conciliação própria.
        not_(and_(
            MovimentacaoBancaria.conta_bancaria_id.is_(None),
            MovimentacaoBancaria.tipo == "cartao",
            MovimentacaoBancaria.sentido == "pagamento",
        )),
    )


def regras_ativas(db: Session, cliente_id: int, ids: Optional[Iterable[int]] = None) -> list[RegraNegocioBancaria]:
    query = db.query(RegraNegocioBancaria).filter(
        RegraNegocioBancaria.cliente_id == cliente_id,
        RegraNegocioBancaria.ativo.is_(True),
        RegraNegocioBancaria.deleted_at.is_(None),
    )
    if ids is not None:
        query = query.filter(RegraNegocioBancaria.id.in_(list(ids)))
    return query.order_by(RegraNegocioBancaria.id).all()  # ordem fixa: a regra mais antiga tem prioridade


def regra_casa(regra: RegraNegocioBancaria, mov: MovimentacaoBancaria) -> bool:
    if regra.conta_origem_id and mov.conta_bancaria_id != regra.conta_origem_id:
        return False
    padrao = (regra.padrao_descricao or "").strip().casefold()
    return bool(padrao) and padrao in (mov.descricao or "").casefold()


# ------------------------------------------------------------------ ações

def _conciliar_receita(db: Session, regra: RegraNegocioBancaria, mov: MovimentacaoBancaria) -> bool:
    if mov.sentido != "recebimento" or not regra.plano_conta_id:
        return False
    ja_vinculado = exists().where(and_(
        MovimentacaoBancaria.conciliada_com_atendimento_id == Atendimento.id,
        MovimentacaoBancaria.id != mov.id,
    ))
    candidatos = db.query(Atendimento).filter(
        Atendimento.cliente_id == mov.cliente_id,
        Atendimento.plano_conta_id == regra.plano_conta_id,
        Atendimento.status_conciliacao == StatusConciliacao.pendente,
        Atendimento.arquivado_conciliacao_banco.is_(False),
        Atendimento.deleted_at.is_(None),
        Atendimento.valor_servico == mov.valor,
        ~ja_vinculado,
    ).limit(2).all()
    if len(candidatos) > 1:  # ambíguo: não arrisca
        return False
    if not candidatos:
        if not regra.criar_lancamento:
            return False
        candidatos = [_criar_recebimento(db, regra, mov)]
    vincular_recebimento(mov, candidatos[0])
    return True


def _observacao_automatica(regra: RegraNegocioBancaria, mov: MovimentacaoBancaria) -> str:
    return f"Criado pela regra bancária \"{regra.nome}\" a partir do extrato: {mov.descricao or ''}".strip()[:500]


def _criar_recebimento(db: Session, regra: RegraNegocioBancaria, mov: MovimentacaoBancaria) -> Atendimento:
    """Lançamento a receber criado pela regra (ex.: rendimento de aplicação), já com o plano da regra."""
    plano = db.get(PlanoConta, regra.plano_conta_id)
    at = Atendimento(
        cliente_id=mov.cliente_id, data_atendimento=mov.data_movimento, valor_servico=mov.valor,
        descricao_servico=plano.nome if plano else regra.nome, plano_conta_id=regra.plano_conta_id,
        condicao_pagamento=CondicaoPagamento.transferencia, forma_pagamento=FormaPagamento.transferencia,
        data_prevista_recebimento=mov.data_movimento, observacao=_observacao_automatica(regra, mov),
    )
    db.add(at)
    db.flush()
    return at


def _conciliar_despesa(db: Session, regra: RegraNegocioBancaria, mov: MovimentacaoBancaria) -> bool:
    if mov.sentido != "pagamento" or not regra.plano_conta_id:
        return False
    possiveis = db.query(ContaPagar).filter(
        ContaPagar.cliente_id == mov.cliente_id,
        ContaPagar.plano_conta_id == regra.plano_conta_id,
        ContaPagar.status.in_(STATUS_CONTA_CONCILIAVEL),
        ContaPagar.arquivado_conciliacao_banco.is_(False),
        ContaPagar.deleted_at.is_(None),
        ContaPagar.valor >= mov.valor,
    ).all()
    # Compara com o saldo em aberto (descontando pagamentos parciais), como a conciliação manual.
    candidatos = [c for c in possiveis if Decimal(str(c.valor)) - total_pago_conta(db, c.id) == Decimal(str(mov.valor))]
    if len(candidatos) > 1:
        return False
    if not candidatos:
        if not regra.criar_lancamento:
            return False
        candidatos = [_criar_despesa(db, regra, mov)]
    conta = candidatos[0]
    if not registrar_pagamento_conta(db, conta, mov.valor, mov.data_movimento, None, movimentacao_id=mov.id,
                                     observacao=f"Conciliação automática: {regra.nome}"):
        return False
    mov.conta_pagar_id = conta.id
    mov.status = StatusMovimentacaoBancaria.conciliada
    return True


def _criar_despesa(db: Session, regra: RegraNegocioBancaria, mov: MovimentacaoBancaria) -> ContaPagar:
    """Conta a pagar criada pela regra (ex.: tarifa bancária), pronta para receber a baixa do extrato."""
    plano = db.get(PlanoConta, regra.plano_conta_id)
    conta = ContaPagar(
        cliente_id=mov.cliente_id, descricao=(mov.descricao or regra.nome)[:500], tipo=TipoContaPagar.pontual,
        valor=mov.valor, vencimento=mov.data_movimento, data_competencia=mov.data_movimento,
        plano_conta_id=regra.plano_conta_id, categoria_dre=plano.chave if plano else None,
        conta_bancaria_id=mov.conta_bancaria_id, status=StatusContaPagar.pago_nao_conciliado,
        observacao=_observacao_automatica(regra, mov),
    )
    db.add(conta)
    db.flush()
    return conta


def _transferir(db: Session, regra: RegraNegocioBancaria, mov: MovimentacaoBancaria) -> bool:
    if not regra.conta_destino_id or mov.sentido != "pagamento" or not mov.conta_bancaria_id:
        return False
    identificador = f"regra-bancaria:{regra.id}:{mov.id}"
    if db.query(MovimentacaoBancaria.id).filter(MovimentacaoBancaria.identificador_externo == identificador).first():
        mov.tipo = "transf_interna"
        mov.status = StatusMovimentacaoBancaria.conciliada
        return True
    mov.tipo = "transf_interna"
    mov.status = StatusMovimentacaoBancaria.conciliada
    db.add(MovimentacaoBancaria(
        cliente_id=mov.cliente_id, conta_bancaria_id=regra.conta_destino_id,
        identificador_externo=identificador, origem_manual=False,
        tipo="transf_interna", sentido="recebimento",
        data_movimento=mov.data_movimento, valor=mov.valor,
        descricao=f"Transferência automática: {regra.nome}",
        origem_arquivo="Regra de negócio bancária",
        status=StatusMovimentacaoBancaria.conciliada,
    ))
    return True


ACOES_REGRA = {
    "conciliar_receita": _conciliar_receita,
    "conciliar_despesa": _conciliar_despesa,
    "transferencia": _transferir,
}


def aplicar_em_movimento(db: Session, regras: list[RegraNegocioBancaria], mov: MovimentacaoBancaria) -> bool:
    """Aplica a primeira regra que casar e conseguir conciliar a movimentação."""
    for regra in regras:
        if regra_casa(regra, mov) and ACOES_REGRA.get(regra.acao, lambda *a: False)(db, regra, mov):
            return True
    return False


# ------------------------------------------------------------------ execução em lote

def aplicar_regras(
    db: Session,
    cliente_id: int,
    regras: Optional[list[RegraNegocioBancaria]] = None,
    *,
    tamanho_lote: int = TAMANHO_LOTE,
    confirmar_por_lote: bool = False,
) -> ResultadoRegras:
    """Executa as regras sobre todo o histórico elegível do cliente, em lotes.

    confirmar_por_lote=False mantém tudo na transação de quem chamou (importação/manual);
    True confirma cada lote, para a aplicação retroativa a grandes históricos.
    """
    resultado = ResultadoRegras()
    regras = regras_ativas(db, cliente_id) if regras is None else [r for r in regras if r.cliente_id == cliente_id]
    if not regras:
        return resultado
    ultimo_id = 0
    filtro = filtro_movimentos_elegiveis(cliente_id)
    while True:
        lote = (
            db.query(MovimentacaoBancaria)
            .filter(filtro, MovimentacaoBancaria.id > ultimo_id)
            .order_by(MovimentacaoBancaria.id)
            .limit(tamanho_lote)
            .with_for_update(skip_locked=True)
            .all()
        )
        if not lote:
            break
        resultado.lotes += 1
        for mov in lote:
            ultimo_id = mov.id
            resultado.analisados += 1
            try:
                with db.begin_nested():
                    if aplicar_em_movimento(db, regras, mov):
                        resultado.conciliados += 1
            except Exception as exc:  # um lançamento com problema não interrompe os demais
                resultado.falhas += 1
                resultado.erros.append(f"Movimentação #{mov.id}: {exc.__class__.__name__}")
                logger.exception("regra_bancaria_falhou", extra={"client_id": cliente_id, "movement_id": mov.id})
        if confirmar_por_lote:
            db.commit()  # o mapa de identidade é fraco: o lote já processado sai da memória
        else:
            db.flush()
    return resultado
