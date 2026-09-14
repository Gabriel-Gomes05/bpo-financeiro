import json
import logging
import os
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.authorization import Permission, require_permission
from app.config import UPLOAD_DIR
from app.database import get_db
from app.utils import cliente_ativo as _ca, salvar_upload_temporario
from app.models import (
    Atendimento,
    AtendimentoCentroCustoRateio,
    CentroCusto,
    ClienteBPO,
    CondicaoPagamento,
    ContaBancaria,
    ContaPagar,
    ContaPagarCentroCustoRateio,
    ExtratoLinhaBancaria,
    FormaPagamento,
    MovimentacaoBancaria,
    PagamentoParcialContaPagar,
    PlanoConta,
    PerfilUsuario,
    RegraNegocioBancaria,
    StatusConciliacao,
    StatusContaPagar,
    StatusExtratoLinha,
    StatusMovimentacaoBancaria,
    StatusTransferenciaCartao,
    TipoContaBancaria,
    TransferenciaCartao,
    Usuario,
)
from app.services.conciliacao_service import (
    buscar_sugestao,
    conciliar_pix_ted,
    importar_extrato_conta_corrente,
    importar_movimentacoes_bancarias,
    importar_lancamentos,
    ler_arquivo_extrato,
    limpar_divergencias_anteriores,
    limpar_movimentacoes_anteriores,
    parse_ofx,
)
from app.services.log_service import registrar as _log
from app.errors import public_import_error

from app.services.contas_bancarias_service import conta_do_cliente, registrar_transferencia, saldo_previsto


async def get_banco_db(request: Request, db: Session = Depends(get_db)):
    cliente = request.query_params.get("cliente_id")
    selected = request.query_params.get("conta_bancaria_id")
    if request.method == "GET":
        cliente = request.cookies.get("cliente_ativo") or cliente
    if request.method == "POST":
        form = await request.form()
        cliente = form.get("cliente_id", cliente)
        selected = form.get("conta_bancaria_id", selected)
    cliente = str(cliente or request.cookies.get("cliente_ativo", ""))
    if selected is None:
        selected = request.cookies.get("banco_conta_" + cliente, "")
    if selected and str(selected).isdigit() and cliente.isdigit():
        conta_do_cliente(db, int(cliente), int(selected))
        db.info["banco_conta_id"] = int(selected)
    return db


def _filtrar_conta(db, registros):
    conta_id = db.info.get("banco_conta_id")
    return [m for m in registros if not conta_id or m.conta_bancaria_id == conta_id]


router = APIRouter()
require_conciliacao = require_permission(Permission.CONCILIACAO)
logger = logging.getLogger(__name__)


def _plano_valido(db: Session, cliente_id: int, plano_id: int, tipo: str) -> PlanoConta | None:
    return db.query(PlanoConta).filter(
        PlanoConta.id == plano_id, PlanoConta.tipo == tipo, PlanoConta.ativo.is_(True),
        or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == cliente_id),
    ).first()


def _aplicar_regras_bancarias(db: Session, cliente_id: int) -> int:
    regras = db.query(RegraNegocioBancaria).filter(
        RegraNegocioBancaria.cliente_id == cliente_id,
        RegraNegocioBancaria.ativo.is_(True),
    ).all()
    movimentos = db.query(MovimentacaoBancaria).filter(
        MovimentacaoBancaria.cliente_id == cliente_id,
        MovimentacaoBancaria.status != StatusMovimentacaoBancaria.conciliada,
        MovimentacaoBancaria.conta_bancaria_id.isnot(None),
    ).all()
    aplicadas = 0
    for movimento in movimentos:
        descricao = (movimento.descricao or "").casefold()
        for regra in regras:
            if regra.conta_origem_id and movimento.conta_bancaria_id != regra.conta_origem_id:
                continue
            if (regra.padrao_descricao or "").strip().casefold() not in descricao:
                continue
            if regra.acao == "conciliar_receita":
                if movimento.sentido != "recebimento" or not regra.plano_conta_id:
                    continue
                candidatos = db.query(Atendimento).filter(
                    Atendimento.cliente_id == cliente_id,
                    Atendimento.plano_conta_id == regra.plano_conta_id,
                    Atendimento.status_conciliacao == StatusConciliacao.pendente,
                    Atendimento.valor_servico == movimento.valor,
                ).all()
                if len(candidatos) != 1:
                    continue
                atendimento = candidatos[0]
                atendimento.status_conciliacao = StatusConciliacao.conciliado
                atendimento.data_credito = movimento.data_movimento
                movimento.conciliada_com_atendimento_id = atendimento.id
                movimento.status = StatusMovimentacaoBancaria.conciliada
                aplicadas += 1
                break
            if regra.acao == "conciliar_despesa":
                if movimento.sentido != "pagamento" or not regra.plano_conta_id:
                    continue
                candidatos = db.query(ContaPagar).filter(
                    ContaPagar.cliente_id == cliente_id,
                    ContaPagar.plano_conta_id == regra.plano_conta_id,
                    ContaPagar.status.in_([StatusContaPagar.agendado, StatusContaPagar.pago_nao_conciliado]),
                    ContaPagar.valor == movimento.valor,
                ).all()
                if len(candidatos) != 1:
                    continue
                conta = candidatos[0]
                conta.status = StatusContaPagar.pago
                conta.data_pagamento = movimento.data_movimento
                movimento.conta_pagar_id = conta.id
                movimento.status = StatusMovimentacaoBancaria.conciliada
                db.add(PagamentoParcialContaPagar(
                    conta_pagar_id=conta.id, movimentacao_id=movimento.id,
                    valor=movimento.valor, data_pagamento=movimento.data_movimento,
                    observacao=f"Conciliação automática: {regra.nome}",
                ))
                aplicadas += 1
                break
            if regra.acao != "transferencia" or not regra.conta_destino_id or movimento.sentido != "pagamento":
                continue
            identificador = f"regra-bancaria:{regra.id}:{movimento.id}"
            existente = db.query(MovimentacaoBancaria.id).filter(
                MovimentacaoBancaria.identificador_externo == identificador,
            ).first()
            if existente:
                break
            movimento.tipo = "transf_interna"
            movimento.status = StatusMovimentacaoBancaria.conciliada
            db.add(MovimentacaoBancaria(
                cliente_id=cliente_id, conta_bancaria_id=regra.conta_destino_id,
                identificador_externo=identificador, origem_manual=False,
                tipo="transf_interna", sentido="recebimento",
                data_movimento=movimento.data_movimento, valor=movimento.valor,
                descricao=f"Transferência automática: {regra.nome}",
                origem_arquivo="Regra de negócio bancária",
                status=StatusMovimentacaoBancaria.conciliada,
            ))
            aplicadas += 1
            break
    if aplicadas:
        db.flush()
    return aplicadas


@router.post("/conciliacao/banco/regras")
async def criar_regra_bancaria(
    cliente_id: int = Form(...), nome: str = Form(...), padrao_descricao: str = Form(...),
    acao: str = Form("transferencia"), conta_origem_id: Optional[int] = Form(None),
    conta_destino_id: Optional[int] = Form(None), plano_conta_id: Optional[int] = Form(None),
    db: Session = Depends(get_banco_db), usuario: Usuario = Depends(require_conciliacao),
):
    if cliente_id not in [c.id for c in clientes_do_usuario(db, usuario)]:
        raise HTTPException(404, "Cliente indisponível.")
    if acao not in {"transferencia", "conciliar_receita", "conciliar_despesa"} or not nome.strip() or not padrao_descricao.strip():
        raise HTTPException(400, "Informe o tipo, nome e texto da regra.")
    if conta_origem_id:
        conta_do_cliente(db, cliente_id, conta_origem_id)
    plano = None
    if acao == "transferencia":
        if not conta_origem_id or not conta_destino_id or conta_origem_id == conta_destino_id:
            raise HTTPException(400, "Informe contas de origem e destino diferentes.")
        conta_do_cliente(db, cliente_id, conta_destino_id)
    else:
        tipo_plano = "receita" if acao == "conciliar_receita" else "despesa"
        plano = _plano_valido(db, cliente_id, plano_conta_id or 0, tipo_plano)
        if not plano:
            raise HTTPException(400, "Selecione um plano de contas compatível.")
    db.add(RegraNegocioBancaria(
        cliente_id=cliente_id, nome=nome.strip(), padrao_descricao=padrao_descricao.strip(),
        acao=acao, conta_origem_id=conta_origem_id,
        conta_destino_id=conta_destino_id if acao == "transferencia" else None,
        plano_conta_id=plano.id if plano else None, ativo=True,
    ))
    db.flush()
    _aplicar_regras_bancarias(db, cliente_id)
    db.commit()
    return RedirectResponse(f"/conciliacao/banco?cliente_id={cliente_id}#regras-bancarias", 303)


