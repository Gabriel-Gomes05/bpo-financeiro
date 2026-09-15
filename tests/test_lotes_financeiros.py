import asyncio
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
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
from app.services.desconciliacao_service import desconciliar_recebimento
from app.models import ExtratoLinhaBancaria, StatusExtratoLinha, StatusMovimentacaoBancaria, TransferenciaCartao, VendaCartao, StatusVendaCartao


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(contas_pagar, "_log", lambda *a, **kw: None)
    monkeypatch.setattr(lancamentos, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([ClienteBPO(id=1, nome="Cliente A"), ClienteBPO(id=2, nome="Cliente B")])
        session.commit()
        yield session
    engine.dispose()


USUARIO = SimpleNamespace(id=1, nome="Operador", perfil=PerfilUsuario.coordenador)


def test_editar_pagamento_confirmado_preserva_extratos(db):
    item = conta(db, status=StatusContaPagar.pago)
    mov = MovimentacaoBancaria(cliente_id=1, tipo="pix_ted", data_movimento=date.today(), valor=100, conta_pagar_id=item.id, status=StatusMovimentacaoBancaria.conciliada)
    linha = ExtratoLinhaBancaria(cliente_id=1, data=date.today(), tipo="debito", valor=100, conta_pagar_id=item.id, status=StatusExtratoLinha.conciliado)
    db.add_all([mov, linha])
    db.flush()
    db.add(PagamentoParcialContaPagar(conta_pagar_id=item.id, movimentacao_id=mov.id, valor=100, data_pagamento=date.today()))
    db.commit()
    editar_valor(db, item, confirmar_conciliacao=True)
    assert item.status == StatusContaPagar.pendente
    assert item.data_pagamento is None
    assert not item.pagamentos_parciais
    assert mov.conta_pagar_id is None and mov.status == StatusMovimentacaoBancaria.importada
    assert linha.conta_pagar_id is None and linha.status == StatusExtratoLinha.importado


def test_excluir_recebimento_confirmado_preserva_movimento(db):
    at = Atendimento(cliente_id=1, data_atendimento=date.today(), condicao_pagamento="avista", valor_servico=50, status_conciliacao=StatusConciliacao.conciliado)
    db.add(at)
    db.flush()
    mov = MovimentacaoBancaria(cliente_id=1, tipo="pix_ted", data_movimento=date.today(), valor=50, conciliada_com_atendimento_id=at.id, status=StatusMovimentacaoBancaria.conciliada)
    db.add(mov)
    db.commit()
    asyncio.run(lancamentos.excluir_lote_lancamentos(ids=[at.id], db=db, usuario=USUARIO, confirmar_conciliacao=True))
    assert db.query(Atendimento).count() == 0
    assert mov.conciliada_com_atendimento_id is None
    assert mov.status == StatusMovimentacaoBancaria.importada


def test_desconciliar_cartao_reabre_lote_e_preserva_outra_venda(db):
    atendimentos = [Atendimento(cliente_id=1, data_atendimento=date.today(), condicao_pagamento="avista", valor_servico=50, status_conciliacao=StatusConciliacao.conciliado) for _ in range(2)]
    lote = TransferenciaCartao(cliente_id=1, data=date.today(), bandeira="Visa", valor_bruto=100, valor_liquido=100)
    db.add_all([*atendimentos, lote])
    db.flush()
    vendas = [VendaCartao(cliente_id=1, data_venda=date.today(), data_pagamento=date.today(), valor_bruto=50, atendimento_id=at.id, lote_id=lote.id, status=StatusVendaCartao.fechado) for at in atendimentos]
    mov = MovimentacaoBancaria(cliente_id=1, tipo="cartao", data_movimento=date.today(), valor=100, transferencia_cartao_id=lote.id, status=StatusMovimentacaoBancaria.conciliada)
    linha = ExtratoLinhaBancaria(cliente_id=1, data=date.today(), tipo="credito", valor=100, transferencia_id=lote.id, status=StatusExtratoLinha.conciliado)
    db.add_all([*vendas, mov, linha])
    db.commit()
    desconciliar_recebimento(db, atendimentos[0])
    db.commit()
    assert db.query(TransferenciaCartao).count() == 0
    assert vendas[0].atendimento_id is None and vendas[0].status == StatusVendaCartao.pendente
    assert vendas[1].atendimento_id == atendimentos[1].id and vendas[1].status == StatusVendaCartao.conciliado
    assert all(v.lote_id is None for v in vendas)
    assert mov.transferencia_cartao_id is None and linha.transferencia_id is None


def test_desconciliar_exige_confirmacao_e_respeita_cliente(db):
    item = conta(db, status=StatusContaPagar.pago)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(contas_pagar.desconciliar_conta(item.id, False, db, USUARIO))
    assert exc.value.status_code == 409
    assert item.status == StatusContaPagar.pago
    with pytest.raises(HTTPException) as exc:
        asyncio.run(contas_pagar.desconciliar_conta(item.id, True, db, SimpleNamespace(id=99, perfil=PerfilUsuario.funcionario)))
    assert exc.value.status_code == 404
    assert item.status == StatusContaPagar.pago


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


def test_lote_pula_conta_paga_e_aplica_no_restante(db):
    a, b = conta(db), conta(db, status=StatusContaPagar.pago)
    aplicar(db, [a.id, b.id], novo_status="agendado")
    assert a.status == StatusContaPagar.agendado
    assert b.status == StatusContaPagar.pago
    aplicar(db, [a.id, b.id], acao="excluir")
    assert db.query(ContaPagar).count() == 1
    assert db.query(ContaPagar).first().id == b.id


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
    with pytest.raises(HTTPException) as exc:
        asyncio.run(lancamentos.excluir_lote_lancamentos(ids=[a.id, b.id], db=db, usuario=USUARIO))
    assert exc.value.status_code == 409
    assert db.query(Atendimento).count() == 2
    asyncio.run(lancamentos.excluir_lote_lancamentos(ids=[a.id], db=db, usuario=USUARIO))
    assert db.query(Atendimento).count() == 1


def test_exclusao_receber_bloqueia_vinculo_mesmo_pendente(db):
    a = Atendimento(cliente_id=1, data_atendimento=date.today(), condicao_pagamento="avista", valor_servico=50)
    db.add(a)
    db.flush()
    db.add(MovimentacaoBancaria(cliente_id=1, tipo="pix_ted", data_movimento=date.today(), valor=50, descricao="Recebimento", conciliada_com_atendimento_id=a.id))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(lancamentos.excluir_lote_lancamentos(ids=[a.id], db=db, usuario=USUARIO))
    assert exc.value.status_code == 409
    assert db.query(Atendimento).count() == 1


def test_exclusao_lote_preserva_pagamento_parcial(db):
    a = conta(db)
    db.add(PagamentoParcialContaPagar(conta_pagar_id=a.id, valor=30, data_pagamento=date.today()))
    db.commit()
    aplicar(db, [a.id], acao="excluir")
    assert db.query(ContaPagar).count() == 1
    assert db.query(PagamentoParcialContaPagar).count() == 1


def test_exclusao_lote_pula_conta_com_conciliacao_bancaria(db):
    a, b = conta(db), conta(db)
    db.add(MovimentacaoBancaria(cliente_id=1, tipo="pix_ted", data_movimento=date.today(), valor=100, descricao="Pagamento", conta_pagar_id=a.id))
    db.commit()
    aplicar(db, [a.id, b.id], acao="excluir")
    assert db.query(ContaPagar).count() == 1
    assert db.query(ContaPagar).first().id == a.id


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


def recorrencia(db):
    primeiro, segundo, terceiro = conta(db), conta(db), conta(db)
    for item in (primeiro, segundo, terceiro):
        item.recorrencia_grupo_id = primeiro.id
        item.recorrencia_intervalo = "mensal"
    db.commit()
    return primeiro, segundo, terceiro


def excluir_recorrente(db, item, escopo="somente", cliente_id=1):
    request = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1234)})
    return asyncio.run(contas_pagar.excluir_conta(
        conta_id=item.id, request=request, cliente_id=cliente_id,
        escopo=escopo, db=db, usuario=USUARIO,
    ))


