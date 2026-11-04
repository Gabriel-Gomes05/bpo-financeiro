"""Editor: na operação vê só os clientes designados a ele; no cadastro vê todos e pode se designar."""
import asyncio
import inspect
from datetime import date

import pytest
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import ClienteBPO, HistoricoAlteracao, PerfilUsuario, Usuario
from app.routers import (
    admin, auditoria, cliente_ativo, conciliacao, conciliacao_banco, contas_pagar,
    contas_pagar_conciliacao, fechamento, gestao, lancamentos, secretarias,
)
from app.services import tarefas_service

COORD, EDITOR, OUTRO_EDITOR, FUNC = 1, 2, 3, 4
DO_EDITOR, DO_FUNC, SEM_RESP = 10, 20, 30


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    for modulo in (admin, secretarias):
        monkeypatch.setattr(modulo, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=COORD, nome="Coord", email="c@x.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            Usuario(id=EDITOR, nome="Edu", email="e@x.test", senha_hash="x", perfil=PerfilUsuario.editor),
            Usuario(id=OUTRO_EDITOR, nome="Eva", email="e2@x.test", senha_hash="x", perfil=PerfilUsuario.editor),
            Usuario(id=FUNC, nome="Fábio", email="f@x.test", senha_hash="x", perfil=PerfilUsuario.funcionario),
        ])
        session.flush()
        session.add_all([
            ClienteBPO(id=DO_EDITOR, nome="Clínica do Edu", funcionario_id=EDITOR),
            ClienteBPO(id=DO_FUNC, nome="Clínica do Fábio", funcionario_id=FUNC),
            ClienteBPO(id=SEM_RESP, nome="Clínica sem responsável"),
        ])
        session.commit()
        yield session
    engine.dispose()


def u(db, uid):
    return db.get(Usuario, uid)


def chamar(funcao, **kwargs):
    params = {}
    for nome, param in inspect.signature(funcao).parameters.items():
        if param.default is not inspect.Parameter.empty:
            params[nome] = getattr(param.default, "default", param.default)
    params.update(kwargs)
    return asyncio.run(funcao(**params))


def req(path="/", referer=""):
    headers = [(b"referer", referer.encode())] if referer else []
    return Request({"type": "http", "method": "GET", "scheme": "http", "server": ("testserver", 80),
                    "path": path, "headers": headers, "query_string": b"", "client": ("127.0.0.1", 1)})


MODULOS_OPERACIONAIS = [lancamentos, conciliacao, conciliacao_banco, contas_pagar,
                        contas_pagar_conciliacao, fechamento, gestao]


