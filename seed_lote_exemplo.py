"""Seed limpo para demonstrar conciliacao de lotes de cartao."""
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import text
from app.database import SessionLocal
from app.models import (
    Atendimento, ClienteBPO, CondicaoPagamento, FormaPagamento,
    MovimentacaoBancaria, PerfilUsuario, StatusConciliacao,
    StatusMovimentacaoBancaria, TransferenciaCartao, Usuario,
)
from app.services.conciliacao_service import gerar_transferencias_cartao

db = SessionLocal()
cliente    = db.query(ClienteBPO).filter(ClienteBPO.ativo == True).first()
cid        = cliente.id
func_user  = db.query(Usuario).filter(Usuario.perfil == PerfilUsuario.funcionario, Usuario.ativo == True).first()

DIA_ATEND   = date(2026, 5, 26)   # data fixa para nao colidir
DIA_CREDITO = date(2026, 5, 28)   # Stone credita 2 dias depois

# ── Limpa tudo desse dia para comecar do zero ───────────────────────────
db.execute(text("DELETE FROM movimentacoes_bancarias WHERE cliente_id=:c AND origem_arquivo='extrato-banco-exemplo.ofx'"), {"c": cid})
db.execute(text("""
    UPDATE movimentacoes_bancarias SET transferencia_cartao_id=NULL
    WHERE cliente_id=:c AND transferencia_cartao_id IN (
        SELECT id FROM transferencias_cartao WHERE cliente_id=:c AND data=:d)
"""), {"c": cid, "d": DIA_CREDITO})
db.execute(text("DELETE FROM transferencias_cartao WHERE cliente_id=:c AND data=:d"), {"c": cid, "d": DIA_CREDITO})
# Anula FK antes de deletar atendimentos
db.execute(text("""
    UPDATE movimentacoes_bancarias SET conciliada_com_atendimento_id=NULL
    WHERE conciliada_com_atendimento_id IN (
        SELECT id FROM atendimentos WHERE cliente_id=:c AND data_atendimento=:d AND forma_pagamento='cartao_credito')
"""), {"c": cid, "d": DIA_ATEND})
db.execute(text("DELETE FROM atendimentos WHERE cliente_id=:c AND data_atendimento=:d AND forma_pagamento='cartao_credito'"), {"c": cid, "d": DIA_ATEND})
db.commit()

# ── 4 atendimentos de cartao do dia 26/05 ──────────────────────────────
pagamentos = [
    ("Ana Clara",    "Visa",       1500.00, 1470.00),
    ("Joana Souza",  "Visa",       1650.00, 1617.00),
    ("Antonio Nunes","Mastercard", 1750.00, 1715.00),
    ("Jose Filho",   "Mastercard", 1980.00, 1940.40),
]

for nome, bandeira, valor, liquido in pagamentos:
    db.add(Atendimento(
        cliente_id=cid,
        data_atendimento=DIA_ATEND,
        nome_paciente=nome,
        especialidade="Ortopedia",
        tipo_servico="Consulta",
        descricao_servico=f"Consulta ortopedica - {nome}",
        valor_servico=Decimal(str(valor)),
        condicao_pagamento=CondicaoPagamento.avista,
        forma_pagamento=FormaPagamento.cartao_credito,
        parcela_numero=1, parcela_total=1,
        data_prevista_recebimento=DIA_CREDITO,
        bandeira_cartao=bandeira,
        status_conciliacao=StatusConciliacao.conciliado,
        data_credito=DIA_CREDITO,
        valor_liquido=Decimal(str(liquido)),
        lancado_por_id=func_user.id,
    ))
db.commit()

# ── Gera lotes ─────────────────────────────────────────────────────────
gerar_transferencias_cartao(db, cid)

lotes = db.query(TransferenciaCartao).filter(
    TransferenciaCartao.cliente_id == cid,
    TransferenciaCartao.data == DIA_CREDITO,
).order_by(TransferenciaCartao.bandeira).all()

# ── Cria creditos bancarios com valor EXATO dos lotes ──────────────────
for lote in lotes:
    db.add(MovimentacaoBancaria(
        cliente_id=cid, tipo="pix_ted",
        data_movimento=DIA_CREDITO,
        valor=lote.valor_liquido,
        descricao=f"Stone credito {lote.bandeira} {DIA_CREDITO.strftime('%d/%m')}",
        status=StatusMovimentacaoBancaria.importada,
        origem_arquivo="extrato-banco-exemplo.ofx",
    ))
db.commit()

movs = db.query(MovimentacaoBancaria).filter(
    MovimentacaoBancaria.cliente_id == cid,
    MovimentacaoBancaria.origem_arquivo == "extrato-banco-exemplo.ofx",
).all()

# ── Resultado ────────────────────────────────────────────────────────────
SEP = "=" * 65
print(SEP)
print(f"Cliente  : {cliente.nome} (id={cid})")
print(f"Atend.   : {DIA_ATEND.strftime('%d/%m/%Y')}   |   Credito Stone: {DIA_CREDITO.strftime('%d/%m/%Y')}")
print(SEP)

print("\nAtendimentos (cartao - ja conciliados):")
for nome, bandeira, valor, liquido in pagamentos:
    print(f"  {nome:<22} {bandeira:<12} bruto R$ {valor:7.2f}  liq. R$ {liquido:.2f}")

print(f"\nLotes gerados (TransferenciaCartao = conta a receber):")
for lote in lotes:
    print(f"  {lote.data.strftime('%d/%m/%Y')}  {lote.bandeira:<12}  "
          f"{lote.qtd_transacoes} tx  bruto R$ {float(lote.valor_bruto):.2f}  "
          f"liq. R$ {float(lote.valor_liquido):.2f}  [{lote.status.value}]")

print(f"\nCreditos bancarios (extrato banco):")
for m in movs:
    print(f"  {m.data_movimento.strftime('%d/%m/%Y')}  {(m.descricao or ''):<45}  R$ {float(m.valor):.2f}")

print(f"\nComparacao valor lote x credito banco:")
for lote in lotes:
    mov = next((m for m in movs if m.valor == lote.valor_liquido), None)
    status = "BATE ✓" if mov else "nao bate ✗"
    mov_val = float(mov.valor) if mov else 0.0
    print(f"  Lote {lote.bandeira:<12} R$ {float(lote.valor_liquido):.2f}  <->  Stone R$ {mov_val:.2f}  {status}")

print(f"\nAcesse:")
print(f"  http://localhost:8888/conciliacao/banco?cliente_id={cid}")
print(f"\nClique 'Auto-conciliar por valor exato' para vincular tudo automaticamente.")
db.close()
