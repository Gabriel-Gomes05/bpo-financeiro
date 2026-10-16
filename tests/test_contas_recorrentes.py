import asyncio
from decimal import Decimal

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import ClienteBPO, ContaRecorrente, PerfilUsuario, Usuario
from app.routers import contas_recorrentes as rec


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(rec, "_log", lambda *a, **kw: None)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=1, nome="Coord", email="c@example.test", senha_hash="x", perfil=PerfilUsuario.coordenador),
            Usuario(id=2, nome="Ana", email="a@example.test", senha_hash="x", perfil=PerfilUsuario.funcionario),
            ClienteBPO(id=10, nome="Clinica Ana", funcionario_id=2),
            ClienteBPO(id=20, nome="Outra", funcionario_id=None),
        ])
        session.commit()
        yield session
    engine.dispose()


def request(cliente_id=10):
    return Request({"type": "http", "method": "GET", "scheme": "http", "server": ("testserver", 80),
                    "path": "/contas-pagar/recorrentes", "query_string": b"",
                    "headers": [(b"cookie", f"cliente_ativo={cliente_id}".encode())]})


def criar(db, uid=1, cliente_id=10, **kwargs):
    params = dict(descricao="Aluguel", email_destino="fin@cliente.com", dia_vencimento=10,
                  dias_antecedencia=3, fornecedor="Imobiliaria", valor="1500,50")
    params.update(kwargs)
    return asyncio.run(rec.criar_recorrente(request(cliente_id), **params, db=db, usuario=db.get(Usuario, uid)))


def test_coordenador_cria_no_cliente_ativo(db):
    response = criar(db)
    assert response.headers["location"].endswith("sucesso=criada")
    conta = db.query(ContaRecorrente).one()
    assert (conta.cliente_id, conta.valor, conta.email_destino) == (10, Decimal("1500.50"), "fin@cliente.com")


@pytest.mark.parametrize("kwargs", [{"email_destino": "sem-arroba"}, {"dia_vencimento": 32}, {"descricao": " "}, {"valor": "abc"}])
def test_rejeita_dados_invalidos(db, kwargs):
    assert "erro=" in criar(db, **kwargs).headers["location"]
    assert db.query(ContaRecorrente).count() == 0


def test_funcionario_ve_mas_nao_gerencia(db):
    criar(db)
    ana = db.get(Usuario, 2)
    html = asyncio.run(rec.listar_recorrentes(request(), db, ana)).body.decode()
    assert "Aluguel" in html and "Nova conta recorrente" not in html
    with pytest.raises(HTTPException) as exc:
        criar(db, uid=2)
    assert exc.value.status_code == 403


def test_funcionario_nao_acessa_cliente_de_outro(db):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rec.listar_recorrentes(request(20), db, db.get(Usuario, 2)))
    assert exc.value.status_code == 400


def test_pausar_e_excluir_respeitam_cliente_ativo(db):
    criar(db)
    conta = db.query(ContaRecorrente).one()
    coord = db.get(Usuario, 1)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rec.excluir_recorrente(conta.id, request(20), db, coord))
    assert exc.value.status_code == 404
    asyncio.run(rec.alternar_recorrente(conta.id, request(), db, coord))
    assert conta.ativo is False
    asyncio.run(rec.excluir_recorrente(conta.id, request(), db, coord))
    assert db.query(ContaRecorrente).count() == 0


def test_rotinas_removidas_e_recorrentes_registradas():
    import app.main as main
    from starlette.routing import Match

    assert not hasattr(main, "rotinas")
    scope = {"type": "http", "method": "GET", "path": "/contas-pagar/recorrentes"}
    assert any(r.matches(scope)[0] == Match.FULL for r in rec.router.routes)
    assert main.contas_recorrentes is rec