@pytest.mark.parametrize("modulo", MODULOS_OPERACIONAIS, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_editor_opera_so_os_clientes_designados(db, modulo):
    assert {c.id for c in modulo.clientes_do_usuario(db, u(db, EDITOR))} == {DO_EDITOR}
    assert {c.id for c in modulo.clientes_do_usuario(db, u(db, OUTRO_EDITOR))} == set()
    assert {c.id for c in modulo.clientes_do_usuario(db, u(db, COORD))} == {DO_EDITOR, DO_FUNC, SEM_RESP}


def test_painel_e_tarefas_do_editor_listam_so_os_designados(db):
    resposta = chamar(cliente_ativo.painel_geral, request=req("/painel"), db=db, usuario=u(db, EDITOR))
    assert [c.id for c in resposta.context["clientes"]] == [DO_EDITOR]
    assert [c.id for c in tarefas_service.clientes_permitidos(db, u(db, EDITOR))] == [DO_EDITOR]


@pytest.mark.parametrize("cliente_id,autorizado", [(DO_EDITOR, True), (DO_FUNC, False), (SEM_RESP, False)])
def test_editor_so_entra_em_cliente_designado(db, cliente_id, autorizado):
    resposta = chamar(cliente_ativo.selecionar_cliente, request=req(referer="http://testserver/lancamentos"),
                      cliente_id=str(cliente_id), db=db, usuario=u(db, EDITOR))
    assert ("cliente_ativo=" + str(cliente_id) in resposta.headers.get("set-cookie", "")) is autorizado
    if not autorizado:
        assert resposta.headers["location"] == "/painel"


def test_cadastro_de_clientes_continua_mostrando_todos_ao_editor(db):
    resposta = chamar(admin.pagina_clientes, request=req("/admin/clientes"), db=db, usuario=u(db, EDITOR))
    assert {c.id for c in resposta.context["clientes"]} == {DO_EDITOR, DO_FUNC, SEM_RESP}
    assert resposta.context["pode_atribuir"] is True
    assert [f.id for f in resposta.context["funcionarios"]] == [EDITOR]


def editar_responsavel(db, uid, cliente_id, funcionario_id):
    cliente = db.get(ClienteBPO, cliente_id)
    return chamar(admin.editar_cliente_completo, cliente_id=cliente_id, nome=cliente.nome,
                  funcionario_id=funcionario_id, db=db, usuario=u(db, uid))


def test_editor_se_designa_a_outro_cliente(db):
    editar_responsavel(db, EDITOR, SEM_RESP, EDITOR)
    editar_responsavel(db, EDITOR, DO_FUNC, EDITOR)
    db.expire_all()
    assert db.get(ClienteBPO, SEM_RESP).funcionario_id == EDITOR
    assert db.get(ClienteBPO, DO_FUNC).funcionario_id == EDITOR
    assert {c.id for c in lancamentos.clientes_do_usuario(db, u(db, EDITOR))} == {DO_EDITOR, DO_FUNC, SEM_RESP}


def test_editor_nao_designa_outra_pessoa_nem_tira_cliente_dos_outros(db):
    editar_responsavel(db, EDITOR, SEM_RESP, FUNC)
    editar_responsavel(db, EDITOR, DO_FUNC, None)
    editar_responsavel(db, EDITOR, DO_FUNC, OUTRO_EDITOR)
    db.expire_all()
    assert db.get(ClienteBPO, SEM_RESP).funcionario_id is None
    assert db.get(ClienteBPO, DO_FUNC).funcionario_id == FUNC


def test_editor_pode_se_retirar_do_proprio_cliente(db):
    editar_responsavel(db, EDITOR, DO_EDITOR, None)
    db.expire_all()
    assert db.get(ClienteBPO, DO_EDITOR).funcionario_id is None


def test_coordenador_designa_editor_e_funcionario(db):
    editar_responsavel(db, COORD, SEM_RESP, OUTRO_EDITOR)
    db.expire_all()
    assert db.get(ClienteBPO, SEM_RESP).funcionario_id == OUTRO_EDITOR
    resposta = chamar(admin.pagina_clientes, request=req("/admin/clientes"), db=db, usuario=u(db, COORD))
    assert {f.id for f in resposta.context["funcionarios"]} == {EDITOR, OUTRO_EDITOR, FUNC}


def test_editor_cria_cliente_ja_designado_a_si(db):
    chamar(admin.criar_cliente, nome="Nova clínica", funcionario_id=EDITOR, db=db, usuario=u(db, EDITOR))
    chamar(admin.criar_cliente, nome="Outra clínica", funcionario_id=FUNC, db=db, usuario=u(db, EDITOR))
    assert db.query(ClienteBPO).filter_by(nome="Nova clínica").one().funcionario_id == EDITOR
    assert db.query(ClienteBPO).filter_by(nome="Outra clínica").one().funcionario_id is None


def test_secretarias_do_editor_so_dos_clientes_dele(db):
    db.add_all([
        Usuario(id=50, nome="Sec Edu", email="s1@x.test", senha_hash="x", perfil=PerfilUsuario.secretaria, cliente_id=DO_EDITOR),
        Usuario(id=51, nome="Sec Fábio", email="s2@x.test", senha_hash="x", perfil=PerfilUsuario.secretaria, cliente_id=DO_FUNC),
    ])
    db.commit()
    tela = chamar(secretarias.pagina_secretarias, request=req("/admin/secretarias"), db=db, usuario=u(db, EDITOR))
    assert [s.id for s in tela.context["secretarias"]] == [50]
    assert [c.id for c in tela.context["clientes_ativos"]] == [DO_EDITOR]
    criada = chamar(secretarias.criar_secretaria, nome="X", email="x@x.test", senha="segredo1",
                    cliente_id=str(DO_FUNC), db=db, usuario=u(db, EDITOR))
    assert "erro=cliente_obrigatorio" in criada.headers["location"]
    alheia = chamar(secretarias.alternar_secretaria, usuario_id=51, db=db, usuario=u(db, EDITOR))
    assert "erro=usuario_nao_encontrado" in alheia.headers["location"]
    assert db.get(Usuario, 51).ativo is True


def test_auditoria_do_editor_so_dos_clientes_dele(db):
    db.add(Usuario(id=50, nome="Sec", email="s@x.test", senha_hash="x", perfil=PerfilUsuario.secretaria, cliente_id=DO_EDITOR))
    db.flush()
    import uuid
    for cliente_id in (DO_EDITOR, DO_FUNC):
        db.add(HistoricoAlteracao(operacao_id=uuid.uuid4(), usuario_id=50, usuario_nome="Sec", cliente_id=cliente_id,
                                  acao="edicao", modulo="contas_receber", entidade="lancamento", entidade_id=1,
                                  campo="Valor", valor_anterior="R$ 1,00", valor_novo="R$ 2,00"))
    db.commit()
    tela = chamar(auditoria.historico_alteracoes, request=req("/auditoria/historico"), db=db, usuario=u(db, EDITOR))
    assert [op["linha"].cliente_id for op in tela.context["operacoes"]] == [DO_EDITOR]
    assert [c.id for c in tela.context["clientes_filtro"]] == [DO_EDITOR]
    tela = chamar(auditoria.historico_alteracoes, request=req("/auditoria/historico"), db=db, usuario=u(db, COORD))
    assert len(tela.context["operacoes"]) == 2


def test_editor_ve_so_tarefas_dos_clientes_dele_e_as_pessoais(db):
    from app.models import Tarefa
    from app.routers import tarefas as rotas_tarefas
    db.add_all([
        Tarefa(id=1, titulo="Do cliente do Edu", responsavel_id=FUNC, criado_por_id=COORD, cliente_id=DO_EDITOR),
        Tarefa(id=2, titulo="Do cliente do Fábio", responsavel_id=FUNC, criado_por_id=COORD, cliente_id=DO_FUNC),
        Tarefa(id=3, titulo="Do Fábio, mas atribuída ao Edu", responsavel_id=EDITOR, criado_por_id=COORD, cliente_id=DO_FUNC),
        Tarefa(id=4, titulo="Pessoal do Edu", responsavel_id=EDITOR, criado_por_id=EDITOR),
        Tarefa(id=5, titulo="Pessoal da Eva", responsavel_id=OUTRO_EDITOR, criado_por_id=OUTRO_EDITOR),
        Tarefa(id=6, titulo="Criada pelo Edu para o Fábio", responsavel_id=FUNC, criado_por_id=EDITOR),
    ])
    db.commit()
    visiveis = {t.id for t in tarefas_service.tarefas_visiveis(db, u(db, EDITOR))}
    assert visiveis == {1, 4, 6}
    assert {t.id for t in tarefas_service.tarefas_visiveis(db, u(db, COORD))} == {1, 2, 3, 4, 5, 6}
    assert {t.id for t in tarefas_service.tarefas_visiveis(db, u(db, FUNC))} == {1, 2, 6}

    tela = chamar(rotas_tarefas.listar_tarefas, request=req("/tarefas"), db=db, usuario=u(db, EDITOR))
    assert {t.id for t in tela.context["tarefas"]} == {1, 4, 6}
    from app.errors import ErroFlic
    with pytest.raises(ErroFlic):  # tarefa de cliente alheio não abre nem pelo ID
        rotas_tarefas._obter(db, u(db, EDITOR), 2)
