import os
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.config import UPLOAD_DIR
from app.database import get_db
from app.utils import salvar_upload_temporario
from app.models import (
    ClienteBPO,
    ContaPagar,
    ExtratoLinhaBancaria,
    MovimentacaoBancaria,
    PerfilUsuario,
    StatusContaPagar,
    StatusExtratoLinha,
    StatusMovimentacaoBancaria,
    Usuario,
)

router = APIRouter()


def clientes_do_usuario(db: Session, usuario: Usuario):
    if usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor):
        return db.query(ClienteBPO).filter(ClienteBPO.ativo == True).all()
    return db.query(ClienteBPO).filter(
        ClienteBPO.funcionario_id == usuario.id,
        ClienteBPO.ativo == True,
    ).all()


def _contas_pendentes(db: Session, cliente_id: int):
    return (
        db.query(ContaPagar)
        .filter(
            ContaPagar.cliente_id == cliente_id,
            ContaPagar.status.in_([StatusContaPagar.pendente, StatusContaPagar.aguardando_aprovacao]),
        )
        .order_by(ContaPagar.vencimento.asc())
        .all()
    )


def _sugestao_conta(valor_banco: Decimal, data_banco, contas: list):
    melhor = None
    melhor_score = float("inf")
    for conta in contas:
        diferenca_valor = abs(valor_banco - Decimal(str(conta.valor)))
        diferenca_dias = abs((data_banco - conta.vencimento).days) if conta.vencimento else 99
        if diferenca_valor > Decimal("5.00") or diferenca_dias > 7:
            continue
        score = float(diferenca_valor) * 100 + diferenca_dias
        if score < melhor_score:
            melhor_score = score
            melhor = conta
    return melhor


# ---------------------------------------------------------------------------
# Conc. Cartão — Contas a Pagar
# ---------------------------------------------------------------------------

@router.get("/contas-pagar/conciliacao-cartao", response_class=HTMLResponse)
async def pagina_conciliacao_cartao_pagar(
    request: Request,
    cliente_id: Optional[int] = None,
    buscar_mov: Optional[int] = Query(default=None),
    termo: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    contas = []
    painel = []

    if cliente_id and cliente_id in ids_permitidos:
        movimentos_raw = (
            db.query(MovimentacaoBancaria)
            .filter(
                MovimentacaoBancaria.cliente_id == cliente_id,
                MovimentacaoBancaria.sentido == "pagamento",
                MovimentacaoBancaria.status.in_([
                    StatusMovimentacaoBancaria.importada,
                    StatusMovimentacaoBancaria.divergencia,
                    StatusMovimentacaoBancaria.revisada,
                ]),
            )
            .order_by(MovimentacaoBancaria.data_movimento.asc())
            .all()
        )
        contas = _contas_pendentes(db, cliente_id)

        for mov in movimentos_raw:
            valor = Decimal(str(mov.valor))
            sugestao = _sugestao_conta(valor, mov.data_movimento, contas)

            resultados_busca = []
            busca_aberta = buscar_mov == mov.id
            if busca_aberta:
                t = (termo or "").lower().strip()
                if t:
                    resultados_busca = [
                        c for c in contas
                        if t in (c.descricao or "").lower() or t in (c.fornecedor or "").lower()
                    ]
                else:
                    resultados_busca = sorted(
                        contas,
                        key=lambda c: abs(Decimal(str(c.valor)) - valor),
                    )[:8]

            painel.append({
                "mov": mov,
                "sugestao": sugestao,
                "busca_aberta": busca_aberta,
                "busca_termo": termo or "",
                "resultados_busca": resultados_busca,
            })

    return templates.TemplateResponse("contas_pagar_conciliacao_cartao.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "cliente_selecionado": cliente_id,
        "painel": painel,
        "contas_pendentes": contas,
        "resultado": None,
    })


