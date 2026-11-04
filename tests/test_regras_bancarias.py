"""Regras automáticas de conciliação bancária: motor, aplicação retroativa e processamento em lote."""
import asyncio
import inspect
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database import Base
from app.errors import ErroFlic
from app.models import (
    Atendimento, ClienteBPO, ContaBancaria, ContaPagar, FormaPagamento, MovimentacaoBancaria,
    PagamentoParcialContaPagar, PerfilUsuario, PlanoConta, RegraNegocioBancaria, StatusConciliacao,
    StatusContaPagar, StatusMovimentacaoBancaria, TipoContaBancaria, Usuario,
)
from app.routers import conciliacao_banco
from app.services import regras_bancarias_service as svc

A, B = 1, 2
CC_A, INV_A, CC_B = 11, 12, 21
RECEITA, DESPESA = 1, 2


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _savepoints_sqlite(dbapi, _):  # pysqlite precisa disto para SAVEPOINT funcionar
        dbapi.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    monkeypatch.setattr(conciliacao_banco, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=1, nome="Coord", email="c@x.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            ClienteBPO(id=A, nome="Clínica A"), ClienteBPO(id=B, nome="Clínica B"),
            PlanoConta(id=RECEITA, tipo="receita", grupo="R", chave="convenio", nome="Convênio"),
            PlanoConta(id=DESPESA, tipo="despesa", grupo="D", chave="aluguel", nome="Aluguel"),
        ])
        session.flush()
        session.add_all([
            ContaBancaria(id=CC_A, cliente_id=A, nome="Itaú A", tipo=TipoContaBancaria.bancaria),
            ContaBancaria(id=INV_A, cliente_id=A, nome="CDB A", tipo=TipoContaBancaria.investimento),
            ContaBancaria(id=CC_B, cliente_id=B, nome="Itaú B", tipo=TipoContaBancaria.bancaria),
        ])
        session.commit()
        yield session
    engine.dispose()


def mov(db, cliente=A, conta=CC_A, valor="100", descricao="PIX CONVENIO SAUDE", sentido="recebimento", **kw):
    m = MovimentacaoBancaria(cliente_id=cliente, conta_bancaria_id=conta, tipo="pix_ted", sentido=sentido,
                             data_movimento=date(2026, 1, 10), valor=Decimal(valor), descricao=descricao, **kw)
    db.add(m)
    db.flush()
    return m


def lancamento(db, cliente=A, valor="100", **kw):
    at = Atendimento(cliente_id=cliente, data_atendimento=date(2026, 1, 1), valor_servico=Decimal(valor),
                     condicao_pagamento="avista", plano_conta_id=RECEITA, forma_pagamento=FormaPagamento.pix, **kw)
    db.add(at)
    db.flush()
    return at


def conta_pagar(db, cliente=A, valor="300", status=StatusContaPagar.agendado):
    c = ContaPagar(cliente_id=cliente, descricao="Aluguel", valor=Decimal(valor), vencimento=date(2026, 1, 5),
                   status=status, plano_conta_id=DESPESA)
    db.add(c)
    db.flush()
    return c


def chamar(funcao, **kwargs):
    params = {}
    for nome, param in inspect.signature(funcao).parameters.items():
        if param.default is not inspect.Parameter.empty:
            params[nome] = getattr(param.default, "default", param.default)
    params.update(kwargs)
    return asyncio.run(funcao(**params))


def criar_regra(db, acao="conciliar_receita", padrao="convenio", aplicar=False, cliente=A, **kw):
    campos = {"plano_conta_id": RECEITA} if acao == "conciliar_receita" else (
        {"plano_conta_id": DESPESA} if acao == "conciliar_despesa" else {"conta_origem_id": CC_A, "conta_destino_id": INV_A})
    campos.update(kw)
    return chamar(conciliacao_banco.criar_regra_bancaria, cliente_id=cliente, nome="Regra", padrao_descricao=padrao,
                  acao=acao, aplicar_existentes=aplicar, db=db, usuario=db.get(Usuario, 1), **campos)