def test_excluir_primeiro_preserva_e_reagrupa_recorrencia(db):
    primeiro, segundo, terceiro = recorrencia(db)
    excluir_recorrente(db, primeiro)
    assert db.query(ContaPagar).count() == 2
    assert segundo.recorrencia_grupo_id == segundo.id
    assert terceiro.recorrencia_grupo_id == segundo.id
    excluir_recorrente(db, terceiro, "recorrencia")
    assert db.query(ContaPagar).count() == 0


def test_excluir_ocorrencia_intermediaria_preserva_demais(db):
    primeiro, segundo, terceiro = recorrencia(db)
    excluir_recorrente(db, segundo)
    assert db.query(ContaPagar).count() == 2
    assert primeiro.recorrencia_grupo_id == primeiro.id
    assert terceiro.recorrencia_grupo_id == primeiro.id


def test_excluir_toda_recorrencia_a_partir_de_qualquer_ocorrencia(db):
    primeiro, segundo, terceiro = recorrencia(db)
    avulsa = conta(db)
    excluir_recorrente(db, segundo, "recorrencia")
    assert [item.id for item in db.query(ContaPagar).all()] == [avulsa.id]


def test_excluir_recorrencia_pula_pagos_e_exclui_restante(db):
    primeiro, segundo, terceiro = recorrencia(db)
    terceiro.status = StatusContaPagar.pago
    db.commit()
    excluir_recorrente(db, segundo, "recorrencia")
    assert db.query(ContaPagar).count() == 1
    assert db.query(ContaPagar).first().id == terceiro.id
    assert terceiro.status == StatusContaPagar.pago
    assert terceiro.recorrencia_grupo_id == terceiro.id


