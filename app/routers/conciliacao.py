import json
import logging
import os
import uuid
from datetime import date as date_type
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.authorization import Permission, require_permission
from app.config import UPLOAD_DIR
from app.database import get_db
from app.services.recebimento_service import prever_recebimento
from app.utils import cliente_ativo as _ca, salvar_upload_temporario
from app.models import (
    Atendimento,
    AtendimentoCentroCustoRateio,
    CentroCusto,
    ClienteBPO,
    CondicaoPagamento,
    FormaPagamento,
    MovimentacaoBancaria,
    PerfilUsuario,
    PlanoConta,
    StatusConciliacao,
    StatusMovimentacaoBancaria,
    StatusTransferenciaCartao,
    StatusVendaCartao,
    TaxaAntecipacaoCliente,
    TaxaCartaoCliente,
    TransferenciaCartao,
    Usuario,
    VendaCartao,
)
from app.services.conciliacao_service import (
    buscar_sugestao,
    buscar_sugestao_venda,
    fechar_lote_dia,
    importar_lancamentos,
    importar_vendas_cartao,
    ler_arquivo_extrato,
)
from app.services.log_service import registrar as _log
from app.errors import public_import_error

router = APIRouter()
require_conciliacao = require_permission(Permission.CONCILIACAO)
logger = logging.getLogger(__name__)


def clientes_do_usuario(db: Session, usuario: Usuario):
    if usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor):
        return db.query(ClienteBPO).filter(ClienteBPO.ativo == True).all()
    return db.query(ClienteBPO).filter(
        ClienteBPO.funcionario_id == usuario.id,
        ClienteBPO.ativo == True,
    ).all()


def _carregar_vendas_a_conciliar(db: Session, cliente_id: int):
    """Vendas pendentes (sem atendimento vinculado)."""
    return (
        db.query(VendaCartao)
        .filter(
            VendaCartao.cliente_id == cliente_id,
            VendaCartao.status == StatusVendaCartao.pendente,
        )
        .order_by(VendaCartao.data_pagamento.asc(), VendaCartao.bandeira, VendaCartao.id)
        .all()
    )


def _carregar_vendas_conciliadas(db: Session, cliente_id: int):
    """Vendas já conciliadas com atendimento mas ainda não fechadas em lote."""
    return (
        db.query(VendaCartao)
        .filter(
            VendaCartao.cliente_id == cliente_id,
            VendaCartao.status == StatusVendaCartao.conciliado,
        )
        .order_by(VendaCartao.data_pagamento.asc(), VendaCartao.bandeira, VendaCartao.id)
        .all()
    )


def _carregar_atendimentos_pendentes(db: Session, cliente_id: int):
    return (
        db.query(Atendimento)
        .filter(
            Atendimento.cliente_id == cliente_id,
            Atendimento.status_conciliacao.in_([
                StatusConciliacao.pendente,
                StatusConciliacao.divergencia,
            ]),
            Atendimento.forma_pagamento == FormaPagamento.cartao_credito,
        )
        .order_by(Atendimento.data_prevista_recebimento.asc())
        .all()
    )


def _buscar_atendimentos(db: Session, cliente_id: int, venda: VendaCartao, termo: str | None):
    termo = (termo or "").strip()
    query = db.query(Atendimento).filter(
        Atendimento.cliente_id == cliente_id,
        Atendimento.status_conciliacao.in_([StatusConciliacao.pendente, StatusConciliacao.divergencia]),
        Atendimento.forma_pagamento == FormaPagamento.cartao_credito,
    )
    candidatos = query.order_by(Atendimento.data_prevista_recebimento.asc()).all()
    if termo:
        procurado = termo.casefold()
        candidatos = [
            item for item in candidatos
            if any(procurado in (campo or "").casefold() for campo in (
                item.nome_paciente, item.cpf_paciente, item.medico,
            ))
        ]
    return candidatos[:12]


