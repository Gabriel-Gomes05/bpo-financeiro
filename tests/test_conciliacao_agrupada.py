"""Conciliação agrupada: um movimento do extrato com vários lançamentos, desde que a soma bata."""
import asyncio
import inspect
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    Atendimento, ClienteBPO, ContaBancaria, ContaPagar, FormaPagamento, MovimentacaoBancaria,
    PagamentoParcialContaPagar, PerfilUsuario, StatusConciliacao, StatusContaPagar, StatusMovimentacaoBancaria,
    TipoContaBancaria, Usuario,
)
from app.routers import conciliacao_banco
from app.services.desconciliacao_service import desconciliar_pagamento, desconciliar_recebimento

A, B = 1, 2


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(conciliacao_banco, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=1, nome="Coord", email="c@x.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            ClienteBPO(id=A, nome="A"), ClienteBPO(id=B, nome="B"),
        ])
        session.flush()
        session.add(ContaBancaria(id=10, cliente_id=A, nome="CC", tipo=TipoContaBancaria.bancaria))
        session.commit()
        yield session
    engine.dispose()


def chamar(funcao, **kwargs):
    params = {}
    for nome, param in inspect.signature(funcao).parameters.items():
        if param.default is not inspect.Parameter.empty:
            params[nome] = getattr(param.default, "default", param.default)
    params.update(kwargs)
    return asyncio.run(funcao(**params))


def mov(db, valor, sentido="recebimento", cliente=A):
    m = MovimentacaoBancaria(cliente_id=cliente, conta_bancaria_id=10 if cliente == A else None, tipo="pix_ted",
                             sentido=sentido, data_movimento=date(2026, 9, 5), valor=Decimal(valor), descricao="PIX CONVENIO")
    db.add(m)
    db.flush()
    return m


def lanc(db, valor, cliente=A, **kw):
    at = Atendimento(cliente_id=cliente, data_atendimento=date(2026, 9, 1), valor_servico=Decimal(valor),
                     condicao_pagamento="avista", forma_pagamento=FormaPagamento.pix, **kw)
    db.add(at)
    db.flush()
    return at


def conta(db, valor, status=StatusContaPagar.agendado, cliente=A):
    c = ContaPagar(cliente_id=cliente, descricao=f"Boleto {valor}", valor=Decimal(valor), vencimento=date(2026, 9, 5), status=status)
    db.add(c)
    db.flush()
    return c


def receber(db, m, ids, cliente=A):
    return chamar(conciliacao_banco.conciliar_movimentacao_selecionados, mov_id=m.id, cliente_id=cliente,
                  atendimento_ids=ids, db=db, usuario=db.get(Usuario, 1))


def pagar(db, m, ids, cliente=A):
    return chamar(conciliacao_banco.conciliar_saida_selecionadas, mov_id=m.id, cliente_id=cliente,
                  conta_ids=ids, db=db, usuario=db.get(Usuario, 1))


def novo(db, obj):
    db.expire_all()
    return db.get(type(obj), obj.id)


# ------------------------------------------------------------------ recebimentos

def test_um_credito_paga_varios_lancamentos(db):
    lancs = [lanc(db, v) for v in ("100", "150", "250")]
    m = mov(db, "500")
    db.commit()
    resposta = receber(db, m, [a.id for a in lancs])
    assert resposta.headers["location"].endswith("&agrupado=3")
    m = novo(db, m)
    assert m.status == StatusMovimentacaoBancaria.conciliada and m.conciliada_com_atendimento_id == lancs[0].id
    for at in lancs:
        at = novo(db, at)
        assert (at.status_conciliacao, at.movimentacao_grupo_id, at.data_credito) == (StatusConciliacao.conciliado, m.id, m.data_movimento)
        assert at.valor_liquido == at.valor_servico


