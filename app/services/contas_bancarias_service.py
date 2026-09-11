"""Cadastro e registro de transferências internas, sem gerar resultado operacional."""
from datetime import datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.models import ContaBancaria, MovimentacaoBancaria, StatusMovimentacaoBancaria, TipoContaBancaria


def conta_do_cliente(db, cliente_id, conta_id, bloquear=False):
    query = db.query(ContaBancaria).filter(
        ContaBancaria.id == conta_id, ContaBancaria.cliente_id == cliente_id,
        ContaBancaria.ativo.is_(True), ContaBancaria.tipo == TipoContaBancaria.bancaria,
    )
    conta = (query.with_for_update() if bloquear else query).first()
    if not conta:
        raise HTTPException(404, "Conta bancária indisponível para este cliente.")
    return conta


def registrar_transferencia(db, cliente_id, origem_id, destino_id, valor, data, descricao="", token=None):
    if origem_id == destino_id:
        raise HTTPException(400, "Escolha contas diferentes para origem e destino.")
    if not valor.is_finite() or not Decimal("0") < valor <= Decimal("9999999999.99") or valor != valor.quantize(Decimal("0.01")):
        raise HTTPException(400, "Informe um valor positivo com até duas casas decimais.")
    # Ordem fixa evita deadlocks em transferências simultâneas entre as mesmas contas.
    contas = {id_: conta_do_cliente(db, cliente_id, id_, True) for id_ in sorted([origem_id, destino_id])}
    try:
        grupo = str(UUID(token)) if token else str(uuid4())
    except ValueError:
        raise HTTPException(400, "Identificação da transferência inválida.")
    existente = db.query(MovimentacaoBancaria).filter(
        MovimentacaoBancaria.cliente_id == cliente_id,
        MovimentacaoBancaria.identificador_externo == f"transferencia:{grupo}:pagamento",
    ).first()
    if existente:
        return grupo
    for conta_id, sentido in [(origem_id, "pagamento"), (destino_id, "recebimento")]:
        db.add(MovimentacaoBancaria(
            cliente_id=cliente_id, conta_bancaria_id=conta_id, tipo="transf_interna",
            sentido=sentido, data_movimento=data, valor=valor, origem_manual=True,
            identificador_externo=f"transferencia:{grupo}:{sentido}",
            descricao=f"Transferência interna: {contas[origem_id].nome} → {contas[destino_id].nome}" + (f" · {descricao.strip()}" if descricao.strip() else ""),
            status=StatusMovimentacaoBancaria.conciliada,
        ))
    db.flush()
    return grupo


def saldo_previsto(conta, movimentos):
    if conta.saldo_atual is None:
        return None
    referencia = conta.saldo_data_referencia or datetime.min
    if referencia.tzinfo:
        referencia = referencia.replace(tzinfo=None)
    ajuste = Decimal("0")
    for mov in movimentos:
        if mov.tipo != "transf_interna" or not mov.origem_manual:
            continue
        momento = datetime.combine(mov.data_movimento, time.max)
        if momento > referencia:
            ajuste += mov.valor if mov.sentido == "recebimento" else -mov.valor
    return conta.saldo_atual + ajuste
