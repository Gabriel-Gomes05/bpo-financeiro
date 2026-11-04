"""Fechamento de período: extrato bancário em PDF obrigatório e consulta só por admin e editor."""
import asyncio
import inspect
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from fastapi import Request, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app import utils
from app.authorization import Permission, has_permission
from app.database import Base
from app.errors import ErroFlic
from app.models import (
    ClienteBPO, ContaBancaria, ContaPagar, ExtratoPeriodoFechado, PerfilUsuario, PeriodoFechado,
    StatusContaPagar, TipoContaBancaria, Usuario,
)
from app.routers import auditoria, fechamento

COORD, EDITOR, FUNC, MEDICO = 1, 2, 3, 4
DO_EDITOR, OUTRO = 10, 20
PDF = b"%PDF-1.4\n% extrato\n%%EOF\n"


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setattr(utils, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(auditoria, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(fechamento, "_log", lambda *a, **kw: None)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=COORD, nome="Coord", email="c@x.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            Usuario(id=EDITOR, nome="Edu", email="e@x.test", senha_hash="x", perfil=PerfilUsuario.editor),
            Usuario(id=FUNC, nome="Fábio", email="f@x.test", senha_hash="x", perfil=PerfilUsuario.funcionario),
            Usuario(id=MEDICO, nome="Dr.", email="m@x.test", senha_hash="x", perfil=PerfilUsuario.medico),
        ])
        session.flush()
        session.add_all([
            ClienteBPO(id=DO_EDITOR, nome="Clínica do Edu", funcionario_id=EDITOR),
            ClienteBPO(id=OUTRO, nome="Clínica do Fábio", funcionario_id=FUNC),
            ContaBancaria(id=5, cliente_id=DO_EDITOR, nome="Itaú", tipo=TipoContaBancaria.bancaria, banco="Itaú"),
            ContaPagar(cliente_id=DO_EDITOR, descricao="Aluguel", valor=Decimal("800"), vencimento=date(2026, 10, 5),
                       data_pagamento=date(2026, 10, 5), status=StatusContaPagar.pago),
        ])
        session.commit()
        yield session
    engine.dispose()


def u(db, uid):
    return db.get(Usuario, uid)


def req(cliente_id=DO_EDITOR, path="/fechamento/mensal/fechar"):
    headers = [(b"cookie", f"cliente_ativo={cliente_id}".encode())] if cliente_id else []
    return Request({"type": "http", "method": "POST", "scheme": "http", "server": ("testserver", 80),
                    "path": path, "headers": headers, "query_string": b"", "client": ("127.0.0.1", 1)})


def arquivo(nome="extrato.pdf", conteudo=PDF):
    return UploadFile(file=BytesIO(conteudo), filename=nome, headers=Headers({"content-type": "application/pdf"}))


def chamar(funcao, **kwargs):
    params = {}
    for nome, param in inspect.signature(funcao).parameters.items():
        if param.default is not inspect.Parameter.empty:
            params[nome] = getattr(param.default, "default", param.default)
    params.update(kwargs)
    return asyncio.run(funcao(**params))


def fechar(db, uid=EDITOR, cliente_id=DO_EDITOR, extratos=None, inicio="2026-10-01", fim="2026-10-31", **kw):
    return chamar(fechamento.fechar_periodo, request=req(cliente_id), data_inicio=inicio, data_fim=fim,
                  extratos=[arquivo()] if extratos is None else extratos, db=db, usuario=u(db, uid), **kw)


def test_fecha_periodo_com_extrato_pdf_guardado(db, tmp_path):
    resposta = fechar(db, conta_bancaria_id="5", observacao="Conferido com o extrato")
    assert "sucesso=periodo_fechado" in resposta.headers["location"]
    periodo = db.query(PeriodoFechado).one()
    assert (periodo.cliente_id, periodo.data_inicio, periodo.data_fim) == (DO_EDITOR, date(2026, 10, 1), date(2026, 10, 31))
    assert periodo.total_despesas == Decimal("800.00") and periodo.resultado == Decimal("-800.00")
    assert periodo.fechado_por_id == EDITOR and periodo.observacao == "Conferido com o extrato"
    extrato = db.query(ExtratoPeriodoFechado).one()
    assert extrato.nome_arquivo == "extrato.pdf" and extrato.conta_bancaria_id == 5
    with open(extrato.caminho, "rb") as f:
        assert f.read() == PDF
    assert extrato.caminho.startswith(str(tmp_path))


def test_varios_extratos_no_mesmo_fechamento(db):
    fechar(db, extratos=[arquivo("itau.pdf"), arquivo("bradesco.pdf")])
    assert sorted(e.nome_arquivo for e in db.query(ExtratoPeriodoFechado)) == ["bradesco.pdf", "itau.pdf"]


@pytest.mark.parametrize("extratos", [[], [arquivo(nome="")]])
def test_sem_extrato_nao_fecha(db, extratos):
    assert "erro=extrato_obrigatorio" in fechar(db, extratos=extratos).headers["location"]
    assert db.query(PeriodoFechado).count() == 0