def numeros(resposta) -> dict:
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(resposta.headers["location"]).query)
    return {k.removeprefix("regra_"): int(v[0]) for k, v in q.items() if k.startswith("regra_") and k != "regra_criada"}


def recarregar(db, obj):
    db.expire_all()
    return db.get(type(obj), obj.id)


# 1 ------------------------------------------------------------------ criação

def test_criacao_sem_aplicar_nao_mexe_no_historico(db):
    at, m = lancamento(db), mov(db)
    db.commit()
    resposta = criar_regra(db)
    assert "regra_criada=1" in resposta.headers["location"] and "regra_analisados" not in resposta.headers["location"]
    regra = db.query(RegraNegocioBancaria).one()
    assert (regra.cliente_id, regra.acao, regra.plano_conta_id, regra.ativo) == (A, "conciliar_receita", RECEITA, True)
    assert recarregar(db, m).status == StatusMovimentacaoBancaria.importada
    assert recarregar(db, at).status_conciliacao == StatusConciliacao.pendente


# 2 ------------------------------------------------------------------ novos lançamentos

def test_regra_vale_para_novas_movimentacoes(db):
    criar_regra(db)
    at, m = lancamento(db), mov(db)  # chega depois da regra, como numa importação
    assert conciliacao_banco._aplicar_regras_bancarias(db, A) == 1
    db.commit()
    m, at = recarregar(db, m), recarregar(db, at)
    assert m.status == StatusMovimentacaoBancaria.conciliada and m.conciliada_com_atendimento_id == at.id
    # Mesma baixa da conciliação manual: status, data de crédito e valor líquido.
    assert (at.status_conciliacao, at.data_credito, at.valor_liquido) == (StatusConciliacao.conciliado, date(2026, 1, 10), Decimal("100.00"))


# 3 ------------------------------------------------------------------ retroativa

def test_retroativa_concilia_historico_antigo_inclusive_sem_conta(db):
    antigos = [(lancamento(db, valor=str(v)), mov(db, valor=str(v), conta=None if v == 300 else CC_A)) for v in (100, 200, 300)]
    db.commit()
    assert numeros(criar_regra(db, aplicar=True)) == {"analisados": 3, "conciliados": 3, "ignorados": 0, "falhas": 0}
    for at, m in antigos:
        assert recarregar(db, m).conciliada_com_atendimento_id == at.id


def test_retroativa_de_despesa_e_transferencia(db):
    conta = conta_pagar(db, valor="300")
    pagamento = mov(db, sentido="pagamento", valor="300", descricao="TED ALUGUEL SALA")
    aplicacao = mov(db, sentido="pagamento", valor="1000", descricao="APLICACAO CDB")
    db.commit()
    assert numeros(criar_regra(db, acao="conciliar_despesa", padrao="aluguel", aplicar=True))["conciliados"] == 1
    assert recarregar(db, conta).status == StatusContaPagar.pago and recarregar(db, pagamento).conta_pagar_id == conta.id
    assert numeros(criar_regra(db, acao="transferencia", padrao="aplicacao cdb", aplicar=True))["conciliados"] == 1
    entrada = db.query(MovimentacaoBancaria).filter_by(conta_bancaria_id=INV_A).one()
    assert entrada.valor == Decimal("1000.00") and recarregar(db, aplicacao).tipo == "transf_interna"


# 4 ------------------------------------------------------------------ já conciliados

def test_ignora_e_preserva_ja_conciliados(db):
    outro = lancamento(db, status_conciliacao=StatusConciliacao.conciliado)
    conciliado = mov(db, status=StatusMovimentacaoBancaria.conciliada, conciliada_com_atendimento_id=outro.id)
    arquivado = mov(db, valor="50", arquivado_conciliacao_banco=True)
    lancamento(db, valor="50")
    db.commit()
    assert numeros(criar_regra(db, aplicar=True))["analisados"] == 0
    assert recarregar(db, conciliado).conciliada_com_atendimento_id == outro.id
    assert recarregar(db, arquivado).status == StatusMovimentacaoBancaria.importada  # arquivado pelo usuário


