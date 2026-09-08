import asyncio
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import (
    Atendimento, CentroCusto, ClienteBPO, ContaPagar, PerfilUsuario,
    PlanoConta, StatusConciliacao, StatusContaPagar, MovimentacaoBancaria,
    PagamentoParcialContaPagar,
)
from app.routers import contas_pagar, lancamentos
from app.services.conciliacao_service import importar_lancamentos


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(contas_pagar, "_log", lambda *a, **kw: None)
    monkeypatch.setattr(lancamentos, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([ClienteBPO(id=1, nome="Cliente A"), ClienteBPO(id=2, nome="Cliente B")])
        session.commit()
        yield session
    engine.dispose()


USUARIO = SimpleNamespace(id=1, nome="Operador", perfil=PerfilUsuario.coordenador)


def conta(db, **kwargs):
    obj = ContaPagar(cliente_id=1, descricao="Teste", valor=Decimal("100"), vencimento=date.today(), **kwargs)
    db.add(obj)
    db.commit()
    return obj


def aplicar(db, ids, **kwargs):
    params = dict(request=None, ids=ids, acao="editar", plano_conta_id=None,
                  centro_custo_id=None, novo_status="", db=db, usuario=USUARIO)
    params.update(kwargs)
    return asyncio.run(contas_pagar.aplicar_lote_contas(**params))


def test_edicao_lote_categoria_centro_e_status(db):
    a, b = conta(db), conta(db)
    plano = PlanoConta(nome="Despesa", tipo="despesa", grupo="DESPESAS FIXAS", codigo="D1", chave="despesa_teste", ativo=True)
    centro = CentroCusto(cliente_id=1, nome="Administrativo", codigo="ADM", ativo=True)
    db.add_all([plano, centro])
    db.commit()
    aplicar(db, [a.id, b.id], plano_conta_id=plano.id, centro_custo_id=centro.id, novo_status="agendado")
    for item in (a, b):
        assert item.plano_conta_id == plano.id
        assert item.categoria_dre == plano.chave
        assert item.status == StatusContaPagar.agendado
        assert item.rateios_centro_custo[0].valor == Decimal("100")
        assert item.rateios_centro_custo[0].percentual == Decimal("100")


def test_lote_invalido_nao_altera_nenhuma_conta(db):
    a, b = conta(db), conta(db, status=StatusContaPagar.pago)
    aplicar(db, [a.id, b.id], novo_status="agendado")
    assert a.status == StatusContaPagar.pendente
    aplicar(db, [a.id, b.id], acao="excluir")
    assert db.query(ContaPagar).count() == 2


def test_lote_rejeita_centro_de_outro_cliente_e_baixa_manual(db):
    a = conta(db)
    centro = CentroCusto(cliente_id=2, nome="Outro", ativo=True)
    db.add(centro)
    db.commit()
    aplicar(db, [a.id], centro_custo_id=centro.id)
    assert not a.rateios_centro_custo
    aplicar(db, [a.id], novo_status="pago")
    assert a.status == StatusContaPagar.pendente


def test_lote_rejeita_selecao_fora_do_acesso(db, monkeypatch):
    a = conta(db)
    monkeypatch.setattr(contas_pagar, "_ids_clientes_do_usuario", lambda *args: [2])
    with pytest.raises(HTTPException) as exc:
        aplicar(db, [a.id], acao="excluir")
    assert exc.value.status_code == 404
    assert db.query(ContaPagar).count() == 1


def test_excluir_lote_contas(db):
    a, b = conta(db), conta(db)
    aplicar(db, [a.id, b.id], acao="excluir")
    assert db.query(ContaPagar).count() == 0


def test_importacao_adiciona_sem_apagar_pendentes(db):
    at = Atendimento(cliente_id=1, data_atendimento=date.today(), condicao_pagamento="avista", valor_servico=50)
    db.add(at)
    db.commit()
    original_id = at.id
    total = importar_lancamentos(db, 1, pd.DataFrame([{"data": "2026-09-08", "valor": 120}]), substituir_pendentes=False)
    assert total == 1
    assert db.query(Atendimento).count() == 2
    assert db.get(Atendimento, original_id).valor_servico == Decimal("50")


def test_exclusao_receber_bloqueia_conciliado_e_exclui_pendente(db):
    a = Atendimento(cliente_id=1, data_atendimento=date.today(), condicao_pagamento="avista", valor_servico=50)
    b = Atendimento(cliente_id=1, data_atendimento=date.today(), condicao_pagamento="avista", valor_servico=60, status_conciliacao=StatusConciliacao.conciliado)
    db.add_all([a, b])
    db.commit()
    asyncio.run(lancamentos.excluir_lote_lancamentos(ids=[a.id, b.id], db=db, usuario=USUARIO))
    assert db.query(Atendimento).count() == 2
    asyncio.run(lancamentos.excluir_lote_lancamentos(ids=[a.id], db=db, usuario=USUARIO))
    assert db.query(Atendimento).count() == 1


def test_exclusao_receber_bloqueia_vinculo_mesmo_pendente(db):
    a = Atendimento(cliente_id=1, data_atendimento=date.today(), condicao_pagamento="avista", valor_servico=50)
    db.add(a)
    db.flush()
    db.add(MovimentacaoBancaria(cliente_id=1, tipo="pix_ted", data_movimento=date.today(), valor=50, descricao="Recebimento", conciliada_com_atendimento_id=a.id))
    db.commit()
    asyncio.run(lancamentos.excluir_lote_lancamentos(ids=[a.id], db=db, usuario=USUARIO))
    assert db.query(Atendimento).count() == 1


def test_exclusao_lote_preserva_pagamento_parcial(db):
    a = conta(db)
    db.add(PagamentoParcialContaPagar(conta_pagar_id=a.id, valor=30, data_pagamento=date.today()))
    db.commit()
    aplicar(db, [a.id], acao="excluir")
    assert db.query(ContaPagar).count() == 1
    assert db.query(PagamentoParcialContaPagar).count() == 1


def test_modelo_disponivel_importa_parcelas(db):
    total = importar_lancamentos(db, 1, pd.read_excel("static/modelos/modelo_lancamentos_lote.xlsx"), substituir_pendentes=False)
    assert total > 0
    assert db.query(Atendimento).filter(Atendimento.parcela_total == 2).count() > 0


def test_filtros_em_aberto_vencidas_e_a_vencer(db, monkeypatch):
    ontem = conta(db)
    ontem.vencimento = date.today() - timedelta(days=1)
    hoje = conta(db)
    conta(db, status=StatusContaPagar.pago)
    conta(db, status=StatusContaPagar.cancelado)
    db.commit()
    monkeypatch.setattr(contas_pagar.templates, "TemplateResponse", lambda nome, contexto: contexto)
    request = Request({"type": "http", "headers": [], "query_string": b""})
    for situacao, esperados in [("aberto", {ontem.id, hoje.id}), ("vencidas", {ontem.id}), ("a_vencer", {hoje.id})]:
        contexto = asyncio.run(contas_pagar.listar_contas(request=request, situacao=situacao, db=db, usuario=USUARIO))
        assert {c.id for c in contexto["contas"]} == esperados


@pytest.mark.parametrize("modulo,path,funcao", [
    (contas_pagar, "/contas-pagar", contas_pagar.listar_contas),
    (lancamentos, "/lancamentos", lancamentos.listar_lancamentos),
])
def test_telas_renderizam_selecao_e_acoes(db, modulo, path, funcao):
    conta(db)
    db.add(Atendimento(cliente_id=1, data_atendimento=date.today(), condicao_pagamento="avista", valor_servico=50))
    db.commit()
    request = Request({"type": "http", "method": "GET", "scheme": "http", "server": ("testserver", 80), "path": path, "headers": [], "query_string": b""})
    response = asyncio.run(funcao(request=request, db=db, usuario=USUARIO))
    html = response.body.decode()
    assert 'form="form-lote"' in html
    assert 'id="selecionar-todos"' in html
    assert "Excluir selecionados" in html
    assert "/static/js/lote.js" in html