@router.post("/conciliacao/banco/regras/{regra_id}/excluir")
async def excluir_regra_bancaria(
    regra_id: int, cliente_id: int = Form(...), db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    if cliente_id not in [c.id for c in clientes_do_usuario(db, usuario)]:
        raise HTTPException(404)
    regra = db.query(RegraNegocioBancaria).filter(
        RegraNegocioBancaria.id == regra_id, RegraNegocioBancaria.cliente_id == cliente_id,
    ).first()
    if regra:
        regra.ativo = False
        db.commit()
    return RedirectResponse(f"/conciliacao/banco?cliente_id={cliente_id}#regras-bancarias", 303)


@router.post("/conciliacao/banco/contas")
async def cadastrar_conta_bancaria(
    cliente_id: int = Form(...), nome: str = Form(...), banco: str = Form(...),
    agencia: str = Form(""), numero: str = Form(...), saldo: Decimal = Form(...),
    data_saldo: date = Form(...), db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    if cliente_id not in [c.id for c in clientes_do_usuario(db, usuario)]:
        raise HTTPException(404, "Cliente indisponível.")
    if not nome.strip() or len(nome.strip()) > 100 or not banco.strip() or not numero.strip():
        raise HTTPException(400, "Informe nome, banco e número da conta.")
    if not saldo.is_finite() or abs(saldo) > Decimal("999999999999.99") or saldo != saldo.quantize(Decimal("0.01")):
        raise HTTPException(400, "Saldo inválido.")
    existentes = db.query(ContaBancaria).filter(ContaBancaria.cliente_id == cliente_id).all()
    if any((c.banco or "").strip().casefold() == banco.strip().casefold() and (c.agencia or "").strip() == agencia.strip() and (c.conta or "").strip() == numero.strip() for c in existentes):
        raise HTTPException(409, "Esta conta já está cadastrada para o cliente.")
    conta = ContaBancaria(cliente_id=cliente_id, nome=nome.strip(), banco=banco.strip(), agencia=agencia.strip() or None,
        conta=numero.strip(), tipo=TipoContaBancaria.bancaria, ativo=True, saldo_atual=saldo,
        saldo_data_referencia=datetime.combine(data_saldo, datetime.min.time()), saldo_atualizado_em=datetime.now())
    db.add(conta)
    db.commit()
    _log(db, "Conta bancária cadastrada", "conciliacao", usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id, detalhes=f"Conta #{conta.id}")
    response = RedirectResponse(f"/conciliacao/banco?cliente_id={cliente_id}&conta_bancaria_id={conta.id}#movimentacoes", status_code=303)
    response.set_cookie(f"banco_conta_{cliente_id}", str(conta.id), samesite="lax")
    return response


@router.post("/conciliacao/banco/transferencias")
async def transferir_entre_contas(
    cliente_id: int = Form(...), origem_id: int = Form(...), destino_id: int = Form(...),
    valor: Decimal = Form(...), data_transferencia: date = Form(...), descricao: str = Form(""), token: str = Form(...),
    db: Session = Depends(get_banco_db), usuario: Usuario = Depends(require_conciliacao),
):
    if cliente_id not in [c.id for c in clientes_do_usuario(db, usuario)]:
        raise HTTPException(404, "Cliente indisponível.")
    grupo = registrar_transferencia(db, cliente_id, origem_id, destino_id, valor, data_transferencia, descricao, token)
    db.commit()
    _log(db, "Transferência interna registrada", "conciliacao", usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id, detalhes=f"Transferência {grupo}; origem #{origem_id}; destino #{destino_id}; valor {valor}")
    return RedirectResponse(f"/conciliacao/banco?cliente_id={cliente_id}#movimentacoes", status_code=303)


def _chave_centro_custo(cc: CentroCusto) -> str:
    return (cc.codigo or "").strip() or f"centro_custo:{cc.id}"


def _montar_rateios_banco(db: Session, cliente_id: int, valor_total: Decimal, rateios_json: str) -> list[dict]:
    try:
        payload = json.loads(rateios_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list) or not payload:
        return []
    centros = db.query(CentroCusto).filter(
        CentroCusto.cliente_id == cliente_id,
        CentroCusto.ativo == True,
    ).all()
    centros_por_id = {cc.id: cc for cc in centros}
    rateios, usados, soma = [], set(), Decimal("0")
    for item in payload:
        try:
            centro_id = int(item.get("centro_custo_id"))
            percentual = Decimal(str(item.get("percentual") or "").replace(",", "."))
        except (AttributeError, TypeError, ValueError, InvalidOperation):
            return []
        centro = centros_por_id.get(centro_id)
        if not centro or centro_id in usados or percentual <= 0 or percentual > 100:
            return []
        usados.add(centro_id)
        soma += percentual
        rateios.append({"centro": centro, "percentual": percentual,
                        "valor": (valor_total * percentual / Decimal("100")).quantize(Decimal("0.01"))})
    if soma != Decimal("100"):
        return []
    rateios[-1]["valor"] += valor_total - sum((item["valor"] for item in rateios), Decimal("0"))
    return rateios


def clientes_do_usuario(db: Session, usuario: Usuario):
    if usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor):
        return db.query(ClienteBPO).filter(ClienteBPO.ativo == True).all()
    return db.query(ClienteBPO).filter(
        ClienteBPO.funcionario_id == usuario.id,
        ClienteBPO.ativo == True,
    ).all()


def _total_pago_conta(db: Session, conta_id: int) -> Decimal:
    total = db.query(func.coalesce(func.sum(PagamentoParcialContaPagar.valor), 0)).filter(
        PagamentoParcialContaPagar.conta_pagar_id == conta_id,
    ).scalar()
    return Decimal(str(total or 0))


def _registrar_pagamento_conta(
    db: Session,
    conta: ContaPagar,
    valor: Decimal,
    data_pagamento: date,
    usuario_id: int | None,
    movimentacao_id: int | None = None,
    observacao: str | None = None,
) -> bool:
    valor = Decimal(str(valor))
    saldo = Decimal(str(conta.valor)) - _total_pago_conta(db, conta.id)
    if valor <= 0 or valor > saldo:
        return False

    db.add(PagamentoParcialContaPagar(
        conta_pagar_id=conta.id,
        movimentacao_id=movimentacao_id,
        valor=valor,
        data_pagamento=data_pagamento,
        observacao=observacao,
        criado_por_id=usuario_id,
    ))
    novo_total = _total_pago_conta(db, conta.id) + valor
    if novo_total >= Decimal(str(conta.valor)):
        conta.status = StatusContaPagar.pago
        conta.data_pagamento = data_pagamento
    else:
        conta.status = StatusContaPagar.agendado
        conta.data_pagamento = None
    return True


def _carregar_movimentacoes(db: Session, cliente_id: int):
    """Retorna pix_ted pendentes que NÃO estão vinculados a lote de cartão."""
    return _filtrar_conta(db, (
        db.query(MovimentacaoBancaria)
        .filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            MovimentacaoBancaria.tipo == "pix_ted",
            MovimentacaoBancaria.sentido == "recebimento",
            MovimentacaoBancaria.arquivado_conciliacao_banco == False,
            MovimentacaoBancaria.transferencia_cartao_id.is_(None),
            MovimentacaoBancaria.status.in_([
                StatusMovimentacaoBancaria.importada,
                StatusMovimentacaoBancaria.divergencia,
                StatusMovimentacaoBancaria.revisada,
            ]),
        )
        .order_by(MovimentacaoBancaria.data_movimento.asc(), MovimentacaoBancaria.id.asc())
        .all()
    ))


