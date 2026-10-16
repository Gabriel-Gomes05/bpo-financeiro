import asyncio
from datetime import date, timedelta

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import ClienteBPO, PerfilUsuario, Tarefa, Usuario
from app.routers import cliente_ativo, dashboard, tarefas
from app.services import tarefas_service


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(tarefas, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=1, nome="Admin", email="admin@example.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            Usuario(id=2, nome="Ana", email="ana@example.test", senha_hash="x", perfil=PerfilUsuario.funcionario),
            Usuario(id=3, nome="Bruno", email="bruno@example.test", senha_hash="x", perfil=PerfilUsuario.funcionario),
            ClienteBPO(id=10, nome="Clinica Ana", funcionario_id=2),
            ClienteBPO(id=20, nome="Clinica Bruno", funcionario_id=3),
        ])
        session.commit()
        yield session
    engine.dispose()


def usuario(db, uid):
    return db.get(Usuario, uid)


def request(path="/tarefas", query=b"", cookies=""):
    headers = [(b"cookie", cookies.encode())] if cookies else []
    return Request({"type": "http", "method": "GET", "scheme": "http", "server": ("testserver", 80),
                    "path": path, "headers": headers, "query_string": query})


def criar(db, uid, **kwargs):
    params = dict(titulo="Tarefa", descricao=None, prazo=None, responsavel_id=None, cliente_id=None,
                  modulo=None, link=None, voltar="/tarefas", db=db, usuario=usuario(db, uid))
    params.update(kwargs)
    return asyncio.run(tarefas.criar_tarefa(**params))


def test_funcionario_cria_apenas_para_si(db):
    criar(db, 2, titulo="Ver prazo pagamentos", responsavel_id=3)
    tarefa = db.query(Tarefa).one()
    assert tarefa.responsavel_id == 2
    assert tarefa.criado_por_id == 2
    assert tarefa.cliente_id is None


def test_admin_cria_para_equipe_com_cliente_e_modulo(db):
    criar(db, 1, titulo="Reunião", responsavel_id=2, cliente_id=10, modulo="contas_pagar")
    tarefa = db.query(Tarefa).one()
    assert (tarefa.responsavel_id, tarefa.cliente_id, tarefa.modulo) == (2, 10, "contas_pagar")


@pytest.mark.parametrize("kwargs", [
    {"cliente_id": 20},                                   # cliente de outro funcionário
    {"modulo": "contas_pagar"},                           # módulo sem cliente
    {"cliente_id": 10, "modulo": "inexistente"},
    {"link": "javascript:alert(1)"},
    {"link": "//site-externo.com"},
    {"titulo": "   "},
])
def test_rejeita_dados_invalidos(db, kwargs):
    response = criar(db, 2, **kwargs)
    assert "erro_tarefa=" in response.headers["location"]
    assert db.query(Tarefa).count() == 0


def test_aceita_links_interno_e_externo(db):
    criar(db, 2, titulo="A", link="/contas-pagar")
    criar(db, 2, titulo="B", link="https://exemplo.com/doc")
    assert {t.link for t in db.query(Tarefa)} == {"/contas-pagar", "https://exemplo.com/doc"}


def test_voltar_externo_nao_redireciona_para_fora(db):
    response = criar(db, 2, voltar="https://malicioso.com")
    assert response.headers["location"].startswith("/tarefas?")


def test_visibilidade_e_conclusao(db):
    criar(db, 1, titulo="Da Ana", responsavel_id=2)
    criar(db, 1, titulo="Do Bruno", responsavel_id=3)
    ana, bruno = usuario(db, 2), usuario(db, 3)
    tarefa_ana = db.query(Tarefa).filter_by(titulo="Da Ana").one()
    assert [t.titulo for t in tarefas_service.tarefas_visiveis(db, ana)] == ["Da Ana"]
    assert tarefas_service.tarefas_visiveis(db, usuario(db, 1)).count() == 2
    with pytest.raises(HTTPException) as exc:
        asyncio.run(tarefas.alternar_conclusao(tarefa_ana.id, "/tarefas", db, bruno))
    assert exc.value.status_code == 404
    asyncio.run(tarefas.alternar_conclusao(tarefa_ana.id, "/tarefas", db, ana))
    assert tarefa_ana.concluida and tarefa_ana.concluida_em
    # Responsável não edita nem exclui tarefa criada pelo admin.
    with pytest.raises(HTTPException) as exc:
        asyncio.run(tarefas.excluir_tarefa(tarefa_ana.id, "/tarefas", db, ana))
    assert exc.value.status_code == 403


