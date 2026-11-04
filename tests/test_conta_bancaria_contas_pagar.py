"""Contas a pagar: escolha da conta bancária do cliente no lançamento e na edição."""
import asyncio
import inspect
from datetime import date
from decimal import Decimal

import pytest
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.errors import ErroFlic
from app.models import ClienteBPO, ContaBancaria, ContaPagar, PerfilUsuario, TipoContaBancaria, Usuario
from app.routers import contas_pagar

A, B = 1, 2


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(contas_pagar, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=1, nome="Coord", email="c@x.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            ClienteBPO(id=A, nome="Clínica A"), ClienteBPO(id=B, nome="Clínica B"),
        ])
        session.flush()
        session.add_all([
            ContaBancaria(id=10, cliente_id=A, nome="Itaú principal", tipo=TipoContaBancaria.bancaria, banco="Itaú", conta="123-4"),
            ContaBancaria(id=11, cliente_id=A, nome="Nubank PJ", tipo=TipoContaBancaria.cartao, banco="Nubank"),
            ContaBancaria(id=12, cliente_id=A, nome="Antiga", tipo=TipoContaBancaria.bancaria, ativo=False),
            ContaBancaria(id=20, cliente_id=B, nome="Conta da B", tipo=TipoContaBancaria.bancaria),
        ])
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


def criar(db, conta_bancaria_id, **kw):
    dados = dict(cliente_id=A, descricao="Aluguel", valor=Decimal("1200"), vencimento=date(2026, 12, 5),
                 conta_bancaria_id=conta_bancaria_id, db=db, usuario=db.get(Usuario, 1))
    dados.update(kw)
    return chamar(contas_pagar.criar_conta, **dados)


def test_lancamento_guarda_a_conta_escolhida(db):
    criar(db, "10")
    assert db.query(ContaPagar).one().conta_bancaria_id == 10


def test_conta_nao_informada_continua_permitida(db):
    criar(db, "")
    assert db.query(ContaPagar).one().conta_bancaria_id is None


@pytest.mark.parametrize("escolhida", ["20", "12", "999", "abc"])
def test_recusa_conta_de_outro_cliente_inativa_ou_invalida(db, escolhida):
    with pytest.raises(ErroFlic) as exc:
        criar(db, escolhida)
    assert exc.value.codigo == "FLIC-PAG-018"
    assert db.query(ContaPagar).count() == 0


def test_recorrencia_leva_a_conta_para_as_proximas(db):
    criar(db, "11", recorrente=True, recorrencia_intervalo="mensal", recorrencia_qtd=3)
    assert [c.conta_bancaria_id for c in db.query(ContaPagar).order_by(ContaPagar.id)] == [11, 11, 11]


def editar(db, conta, conta_bancaria_id):
    return chamar(contas_pagar.salvar_edicao_conta, conta_id=conta.id, descricao=conta.descricao, valor=conta.valor,
                  vencimento=conta.vencimento, conta_bancaria_id=conta_bancaria_id, db=db, usuario=db.get(Usuario, 1))


def test_edicao_troca_e_limpa_a_conta(db):
    criar(db, "10")
    conta = db.query(ContaPagar).one()
    editar(db, conta, "11")
    db.expire_all()
    assert db.get(ContaPagar, conta.id).conta_bancaria_id == 11
    editar(db, db.get(ContaPagar, conta.id), "")
    db.expire_all()
    assert db.get(ContaPagar, conta.id).conta_bancaria_id is None
    with pytest.raises(ErroFlic):
        editar(db, db.get(ContaPagar, conta.id), "20")


def test_formulario_lista_so_contas_ativas_do_cliente(db):
    req = Request({"type": "http", "method": "GET", "scheme": "http", "server": ("testserver", 80), "path": "/contas-pagar/novo",
                   "headers": [(b"cookie", f"cliente_ativo={A}".encode())], "query_string": b""})
    tela = chamar(contas_pagar.pagina_nova_conta, request=req, db=db, usuario=db.get(Usuario, 1))
    contas_a = tela.context["contas_bancarias_por_cliente"][A]
    assert [(c["id"], c["tipo"]) for c in contas_a] == [(10, "Conta Corrente"), (11, "Cartão de Crédito")]
    html = tela.body.decode()
    assert 'name="conta_bancaria_id"' in html and "Itaú principal — Conta Corrente (Itaú · C/C 123-4)" in html
    assert "Conta da B" not in html and "Antiga" not in html