@pytest.mark.parametrize("valores", [("100", "150"), ("100", "150", "300")])
def test_soma_diferente_nao_concilia(db, valores):
    lancs = [lanc(db, v) for v in valores]
    m = mov(db, "500")
    db.commit()
    assert "erro=agrupado_soma" in receber(db, m, [a.id for a in lancs]).headers["location"]
    assert novo(db, m).status == StatusMovimentacaoBancaria.importada
    assert all(novo(db, a).status_conciliacao == StatusConciliacao.pendente for a in lancs)


def test_lancamento_ja_conciliado_ou_de_outro_cliente_bloqueia_o_grupo(db):
    livre = lanc(db, "200")
    conciliado = lanc(db, "300", status_conciliacao=StatusConciliacao.conciliado)
    alheio = lanc(db, "300", cliente=B)
    m = mov(db, "500")
    db.commit()
    for outro in (conciliado, alheio):
        assert "erro=agrupado_soma" in receber(db, m, [livre.id, outro.id]).headers["location"]
    assert novo(db, livre).status_conciliacao == StatusConciliacao.pendente


def test_um_lancamento_so_mantem_o_comportamento_atual(db):
    at = lanc(db, "480")  # valor diferente é permitido na conciliação 1↔1, como antes
    m = mov(db, "500")
    db.commit()
    receber(db, m, [at.id])
    assert novo(db, m).conciliada_com_atendimento_id == at.id and novo(db, at).movimentacao_grupo_id is None


def test_desconciliar_um_lancamento_reabre_o_grupo_todo(db):
    lancs = [lanc(db, v) for v in ("200", "300")]
    m = mov(db, "500")
    db.commit()
    receber(db, m, [a.id for a in lancs])
    desconciliar_recebimento(db, novo(db, lancs[1]))
    db.commit()
    assert novo(db, m).status == StatusMovimentacaoBancaria.importada and novo(db, m).conciliada_com_atendimento_id is None
    for at in lancs:
        at = novo(db, at)
        assert (at.status_conciliacao, at.movimentacao_grupo_id, at.data_credito) == (StatusConciliacao.pendente, None, None)


def test_desvincular_o_credito_reabre_o_grupo_todo(db):
    lancs = [lanc(db, v) for v in ("200", "300")]
    m = mov(db, "500")
    db.commit()
    receber(db, m, [a.id for a in lancs])
    chamar(conciliacao_banco.desvincular_movimentacao_pix, mov_id=m.id, cliente_id=A, db=db, usuario=db.get(Usuario, 1))
    assert all(novo(db, a).status_conciliacao == StatusConciliacao.pendente for a in lancs)


def test_busca_mostra_lancamentos_menores_com_o_exato_primeiro(db):
    menor, exato, maior = lanc(db, "120"), lanc(db, "500"), lanc(db, "700")
    m = mov(db, "500")
    db.commit()
    achados = [a.id for a in conciliacao_banco._buscar_no_sistema(db, A, m, None)]
    assert achados[0] == exato.id and menor.id in achados and maior.id not in achados


# ------------------------------------------------------------------ pagamentos

def test_um_debito_paga_varias_contas(db):
    c1, c2 = conta(db, "300"), conta(db, "200", status=StatusContaPagar.pago_nao_conciliado)
    m = mov(db, "500", sentido="pagamento")
    db.commit()
    assert pagar(db, m, [c1.id, c2.id]).headers["location"].endswith("&agrupado=2")
    assert novo(db, m).status == StatusMovimentacaoBancaria.conciliada and novo(db, m).conta_pagar_id == c1.id
    for c in (c1, c2):
        assert novo(db, c).status == StatusContaPagar.pago and novo(db, c).data_pagamento == date(2026, 9, 5)
    assert sorted(p.valor for p in db.query(PagamentoParcialContaPagar).filter_by(movimentacao_id=m.id)) == [Decimal("200.00"), Decimal("300.00")]


