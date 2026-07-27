import os
import logging
import re
import unicodedata
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, List

import pandas as pd

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy.orm import Session

from app.authorization import Permission, require_permission
from app.config import UPLOAD_DIR
from app.constants import CATEGORIAS_DESPESA, CATEGORIA_NOME
from app.database import get_db
from app.utils import cliente_ativo as _ca, salvar_upload_temporario
from app.models import CentroCusto, ClienteBPO, ContaPagar, ContaPagarCentroCustoRateio, StatusContaPagar, TipoContaPagar, Usuario, PerfilUsuario
from app.services.log_service import registrar as _log
from app.errors import public_import_error

router = APIRouter()
require_contas_pagar = require_permission(Permission.CONTAS_PAGAR)
logger = logging.getLogger(__name__)



def clientes_do_usuario(db: Session, usuario: Usuario):
    if usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor):
        return db.query(ClienteBPO).filter(ClienteBPO.ativo == True).all()
    return db.query(ClienteBPO).filter(
        ClienteBPO.funcionario_id == usuario.id,
        ClienteBPO.ativo == True,
    ).all()


def _ids_clientes_do_usuario(db: Session, usuario: Usuario) -> list[int]:
    return [c.id for c in clientes_do_usuario(db, usuario)]


def _key_centro_custo(cc: CentroCusto) -> str:
    codigo = (cc.codigo or "").strip()
    return codigo or f"centro_custo:{cc.id}"


def _centros_custo_por_cliente(db: Session, cliente_ids: list[int]) -> dict[int, list[dict]]:
    if not cliente_ids:
        return {}
    centros = db.query(CentroCusto).filter(
        CentroCusto.cliente_id.in_(cliente_ids),
        CentroCusto.ativo == True,
    ).order_by(CentroCusto.cliente_id.asc(), CentroCusto.codigo.asc(), CentroCusto.nome.asc()).all()
    por_cliente: dict[int, list[dict]] = {}
    for cc in centros:
        por_cliente.setdefault(cc.cliente_id, []).append({
            "key": _key_centro_custo(cc),
            "codigo": (cc.codigo or "").strip(),
            "nome": cc.nome,
            "is_medico": bool(cc.is_medico),
            "especialidade": cc.especialidade or "",
        })
    return por_cliente


def _categoria_nome_com_centros(centros_por_cliente: dict[int, list[dict]]) -> dict[str, str]:
    nomes = dict(CATEGORIA_NOME)
    for centros in centros_por_cliente.values():
        for cc in centros:
            rotulo = f"{cc['codigo']} - {cc['nome']}" if cc["codigo"] else cc["nome"]
            nomes[cc["key"]] = rotulo
    return nomes


def _categoria_dre_valida(
    db: Session,
    cliente_id: int,
    categoria_dre: Optional[str],
) -> str | None:
    categoria_dre = (categoria_dre or "").strip()
    if not categoria_dre:
        return None
    centros = _centros_custo_por_cliente(db, [cliente_id]).get(cliente_id, [])
    chaves_validas = {cc["key"] for cc in centros}
    return categoria_dre if categoria_dre in chaves_validas else None


def _decimal_rateio(valor: str) -> Decimal | None:
    try:
        return Decimal(str(valor or "").strip().replace(",", "."))
    except InvalidOperation:
        return None


def _centro_por_key(db: Session, cliente_id: int, key: str) -> CentroCusto | None:
    key = (key or "").strip()
    if not key:
        return None
    centros = db.query(CentroCusto).filter(
        CentroCusto.cliente_id == cliente_id,
        CentroCusto.ativo == True,
    ).all()
    return next((cc for cc in centros if _key_centro_custo(cc) == key), None)


def _montar_rateios_conta(
    db: Session,
    cliente_id: int,
    valor_total: Decimal,
    categorias: List[str],
    percentuais: List[str],
) -> list[dict]:
    rateios = []
    soma = Decimal("0")
    centros_usados: set[int] = set()
    for i, cat in enumerate(categorias):
        pct = _decimal_rateio(percentuais[i] if i < len(percentuais) else "")
        cc = _centro_por_key(db, cliente_id, cat)
        if not cc or pct is None or pct <= 0 or pct > 100 or cc.id in centros_usados:
            continue
        centros_usados.add(cc.id)
        soma += pct
        valor = (valor_total * pct / Decimal("100")).quantize(Decimal("0.01"))
        rateios.append({
            "centro": cc,
            "categoria_key": _key_centro_custo(cc),
            "percentual": pct,
            "valor": valor,
        })
    if not rateios or soma != Decimal("100"):
        return []

    # Garante que o rateio em centavos sempre feche exatamente o valor da conta.
    diferenca = valor_total - sum((r["valor"] for r in rateios), Decimal("0"))
    rateios[-1]["valor"] += diferenca
    return rateios