def test_excluir_recorrencia_toda_paga_nao_exclui_nada(db):
    primeiro, segundo, terceiro = recorrencia(db)
    for item in (primeiro, segundo, terceiro):
        item.status = StatusContaPagar.pago
    db.commit()
    excluir_recorrente(db, segundo, "recorrencia")
    assert db.query(ContaPagar).count() == 3


def test_exclusao_lote_de_recorrentes_preserva_grupo_restante(db):
    primeiro, segundo, terceiro = recorrencia(db)
    aplicar(db, [primeiro.id, segundo.id], acao="excluir")
    assert db.query(ContaPagar).count() == 1
    assert terceiro.recorrencia_grupo_id == terceiro.id
    aplicar(db, [terceiro.id], acao="excluir")
    assert db.query(ContaPagar).count() == 0


def test_exclusao_recorrencia_rejeita_cliente_incorreto_e_escopo_invalido(db):
    primeiro, segundo, terceiro = recorrencia(db)
    excluir_recorrente(db, primeiro, "recorrencia", cliente_id=2)
    assert db.query(ContaPagar).count() == 3
    with pytest.raises(HTTPException) as exc:
        excluir_recorrente(db, primeiro, "invalido")
    assert exc.value.status_code == 400
    assert db.query(ContaPagar).count() == 3


def test_tela_oferece_exclusao_individual_e_recorrencia(db):
    recorrencia(db)
    request = Request({"type": "http", "method": "GET", "scheme": "http", "server": ("testserver", 80), "path": "/contas-pagar", "headers": [], "query_string": b""})
    response = asyncio.run(contas_pagar.listar_contas(request=request, db=db, usuario=USUARIO))
    html = response.body.decode()
    assert '<input type="hidden" name="escopo" value="somente">' in html
    assert '<input type="hidden" name="escopo" value="recorrencia">' in html
    assert "Excluir série" in html


def editar_valor(db, item, escopo="somente", **kwargs):
    params = dict(conta_id=item.id, descricao=item.descricao, fornecedor=None,
                  valor=Decimal("150.01"), vencimento=item.vencimento,
                  data_competencia=None, forma_pagamento=None, plano_conta_id=None,
                  observacao=None, escopo_valor=escopo, db=db, usuario=USUARIO)
    params.update(kwargs)
    return asyncio.run(contas_pagar.salvar_edicao_conta(**params))