def test_conta_parcialmente_paga_entra_pelo_saldo(db):
    c1, c2 = conta(db, "300"), conta(db, "300")
    db.add(PagamentoParcialContaPagar(conta_pagar_id=c1.id, valor=Decimal("100"), data_pagamento=date(2026, 9, 1)))
    m = mov(db, "500", sentido="pagamento")  # saldo 200 + 300
    db.commit()
    pagar(db, m, [c1.id, c2.id])
    assert novo(db, c1).status == StatusContaPagar.pago and novo(db, c2).status == StatusContaPagar.pago
    assert db.query(PagamentoParcialContaPagar).filter_by(conta_pagar_id=c1.id, movimentacao_id=m.id).one().valor == Decimal("200.00")


def test_soma_de_contas_diferente_nao_concilia(db):
    c1, c2 = conta(db, "300"), conta(db, "100")
    m = mov(db, "500", sentido="pagamento")
    db.commit()
    assert "erro=agrupado_soma" in pagar(db, m, [c1.id, c2.id]).headers["location"]
    assert db.query(PagamentoParcialContaPagar).count() == 0 and novo(db, m).status == StatusMovimentacaoBancaria.importada


def test_desvincular_debito_reabre_todas_as_contas(db):
    c1, c2 = conta(db, "300"), conta(db, "300")
    anterior = PagamentoParcialContaPagar(conta_pagar_id=c1.id, valor=Decimal("100"), data_pagamento=date(2026, 9, 1))
    db.add(anterior)
    m = mov(db, "500", sentido="pagamento")
    db.commit()
    pagar(db, m, [c1.id, c2.id])
    chamar(conciliacao_banco.desvincular_saida, mov_id=m.id, cliente_id=A, db=db, usuario=db.get(Usuario, 1))
    assert novo(db, m).status == StatusMovimentacaoBancaria.importada and novo(db, m).conta_pagar_id is None
    assert novo(db, c1).status == StatusContaPagar.agendado and novo(db, c2).status == StatusContaPagar.agendado
    assert [p.valor for p in db.query(PagamentoParcialContaPagar)] == [Decimal("100.00")]  # o pagamento anterior fica


def test_desconciliar_uma_conta_reabre_as_outras_do_mesmo_debito(db):
    c1, c2 = conta(db, "300"), conta(db, "200")
    m = mov(db, "500", sentido="pagamento")
    db.commit()
    pagar(db, m, [c1.id, c2.id])
    desconciliar_pagamento(db, novo(db, c1))
    db.commit()
    assert novo(db, m).status == StatusMovimentacaoBancaria.importada
    assert novo(db, c2).status == StatusContaPagar.agendado
    assert db.query(PagamentoParcialContaPagar).count() == 0


def test_uma_conta_so_mantem_o_pagamento_parcial(db):
    c = conta(db, "800")
    m = mov(db, "500", sentido="pagamento")
    db.commit()
    pagar(db, m, [c.id])
    assert novo(db, c).status == StatusContaPagar.agendado and novo(db, m).conta_pagar_id == c.id


# ------------------------------------------------------------------ sistema -> vários do banco

def lanc_varios(db, at, ids, cliente=A):
    return chamar(conciliacao_banco.conciliar_lancamento_movimentos, at_id=at.id, cliente_id=cliente,
                  mov_ids=ids, db=db, usuario=db.get(Usuario, 1))


def conta_varios(db, c, ids, cliente=A):
    return chamar(conciliacao_banco.conciliar_conta_movimentos, conta_id=c.id, cliente_id=cliente,
                  mov_ids=ids, db=db, usuario=db.get(Usuario, 1))


def test_um_lancamento_recebido_em_varios_creditos(db):
    at = lanc(db, "1000")
    m1, m2 = mov(db, "600"), mov(db, "400")
    db.commit()
    assert lanc_varios(db, at, [m1.id, m2.id]).headers["location"].endswith("&agrupado_banco=2")
    at = novo(db, at)
    assert at.status_conciliacao == StatusConciliacao.conciliado and at.valor_liquido == Decimal("1000.00")
    for m in (m1, m2):
        m = novo(db, m)
        assert m.status == StatusMovimentacaoBancaria.conciliada and m.conciliada_com_atendimento_id == at.id


