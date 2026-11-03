import asyncio
import shutil
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import openpyxl
import pandas as pd
import pytest
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Atendimento, ClienteBPO, FormaPagamento, PerfilUsuario, PlanoConta, Usuario
from app.routers import lancamentos
from app.services import conciliacao_service as cs


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(lancamentos, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=1, nome="Coord", email="c@example.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            ClienteBPO(id=1, nome="Cliente"),
            PlanoConta(tipo="receita", grupo="R", chave="consulta", codigo="20.01", nome="Consulta", ativo=True),
            PlanoConta(tipo="receita", grupo="R", chave="procedimentos", codigo="20.02", nome="Procedimentos", ativo=True),
            PlanoConta(tipo="receita", grupo="R", chave="dez", codigo="20.10", nome="Teste dez", ativo=True),
        ])
        session.commit()
        yield session
    engine.dispose()


def importar(db, linhas, **kwargs):
    ocorrencias = []
    total = cs.importar_lancamentos(db, 1, pd.DataFrame(linhas), substituir_pendentes=False,
                                    ocorrencias=ocorrencias, **kwargs)
    return total, ocorrencias, db.query(Atendimento).order_by(Atendimento.id).all()


# --- Leitura de cada tipo de campo -------------------------------------------------

@pytest.mark.parametrize("entrada,esperado", [
    (150, Decimal("150.00")), (350.5, Decimal("350.50")), ("350,00", Decimal("350.00")),
    ("1.234,56", Decimal("1234.56")), ("R$ 1.234,56", Decimal("1234.56")), ("1234.56", Decimal("1234.56")),
    ("1.234.567", Decimal("1234567.00")),
])
def test_valor_formato_brasileiro(entrada, esperado):
    assert cs._valor_planilha(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    ("05/06/2026", date(2026, 6, 5)), ("25/06/2026", date(2026, 6, 25)), ("05/06/26", date(2026, 6, 5)),
    ("2026-06-05", date(2026, 6, 5)), (pd.Timestamp("2026-06-05"), date(2026, 6, 5)),
    (None, None), (float("nan"), None), (pd.NaT, None), ("", None),
])
def test_data_dia_mes_ano_e_vazio_vira_none(entrada, esperado):
    assert cs._data_planilha(entrada) == esperado


@pytest.mark.parametrize("entrada,fracao,esperado", [
    ("2,5%", True, Decimal("2.50")), (2.5, True, Decimal("2.50")), (0.025, True, Decimal("2.50")),
    (0.025, False, Decimal("0.03")), ("1,85 %", False, Decimal("1.85")), (None, True, None),
])
def test_taxa(entrada, fracao, esperado):
    assert cs._taxa_planilha(entrada, fracao) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    (None, (1, 1)), (1, (1, 1)), (2.0, (2, 2)), ("1/3", (1, 3)), ("01/03", (1, 3)), ("1 de 3", (1, 3)),
])
def test_parcela(entrada, esperado):
    assert cs._parcela_planilha(entrada) == esperado


@pytest.mark.parametrize("entrada,esperado", [
    ("Boleto", FormaPagamento.boleto), ("Cheque", FormaPagamento.cheque), ("Débito", FormaPagamento.cartao_debito),
    ("Cartão de Débito", FormaPagamento.cartao_debito), ("Cartão de crédito", FormaPagamento.cartao_credito),
    ("Transferência bancária", FormaPagamento.transferencia), ("PIX", FormaPagamento.pix),
    ("Débito automático", FormaPagamento.debito_automatico), ("Dinheiro", FormaPagamento.dinheiro),
])
def test_formas_com_acento(db, entrada, esperado):
    _, ocorrencias, (at,) = importar(db, [{"data": "2026-06-05", "valor": 10, "forma_pagamento": entrada}])
    assert at.forma_pagamento == esperado
    assert ocorrencias == []


# --- Importação ------------------------------------------------------------------

def test_datas_opcionais_vazias_ficam_none_e_nao_nat(db):
    total, _, (at,) = importar(db, [{
        "data_atendimento": "05/06/2026", "valor_servico": 100,
        "data_prevista_recebimento": float("nan"), "data_credito": pd.NaT,
    }])
    assert total == 1
    assert at.data_credito is None
    assert at.data_prevista_recebimento == date(2026, 6, 5)


