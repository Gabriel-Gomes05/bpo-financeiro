"""Isolamento entre empresas (IDOR) em TODAS as rotas que recebem id de objeto no caminho.

As rotas não são listadas à mão: o teste percorre o app e encontra cada rota operacional com
``{..._id}``. Para cada uma, um usuário da empresa A tenta ler/alterar o objeto da empresa B:

* a resposta tem de ser 404 (sem revelar que o registro existe);
* nenhum dado da empresa B pode mudar.

E o mesmo usuário, nos objetos da própria empresa A, não pode receber 404.
"""
import asyncio
import inspect
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import get_origin

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.database import Base
from app.main import app
from app.models import (
    Atendimento, ClienteBPO, ContaBancaria, ContaPagar, ExtratoLinhaBancaria, FormaPagamento,
    MovimentacaoBancaria, PerfilUsuario, RegraNegocioBancaria, StatusContaPagar, TipoContaBancaria,
    TransferenciaCartao, Usuario, VendaCartao,
)

A, B = 1, 2
MODULOS_OPERACIONAIS = {
    "app.routers.lancamentos", "app.routers.contas_pagar", "app.routers.contas_pagar_conciliacao",
    "app.routers.conciliacao", "app.routers.conciliacao_banco",
}
# parâmetro do caminho -> chave do objeto criado para cada empresa
PARAMETRO_OBJETO = {
    "at_id": "atendimento", "atendimento_id": "atendimento", "conta_id": "conta", "mov_id": "mov",
    "venda_id": "venda", "lote_id": "lote", "linha_id": "linha", "regra_id": "regra",
}
MODELOS = [Atendimento, ContaPagar, MovimentacaoBancaria, VendaCartao, TransferenciaCartao,
           ExtratoLinhaBancaria, RegraNegocioBancaria]


def _rotas():
    def todas(rotas):
        for rota in rotas:
            if hasattr(rota, "original_router"):
                yield from todas(rota.original_router.routes)
            elif hasattr(rota, "endpoint"):
                yield rota
    vistas = set()
    for rota in todas(app.routes):
        if rota.endpoint.__module__ not in MODULOS_OPERACIONAIS:
            continue
        params = [p for p in rota.path_regex.groupindex]
        if not params:
            continue
        chave = (rota.endpoint, rota.path)
        if chave not in vistas:
            vistas.add(chave)
            yield pytest.param(rota, id=f"{sorted(rota.methods)[0]} {rota.path}")


ROTAS = list(_rotas())


def test_todas_as_rotas_por_id_sao_conhecidas():
    """Rota nova com id no caminho precisa ser mapeada aqui para entrar no teste de isolamento."""
    desconhecidos = {p for r in ROTAS for p in r.values[0].path_regex.groupindex if p not in PARAMETRO_OBJETO}
    assert not desconhecidos, f"parâmetros sem mapeamento: {desconhecidos}"
    assert len(ROTAS) >= 40


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Usuario(id=10, nome="Editor A", email="ea@x.test", senha_hash="x", perfil=PerfilUsuario.editor),
            Usuario(id=11, nome="Func A", email="fa@x.test", senha_hash="x", perfil=PerfilUsuario.funcionario),
            Usuario(id=12, nome="Editor B", email="eb@x.test", senha_hash="x", perfil=PerfilUsuario.editor),
        ])
        session.flush()
        session.add_all([ClienteBPO(id=A, nome="Empresa A", funcionario_id=10),
                         ClienteBPO(id=B, nome="Empresa B", funcionario_id=12)])
        session.flush()
        session.add(Usuario(id=13, nome="Secretária A", email="sa@x.test", senha_hash="x",
                            perfil=PerfilUsuario.secretaria, cliente_id=A))
        objetos = {}
        for cid in (A, B):
            conta_banco = ContaBancaria(cliente_id=cid, nome=f"CC {cid}", tipo=TipoContaBancaria.bancaria)
            session.add(conta_banco)
            session.flush()
            itens = {
                "atendimento": Atendimento(cliente_id=cid, data_atendimento=date(2026, 9, 1), valor_servico=Decimal("100"),
                                           condicao_pagamento="avista", forma_pagamento=FormaPagamento.pix),
                "conta": ContaPagar(cliente_id=cid, descricao=f"Conta {cid}", valor=Decimal("200"),
                                    vencimento=date(2026, 9, 5), status=StatusContaPagar.agendado),
                "mov": MovimentacaoBancaria(cliente_id=cid, conta_bancaria_id=conta_banco.id, tipo="pix_ted",
                                            sentido="recebimento", data_movimento=date(2026, 9, 5), valor=Decimal("100"),
                                            descricao="PIX"),
                "venda": VendaCartao(cliente_id=cid, data_venda=date(2026, 9, 1), data_pagamento=date(2026, 9, 2),
                                     valor_bruto=Decimal("100")),
                "lote": TransferenciaCartao(cliente_id=cid, data=date(2026, 9, 2), bandeira="visa",
                                            valor_bruto=Decimal("100"), valor_liquido=Decimal("97")),
                "linha": ExtratoLinhaBancaria(cliente_id=cid, data=date(2026, 9, 2), valor=Decimal("200"), tipo="debito"),
                "regra": RegraNegocioBancaria(cliente_id=cid, nome="Regra", padrao_descricao="PIX"),
            }
            session.add_all(itens.values())
            session.flush()
            objetos[cid] = {k: v.id for k, v in itens.items()}
        session.commit()
        session.info["objetos"] = objetos
        yield session
    engine.dispose()