def _carregar_lancamentos_pendentes(db: Session, cliente_id: int):
    return (
        db.query(Atendimento)
        .filter(
            Atendimento.cliente_id == cliente_id,
            Atendimento.arquivado_conciliacao_banco == False,
            Atendimento.status_conciliacao.in_([
                StatusConciliacao.pendente,
                StatusConciliacao.divergencia,
            ]),
            Atendimento.forma_pagamento.in_([FormaPagamento.pix, FormaPagamento.transferencia]),
        )
        .order_by(Atendimento.data_prevista_recebimento.asc())
        .all()
    )


def _buscar_no_sistema(db: Session, cliente_id: int, mov: MovimentacaoBancaria, termo: str | None):
    from app.services.conciliacao_service import _extrair_cpf_digitos_meio
    termo = (termo or "").strip()
    valor = Decimal(str(mov.valor or 0))

    query = db.query(Atendimento).filter(
        Atendimento.cliente_id == cliente_id,
        Atendimento.arquivado_conciliacao_banco == False,
        Atendimento.status_conciliacao.in_([StatusConciliacao.pendente, StatusConciliacao.divergencia]),
        Atendimento.valor_servico == valor,
        Atendimento.forma_pagamento.in_([FormaPagamento.pix, FormaPagamento.transferencia]),
    )
    candidatos = query.order_by(Atendimento.data_prevista_recebimento.asc()).all()
    if mov.cpf_digitos_meio:
        procurado = mov.cpf_digitos_meio.casefold()
        candidatos = [a for a in candidatos if procurado in (a.cpf_paciente or "").casefold()]
    elif termo:
        procurado = termo.casefold()
        candidatos = [
            item for item in candidatos
            if any(procurado in (campo or "").casefold() for campo in (
                item.nome_paciente, item.cpf_paciente, item.medico, item.descricao_servico,
            ))
        ]
    return candidatos[:12]


def _montar_painel(
    db: Session,
    cliente_id: int,
    lancamentos: list,
    movimentacoes: list,
    busca_mov_id: Optional[int] = None,
    busca_termo: Optional[str] = None,
):
    banco_pendente = []
    sugestoes_prontas = 0
    sugestoes_verdes = 0
    revisar = 0

    for mov in movimentacoes:
        sugestao = buscar_sugestao(mov, lancamentos)
        if sugestao and sugestao["status"] in ("sugestao_pronta", "sugestao_verde"):
            sugestoes_prontas += 1
        elif sugestao and sugestao["status"] == "sugestao_verde":
            sugestoes_verdes += 1
        elif sugestao:
            revisar += 1

        busca_aberta = busca_mov_id == mov.id
        resultados_busca = _buscar_no_sistema(db, cliente_id, mov, busca_termo) if busca_aberta else []

        banco_pendente.append({
            "movimentacao": mov,
            "sugestao": sugestao,
            "busca_aberta": busca_aberta,
            "busca_termo": busca_termo or "",
            "resultados_busca": resultados_busca,
        })

    return {
        "banco_pendente": banco_pendente,
        "totais": {
            "movimentos_banco": len(movimentacoes),
            "lancamentos_erp": len(lancamentos),
            "sugestoes_prontas": sugestoes_prontas + sugestoes_verdes,
            "sugestoes_verdes": sugestoes_verdes,
            "conciliar_todos": sugestoes_prontas + sugestoes_verdes,
            "revisar": revisar,
        },
    }


def _aplicar_conciliacao(db: Session, mov: MovimentacaoBancaria, at: Atendimento):
    at.status_conciliacao = StatusConciliacao.conciliado
    at.data_credito = mov.data_movimento
    at.valor_liquido = mov.valor
    mov.status = StatusMovimentacaoBancaria.conciliada
    mov.conciliada_com_atendimento_id = at.id
    db.commit()


def _conciliar_pix_ted_prontos(db: Session, cliente_id: int, usuario: Usuario | None = None) -> int:
    movs = _carregar_movimentacoes(db, cliente_id)
    lancs = _carregar_lancamentos_pendentes(db, cliente_id)
    conciliados = 0
    for mov in movs:
        sugestao = buscar_sugestao(mov, lancs)
        if sugestao and sugestao["status"] == "sugestao_pronta":
            at = sugestao["atendimento"]
            _aplicar_conciliacao(db, mov, at)
            if usuario:
                _log(
                    db,
                    "Conciliação PIX/TED em lote",
                    "conciliacao",
                    usuario_id=usuario.id,
                    usuario_nome=usuario.nome,
                    cliente_id=cliente_id,
                    detalhes=f"Movimentação #{mov.id} -> Atendimento #{at.id}",
                )
            lancs = [l for l in lancs if l.id != at.id]
            conciliados += 1
    return conciliados


def _auto_match_lotes(db: Session, cliente_id: int, usuario: Usuario | None = None) -> int:
    lotes_pendentes = db.query(TransferenciaCartao).filter(
        TransferenciaCartao.cliente_id == cliente_id,
        TransferenciaCartao.status == StatusTransferenciaCartao.pendente,
    ).all()

    conciliados = 0
    for lote in lotes_pendentes:
        mov = db.query(MovimentacaoBancaria).filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            or_(db.info.get("banco_conta_id") is None, MovimentacaoBancaria.conta_bancaria_id == db.info.get("banco_conta_id")),
            MovimentacaoBancaria.tipo == "pix_ted",
            MovimentacaoBancaria.sentido == "recebimento",
            MovimentacaoBancaria.conciliada_com_atendimento_id.is_(None),
            MovimentacaoBancaria.transferencia_cartao_id.is_(None),
            MovimentacaoBancaria.valor == lote.valor_liquido,
        ).first()
        if mov:
            mov.transferencia_cartao_id = lote.id
            mov.status = StatusMovimentacaoBancaria.conciliada
            lote.status = StatusTransferenciaCartao.conciliada
            if usuario:
                _log(
                    db,
                    "Conciliação de lotes em lote",
                    "conciliacao",
                    usuario_id=usuario.id,
                    usuario_nome=usuario.nome,
                    cliente_id=cliente_id,
                    detalhes=f"Lote #{lote.id} -> Movimentação #{mov.id} por valor exato",
                )
            conciliados += 1

    if conciliados:
        db.commit()
    return conciliados


def _carregar_saidas_banco(db: Session, cliente_id: int):
    """Saídas bancárias ainda não vinculadas a uma conta a pagar."""
    return _filtrar_conta(db, (
        db.query(MovimentacaoBancaria)
        .filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            MovimentacaoBancaria.sentido == "pagamento",
            MovimentacaoBancaria.arquivado_conciliacao_banco == False,
            MovimentacaoBancaria.conta_pagar_id.is_(None),
            MovimentacaoBancaria.status.in_([
                StatusMovimentacaoBancaria.importada,
                StatusMovimentacaoBancaria.divergencia,
                StatusMovimentacaoBancaria.revisada,
            ]),
        )
        .order_by(MovimentacaoBancaria.data_movimento.desc())
        .all()
    ))


def _carregar_contas_agendadas(db: Session, cliente_id: int):
    """Contas a pagar com status agendado aguardando conciliação bancária."""
    return (
        db.query(ContaPagar)
        .filter(
            ContaPagar.cliente_id == cliente_id,
            ContaPagar.status.in_([
                StatusContaPagar.agendado,
                StatusContaPagar.pago_nao_conciliado,
            ]),
            ContaPagar.arquivado_conciliacao_banco == False,
        )
        .order_by(ContaPagar.vencimento.asc())
        .all()
    )