def test_linhas_invalidas_sao_ignoradas_com_motivo_e_numero_da_linha(db):
    total, ocorrencias, ats = importar(db, [
        {"data": "05/06/2026", "valor": "350,00"},
        {"data": "31/02/2026", "valor": 10},
        {"data": "06/06/2026", "valor": "abc"},
        {"data": "07/06/2026", "valor": -50},
        {"data": None, "valor": None},
    ])
    assert total == 1 and ats[0].valor_servico == Decimal("350.00")
    assert len(ocorrencias) == 3
    assert ocorrencias[0].startswith("[FLIC-IMP-101] Linha 3:") and "data inválida" in ocorrencias[0]
    assert ocorrencias[1].startswith("[FLIC-IMP-102] Linha 4:") and "valor inválido" in ocorrencias[1]
    assert ocorrencias[2].startswith("[FLIC-IMP-103] Linha 5:") and "maior que zero" in ocorrencias[2]


def test_forma_desconhecida_fica_em_branco_e_avisada(db):
    _, ocorrencias, (at, sem_forma) = importar(db, [
        {"data": "2026-06-05", "valor": 10, "forma_pagamento": "Permuta"},
        {"data": "2026-06-05", "valor": 10},
    ])
    assert at.forma_pagamento is None and sem_forma.forma_pagamento is None
    assert ocorrencias == ['[FLIC-IMP-104] Linha 2: forma de pagamento "Permuta" não reconhecida; ficou em branco.']


def test_plano_numerico_e_inexistente(db):
    _, ocorrencias, (dez, nome, ausente) = importar(db, [
        {"data": "2026-06-05", "valor": 10, "plano_de_contas": 20.1},
        {"data": "2026-06-05", "valor": 10, "plano_de_contas": "consulta"},
        {"data": "2026-06-05", "valor": 10, "plano_de_contas": "99.99"},
    ])
    assert dez.plano_conta.codigo == "20.10"
    assert nome.plano_conta.codigo == "20.01"
    assert ausente.plano_conta_id is None
    assert ocorrencias == ['[FLIC-IMP-105] Linha 4: plano de contas "99.99" não encontrado; ficou sem plano.']


def test_campo_opcional_invalido_nao_derruba_a_linha(db):
    _, ocorrencias, (at,) = importar(db, [{"data": "2026-06-05", "valor": 10, "data_credito": "32/13/2026",
                                           "parcela": "1 de 3", "cpf_paciente": 1234567890}])
    assert at.data_credito is None and (at.parcela_numero, at.parcela_total) == (1, 3)
    assert at.cpf_paciente == "01234567890"
    assert ocorrencias[0].startswith("[FLIC-IMP-106]") and "data do crédito inválido(a)" in ocorrencias[0]


def test_modelo_de_lote_continua_importando(db):
    total, ocorrencias, ats = importar(db, pd.read_excel("static/modelos/modelo_lancamentos_lote.xlsx").to_dict("records"))
    assert total == 2 and ocorrencias == []
    assert [a.forma_pagamento for a in ats] == [FormaPagamento.pix, FormaPagamento.cartao_credito]


# --- Leitores e rotas --------------------------------------------------------------

def preencher_bpo(tmp_path, linhas):
    caminho = tmp_path / "bpo.xlsx"
    shutil.copy("static/modelos/modelo_bpo_receitas.xlsx", caminho)
    wb = openpyxl.load_workbook(caminho)
    ws = wb["RECEITA"]
    cab = [c.value for c in ws[6]]
    for r, dados in enumerate(linhas, start=7):
        for i, coluna in enumerate(cab, start=1):
            if coluna in dados:
                ws.cell(r, i, dados[coluna])
    wb.save(caminho)
    return str(caminho)


