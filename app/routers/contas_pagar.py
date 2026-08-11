import os
import re
import unicodedata
import uuid
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, List

import pandas as pd

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.config import UPLOAD_DIR
from app.constants import CATEGORIAS_DESPESA, CATEGORIA_NOME
from app.database import get_db
from app.utils import cliente_ativo as _ca, salvar_upload_temporario
from app.models import CentroCusto, ClienteBPO, ContaPagar, ContaPagarCentroCustoRateio, FormaPagamento, StatusContaPagar, TipoContaPagar, Usuario, PerfilUsuario
from app.services.log_service import registrar as _log

router = APIRouter()



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


FREQUENCIAS_RECORRENCIA = {"semanal", "quinzenal", "mensal", "personalizado"}
RECORRENCIA_QTD_MAXIMA = 60
FORMAS_PAGAMENTO_VALIDAS = {f.value for f in FormaPagamento}

# Matriz de transição manual de status — "pago" nunca aparece aqui: só é setado
# via conciliação bancária, que também cuida do estorno (PagamentoParcialContaPagar).
TRANSICOES_STATUS_CONTA_PAGAR: dict[StatusContaPagar, set[StatusContaPagar]] = {
    StatusContaPagar.pendente: {StatusContaPagar.aguardando_aprovacao, StatusContaPagar.agendado, StatusContaPagar.cancelado},
    StatusContaPagar.aguardando_aprovacao: {StatusContaPagar.pendente, StatusContaPagar.agendado, StatusContaPagar.cancelado},
    StatusContaPagar.agendado: {StatusContaPagar.pendente, StatusContaPagar.aguardando_aprovacao, StatusContaPagar.cancelado},
    StatusContaPagar.cancelado: {StatusContaPagar.pendente},
    StatusContaPagar.pago: set(),
}


def _status_permitidos(atual: StatusContaPagar) -> list[StatusContaPagar]:
    return sorted(TRANSICOES_STATUS_CONTA_PAGAR.get(atual, set()), key=lambda s: s.value)


def _alterar_status_conta(
    db: Session,
    conta: ContaPagar,
    novo_status: StatusContaPagar,
    usuario: Usuario,
) -> bool:
    """Aplica a transição se permitida pela matriz. Retorna True se mudou algo."""
    if novo_status not in TRANSICOES_STATUS_CONTA_PAGAR.get(conta.status, set()):
        return False
    status_anterior = conta.status
    conta.status = novo_status
    db.commit()
    _log(
        db, "Status da conta alterado", "contas_pagar",
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        cliente_id=conta.cliente_id,
        detalhes=f"{conta.descricao} — {status_anterior.value} → {novo_status.value}",
    )
    return True


def _data_recorrencia(origem: date, intervalo: str, dias_personalizado: Optional[int], indice: int) -> date:
    """Data da N-ésima ocorrência futura (indice=1,2,3...), sempre calculada a partir
    da data de origem — evita que o dia do mês "derrape" (ex: 31 -> 28 -> 28 -> 28)
    quando uma ocorrência intermediária cai num mês mais curto."""
    if intervalo == "semanal":
        return origem + timedelta(days=7 * indice)
    if intervalo == "quinzenal":
        return origem + timedelta(days=15 * indice)
    if intervalo == "personalizado":
        dias = dias_personalizado if dias_personalizado and dias_personalizado > 0 else 30
        return origem + timedelta(days=dias * indice)
    # mensal (padrão): mantém o dia original do mês, ajustado ao último dia do mês de destino
    total_meses = origem.month - 1 + indice
    ano = origem.year + total_meses // 12
    mes = total_meses % 12 + 1
    ultimo_dia = monthrange(ano, mes)[1]
    return date(ano, mes, min(origem.day, ultimo_dia))


@router.get("/contas-pagar", response_class=HTMLResponse)
async def listar_contas(
    request: Request,
    cliente_id: Optional[int] = None,
    flash: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
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
    status_permitidos_por_conta = {c.id: [s.value for s in _status_permitidos(c.status)] for c in contas}

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
        "status_permitidos_por_conta": status_permitidos_por_conta,
        "flash": flash,
    })


