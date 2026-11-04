"""Auditoria → Histórico de alterações das secretárias (somente leitura, coordenador e editor)."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.auth import ve_todos_os_clientes
from app.authorization import Permission, require_permission
from app.config import UPLOAD_DIR
from app.database import get_db
from app.errors import erro
from app.jinja import templates
from app.models import (
    ClienteBPO, ExtratoPeriodoFechado, HistoricoAlteracao, PerfilUsuario, PeriodoFechado, Usuario,
)
from app.services.historico_service import ACOES, ENTIDADES

router = APIRouter(prefix="/auditoria")
require_auditoria = require_permission(Permission.AUDITORIA)

FUSO_BRASILIA = timezone(timedelta(hours=-3))
LIMITE_LINHAS = 5000
LIMITE_OPERACOES = 300


def _local(momento: datetime) -> datetime:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(FUSO_BRASILIA)


def _int(valor: Optional[str]) -> Optional[int]:
    valor = (valor or "").strip().lstrip("#")
    return int(valor) if valor.isdigit() else None


def _data(valor: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def _ids_meus_clientes(db: Session, usuario: Usuario):
    return db.query(ClienteBPO.id).filter(ClienteBPO.funcionario_id == usuario.id)


def _consulta_base(db: Session, usuario: Usuario):
    query = db.query(HistoricoAlteracao)
    if not ve_todos_os_clientes(usuario):
        # Editor vê só o histórico dos clientes designados a ele.
        query = query.filter(HistoricoAlteracao.cliente_id.in_(_ids_meus_clientes(db, usuario)))
    if usuario.perfil != PerfilUsuario.coordenador:
        # Editor acompanha as secretárias ativas; o histórico de desativadas é do administrador.
        query = query.join(Usuario, Usuario.id == HistoricoAlteracao.usuario_id).filter(
            Usuario.ativo.is_(True), Usuario.deleted_at.is_(None),
        )
    return query


def _agrupar(linhas: list[HistoricoAlteracao]) -> list[dict]:
    """Uma operação = mesma requisição + mesmo registro; os campos alterados ficam juntos."""
    operacoes: dict[tuple, dict] = {}
    for linha in linhas:
        chave = (linha.operacao_id, linha.entidade, linha.entidade_id)
        op = operacoes.get(chave)
        if op is None:
            op = operacoes[chave] = {"linha": linha, "quando": _local(linha.criado_em), "campos": [], "acao": linha.acao}
        op["campos"].append(linha)
        if linha.acao == "criacao":
            op["acao"] = "criacao"
    return list(operacoes.values())


@router.get("/historico", response_class=HTMLResponse)
async def historico_alteracoes(
    request: Request,
    secretaria_id: Optional[str] = None,
    cliente_id: Optional[str] = None,
    acao: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    registro: Optional[str] = None,
    campo: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_auditoria),
):
    filtros = {
        "secretaria_id": _int(secretaria_id),
        "cliente_id": _int(cliente_id),
        "acao": acao if acao in ACOES else None,
        "data_inicio": _data(data_inicio),
        "data_fim": _data(data_fim),
        "registro": _int(registro),
        "campo": (campo or "").strip()[:80] or None,
    }
    query = _consulta_base(db, usuario)
    if filtros["secretaria_id"]:
        query = query.filter(HistoricoAlteracao.usuario_id == filtros["secretaria_id"])
    if filtros["cliente_id"]:
        query = query.filter(HistoricoAlteracao.cliente_id == filtros["cliente_id"])
    if filtros["acao"]:
        query = query.filter(HistoricoAlteracao.acao == filtros["acao"])
    if filtros["data_inicio"]:
        inicio = datetime.combine(filtros["data_inicio"], time.min, FUSO_BRASILIA)
        query = query.filter(HistoricoAlteracao.criado_em >= inicio)
    if filtros["data_fim"]:
        fim = datetime.combine(filtros["data_fim"] + timedelta(days=1), time.min, FUSO_BRASILIA)
        query = query.filter(HistoricoAlteracao.criado_em < fim)
    if filtros["registro"]:
        query = query.filter(HistoricoAlteracao.entidade_id == filtros["registro"])
    if filtros["campo"]:
        query = query.filter(HistoricoAlteracao.campo.ilike(f"%{filtros['campo']}%"))

    linhas = query.order_by(HistoricoAlteracao.criado_em.desc(), HistoricoAlteracao.id.desc()).limit(LIMITE_LINHAS).all()
    operacoes = _agrupar(linhas)

    secretarias = db.query(Usuario).filter(Usuario.perfil == PerfilUsuario.secretaria)
    clientes_filtro = db.query(ClienteBPO)
    if usuario.perfil != PerfilUsuario.coordenador:
        secretarias = secretarias.filter(Usuario.ativo.is_(True), Usuario.deleted_at.is_(None))
    if not ve_todos_os_clientes(usuario):
        secretarias = secretarias.filter(Usuario.cliente_id.in_(_ids_meus_clientes(db, usuario)))
        clientes_filtro = clientes_filtro.filter(ClienteBPO.funcionario_id == usuario.id)
    campos = sorted({c for (c,) in db.query(HistoricoAlteracao.campo).distinct() if c})

    return templates.TemplateResponse("auditoria_historico.html", {
        "request": request,
        "usuario": usuario,
        "operacoes": operacoes[:LIMITE_OPERACOES],
        "total_operacoes": len(operacoes),
        "limite": LIMITE_OPERACOES,
        "filtros": filtros,
        "secretarias": secretarias.order_by(Usuario.nome).all(),
        "clientes_filtro": clientes_filtro.order_by(ClienteBPO.nome).all(),
        "campos": campos,
        "acoes": ACOES,
        "entidades": ENTIDADES,
    })


@router.get("/historico/{operacao_id}", response_class=HTMLResponse)
async def detalhe_operacao(
    operacao_id: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_auditoria),
):
    try:
        operacao = uuid.UUID(operacao_id)
    except ValueError:
        raise erro("FLIC-GER-404") from None
    linhas = _consulta_base(db, usuario).filter(
        HistoricoAlteracao.operacao_id == operacao,
    ).order_by(HistoricoAlteracao.entidade_id, HistoricoAlteracao.id).all()
    if not linhas:
        raise erro("FLIC-GER-404")
    return templates.TemplateResponse("auditoria_detalhe.html", {
        "request": request,
        "usuario": usuario,
        "operacoes": _agrupar(linhas),
        "primeira": linhas[0],
        "quando": _local(linhas[0].criado_em),
        "acoes": ACOES,
        "entidades": ENTIDADES,
    })


# ------------------------------------------------------------------ extratos de fechamento

def _periodos_visiveis(db: Session, usuario: Usuario):
    query = db.query(PeriodoFechado).options(
        joinedload(PeriodoFechado.cliente), joinedload(PeriodoFechado.fechado_por),
        joinedload(PeriodoFechado.extratos),
    ).filter(PeriodoFechado.deleted_at.is_(None))
    if not ve_todos_os_clientes(usuario):
        query = query.filter(PeriodoFechado.cliente_id.in_(_ids_meus_clientes(db, usuario)))
    return query


@router.get("/extratos", response_class=HTMLResponse)
async def extratos_de_fechamento(
    request: Request,
    cliente_id: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_auditoria),
):
    filtro_cliente = _int(cliente_id)
    query = _periodos_visiveis(db, usuario)
    if filtro_cliente:
        query = query.filter(PeriodoFechado.cliente_id == filtro_cliente)
    clientes = db.query(ClienteBPO)
    if not ve_todos_os_clientes(usuario):
        clientes = clientes.filter(ClienteBPO.funcionario_id == usuario.id)
    return templates.TemplateResponse("auditoria_extratos.html", {
        "request": request,
        "usuario": usuario,
        "periodos": query.order_by(PeriodoFechado.data_inicio.desc(), PeriodoFechado.id.desc()).limit(500).all(),
        "clientes_filtro": clientes.order_by(ClienteBPO.nome).all(),
        "filtro_cliente": filtro_cliente,
        "local": _local,
    })


@router.get("/extratos/{extrato_id}")
async def baixar_extrato(
    extrato_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_auditoria),
):
    extrato = db.query(ExtratoPeriodoFechado).join(PeriodoFechado).filter(
        ExtratoPeriodoFechado.id == extrato_id, ExtratoPeriodoFechado.deleted_at.is_(None),
        PeriodoFechado.id.in_(_periodos_visiveis(db, usuario).with_entities(PeriodoFechado.id)),
    ).first()
    if not extrato:
        raise erro("FLIC-FEC-005")
    upload_dir = Path(UPLOAD_DIR).resolve()
    caminho = Path(extrato.caminho).resolve()
    if upload_dir not in caminho.parents or not caminho.is_file():
        raise erro("FLIC-FEC-005")
    return FileResponse(
        path=str(caminho), media_type="application/pdf", filename=extrato.nome_arquivo,
        content_disposition_type="inline", headers={"Cache-Control": "no-store"},
    )