def _carregar_lotes_cartao(db: Session, cliente_id: int):
    return (
        db.query(TransferenciaCartao)
        .filter(TransferenciaCartao.cliente_id == cliente_id)
        .order_by(TransferenciaCartao.data.desc(), TransferenciaCartao.bandeira)
        .all()
    )


def _carregar_creditos_banco_para_lote(db: Session, cliente_id: int):
    """MovimentacaoBancaria pix_ted ainda não vinculadas a lote de cartão (disponíveis para match)."""
    return _filtrar_conta(db, (
        db.query(MovimentacaoBancaria)
        .filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            MovimentacaoBancaria.tipo == "pix_ted",
            MovimentacaoBancaria.sentido == "recebimento",
            MovimentacaoBancaria.arquivado_conciliacao_banco == False,
            MovimentacaoBancaria.transferencia_cartao_id.is_(None),
            MovimentacaoBancaria.status.in_([
                StatusMovimentacaoBancaria.importada,
                StatusMovimentacaoBancaria.divergencia,
                StatusMovimentacaoBancaria.revisada,
                StatusMovimentacaoBancaria.conciliada,
            ]),
        )
        .order_by(MovimentacaoBancaria.data_movimento.desc())
        .all()
    ))


def _carregar_pix_conciliados(db: Session, cliente_id: int):
    """PIX/TED já conciliados com atendimento — para exibir com opção de desvincular."""
    return _filtrar_conta(db, (
        db.query(MovimentacaoBancaria)
        .filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            MovimentacaoBancaria.tipo == "pix_ted",
            MovimentacaoBancaria.sentido == "recebimento",
            MovimentacaoBancaria.status == StatusMovimentacaoBancaria.conciliada,
            MovimentacaoBancaria.arquivado_conciliacao_banco == False,
            MovimentacaoBancaria.conciliada_com_atendimento_id.isnot(None),
            MovimentacaoBancaria.transferencia_cartao_id.is_(None),
        )
        .order_by(MovimentacaoBancaria.data_movimento.desc())
        .limit(100)
        .all()
    ))


def _resumo_periodo_movimentacoes(movimentacoes: list) -> str:
    if not movimentacoes:
        return ""
    datas = [m.data_movimento for m in movimentacoes if m.data_movimento]
    if not datas:
        return ""
    inicio = min(datas)
    fim = max(datas)
    if inicio == fim:
        return f"em {inicio.strftime('%d/%m/%Y')}"
    return f"de {inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"


def _opcoes_mes_movimentacoes(movimentacoes: list) -> list[dict]:
    opcoes = []
    vistos = set()
    for mov in movimentacoes:
        if not mov.data_movimento:
            continue
        chave = mov.data_movimento.strftime("%Y-%m")
        if chave in vistos:
            continue
        vistos.add(chave)
        opcoes.append({
            "valor": chave,
            "label": mov.data_movimento.strftime("%m/%Y"),
        })
    return opcoes


def _carregar_saidas_conciliadas(db: Session, cliente_id: int):
    """Saídas bancárias já conciliadas com conta a pagar — para exibir com opção de desvincular."""
    return _filtrar_conta(db, (
        db.query(MovimentacaoBancaria)
        .filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            MovimentacaoBancaria.sentido == "pagamento",
            MovimentacaoBancaria.status == StatusMovimentacaoBancaria.conciliada,
            MovimentacaoBancaria.arquivado_conciliacao_banco == False,
            MovimentacaoBancaria.conta_pagar_id.isnot(None),
        )
        .order_by(MovimentacaoBancaria.data_movimento.desc())
        .limit(100)
        .all()
    ))


def _carregar_arquivados(db: Session, cliente_id: int):
    movimentacoes = (
        db.query(MovimentacaoBancaria)
        .filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            MovimentacaoBancaria.arquivado_conciliacao_banco == True,
        )
        .order_by(MovimentacaoBancaria.data_movimento.desc(), MovimentacaoBancaria.id.desc())
        .all()
    )
    lancamentos = (
        db.query(Atendimento)
        .filter(
            Atendimento.cliente_id == cliente_id,
            Atendimento.arquivado_conciliacao_banco == True,
        )
        .order_by(Atendimento.data_prevista_recebimento.desc(), Atendimento.id.desc())
        .all()
    )
    contas = (
        db.query(ContaPagar)
        .filter(
            ContaPagar.cliente_id == cliente_id,
            ContaPagar.arquivado_conciliacao_banco == True,
        )
        .order_by(ContaPagar.vencimento.desc(), ContaPagar.id.desc())
        .all()
    )
    return movimentacoes, lancamentos, contas


def _conta_bancaria_do_ofx(db: Session, cliente_id: int, df) -> ContaBancaria:
    banco = str(df.attrs.get("ofx_banco") or "Banco OFX").strip()
    numero = str(df.attrs.get("ofx_conta") or "Conta não identificada").strip()
    conta = db.query(ContaBancaria).filter(
        ContaBancaria.cliente_id == cliente_id,
        ContaBancaria.banco == banco,
        ContaBancaria.conta == numero,
    ).first()
    if db.info.get("banco_conta_id"):
        selecionada = conta_do_cliente(db, cliente_id, db.info["banco_conta_id"])
        if conta and conta.id != selecionada.id:
            raise ValueError("O OFX pertence a outra conta cadastrada.")
        if selecionada.conta and numero and selecionada.conta.strip() != numero:
            raise ValueError("O numero da conta do OFX difere da conta selecionada.")
        conta = selecionada
    if not conta:
        conta = ContaBancaria(
            cliente_id=cliente_id,
            nome=f"{banco} · {numero}",
            tipo=TipoContaBancaria.bancaria,
            banco=banco,
            conta=numero,
            ativo=True,
        )
        db.add(conta)
        db.flush()
    if "ofx_saldo" in df.attrs:
        referencia = df.attrs.get("ofx_saldo_data") or datetime.now()
        referencia = datetime.combine(referencia.date(), datetime.max.time())
        if not conta.saldo_data_referencia or referencia >= conta.saldo_data_referencia.replace(tzinfo=None):
            conta.saldo_atual = df.attrs["ofx_saldo"]
            conta.saldo_data_referencia = referencia
            conta.saldo_atualizado_em = datetime.now()
    return conta


def _resumo_saldos_bancarios(db: Session, cliente_id: int | None) -> list[dict]:
    if not cliente_id:
        return []
    contas = db.query(ContaBancaria).filter(
        ContaBancaria.cliente_id == cliente_id,
        ContaBancaria.ativo == True,
        ContaBancaria.tipo == TipoContaBancaria.bancaria,
    ).order_by(ContaBancaria.nome).all()
    resumos = []
    for conta in contas:
        movimentos = db.query(MovimentacaoBancaria).filter(
            MovimentacaoBancaria.cliente_id == cliente_id,
            MovimentacaoBancaria.conta_bancaria_id == conta.id,
            MovimentacaoBancaria.arquivado_conciliacao_banco == False,
        ).all()
        entradas = sum((Decimal(str(m.valor or 0)) for m in movimentos if m.sentido == "recebimento"), Decimal("0"))
        saidas = sum((Decimal(str(m.valor or 0)) for m in movimentos if m.sentido == "pagamento"), Decimal("0"))
        pendentes = [m for m in movimentos if m.status != StatusMovimentacaoBancaria.conciliada]
        resumos.append({
            "conta": conta,
            "saldo_previsto": saldo_previsto(conta, movimentos),
            "entradas": entradas,
            "saidas": saidas,
            "total_movimentos": len(movimentos),
            "conciliados": len(movimentos) - len(pendentes),
            "pendentes": len(pendentes),
            "conferido": bool(movimentos) and not pendentes,
        })
    return resumos


