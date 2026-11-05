"""Perfil Secretária: cadastro, permissões, isolamento por cliente e histórico de alterações."""
import asyncio
import inspect
import json
import re
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, Request
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import acesso_secretaria, auth
from app.acesso_secretaria import rota_liberada, verificar_acesso
from app.auth import verificar_senha
from app.authorization import Permission, has_permission
from app.database import Base
from app.errors import ErroFlic
from app.models import (
    Atendimento, CentroCusto, ClienteBPO, HistoricoAlteracao, PerfilUsuario, PlanoConta,
    StatusConciliacao, Usuario,
)
from app.routers import admin, auditoria, lancamentos, secretarias
from app.services import historico_service

ADMIN, EDITOR, FUNCIONARIO, MARIA = 1, 2, 3, 4
ABC, XYZ = 10, 20


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    for modulo in (lancamentos, secretarias, admin):
        monkeypatch.setattr(modulo, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            ClienteBPO(id=ABC, nome="Empresa ABC"),
            ClienteBPO(id=XYZ, nome="Empresa XYZ"),
        ])
        session.flush()
        session.add_all([
            Usuario(id=ADMIN, nome="Admin", email="admin@x.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            Usuario(id=EDITOR, nome="Edu", email="edu@x.test", senha_hash="x", perfil=PerfilUsuario.editor),
            Usuario(id=FUNCIONARIO, nome="Fábio", email="fabio@x.test", senha_hash="x", perfil=PerfilUsuario.funcionario),
            Usuario(id=MARIA, nome="Maria Silva", email="maria@x.test", senha_hash="x",
                    perfil=PerfilUsuario.secretaria, cliente_id=ABC),
            CentroCusto(id=1, cliente_id=ABC, nome="Dr. Ana", ativo=True),
        ])
        session.flush()
        session.get(ClienteBPO, ABC).funcionario_id = EDITOR  # ABC é designado ao editor; XYZ não
        session.add_all([
            PlanoConta(id=1, tipo="receita", grupo="Receitas", chave="consulta", nome="Consulta", ativo=True),
            Atendimento(id=152, cliente_id=ABC, data_atendimento=date(2026, 11, 3), valor_servico=Decimal("1500"),
                        condicao_pagamento="avista", nome_paciente="Paciente ABC"),
            Atendimento(id=200, cliente_id=XYZ, data_atendimento=date(2026, 11, 3), valor_servico=Decimal("90"),
                        condicao_pagamento="avista", nome_paciente="Paciente XYZ"),
        ])
        session.commit()
        yield session
    engine.dispose()


def u(db, uid):
    return db.get(Usuario, uid)


def requisicao(metodo="GET", caminho="/lancamentos", cookie=f"cliente_ativo={ABC}", query=b""):
    headers = [(b"cookie", cookie.encode())] if cookie else []
    req = Request({"type": "http", "method": metodo, "scheme": "http", "server": ("testserver", 80),
                   "path": caminho, "headers": headers, "query_string": query, "client": ("10.0.0.7", 5000)})
    req.state.request_id = "6f1c2f3e-0000-4000-8000-000000000001"
    return req


def chamar(funcao, **kwargs):
    params = {}
    for nome, param in inspect.signature(funcao).parameters.items():
        if param.default is not inspect.Parameter.empty:
            params[nome] = getattr(param.default, "default", param.default)
    params.update(kwargs)
    return asyncio.run(funcao(**params))


def como_secretaria(db, metodo="GET", caminho="/lancamentos"):
    """Passa pelo controle de acesso, como toda requisição autenticada da secretária."""
    req = requisicao(metodo, caminho)
    verificar_acesso(req, db, u(db, MARIA))
    return req


def historico(db, **filtros):
    return db.query(HistoricoAlteracao).filter_by(**filtros).order_by(HistoricoAlteracao.id).all()


def bloqueio(db, metodo, caminho):
    with pytest.raises(ErroFlic) as exc:
        verificar_acesso(requisicao(metodo, caminho), db, u(db, MARIA))
    return exc.value.codigo


# ------------------------------------------------------------------ cadastro

def criar_secretaria(db, por, **kwargs):
    dados = dict(nome="Joana", email="joana@x.test", senha="segredo1", cliente_id=str(ABC))
    dados.update(kwargs)
    return chamar(secretarias.criar_secretaria, db=db, usuario=u(db, por), **dados)


@pytest.mark.parametrize("por", [ADMIN, EDITOR])
def test_admin_e_editor_cadastram_secretaria_vinculada(db, por):
    resposta = criar_secretaria(db, por, email=" Joana@X.test ")
    assert resposta.headers["location"] == "/admin/secretarias?sucesso=criada"
    nova = db.query(Usuario).filter_by(email="joana@x.test").one()
    assert nova.perfil == PerfilUsuario.secretaria and nova.cliente_id == ABC and nova.ativo
    assert nova.senha_hash.startswith("$2") and verificar_senha("segredo1", nova.senha_hash)


def test_somente_admin_e_editor_gerenciam_secretarias():
    def perfil(p):
        return Usuario(perfil=p)
    assert has_permission(perfil(PerfilUsuario.coordenador), Permission.SECRETARIAS)
    assert has_permission(perfil(PerfilUsuario.editor), Permission.SECRETARIAS)
    for p in (PerfilUsuario.funcionario, PerfilUsuario.secretaria, PerfilUsuario.medico):
        assert not has_permission(perfil(p), Permission.SECRETARIAS)
        assert not has_permission(perfil(p), Permission.AUDITORIA)


@pytest.mark.parametrize("cliente_id", ["", "999", "abc"])
def test_cadastro_sem_cliente_valido_e_recusado(db, cliente_id):
    resposta = criar_secretaria(db, ADMIN, cliente_id=cliente_id)
    assert "erro=cliente_obrigatorio" in resposta.headers["location"]
    assert db.query(Usuario).filter_by(email="joana@x.test").count() == 0


def test_cadastro_com_cliente_inativo_e_recusado(db):
    db.get(ClienteBPO, XYZ).ativo = False
    db.commit()
    assert "erro=cliente_obrigatorio" in criar_secretaria(db, ADMIN, cliente_id=str(XYZ)).headers["location"]


def test_cadastro_com_email_existente_e_recusado(db):
    resposta = criar_secretaria(db, EDITOR, email="MARIA@x.test")
    assert "erro=email_duplicado" in resposta.headers["location"]
    assert db.query(Usuario).filter_by(perfil=PerfilUsuario.secretaria).count() == 1


def test_cadastro_com_senha_curta_e_recusado(db):
    assert "erro=senha_curta" in criar_secretaria(db, ADMIN, senha="123").headers["location"]


def test_edicao_dos_dados_troca_cliente_e_senha_e_encerra_sessao(db):
    versao = u(db, MARIA).auth_version
    resposta = chamar(secretarias.editar_secretaria, usuario_id=MARIA, nome="Maria S.", email="maria2@x.test",
                      cliente_id=str(XYZ), senha="novasenha", db=db, usuario=u(db, ADMIN))
    assert resposta.headers["location"] == "/admin/secretarias?sucesso=editada"
    maria = u(db, MARIA)
    assert (maria.nome, maria.email, maria.cliente_id) == ("Maria S.", "maria2@x.test", XYZ)
    assert verificar_senha("novasenha", maria.senha_hash)
    assert maria.auth_version == versao + 1


def test_edicao_nao_remove_o_vinculo(db):
    resposta = chamar(secretarias.editar_secretaria, usuario_id=MARIA, nome="Maria", email="maria@x.test",
                      cliente_id="", db=db, usuario=u(db, ADMIN))
    assert "erro=cliente_obrigatorio" in resposta.headers["location"]
    assert u(db, MARIA).cliente_id == ABC


def test_editor_nao_edita_usuario_que_nao_e_secretaria(db):
    resposta = chamar(secretarias.editar_secretaria, usuario_id=ADMIN, nome="X", email="admin@x.test",
                      cliente_id=str(ABC), db=db, usuario=u(db, EDITOR))
    assert "erro=usuario_nao_encontrado" in resposta.headers["location"]
    assert u(db, ADMIN).perfil == PerfilUsuario.coordenador and u(db, ADMIN).cliente_id is None


def test_desativacao_e_reativacao(db):
    chamar(secretarias.alternar_secretaria, usuario_id=MARIA, db=db, usuario=u(db, ADMIN))
    assert u(db, MARIA).ativo is False
    chamar(secretarias.alternar_secretaria, usuario_id=MARIA, db=db, usuario=u(db, EDITOR))
    assert u(db, MARIA).ativo is True


def test_cadastro_de_funcionarios_nao_cria_secretaria_sem_cliente(db):
    resposta = chamar(admin.criar_usuario, nome="Sem vínculo", email="sv@x.test", senha="segredo1",
                      perfil="secretaria", db=db, _=u(db, ADMIN))
    assert "erro=usar_tela_secretarias" in resposta.headers["location"]
    resposta = chamar(admin.editar_usuario, usuario_id=FUNCIONARIO, nome="Fábio", email="fabio@x.test",
                      perfil="secretaria", db=db, coordenador=u(db, ADMIN))
    assert "erro=usar_tela_secretarias" in resposta.headers["location"]
    assert u(db, FUNCIONARIO).perfil == PerfilUsuario.funcionario


# ------------------------------------------------------------------ permissões

@pytest.mark.parametrize("metodo,caminho", [
    ("GET", "/lancamentos"), ("GET", "/lancamentos/novo"), ("POST", "/lancamentos"),
    ("GET", "/lancamentos/152/editar"), ("POST", "/lancamentos/152/editar"), ("POST", "/logout"),
])
def test_secretaria_acessa_contas_a_receber(db, metodo, caminho):
    verificar_acesso(requisicao(metodo, caminho), db, u(db, MARIA))
    assert historico(db, acao="tentativa_bloqueada") == []


@pytest.mark.parametrize("caminho", ["/lancamentos/152/excluir", "/lancamentos/lote/excluir",
                                     "/contas-pagar/1/excluir", "/tarefas/1/excluir"])
def test_secretaria_nao_exclui_e_tentativa_fica_registrada(db, caminho):
    assert bloqueio(db, "POST", caminho) == "FLIC-AUT-009"
    tentativa = historico(db, acao="tentativa_bloqueada")[-1]
    assert (tentativa.usuario_id, tentativa.cliente_id, tentativa.campo) == (MARIA, ABC, "Exclusão")
    assert tentativa.valor_novo == f"POST {caminho}" and tentativa.ip == "10.0.0.7"


@pytest.mark.parametrize("metodo,caminho", [
    ("GET", "/contas-pagar"), ("GET", "/contas-pagar/novo"), ("POST", "/contas-pagar"),
    ("GET", "/conciliacao"), ("GET", "/conciliacao/banco"), ("GET", "/importacoes"),
    ("POST", "/lancamentos/importar"), ("POST", "/lancamentos/152/desconciliar"),
    ("GET", "/fechamento"), ("GET", "/gestao/dre"), ("GET", "/tarefas"),
    ("GET", "/admin/clientes"), ("GET", "/admin/funcionarios"), ("GET", "/admin/secretarias"),
    ("POST", f"/admin/secretarias/{MARIA}/editar"), ("GET", "/admin/plano-contas"),
    ("GET", "/auditoria/historico"), ("GET", "/logs"), ("POST", "/cliente/selecionar"),
])
def test_secretaria_bloqueada_fora_de_contas_a_receber(db, metodo, caminho):
    assert bloqueio(db, metodo, caminho) == "FLIC-AUT-008"
    assert historico(db, acao="tentativa_bloqueada")[-1].valor_novo == f"{metodo} {caminho}"


def _rota_concreta(caminho: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", caminho)


def _rotas_api():
    from app.main import app
    for rota in app.routes:
        if isinstance(rota, APIRoute):
            yield rota
        elif hasattr(rota, "original_router"):  # FastAPI >= 0.139 guarda o router incluído
            yield from (r for r in rota.original_router.routes if isinstance(r, APIRoute))


def test_toda_rota_do_sistema_fora_da_lista_e_negada():
    """Garante que rotas novas nascem bloqueadas para a secretária."""
    rotas = list(_rotas_api())
    assert len(rotas) > 100
    liberadas = set()
    for rota in rotas:
        for metodo in rota.methods:
            caminho = _rota_concreta(rota.path).rstrip("/") or "/"
            if rota_liberada(metodo, caminho):
                liberadas.add((metodo, rota.path))
    assert liberadas == {
        ("GET", "/lancamentos"), ("GET", "/lancamentos/novo"), ("POST", "/lancamentos"),
        ("GET", "/lancamentos/{at_id}/editar"), ("POST", "/lancamentos/{at_id}/editar"),
        ("GET", "/ajuda/erros"), ("GET", "/tutorial"),
    }


def _depende_de(dependant, alvo) -> bool:
    return any(d.call is alvo or _depende_de(d, alvo) for d in dependant.dependencies)


def test_toda_rota_privada_passa_pelo_controle_de_acesso():
    # /admin/procedimentos só redireciona para /admin/servicos (protegida), sem ler dados.
    publicas = {"/login", "/health", "/ready", "/version", "/admin/procedimentos"}
    sem_controle = [rota.path for rota in _rotas_api()
                    if rota.path not in publicas and not _depende_de(rota.dependant, auth.get_usuario_atual)]
    assert not sem_controle, sem_controle


def test_controle_roda_dentro_da_autenticacao(db, monkeypatch):
    monkeypatch.setattr(auth, "decodificar_token", lambda token: {"sub": str(MARIA), "ver": 0, "jti": "j"})
    monkeypatch.setattr(auth, "token_revogado", lambda jti: False)
    def autenticada(caminho):
        req = requisicao("GET", caminho)
        req.scope["headers"].append((b"authorization", b"Bearer token"))
        return req

    with pytest.raises(ErroFlic) as exc:
        auth.get_usuario_atual(autenticada("/contas-pagar"), db)
    assert exc.value.codigo == "FLIC-AUT-008"
    assert auth.get_usuario_atual(autenticada("/lancamentos"), db).id == MARIA


def test_secretaria_sem_cliente_nao_entra_mas_pode_sair(db):
    maria = u(db, MARIA)
    maria.cliente_id = None
    with pytest.raises(ErroFlic) as exc:
        verificar_acesso(requisicao("GET", "/lancamentos"), db, maria)
    assert exc.value.codigo == "FLIC-AUT-010"
    verificar_acesso(requisicao("POST", "/logout"), db, maria)


def test_secretaria_com_cliente_inativado_perde_acesso(db):
    db.get(ClienteBPO, ABC).ativo = False
    db.commit()
    assert bloqueio(db, "GET", "/lancamentos") == "FLIC-AUT-010"


@pytest.mark.parametrize("caminho", ["/", "/inicio", "/painel"])
def test_paginas_iniciais_levam_aos_lancamentos_do_cliente(db, caminho):
    with pytest.raises(HTTPException) as exc:
        verificar_acesso(requisicao("GET", caminho, cookie=""), db, u(db, MARIA))
    assert exc.value.status_code == 303
    assert exc.value.headers["Location"] == "/lancamentos"
    assert f"cliente_ativo={ABC}" in exc.value.headers["set-cookie"]


def test_menu_da_secretaria_so_tem_contas_a_receber(db):
    req = como_secretaria(db)
    html = chamar(lancamentos.listar_lancamentos, request=req, db=db, usuario=u(db, MARIA)).body.decode()
    menu = html.split('<nav', 1)[1].split('</nav>', 1)[0]
    links = set(re.findall(r'href="([^"]+)"', menu))
    assert links == {"/lancamentos/novo", "/lancamentos", "/tutorial"}
    assert "Empresa ABC" in menu
    assert "/excluir" not in html and "form-lote" not in html and "/importacoes" not in html


# ------------------------------------------------------------------ isolamento

def test_secretaria_ve_somente_o_proprio_cliente(db):
    req = como_secretaria(db)
    resposta = chamar(lancamentos.listar_lancamentos, request=req, cliente_id=XYZ,
                      data_inicio="2026-11-01", data_fim="2026-11-30", db=db, usuario=u(db, MARIA))
    assert [a.id for a in resposta.context["atendimentos"]] == [152]
    assert [c.id for c in resposta.context["clientes"]] == [ABC]


def test_cookie_e_url_de_outro_cliente_sao_ignorados(db):
    req = requisicao("GET", "/lancamentos", cookie=f"cliente_ativo={XYZ}", query=f"cliente_id={XYZ}".encode())
    verificar_acesso(req, db, u(db, MARIA))  # sem redirecionar: evita laço com cookie travado
    resposta = chamar(lancamentos.listar_lancamentos, request=req, cliente_id=XYZ,
                      data_inicio="2026-11-01", data_fim="2026-11-30", db=db, usuario=u(db, MARIA))
    assert [a.id for a in resposta.context["atendimentos"]] == [152]
    assert "Paciente XYZ" not in resposta.body.decode()


def test_secretaria_nao_abre_nem_edita_lancamento_de_outro_cliente(db):
    # Outro cliente: 404 (não revela que o registro existe) na leitura e na escrita.
    req = como_secretaria(db, "GET", "/lancamentos/200/editar")
    with pytest.raises(HTTPException) as exc:
        chamar(lancamentos.form_editar_lancamento, at_id=200, request=req, db=db, usuario=u(db, MARIA))
    assert exc.value.status_code == 404
    req = como_secretaria(db, "POST", "/lancamentos/200/editar")
    with pytest.raises(HTTPException) as exc:
        chamar(lancamentos.salvar_edicao_lancamento, at_id=200, request=req, data_atendimento=date(2026, 11, 4),
               valor_servico="1", db=db, usuario=u(db, MARIA))
    assert exc.value.status_code == 404
    db.expire_all()
    assert db.get(Atendimento, 200).valor_servico == Decimal("90.00")


def test_secretaria_nao_cria_lancamento_em_outro_cliente(db):
    req = como_secretaria(db, "POST", "/lancamentos")
    resposta = chamar(lancamentos.criar_lancamentos, request=req, cliente_id=XYZ, data_atendimento=date(2026, 11, 4),
                      plano_conta_id=["1"], valor_servico=["50"], forma_pagamento=["dinheiro"], db=db, usuario=u(db, MARIA))
    assert "erro=acesso_negado" in resposta.headers["location"]
    assert db.query(Atendimento).filter_by(cliente_id=XYZ).count() == 1


def test_banco_recusa_gravacao_em_outro_cliente_mesmo_sem_passar_pela_rota(db):
    como_secretaria(db)
    db.add(Atendimento(cliente_id=XYZ, data_atendimento=date(2026, 11, 4), valor_servico=1, condicao_pagamento="avista"))
    with pytest.raises(ErroFlic) as exc:
        db.flush()
    assert exc.value.codigo == "FLIC-AUT-006"
    db.rollback()
    como_secretaria(db)
    db.get(Atendimento, 152).cliente_id = XYZ
    with pytest.raises(ErroFlic):
        db.flush()


def test_banco_recusa_exclusao_pela_secretaria(db):
    como_secretaria(db)
    db.delete(db.get(Atendimento, 152))
    with pytest.raises(ErroFlic) as exc:
        db.flush()
    assert exc.value.codigo == "FLIC-AUT-009"
    db.rollback()
    como_secretaria(db)
    from datetime import datetime, timezone
    db.get(Atendimento, 152).deleted_at = datetime.now(timezone.utc)
    with pytest.raises(ErroFlic):
        db.flush()


def test_secretaria_nao_edita_lancamento_conciliado(db):
    db.get(Atendimento, 152).status_conciliacao = StatusConciliacao.conciliado
    db.commit()
    req = como_secretaria(db, "POST", "/lancamentos/152/editar")
    with pytest.raises(ErroFlic) as exc:
        chamar(lancamentos.salvar_edicao_lancamento, at_id=152, request=req, data_atendimento=date(2026, 11, 4),
               valor_servico="1800", db=db, usuario=u(db, MARIA))
    assert exc.value.codigo == "FLIC-REC-015"


# ------------------------------------------------------------------ auditoria

def test_criacao_registrada_automaticamente(db):
    req = como_secretaria(db, "POST", "/lancamentos")
    resposta = chamar(lancamentos.criar_lancamentos, request=req, cliente_id=ABC, data_atendimento=date(2026, 11, 4),
                      nome_paciente=["João"], plano_conta_id=["1"], valor_servico=["250"], forma_pagamento=["pix"],
                      nome_pagador_pix=["João"],
                      rateios_json=[json.dumps([{"centro_custo_id": 1, "percentual": "100"}])],
                      db=db, usuario=u(db, MARIA))
    assert resposta.status_code == 303
    novo = db.query(Atendimento).filter_by(cliente_id=ABC).order_by(Atendimento.id.desc()).first()
    linhas = historico(db, entidade="lancamento", entidade_id=novo.id)
    assert linhas and {l.acao for l in linhas} == {"criacao"}
    campos = {l.campo: l.valor_novo for l in linhas}
    assert campos["Valor"] == "R$ 250,00"
    assert campos["Paciente"] == "João"
    assert campos["Data do atendimento"] == "04/11/2026"
    assert campos["Plano de contas"] == "Consulta (#1)"
    assert campos["Rateio · Dr. Ana"] == "100,00% (R$ 250,00)"
    l = linhas[0]
    assert (l.usuario_id, l.usuario_nome, l.cliente_id, l.cliente_nome) == (MARIA, "Maria Silva", ABC, "Empresa ABC")
    assert l.ip == "10.0.0.7" and l.criado_em is not None and l.modulo == "contas_receber"


def test_edicao_registra_valor_anterior_e_novo(db):
    req = como_secretaria(db, "POST", "/lancamentos/152/editar")
    chamar(lancamentos.salvar_edicao_lancamento, at_id=152, request=req, data_atendimento=date(2026, 11, 4),
           nome_paciente="Paciente ABC", valor_servico="1800", observacao="Ajuste", db=db, usuario=u(db, MARIA))
    linhas = {l.campo: l for l in historico(db, entidade="lancamento", entidade_id=152, acao="edicao")}
    assert (linhas["Valor"].valor_anterior, linhas["Valor"].valor_novo) == ("R$ 1.500,00", "R$ 1.800,00")
    assert (linhas["Data do atendimento"].valor_anterior, linhas["Data do atendimento"].valor_novo) == ("03/11/2026", "04/11/2026")
    assert (linhas["Observação"].valor_anterior, linhas["Observação"].valor_novo) == (None, "Ajuste")
    assert "Paciente" not in linhas  # campo que não mudou não gera linha
    assert {l.operacao_id for l in linhas.values()} == {next(iter(linhas.values())).operacao_id}


def test_alteracoes_de_outros_perfis_nao_entram_no_historico(db):
    db.get(Atendimento, 152).valor_servico = Decimal("10")
    db.commit()
    assert historico(db) == []


def test_historico_e_imutavel_pela_aplicacao(db):
    req = como_secretaria(db, "POST", "/lancamentos/152/editar")
    chamar(lancamentos.salvar_edicao_lancamento, at_id=152, request=req, data_atendimento=date(2026, 11, 3),
           nome_paciente="Paciente ABC", valor_servico="1600", db=db, usuario=u(db, MARIA))
    db.info.pop(historico_service.CHAVE_CONTEXTO, None)
    linha = historico(db)[0]
    linha.valor_novo = "R$ 0,00"
    with pytest.raises(HTTPException):
        db.flush()
    db.rollback()
    db.delete(historico(db)[0])
    with pytest.raises(HTTPException):
        db.flush()
    db.rollback()
    assert historico(db)[0].valor_novo == "R$ 1.600,00"


def test_operacao_e_historico_sao_gravados_juntos(db, monkeypatch):
    def falha(*a, **kw):
        raise RuntimeError("falha ao gravar histórico")
    monkeypatch.setattr(historico_service, "_linhas_registro", falha)
    req = como_secretaria(db, "POST", "/lancamentos/152/editar")
    with pytest.raises(RuntimeError):
        chamar(lancamentos.salvar_edicao_lancamento, at_id=152, request=req, data_atendimento=date(2026, 11, 3),
               nome_paciente="Paciente ABC", valor_servico="1700", db=db, usuario=u(db, MARIA))
    db.rollback()
    db.info.pop(historico_service.CHAVE_CONTEXTO, None)
    assert db.get(Atendimento, 152).valor_servico == Decimal("1500.00")


def _gerar_historico(db):
    req = como_secretaria(db, "POST", "/lancamentos/152/editar")
    chamar(lancamentos.salvar_edicao_lancamento, at_id=152, request=req, data_atendimento=date(2026, 11, 3),
           nome_paciente="Paciente ABC", valor_servico="1800", db=db, usuario=u(db, MARIA))
    db.info.pop(historico_service.CHAVE_CONTEXTO, None)


def _tela(db, uid, **filtros):
    req = requisicao("GET", "/auditoria/historico", cookie="")
    return chamar(auditoria.historico_alteracoes, request=req, db=db, usuario=u(db, uid), **filtros)


@pytest.mark.parametrize("uid", [ADMIN, EDITOR])
def test_admin_e_editor_visualizam_o_historico(db, uid):
    _gerar_historico(db)
    resposta = _tela(db, uid)
    html = resposta.body.decode()
    assert "Maria Silva" in html and "Empresa ABC" in html
    assert "R$ 1.500,00 → R$ 1.800,00" in html
    assert len(resposta.context["operacoes"]) == 1
    detalhe = chamar(auditoria.detalhe_operacao, operacao_id=str(historico(db)[0].operacao_id),
                     request=requisicao("GET", "/auditoria/historico/x", cookie=""), db=db, usuario=u(db, uid))
    assert "R$ 1.800,00" in detalhe.body.decode() and "10.0.0.7" in detalhe.body.decode()


@pytest.mark.parametrize("filtros,esperado", [
    ({"secretaria_id": str(MARIA)}, 1), ({"secretaria_id": str(EDITOR)}, 0),
    ({"cliente_id": str(ABC)}, 1), ({"cliente_id": str(XYZ)}, 0),
    ({"acao": "edicao"}, 1), ({"acao": "criacao"}, 0),
    ({"registro": "152"}, 1), ({"registro": "#200"}, 0),
    ({"campo": "valor"}, 1), ({"campo": "Bandeira"}, 0),
    ({"data_inicio": date.today().isoformat(), "data_fim": date.today().isoformat()}, 1),
    ({"data_inicio": "2020-01-01", "data_fim": "2020-01-31"}, 0),
])
def test_filtros_do_historico(db, filtros, esperado):
    _gerar_historico(db)
    assert len(_tela(db, ADMIN, **filtros).context["operacoes"]) == esperado


def test_editor_nao_ve_historico_de_secretaria_desativada_e_admin_ve(db):
    _gerar_historico(db)
    u(db, MARIA).ativo = False
    db.commit()
    assert len(_tela(db, EDITOR).context["operacoes"]) == 0
    assert len(_tela(db, ADMIN).context["operacoes"]) == 1


def test_secretaria_nao_acessa_auditoria(db):
    assert bloqueio(db, "GET", "/auditoria/historico") == "FLIC-AUT-008"
    assert not has_permission(u(db, MARIA), Permission.AUDITORIA)