@router.post("/contas-pagar/conciliacao-cartao/processar")
async def importar_cartao_pagar(
    request: Request,
    cliente_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar/conciliacao-cartao", status_code=303)

    erro = None
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

        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        def _col(names):
            for n in names:
                if n in df.columns:
                    return n
            return None

        c_data = _col(["data", "date", "data_compra", "data_transacao", "data_pagamento"])
        c_val = _col(["valor", "valor_bruto", "amount", "bruto"])
        c_desc = _col(["descricao", "estabelecimento", "historico", "titulo", "memo"])
        c_dig = _col(["ultimos_digitos", "final_cartao", "card_last4", "digitos"])

        if not c_data or not c_val:
            raise ValueError("Arquivo não contém colunas de data e valor reconhecíveis.")

        # Remove movimentos anteriores de pagamento com cartão (não conciliados)
        db.query(MovimentacaoBancaria).filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            MovimentacaoBancaria.sentido == "pagamento",
            MovimentacaoBancaria.tipo == "cartao",
            MovimentacaoBancaria.status.in_([
                StatusMovimentacaoBancaria.importada,
                StatusMovimentacaoBancaria.divergencia,
            ]),
        ).delete()
        db.commit()

        for _, row in df.iterrows():
            try:
                data = pd.to_datetime(row[c_data]).date()
                valor = Decimal(str(row[c_val])).quantize(Decimal("0.01"))
            except Exception:
                continue

            descricao = str(row[c_desc]).strip() if c_desc and pd.notna(row[c_desc]) else None
            digitos = str(row[c_dig]).strip().zfill(4)[-4:] if c_dig and pd.notna(row[c_dig]) else None

            mov = MovimentacaoBancaria(
                cliente_id=cliente_id,
                tipo="cartao",
                sentido="pagamento",
                data_movimento=data,
                valor=abs(valor),
                descricao=descricao,
                digitos_cartao=digitos,
                origem_arquivo=nome_original,
                status=StatusMovimentacaoBancaria.importada,
            )
            db.add(mov)

        db.commit()

    except Exception as e:
        erro = str(e)
    finally:
        try:
            if caminho:
                os.remove(caminho)
        except OSError:
            pass

    base = f"/contas-pagar/conciliacao-cartao?cliente_id={cliente_id}"
    if erro:
        return RedirectResponse(url=f"{base}&flash_error={erro}", status_code=303)
    return RedirectResponse(url=base, status_code=303)


@router.post("/contas-pagar/conciliacao-cartao/mov/{mov_id}/conciliar")
async def conciliar_cartao_pagar(
    mov_id: int,
    cliente_id: int = Form(...),
    conta_pagar_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    mov = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_pagar_id).first()

    if (
        mov and conta
        and mov.cliente_id in ids_permitidos
        and conta.cliente_id in ids_permitidos
        and mov.cliente_id == cliente_id
        and conta.cliente_id == cliente_id
    ):
        mov.status = StatusMovimentacaoBancaria.conciliada
        mov.conta_pagar_id = conta.id
        conta.status = StatusContaPagar.pago
        conta.data_pagamento = mov.data_movimento
        db.commit()

    return RedirectResponse(url=f"/contas-pagar/conciliacao-cartao?cliente_id={cliente_id}", status_code=303)


