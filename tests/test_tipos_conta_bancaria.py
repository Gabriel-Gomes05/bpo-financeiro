"""Cadastro de contas bancárias por tipo: Conta Corrente, Investimentos e Cartão de Crédito."""
import asyncio
import inspect
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.errors import ErroFlic
from app.models import ClienteBPO, ContaBancaria, MovimentacaoBancaria, PerfilUsuario, TipoContaBancaria, Usuario
from app.routers import conciliacao_banco
from app.services.contas_bancarias_service import conta_do_cliente, registrar_transferencia

CLIENTE, OUTRO = 1, 2


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(conciliacao_banco, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=1, nome="Coord", email="c@x.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            ClienteBPO(id=CLIENTE, nome="Clínica"), ClienteBPO(id=OUTRO, nome="Outra"),
        ])
        session.commit()
        yield session
    engine.dispose()


def cadastrar(db, **campos):
    params = {}
    for nome, param in inspect.signature(conciliacao_banco.cadastrar_conta_bancaria).parameters.items():
        if param.default is not inspect.Parameter.empty:
            params[nome] = getattr(param.default, "default", param.default)
    params.update(cliente_id=CLIENTE, db=db, usuario=db.get(Usuario, 1))
    params.update(campos)
    return asyncio.run(conciliacao_banco.cadastrar_conta_bancaria(**params))


def erro_ao_cadastrar(db, **campos):
    with pytest.raises(ErroFlic) as exc:
        cadastrar(db, **campos)
    return exc.value.codigo


# ---------------------------------------------------------------- conta corrente

def test_conta_corrente_com_agencia_numero_e_saldo(db):
    resposta = cadastrar(db, tipo="bancaria", banco="Itaú", agencia="0001", numero="12345-6",
                         saldo="1500.50", data_saldo=date(2026, 11, 1))
    conta = db.query(ContaBancaria).one()
    assert (conta.tipo, conta.banco, conta.agencia, conta.conta) == (TipoContaBancaria.bancaria, "Itaú", "0001", "12345-6")
    assert conta.nome == "Itaú · Ag. 0001 · C/C 12345-6"  # nome é opcional na conta corrente
    assert conta.saldo_atual == Decimal("1500.50") and conta.cliente_id == CLIENTE
    assert f"conta_bancaria_id={conta.id}" in resposta.headers["location"]


@pytest.mark.parametrize("faltando", ["banco", "agencia", "numero"])
def test_conta_corrente_exige_banco_agencia_e_numero(db, faltando):
    campos = dict(tipo="bancaria", banco="Itaú", agencia="0001", numero="123", saldo="0")
    campos[faltando] = " "
    assert erro_ao_cadastrar(db, **campos) == "FLIC-CON-004"
    assert db.query(ContaBancaria).count() == 0


def test_conta_corrente_exige_saldo_inicial(db):
    assert erro_ao_cadastrar(db, tipo="bancaria", banco="Itaú", agencia="1", numero="2", saldo="") == "FLIC-CON-005"


def test_conta_corrente_duplicada(db):
    cadastrar(db, tipo="bancaria", banco="Itaú", agencia="1", numero="2", saldo="0")
    assert erro_ao_cadastrar(db, tipo="bancaria", banco="itaú", agencia="1", numero="2", saldo="0") == "FLIC-CON-006"


# ---------------------------------------------------------------- investimentos

def test_investimento_com_nome_e_descricao_sem_agencia_e_numero(db):
    cadastrar(db, tipo="investimento", banco="XP", nome="CDB Liquidez", descricao="Reserva de emergência",
              agencia="9999", numero="888")
    conta = db.query(ContaBancaria).one()
    assert conta.tipo == TipoContaBancaria.investimento
    assert (conta.nome, conta.descricao) == ("CDB Liquidez", "Reserva de emergência")
    assert conta.agencia is None and conta.conta is None  # não são usados nesse tipo
    assert conta.saldo_atual is None  # saldo é opcional


@pytest.mark.parametrize("faltando", ["banco", "nome", "descricao"])
def test_investimento_exige_banco_nome_e_descricao(db, faltando):
    campos = dict(tipo="investimento", banco="XP", nome="CDB", descricao="Reserva")
    campos[faltando] = ""
    assert erro_ao_cadastrar(db, **campos) == "FLIC-CON-004"


def test_investimento_recebe_transferencia_da_conta_corrente(db):
    cadastrar(db, tipo="bancaria", banco="Itaú", agencia="1", numero="2", saldo="1000")
    cadastrar(db, tipo="investimento", banco="Itaú", nome="CDB", descricao="Aplicação", saldo="0")
    corrente, investimento = db.query(ContaBancaria).order_by(ContaBancaria.id).all()
    registrar_transferencia(db, CLIENTE, corrente.id, investimento.id, Decimal("300"), date(2026, 11, 4), "Aplicação CDB")
    db.commit()
    assert db.query(MovimentacaoBancaria).filter_by(conta_bancaria_id=investimento.id, sentido="recebimento").count() == 1
    ids = {r["conta"].id for r in conciliacao_banco._resumo_saldos_bancarios(db, CLIENTE)}
    assert ids == {corrente.id, investimento.id}


# ---------------------------------------------------------------- cartão de crédito

def test_cartao_de_credito_so_e_cadastrado(db):
    resposta = cadastrar(db, tipo="cartao", banco="Nubank", nome="Cartão corporativo", saldo="999")
    cartao = db.query(ContaBancaria).one()
    assert cartao.tipo == TipoContaBancaria.cartao and cartao.nome == "Cartão corporativo"
    assert cartao.saldo_atual is None
    assert resposta.headers["location"].endswith("#contas-cadastradas")
    # Sem regras de fatura ainda: fora de saldos, transferências e conciliação.
    assert conciliacao_banco._resumo_saldos_bancarios(db, CLIENTE) == []
    with pytest.raises(ErroFlic) as exc:
        conta_do_cliente(db, CLIENTE, cartao.id)
    assert exc.value.codigo == "FLIC-CON-007"


def test_cartao_exige_banco_e_nome(db):
    assert erro_ao_cadastrar(db, tipo="cartao", banco="Nubank", nome="") == "FLIC-CON-004"


# ---------------------------------------------------------------- geral

@pytest.mark.parametrize("tipo", ["", "poupanca", "BANCARIA"])
def test_tipo_invalido(db, tipo):
    assert erro_ao_cadastrar(db, tipo=tipo, banco="X", nome="Y") == "FLIC-CON-017"


def test_conta_sempre_vinculada_a_cliente_permitido(db):
    with pytest.raises(ErroFlic) as exc:
        cadastrar(db, cliente_id=999, tipo="cartao", banco="X", nome="Y")
    assert exc.value.codigo == "FLIC-AUT-004"


def test_contas_antigas_continuam_conta_corrente(db):
    db.add(ContaBancaria(cliente_id=CLIENTE, nome="Legada", tipo=TipoContaBancaria.bancaria, banco="BB", conta="1"))
    db.commit()
    legada = db.query(ContaBancaria).one()
    assert conta_do_cliente(db, CLIENTE, legada.id).id == legada.id
    assert conciliacao_banco.ROTULOS_TIPO_CONTA[legada.tipo] == "Conta Corrente"