def test_bpo_com_datas_vazias_taxas_e_numero_de_linha(db, tmp_path):
    caminho = preencher_bpo(tmp_path, [
        {"Data do atendimento": "05/06/2026", "Valor do serviço": "450,00", "Forma de pagamento": "PIX"},
        {"Data do atendimento": "20/06/2026", "Valor do serviço": 300, "Taxa do cartão": 0.0185,
         "Forma de pagamento": "Cartão de crédito"},
        {"Data do atendimento": "21/06/2026", "Valor do serviço": 300, "Taxa do cartão": "1,85%"},
        {"Data do atendimento": "21/06/2026", "Valor do serviço": "xx"},
    ])
    ocorrencias = []
    total = cs.importar_lancamentos(db, 1, cs.ler_planilha_bpo_receitas(caminho), substituir_pendentes=False,
                                    linha_inicial=7, ocorrencias=ocorrencias, taxa_fracao_automatica=False)
    ats = db.query(Atendimento).order_by(Atendimento.id).all()
    assert total == 3
    assert ats[0].data_atendimento == date(2026, 6, 5) and ats[0].data_credito is None
    assert ats[1].taxa_cartao == Decimal("1.85") and ats[2].taxa_cartao == Decimal("1.85")
    assert ocorrencias[0].startswith("[FLIC-IMP-102] Linha 10:")


def test_visao_com_datas_vazias(db, tmp_path):
    caminho = tmp_path / "visao.xlsx"
    shutil.copy("static/modelos/modelo_visao_contas_receber.xlsx", caminho)
    wb = openpyxl.load_workbook(caminho)
    ws = wb.worksheets[0]
    cab = [c.value for c in ws[1]]
    ws.append([{"Nome do cliente": "Ana", "Data de competência": "05/06/2026", "Valor original da parcela (R$)": "1.200,00",
                "Forma de recebimento": "Transferência bancária"}.get(c) for c in cab])
    wb.save(caminho)
    total = cs.importar_lancamentos(db, 1, cs.ler_visao_contas_a_receber(str(caminho)), substituir_pendentes=False)
    (at,) = db.query(Atendimento).all()
    assert total == 1 and at.valor_servico == Decimal("1200.00")
    assert at.forma_pagamento == FormaPagamento.transferencia and at.data_credito is None


def _chamar_rota(db, monkeypatch, tmp_path, funcao, arquivo):
    async def upload(*args, **kwargs):
        destino = tmp_path / ("upload-" + arquivo.split("/")[-1].split("\\")[-1])
        shutil.copy(arquivo, destino)
        return str(destino), "planilha.xlsx", ".xlsx"
    monkeypatch.setattr("app.utils.salvar_upload_temporario", upload)
    request = Request({"type": "http", "method": "POST", "scheme": "http", "server": ("testserver", 80),
                       "path": "/lancamentos/importar", "headers": [], "query_string": b""})
    response = asyncio.run(funcao(request=request, cliente_id=1, arquivo=SimpleNamespace(filename="planilha.xlsx"),
                                  db=db, usuario=db.get(Usuario, 1)))
    flash = parse_qs(urlparse(response.headers["location"]).query)["flash"][0]
    return response, flash


def test_rota_de_lote_nao_da_mais_erro_500(db, monkeypatch, tmp_path):
    response, flash = _chamar_rota(db, monkeypatch, tmp_path, lancamentos.importar_planilha_lancamentos,
                                   "static/modelos/modelo_lancamentos_lote.xlsx")
    assert response.status_code == 303
    assert "cliente_ativo=1" in response.headers["set-cookie"]
    assert flash == "2 lançamento(s) importado(s)."


def test_rota_mostra_linhas_ignoradas(db, monkeypatch, tmp_path):
    caminho = preencher_bpo(tmp_path, [{"Data do atendimento": "05/06/2026", "Valor do serviço": "abc"}])
    _, flash = _chamar_rota(db, monkeypatch, tmp_path, lancamentos.importar_planilha_bpo_atualizado, caminho)
    assert flash.startswith("0 lançamento(s) importado(s)")
    assert "[FLIC-IMP-102] Linha 7: ignorada — valor inválido (abc)." in flash


def test_rota_mostra_erro_de_formato_do_arquivo(db, monkeypatch, tmp_path):
    caminho = tmp_path / "sem_aba.xlsx"
    openpyxl.Workbook().save(caminho)
    _, flash = _chamar_rota(db, monkeypatch, tmp_path, lancamentos.importar_planilha_bpo_atualizado, str(caminho))
    assert flash == "[FLIC-IMP-001] A planilha não contém a aba RECEITA esperada."