def _montar_painel(db, cliente_id, vendas, atendimentos, busca_venda_id=None, busca_termo=None):
    itens = []
    prontas = 0
    verdes = 0
    revisar = 0
    for venda in vendas:
        sug = buscar_sugestao_venda(venda, atendimentos)
        if sug:
            if sug["status"] == "sugestao_pronta":
                prontas += 1
            elif sug["status"] == "sugestao_verde":
                verdes += 1
            else:
                revisar += 1
        busca_aberta = busca_venda_id == venda.id
        resultados_busca = _buscar_atendimentos(db, cliente_id, venda, busca_termo) if busca_aberta else []
        itens.append({
            "venda": venda,
            "sugestao": sug,
            "busca_aberta": busca_aberta,
            "busca_termo": busca_termo or "",
            "resultados_busca": resultados_busca,
        })
    return {
        "itens": itens,
        "totais": {
            "vendas": len(vendas),
            "atendimentos": len(atendimentos),
            "prontas": prontas + verdes,
            "verdes": verdes,
            "conciliar_todos": prontas + verdes,
            "revisar": revisar,
        },
    }


def _agrupar_conciliadas(vendas_conciliadas: list) -> list:
    grupos: dict = {}
    for v in vendas_conciliadas:
        chave = (v.data_pagamento, v.bandeira or "Outros")
        if chave not in grupos:
            grupos[chave] = {
                "data_pagamento": v.data_pagamento,
                "bandeira": v.bandeira or "Outros",
                "vendas": [],
                "total_bruto": Decimal("0"),
                "total_liquido": Decimal("0"),
                "qtd": 0,
            }
        g = grupos[chave]
        g["vendas"].append(v)
        g["total_bruto"]   += v.valor_bruto or Decimal("0")
        g["total_liquido"] += v.valor_liquido or v.valor_bruto or Decimal("0")
        g["qtd"] += 1
    return sorted(grupos.values(), key=lambda x: (x["data_pagamento"], x["bandeira"]))


def _carregar_lotes_recentes(db: Session, cliente_id: int):
    return (
        db.query(TransferenciaCartao)
        .filter(TransferenciaCartao.cliente_id == cliente_id)
        .order_by(TransferenciaCartao.data.desc(), TransferenciaCartao.bandeira)
        .limit(30)
        .all()
    )


