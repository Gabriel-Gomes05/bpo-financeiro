"""Aba Tutorial: cada perfil recebe só o treinamento do que pode fazer, com imagens existentes."""
import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.acesso_secretaria import rota_liberada
from app.database import Base
from app.models import ClienteBPO, PerfilUsuario, Usuario
from app.routers import tutorial as rota
from app.tutorial import MODULOS, PERFIS, treinamento_do_perfil

ESTATICO = Path(__file__).resolve().parents[1] / "static" / "tutorial"


def ids(perfil):
    return {item["modulo"].id for item in treinamento_do_perfil(perfil)["modulos"]}


def test_secretaria_ve_so_lancamentos_e_ajuda():
    assert ids("secretaria") == {"primeiros-passos", "lancamentos", "incluir-lancamento", "ajuda"}


def test_medico_nao_aprende_o_que_nao_pode_fazer():
    medico = ids("medico")
    assert {"dashboard", "lancamentos", "contas-pagar", "receitas-despesas", "dre"} <= medico
    assert not medico & {"incluir-lancamento", "conciliacao-banco", "conciliar-varios", "importacoes",
                         "incluir-conta", "aprovacao", "orcamento", "fechamento", "clientes", "auditoria"}


def test_funcionario_editor_e_coordenador():
    func, editor, coord = ids("funcionario"), ids("editor"), ids("coordenador")
    assert {"conciliacao-banco", "conciliar-varios", "incluir-conta", "clientes"} <= func
    assert not func & {"grupos-servicos", "auditoria", "funcionarios-plano"}
    assert {"grupos-servicos", "auditoria"} <= editor and "funcionarios-plano" not in editor
    assert coord == {m.id for m in MODULOS}


def test_passos_tambem_sao_filtrados_por_perfil():
    def passos(perfil, modulo):
        item = next(i for i in treinamento_do_perfil(perfil)["modulos"] if i["modulo"].id == modulo)
        return [p.titulo for p in item["passos"]]
    assert "Exclua" not in passos("secretaria", "lancamentos")
    assert "Exclua" in passos("funcionario", "lancamentos")
    assert "Somente consulta" in passos("medico", "contas-pagar")
    assert "Mude o status" not in passos("medico", "contas-pagar")
    assert "Escolha a empresa" not in passos("secretaria", "primeiros-passos")


def test_secretaria_ve_os_prints_da_propria_tela():
    imagens = {i["modulo"].id: i["imagem"] for i in treinamento_do_perfil("secretaria")["modulos"]}
    assert imagens["lancamentos"] == "menu-secretaria" and imagens["incluir-lancamento"] == "secretaria-novo"


def test_todas_as_imagens_existem():
    nomes = {m.imagem for m in MODULOS if m.imagem} | {e[0] for m in MODULOS for e in m.imagens_extras}
    nomes |= {p["imagem"] for p in PERFIS.values()} | {"menu-secretaria", "secretaria-novo"}
    faltando = sorted(n for n in nomes if not (ESTATICO / f"{n}.webp").is_file())
    assert not faltando, faltando


def test_secretaria_pode_abrir_o_tutorial():
    assert rota_liberada("GET", "/tutorial")
    assert not rota_liberada("POST", "/tutorial")


@pytest.mark.parametrize("perfil", list(PerfilUsuario))
def test_pagina_renderiza_para_cada_perfil(perfil):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(ClienteBPO(id=1, nome="Empresa A"))
        db.flush()
        usuario = Usuario(id=5, nome="Pessoa Teste", email="p@x.test", senha_hash="x", perfil=perfil,
                          cliente_id=1 if perfil == PerfilUsuario.secretaria else None)
        db.add(usuario)
        db.commit()
        req = Request({"type": "http", "method": "GET", "path": "/tutorial", "query_string": b"", "headers": []})
        html = asyncio.run(rota.pagina_tutorial(req, db, usuario)).body.decode()
    esperado = treinamento_do_perfil(perfil)
    assert f"perfil {esperado['perfil']['nome']}" in html
    for item in esperado["modulos"]:
        assert f'id="{item["modulo"].id}"' in html
    if perfil == PerfilUsuario.secretaria:
        assert 'id="conciliacao-banco"' not in html
    engine.dispose()