def test_mensagem_limita_avisos():
    msg = lancamentos._mensagem_importacao("1 importado.", [f"Linha {i}: x." for i in range(8)])
    assert "Linha 4: x." in msg and "Linha 5: x." not in msg and "(e mais 3 aviso(s))" in msg


# --- Leitura de CSV --------------------------------------------------------------------

@pytest.mark.parametrize("conteudo", [
    "data,valor,taxa,digitos\n2026-05-28,350.00,2.50,0123\n2026-05-29,1234.5,3,4521\n",
    "data;valor;taxa;digitos\n2026-05-28;350,00;2,50;0123\n2026-05-29;1.234,50;3;4521\n",
    "data\tvalor\ttaxa\tdigitos\n2026-05-28\t350,00\t2,5\t0123\n2026-05-29\t1234,50\t3\t4521\n",
])
def test_csv_ponto_ou_virgula_decimal_e_separadores(tmp_path, conteudo):
    caminho = tmp_path / "extrato.csv"
    caminho.write_text(conteudo, encoding="utf-8")
    df = cs.ler_csv(str(caminho))
    assert list(df["valor"]) == [350.0, 1234.5]
    assert list(df["taxa"]) == [2.5, 3]
    assert list(df["digitos"]) == ["0123", "4521"]  # zero à esquerda preservado
    assert list(df["data"]) == ["2026-05-28", "2026-05-29"]


def test_csv_latin1_do_excel(tmp_path):
    caminho = tmp_path / "excel.csv"
    caminho.write_bytes("descrição;valor\nConsulta São José;350,00\n".encode("latin-1"))
    df = cs.ler_csv(str(caminho))
    assert list(df.columns) == ["descrição", "valor"] and df["valor"][0] == 350.0


@pytest.mark.parametrize("texto,esperado", [
    ("350.00", 350.0), ("350,00", 350.0), ("1.234,56", 1234.56), ("1,234.56", 1234.56),
    ("1.234", 1234), ("2.5", 2.5), ("10", 10), ("-45,10", -45.1),
])
def test_numero_csv(texto, esperado):
    assert cs._numero_csv(texto) == esperado


def test_csv_da_maquininha_com_ponto_decimal_mantem_valores(tmp_path):
    caminho = tmp_path / "maquininha.csv"
    caminho.write_text(
        "data_venda,data_pagamento,valor_bruto,taxa_percentual\n"
        "2026-05-28,2026-05-29,350.00,2.50\n",
        encoding="utf-8",
    )
    df = cs.ler_arquivo_extrato(str(caminho))
    assert df["valor_bruto"].iloc[0] == 350.0 and df["taxa_percentual"].iloc[0] == 2.5


# --- Reimportação não duplica --------------------------------------------------------------

def test_reimportar_lancamentos_nao_duplica_mas_aceita_repeticao_no_arquivo(db):
    linhas = [
        {"data": "2026-06-05", "valor": 350, "nome_paciente": "Ana"},
        {"data": "2026-06-05", "valor": 350, "nome_paciente": "Ana"},  # duas consultas iguais no mesmo dia
        {"data": "2026-06-06", "valor": 200, "nome_paciente": "Bruno"},
    ]
    total, ocorrencias, _ = importar(db, linhas)
    assert total == 3 and ocorrencias == []
    total, ocorrencias, ats = importar(db, linhas)
    assert total == 0 and len(ats) == 3
    assert ocorrencias == ["[FLIC-IMP-107] 3 linha(s) já importada(s) anteriormente foram ignoradas para não duplicar."]
    total, _, ats = importar(db, linhas + [{"data": "2026-06-05", "valor": 350, "nome_paciente": "Ana"}])
    assert total == 1 and len(ats) == 4  # a 3ª consulta igual é nova