@router.get("/contas-pagar/{conta_id}/documento")
async def baixar_documento_conta(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
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


@router.get("/contas-pagar/{conta_id}/editar", response_class=HTMLResponse)
async def form_editar_conta(
    conta_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta or conta.cliente_id not in _ids_clientes_do_usuario(db, usuario):
        return RedirectResponse(url="/contas-pagar", status_code=303)
    if conta.status == StatusContaPagar.pago:
        return RedirectResponse(
            url=f"/contas-pagar?cliente_id={conta.cliente_id}&flash=Conta+j%C3%A1+paga%2C+n%C3%A3o+pode+ser+editada",
            status_code=303,
        )
    centros_por_cliente = _centros_custo_por_cliente(db, [conta.cliente_id])
    return templates.TemplateResponse("contas_pagar_editar.html", {
        "request": request,
        "usuario": usuario,
        "conta": conta,
        "categoria_nome": _categoria_nome_com_centros(centros_por_cliente),
        "formas_pagamento": list(FormaPagamento),
    })


@router.post("/contas-pagar/{conta_id}/editar")
async def salvar_edicao_conta(
    conta_id: int,
    descricao: str = Form(...),
    fornecedor: Optional[str] = Form(None),
    valor: Decimal = Form(...),
    vencimento: date = Form(...),
    data_competencia: Optional[date] = Form(None),
    forma_pagamento: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta or conta.cliente_id not in _ids_clientes_do_usuario(db, usuario):
        return RedirectResponse(url="/contas-pagar", status_code=303)
    if conta.status == StatusContaPagar.pago:
        return RedirectResponse(
            url=f"/contas-pagar?cliente_id={conta.cliente_id}&flash=Conta+j%C3%A1+paga%2C+n%C3%A3o+pode+ser+editada",
            status_code=303,
        )

    conta.descricao = descricao
    conta.fornecedor = fornecedor or None
    conta.valor = valor
    conta.vencimento = vencimento
    conta.data_competencia = data_competencia or vencimento
    conta.forma_pagamento = forma_pagamento if forma_pagamento in FORMAS_PAGAMENTO_VALIDAS else None
    conta.observacao = observacao or None
    db.commit()
    _log(
        db, "Conta a pagar editada", "contas_pagar",
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        cliente_id=conta.cliente_id,
        detalhes=f"Conta #{conta_id} editada",
    )
    return RedirectResponse(url=f"/contas-pagar?cliente_id={conta.cliente_id}", status_code=303)


@router.post("/contas-pagar")
async def criar_conta(
    cliente_id: int = Form(...),
    descricao: str = Form(...),
    fornecedor: Optional[str] = Form(None),
    valor: Decimal = Form(...),
    vencimento: date = Form(...),
    data_competencia: Optional[date] = Form(None),
    forma_pagamento: Optional[str] = Form(None),
    categoria_dre: Optional[str] = Form(None),
    rateio_centro_custo_key: List[str] = Form(default=[]),
    rateio_percentual: List[str] = Form(default=[]),
    especialidade: Optional[str] = Form(None),
    observacao: Optional[str] = Form(None),
    documento: Optional[UploadFile] = File(None),
    recorrente: bool = Form(False),
    recorrencia_intervalo: str = Form("mensal"),
    recorrencia_dias: Optional[int] = Form(None),
    recorrencia_qtd: int = Form(1),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    if recorrente and recorrencia_intervalo not in FREQUENCIAS_RECORRENCIA:
        recorrencia_intervalo = "mensal"
    qtd_ocorrencias = max(1, min(recorrencia_qtd or 1, RECORRENCIA_QTD_MAXIMA)) if recorrente else 1
    tipo = TipoContaPagar.fixa if recorrente else TipoContaPagar.pontual
    forma_pagamento = forma_pagamento if forma_pagamento in FORMAS_PAGAMENTO_VALIDAS else None
    data_competencia = data_competencia or vencimento

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
        data_competencia=data_competencia,
        forma_pagamento=forma_pagamento,
        categoria_dre=categoria_compat,
        especialidade=especialidade_valor,
        status=StatusContaPagar.pendente,
        documento_path=documento_path,
        observacao=observacao or None,
        lancado_por_id=usuario.id,
        recorrencia_intervalo=recorrencia_intervalo if recorrente else None,
        recorrencia_dias=recorrencia_dias if recorrente and recorrencia_intervalo == "personalizado" else None,
    )
    db.add(conta)
    db.flush()
    if recorrente:
        conta.recorrencia_grupo_id = conta.id
    for r in rateios:
        db.add(ContaPagarCentroCustoRateio(
            conta_pagar_id=conta.id,
            centro_custo_id=r["centro"].id,
            categoria_key=r["categoria_key"],
            percentual=r["percentual"],
            valor=r["valor"],
        ))

    proximas_geradas = 0
    if recorrente and qtd_ocorrencias > 1:
        for indice in range(1, qtd_ocorrencias):
            data_ocorrencia = _data_recorrencia(vencimento, recorrencia_intervalo, recorrencia_dias, indice)
            data_competencia_ocorrencia = _data_recorrencia(data_competencia, recorrencia_intervalo, recorrencia_dias, indice)
            db.add(ContaPagar(
                cliente_id=cliente_id,
                descricao=descricao,
                fornecedor=fornecedor or None,
                tipo=tipo,
                valor=valor,
                vencimento=data_ocorrencia,
                data_competencia=data_competencia_ocorrencia,
                forma_pagamento=forma_pagamento,
                categoria_dre=categoria_compat,
                especialidade=especialidade_valor,
                status=StatusContaPagar.pendente,
                observacao=observacao or None,
                lancado_por_id=usuario.id,
                recorrencia_intervalo=recorrencia_intervalo,
                recorrencia_dias=recorrencia_dias if recorrencia_intervalo == "personalizado" else None,
                recorrencia_grupo_id=conta.id,
            ))
            proximas_geradas += 1

    db.commit()
    cliente_obj = next((c for c in clientes_do_usuario(db, usuario) if c.id == cliente_id), None)
    detalhes = f"{descricao} — R$ {valor} | venc. {vencimento.strftime('%d/%m/%Y')}"
    if proximas_geradas:
        detalhes += f" | + {proximas_geradas} ocorrência(s) futura(s) geradas ({recorrencia_intervalo})"
    _log(
        db, "Conta a pagar criada", "contas_pagar",
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        cliente_id=cliente_id, cliente_nome=cliente_obj.nome if cliente_obj else None,
        detalhes=detalhes,
    )
    return RedirectResponse(url=f"/contas-pagar?cliente_id={cliente_id}", status_code=303)


@router.post("/contas-pagar/importar")
async def importar_contas(
    request: Request,
    cliente_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
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

    except Exception as e:
        flash_error = str(e)
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
    status_permitidos_por_conta = {c.id: [s.value for s in _status_permitidos(c.status)] for c in contas}

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
        "status_permitidos_por_conta": status_permitidos_por_conta,
    })


@router.post("/contas-pagar/{conta_id}/status")
async def alterar_status_conta_rota(
    conta_id: int,
    novo_status: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    clientes = clientes_do_usuario(db, usuario)
    if conta.cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    try:
        status_enum = StatusContaPagar(novo_status)
    except ValueError:
        return RedirectResponse(url=f"/contas-pagar?cliente_id={conta.cliente_id}", status_code=303)

    if not _alterar_status_conta(db, conta, status_enum, usuario):
        return RedirectResponse(
            url=f"/contas-pagar?cliente_id={conta.cliente_id}&flash=Transi%C3%A7%C3%A3o+de+status+n%C3%A3o+permitida",
            status_code=303,
        )
    return RedirectResponse(url=f"/contas-pagar?cliente_id={conta.cliente_id}", status_code=303)


@router.post("/contas-pagar/{conta_id}/agendar")
async def agendar_pagamento(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    """Wrapper de compatibilidade — equivalente a status=agendado."""
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta:
        return RedirectResponse(url="/contas-pagar", status_code=303)
    clientes = clientes_do_usuario(db, usuario)
    if conta.cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)
    _alterar_status_conta(db, conta, StatusContaPagar.agendado, usuario)
    return RedirectResponse(url=f"/contas-pagar?cliente_id={conta.cliente_id}", status_code=303)


@router.post("/contas-pagar/{conta_id}/cancelar")
async def cancelar_conta(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    """Wrapper de compatibilidade — equivalente a status=cancelado."""
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta:
        return RedirectResponse(url="/contas-pagar", status_code=303)
    clientes = clientes_do_usuario(db, usuario)
    if conta.cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)
    _alterar_status_conta(db, conta, StatusContaPagar.cancelado, usuario)
    return RedirectResponse(url=f"/contas-pagar?cliente_id={conta.cliente_id}", status_code=303)