def _movimentacoes_do_extrato(db: Session, cliente_id: int | None):
    if not cliente_id:
        return []
    return db.query(MovimentacaoBancaria).filter(
        MovimentacaoBancaria.cliente_id == cliente_id,
        MovimentacaoBancaria.conta_bancaria_id.isnot(None),
        or_(db.info.get("banco_conta_id") is None, MovimentacaoBancaria.conta_bancaria_id == db.info.get("banco_conta_id")),
        MovimentacaoBancaria.arquivado_conciliacao_banco == False,
    ).order_by(MovimentacaoBancaria.data_movimento.desc(), MovimentacaoBancaria.id.desc()).limit(500).all()


def _ctx_padrao(db, usuario, cliente_id, busca_mov_id=None, busca_termo=None, mes_conciliado=None,
                data_inicio=None, data_fim=None):
    clientes = clientes_do_usuario(db, usuario)
    movs  = _carregar_movimentacoes(db, cliente_id) if cliente_id else []
    lancs = _carregar_lancamentos_pendentes(db, cliente_id) if cliente_id else []
    lotes   = _carregar_lotes_cartao(db, cliente_id) if cliente_id else []
    creditos_banco = _carregar_creditos_banco_para_lote(db, cliente_id) if cliente_id else []
    saidas_banco = _carregar_saidas_banco(db, cliente_id) if cliente_id else []
    contas_agendadas = _carregar_contas_agendadas(db, cliente_id) if cliente_id else []
    def dentro_periodo(data_item):
        return (not data_inicio or (data_item and data_item >= data_inicio)) and (not data_fim or (data_item and data_item <= data_fim))
    if data_inicio or data_fim:
        movs = [m for m in movs if dentro_periodo(m.data_movimento)]
        creditos_banco = [m for m in creditos_banco if dentro_periodo(m.data_movimento)]
        saidas_banco = [m for m in saidas_banco if dentro_periodo(m.data_movimento)]
        lancs = [a for a in lancs if dentro_periodo(a.data_prevista_recebimento)]
        contas_agendadas = [c for c in contas_agendadas if dentro_periodo(c.vencimento)]
    extrato_movimentacoes = _movimentacoes_do_extrato(db, cliente_id)
    if data_inicio or data_fim:
        extrato_movimentacoes = [m for m in extrato_movimentacoes if dentro_periodo(m.data_movimento)]
    pix_conciliados_todos = _carregar_pix_conciliados(db, cliente_id) if cliente_id else []
    pix_conciliados = pix_conciliados_todos
    if mes_conciliado:
        pix_conciliados = [
            mov for mov in pix_conciliados_todos
            if mov.data_movimento and mov.data_movimento.strftime("%Y-%m") == mes_conciliado
        ]
    saidas_conciliadas = _carregar_saidas_conciliadas(db, cliente_id) if cliente_id else []
    arquivados = _carregar_arquivados(db, cliente_id) if cliente_id else ([], [], [])
    painel  = _montar_painel(db, cliente_id, lancs, movs, busca_mov_id, busca_termo) if cliente_id else None
    return {
        "clientes": clientes,
        "cliente_selecionado": cliente_id,
        "conta_bancaria_selecionada": db.info.get("banco_conta_id"),
        "transferencia_token": str(uuid.uuid4()),
        "receitas_pendentes": lancs,
        "movimentacoes_bancarias": movs,
        "lotes_cartao": lotes,
        "creditos_banco": creditos_banco,
        "saidas_banco": saidas_banco,
        "contas_agendadas": contas_agendadas,
        "pix_conciliados": pix_conciliados,
        "pix_conciliados_mes_opcoes": _opcoes_mes_movimentacoes(pix_conciliados_todos) if cliente_id else [],
        "pix_conciliados_mes": mes_conciliado or "",
        "pix_conciliados_periodo": _resumo_periodo_movimentacoes(pix_conciliados) if cliente_id else "",
        "saidas_conciliadas": saidas_conciliadas,
        "movimentacoes_arquivadas": arquivados[0],
        "lancamentos_arquivados": arquivados[1],
        "contas_arquivadas": arquivados[2],
        "painel": painel,
        "saldos_bancarios": _resumo_saldos_bancarios(db, cliente_id),
        "regras_bancarias": db.query(RegraNegocioBancaria).filter(
            RegraNegocioBancaria.cliente_id == cliente_id,
            RegraNegocioBancaria.ativo.is_(True),
        ).order_by(RegraNegocioBancaria.nome).all() if cliente_id else [],
        "planos_receita_banco": db.query(PlanoConta).filter(
            PlanoConta.tipo == "receita", PlanoConta.ativo.is_(True),
            or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == cliente_id),
        ).order_by(PlanoConta.codigo, PlanoConta.nome).all() if cliente_id else [],
        "planos_despesa_banco": db.query(PlanoConta).filter(
            PlanoConta.tipo == "despesa", PlanoConta.ativo.is_(True),
            or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == cliente_id),
        ).order_by(PlanoConta.codigo, PlanoConta.nome).all() if cliente_id else [],
        "extrato_movimentacoes": extrato_movimentacoes,
        "resultado": None,
        "tipo_selecionado": "pix_ted",
        "hoje": date.today().isoformat(),
        "data_inicio_banco": data_inicio.isoformat() if data_inicio else "",
        "data_fim_banco": data_fim.isoformat() if data_fim else "",
        "centros_custo_banco": db.query(CentroCusto).filter(
            CentroCusto.cliente_id == cliente_id,
            CentroCusto.ativo == True,
        ).order_by(CentroCusto.nome).all() if cliente_id else [],
    }


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@router.get("/conciliacao/banco", response_class=HTMLResponse)
async def pagina_banco(
    request: Request,
    cliente_id: Optional[int] = None,
    buscar_mov: Optional[int] = Query(default=None),
    termo: Optional[str] = Query(default=None),
    lote_fechado: Optional[int] = Query(default=None),
    mes_conciliado: Optional[str] = Query(default=None),
    arquivados: bool = Query(default=False),
    manual_criado: Optional[str] = Query(default=None),
    data_inicio: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    if usuario.perfil.value in ("secretaria", "medico"):
        return RedirectResponse(url="/", status_code=303)
    cliente_id = _ca(request, cliente_id)
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    if cliente_id and cliente_id not in ids_permitidos:
        cliente_id = None
    flash_success = None
    flash_error = None
    if manual_criado == "receita":
        flash_success = "Conta a receber criada e adicionada às sugestões da conciliação."
    elif manual_criado == "despesa":
        flash_success = "Despesa criada e adicionada às sugestões da conciliação."
    elif manual_criado == "parcial":
        flash_success = "Pagamento parcial registrado. O saldo restante continua pendente."
    elif manual_criado == "movimentacao":
        flash_success = "Movimentação manual criada no extrato e marcada para conciliação."
    elif manual_criado == "movimentacao_invalida":
        flash_error = "Selecione uma conta bancária ou informe banco e número da nova conta."
    elif manual_criado == "parcial_invalido":
        flash_error = "O pagamento parcial deve ser maior que zero e não pode ultrapassar o saldo da despesa."
    elif manual_criado == "rateio_invalido":
        flash_error = "Rateio inválido: use centros diferentes e feche exatamente 100%."
    if lote_fechado:
        lote = db.query(TransferenciaCartao).filter(TransferenciaCartao.id == lote_fechado).first()
        if lote:
            flash_success = (
                f"Lote {lote.bandeira} {lote.data.strftime('%d/%m/%Y')} fechado — "
                f"R$ {lote.valor_liquido:.2f} aguardando crédito bancário."
            )

    ctx = _ctx_padrao(db, usuario, cliente_id, buscar_mov, termo, mes_conciliado, data_inicio, data_fim)
    response = templates.TemplateResponse("conciliacao_banco.html", {
        "request": request, "usuario": usuario,
        "flash_success": flash_success,
        "flash_error": flash_error,
        "lote_destaque_id": lote_fechado,
        "mostrar_arquivados": arquivados,
        **ctx,
    })
    if cliente_id:
        response.set_cookie(f"banco_conta_{cliente_id}", str(db.info.get("banco_conta_id") or ""), samesite="lax")
    return response



@router.post("/conciliacao/banco/manual/receita")
async def criar_receita_manual_banco(
    request: Request,
    cliente_id: int = Form(...),
    descricao: str = Form(...),
    nome_pagador: str = Form(""),
    valor: Decimal = Form(...),
    data_recebimento: date = Form(...),
    forma_pagamento: str = Form("pix"),
    plano_conta_id: int = Form(...),
    observacao: str = Form(""),
    rateios_json: str = Form("[]"),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    plano = _plano_valido(db, cliente_id, plano_conta_id, "receita")
    if cliente_id not in [c.id for c in clientes] or valor <= 0 or not plano:
        return RedirectResponse(url="/conciliacao/banco", status_code=303)

    forma = FormaPagamento.transferencia if forma_pagamento == "transferencia" else FormaPagamento.pix
    condicao = CondicaoPagamento.transferencia if forma == FormaPagamento.transferencia else CondicaoPagamento.pix
    rateios = _montar_rateios_banco(db, cliente_id, valor, rateios_json)
    if rateios_json not in ("", "[]") and not rateios:
        return RedirectResponse(
            url=f"/conciliacao/banco?cliente_id={cliente_id}&manual_criado=rateio_invalido", status_code=303,
        )
    atendimento = Atendimento(
        cliente_id=cliente_id,
        data_atendimento=data_recebimento,
        nome_paciente=nome_pagador.strip() or None,
        descricao_servico=descricao.strip(),
        valor_servico=valor,
        valor_liquido=valor,
        valor_clinica=valor,
        condicao_pagamento=condicao,
        forma_pagamento=forma,
        data_prevista_recebimento=data_recebimento,
        status_conciliacao=StatusConciliacao.pendente,
        observacao=observacao.strip() or None,
        lancado_por_id=usuario.id,
        centro_custo_id=rateios[0]["centro"].id if rateios else None,
        plano_conta_id=plano.id,
    )
    db.add(atendimento)
    db.flush()
    for rateio in rateios:
        db.add(AtendimentoCentroCustoRateio(
            atendimento_id=atendimento.id, centro_custo_id=rateio["centro"].id,
            percentual=rateio["percentual"], valor=rateio["valor"],
        ))
    db.commit()
    _log(db, "Conta a receber criada na conciliação bancária", "conciliacao_banco",
         usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
         detalhes=f"Atendimento #{atendimento.id} - {descricao.strip()}",
         ip=request.client.host if request.client else None)
    return RedirectResponse(
        url=f"/conciliacao/banco?cliente_id={cliente_id}&manual_criado=receita",
        status_code=303,
    )


@router.post("/conciliacao/banco/manual/movimentacao")
async def criar_movimentacao_manual_banco(
    request: Request,
    cliente_id: int = Form(...),
    conta_bancaria_id: Optional[int] = Form(None),
    banco: str = Form(""),
    conta_numero: str = Form(""),
    sentido: str = Form(...),
    data_movimento: date = Form(...),
    valor: Decimal = Form(...),
    descricao: str = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes] or valor <= 0 or sentido not in ("recebimento", "pagamento"):
        return RedirectResponse(url="/conciliacao/banco", status_code=303)

    conta_bancaria = None
    if conta_bancaria_id:
        conta_bancaria = db.query(ContaBancaria).filter(
            ContaBancaria.id == conta_bancaria_id,
            ContaBancaria.cliente_id == cliente_id,
            ContaBancaria.ativo == True,
        ).first()
    if not conta_bancaria:
        banco_nome = banco.strip()
        numero = conta_numero.strip()
        if not banco_nome or not numero:
            return RedirectResponse(
                url=f"/conciliacao/banco?cliente_id={cliente_id}&manual_criado=movimentacao_invalida",
                status_code=303,
            )
        conta_bancaria = db.query(ContaBancaria).filter(
            ContaBancaria.cliente_id == cliente_id,
            ContaBancaria.banco == banco_nome,
            ContaBancaria.conta == numero,
        ).first()
        if not conta_bancaria:
            conta_bancaria = ContaBancaria(
                cliente_id=cliente_id,
                nome=f"{banco_nome} · {numero}",
                tipo=TipoContaBancaria.bancaria,
                banco=banco_nome,
                conta=numero,
                ativo=True,
            )
            db.add(conta_bancaria)
            db.flush()

    movimento = MovimentacaoBancaria(
        cliente_id=cliente_id,
        conta_bancaria_id=conta_bancaria.id,
        tipo="pix_ted",
        sentido=sentido,
        data_movimento=data_movimento,
        valor=valor,
        descricao=descricao.strip(),
        origem_arquivo="Lançamento manual no sistema",
        origem_manual=True,
        status=StatusMovimentacaoBancaria.importada,
    )
    db.add(movimento)
    db.flush()
    _aplicar_regras_bancarias(db, cliente_id)
    db.commit()
    _log(db, "Movimentação manual criada no extrato", "conciliacao_banco",
         usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
         detalhes=f"Movimentação #{movimento.id} - {sentido} - R$ {valor}",
         ip=request.client.host if request.client else None)
    return RedirectResponse(
        url=f"/conciliacao/banco?cliente_id={cliente_id}&manual_criado=movimentacao",
        status_code=303,
    )
@router.post("/conciliacao/banco/manual/despesa")
async def criar_despesa_manual_banco(
    request: Request,
    cliente_id: int = Form(...),
    descricao: str = Form(...),
    fornecedor: str = Form(""),
    valor: Decimal = Form(...),
    vencimento: date = Form(...),
    plano_conta_id: int = Form(...),
    observacao: str = Form(""),
    rateios_json: str = Form("[]"),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    plano = _plano_valido(db, cliente_id, plano_conta_id, "despesa")
    if cliente_id not in [c.id for c in clientes] or valor <= 0 or not plano:
        return RedirectResponse(url="/conciliacao/banco", status_code=303)

    rateios = _montar_rateios_banco(db, cliente_id, valor, rateios_json)
    if rateios_json not in ("", "[]") and not rateios:
        return RedirectResponse(
            url=f"/conciliacao/banco?cliente_id={cliente_id}&manual_criado=rateio_invalido", status_code=303,
        )
    conta = ContaPagar(
        cliente_id=cliente_id,
        descricao=descricao.strip(),
        fornecedor=fornecedor.strip() or None,
        valor=valor,
        vencimento=vencimento,
        status=StatusContaPagar.agendado,
        observacao=observacao.strip() or None,
        lancado_por_id=usuario.id,
        categoria_dre=_chave_centro_custo(rateios[0]["centro"]) if rateios else None,
        plano_conta_id=plano.id,
    )
    db.add(conta)
    db.flush()
    for rateio in rateios:
        db.add(ContaPagarCentroCustoRateio(
            conta_pagar_id=conta.id, centro_custo_id=rateio["centro"].id,
            categoria_key=_chave_centro_custo(rateio["centro"]),
            percentual=rateio["percentual"], valor=rateio["valor"],
        ))
    db.commit()
    _log(db, "Despesa criada na conciliação bancária", "conciliacao_banco",
         usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
         detalhes=f"Conta a pagar #{conta.id} - {descricao.strip()}",
         ip=request.client.host if request.client else None)
    return RedirectResponse(
        url=f"/conciliacao/banco?cliente_id={cliente_id}&manual_criado=despesa",
        status_code=303,
    )


@router.post("/conciliacao/banco/manual/pagamento-parcial")
async def criar_pagamento_parcial_banco(
    request: Request,
    cliente_id: int = Form(...),
    conta_id: int = Form(...),
    valor: Decimal = Form(...),
    data_pagamento: date = Form(...),
    observacao: str = Form(""),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    autorizado = (
        conta
        and conta.cliente_id == cliente_id
        and cliente_id in [c.id for c in clientes]
        and conta.status in (StatusContaPagar.agendado, StatusContaPagar.pago_nao_conciliado)
        and not conta.arquivado_conciliacao_banco
    )
    if not autorizado or not _registrar_pagamento_conta(
        db, conta, valor, data_pagamento, usuario.id,
        observacao=observacao.strip() or "Pagamento parcial manual",
    ):
        return RedirectResponse(
            url=f"/conciliacao/banco?cliente_id={cliente_id}&manual_criado=parcial_invalido",
            status_code=303,
        )

    db.commit()
    _log(db, "Pagamento parcial de despesa registrado", "conciliacao_banco",
         usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
         detalhes=f"Conta a pagar #{conta.id} - R$ {valor}",
         ip=request.client.host if request.client else None)
    return RedirectResponse(
        url=f"/conciliacao/banco?cliente_id={cliente_id}&manual_criado=parcial",
        status_code=303,
    )


@router.post("/conciliacao/banco/importar-lancamentos", response_class=HTMLResponse)
async def importar_lancamentos_banco(
    request: Request,
    cliente_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao/banco", status_code=303)

    flash_success = None
    flash_error = None
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
    except Exception:
        flash_error = public_import_error(logger, "importar_lancamentos_banco")
    finally:
        try:
            if caminho:
                os.remove(caminho)
        except OSError:
            pass

    ctx = _ctx_padrao(db, usuario, cliente_id)
    return templates.TemplateResponse("conciliacao_banco.html", {
        "request": request, "usuario": usuario,
        "flash_success": flash_success, "flash_error": flash_error,
        **ctx,
    })


@router.post("/conciliacao/banco/importar-extrato", response_class=HTMLResponse)
async def importar_extrato_banco(
    request: Request,
    cliente_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao/banco", status_code=303)

    resultado = {"arquivo": arquivo.filename, "conciliados": [], "divergencias": [], "erro": None}
    caminho = None
    try:
        caminho, nome_original, ext = await salvar_upload_temporario(
            arquivo,
            {".csv", ".xlsx", ".xls", ".ofx", ".ofc"},
        )
        resultado["arquivo"] = nome_original

        if ext in (".ofx", ".ofc"):
            df = parse_ofx(caminho)
            conta_bancaria = _conta_bancaria_do_ofx(db, cliente_id, df)
            importacao = importar_movimentacoes_bancarias(
                db, cliente_id, df, nome_original, conta_bancaria_id=conta_bancaria.id,
            )
            resultado["conciliados"] = []
            resultado["divergencias"] = []
            resultado["importados"] = importacao["importados"]
            resultado["regras_aplicadas"] = _aplicar_regras_bancarias(db, cliente_id)
            db.commit()
        else:
            if not db.info.get("banco_conta_id"):
                raise ValueError("Selecione a conta bancaria antes de importar CSV ou XLSX.")
            df = ler_arquivo_extrato(caminho)
            importacao = importar_movimentacoes_bancarias(db, cliente_id, df, nome_original, conta_bancaria_id=db.info["banco_conta_id"])
            resultado["importados"] = importacao["importados"]
            resultado["regras_aplicadas"] = _aplicar_regras_bancarias(db, cliente_id)
            db.commit()
    except Exception:
        db.rollback()
        resultado["erro"] = public_import_error(logger, "importar_extrato_banco")
    finally:
        try:
            if caminho:
                os.remove(caminho)
        except OSError:
            pass

    ctx = _ctx_padrao(db, usuario, cliente_id)
    return templates.TemplateResponse("conciliacao_banco.html", {
        "request": request, "usuario": usuario,
        "resultado": resultado if not resultado["erro"] else None,
        "flash_error": resultado["erro"],
        **ctx,
    })


@router.post("/conciliacao/banco/conciliar-todos-prontos")
async def conciliar_todos_prontos(
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao/banco", status_code=303)

    _conciliar_pix_ted_prontos(db, cliente_id, usuario)

    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/banco/movimentacao/{mov_id}/conciliar")
async def conciliar_movimentacao(
    mov_id: int,
    cliente_id: int = Form(...),
    atendimento_id: int = Form(...),
    origem: str = Form("sugestao"),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    mov = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()
    at = db.query(Atendimento).filter(Atendimento.id == atendimento_id).first()

    if (mov and at
            and mov.cliente_id in ids_permitidos
            and at.cliente_id == mov.cliente_id == cliente_id):
        _aplicar_conciliacao(db, mov, at)

    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/banco/movimentacao/{mov_id}/revisar")
async def revisar_movimentacao(
    mov_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    mov = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()
    if mov and mov.cliente_id in ids_permitidos:
        mov.status = StatusMovimentacaoBancaria.revisada
        db.commit()

    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/banco/movimentacao/{mov_id}/arquivar")
async def arquivar_movimentacao(
    mov_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    mov = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()
    if mov and mov.cliente_id == cliente_id and cliente_id in [c.id for c in clientes]:
        mov.arquivado_conciliacao_banco = True
        db.commit()
        _log(db, "Movimentação bancária arquivada", "conciliacao_banco",
             usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
             detalhes=f"Movimentação #{mov.id}")
    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/banco/movimentacao/{mov_id}/restaurar")
async def restaurar_movimentacao(
    mov_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    mov = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()
    if mov and mov.cliente_id == cliente_id and cliente_id in [c.id for c in clientes]:
        mov.arquivado_conciliacao_banco = False
        db.commit()
    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}&arquivados=1", status_code=303)


@router.post("/conciliacao/banco/lancamento/{atendimento_id}/arquivar")
async def arquivar_lancamento_sistema(
    atendimento_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    atendimento = db.query(Atendimento).filter(Atendimento.id == atendimento_id).first()
    if atendimento and atendimento.cliente_id == cliente_id and cliente_id in [c.id for c in clientes]:
        atendimento.arquivado_conciliacao_banco = True
        db.commit()
        _log(db, "Lançamento do sistema arquivado", "conciliacao_banco",
             usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
             detalhes=f"Atendimento #{atendimento.id}")
    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/banco/lancamento/{atendimento_id}/restaurar")
async def restaurar_lancamento_sistema(
    atendimento_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    atendimento = db.query(Atendimento).filter(Atendimento.id == atendimento_id).first()
    if atendimento and atendimento.cliente_id == cliente_id and cliente_id in [c.id for c in clientes]:
        atendimento.arquivado_conciliacao_banco = False
        db.commit()
    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}&arquivados=1", status_code=303)


@router.post("/conciliacao/banco/conta/{conta_id}/arquivar")
async def arquivar_conta_sistema(
    conta_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if conta and conta.cliente_id == cliente_id and cliente_id in [c.id for c in clientes]:
        conta.arquivado_conciliacao_banco = True
        db.commit()
        _log(db, "Conta do sistema arquivada na conciliação", "conciliacao_banco",
             usuario_id=usuario.id, usuario_nome=usuario.nome, cliente_id=cliente_id,
             detalhes=f"Conta a pagar #{conta.id}")
    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/banco/conta/{conta_id}/restaurar")
async def restaurar_conta_sistema(
    conta_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()
    if conta and conta.cliente_id == cliente_id and cliente_id in [c.id for c in clientes]:
        conta.arquivado_conciliacao_banco = False
        db.commit()
    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}&arquivados=1", status_code=303)


@router.post("/conciliacao/banco/movimentacao/{mov_id}/desvincular")
async def desvincular_movimentacao_pix(
    mov_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]

    mov = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()
    if not mov or mov.cliente_id not in ids_ok or mov.cliente_id != cliente_id:
        return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}#movimentacoes", status_code=303)

    if mov.conciliada_com_atendimento_id:
        at = db.query(Atendimento).filter(Atendimento.id == mov.conciliada_com_atendimento_id).first()
        if at:
            at.status_conciliacao = StatusConciliacao.pendente
            at.data_credito = None
            at.valor_liquido = at.valor_servico  # restaura valor original

    mov.conciliada_com_atendimento_id = None
    mov.status = StatusMovimentacaoBancaria.importada
    db.commit()
    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}#movimentacoes", status_code=303)


@router.post("/conciliacao/banco/movimentacao/{mov_id}/criar-e-conciliar")
async def criar_e_conciliar(
    mov_id: int,
    cliente_id: int = Form(...),
    data_atendimento: str = Form(...),
    nome_paciente: str = Form(""),
    cpf_paciente: str = Form(""),
    medico: str = Form(""),
    especialidade: str = Form(""),
    tipo_servico: str = Form(""),
    descricao_servico: str = Form(""),
    observacao: str = Form(""),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    from datetime import date as date_type
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    mov = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()
    if not mov or mov.cliente_id not in ids_permitidos or mov.cliente_id != cliente_id:
        return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)

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
        valor_servico=mov.valor,
        condicao_pagamento=CondicaoPagamento.pix,
        forma_pagamento=FormaPagamento.pix,
        data_prevista_recebimento=mov.data_movimento,
        data_credito=mov.data_movimento,
        valor_liquido=mov.valor,
        status_conciliacao=StatusConciliacao.conciliado,
        observacao=observacao or None,
        lancado_por_id=usuario.id,
    )
    db.add(at)
    db.flush()

    mov.status = StatusMovimentacaoBancaria.conciliada
    mov.conciliada_com_atendimento_id = at.id
    db.commit()

    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


# ---------------------------------------------------------------------------
# Lotes de cartão × extrato conta corrente
# ---------------------------------------------------------------------------

@router.post("/conciliacao/banco/conta-corrente/importar", response_class=HTMLResponse)
async def importar_conta_corrente(
    request: Request,
    cliente_id: int = Form(...),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao/banco", status_code=303)

    flash_success = flash_error = None
    caminho = None
    try:
        caminho, nome_original, ext = await salvar_upload_temporario(
            arquivo,
            {".csv", ".xlsx", ".xls", ".ofx", ".ofc"},
        )
        df = parse_ofx(caminho) if ext in (".ofx", ".ofc") else ler_arquivo_extrato(caminho)
        res = importar_extrato_conta_corrente(db, cliente_id, df, nome_original)
        flash_success = (
            f"{res['importados']} linha(s) importada(s) de '{nome_original}'. "
            "As correspondências encontradas estão disponíveis como sugestões."
        )
    except Exception:
        flash_error = public_import_error(logger, "importar_conta_corrente")
    finally:
        try:
            if caminho:
                os.remove(caminho)
        except OSError:
            pass

    ctx = _ctx_padrao(db, usuario, cliente_id)
    return templates.TemplateResponse("conciliacao_banco.html", {
        "request": request, "usuario": usuario,
        "flash_success": flash_success, "flash_error": flash_error,
        **ctx,
    })


@router.post("/conciliacao/banco/lote/{lote_id}/conciliar")
async def conciliar_lote_com_banco(
    lote_id: int,
    cliente_id: int = Form(...),
    mov_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]

    lote = db.query(TransferenciaCartao).filter(TransferenciaCartao.id == lote_id).first()
    mov  = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()

    if (lote and mov
            and lote.cliente_id in ids_ok
            and mov.cliente_id == lote.cliente_id == cliente_id):
        mov.transferencia_cartao_id = lote.id
        mov.status = StatusMovimentacaoBancaria.conciliada
        lote.status = StatusTransferenciaCartao.conciliada
        db.commit()

    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/banco/lote/auto-match")
async def auto_match_lotes(
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    """Auto-concilia lotes pendentes com MovimentacaoBancaria de valor exato."""
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao/banco", status_code=303)

    _auto_match_lotes(db, cliente_id, usuario)
    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/banco/lote/{lote_id}/desvincular")
async def desvincular_lote(
    lote_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    lote = db.query(TransferenciaCartao).filter(TransferenciaCartao.id == lote_id).first()

    if lote and lote.cliente_id in [c.id for c in clientes]:
        mov = db.query(MovimentacaoBancaria).filter(
            MovimentacaoBancaria.transferencia_cartao_id == lote.id
        ).first()
        if mov:
            mov.transferencia_cartao_id = None
            mov.status = StatusMovimentacaoBancaria.importada
        lote.status = StatusTransferenciaCartao.pendente
        db.commit()

    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}#movimentacoes", status_code=303)


# ---------------------------------------------------------------------------
# Saídas bancárias × Contas a Pagar agendadas
# ---------------------------------------------------------------------------

@router.post("/conciliacao/banco/saida/{mov_id}/conciliar")
async def conciliar_saida_com_conta(
    mov_id: int,
    cliente_id: int = Form(...),
    conta_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_ok = [c.id for c in clientes]

    mov   = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()
    conta = db.query(ContaPagar).filter(ContaPagar.id == conta_id).first()

    if (mov and conta
            and mov.cliente_id in ids_ok
            and conta.cliente_id == mov.cliente_id == cliente_id):
        if _registrar_pagamento_conta(
            db, conta, mov.valor, mov.data_movimento, usuario.id,
            movimentacao_id=mov.id,
            observacao="Pagamento conciliado com movimentação bancária",
        ):
            mov.conta_pagar_id = conta.id
            mov.status = StatusMovimentacaoBancaria.conciliada
            db.commit()

    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)


@router.post("/conciliacao/banco/saida/{mov_id}/desvincular")
async def desvincular_saida(
    mov_id: int,
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    clientes = clientes_do_usuario(db, usuario)
    mov = db.query(MovimentacaoBancaria).filter(MovimentacaoBancaria.id == mov_id).first()

    if mov and mov.cliente_id in [c.id for c in clientes]:
        conta = db.query(ContaPagar).filter(ContaPagar.id == mov.conta_pagar_id).first()
        pagamento = db.query(PagamentoParcialContaPagar).filter(
            PagamentoParcialContaPagar.movimentacao_id == mov.id,
        ).first()
        if pagamento:
            db.delete(pagamento)
            db.flush()
        if conta:
            total_pago = _total_pago_conta(db, conta.id)
            conta.status = StatusContaPagar.pago if total_pago >= Decimal(str(conta.valor)) else StatusContaPagar.agendado
            conta.data_pagamento = (
                db.query(func.max(PagamentoParcialContaPagar.data_pagamento)).filter(
                    PagamentoParcialContaPagar.conta_pagar_id == conta.id,
                ).scalar()
                if conta.status == StatusContaPagar.pago else None
            )
        mov.conta_pagar_id = None
        mov.status = StatusMovimentacaoBancaria.importada
        db.commit()

    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}#movimentacoes", status_code=303)


@router.post("/conciliacao/banco/saida/auto-match")
async def auto_match_saidas(
    cliente_id: int = Form(...),
    db: Session = Depends(get_banco_db),
    usuario: Usuario = Depends(require_conciliacao),
):
    """Concilia em lote, por acao do usuario, saidas com contas de valor exato."""
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/conciliacao/banco", status_code=303)

    saidas = _carregar_saidas_banco(db, cliente_id)
    contas = _carregar_contas_agendadas(db, cliente_id)

    usadas = set()
    for mov in saidas:
        for conta in contas:
            if conta.id in usadas:
                continue
            saldo = Decimal(str(conta.valor)) - _total_pago_conta(db, conta.id)
            if saldo == mov.valor and _registrar_pagamento_conta(
                db, conta, mov.valor, mov.data_movimento, usuario.id,
                movimentacao_id=mov.id,
                observacao="Pagamento conciliado em lote",
            ):
                mov.conta_pagar_id = conta.id
                mov.status = StatusMovimentacaoBancaria.conciliada
                usadas.add(conta.id)
                break

    db.commit()
    return RedirectResponse(url=f"/conciliacao/banco?cliente_id={cliente_id}", status_code=303)