def test_editar_valor_somente_ocorrencia(db):
    primeiro, segundo, terceiro = recorrencia(db)
    editar_valor(db, segundo)
    assert [c.valor for c in (primeiro, segundo, terceiro)] == [Decimal("100"), Decimal("150.01"), Decimal("100")]


def test_editar_valor_proximos_preserva_anteriores_datas_e_outros_campos(db):
    primeiro, segundo, terceiro = recorrencia(db)
    primeiro.vencimento = date(2026, 1, 10)
    segundo.vencimento = date(2026, 2, 10)
    terceiro.vencimento = date(2026, 3, 10)
    outra = conta(db)
    db.commit()
    editar_valor(db, segundo, "proximos", vencimento=date(2026, 4, 10), descricao="Alterada")
    assert primeiro.valor == outra.valor == Decimal("100")
    assert segundo.valor == terceiro.valor == Decimal("150.01")
    assert terceiro.vencimento == date(2026, 3, 10)
    assert terceiro.descricao == "Teste"
    assert segundo.descricao == "Alterada"


def test_editar_proximos_pula_pagamento_parcial_e_aplica_no_restante(db):
    primeiro, segundo, terceiro = recorrencia(db)
    db.add(PagamentoParcialContaPagar(conta_pagar_id=terceiro.id, valor=30, data_pagamento=date.today()))
    db.commit()
    editar_valor(db, segundo, "proximos", descricao="Alterado")
    assert primeiro.valor == Decimal("100")
    assert segundo.valor == Decimal("150.01")
    assert terceiro.valor == Decimal("100")
    assert segundo.descricao == "Alterado"
    assert terceiro.descricao == "Teste"


def test_editar_somente_bloqueia_lancamento_com_pagamento_parcial(db):
    item = conta(db)
    db.add(PagamentoParcialContaPagar(conta_pagar_id=item.id, valor=30, data_pagamento=date.today()))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        editar_valor(db, item, descricao="Nao salvar")
    assert exc.value.status_code == 409
    assert item.valor == Decimal("100")
    assert item.descricao == "Teste"


def test_editar_valor_recalcula_rateios_sem_perder_centavos(db):
    from app.models import ContaPagarCentroCustoRateio
    primeiro, segundo, terceiro = recorrencia(db)
    centros = [CentroCusto(cliente_id=1, nome=str(i), ativo=True) for i in range(2)]
    db.add_all(centros)
    db.flush()
    for item in (segundo, terceiro):
        for cc in centros:
            item.rateios_centro_custo.append(ContaPagarCentroCustoRateio(centro_custo_id=cc.id, categoria_key=str(cc.id), percentual=50, valor=50))
    db.commit()
    editar_valor(db, segundo, "proximos")
    for item in (segundo, terceiro):
        assert sum(r.valor for r in item.rateios_centro_custo) == Decimal("150.01")
        assert all(r.percentual == 50 for r in item.rateios_centro_custo)


def test_editar_valor_rejeita_escopo_invalido(db):
    item = conta(db)
    with pytest.raises(HTTPException):
        editar_valor(db, item, "todos")
    assert item.valor == Decimal("100")