def _ctx(db, usuario, cliente_id, busca_venda_id=None, busca_termo=None):
    clientes = clientes_do_usuario(db, usuario)
    vendas_pendentes    = _carregar_vendas_a_conciliar(db, cliente_id) if cliente_id else []
    vendas_conciliadas  = _carregar_vendas_conciliadas(db, cliente_id) if cliente_id else []
    atendimentos        = _carregar_atendimentos_pendentes(db, cliente_id) if cliente_id else []
    painel = _montar_painel(db, cliente_id, vendas_pendentes, atendimentos,
                            busca_venda_id, busca_termo) if cliente_id else None
    grupos_prontos = _agrupar_conciliadas(vendas_conciliadas)
    lotes = _carregar_lotes_recentes(db, cliente_id) if cliente_id else []
    return {
        "clientes": clientes,
        "cliente_selecionado": cliente_id,
        "painel": painel,
        "grupos_prontos": grupos_prontos,
        "lotes_recentes": lotes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rotas — Conciliação Cartão
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/conciliacao", response_class=HTMLResponse)
async def pagina_conciliacao_cartao(
    request: Request,
    cliente_id: Optional[int] = None,
    buscar_venda: Optional[int] = Query(default=None),
    termo: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    if usuario.perfil.value in ("secretaria", "medico"):
        return RedirectResponse(url="/", status_code=303)
    cliente_id = _ca(request, cliente_id)
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    if cliente_id and cliente_id not in ids_permitidos:
        cliente_id = None
    ctx = _ctx(db, usuario, cliente_id, buscar_venda, termo)
    return templates.TemplateResponse("conciliacao_cartao.html", {
        "request": request, "usuario": usuario, **ctx,
    })


@router.post("/conciliacao/importar", response_class=HTMLResponse)
async def importar_extrato_maquininha(
    request: Request,
    cliente_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao", status_code=303)

    flash_success = flash_error = None
    caminho = None
    try:
        caminho, nome_original, _ = await salvar_upload_temporario(
            arquivo,
            {".csv", ".xlsx", ".xls"},
        )
        df = ler_arquivo_extrato(caminho)
        total = importar_vendas_cartao(db, cliente_id, df, nome_original)
        flash_success = (
            f"{total} venda(s) importada(s) de '{nome_original}'. "
            "As correspondências encontradas estão disponíveis como sugestões."
        )
        _log(db, "Extrato de maquininha importado", "conciliacao_cartao",
             usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
             detalhes=f"{total} linha(s) de '{nome_original}' importada(s) para revisão",
             ip=request.client.host if request.client else None)
    except Exception:
        flash_error = public_import_error(logger, "importar_extrato_maquininha")
    finally:
        try:
            if caminho:
                os.remove(caminho)
        except OSError:
            pass

    ctx = _ctx(db, usuario, cliente_id)
    return templates.TemplateResponse("conciliacao_cartao.html", {
        "request": request, "usuario": usuario,
        "flash_success": flash_success, "flash_error": flash_error,
        **ctx,
    })


@router.post("/conciliacao/conciliar-todos-prontos")
async def conciliar_todos_prontos(
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao", status_code=303)

    conciliados = _conciliar_vendas_prontas(db, cliente_id, usuario)
    if conciliados:
        _log(db, f"Conciliação cartão em lote: {conciliados} venda(s)", "conciliacao_cartao",
             usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id)
    return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)


def _aplicar_conciliacao(db: Session, venda: VendaCartao, at: Atendimento):
    at.status_conciliacao = StatusConciliacao.conciliado
    at.data_credito = venda.data_pagamento
    at.valor_liquido = venda.valor_liquido or venda.valor_bruto
    if venda.taxa_percentual:
        at.taxa_cartao = venda.taxa_percentual
    if venda.ultimos_digitos:
        at.ultimos_digitos_cartao = venda.ultimos_digitos
    venda.status = StatusVendaCartao.conciliado
    venda.atendimento_id = at.id
    db.commit()


def _conciliar_vendas_prontas(db: Session, cliente_id: int, usuario: Usuario | None = None) -> int:
    vendas = _carregar_vendas_a_conciliar(db, cliente_id)
    atendimentos = _carregar_atendimentos_pendentes(db, cliente_id)
    conciliados = 0
    for venda in vendas:
        sug = buscar_sugestao_venda(venda, atendimentos)
        if sug and sug["status"] in ("sugestao_pronta", "sugestao_verde"):
            at = sug["atendimento"]
            _aplicar_conciliacao(db, venda, at)
            if usuario:
                _log(
                    db,
                    "Conciliação de cartão em lote",
                    "conciliacao",
                    usuario_id=usuario.id,
                    usuario_nome=usuario.nome,
                    cliente_id=cliente_id,
                    detalhes=f"Venda #{venda.id} -> Atendimento #{at.id}",
                )
            atendimentos = [a for a in atendimentos if a.id != at.id]
            conciliados += 1
    return conciliados


def _conciliar_pix_ted_prontos(db: Session, cliente_id: int, usuario: Usuario | None = None) -> int:
    movs = (
        db.query(MovimentacaoBancaria)
        .filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            MovimentacaoBancaria.tipo == "pix_ted",
            MovimentacaoBancaria.sentido == "recebimento",
            MovimentacaoBancaria.transferencia_cartao_id.is_(None),
            MovimentacaoBancaria.status.in_([
                StatusMovimentacaoBancaria.importada,
                StatusMovimentacaoBancaria.divergencia,
                StatusMovimentacaoBancaria.revisada,
            ]),
        )
        .order_by(MovimentacaoBancaria.data_movimento.asc(), MovimentacaoBancaria.id.asc())
        .all()
    )
    lancs = (
        db.query(Atendimento)
        .filter(
            Atendimento.cliente_id == cliente_id,
            Atendimento.status_conciliacao.in_([
                StatusConciliacao.pendente,
                StatusConciliacao.divergencia,
            ]),
            Atendimento.forma_pagamento.in_([FormaPagamento.pix, FormaPagamento.transferencia]),
        )
        .order_by(Atendimento.data_prevista_recebimento.asc())
        .all()
    )

    conciliados = 0
    for mov in movs:
        sugestao = buscar_sugestao(mov, lancs)
        if sugestao and sugestao["status"] == "sugestao_pronta":
            at = sugestao["atendimento"]
            at.status_conciliacao = StatusConciliacao.conciliado
            at.data_credito = mov.data_movimento
            at.valor_liquido = mov.valor
            mov.status = StatusMovimentacaoBancaria.conciliada
            mov.conciliada_com_atendimento_id = at.id
            db.commit()
            if usuario:
                _log(
                    db,
                    "Conciliação automática PIX/TED",
                    "conciliacao",
                    usuario_id=None,
                    usuario_nome="Automatico",
                    cliente_id=cliente_id,
                    detalhes=f"Movimentação #{mov.id} -> Atendimento #{at.id}",
                )
            lancs = [l for l in lancs if l.id != at.id]
            conciliados += 1
    return conciliados


@router.post("/conciliacao/venda/{venda_id}/conciliar")
async def conciliar_venda(
    venda_id: int,
    cliente_id: int = Form(...),
    atendimento_id: int = Form(...),
    origem: str = Form("sugestao"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]

    venda = db.query(VendaCartao).filter(VendaCartao.id == venda_id).first()
    at    = db.query(Atendimento).filter(Atendimento.id == atendimento_id).first()

    if (venda and at
            and venda.cliente_id in ids_ok
            and at.cliente_id == venda.cliente_id == cliente_id
            and venda.status == StatusVendaCartao.pendente):
        _aplicar_conciliacao(db, venda, at)
        _log(db, "Venda conciliada com atendimento", "conciliacao_cartao",
             usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
             detalhes=f"Venda #{venda_id} → Atendimento #{atendimento_id}")

    return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/venda/{venda_id}/editar")
async def editar_venda(
    venda_id: int,
    cliente_id: int = Form(...),
    atendimento_id: Optional[int] = Form(default=None),
    valor_bruto: str = Form(...),
    taxa_percentual: str = Form(""),
    valor_liquido: str = Form(...),
    at_valor_servico: str = Form(...),
    at_taxa_cartao: str = Form(""),
    at_valor_liquido: str = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]

    venda = db.query(VendaCartao).filter(VendaCartao.id == venda_id).first()
    if not venda or venda.cliente_id not in ids_ok:
        return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)

    try:
        venda.valor_bruto    = Decimal(valor_bruto.replace(",", "."))
        venda.valor_liquido  = Decimal(valor_liquido.replace(",", "."))
        if taxa_percentual.strip():
            venda.taxa_percentual = Decimal(taxa_percentual.replace(",", "."))
    except Exception:
        pass

    # Atendimento: usa o vinculado à venda, ou o passado como parâmetro (sugestão pendente)
    at_id = venda.atendimento_id or atendimento_id
    if at_id:
        at = db.query(Atendimento).filter(
            Atendimento.id == at_id,
            Atendimento.cliente_id == cliente_id,
        ).first()
        if at:
            try:
                at.valor_servico = Decimal(at_valor_servico.replace(",", "."))
                at.valor_liquido = Decimal(at_valor_liquido.replace(",", "."))
                if at_taxa_cartao.strip():
                    at.taxa_cartao = Decimal(at_taxa_cartao.replace(",", "."))
            except Exception:
                pass

    db.commit()
    _log(db, "Venda e lançamento editados", "conciliacao_cartao",
         usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
         detalhes=f"Venda #{venda_id} editada manualmente")

    return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/lote/{lote_id}/reabrir")
async def reabrir_lote(
    lote_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]

    lote = db.query(TransferenciaCartao).filter(TransferenciaCartao.id == lote_id).first()
    if not lote or lote.cliente_id not in ids_ok or lote.cliente_id != cliente_id:
        return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)

    # Se estiver conciliado com o banco, desfaz o vínculo bancário primeiro
    mov = db.query(MovimentacaoBancaria).filter(
        MovimentacaoBancaria.transferencia_cartao_id == lote_id
    ).first()
    if mov:
        mov.transferencia_cartao_id = None
        mov.status = StatusMovimentacaoBancaria.importada

    # Reverte vendas para conciliado (voltam para grupos_prontos)
    vendas = db.query(VendaCartao).filter(VendaCartao.lote_id == lote_id).all()
    for v in vendas:
        v.status = StatusVendaCartao.conciliado
        v.lote_id = None

    db.delete(lote)
    db.commit()
    return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/venda/{venda_id}/desvincular")
async def desvincular_venda(
    venda_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]

    venda = db.query(VendaCartao).filter(VendaCartao.id == venda_id).first()
    if venda and venda.cliente_id in ids_ok and venda.status == StatusVendaCartao.conciliado:
        at = db.query(Atendimento).filter(Atendimento.id == venda.atendimento_id).first()
        if at:
            at.status_conciliacao = StatusConciliacao.pendente
            at.data_credito = None
        venda.status = StatusVendaCartao.pendente
        venda.atendimento_id = None
        db.commit()

    return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/venda/{venda_id}/criar-e-conciliar")
async def criar_e_conciliar_venda(
    venda_id: int,
    cliente_id: int = Form(...),
    data_atendimento: str = Form(...),
    nome_paciente: str = Form(""),
    cpf_paciente: str = Form(""),
    medico: str = Form(""),
    especialidade: str = Form(""),
    tipo_servico: str = Form(""),
    descricao_servico: str = Form(""),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]

    venda = db.query(VendaCartao).filter(VendaCartao.id == venda_id).first()
    if not venda or venda.cliente_id not in ids_ok or venda.cliente_id != cliente_id:
        return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)

    try:
        data_atend = date_type.fromisoformat(data_atendimento)
    except ValueError:
        data_atend = date_type.today()

    at = Atendimento(
        cliente_id=cliente_id,
        data_atendimento=data_atend,
        nome_paciente=nome_paciente or None,
        cpf_paciente=cpf_paciente or None,
        medico=medico or None,
        especialidade=especialidade or None,
        tipo_servico=tipo_servico or None,
        descricao_servico=descricao_servico or None,
        valor_servico=venda.valor_bruto,
        condicao_pagamento=CondicaoPagamento.avista,
        forma_pagamento=FormaPagamento.cartao_credito,
        ultimos_digitos_cartao=venda.ultimos_digitos,
        bandeira_cartao=venda.bandeira,
        taxa_cartao=venda.taxa_percentual,
        valor_liquido=venda.valor_liquido,
        data_prevista_recebimento=venda.data_pagamento,
        data_credito=venda.data_pagamento,
        status_conciliacao=StatusConciliacao.conciliado,
        observacao=observacao or None,
        lancado_por_id=usuario.id,
    )
    db.add(at)
    db.flush()
    venda.status = StatusVendaCartao.conciliado
    venda.atendimento_id = at.id
    db.commit()
    _log(db, "Atendimento criado e venda conciliada", "conciliacao_cartao",
         usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
         detalhes=f"Venda #{venda_id} → novo Atendimento #{at.id}")

    return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/venda/{venda_id}/cancelar")
