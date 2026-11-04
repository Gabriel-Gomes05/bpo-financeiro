"""Histórico de alterações das secretárias (Auditoria → Histórico de alterações).

Funcionamento:
- `iniciar` guarda em `db.info` quem é a secretária, o cliente dela, o IP e o request.
- Enquanto esse contexto existir, o listener `after_flush` grava uma linha por campo
  criado/alterado/removido, na MESMA transação da operação: se o histórico não for
  gravado, a alteração também não é.
- O listener `before_flush` barra, no backend, exclusões e gravações em outro cliente,
  e impede qualquer UPDATE/DELETE do próprio histórico pela aplicação.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.errors import erro
from app.models import (
    Atendimento, AtendimentoCentroCustoRateio, AuditEvent, CentroCusto, HistoricoAlteracao,
    LogAuditoria, PlanoConta, Usuario,
)

CHAVE_CONTEXTO = "historico_secretaria"

ACOES = {
    "criacao": "Criação",
    "edicao": "Edição",
    "remocao": "Remoção",
    "tentativa_bloqueada": "Tentativa bloqueada",
}
ENTIDADES = {"lancamento": "Lançamento", "rota": "Acesso"}

_NAO_AUDITADOS = (HistoricoAlteracao, LogAuditoria, AuditEvent, Usuario)
_CAMPOS_TECNICOS = {
    "id", "public_id", "created_at", "updated_at", "deleted_at", "created_by", "updated_by",
    "criado_em", "lancado_por_id", "cliente_id", "centro_custo_id",
}
ROTULOS_LANCAMENTO = {
    "data_atendimento": "Data do atendimento",
    "nome_paciente": "Paciente",
    "cpf_paciente": "CPF",
    "medico": "Centro de custo",
    "especialidade": "Especialidade",
    "tipo_servico": "Tipo de serviço",
    "descricao_servico": "Descrição",
    "valor_servico": "Valor",
    "condicao_pagamento": "Condição de pagamento",
    "parcela_numero": "Parcela",
    "parcela_total": "Total de parcelas",
    "data_prevista_recebimento": "Previsão de recebimento",
    "forma_pagamento": "Forma de pagamento",
    "nome_pagador_pix": "Pagador do Pix",
    "ultimos_digitos_cartao": "Dígitos do cartão",
    "bandeira_cartao": "Bandeira",
    "taxa_cartao": "Taxa do cartão",
    "valor_liquido": "Valor líquido",
    "data_credito": "Data de crédito",
    "banco_recebimento": "Banco de recebimento",
    "status_conciliacao": "Status",
    "arquivado_conciliacao_banco": "Arquivado na conciliação",
    "valor_clinica": "Valor da clínica",
    "percentual_medico": "% do centro de custo",
    "valor_medico": "Valor do centro de custo",
    "data_pagamento_medico": "Pagamento do centro de custo",
    "observacao": "Observação",
    "plano_conta_id": "Plano de contas",
}
_PERCENTUAIS = {"taxa_cartao", "percentual_medico", "percentual"}
_NOMES_POR_ID = {"plano_conta_id": PlanoConta}


# --------------------------------------------------------------------- contexto

def iniciar(db: Session, request, usuario, cliente) -> dict:
    """Ativa o histórico para a sessão da requisição da secretária."""
    from app.security import client_ip

    contexto = {
        "operacao_id": uuid.uuid4(),
        "usuario_id": usuario.id,
        "usuario_nome": usuario.nome,
        "cliente_id": cliente.id,
        "cliente_nome": cliente.nome,
        "ip": client_ip(request) if request is not None else None,
        "request_id": _uuid(getattr(getattr(request, "state", None), "request_id", None)),
        "criados": set(),  # (entidade, id) criados nesta operação: complementos seguem como criação
    }
    db.info[CHAVE_CONTEXTO] = contexto
    return contexto


def registrar_tentativa(db: Session, contexto: dict, metodo: str, caminho: str, exclusao: bool) -> None:
    """Grava (e confirma) a tentativa de acessar algo bloqueado, antes de negar o acesso."""
    numeros = re.findall(r"/(\d+)(?=/|$)", caminho)
    db.execute(HistoricoAlteracao.__table__.insert(), [_linha(
        contexto, "tentativa_bloqueada", _modulo_da_rota(caminho), "rota",
        int(numeros[0]) if numeros else None,
        "Exclusão" if exclusao else "Acesso a área restrita", None, f"{metodo} {caminho}",
    )])
    db.commit()


def _modulo_da_rota(caminho: str) -> str:
    partes = [p for p in caminho.split("/") if p]
    return (partes[0] if partes else "inicio")[:50]


def _uuid(valor):
    if valor is None or isinstance(valor, uuid.UUID):
        return valor
    try:
        return uuid.UUID(str(valor))
    except ValueError:
        return None


def _linha(contexto, acao, modulo, entidade, entidade_id, campo, anterior, novo) -> dict:
    return {
        "operacao_id": contexto["operacao_id"],
        "usuario_id": contexto["usuario_id"],
        "usuario_nome": contexto["usuario_nome"],
        "cliente_id": contexto["cliente_id"],
        "cliente_nome": contexto["cliente_nome"],
        "acao": acao,
        "modulo": modulo,
        "entidade": entidade,
        "entidade_id": entidade_id,
        "campo": campo[:80] if campo else None,
        "valor_anterior": anterior,
        "valor_novo": novo,
        "ip": contexto["ip"],
        "request_id": contexto["request_id"],
    }


# --------------------------------------------------------------------- formatação

def _brl(valor) -> str:
    return f"{Decimal(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar(campo: str, valor, db: Session | None = None) -> str | None:
    if valor is None or valor == "":
        return None
    if campo in _NOMES_POR_ID and db is not None:
        with db.no_autoflush:
            registro = db.get(_NOMES_POR_ID[campo], valor)
        return f"{registro.nome} (#{valor})" if registro else f"#{valor}"
    if isinstance(valor, Enum):
        return str(valor.value).replace("_", " ")
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, (Decimal, float)):
        if campo in _PERCENTUAIS:
            return f"{_brl(valor)}%"
        if campo.startswith("valor"):
            return f"R$ {_brl(valor)}"
        return _brl(valor)
    return str(valor)[:1000]


# --------------------------------------------------------------------- listeners

def _tem_coluna(obj, nome: str) -> bool:
    return nome in inspect(obj).mapper.columns


def _historico_do_campo(obj, chave):
    hist = inspect(obj).attrs[chave].history
    if not hist.has_changes():
        return None
    anterior = hist.deleted[0] if hist.deleted else None
    novo = hist.added[0] if hist.added else None
    return anterior, novo


@event.listens_for(Session, "before_flush")
def _proteger(session: Session, _flush_context, _instances) -> None:
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, HistoricoAlteracao):
            raise erro("FLIC-GER-403", "O histórico de alterações não pode ser alterado nem excluído.")

    contexto = session.info.get(CHAVE_CONTEXTO)
    if not contexto:
        return
    for obj in session.deleted:
        if not isinstance(obj, _NAO_AUDITADOS) and _tem_coluna(obj, "cliente_id"):
            raise erro("FLIC-AUT-009")
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, _NAO_AUDITADOS):
            continue
        if _tem_coluna(obj, "deleted_at") and obj in session.dirty:
            mudanca = _historico_do_campo(obj, "deleted_at")
            if mudanca and mudanca[1] is not None:
                raise erro("FLIC-AUT-009")
        if _tem_coluna(obj, "cliente_id") and obj.cliente_id is not None and obj.cliente_id != contexto["cliente_id"]:
            raise erro("FLIC-AUT-006")


@event.listens_for(Session, "after_flush")
def _registrar(session: Session, _flush_context) -> None:
    contexto = session.info.get(CHAVE_CONTEXTO)
    if not contexto:
        return
    criados = contexto["criados"]
    for obj in session.new:
        if isinstance(obj, Atendimento):
            criados.add(("lancamento", obj.id))
    linhas: list[dict] = []
    for acao, objetos in (("criacao", session.new), ("edicao", session.dirty), ("remocao", session.deleted)):
        for obj in objetos:
            if isinstance(obj, _NAO_AUDITADOS):
                continue
            if isinstance(obj, AtendimentoCentroCustoRateio):
                linhas += _linhas_rateio(session, contexto, obj, acao)
            else:
                linhas += _linhas_registro(session, contexto, obj, acao)
    if linhas:
        session.connection().execute(HistoricoAlteracao.__table__.insert(), linhas)


def _linhas_registro(session, contexto, obj, acao) -> list[dict]:
    estado = inspect(obj)
    if isinstance(obj, Atendimento):
        entidade, modulo, rotulos = "lancamento", "contas_receber", ROTULOS_LANCAMENTO
    else:
        entidade, modulo, rotulos = obj.__tablename__, "contas_receber", {}
    linhas = []
    for coluna in estado.mapper.column_attrs:
        chave = coluna.key
        if chave in _CAMPOS_TECNICOS or (rotulos and chave not in rotulos):
            continue
        if acao == "edicao":
            mudanca = _historico_do_campo(obj, chave)
            if not mudanca:
                continue
            anterior, novo = mudanca
        elif acao == "criacao":
            anterior, novo = None, getattr(obj, chave)
        else:
            anterior, novo = getattr(obj, chave), None
        texto_anterior, texto_novo = formatar(chave, anterior, session), formatar(chave, novo, session)
        if texto_anterior == texto_novo:
            continue
        linhas.append(_linha(contexto, "criacao" if (entidade, obj.id) in contexto["criados"] else acao,
                             modulo, entidade, obj.id, rotulos.get(chave, chave), texto_anterior, texto_novo))
    return linhas


def _linhas_rateio(session, contexto, rateio, acao) -> list[dict]:
    with session.no_autoflush:
        centro = session.get(CentroCusto, rateio.centro_custo_id)
    campo = f"Rateio · {centro.nome if centro else '#' + str(rateio.centro_custo_id)}"
    texto = f"{formatar('percentual', rateio.percentual)} ({formatar('valor', rateio.valor)})"
    if acao == "edicao":
        mudancas = [_historico_do_campo(rateio, c) for c in ("percentual", "valor")]
        if not any(mudancas):
            return []
        p_ant = (mudancas[0] or (rateio.percentual,))[0]
        v_ant = (mudancas[1] or (rateio.valor,))[0]
        anterior = f"{formatar('percentual', p_ant)} ({formatar('valor', v_ant)})"
        novo = texto
    elif acao == "criacao":
        anterior, novo = None, texto
    else:
        anterior, novo = texto, None
    if anterior == novo:
        return []
    pai_novo = ("lancamento", rateio.atendimento_id) in contexto["criados"]
    return [_linha(contexto, "criacao" if pai_novo else "edicao", "contas_receber", "lancamento",
                   rateio.atendimento_id, campo, anterior, novo)]