def test_exclusao_e_logica(db):
    criar(db, 2, titulo="Minha")
    tarefa = db.query(Tarefa).one()
    asyncio.run(tarefas.excluir_tarefa(tarefa.id, "/tarefas", db, usuario(db, 2)))
    assert tarefa.deleted_at is not None
    assert tarefas_service.tarefas_visiveis(db, usuario(db, 2)).count() == 0


def test_pessoais_no_painel_e_de_cliente_no_dashboard(db):
    criar(db, 2, titulo="Pessoal", prazo=date.today() - timedelta(days=1))
    criar(db, 2, titulo="Do cliente", cliente_id=10)
    ana = usuario(db, 2)
    assert [t.titulo for t in tarefas_service.pendentes_pessoais(db, ana)] == ["Pessoal"]
    assert [t.titulo for t in tarefas_service.pendentes_do_cliente(db, ana, 10)] == ["Do cliente"]
    assert tarefas_service.pendentes_por_cliente(db, ana, [10, 20]) == {10: 1}

    html = asyncio.run(cliente_ativo.painel_geral(request("/painel"), db, ana)).body.decode()
    assert "Minhas tarefas" in html and "Pessoal" in html and "Atrasada" in html
    assert "1 tarefa(s)" in html

    html = asyncio.run(dashboard.dashboard(request("/", cookies="cliente_ativo=10"), db, ana)).body.decode()
    assert "Tarefas deste cliente" in html and "Do cliente" in html


def test_abrir_entra_no_cliente_e_vai_ao_modulo(db):
    criar(db, 1, titulo="Reunião", responsavel_id=2, cliente_id=10, modulo="conciliacao_banco",
          link="https://externo.com")
    tarefa = db.query(Tarefa).one()
    response = asyncio.run(tarefas.abrir_tarefa(tarefa.id, request(), "link", db, usuario(db, 2)))
    # Link externo nunca passa pelo redirecionamento do servidor; cai no módulo.
    assert response.headers["location"] == "/conciliacao/banco"
    assert "cliente_ativo=10" in response.headers["set-cookie"]


def test_abrir_sem_acesso_ao_cliente_nao_troca_empresa(db):
    criar(db, 1, titulo="Reunião", responsavel_id=3, cliente_id=10)
    tarefa = db.query(Tarefa).one()
    response = asyncio.run(tarefas.abrir_tarefa(tarefa.id, request(), "modulo", db, usuario(db, 3)))
    assert "erro_tarefa=" in response.headers["location"]
    assert "set-cookie" not in response.headers


def test_tela_lista_e_formulario(db):
    criar(db, 1, titulo="Fechar DRE", responsavel_id=2, cliente_id=10, modulo="gestao_dre")
    html = asyncio.run(tarefas.listar_tarefas(request(), db=db, usuario=usuario(db, 1))).body.decode()
    assert "Fechar DRE" in html
    assert 'name="responsavel_id"' in html
    assert "/tarefas/1/abrir?destino=modulo" in html
    html = asyncio.run(tarefas.listar_tarefas(request(), db=db, usuario=usuario(db, 2))).body.decode()
    assert 'name="responsavel_id"' not in html


