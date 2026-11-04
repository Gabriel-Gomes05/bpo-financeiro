"""Controle de acesso do perfil Secretária, aplicado no backend a toda requisição autenticada.

A secretária só alcança as rotas de `ROTAS_LIBERADAS` (Contas a Receber → Lançamentos) e
sempre no cliente vinculado ao usuário: o cliente vem do cadastro dela, nunca do
cookie, da URL ou do formulário. Qualquer outra rota é negada e a tentativa fica no
histórico de alterações.
"""
from __future__ import annotations

import re

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.errors import erro
from app.models import ClienteBPO, PerfilUsuario, Usuario
from app.services import historico_service

_LEITURA = frozenset({"GET", "HEAD"})
ROTAS_LIBERADAS = (
    (_LEITURA, re.compile(r"/lancamentos")),
    (_LEITURA, re.compile(r"/lancamentos/novo")),
    (frozenset({"POST"}), re.compile(r"/lancamentos")),
    (_LEITURA | {"POST"}, re.compile(r"/lancamentos/\d+/editar")),
    (_LEITURA, re.compile(r"/ajuda/erros")),
)
PAGINAS_INICIAIS = {"/", "/inicio", "/painel"}
PAGINA_INICIAL_SECRETARIA = "/lancamentos"


def eh_secretaria(usuario: Usuario) -> bool:
    return usuario.perfil == PerfilUsuario.secretaria


def rota_liberada(metodo: str, caminho: str) -> bool:
    return any(metodo in metodos and padrao.fullmatch(caminho) for metodos, padrao in ROTAS_LIBERADAS)


def eh_exclusao(metodo: str, caminho: str) -> bool:
    return metodo == "DELETE" or bool(re.search(r"/(excluir|remover|apagar|delete)\b", caminho))


def cliente_vinculado(db: Session, usuario: Usuario) -> ClienteBPO | None:
    if not usuario.cliente_id:
        return None
    return db.query(ClienteBPO).filter(
        ClienteBPO.id == usuario.cliente_id,
        ClienteBPO.ativo.is_(True),
        ClienteBPO.deleted_at.is_(None),
    ).first()


def _redirecionar(request: Request, destino: str, cliente_id: int) -> HTTPException:
    """Redireciona fixando o cookie de empresa no cliente da secretária."""
    resposta = RedirectResponse(destino, status_code=303)
    resposta.set_cookie(
        "cliente_ativo", str(cliente_id), max_age=60 * 60 * 24 * 30, samesite="strict",
        httponly=True, secure=_cookie_seguro(request), path="/",
    )
    return HTTPException(status_code=303, headers={
        "Location": destino, "set-cookie": resposta.headers["set-cookie"],
    })


def _cookie_seguro(request: Request) -> bool:
    from app.security import secure_cookie_for
    return secure_cookie_for(request)


def verificar_acesso(request: Request, db: Session, usuario: Usuario) -> None:
    metodo = request.method.upper()
    caminho = request.url.path.rstrip("/") or "/"
    if metodo == "POST" and caminho == "/logout":
        return
    cliente = cliente_vinculado(db, usuario)
    if not cliente:
        raise erro("FLIC-AUT-010")
    contexto = historico_service.iniciar(db, request, usuario, cliente)

    if metodo in _LEITURA and caminho in PAGINAS_INICIAIS:
        raise _redirecionar(request, PAGINA_INICIAL_SECRETARIA, cliente.id)
    if not rota_liberada(metodo, caminho):
        exclusao = eh_exclusao(metodo, caminho)
        historico_service.registrar_tentativa(db, contexto, metodo, caminho, exclusao)
        raise erro("FLIC-AUT-009" if exclusao else "FLIC-AUT-008")
    # Cookie/URL de outro cliente não precisam de redirecionamento: as rotas liberadas
    # consultam somente usuario.cliente_id (ver lancamentos.clientes_do_usuario).