# 5 ------------------------------------------------------------------ duplicidade

def test_sem_conciliacao_duplicada_nem_ambigua(db):
    at = lancamento(db, valor="100")
    m1, m2 = mov(db, valor="100"), mov(db, valor="100")
    db.commit()
    assert numeros(criar_regra(db, aplicar=True))["conciliados"] == 1
    vinculos = [recarregar(db, m).conciliada_com_atendimento_id for m in (m1, m2)]
    assert vinculos.count(at.id) == 1 and vinculos.count(None) == 1


def test_candidatos_ambiguos_nao_sao_conciliados(db):
    lancamento(db, valor="100"), lancamento(db, valor="100")
    m = mov(db, valor="100")
    db.commit()
    assert numeros(criar_regra(db, aplicar=True))["conciliados"] == 0
    assert recarregar(db, m).status == StatusMovimentacaoBancaria.importada


def test_despesa_respeita_pagamentos_parciais(db):
    """Bug corrigido: a regra pagava o valor cheio de uma conta já parcialmente paga (R$ 140 de R$ 100)."""
    conta = conta_pagar(db, valor="100")
    db.add(PagamentoParcialContaPagar(conta_pagar_id=conta.id, valor=Decimal("40"), data_pagamento=date(2026, 1, 2)))
    cheio, saldo = mov(db, sentido="pagamento", valor="100", descricao="ALUGUEL"), mov(db, sentido="pagamento", valor="60", descricao="ALUGUEL")
    db.commit()
    assert numeros(criar_regra(db, acao="conciliar_despesa", padrao="aluguel", aplicar=True))["conciliados"] == 1
    assert recarregar(db, cheio).status == StatusMovimentacaoBancaria.importada
    assert recarregar(db, saldo).conta_pagar_id == conta.id
    assert sum(p.valor for p in db.query(PagamentoParcialContaPagar)) == Decimal("100.00")
    assert recarregar(db, conta).status == StatusContaPagar.pago


# 6 ------------------------------------------------------------------ sem correspondência

def test_regra_sem_correspondencias(db):
    for v in ("10", "20"):
        mov(db, valor=v, descricao="TARIFA BANCARIA")
    db.commit()
    assert numeros(criar_regra(db, padrao="convenio", aplicar=True)) == {"analisados": 2, "conciliados": 0, "ignorados": 2, "falhas": 0}


# 7 ------------------------------------------------------------------ grande volume

def test_grande_volume_em_lotes(db):
    total = 1250
    db.add_all([MovimentacaoBancaria(cliente_id=A, conta_bancaria_id=CC_A, tipo="pix_ted", sentido="pagamento",
                                     data_movimento=date(2026, 1, 1), valor=Decimal(i + 1),
                                     descricao="APLICACAO CDB" if i % 10 == 0 else "OUTRA SAIDA")
                for i in range(total)])
    db.commit()
    regra = RegraNegocioBancaria(cliente_id=A, nome="CDB", padrao_descricao="aplicacao cdb", acao="transferencia",
                                 conta_origem_id=CC_A, conta_destino_id=INV_A)
    db.add(regra)
    db.commit()
    resultado = svc.aplicar_regras(db, A, [regra], tamanho_lote=100, confirmar_por_lote=True)
    assert (resultado.analisados, resultado.conciliados, resultado.ignorados, resultado.falhas) == (total, 125, total - 125, 0)
    assert resultado.lotes == 13
    assert db.query(MovimentacaoBancaria).filter_by(conta_bancaria_id=INV_A).count() == 125


# 8 ------------------------------------------------------------------ falhas

