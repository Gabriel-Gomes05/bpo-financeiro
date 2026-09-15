from app.services.desconciliacao_service import desconciliar_pagamento, exigir_confirmacao
import os
import logging
import re
import shutil
import unicodedata
import uuid
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, List
from urllib.parse import quote_plus

import pandas as pd

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.authorization import Permission, require_permission
from app.config import UPLOAD_DIR
from app.constants import CATEGORIAS_DESPESA, CATEGORIA_NOME
from app.database import get_db
from app.utils import cliente_ativo as _ca, salvar_upload_temporario
from app.models import (
    CentroCusto,
    ClienteBPO,
    ContaPagar,
    ContaPagarCentroCustoRateio,
    ExtratoLinhaBancaria,
    FormaPagamento,
    MovimentacaoBancaria,
    PerfilUsuario,
    PlanoConta,
    StatusContaPagar,
    TipoContaPagar,
    Usuario,
)
from app.services.log_service import registrar as _log
from app.errors import public_import_error
from app.security import secure_cookie_for

router = APIRouter()
require_contas_pagar = require_permission(Permission.CONTAS_PAGAR)
logger = logging.getLogger(__name__)


def _planos_despesa(db: Session, cliente_ids: list[int]) -> list[PlanoConta]:
    return db.query(PlanoConta).filter(
        PlanoConta.tipo == "despesa",
        PlanoConta.ativo == True,
        or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id.in_(cliente_ids)),
    ).order_by(PlanoConta.codigo.asc(), PlanoConta.nome.asc()).all()