@pytest.mark.parametrize("intervalo,dias,esperadas", [
    ("mensal", None, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]),
    ("semanal", None, [date(2026, 1, 31), date(2026, 2, 7), date(2026, 2, 14)]),
    ("quinzenal", None, [date(2026, 1, 31), date(2026, 2, 15), date(2026, 3, 2)]),
    ("personalizado", 10, [date(2026, 1, 31), date(2026, 2, 10), date(2026, 2, 20)]),
])
def test_recorrencia_copia_dados_rateios_e_anexo(db, monkeypatch, tmp_path, intervalo, dias, esperadas):
    from app.models import Usuario
    usuario = Usuario(id=1, nome="Operador", email="recorrencia@example.test", senha_hash="teste", perfil=PerfilUsuario.coordenador)
    plano = PlanoConta(nome="Despesa", tipo="despesa", grupo="DESPESAS FIXAS", codigo="D1", chave="despesa_teste", ativo=True)
    centros = [CentroCusto(cliente_id=1, nome="Centro " + str(i), codigo="C" + str(i), ativo=True) for i in range(2)]
    db.add_all([usuario, plano, *centros])
    db.commit()
    anexo = tmp_path / "documento.pdf"
    anexo.write_bytes(b"anexo de teste")
    async def upload(*args):
        return str(anexo), None, None
    monkeypatch.setattr(contas_pagar, "salvar_upload_temporario", upload)
    response = asyncio.run(contas_pagar.criar_conta(
        cliente_id=1, descricao="Contrato", fornecedor="Fornecedor", valor=Decimal("100.01"),
        vencimento=esperadas[0], data_competencia=date(2026, 1, 15), forma_pagamento="pix",
        categoria_dre=None, plano_conta_id=plano.id,
        rateio_centro_custo_key=[c.codigo for c in centros], rateio_percentual=["50", "50"],
        especialidade="Clinica", observacao="Observacao", documento=SimpleNamespace(filename="documento.pdf"),
        recorrente=True, recorrencia_intervalo=intervalo, recorrencia_dias=dias, recorrencia_qtd=3,
        db=db, usuario=usuario,
    ))
    assert response.status_code == 303
    db.expire_all()
    itens = db.query(ContaPagar).order_by(ContaPagar.id).all()
    assert [item.vencimento for item in itens] == esperadas
    competencias = {
        "mensal": [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15)],
        "semanal": [date(2026, 1, 15), date(2026, 1, 22), date(2026, 1, 29)],
        "quinzenal": [date(2026, 1, 15), date(2026, 1, 30), date(2026, 2, 14)],
        "personalizado": [date(2026, 1, 15), date(2026, 1, 25), date(2026, 2, 4)],
    }
    assert [item.data_competencia for item in itens] == competencias[intervalo]
    original = itens[0]
    campos = [c.name for c in ContaPagar.__table__.columns if c.name not in {
        "id", "public_id", "vencimento", "data_competencia", "documento_path", "criado_em", "updated_at", "created_at",
    }]
    def rateios(item):
        return sorted((r.centro_custo_id, r.categoria_key, r.percentual, r.valor) for r in item.rateios_centro_custo)
    for item in itens:
        for campo in campos:
            assert getattr(item, campo) == getattr(original, campo), campo
        assert rateios(item) == rateios(original)
        assert sum(r.valor for r in item.rateios_centro_custo) == Decimal("100.01")
        assert Path(item.documento_path).read_bytes() == anexo.read_bytes()
    assert len({item.documento_path for item in itens}) == 3
    assert len({r.id for item in itens for r in item.rateios_centro_custo}) == 6
    editar_valor(db, itens[1], descricao="Alterado", plano_conta_id=plano.id,
                 rateio_centro_custo_key=[centros[1].codigo], rateio_percentual=["100"])
    db.expire_all()
    assert itens[0].descricao == itens[2].descricao == "Contrato"
    assert itens[0].valor == itens[2].valor == Decimal("100.01")
    assert rateios(itens[0]) == rateios(itens[2])
    assert len(itens[1].rateios_centro_custo) == 1
    assert itens[1].rateios_centro_custo[0].valor == Decimal("150.01")


def test_edicao_rateio_invalido_nao_altera_conta(db):
    item = conta(db)
    centro = CentroCusto(cliente_id=1, nome="Centro", codigo="C1", ativo=True)
    db.add(centro)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        editar_valor(db, item, rateio_centro_custo_key=["C1"], rateio_percentual=["90"])
    assert exc.value.status_code == 400
    assert item.valor == Decimal("100")
    assert not item.rateios_centro_custo


def test_formulario_edicao_exibe_rateios(db):
    from app.models import ContaPagarCentroCustoRateio
    item = conta(db)
    centro = CentroCusto(cliente_id=1, nome="Administrativo", codigo="ADM", ativo=True)
    db.add(centro)
    db.flush()
    item.rateios_centro_custo.append(ContaPagarCentroCustoRateio(
        centro_custo_id=centro.id, categoria_key="ADM", percentual=100, valor=100,
    ))
    db.commit()
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "session": {}})
    response = asyncio.run(contas_pagar.form_editar_conta(item.id, request, db, USUARIO))
    html = response.body.decode()
    assert 'value="ADM" selected' in html
    assert 'name="rateio_percentual"' in html