async def cancelar_venda(
    venda_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]
    venda = db.query(VendaCartao).filter(VendaCartao.id == venda_id).first()
    if venda and venda.cliente_id in ids_ok and venda.status == StatusVendaCartao.pendente:
        venda.status = StatusVendaCartao.cancelado
        db.commit()
    return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/fechar-lote")
async def fechar_lote(
    cliente_id: int = Form(...),
    data_pagamento: str = Form(...),
    bandeira: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao", status_code=303)

    try:
        data = date_type.fromisoformat(data_pagamento)
        lote = fechar_lote_dia(db, cliente_id, data, bandeira or None)
        _log(db, "Lote de cartão fechado", "conciliacao_cartao",
             usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
             detalhes=f"Lote #{lote.id} — {lote.bandeira} {lote.data.strftime('%d/%m/%Y')} "
                      f"R$ {lote.valor_liquido:.2f} ({lote.qtd_transacoes} transações)")
        # Redireciona para Conciliação Banco para o lote aparecer como "Lançamento do sistema"
        return RedirectResponse(
            url=f"/conciliacao/banco?cliente_id={cliente_id}&lote_fechado={lote.id}",
            status_code=303,
        )
    except Exception:
        logger.exception("fechar_lote_failed")

    return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)


async def _reabrir_lote_duplicado_removido(
    lote_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]
    lote = db.query(TransferenciaCartao).filter(TransferenciaCartao.id == lote_id).first()
    if lote and lote.cliente_id in ids_ok:
        mov = db.query(MovimentacaoBancaria).filter(
            MovimentacaoBancaria.transferencia_cartao_id == lote.id
        ).first()
        if mov:
            mov.transferencia_cartao_id = None
            mov.status = StatusMovimentacaoBancaria.importada
        db.query(VendaCartao).filter(VendaCartao.lote_id == lote.id).update(
            {"status": StatusVendaCartao.conciliado, "lote_id": None}
        )
        db.delete(lote)
        db.commit()
    return RedirectResponse(url=f"/conciliacao?cliente_id={cliente_id}", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# Lançamentos (atendimentos pendentes)
# ─────────────────────────────────────────────────────────────────────────────

def _carregar_lancamentos(db: Session, cliente_id: int):
    return (
        db.query(Atendimento)
        .filter(
            Atendimento.cliente_id == cliente_id,
            Atendimento.status_conciliacao.in_([
                StatusConciliacao.pendente,
                StatusConciliacao.divergencia,
            ]),
        )
        .order_by(Atendimento.data_prevista_recebimento.asc())
        .all()
    )


def _decimal_form(valor: str) -> Decimal | None:
    try:
        return Decimal(str(valor).strip().replace(",", ".")) if str(valor).strip() else None
    except InvalidOperation:
        return None


def _calcular_intervalos_lancamento(forma_pagamento: str, parcela_total: int, recorrencia: str | None):
    if forma_pagamento == FormaPagamento.cartao_credito.value:
        n = max(int(parcela_total or 1), 1)
        return [30 * i for i in range(1, n + 1)]
    if recorrencia:
        intervalos = [int(x.strip()) for x in recorrencia.split("/") if x.strip().isdigit()]
        if intervalos:
            return sorted(intervalos)
    return [0]


def _taxa_cartao_cliente(db: Session, cliente_id: int, bandeira: str | None) -> Decimal | None:
    if not bandeira:
        return None
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if cliente and cliente.antecipa:
        ant = db.query(TaxaAntecipacaoCliente).filter(
            TaxaAntecipacaoCliente.cliente_id == cliente_id,
            TaxaAntecipacaoCliente.bandeira == bandeira,
            TaxaAntecipacaoCliente.selecionada == True,
            TaxaAntecipacaoCliente.ativo == True,
        ).first()
        if ant:
            return Decimal(str(ant.taxa_percentual))
    taxa = db.query(TaxaCartaoCliente).filter(
        TaxaCartaoCliente.cliente_id == cliente_id,
        TaxaCartaoCliente.bandeira == bandeira,
        TaxaCartaoCliente.ativo == True,
    ).first()
    return Decimal(str(taxa.taxa_percentual)) if taxa else None


def _rateios_lancamento_manual(raw: str, centros: dict[int, CentroCusto]) -> list[dict]:
    try:
        payload = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(payload, list):
        return []
    rateios = []
    usados: set[int] = set()
    soma = Decimal("0")
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            centro_id = int(item.get("centro_custo_id") or 0)
        except (TypeError, ValueError):
            continue
        percentual = _decimal_form(str(item.get("percentual") or ""))
        centro = centros.get(centro_id)
        if not centro or percentual is None or percentual <= 0 or percentual > 100 or centro_id in usados:
            continue
        usados.add(centro_id)
        soma += percentual
        rateios.append({"centro": centro, "percentual": percentual})
    return rateios if rateios and soma == Decimal("100") else []


@router.get("/conciliacao/lancamentos", response_class=HTMLResponse)
async def pagina_lancamentos(
    request: Request,
    cliente_id: Optional[int] = None,
    flash: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    cliente_id = _ca(request, cliente_id)
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    cliente_valido = cliente_id if (cliente_id and cliente_id in ids_permitidos) else None
    lancamentos = _carregar_lancamentos(db, cliente_valido) if cliente_valido else []
    centros_custo = db.query(CentroCusto).filter(
        CentroCusto.cliente_id == cliente_valido,
        CentroCusto.ativo == True,
    ).order_by(CentroCusto.nome).all() if cliente_valido else []
    planos_conta = db.query(PlanoConta).filter(
        PlanoConta.tipo == "receita",
        PlanoConta.ativo == True,
        or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == cliente_valido),
    ).order_by(PlanoConta.codigo.asc(), PlanoConta.nome.asc()).all() if cliente_valido else []
    return templates.TemplateResponse("conciliacao_lancamentos.html", {
        "request": request, "usuario": usuario,
        "clientes": clientes, "cliente_selecionado": cliente_valido,
        "lancamentos": lancamentos,
        "centros_custo": centros_custo,
        "planos_conta": planos_conta,
        "hoje": date_type.today().isoformat(),
        "flash_error": flash,
    })


@router.post("/conciliacao/lancamentos/importar", response_class=HTMLResponse)
async def importar_lancamentos_conciliacao(
    request: Request,
    cliente_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao/lancamentos", status_code=303)

    flash_success = flash_error = None
    caminho = None
    try:
        caminho, nome_original, _ = await salvar_upload_temporario(
            arquivo,
            {".csv", ".xlsx", ".xls"},
        )
        df = ler_arquivo_extrato(caminho)
        total = importar_lancamentos(db, cliente_id, df)
        flash_success = (
            f"{total} lancamento(s) importado(s) de '{nome_original}'. "
            "As correspondências encontradas estão disponíveis como sugestões."
        )
        _log(db, "Lançamentos importados", "lancamentos",
             usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
             detalhes=f"{total} linha(s) de '{nome_original}'",
             ip=request.client.host if request.client else None)
    except Exception:
        flash_error = public_import_error(logger, "importar_lancamentos_conciliacao")
    finally:
        try:
            if caminho:
                os.remove(caminho)
        except OSError:
            pass

    lancamentos = _carregar_lancamentos(db, cliente_id)
    centros_custo = db.query(CentroCusto).filter(
        CentroCusto.cliente_id == cliente_id,
        CentroCusto.ativo == True,
    ).order_by(CentroCusto.nome).all()
    planos_conta = db.query(PlanoConta).filter(
        PlanoConta.tipo == "receita",
        PlanoConta.ativo == True,
        or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == cliente_id),
    ).order_by(PlanoConta.codigo.asc(), PlanoConta.nome.asc()).all()
    return templates.TemplateResponse("conciliacao_lancamentos.html", {
        "request": request, "usuario": usuario,
        "clientes": clientes_do_usuario(db, usuario),
        "cliente_selecionado": cliente_id,
        "lancamentos": lancamentos,
        "centros_custo": centros_custo,
        "planos_conta": planos_conta,
        "flash_success": flash_success,
        "flash_error": flash_error,
        "hoje": date_type.today().isoformat(),
    })


@router.post("/conciliacao/lancamentos/manual")
async def criar_lancamento_manual_conciliacao(
    request: Request,
    cliente_id: int = Form(...),
    data_atendimento: date_type = Form(...),
    nome_paciente: str = Form(""),
    cpf_paciente: str = Form(""),
    centro_custo_id: str = Form(""),
    rateios_json: str = Form("[]"),
    especialidade: str = Form(""),
    descricao_servico: str = Form(""),
    plano_conta_id: Optional[int] = Form(None),
    valor_servico: str = Form(...),
    forma_pagamento: str = Form(""),
    condicao_pagamento: str = Form("avista"),
    parcela_total: int = Form(1),
    recorrencia: str = Form(""),
    ultimos_digitos_cartao: str = Form(""),
    bandeira_cartao: str = Form(""),
    percentual_medico: str = Form(""),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    if cliente_id not in ids_permitidos:
        return RedirectResponse(url="/conciliacao/lancamentos", status_code=303)

    valor = _decimal_form(valor_servico)
    if not valor or valor <= 0:
        return RedirectResponse(url=f"/conciliacao/lancamentos?cliente_id={cliente_id}", status_code=303)

    cliente = next((c for c in clientes if c.id == cliente_id), None)
    forma = forma_pagamento.strip() or None
    condicao = condicao_pagamento.strip() or "avista"
    is_parcelado = condicao == CondicaoPagamento.parcelado.value
    intervalos = _calcular_intervalos_lancamento(forma or "", parcela_total, recorrencia) if is_parcelado else [0]


    qtd_parcelas = len(intervalos)
    valor_parcela = (valor / Decimal(qtd_parcelas)).quantize(Decimal("0.01"))
    valor_ultima = valor - valor_parcela * (qtd_parcelas - 1)
    bandeira = bandeira_cartao.strip() or None
    taxa_pct = _taxa_cartao_cliente(db, cliente_id, bandeira) if forma == FormaPagamento.cartao_credito.value else None
    pct_medico = _decimal_form(percentual_medico)
    centros_validos = {
        centro.id: centro for centro in db.query(CentroCusto).filter(
            CentroCusto.cliente_id == cliente_id,
            CentroCusto.ativo == True,
        ).all()
    }
    rateios = _rateios_lancamento_manual(rateios_json, centros_validos)
    if rateios_json not in ("", "[]") and not rateios:
        return RedirectResponse(
            url=f"/conciliacao/lancamentos?cliente_id={cliente_id}&flash=Rateio+inv%C3%A1lido%3A+use+centros+diferentes+e+feche+100%25",
            status_code=303,
        )
    cc_id = rateios[0]["centro"].id if rateios else (
        int(centro_custo_id) if centro_custo_id.strip().isdigit() else None
    )
    cc = centros_validos.get(cc_id) if cc_id else None
    especialidade_valor = especialidade.strip() or next(
        (rateio["centro"].especialidade for rateio in rateios
         if rateio["centro"].is_medico and rateio["centro"].especialidade),
        None,
    )
    plano = db.query(PlanoConta).filter(
        PlanoConta.id == plano_conta_id,
        PlanoConta.tipo == "receita",
        PlanoConta.ativo == True,
        or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == cliente_id),
    ).first() if plano_conta_id else None

    for parcela_numero, dias in enumerate(intervalos, 1):
        valor_item = valor_ultima if parcela_numero == qtd_parcelas else valor_parcela
        valor_liquido = valor_item
        if taxa_pct is not None:
            valor_liquido = (valor_item * (Decimal("1") - taxa_pct / Decimal("100"))).quantize(Decimal("0.01"))

        valor_medico = None
        if pct_medico:
            valor_medico = (valor_item * pct_medico / Decimal("100")).quantize(Decimal("0.01"))

        valor_clinica = valor_liquido - valor_medico if valor_medico is not None else valor_liquido

        atendimento = Atendimento(
            cliente_id=cliente_id,
            data_atendimento=data_atendimento,
            nome_paciente=nome_paciente.strip() or None,
            cpf_paciente=cpf_paciente.strip() or None,
            centro_custo_id=cc_id,
            medico=cc.nome if cc else None,
            especialidade=especialidade_valor,
            descricao_servico=descricao_servico.strip() or None,
            plano_conta_id=plano.id if plano else None,
            valor_servico=valor_item,
            condicao_pagamento=condicao,
            parcela_numero=parcela_numero,
            parcela_total=qtd_parcelas,
            data_prevista_recebimento=prever_recebimento(
                data_atendimento, dias, forma, bool(cliente and cliente.antecipa),
            ),
            forma_pagamento=forma,
            ultimos_digitos_cartao=ultimos_digitos_cartao.strip() or None,
            bandeira_cartao=bandeira,
            taxa_cartao=taxa_pct,
            valor_liquido=valor_liquido,
            valor_clinica=valor_clinica,
            status_conciliacao=StatusConciliacao.pendente,
            percentual_medico=pct_medico,
            valor_medico=valor_medico,
            observacao=observacao.strip() or None,
            lancado_por_id=usuario.id,
        )
        db.add(atendimento)
        db.flush()
        valores_rateio = []
        for rateio in rateios:
            valores_rateio.append((
                valor_item * rateio["percentual"] / Decimal("100")
            ).quantize(Decimal("0.01")))
        if valores_rateio:
            valores_rateio[-1] += valor_item - sum(valores_rateio, Decimal("0"))
        for rateio, valor_rateio in zip(rateios, valores_rateio):
            db.add(AtendimentoCentroCustoRateio(
                atendimento_id=atendimento.id,
                centro_custo_id=rateio["centro"].id,
                percentual=rateio["percentual"],
                valor=valor_rateio,
            ))

    db.commit()
    _log(db, "Lançamento manual criado", "lancamentos",
         usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
         cliente_nome=cliente.nome if cliente else None,
         detalhes=f"{qtd_parcelas} lançamento(s) em {data_atendimento.strftime('%d/%m/%Y')}",
         ip=request.client.host if request.client else None)

    return RedirectResponse(
        url=f"/conciliacao/lancamentos?cliente_id={cliente_id}",
        status_code=303,
    )