def test_lancamento_com_creditos_que_nao_somam_nao_concilia(db):
    at = lanc(db, "1000")
    m1, m2, pagamento = mov(db, "600"), mov(db, "300"), mov(db, "400", sentido="pagamento")
    db.commit()
    assert "erro=agrupado_soma" in lanc_varios(db, at, [m1.id, m2.id]).headers["location"]
    assert "erro=agrupado_soma" in lanc_varios(db, at, [m1.id, pagamento.id]).headers["location"]
    assert novo(db, at).status_conciliacao == StatusConciliacao.pendente
    assert novo(db, m1).status == StatusMovimentacaoBancaria.importada


def test_desvincular_um_credito_solta_os_outros_do_mesmo_lancamento(db):
    at = lanc(db, "1000")
    m1, m2 = mov(db, "600"), mov(db, "400")
    db.commit()
    lanc_varios(db, at, [m1.id, m2.id])
    chamar(conciliacao_banco.desvincular_movimentacao_pix, mov_id=m1.id, cliente_id=A, db=db, usuario=db.get(Usuario, 1))
    assert novo(db, at).status_conciliacao == StatusConciliacao.pendente
    for m in (m1, m2):
        assert novo(db, m).status == StatusMovimentacaoBancaria.importada and novo(db, m).conciliada_com_atendimento_id is None


def test_desconciliar_lancamento_solta_todos_os_creditos(db):
    at = lanc(db, "1000")
    m1, m2 = mov(db, "600"), mov(db, "400")
    db.commit()
    lanc_varios(db, at, [m1.id, m2.id])
    desconciliar_recebimento(db, novo(db, at))
    db.commit()
    assert all(novo(db, m).status == StatusMovimentacaoBancaria.importada for m in (m1, m2))


def test_uma_conta_paga_com_varios_debitos(db):
    c = conta(db, "1000")
    m1, m2 = mov(db, "700", sentido="pagamento"), mov(db, "300", sentido="pagamento")
    db.commit()
    assert conta_varios(db, c, [m1.id, m2.id]).headers["location"].endswith("&agrupado_banco=2")
    assert novo(db, c).status == StatusContaPagar.pago
    assert all(novo(db, m).conta_pagar_id == c.id and novo(db, m).status == StatusMovimentacaoBancaria.conciliada for m in (m1, m2))
    assert sorted(p.valor for p in db.query(PagamentoParcialContaPagar).filter_by(conta_pagar_id=c.id)) == [Decimal("300.00"), Decimal("700.00")]


def test_conta_com_debitos_que_nao_somam_nao_concilia(db):
    c = conta(db, "1000")
    m1, m2 = mov(db, "700", sentido="pagamento"), mov(db, "200", sentido="pagamento")
    db.commit()
    assert "erro=agrupado_soma" in conta_varios(db, c, [m1.id, m2.id]).headers["location"]
    assert novo(db, c).status == StatusContaPagar.agendado and db.query(PagamentoParcialContaPagar).count() == 0


def test_desconciliar_conta_solta_todos_os_debitos(db):
    c = conta(db, "1000")
    m1, m2 = mov(db, "700", sentido="pagamento"), mov(db, "300", sentido="pagamento")
    db.commit()
    conta_varios(db, c, [m1.id, m2.id])
    desconciliar_pagamento(db, novo(db, c))
    db.commit()
    assert all(novo(db, m).status == StatusMovimentacaoBancaria.importada and novo(db, m).conta_pagar_id is None for m in (m1, m2))
    assert db.query(PagamentoParcialContaPagar).count() == 0


def test_conta_com_varios_debitos_sem_autoflush(db):
    """Produção usa sessão sem autoflush: o segundo débito precisa enxergar o primeiro pagamento."""
    c = conta(db, "1000")
    m1, m2 = mov(db, "700", sentido="pagamento"), mov(db, "300", sentido="pagamento")
    db.commit()
    db.autoflush = False
    conta_varios(db, c, [m1.id, m2.id])
    assert novo(db, c).status == StatusContaPagar.pago and novo(db, c).data_pagamento == date(2026, 9, 5)