def test_falha_em_um_lancamento_nao_deixa_estado_inconsistente(db, monkeypatch):
    pares = [(lancamento(db, valor=str(v)), mov(db, valor=str(v))) for v in (100, 200, 300)]
    db.commit()
    original = svc.ACOES_REGRA["conciliar_receita"]
    alvo = pares[1][1].id

    def instavel(sessao, regra, m):
        feito = original(sessao, regra, m)
        if m.id == alvo:
            raise RuntimeError("falha no meio da baixa")
        return feito

    monkeypatch.setitem(svc.ACOES_REGRA, "conciliar_receita", instavel)
    assert numeros(criar_regra(db, aplicar=True)) == {"analisados": 3, "conciliados": 2, "ignorados": 0, "falhas": 1}
    at_falha, mov_falha = (recarregar(db, o) for o in pares[1])
    assert mov_falha.status == StatusMovimentacaoBancaria.importada and mov_falha.conciliada_com_atendimento_id is None
    assert at_falha.status_conciliacao == StatusConciliacao.pendente and at_falha.valor_liquido is None
    assert recarregar(db, pares[0][1]).status == StatusMovimentacaoBancaria.conciliada


def test_falha_geral_mostra_erro_e_mantem_a_regra(db, monkeypatch):
    mov(db)
    db.commit()

    def quebra(*a, **kw):
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr(svc, "aplicar_regras", quebra)
    resposta = criar_regra(db, aplicar=True)
    assert "erro=regra_retroativa_falhou" in resposta.headers["location"]
    assert db.query(RegraNegocioBancaria).count() == 1


# 9 ------------------------------------------------------------------ isolamento

def test_isolamento_entre_clientes(db):
    lancamento(db, cliente=B, valor="100")
    m_b = mov(db, cliente=B, conta=CC_B, valor="100")
    lancamento(db, valor="100")
    m_a = mov(db, valor="100")
    db.commit()
    assert numeros(criar_regra(db, aplicar=True)) == {"analisados": 1, "conciliados": 1, "ignorados": 0, "falhas": 0}
    assert recarregar(db, m_b).status == StatusMovimentacaoBancaria.importada
    assert recarregar(db, m_a).status == StatusMovimentacaoBancaria.conciliada
    regra_a = db.query(RegraNegocioBancaria).one()
    assert svc.aplicar_regras(db, B, [regra_a]).analisados == 0  # regra de A nunca roda em B
    with pytest.raises(ErroFlic):
        criar_regra(db, cliente=99, aplicar=True)


def test_reaplicar_regra_de_outro_cliente_e_negado(db):
    criar_regra(db)
    regra = db.query(RegraNegocioBancaria).one()
    with pytest.raises(ErroFlic) as exc:
        chamar(conciliacao_banco.aplicar_regra_existentes, regra_id=regra.id, cliente_id=B, db=db, usuario=db.get(Usuario, 1))
    assert exc.value.codigo == "FLIC-CON-019"


# 10 ----------------------------------------------------------------- execução repetida

def test_execucao_repetida_nao_duplica(db):
    lancamento(db, valor="100")
    mov(db, valor="100")
    conta_pagar(db, valor="300")
    mov(db, sentido="pagamento", valor="300", descricao="ALUGUEL")
    mov(db, sentido="pagamento", valor="1000", descricao="APLICACAO CDB")
    db.commit()
    for acao, padrao in (("conciliar_receita", "convenio"), ("conciliar_despesa", "aluguel"), ("transferencia", "aplicacao cdb")):
        criar_regra(db, acao=acao, padrao=padrao, aplicar=True)
    estado = (db.query(MovimentacaoBancaria).count(), db.query(PagamentoParcialContaPagar).count())
    for regra in db.query(RegraNegocioBancaria).all():
        resposta = chamar(conciliacao_banco.aplicar_regra_existentes, regra_id=regra.id, cliente_id=A, db=db,
                          usuario=db.get(Usuario, 1))
        assert numeros(resposta)["conciliados"] == 0
    assert (db.query(MovimentacaoBancaria).count(), db.query(PagamentoParcialContaPagar).count()) == estado
    assert conciliacao_banco._aplicar_regras_bancarias(db, A) == 0