@pytest.mark.parametrize("nome,conteudo", [("extrato.pdf", b"nao sou pdf"), ("extrato.png", b"\x89PNG\r\n\x1a\n"),
                                           ("extrato.pdf", b"")])
def test_extrato_que_nao_e_pdf_nao_fecha_e_nao_deixa_arquivo(db, tmp_path, nome, conteudo):
    resposta = fechar(db, extratos=[arquivo(), arquivo(nome, conteudo)])
    assert "erro=extrato_invalido" in resposta.headers["location"]
    assert db.query(PeriodoFechado).count() == 0
    assert list(tmp_path.iterdir()) == []


def test_periodo_sobreposto_ou_invalido(db):
    fechar(db)
    assert "erro=periodo_ja_fechado" in fechar(db, inicio="2026-10-15", fim="2026-11-15").headers["location"]
    assert "erro=periodo_invalido" in fechar(db, inicio="2026-12-31", fim="2026-12-01").headers["location"]
    assert "erro=periodo_invalido" in fechar(db, inicio="", fim="").headers["location"]
    assert "sucesso=periodo_fechado" in fechar(db, inicio="2026-11-01", fim="2026-11-30").headers["location"]
    assert db.query(PeriodoFechado).count() == 2


def test_funcionario_fecha_mas_medico_nao(db):
    assert "sucesso" in fechar(db, uid=FUNC, cliente_id=OUTRO).headers["location"]
    with pytest.raises(ErroFlic) as exc:
        fechar(db, uid=MEDICO)
    assert exc.value.codigo == "FLIC-AUT-002"


def test_nao_fecha_cliente_fora_do_acesso(db):
    with pytest.raises(ErroFlic) as exc:
        fechar(db, uid=EDITOR, cliente_id=OUTRO)
    assert exc.value.codigo == "FLIC-AUT-004"


# ------------------------------------------------------------------ consulta

def test_somente_admin_e_editor_consultam_extratos(db):
    assert has_permission(u(db, COORD), Permission.AUDITORIA) and has_permission(u(db, EDITOR), Permission.AUDITORIA)
    assert not has_permission(u(db, FUNC), Permission.AUDITORIA)
    assert fechamento.pode_consultar_extratos(u(db, EDITOR)) and not fechamento.pode_consultar_extratos(u(db, FUNC))


def baixar(db, uid, extrato_id):
    return chamar(auditoria.baixar_extrato, extrato_id=extrato_id, db=db, usuario=u(db, uid))


def test_admin_e_editor_baixam_o_pdf(db):
    fechar(db)
    extrato = db.query(ExtratoPeriodoFechado).one()
    for uid in (COORD, EDITOR):
        resposta = baixar(db, uid, extrato.id)
        assert resposta.media_type == "application/pdf" and resposta.path == extrato.caminho
        assert "inline" in resposta.headers["content-disposition"]


def test_editor_nao_baixa_extrato_de_cliente_alheio(db):
    fechar(db, uid=FUNC, cliente_id=OUTRO)
    extrato = db.query(ExtratoPeriodoFechado).one()
    with pytest.raises(ErroFlic) as exc:
        baixar(db, EDITOR, extrato.id)
    assert exc.value.codigo == "FLIC-FEC-005"
    assert baixar(db, COORD, extrato.id).path == extrato.caminho


def test_lista_de_extratos_respeita_os_clientes_do_editor(db):
    fechar(db)
    fechar(db, uid=FUNC, cliente_id=OUTRO)
    pedido = req(None, "/auditoria/extratos")
    editor = chamar(auditoria.extratos_de_fechamento, request=pedido, db=db, usuario=u(db, EDITOR))
    assert [p.cliente_id for p in editor.context["periodos"]] == [DO_EDITOR]
    admin = chamar(auditoria.extratos_de_fechamento, request=pedido, db=db, usuario=u(db, COORD))
    assert {p.cliente_id for p in admin.context["periodos"]} == {DO_EDITOR, OUTRO}
    assert "extrato.pdf" in admin.body.decode()


def test_tela_de_fechamento_mostra_periodo_fechado(db):
    fechar(db)
    pedido = req(DO_EDITOR, "/fechamento/mensal")
    tela = chamar(fechamento.fechamento_mensal, request=pedido, data_inicio="2026-10-01", data_fim="2026-10-31",
                  db=db, usuario=u(db, EDITOR))
    html = tela.body.decode()
    assert tela.context["periodo_atual"] is not None
    assert "Período fechado" in html and "/auditoria/extratos/" in html
    assert 'action="/fechamento/mensal/fechar"' not in html  # não fecha de novo
    func = chamar(fechamento.fechamento_mensal, request=req(OUTRO, "/fechamento/mensal"), data_inicio="2026-10-01",
                  data_fim="2026-10-31", db=db, usuario=u(db, FUNC))
    assert 'action="/fechamento/mensal/fechar"' in func.body.decode()