def _plano_despesa_valido(db: Session, cliente_id: int, plano_conta_id: int | None) -> PlanoConta | None:
    if not plano_conta_id:
        return None
    return db.query(PlanoConta).filter(
        PlanoConta.id == plano_conta_id,
        PlanoConta.tipo == "despesa",
        PlanoConta.ativo == True,
        or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == cliente_id),
    ).first()



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
        percentual_raw = percentuais[i] if i < len(percentuais) else ""
        if not (cat or "").strip() and not (percentual_raw or "").strip():
            continue
        pct = _decimal_rateio(percentual_raw)
        cc = _centro_por_key(db, cliente_id, cat)
        if not cc or pct is None or pct <= 0 or pct > 100 or cc.id in centros_usados:
            return []
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
    StatusContaPagar.aguardando_aprovacao: {StatusContaPagar.agendado, StatusContaPagar.cancelado},
    StatusContaPagar.agendado: {StatusContaPagar.pago_nao_conciliado, StatusContaPagar.aguardando_aprovacao, StatusContaPagar.cancelado},
    StatusContaPagar.pago_nao_conciliado: {StatusContaPagar.agendado, StatusContaPagar.cancelado},
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
    situacao: Optional[str] = None,
    status: Optional[str] = None,
    forma_pagamento: Optional[str] = None,
    vencimento_inicio: Optional[str] = None,
    vencimento_fim: Optional[str] = None,
    flash: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    cliente_id = _ca(request, None)
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    status = status if status in {s.value for s in StatusContaPagar} else None
    forma_pagamento = forma_pagamento if forma_pagamento in {f.value for f in FormaPagamento} else None
    try:
        venc_inicio = date.fromisoformat(vencimento_inicio) if vencimento_inicio else None
    except ValueError:
        venc_inicio = None
    try:
        venc_fim = date.fromisoformat(vencimento_fim) if vencimento_fim else None
    except ValueError:
        venc_fim = None

    query = db.query(ContaPagar).filter(
        ContaPagar.cliente_id.in_(ids_permitidos)
    )
    if cliente_id:
        query = query.filter(ContaPagar.cliente_id == cliente_id)
    if status:
        query = query.filter(ContaPagar.status == status)
    if forma_pagamento:
        query = query.filter(ContaPagar.forma_pagamento == forma_pagamento)
    if venc_inicio:
        query = query.filter(ContaPagar.vencimento >= venc_inicio)
    if venc_fim:
        query = query.filter(ContaPagar.vencimento <= venc_fim)

    if situacao in {"aberto", "a_vencer", "vencidas"}:
        query = query.filter(ContaPagar.status.notin_([StatusContaPagar.pago, StatusContaPagar.cancelado]))
        if situacao == "a_vencer":
            query = query.filter(ContaPagar.vencimento >= date.today())
        elif situacao == "vencidas":
            query = query.filter(ContaPagar.vencimento < date.today())

    # Ordena: vencidas primeiro, depois por vencimento
    contas = query.order_by(ContaPagar.vencimento.asc()).limit(200).all()
    hoje_media = date.today()
    meses_media = []
    for deslocamento in (2, 1, 0):
        total_meses = hoje_media.year * 12 + hoje_media.month - 1 - deslocamento
        meses_media.append((total_meses // 12, total_meses % 12 + 1))
    inicio_media = date(meses_media[0][0], meses_media[0][1], 1)
    historico_media = db.query(ContaPagar).filter(
        ContaPagar.cliente_id.in_(ids_permitidos),
        ContaPagar.vencimento >= inicio_media,
        ContaPagar.vencimento <= date.today(),
        ContaPagar.status != StatusContaPagar.cancelado,
    ).all()
    valores_por_despesa: dict[tuple[int, str], list[tuple[date, Decimal]]] = {}
    for item in historico_media:
        chave_descricao = " ".join((item.descricao or "").casefold().split())
        valores_por_despesa.setdefault((item.cliente_id, chave_descricao), []).append((item.vencimento, item.valor))
    nomes_meses = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")
    medias_por_conta = {}
    for item in contas:
        chave_descricao = " ".join((item.descricao or "").casefold().split())
        ocorrencias = valores_por_despesa.get((item.cliente_id, chave_descricao), [])
        valores = [valor_item for _, valor_item in ocorrencias]
        medias_por_conta[item.id] = {
            "media": (sum(valores, Decimal("0")) / len(valores)).quantize(Decimal("0.01")) if valores else None,
            "quantidade": len(valores),
            "meses": [
                {
                    "label": nomes_meses[mes - 1],
                    "valor": float(sum(
                        (valor_item for vencimento_item, valor_item in ocorrencias
                         if vencimento_item.year == ano and vencimento_item.month == mes),
                        Decimal("0"),
                    )),
                }
                for ano, mes in meses_media
            ],
        }
    centros_por_cliente = _centros_custo_por_cliente(db, ids_permitidos)
    status_permitidos_por_conta = {c.id: [s.value for s in _status_permitidos(c.status)] for c in contas}

    return templates.TemplateResponse("contas_pagar.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "contas": contas,
        "situacao_selecionada": situacao,
        "planos_lote": _planos_despesa(db, ids_permitidos),
        "centros_lote": db.query(CentroCusto).filter(CentroCusto.cliente_id.in_(ids_permitidos), CentroCusto.ativo == True).order_by(CentroCusto.nome).all(),
        "hoje": date.today(),
        "cliente_selecionado": cliente_id,
        "status_selecionado": status,
        "forma_pagamento_selecionada": forma_pagamento,
        "vencimento_inicio": vencimento_inicio or "",
        "vencimento_fim": vencimento_fim or "",
        "categorias_despesa": CATEGORIAS_DESPESA,
        "categoria_nome": _categoria_nome_com_centros(centros_por_cliente),
        "status_permitidos_por_conta": status_permitidos_por_conta,
        "medias_por_conta": medias_por_conta,
        "inicio_media": inicio_media,
        "flash": flash,
    })


@router.get("/contas-pagar/novo", response_class=HTMLResponse)
async def pagina_nova_conta(
    request: Request,
    cliente_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cliente_id = _ca(request, cliente_id)
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    centros_por_cliente = _centros_custo_por_cliente(db, ids_permitidos)

    return templates.TemplateResponse("contas_pagar_novo.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "cliente_selecionado": cliente_id if cliente_id in ids_permitidos else None,
        "centros_custo_por_cliente": centros_por_cliente,
        "planos_conta_despesa": _planos_despesa(db, ids_permitidos),
        "conta_origem": None,
        "rateios_iniciais": [],
    })


@router.get("/contas-pagar/{conta_id}/clonar", response_class=HTMLResponse)
async def clonar_conta(
    conta_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    ids_permitidos = _ids_clientes_do_usuario(db, usuario)
    if not conta or conta.cliente_id not in ids_permitidos:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    return templates.TemplateResponse("contas_pagar_novo.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes_do_usuario(db, usuario),
        "cliente_selecionado": conta.cliente_id,
        "centros_custo_por_cliente": _centros_custo_por_cliente(db, ids_permitidos),
        "planos_conta_despesa": _planos_despesa(db, ids_permitidos),
        "conta_origem": conta,
        "rateios_iniciais": [
            {"key": rateio.categoria_key, "percentual": float(rateio.percentual)}
            for rateio in conta.rateios_centro_custo
        ],
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

    centros_por_cliente = _centros_custo_por_cliente(db, [conta.cliente_id])
    return templates.TemplateResponse("contas_pagar_editar.html", {
        "request": request,
        "usuario": usuario,
        "conta": conta,
        "categoria_nome": _categoria_nome_com_centros(centros_por_cliente),
        "formas_pagamento": list(FormaPagamento),
        "planos_conta_despesa": _planos_despesa(db, [conta.cliente_id]),
        "centros_custo": centros_por_cliente.get(conta.cliente_id, []),
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
    plano_conta_id: Optional[int] = Form(None),
    observacao: Optional[str] = Form(None),
    escopo_valor: str = Form("somente"),
    rateio_centro_custo_key: Optional[List[str]] = Form(None),
    rateio_percentual: Optional[List[str]] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
    confirmar_conciliacao: bool = Form(False),
):
    if usuario.perfil == PerfilUsuario.medico:
        raise HTTPException(403, "Perfil somente leitura.")
    if escopo_valor not in {"somente", "proximos"}:
        raise HTTPException(400, "Opção de edição inválida.")
    if not valor.is_finite() or valor < 0 or valor > Decimal("9999999999.99") or valor != valor.quantize(Decimal("0.01")):
        raise HTTPException(400, "Informe um valor válido com até duas casas decimais.")
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta or conta.cliente_id not in _ids_clientes_do_usuario(db, usuario):
        return RedirectResponse(url="/contas-pagar", status_code=303)


    novos_rateios = None
    if isinstance(rateio_centro_custo_key, list):
        novos_rateios = _montar_rateios_conta(
            db, conta.cliente_id, valor, rateio_centro_custo_key,
            rateio_percentual if isinstance(rateio_percentual, list) else [],
        )
        if any(key.strip() for key in rateio_centro_custo_key) and not novos_rateios:
            raise HTTPException(400, "Rateio invalido: use centros diferentes e feche 100%.")

    contas_valor = [conta]
    if escopo_valor == "proximos" and conta.recorrencia_grupo_id:
        grupo_id = conta.recorrencia_grupo_id
        contas_valor = db.query(ContaPagar).filter(
            ContaPagar.cliente_id == conta.cliente_id,
            or_(ContaPagar.id == grupo_id, ContaPagar.recorrencia_grupo_id == grupo_id),
            or_(
                ContaPagar.vencimento > conta.vencimento,
                (ContaPagar.vencimento == conta.vencimento) & (ContaPagar.id >= conta.id),
            ),
        ).order_by(ContaPagar.vencimento, ContaPagar.id).all()
    protegidos = _ids_protegidos(db, contas_valor)
    if protegidos and confirmar_conciliacao is True:
        for item in contas_valor:
            if item.id in protegidos:
                desconciliar_pagamento(db, item)
        protegidos.clear()
    elif conta.id in protegidos:
        exigir_confirmacao(confirmar_conciliacao)
    contas_valor = [item for item in contas_valor if item.id not in protegidos]
    ids = [item.id for item in contas_valor]
    ignorados = len(protegidos)
    for item in contas_valor:
        item.valor = valor
        rateios = item.rateios_centro_custo
        if rateios:
            for rateio in rateios:
                rateio.valor = (valor * rateio.percentual / Decimal("100")).quantize(Decimal("0.01"))
            rateios[-1].valor += valor - sum((r.valor for r in rateios), Decimal("0"))

    if novos_rateios is not None:
        conta.rateios_centro_custo = [ContaPagarCentroCustoRateio(
            centro_custo_id=r["centro"].id,
            categoria_key=r["categoria_key"],
            percentual=r["percentual"],
            valor=r["valor"],
        ) for r in novos_rateios]

    conta.descricao = descricao
    conta.fornecedor = fornecedor or None
    conta.valor = valor
    conta.vencimento = vencimento
    conta.data_competencia = data_competencia or vencimento
    conta.forma_pagamento = forma_pagamento if forma_pagamento in FORMAS_PAGAMENTO_VALIDAS else None
    plano = _plano_despesa_valido(db, conta.cliente_id, plano_conta_id)
    conta.plano_conta_id = plano.id if plano else None
    conta.categoria_dre = plano.chave if plano else None
    conta.observacao = observacao or None
    db.commit()
    _log(
        db, "Conta a pagar editada", "contas_pagar",
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        cliente_id=conta.cliente_id,
        detalhes=f"Conta #{conta_id} editada; escopo do valor: {escopo_valor}; valor: {valor}; IDs: {ids}; ignorados por pagamento/conciliação: {ignorados}",
    )
    mensagem = None
    if ignorados:
        mensagem = f"Valor atualizado em {len(ids)} lançamento(s). {ignorados} não foram alterados por já estarem pagos ou conciliados."
    destino = f"/contas-pagar?cliente_id={conta.cliente_id}"
    if mensagem:
        destino += "&flash=" + quote_plus(mensagem)
    return RedirectResponse(url=destino, status_code=303)


def _ids_protegidos(db: Session, contas: list[ContaPagar]) -> set[int]:
    """IDs de contas com pagamento ou conciliação, que não podem ser alteradas/excluídas."""
    if not contas:
        return set()
    ids = [conta.id for conta in contas]
    protegidos = {conta.id for conta in contas if conta.status == StatusContaPagar.pago or conta.pagamentos_parciais}
    protegidos.update(
        row[0] for row in db.query(MovimentacaoBancaria.conta_pagar_id)
        .filter(MovimentacaoBancaria.conta_pagar_id.in_(ids)).all()
    )
    protegidos.update(
        row[0] for row in db.query(ExtratoLinhaBancaria.conta_pagar_id)
        .filter(ExtratoLinhaBancaria.conta_pagar_id.in_(ids)).all()
    )
    return protegidos


def _preparar_exclusao_recorrencias(db: Session, contas: list[ContaPagar]) -> None:
    """Preserva o grupo restante quando seu lançamento de referência é excluído."""
    ids = {conta.id for conta in contas}
    dependentes = db.query(ContaPagar).filter(
        ContaPagar.recorrencia_grupo_id.in_(ids),
    ).order_by(ContaPagar.id).all()
    grupos: dict[int, list[ContaPagar]] = {}
    clientes = {conta.id: conta.cliente_id for conta in contas}
    for dependente in dependentes:
        if dependente.cliente_id != clientes[dependente.recorrencia_grupo_id]:
            raise HTTPException(409, "Recorrência inconsistente entre clientes.")
        if dependente.id not in ids:
            grupos.setdefault(dependente.recorrencia_grupo_id, []).append(dependente)
    for restantes in grupos.values():
        novo_grupo_id = restantes[0].id
        for restante in restantes:
            restante.recorrencia_grupo_id = novo_grupo_id
    for conta in contas:
        conta.recorrencia_grupo_id = None
    # Atualiza as referências antes dos DELETEs, inclusive a autorreferência do grupo.
    db.flush()


@router.post("/contas-pagar/{conta_id}/excluir")
async def excluir_conta(
    conta_id: int,
    request: Request,
    cliente_id: int = Form(...),
    escopo: str = Form("somente"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
    confirmar_conciliacao: bool = Form(False),
):
    if usuario.perfil == PerfilUsuario.medico:
        raise HTTPException(403, "Perfil somente leitura.")
    if escopo not in {"somente", "recorrencia"}:
        raise HTTPException(400, "Opção de exclusão inválida.")
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    ids_permitidos = _ids_clientes_do_usuario(db, usuario)
    destino = f"/contas-pagar?cliente_id={cliente_id}"
    if not conta or conta.cliente_id not in ids_permitidos or conta.cliente_id != cliente_id:
        return RedirectResponse(url=destino, status_code=303)

    contas = [conta]
    if escopo == "recorrencia":
        grupo_id = conta.recorrencia_grupo_id or conta.id
        contas = db.query(ContaPagar).filter(
            ContaPagar.cliente_id == cliente_id,
            or_(ContaPagar.id == grupo_id, ContaPagar.recorrencia_grupo_id == grupo_id),
        ).order_by(ContaPagar.id).all()

    protegidos = _ids_protegidos(db, contas)
    if protegidos and confirmar_conciliacao is True:
        for item in contas:
            if item.id in protegidos:
                desconciliar_pagamento(db, item)
        protegidos.clear()
    elif escopo == "somente" and conta.id in protegidos:
        exigir_confirmacao(confirmar_conciliacao)

    elegiveis = [item for item in contas if item.id not in protegidos]
    if not elegiveis:
        mensagem = "Este lançamento tem pagamento ou conciliação e não pode ser excluído." if escopo == "somente" else "Todos os lançamentos dessa recorrência têm pagamento ou conciliação. Nada foi excluído."
        return RedirectResponse(url=f"{destino}&flash=" + quote_plus(mensagem), status_code=303)

    ids = [item.id for item in elegiveis]
    documentos = [item.documento_path for item in elegiveis if item.documento_path]
    _preparar_exclusao_recorrencias(db, elegiveis)
    for item in elegiveis:
        db.delete(item)
    db.commit()
    for documento in documentos:
        caminho = Path(documento).resolve()
        if Path(UPLOAD_DIR).resolve() in caminho.parents and caminho.is_file():
            try:
                caminho.unlink()
            except OSError:
                logger.warning("conta_documento_delete_failed", extra={"conta_id": conta_id})
    _log(
        db, "Conta a pagar excluída", "contas_pagar",
        usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
        detalhes=f"Escopo: {escopo}; IDs excluídos: {ids}; ignorados por pagamento/conciliação: {len(protegidos)}",
        ip=request.client.host if request.client else None,
    )
    mensagem = f"{len(elegiveis)} lançamento(s) excluído(s) com sucesso."
    if protegidos:
        mensagem += f" {len(protegidos)} não foram excluídos por já estarem pagos ou conciliados."
    return RedirectResponse(url=f"{destino}&flash=" + quote_plus(mensagem), status_code=303)


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
    plano_conta_id: Optional[int] = Form(None),
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
    usuario: Usuario = Depends(require_contas_pagar),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    if usuario.perfil == PerfilUsuario.medico:
        raise HTTPException(403, "Perfil somente leitura.")
    if recorrente and recorrencia_intervalo not in FREQUENCIAS_RECORRENCIA:
        raise HTTPException(400, "Intervalo de recorrencia invalido.")
    if recorrente and (not 1 <= recorrencia_qtd <= RECORRENCIA_QTD_MAXIMA or (recorrencia_intervalo == "personalizado" and (not recorrencia_dias or not 1 <= recorrencia_dias <= 3660))):
        raise HTTPException(400, "Revise a quantidade e os dias da recorrencia.")
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
    plano = _plano_despesa_valido(db, cliente_id, plano_conta_id)
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
        plano_conta_id=plano.id if plano else None,
        especialidade=especialidade_valor,
        status=StatusContaPagar.aguardando_aprovacao,
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
            documento_ocorrencia = None
            if documento_path:
                origem_documento = Path(documento_path)
                documento_ocorrencia = str(origem_documento.with_name(
                    f"{uuid.uuid4().hex}{origem_documento.suffix}"
                ))
                shutil.copyfile(documento_path, documento_ocorrencia)
            nova_conta = ContaPagar(
                cliente_id=conta.cliente_id,
                descricao=conta.descricao,
                fornecedor=conta.fornecedor,
                tipo=conta.tipo,
                valor=conta.valor,
                vencimento=data_ocorrencia,
                data_competencia=_data_recorrencia(data_competencia, recorrencia_intervalo, recorrencia_dias, indice),
                forma_pagamento=conta.forma_pagamento,
                categoria_dre=conta.categoria_dre,
                plano_conta_id=conta.plano_conta_id,
                especialidade=conta.especialidade,
                status=conta.status,
                documento_path=documento_ocorrencia,
                observacao=conta.observacao,
                lancado_por_id=conta.lancado_por_id,
                recorrencia_intervalo=conta.recorrencia_intervalo,
                recorrencia_dias=conta.recorrencia_dias,
                recorrencia_grupo_id=conta.id,
                rateios_centro_custo=[ContaPagarCentroCustoRateio(
                    centro_custo_id=r["centro"].id,
                    categoria_key=r["categoria_key"],
                    percentual=r["percentual"],
                    valor=r["valor"],
                ) for r in rateios],
            )
            db.add(nova_conta)
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
    usuario: Usuario = Depends(require_contas_pagar),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/contas-pagar", status_code=303)

    if usuario.perfil == PerfilUsuario.medico:
        raise HTTPException(403, "Perfil somente leitura.")

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
        c_comp = _col(df, ["data_competencia", "competencia"])
        c_forma = _col(df, ["forma_pagamento", "forma_de_pagamento"])
        c_recorrente = _col(df, ["recorrente"])
        c_intervalo = _col(df, ["recorrencia_intervalo", "intervalo"])
        c_dias = _col(df, ["recorrencia_dias"])
        c_qtd = _col(df, ["recorrencia_qtd", "quantidade"])
        c_plano = _col(df, ["plano_de_contas", "plano_contas", "plano_de_conta", "plano_conta", "codigo_plano_conta"])

        planos_importacao = _planos_despesa(db, [cliente_id])
        planos_por_referencia = {}
        for plano in planos_importacao:
            if plano.codigo:
                planos_por_referencia[_norm(plano.codigo)] = plano
            planos_por_referencia[_norm(plano.nome)] = plano

        if not c_desc or not c_valor or not c_venc:
            raise ValueError(
                "Planilha deve ter colunas: descricao, valor e vencimento "
                f"(encontradas: {list(df.columns)})"
            )

        novas_series = []
        importadas = 0
        for numero, (_, row) in enumerate(df.iterrows(), start=2):
            if row.isna().all():
                continue

            def texto(coluna):
                return str(row[coluna]).strip() if coluna and pd.notna(row[coluna]) else ""

            try:
                descricao = texto(c_desc)
                if not descricao:
                    raise ValueError("Informe a descricao.")
                valor_raw = texto(c_valor).replace("R$", "").replace(" ", "")
                if "," in valor_raw:
                    valor_raw = valor_raw.replace(".", "").replace(",", ".")
                valor = Decimal(valor_raw)
                if not valor.is_finite() or valor <= 0 or valor > Decimal("9999999999.99"):
                    raise ValueError("Valor deve ser positivo e finito.")
                valor = valor.quantize(Decimal("0.01"))
                vencimento = pd.to_datetime(row[c_venc], dayfirst=isinstance(row[c_venc], str) and "/" in row[c_venc]).date()
                if pd.isna(vencimento):
                    raise ValueError("Informe o vencimento.")
                competencia_raw = texto(c_comp)
                competencia = pd.to_datetime(competencia_raw, dayfirst="/" in competencia_raw).date() if competencia_raw else vencimento
                if pd.isna(competencia):
                    raise ValueError("Data de competencia invalida.")
                referencia_plano = texto(c_plano)
                plano = planos_por_referencia.get(_norm(referencia_plano)) if referencia_plano else None
                if referencia_plano and not plano:
                    raise ValueError("Plano de despesa nao encontrado para esta empresa.")
                forma = _norm(texto(c_forma))
                if forma and forma not in FORMAS_PAGAMENTO_VALIDAS:
                    raise ValueError("Forma de pagamento invalida.")
                intervalo = _norm(texto(c_intervalo))
                tipo_raw = _norm(texto(c_tipo))
                recorrente_raw = _norm(texto(c_recorrente))
                if recorrente_raw and recorrente_raw not in {"sim", "true", "1", "1_0", "nao", "false", "0", "0_0"}:
                    raise ValueError("Recorrente deve ser sim ou nao.")
                recorrente = recorrente_raw in {"sim", "true", "1", "1_0"} or bool(intervalo) or tipo_raw in {"fixa", "recorrente"}
                intervalo = intervalo or "mensal"
                if recorrente and intervalo not in FREQUENCIAS_RECORRENCIA:
                    raise ValueError("Intervalo de recorrencia invalido.")
                quantidade_raw = Decimal(texto(c_qtd) or "1")
                if not quantidade_raw.is_finite() or quantidade_raw != quantidade_raw.to_integral_value() or not 1 <= quantidade_raw <= RECORRENCIA_QTD_MAXIMA:
                    raise ValueError("Quantidade deve ser inteira, de 1 a 60.")
                quantidade = int(quantidade_raw)
                if not recorrente and quantidade != 1:
                    raise ValueError("Marque recorrente para gerar mais de uma ocorrencia.")
                dias_raw = Decimal(texto(c_dias) or "0")
                if not dias_raw.is_finite() or dias_raw != dias_raw.to_integral_value() or not 0 <= dias_raw <= 3660:
                    raise ValueError("Dias de recorrencia invalidos.")
                dias = int(dias_raw)
                if recorrente and intervalo == "personalizado" and dias < 1:
                    raise ValueError("Informe os dias do intervalo personalizado.")
                serie = []
                for indice in range(quantidade):
                    serie.append(ContaPagar(
                        cliente_id=cliente_id, descricao=descricao,
                        fornecedor=texto(c_forn) or None,
                        tipo=TipoContaPagar.fixa if recorrente else TipoContaPagar.pontual,
                        valor=valor,
                        vencimento=_data_recorrencia(vencimento, intervalo, dias, indice),
                        data_competencia=_data_recorrencia(competencia, intervalo, dias, indice),
                        forma_pagamento=forma or None,
                        plano_conta_id=plano.id if plano else None,
                        categoria_dre=plano.chave if plano else None,
                        observacao=texto(c_obs) or None,
                        status=StatusContaPagar.aguardando_aprovacao,
                        lancado_por_id=usuario.id,
                        recorrencia_intervalo=intervalo if recorrente else None,
                        recorrencia_dias=dias if recorrente and intervalo == "personalizado" else None,
                    ))
                novas_series.append(serie)
            except (ValueError, InvalidOperation, OverflowError) as exc:
                raise ValueError(f"Linha {numero}: {exc}") from exc

        for serie in novas_series:
            db.add(serie[0])
            db.flush()
            if serie[0].recorrencia_intervalo:
                for conta in serie:
                    conta.recorrencia_grupo_id = serie[0].id
            db.add_all(serie[1:])
            importadas += len(serie)

        db.commit()
        flash_success = f"{importadas} conta(s) importada(s) de '{nome_original}'."
        _log(
            db, "Contas importadas", "contas_pagar",
            usuario_id=usuario.id, usuario_nome=usuario.nome,
            cliente_id=cliente_id,
            detalhes=f"{importadas} conta(s) de '{nome_original}'",
        )

    except ValueError as exc:
        db.rollback()
        flash_error = f"Nenhuma conta importada. {exc}"
    except Exception:
        db.rollback()
        flash_error = public_import_error(logger, "importar_contas_pagar")
    finally:
        try:
            if caminho:
                os.remove(caminho)
        except OSError:
            pass

    response = RedirectResponse(
        url="/contas-pagar?cliente_id=" + str(cliente_id) + "&flash=" + quote_plus(flash_error or flash_success or ""),
        status_code=303,
    )
    response.set_cookie("cliente_ativo", str(cliente_id), httponly=True, samesite="strict", secure=secure_cookie_for(request), path="/")
    return response

@router.post("/contas-pagar/{conta_id}/status")
async def alterar_status_conta_rota(
    conta_id: int,
    novo_status: str = Form(...),
    retorno: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
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
    destino = retorno if retorno and retorno.startswith("/fechamento") else f"/contas-pagar?cliente_id={conta.cliente_id}"
    return RedirectResponse(url=destino, status_code=303)


@router.post("/contas-pagar/{conta_id}/recebido")
async def alterar_recebido_conta(
    conta_id: int,
    recebido: bool = Form(False),
    retorno: str = Form("/contas-pagar"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
):
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if not conta or conta.cliente_id not in _ids_clientes_do_usuario(db, usuario):
        return RedirectResponse(url="/contas-pagar", status_code=303)
    conta.recebido = recebido
    db.commit()
    _log(db, "Recebimento informativo alterado", "contas_pagar",
         usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=conta.cliente_id,
         detalhes=f"Conta #{conta.id}: {'Sim' if recebido else 'Não'}")
    destino = retorno if retorno.startswith("/fechamento") else f"/contas-pagar?cliente_id={conta.cliente_id}"
    return RedirectResponse(url=destino, status_code=303)


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
    usuario: Usuario = Depends(require_contas_pagar),
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


@router.post("/contas-pagar/lote/aplicar")
async def aplicar_lote_contas(
    request: Request,
    ids: List[int] = Form(...),
    acao: str = Form(...),
    plano_conta_id: Optional[int] = Form(None),
    centro_custo_id: Optional[int] = Form(None),
    novo_status: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_contas_pagar),
    confirmar_conciliacao: bool = Form(False),
):
    if usuario.perfil == PerfilUsuario.medico:
        raise HTTPException(403, "Perfil somente leitura.")
    if acao not in {"editar", "excluir"} or not ids or len(set(ids)) > 200:
        raise HTTPException(400, "Seleção ou ação inválida.")
    contas = db.query(ContaPagar).filter(ContaPagar.id.in_(set(ids)), ContaPagar.cliente_id.in_(_ids_clientes_do_usuario(db, usuario))).all()
    if len(contas) != len(set(ids)):
        raise HTTPException(404, "Seleção contém contas indisponíveis.")
    def erro(mensagem):
        return RedirectResponse("/contas-pagar?flash=" + quote_plus(mensagem + " Nenhuma conta foi alterada."), status_code=303)
    if acao == "editar" and not (plano_conta_id or centro_custo_id or novo_status):
        return erro("Escolha ao menos um campo para editar.")

    protegidos = _ids_protegidos(db, contas)
    elegiveis = contas if confirmar_conciliacao is True else [conta for conta in contas if conta.id not in protegidos]
    if not elegiveis:
        return erro("Todas as contas selecionadas têm pagamento ou conciliação.")

    planos, centros = {}, {}
    for conta in elegiveis:
        if acao == "excluir":
            continue
        if plano_conta_id:
            planos[conta.id] = _plano_despesa_valido(db, conta.cliente_id, plano_conta_id)
            if not planos[conta.id]:
                return erro("Categoria inválida para um dos clientes selecionados.")
        if centro_custo_id:
            centros[conta.id] = db.query(CentroCusto).filter(CentroCusto.id == centro_custo_id, CentroCusto.cliente_id == conta.cliente_id, CentroCusto.ativo == True).first()
            if not centros[conta.id]:
                return erro("Centro de custo inválido para um dos clientes selecionados.")
        status_base = StatusContaPagar.pendente if conta.id in protegidos and confirmar_conciliacao is True else conta.status
        if novo_status and novo_status != status_base.value and novo_status not in {s.value for s in _status_permitidos(status_base)}:
            return erro("Transição de status não permitida. Pagamentos são registrados pela conciliação.")
    if confirmar_conciliacao is True:
        for conta in elegiveis:
            if conta.id in protegidos:
                desconciliar_pagamento(db, conta)
        protegidos.clear()
    documentos = []
    if acao == "excluir":
        _preparar_exclusao_recorrencias(db, elegiveis)
    for conta in elegiveis:
        if acao == "excluir":
            if conta.documento_path:
                documentos.append(conta.documento_path)
            db.delete(conta)
        else:
            if plano_conta_id:
                conta.plano_conta_id = planos[conta.id].id
                conta.categoria_dre = planos[conta.id].chave
            if centro_custo_id:
                centro = centros[conta.id]
                conta.rateios_centro_custo.clear()
                conta.rateios_centro_custo.append(ContaPagarCentroCustoRateio(centro_custo_id=centro.id, categoria_key=_key_centro_custo(centro), percentual=Decimal("100"), valor=conta.valor))
            if novo_status:
                conta.status = StatusContaPagar(novo_status)
    db.commit()
    for documento in documentos:
        caminho = Path(documento).resolve()
        if Path(UPLOAD_DIR).resolve() in caminho.parents and caminho.is_file():
            try:
                caminho.unlink()
            except OSError:
                logger.warning("conta_documento_delete_failed")
    _log(
        db, "Contas a pagar em lote", "contas_pagar", usuario_id=usuario.id, usuario_nome=usuario.nome,
        detalhes=f"Ação: {acao}; IDs: {sorted(c.id for c in elegiveis)}; ignorados por pagamento/conciliação: {len(protegidos)}",
    )
    mensagem = f"{len(elegiveis)} conta(s) atualizada(s)."
    if protegidos:
        mensagem += f" {len(protegidos)} não foram alteradas por já estarem pagas ou conciliadas."
    return RedirectResponse("/contas-pagar?flash=" + quote_plus(mensagem), status_code=303)


@router.post("/contas-pagar/{conta_id}/desconciliar")
async def desconciliar_conta(conta_id: int, confirmar_conciliacao: bool = Form(False), db: Session = Depends(get_db), usuario: Usuario = Depends(require_contas_pagar)):
    if usuario.perfil == PerfilUsuario.medico:
        raise HTTPException(403, "Perfil somente leitura.")
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id, ContaPagar.cliente_id.in_(_ids_clientes_do_usuario(db, usuario))).first()
    if not conta:
        raise HTTPException(404, "Conta indisponivel.")
    exigir_confirmacao(confirmar_conciliacao)
    desconciliar_pagamento(db, conta)
    db.commit()
    _log(db, "Conta a pagar desconciliada", "contas_pagar", usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=conta.cliente_id, detalhes=f"Conta #{conta.id}")
    return RedirectResponse(f"/contas-pagar?cliente_id={conta.cliente_id}", status_code=303)