def test_calendario_posiciona_tarefas_no_dia_do_prazo(db):
    criar(db, 2, titulo="Pagar fornecedor", prazo=date(2026, 10, 20))
    criar(db, 2, titulo="Reuniao cliente", prazo=date(2026, 10, 5), cliente_id=10)
    criar(db, 2, titulo="Sem prazo")
    criar(db, 1, titulo="De outra pessoa", responsavel_id=3, prazo=date(2026, 10, 20))
    ana = usuario(db, 2)
    cal = tarefas_service.montar_calendario(
        tarefas_service.do_usuario(db, ana), date(2026, 10, 1), hoje=date(2026, 10, 15),
    )
    dias = {d["data"]: d for semana in cal["semanas"] for d in semana}
    assert cal["titulo"] == "Outubro de 2026"
    assert (cal["anterior"], cal["proximo"]) == ("2026-09", "2026-11")
    assert all(len(semana) == 7 and semana[0].weekday() == 6 for semana in
               [[d["data"] for d in s] for s in cal["semanas"]])
    assert [t.titulo for t in dias[date(2026, 10, 20)]["tarefas"]] == ["Pagar fornecedor"]
    assert [t.titulo for t in dias[date(2026, 10, 5)]["tarefas"]] == ["Reuniao cliente"]
    assert dias[date(2026, 10, 15)]["hoje"]
    assert sum(len(d["tarefas"]) for d in dias.values()) == 2


@pytest.mark.parametrize("valor,esperado", [
    ("2026-02", date(2026, 2, 1)), ("2026-13", date(2026, 10, 1)), ("abc", date(2026, 10, 1)), (None, date(2026, 10, 1)),
])
def test_mes_referencia(valor, esperado):
    assert tarefas_service.mes_referencia(valor, date(2026, 10, 15)) == esperado


def test_painel_e_dashboard_geral_alternam_lista_e_calendario(db):
    hoje = date.today()
    criar(db, 2, titulo="Tarefa do calendario", prazo=hoje)
    ana = usuario(db, 2)
    html = asyncio.run(cliente_ativo.painel_geral(request("/painel"), db, ana, visao="calendario")).body.decode()
    assert "Tarefa do calendario" in html and "Somente tarefas com prazo" in html
    assert 'href="/painel?visao=lista"' in html
    html = asyncio.run(cliente_ativo.painel_geral(request("/painel"), db, ana)).body.decode()
    assert "Somente tarefas com prazo" not in html and "Tarefa do calendario" in html
    html = asyncio.run(dashboard.dashboard(request("/", query=b"visao=calendario"), db, ana)).body.decode()
    assert "Minhas tarefas" in html and "Somente tarefas com prazo" in html


def test_item_escapa_html_informado_pelo_usuario(db):
    criar(db, 2, titulo='<img src=x onerror="alert(1)">', descricao="<script>alert(2)</script>")
    html = asyncio.run(cliente_ativo.painel_geral(request("/painel"), db, usuario(db, 2))).body.decode()
    assert "<img src=x" not in html and "<script>alert(2)" not in html
    assert "&lt;img" in html


def test_cards_do_dashboard_contam_tarefas_com_prazo_hoje(db):
    hoje = date.today()
    criar(db, 1, titulo="Hoje A", responsavel_id=2, cliente_id=10, prazo=hoje)
    criar(db, 1, titulo="Hoje B", responsavel_id=2, cliente_id=10, prazo=hoje)
    criar(db, 1, titulo="Amanha", responsavel_id=2, cliente_id=10, prazo=hoje + timedelta(days=1))
    tarefa = db.query(Tarefa).filter_by(titulo="Hoje A").one()
    asyncio.run(tarefas.alternar_conclusao(tarefa.id, "/", db, usuario(db, 2)))
    monkey = dashboard.templates.TemplateResponse
    try:
        dashboard.templates.TemplateResponse = lambda nome, contexto: contexto
        ctx = asyncio.run(dashboard.dashboard(request("/", cookies="cliente_ativo=10"), db, usuario(db, 1)))
    finally:
        dashboard.templates.TemplateResponse = monkey
    assert (ctx["total_tarefas"], ctx["tarefas_concluidas"]) == (2, 1)


def test_rotinas_e_tela_de_recorrentes_removidas():
    import importlib.util

    import app.main as main
    assert not hasattr(main, "rotinas")
    assert importlib.util.find_spec("app.routers.rotinas") is None
    assert importlib.util.find_spec("app.routers.contas_recorrentes") is None
    assert all(not caminho.startswith("/rotinas") for _, caminho in tarefas_service.MODULOS_TAREFA.values())
