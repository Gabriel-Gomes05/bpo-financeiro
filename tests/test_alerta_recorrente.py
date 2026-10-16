import asyncio
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import ClienteBPO, ContaPagar, PerfilUsuario, StatusContaPagar, Usuario
from app.routers import contas_pagar, dashboard

HOJE = date.today()


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(contas_pagar, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=1, nome="Coord", email="c@example.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            ClienteBPO(id=1, nome="Cliente A"),
        ])
        session.commit()
        yield session
    engine.dispose()


def lancar(db, vencimento, recorrente=True, qtd=3, intervalo="semanal", **extra):
    params = dict(
        cliente_id=1, descricao="Aluguel", fornecedor=None, valor=Decimal("100"), vencimento=vencimento,
        data_competencia=None, forma_pagamento=None, categoria_dre=None, plano_conta_id=None,
        rateio_centro_custo_key=[], rateio_percentual=[], especialidade=None, observacao=None,
        documento=None, recorrente=recorrente, recorrencia_intervalo=intervalo, recorrencia_dias=None,
        recorrencia_qtd=qtd, db=db, usuario=db.get(Usuario, 1),
    )
    params.update(extra)
    asyncio.run(contas_pagar.criar_conta(**params))
    return db.query(ContaPagar).order_by(ContaPagar.id).all()


def alertas(db):
    return dashboard._alertas_recorrentes(db, HOJE, [1])


def test_aviso_configurado_no_lancamento_vale_para_a_serie(db):
    serie = lancar(db, HOJE, aviso_dias_antes=5)
    assert [c.aviso_dias_antes for c in serie] == [5, 5, 5]


def test_aviso_padrao_e_limites(db):
    assert lancar(db, HOJE, qtd=1)[0].aviso_dias_antes == 3
    db.query(ContaPagar).delete()
    assert lancar(db, HOJE, qtd=1, aviso_dias_antes=99)[0].aviso_dias_antes == 30
    db.query(ContaPagar).delete()
    assert lancar(db, HOJE, recorrente=False, qtd=1, aviso_dias_antes=5)[0].aviso_dias_antes is None


def test_alerta_respeita_janela_status_e_recorrencia(db):
    # Série semanal: vence em 4, 11 e 18 dias; aviso de 5 dias -> só a primeira entra.
    lancar(db, HOJE + timedelta(days=4), aviso_dias_antes=5)
    assert [a["dias_restantes"] for a in alertas(db)] == [4]

    # Conta avulsa não gera alerta de recorrente.
    lancar(db, HOJE + timedelta(days=1), recorrente=False, qtd=1)
    assert len(alertas(db)) == 1

    # Conta paga sai do alerta.
    alertas(db)[0]["conta"].status = StatusContaPagar.pago
    db.commit()
    assert alertas(db) == []


def test_alerta_no_dia_com_aviso_zero(db):
    lancar(db, HOJE, qtd=1, aviso_dias_antes=0)
    lancar(db, HOJE + timedelta(days=1), qtd=1, aviso_dias_antes=0)
    assert [a["dias_restantes"] for a in alertas(db)] == [0]


def test_edicao_altera_aviso_desta_e_das_proximas(db):
    primeira, segunda, terceira = lancar(db, HOJE, aviso_dias_antes=3)
    params = dict(conta_id=segunda.id, descricao="Aluguel", fornecedor=None, valor=Decimal("100"),
                  vencimento=segunda.vencimento, data_competencia=None, forma_pagamento=None,
                  plano_conta_id=None, observacao=None, db=db, usuario=db.get(Usuario, 1))
    asyncio.run(contas_pagar.salvar_edicao_conta(**params, escopo_valor="somente", aviso_dias_antes=7))
    assert [c.aviso_dias_antes for c in (primeira, segunda, terceira)] == [3, 7, 3]
    asyncio.run(contas_pagar.salvar_edicao_conta(**params, escopo_valor="proximos", aviso_dias_antes=10))
    assert [c.aviso_dias_antes for c in (primeira, segunda, terceira)] == [3, 10, 10]