def _foto_da_empresa(db, cliente_id):
    """Estado de todas as linhas da empresa (para provar que nada mudou)."""
    db.expire_all()
    foto = {}
    for modelo in MODELOS:
        for obj in db.query(modelo).filter(modelo.cliente_id == cliente_id).order_by(modelo.id):
            colunas = sa_inspect(modelo).columns.keys()
            foto[(modelo.__name__, obj.id)] = {c: getattr(obj, c) for c in colunas if c not in ("updated_at", "updated_by")}
    return foto


def _requisicao(metodo, caminho):
    return Request({"type": "http", "method": metodo, "path": caminho, "query_string": b"",
                    "headers": [(b"host", b"testserver")], "client": ("127.0.0.1", 1), "server": ("testserver", 80),
                    "scheme": "http", "root_path": "", "session": {}})


def _valor_padrao(anotacao):
    origem = get_origin(anotacao)
    if origem in (list, tuple) or anotacao in (list,):
        return []
    texto = str(anotacao)
    if "int" in texto:
        return 1
    if "Decimal" in texto or "float" in texto:
        return Decimal("1")
    if "date" in texto:
        return date(2026, 9, 5)
    if "bool" in texto:
        return False
    return "1"


def _chamar(rota, db, usuario, empresa_do_objeto, empresa_do_usuario):
    objetos = db.info["objetos"]
    caminho = rota.path
    kwargs = {}
    for nome, param in inspect.signature(rota.endpoint).parameters.items():
        if nome in rota.path_regex.groupindex:
            kwargs[nome] = objetos[empresa_do_objeto][PARAMETRO_OBJETO[nome]]
            caminho = caminho.replace("{%s}" % nome, str(kwargs[nome])).replace("{%s:int}" % nome, str(kwargs[nome]))
        elif nome == "db":
            kwargs[nome] = db
        elif nome == "usuario":
            kwargs[nome] = usuario
        elif nome == "request":
            kwargs[nome] = None  # preenchido abaixo, com o caminho real
        elif nome == "cliente_id":
            kwargs[nome] = empresa_do_usuario
        elif nome in PARAMETRO_OBJETO or nome == "conta_pagar_id":
            # ids secundários do formulário apontam para objetos da empresa do usuário
            kwargs[nome] = objetos[empresa_do_usuario][PARAMETRO_OBJETO.get(nome, "conta")]
        elif param.default is not inspect.Parameter.empty:
            padrao = getattr(param.default, "default", param.default)
            obrigatorio = padrao is Ellipsis or type(padrao).__name__ == "PydanticUndefinedType"
            kwargs[nome] = _valor_padrao(param.annotation) if obrigatorio else padrao
        else:
            kwargs[nome] = _valor_padrao(param.annotation)
    if "request" in kwargs:
        kwargs["request"] = _requisicao(sorted(rota.methods)[0], caminho)
    resultado = rota.endpoint(**kwargs)
    return asyncio.run(resultado) if inspect.iscoroutine(resultado) else resultado


def _usuario(db, uid):
    return db.get(Usuario, uid)


@pytest.mark.parametrize("perfil_uid", [10, 11, 13], ids=["editor_A", "funcionario_A", "secretaria_A"])
@pytest.mark.parametrize("rota", ROTAS)
def test_empresa_a_nao_alcanca_objeto_da_empresa_b(db, rota, perfil_uid):
    if perfil_uid == 11:  # funcionário A também é responsável pela empresa A
        db.get(ClienteBPO, A).funcionario_id = 11
        db.commit()
    antes = _foto_da_empresa(db, B)
    with pytest.raises(HTTPException) as exc:
        _chamar(rota, db, _usuario(db, perfil_uid), empresa_do_objeto=B, empresa_do_usuario=A)
    assert (exc.value.status_code, getattr(exc.value, "codigo", None)) == (404, "FLIC-GER-404"),         f"{rota.path} respondeu {exc.value.status_code} {getattr(exc.value, 'codigo', '')}"
    db.rollback()
    assert _foto_da_empresa(db, B) == antes, f"{rota.path} alterou dados da empresa B"


# 404 legítimo na própria empresa: a conta de teste não tem documento anexado.
SEM_ANEXO = {"/contas-pagar/{conta_id}/documento"}


@pytest.mark.parametrize("rota", ROTAS)
def test_empresa_a_alcanca_os_proprios_objetos(db, rota):
    if rota.path in SEM_ANEXO:
        pytest.skip("objeto existe, mas não tem arquivo anexado")
    try:
        _chamar(rota, db, _usuario(db, 10), empresa_do_objeto=A, empresa_do_usuario=A)
    except HTTPException as exc:
        # O 404 de autorização é FLIC-GER-404; outros códigos são regras de negócio (dado fictício).
        assert getattr(exc, "codigo", None) != "FLIC-GER-404", f"{rota.path} negou objeto da própria empresa"
    except Exception:
        pass  # dados fictícios podem não satisfazer a regra de negócio; o que importa é não ser 404


def test_camada_central_responde_404_para_id_invalido(db):
    from app.acesso_objetos import obter_do_tenant
    for invalido in (None, "1", 1.0, True, 999999):
        with pytest.raises(HTTPException) as exc:
            obter_do_tenant(db, _usuario(db, 10), Atendimento, invalido)
        assert exc.value.status_code == 404


def test_coordenador_alcanca_qualquer_empresa(db):
    from app.acesso_objetos import obter_do_tenant
    coord = SimpleNamespace(id=99, perfil=PerfilUsuario.coordenador)
    assert obter_do_tenant(db, coord, Atendimento, db.info["objetos"][B]["atendimento"]).cliente_id == B
