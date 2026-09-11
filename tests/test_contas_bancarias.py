from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import ClienteBPO, ContaBancaria, MovimentacaoBancaria, TipoContaBancaria, Atendimento, ContaPagar
from app.routers import conciliacao_banco
from app.services.contas_bancarias_service import registrar_transferencia, saldo_previsto


@pytest.fixture
def banco():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([ClienteBPO(id=1, nome="A"), ClienteBPO(id=2, nome="B")])
        db.flush()
        contas = [ContaBancaria(cliente_id=cliente, nome=f"Conta {i}", tipo=TipoContaBancaria.bancaria,
            banco="Banco", conta=str(i), saldo_atual=Decimal("1000"), saldo_data_referencia=datetime(2026, 1, 1)) for i, cliente in enumerate([1, 1, 2], 1)]
        db.add_all(contas)
        db.commit()
        yield db, contas
    engine.dispose()


def test_transferencia_preserva_total_sem_receita_ou_despesa(banco):
    db, contas = banco
    registrar_transferencia(db, 1, contas[0].id, contas[1].id, Decimal("250"), date(2026, 1, 2))
    db.commit()
    movimentos = db.query(MovimentacaoBancaria).all()
    assert len(movimentos) == 2
    saldos = [saldo_previsto(c, [m for m in movimentos if m.conta_bancaria_id == c.id]) for c in contas[:2]]
    assert saldos == [Decimal("750"), Decimal("1250")]
    assert sum(saldos) == Decimal("2000")
    assert db.query(Atendimento).count() == 0
    assert db.query(ContaPagar).count() == 0
    assert conciliacao_banco._carregar_movimentacoes(db, 1) == []
    assert conciliacao_banco._carregar_saidas_banco(db, 1) == []


@pytest.mark.parametrize("valor", ["0", "-1", "NaN", "Infinity", "1.001"])
def test_transferencia_rejeita_valores_invalidos(banco, valor):
    db, contas = banco
    with pytest.raises(HTTPException):
        registrar_transferencia(db, 1, contas[0].id, contas[1].id, Decimal(valor), date.today())
    assert db.query(MovimentacaoBancaria).count() == 0


def test_transferencia_rejeita_conta_igual_e_outro_cliente(banco):
    db, contas = banco
    for destino in [contas[0].id, contas[2].id]:
        with pytest.raises(HTTPException):
            registrar_transferencia(db, 1, contas[0].id, destino, Decimal("10"), date.today())
    assert db.query(MovimentacaoBancaria).count() == 0


def test_filtro_conta_extrato_e_sugestoes(banco):
    db, contas = banco
    for conta in contas:
        db.add(MovimentacaoBancaria(cliente_id=conta.cliente_id, conta_bancaria_id=conta.id,
            tipo="pix_ted", sentido="recebimento", data_movimento=date.today(), valor=50))
    db.commit()
    db.info["banco_conta_id"] = contas[0].id
    for carregar in [conciliacao_banco._movimentacoes_do_extrato, conciliacao_banco._carregar_movimentacoes, conciliacao_banco._carregar_creditos_banco_para_lote]:
        movimentos = carregar(db, 1)
        assert len(movimentos) == 1
        assert movimentos[0].conta_bancaria_id == contas[0].id


def test_ofx_posterior_absorve_transferencias_sem_duplicar_saldo(banco):
    db, contas = banco
    registrar_transferencia(db, 1, contas[0].id, contas[1].id, Decimal("250"), date(2026, 1, 2))
    db.commit()
    contas[0].saldo_atual = Decimal("750")
    contas[0].saldo_data_referencia = datetime(2026, 1, 2, 23, 59, 59, 999999)
    movimentos = db.query(MovimentacaoBancaria).filter_by(conta_bancaria_id=contas[0].id).all()
    assert saldo_previsto(contas[0], movimentos) == Decimal("750")


def test_reenvio_da_transferencia_nao_duplica(banco):
    db, contas = banco
    token = "28bd7f31-f039-44f5-a882-0747cba27ff8"
    for _ in range(2):
        registrar_transferencia(db, 1, contas[0].id, contas[1].id, Decimal("25"), date.today(), token=token)
        db.commit()
    assert db.query(MovimentacaoBancaria).count() == 2
