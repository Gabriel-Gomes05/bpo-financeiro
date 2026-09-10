import asyncio
import inspect
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Atendimento, AtendimentoCentroCustoRateio, CentroCusto, ClienteBPO, PerfilUsuario, PlanoConta, StatusConciliacao
from app.routers import lancamentos


@pytest.fixture
def dados(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(lancamentos, "_log", lambda *a, **kw: None)
    with Session(engine) as db:
        db.add_all([ClienteBPO(id=1, nome="A"), ClienteBPO(id=2, nome="B")])
        centros = [CentroCusto(cliente_id=1, nome="Centro " + str(i), ativo=True) for i in range(2)]
        plano = PlanoConta(cliente_id=1, nome="Receita", tipo="receita", grupo="Receitas", chave="receita", ativo=True)
        at = Atendimento(cliente_id=1, data_atendimento=date(2026, 1, 1), valor_servico=100, condicao_pagamento="avista")
        db.add_all([*centros, plano, at])
        db.commit()
        yield db, at, centros, plano
    engine.dispose()


USUARIO = SimpleNamespace(id=1, nome="Operador", perfil=PerfilUsuario.coordenador)


def editar(dados, **kwargs):
    db, at, centros, plano = dados
    params = {name: param.default.default for name, param in inspect.signature(lancamentos.salvar_edicao_lancamento).parameters.items() if hasattr(param.default, "default")}
    params.update(at_id=at.id, request=Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1)}), db=db, usuario=USUARIO,
                  data_atendimento=date(2026, 2, 1), valor_servico="150.01")
    params.update(kwargs)
    return asyncio.run(lancamentos.salvar_edicao_lancamento(**params))


def test_editar_todos_campos_e_rateio(dados):
    db, at, centros, plano = dados
    response = editar(dados, nome_paciente="Cliente", cpf_paciente="12345678900", centro_custo_id=str(centros[0].id),
                     especialidade="Clinica", descricao_servico="Servico", plano_conta_id=str(plano.id),
                     forma_pagamento="cartao_credito", condicao_pagamento="parcelado", parcela_numero=2, parcela_total=3,
                     ultimos_digitos_cartao="1234", bandeira_cartao="Visa", taxa_cartao="2.50", percentual_medico="30",
                     data_prevista_recebimento=date(2026, 3, 10), banco_recebimento="Banco", data_credito=date(2026, 3, 11),
                     data_pagamento_medico=date(2026, 3, 12), observacao="Nota",
                     rateio_centro_custo_id=[str(c.id) for c in centros], rateio_percentual=["50", "50"])
    assert response.status_code == 303
    db.expire_all()
    assert at.nome_paciente == "Cliente"
    assert at.cpf_paciente == "12345678900"
    assert at.plano_conta_id == plano.id
    assert at.especialidade == "Clinica" and at.descricao_servico == "Servico"
    assert at.data_atendimento == date(2026, 2, 1)
    assert at.data_prevista_recebimento == date(2026, 3, 10)
    assert at.banco_recebimento == "Banco" and at.data_credito == date(2026, 3, 11)
    assert at.data_pagamento_medico == date(2026, 3, 12)
    assert at.parcela_numero == 2 and at.parcela_total == 3
    assert at.ultimos_digitos_cartao == "1234" and at.bandeira_cartao == "Visa"
    assert at.observacao == "Nota"
    assert at.valor_liquido == Decimal("146.26")
    assert at.valor_medico == Decimal("45.00")
    assert at.valor_clinica == Decimal("101.26")
    assert sum(r.valor for r in at.rateios_centro_custo) == at.valor_servico
    assert len(at.rateios_centro_custo) == 2


@pytest.mark.parametrize("kwargs", [
    {"valor_servico": "NaN"}, {"valor_servico": "-1"}, {"valor_servico": "1.001"},
    {"percentual_medico": "101"}, {"taxa_cartao": "Infinity", "forma_pagamento": "cartao_credito"},
    {"parcela_numero": 3, "parcela_total": 2}, {"forma_pagamento": "invalida"},
    {"rateio_centro_custo_id": ["1", "1"], "rateio_percentual": ["50", "50"]},
    {"rateio_centro_custo_id": ["1"], "rateio_percentual": ["90"]},
    {"rateio_centro_custo_id": ["1"], "rateio_percentual": ["NaN"]},
])
def test_edicao_invalida_preserva_dados(dados, kwargs):
    with pytest.raises(HTTPException) as exc:
        editar(dados, **kwargs)
    assert exc.value.status_code == 400
    assert dados[1].valor_servico == 100


def test_rateio_rejeita_centro_de_outro_cliente(dados):
    db, at, _, _ = dados
    centro = CentroCusto(cliente_id=2, nome="Outro", ativo=True)
    db.add(centro)
    db.commit()
    with pytest.raises(HTTPException):
        editar(dados, rateio_centro_custo_id=[str(centro.id)], rateio_percentual=["100"])
    assert not at.rateios_centro_custo


def test_remover_rateio_e_trocar_cartao_por_boleto(dados):
    db, at, centros, _ = dados
    at.forma_pagamento = "cartao_credito"
    at.taxa_cartao = 3
    at.bandeira_cartao = "Visa"
    at.rateios_centro_custo.append(AtendimentoCentroCustoRateio(centro_custo_id=centros[0].id, percentual=100, valor=100))
    db.commit()
    editar(dados, forma_pagamento="boleto", rateio_centro_custo_id=[""], rateio_percentual=[""])
    assert not at.rateios_centro_custo
    assert at.taxa_cartao is None and at.bandeira_cartao is None
    assert at.valor_liquido == at.valor_servico


def test_conciliado_e_outro_cliente_nao_sao_editados(dados):
    db, at, _, _ = dados
    at.status_conciliacao = StatusConciliacao.conciliado
    db.commit()
    assert editar(dados).status_code == 303
    assert at.valor_servico == 100
    at.status_conciliacao = StatusConciliacao.pendente
    db.commit()
    assert editar(dados, usuario=SimpleNamespace(id=99, perfil=PerfilUsuario.funcionario)).status_code == 303
    assert at.valor_servico == 100


def test_formulario_expoe_campos_e_selecoes(dados):
    db, at, centros, plano = dados
    at.forma_pagamento = "boleto"
    at.rateios_centro_custo.append(AtendimentoCentroCustoRateio(centro_custo_id=centros[0].id, percentual=100, valor=100))
    db.commit()
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "session": {}})
    response = asyncio.run(lancamentos.form_editar_lancamento(at.id, request, db, USUARIO))
    html = response.body.decode()
    for campo in ("data_prevista_recebimento", "taxa_cartao", "rateio_centro_custo_id", "rateio_percentual", "parcela_numero", "banco_recebimento", "data_credito"):
        assert f'name="{campo}"' in html
    assert 'value="boleto" selected' in html