def test_reimportar_extrato_pix_ted_nao_duplica(db):
    from app.models import ContaBancaria, MovimentacaoBancaria, TipoContaBancaria
    db.add(ContaBancaria(id=1, cliente_id=1, nome="Conta", tipo=TipoContaBancaria.bancaria))
    db.commit()
    df = pd.DataFrame([{"data": "2026-05-21", "valor": 310.0, "descricao": "PIX Ricardo"},
                       {"data": "2026-05-24", "valor": -250.0, "descricao": "Pagamento"}])
    assert cs.importar_movimentacoes_bancarias(db, 1, df, "a.csv", conta_bancaria_id=1)["importados"] == 2
    res = cs.importar_movimentacoes_bancarias(db, 1, df, "a.csv", conta_bancaria_id=1)
    assert res["importados"] == 0 and res["repetidos"] == 2 and res["aviso"].startswith("[FLIC-IMP-107]")
    assert db.query(MovimentacaoBancaria).count() == 2


def test_reimportar_conta_corrente_e_vendas_nao_duplica(db):
    from app.models import ExtratoLinhaBancaria, VendaCartao
    extrato = pd.DataFrame([{"data": "2026-05-20", "valor": 350.0, "descricao": "PIX João"}])
    cs.importar_extrato_conta_corrente(db, 1, extrato, "cc.xlsx")
    assert cs.importar_extrato_conta_corrente(db, 1, extrato, "cc.xlsx")["importados"] == 0
    assert db.query(ExtratoLinhaBancaria).count() == 1

    vendas = pd.DataFrame([{"data_venda": "2026-05-28", "data_pagamento": "2026-05-29", "valor_bruto": 350.0,
                            "ultimos_digitos": "4521", "parcelas": 1}])
    assert cs.importar_vendas_cartao(db, 1, vendas, "maq.xlsx") == 1
    est = {}
    assert cs.importar_vendas_cartao(db, 1, vendas, "maq.xlsx", estatisticas=est) == 0
    assert est["repetidos"] == 1 and db.query(VendaCartao).count() == 1


def test_conciliacoes_nao_apagam_lancamentos_pendentes():
    from pathlib import Path
    for arquivo in ("app/routers/conciliacao.py", "app/routers/conciliacao_banco.py"):
        codigo = Path(arquivo).read_text(encoding="utf-8")
        assert "importar_lancamentos(db, cliente_id, df)" not in codigo
        assert "substituir_pendentes=False" in codigo


def test_reimportar_contas_a_pagar_nao_duplica(db, monkeypatch, tmp_path):
    from app.models import ContaPagar
    from app.routers import contas_pagar
    monkeypatch.setattr(contas_pagar, "_log", lambda *a, **kw: None)
    origem = tmp_path / "contas.xlsx"
    shutil.copy("static/modelos/modelo_contas_pagar.xlsx", origem)
    wb = openpyxl.load_workbook(origem)
    ws = wb["Contas a pagar"]
    cab = [c.value for c in ws[1]]
    for dados in [
        {"descricao": "Aluguel", "valor": 3200, "vencimento": "10/11/2026", "recorrente": "sim",
         "recorrencia_intervalo": "mensal", "recorrencia_qtd": 3},
        {"descricao": "Energia", "fornecedor": "Enel", "valor": "540,90", "vencimento": "15/11/2026"},
    ]:
        ws.append([dados.get(c) for c in cab])
    wb.save(origem)

    async def upload(*args, **kwargs):
        destino = tmp_path / "upload.xlsx"
        shutil.copy(origem, destino)
        return str(destino), "contas.xlsx", ".xlsx"
    monkeypatch.setattr(contas_pagar, "salvar_upload_temporario", upload)
    request = Request({"type": "http", "method": "POST", "scheme": "http", "server": ("testserver", 80),
                       "path": "/contas-pagar/importar", "headers": [], "query_string": b""})

    def importar_arquivo():
        resposta = asyncio.run(contas_pagar.importar_contas(request=request, cliente_id=1,
                               arquivo=SimpleNamespace(filename="contas.xlsx"), db=db, usuario=db.get(Usuario, 1)))
        return parse_qs(urlparse(resposta.headers["location"]).query)["flash"][0]

    assert importar_arquivo() == "4 conta(s) importada(s) de 'contas.xlsx'."
    assert importar_arquivo().startswith("0 conta(s) importada(s) de 'contas.xlsx'. [FLIC-IMP-107] 4 linha(s)")
    assert db.query(ContaPagar).count() == 4