@router.post("/contas-pagar/conciliacao-cartao/mov/{mov_id}/ignorar")
async def ignorar_cartao_pagar(
    mov_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    mov = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()
    if mov and mov.cliente_id in ids_permitidos:
        mov.status = StatusMovimentacaoBancaria.revisada
        db.commit()

    return RedirectResponse(url=f"/contas-pagar/conciliacao-cartao?cliente_id={cliente_id}", status_code=303)


# ---------------------------------------------------------------------------
# Conc. Banco — Contas a Pagar
# ---------------------------------------------------------------------------

@router.get("/contas-pagar/conciliacao-banco", response_class=HTMLResponse)
async def pagina_conciliacao_banco_pagar(
    request: Request,
    cliente_id: Optional[int] = None,
    buscar_linha: Optional[int] = Query(default=None),
    termo: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    contas = []
    painel = []

    if cliente_id and cliente_id in ids_permitidos:
        linhas_debito = (
            db.query(ExtratoLinhaBancaria)
            .filter(
                ExtratoLinhaBancaria.cliente_id == cliente_id,
                ExtratoLinhaBancaria.tipo == "debito",
                ExtratoLinhaBancaria.status == StatusExtratoLinha.importado,
                ExtratoLinhaBancaria.conta_pagar_id.is_(None),
            )
            .order_by(ExtratoLinhaBancaria.data.asc())
            .all()
        )
        contas = _contas_pendentes(db, cliente_id)

        for linha in linhas_debito:
            valor = Decimal(str(linha.valor))
            sugestao = _sugestao_conta(valor, linha.data, contas)

            resultados_busca = []
            busca_aberta = buscar_linha == linha.id
            if busca_aberta:
                t = (termo or "").lower().strip()
                if t:
                    resultados_busca = [
                        c for c in contas
                        if t in (c.descricao or "").lower() or t in (c.fornecedor or "").lower()
                    ]
                else:
                    resultados_busca = sorted(
                        contas,
                        key=lambda c: abs(Decimal(str(c.valor)) - valor),
                    )[:8]

            painel.append({
                "linha": linha,
                "sugestao": sugestao,
                "busca_aberta": busca_aberta,
                "busca_termo": termo or "",
                "resultados_busca": resultados_busca,
            })

    return templates.TemplateResponse("contas_pagar_conciliacao_banco.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "cliente_selecionado": cliente_id,
        "painel": painel,
        "contas_pendentes": contas,
        "resultado": None,
    })


@router.post("/contas-pagar/conciliacao-banco/importar")
async def importar_banco_pagar(
    request: Request,
    cliente_id: int = Form(...),
    arquivo: UploadFile = File(...),
    col_data: str = Form("data"),
    col_descricao: str = Form("descricao"),
    col_valor: str = Form("valor"),
    col_tipo: str = Form("tipo"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar/conciliacao-banco", status_code=303)

    erro = None
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

        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        def _col(names):
            for n in names:
                if n in df.columns:
                    return n
            return None

        c_data = _col([col_data, "data", "date", "data_lancamento", "dt_lancamento"])
        c_desc = _col([col_descricao, "descricao", "historico", "titulo", "memo"])
        c_val = _col([col_valor, "valor", "amount", "credito", "debito"])
        c_tipo = _col([col_tipo, "tipo", "natureza", "dc", "credito/debito"])

        if not c_data or not c_val:
            raise ValueError("Arquivo não contém colunas de data e valor reconhecíveis.")

        for _, row in df.iterrows():
            try:
                data_linha = pd.to_datetime(row[c_data]).date()
                valor_raw = Decimal(str(row[c_val])).quantize(Decimal("0.01"))
            except Exception:
                continue

            if c_tipo:
                tipo_str = str(row[c_tipo]).strip().lower()
                tipo = "credito" if any(x in tipo_str for x in ["c", "cred", "entrada", "+"]) else "debito"
            else:
                tipo = "credito" if valor_raw > 0 else "debito"

            descricao = str(row[c_desc]).strip() if c_desc else ""

            linha = ExtratoLinhaBancaria(
                cliente_id=cliente_id,
                data=data_linha,
                descricao=descricao,
                valor=abs(valor_raw),
                tipo=tipo,
                status=StatusExtratoLinha.importado,
                origem_arquivo=nome_original,
            )
            db.add(linha)

        db.commit()

    except Exception as e:
        erro = str(e)
    finally:
        try:
            if caminho:
                os.remove(caminho)
        except OSError:
            pass

    base = f"/contas-pagar/conciliacao-banco?cliente_id={cliente_id}"
    if erro:
        return RedirectResponse(url=f"{base}&flash_error={erro}", status_code=303)
    return RedirectResponse(url=base, status_code=303)


@router.post("/contas-pagar/conciliacao-banco/linha/{linha_id}/conciliar")
async def conciliar_linha_banco_pagar(
    linha_id: int,
    cliente_id: int = Form(...),
    conta_pagar_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    linha = db.query(ExtratoLinhaBancaria).filter(ExtratoLinhaBancaria.id == linha_id).first()
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_pagar_id).first()

    if (
        linha and conta
        and linha.cliente_id in ids_permitidos
        and conta.cliente_id in ids_permitidos
        and linha.cliente_id == cliente_id
        and conta.cliente_id == cliente_id
    ):
        linha.status = StatusExtratoLinha.conciliado
        linha.conta_pagar_id = conta.id
        conta.status = StatusContaPagar.pago
        conta.data_pagamento = linha.data
        db.commit()

    return RedirectResponse(url=f"/contas-pagar/conciliacao-banco?cliente_id={cliente_id}", status_code=303)


@router.post("/contas-pagar/conciliacao-banco/linha/{linha_id}/ignorar")
async def ignorar_linha_banco_pagar(
    linha_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    linha = db.query(ExtratoLinhaBancaria).filter(ExtratoLinhaBancaria.id == linha_id).first()
    if linha and linha.cliente_id in ids_permitidos:
        linha.status = StatusExtratoLinha.ignorado
        db.commit()

    return RedirectResponse(url=f"/contas-pagar/conciliacao-banco?cliente_id={cliente_id}", status_code=303)