@router.get("/contas-pagar", response_class=HTMLResponse)
async def listar_contas(
    request: Request,
    cliente_id: Optional[int] = None,
    flash: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    cliente_id = _ca(request, cliente_id)
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    query = db.query(ContaPagar).filter(
        ContaPagar.cliente_id.in_(ids_permitidos)
    )
    if cliente_id and cliente_id in ids_permitidos:
        query = query.filter(ContaPagar.cliente_id == cliente_id)

    # Ordena: vencidas primeiro, depois por vencimento
    contas = query.order_by(ContaPagar.vencimento.asc()).limit(200).all()
    centros_por_cliente = _centros_custo_por_cliente(db, ids_permitidos)

    return templates.TemplateResponse("contas_pagar.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "contas": contas,
        "hoje": date.today(),
        "cliente_selecionado": cliente_id,
        "categorias_despesa": CATEGORIAS_DESPESA,
        "centros_custo_por_cliente": centros_por_cliente,
        "categoria_nome": _categoria_nome_com_centros(centros_por_cliente),
        "flash": flash,
    })


@router.get("/contas-pagar/{conta_id}/documento")
async def baixar_documento_conta(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta or conta.cliente_id not in _ids_clientes_do_usuario(db, usuario):
        raise HTTPException(status_code=404)
    if not conta.documento_path:
        raise HTTPException(status_code=404)

    upload_dir = Path(UPLOAD_DIR).resolve()
    caminho = Path(conta.documento_path).resolve()
    if upload_dir not in caminho.parents or not caminho.is_file():
        raise HTTPException(status_code=404)

    return FileResponse(
        path=str(caminho),
        filename=caminho.name,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/contas-pagar")
async def criar_conta(
    cliente_id: int = Form(...),
    descricao: str = Form(...),
    fornecedor: Optional[str] = Form(None),
    tipo: str = Form("pontual"),
    valor: Decimal = Form(...),
    vencimento: date = Form(...),
    categoria_dre: Optional[str] = Form(None),
    rateio_centro_custo_key: List[str] = Form(default=[]),
    rateio_percentual: List[str] = Form(default=[]),
    especialidade: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
    documento: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    # Salva documento se enviado
    documento_path = None
    if documento and documento.filename:
        caminho, _, _ = await salvar_upload_temporario(
            documento,
            {".pdf", ".png", ".jpg", ".jpeg", ".csv", ".xlsx", ".xls"},
        )
        documento_path = caminho

    rateios = _montar_rateios_conta(db, cliente_id, valor, rateio_centro_custo_key, rateio_percentual)
    if any((key or "").strip() for key in rateio_centro_custo_key) and not rateios:
        return RedirectResponse(
            url=f"/contas-pagar?cliente_id={cliente_id}&flash=Rateio+inv%C3%A1lido%3A+use+centros+diferentes+e+feche+100%25",
            status_code=303,
        )
    categoria_compat = rateios[0]["categoria_key"] if rateios else _categoria_dre_valida(db, cliente_id, categoria_dre)
    especialidade_valor = (especialidade or "").strip() or next(
        (r["centro"].especialidade for r in rateios if r["centro"].is_medico and r["centro"].especialidade),
        None,
    )

    conta = ContaPagar(
        cliente_id=cliente_id,
        descricao=descricao,
        fornecedor=fornecedor or None,
        tipo=tipo,
        valor=valor,
        vencimento=vencimento,
        categoria_dre=categoria_compat,
        especialidade=especialidade_valor,
        status=StatusContaPagar.pendente,
        documento_path=documento_path,
        observacao=observacao or None,
        lancado_por_id=usuario.id,
    )
    db.add(conta)
    db.flush()
    for r in rateios:
        db.add(ContaPagarCentroCustoRateio(
            conta_pagar_id=conta.id,
            centro_custo_id=r["centro"].id,
            categoria_key=r["categoria_key"],
            percentual=r["percentual"],
            valor=r["valor"],
        ))
    db.commit()
    cliente_obj = next((c for c in clientes_do_usuario(db, usuario) if c.id == cliente_id), None)
    _log(
        db, "Conta a pagar criada", "contas_pagar",
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        cliente_id=cliente_id, cliente_nome=cliente_obj.nome if cliente_obj else None,
        detalhes=f"{descricao} — R$ {valor} | venc. {vencimento.strftime('%d/%m/%Y')}",
    )
    return RedirectResponse(url=f"/contas-pagar?cliente_id={cliente_id}", status_code=303)


@router.post("/contas-pagar/importar")
async def importar_contas(
    request: Request,
    cliente_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    def _norm(nome: str) -> str:
        nome = unicodedata.normalize("NFKD", nome)
        nome = "".join(c for c in nome if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", "_", nome.strip().lower()).strip("_")

    def _col(df, opcoes):
        for n in opcoes:
            if n in df.columns:
                return n
        return None

    flash_success = None
    flash_error = None
    caminho = None

    try:
        caminho, nome_original, ext = await salvar_upload_temporario(
            arquivo,
            {".csv", ".xlsx", ".xls"},
        )

        if ext == ".csv":
            df = pd.read_csv(caminho, decimal=",", thousands=".")
        else:
            df = pd.read_excel(caminho)

        df.columns = [_norm(str(c)) for c in df.columns]

        c_desc  = _col(df, ["descricao", "description", "nome", "conta"])
        c_forn  = _col(df, ["fornecedor", "empresa", "supplier", "favorecido"])
        c_tipo  = _col(df, ["tipo", "type", "recorrencia"])
        c_valor = _col(df, ["valor", "value", "amount", "vlr"])
        c_venc  = _col(df, ["vencimento", "data_vencimento", "vence", "due_date", "data"])
        c_obs   = _col(df, ["observacao", "obs", "nota", "note"])

        if not c_desc or not c_valor or not c_venc:
            raise ValueError(
                "Planilha deve ter colunas: descricao, valor e vencimento "
                f"(encontradas: {list(df.columns)})"
            )

        importadas = 0
        for _, row in df.iterrows():
            try:
                descricao = str(row[c_desc]).strip()
                if not descricao or descricao.lower() in ("nan", "none", ""):
                    continue

                valor = Decimal(str(row[c_valor]).replace(",", ".")).quantize(Decimal("0.01"))
                vencimento = pd.to_datetime(row[c_venc]).date()

                fornecedor = str(row[c_forn]).strip() if c_forn and pd.notna(row[c_forn]) else None
                if fornecedor and fornecedor.lower() in ("nan", "none", ""):
                    fornecedor = None

                observacao = str(row[c_obs]).strip() if c_obs and pd.notna(row[c_obs]) else None
                if observacao and observacao.lower() in ("nan", "none", ""):
                    observacao = None

                tipo_raw = str(row[c_tipo]).strip().lower() if c_tipo and pd.notna(row[c_tipo]) else "pontual"
                tipo = TipoContaPagar.fixa if "fix" in tipo_raw or "recor" in tipo_raw else TipoContaPagar.pontual

                db.add(ContaPagar(
                    cliente_id=cliente_id,
                    descricao=descricao,
                    fornecedor=fornecedor,
                    tipo=tipo,
                    valor=valor,
                    vencimento=vencimento,
                    observacao=observacao,
                    status=StatusContaPagar.pendente,
                    lancado_por_id=usuario.id,
                ))
                importadas += 1
            except (InvalidOperation, ValueError, Exception):
                continue

        db.commit()
        flash_success = f"{importadas} conta(s) importada(s) de '{nome_original}'."
        _log(
            db, "Contas importadas", "contas_pagar",
            usuario_id=usuario.id, usuario_nome=usuario.nome,
            cliente_id=cliente_id,
            detalhes=f"{importadas} conta(s) de '{nome_original}'",
        )

    except Exception:
        flash_error = public_import_error(logger, "importar_contas_pagar")
    finally:
        try:
            if caminho:
                os.remove(caminho)
        except OSError:
            pass

    clientes_lista = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes_lista]
    query = db.query(ContaPagar).filter(ContaPagar.cliente_id.in_(ids_permitidos))
    if cliente_id:
        query = query.filter(ContaPagar.cliente_id == cliente_id)
    contas = query.order_by(ContaPagar.vencimento.asc()).limit(200).all()
    centros_por_cliente = _centros_custo_por_cliente(db, ids_permitidos)

    return templates.TemplateResponse("contas_pagar.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes_lista,
        "contas": contas,
        "hoje": date.today(),
        "cliente_selecionado": cliente_id,
        "flash_success": flash_success,
        "flash_error": flash_error,
        "categorias_despesa": CATEGORIAS_DESPESA,
        "centros_custo_por_cliente": centros_por_cliente,
        "categoria_nome": _categoria_nome_com_centros(centros_por_cliente),
    })


@router.post("/contas-pagar/{conta_id}/agendar")
async def agendar_pagamento(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    clientes = clientes_do_usuario(db, usuario)
    if conta.cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    conta.status = StatusContaPagar.agendado
    db.commit()
    _log(
        db, "Pagamento agendado", "contas_pagar",
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        cliente_id=conta.cliente_id,
        detalhes=f"{conta.descricao} — R$ {conta.valor} | venc. {conta.vencimento.strftime('%d/%m/%Y')}",
    )
    return RedirectResponse(url=f"/contas-pagar?cliente_id={conta.cliente_id}", status_code=303)


@router.post("/contas-pagar/{conta_id}/cancelar")
async def cancelar_conta(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    clientes = clientes_do_usuario(db, usuario)
    if conta.cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    if conta.status != StatusContaPagar.pago:
        conta.status = StatusContaPagar.cancelado
        db.commit()
        _log(
            db, "Conta cancelada", "contas_pagar",
            usuario_id=usuario.id, usuario_nome=usuario.nome,
            cliente_id=conta.cliente_id,
            detalhes=f"{conta.descricao} — R$ {conta.valor}",
        )
    return RedirectResponse(url=f"/contas-pagar?cliente_id={conta.cliente_id}", status_code=303)
