"""Autorização de objeto por empresa (tenant) — fonte única para as rotas operacionais.

Regra: um usuário só alcança objetos (lançamento, conta a pagar, movimentação, venda,
lote, linha de extrato...) de uma empresa permitida a ele:

* coordenador  → todas as empresas ativas;
* secretária   → somente a empresa do cadastro dela (``usuario.cliente_id``);
* editor e funcionário → as empresas em que são o responsável (``ClienteBPO.funcionario_id``).

``obter_do_tenant`` aplica o filtro de empresa dentro do próprio SQL — o objeto de outra
empresa nunca é carregado — e responde 404 tanto para id inexistente quanto para id de
outra empresa, para não revelar que o registro existe.

O cadastro de clientes (``app.routers.admin``) tem regra própria e mais ampla de
propósito: o editor enxerga todos os clientes no cadastro para poder se atribuir.
"""
from __future__ import annotations

from typing import TypeVar

from sqlalchemy.orm import Query, Session

from app.auth import ve_todos_os_clientes
from app.errors import erro
from app.models import ClienteBPO, PerfilUsuario, Usuario

Modelo = TypeVar("Modelo")


def consulta_empresas_permitidas(db: Session, usuario: Usuario) -> Query:
    """Consulta de ClienteBPO com as empresas que o usuário pode operar."""
    query = db.query(ClienteBPO).filter(ClienteBPO.ativo.is_(True), ClienteBPO.deleted_at.is_(None))
    if ve_todos_os_clientes(usuario):
        return query
    if usuario.perfil == PerfilUsuario.secretaria:
        # Sempre o cliente do cadastro dela: cookie, URL e formulário são ignorados.
        return query.filter(ClienteBPO.id == usuario.cliente_id)
    return query.filter(ClienteBPO.funcionario_id == usuario.id)


def empresas_permitidas(db: Session, usuario: Usuario) -> list[ClienteBPO]:
    return consulta_empresas_permitidas(db, usuario).order_by(ClienteBPO.nome).all()


def ids_empresas_permitidas(db: Session, usuario: Usuario) -> list[int]:
    return [cid for (cid,) in consulta_empresas_permitidas(db, usuario).with_entities(ClienteBPO.id)]


def pode_operar_empresa(db: Session, usuario: Usuario, cliente_id) -> bool:
    if not isinstance(cliente_id, int):
        return False
    return consulta_empresas_permitidas(db, usuario).filter(ClienteBPO.id == cliente_id).count() > 0


def obter_do_tenant(db: Session, usuario: Usuario, modelo: type[Modelo], objeto_id,
                    *, cliente_id: int | None = None, para_atualizar: bool = False) -> Modelo:
    """Carrega ``modelo`` pelo id somente se ele pertence a uma empresa permitida ao usuário.

    Com ``cliente_id``, o objeto também precisa ser dessa empresa (a da tela/formulário).
    Id inexistente, inválido ou de outra empresa → 404 (FLIC-GER-404), sem distinção.
    """
    if not isinstance(objeto_id, int) or isinstance(objeto_id, bool):
        raise erro("FLIC-GER-404")
    permitidas = consulta_empresas_permitidas(db, usuario).with_entities(ClienteBPO.id)
    query = db.query(modelo).filter(modelo.id == objeto_id, modelo.cliente_id.in_(permitidas))
    if cliente_id is not None:
        query = query.filter(modelo.cliente_id == cliente_id)
    if para_atualizar:
        query = query.with_for_update()
    objeto = query.first()
    if objeto is None:
        raise erro("FLIC-GER-404")
    return objeto
