"""
Seed: dados de teste para Conciliação Cartão + Conciliação Banco.

Cria para PRESTI (id=1) e REF DOR (id=2):
  - VendaCartao pendentes  → para testar a tela de conciliação cartão
  - VendaCartao já fechadas em TransferenciaCartao (lotes)
  - MovimentacaoBancaria créditos do banco que batem com os lotes
    → para testar o match automático na conciliação banco
"""

import sys
sys.path.insert(0, ".")

from datetime import date, timedelta
from decimal import Decimal

from app.database import SessionLocal, criar_tabelas, migrar_schema
from app.models import (
    MovimentacaoBancaria,
    StatusMovimentacaoBancaria,
    StatusTransferenciaCartao,
    StatusVendaCartao,
    TransferenciaCartao,
    VendaCartao,
)

criar_tabelas()
migrar_schema()
db = SessionLocal()

hoje = date.today()

# ─────────────────────────────────────────────────────────────────────────────
# Dados fictícios reutilizáveis
# ─────────────────────────────────────────────────────────────────────────────

CLIENTES = [
    {"id": 1, "nome": "PRESTI"},
    {"id": 2, "nome": "REF DOR"},
]

PORTADORES = [
    ("JOAO CARLOS SILVA",    "4521", "Visa"),
    ("MARIA FERNANDA SOUZA", "7834", "Visa"),
    ("CARLOS EDUARDO LIMA",  "1290", "Mastercard"),
    ("ANA PAULA COSTA",      "3302", "Mastercard"),
    ("PEDRO HENRIQUE SANTOS","3388", "Elo"),
    ("LUCIA APARECIDA FERREIRA","9901","Visa"),
    ("PAULO ROBERTO MENDES", "1122", "Mastercard"),
    ("FERNANDA ROCHA ALVES", "5544", "Visa"),
    ("ROBERTO GOMES JUNIOR", "8877", "Elo"),
    ("CLAUDIA MELO PIRES",   "6631", "Mastercard"),
]

TAXAS = {"Visa": Decimal("2.50"), "Mastercard": Decimal("2.99"), "Elo": Decimal("3.20")}

def liquido(bruto: Decimal, bandeira: str) -> Decimal:
    taxa = TAXAS.get(bandeira, Decimal("2.99"))
    return (bruto * (1 - taxa / 100)).quantize(Decimal("0.01"))

def add_venda(cliente_id, data_venda, data_pagamento, portador, digitos, bandeira,
              bruto, status=StatusVendaCartao.pendente, lote_id=None, origem="seed_teste.csv"):
    vl = liquido(bruto, bandeira)
    taxa = TAXAS.get(bandeira, Decimal("2.99"))
    v = VendaCartao(
        cliente_id=cliente_id,
        data_venda=data_venda,
        data_pagamento=data_pagamento,
        bandeira=bandeira,
        ultimos_digitos=digitos,
        nome_portador=portador,
        valor_bruto=bruto,
        taxa_percentual=taxa,
        valor_liquido=vl,
        parcelas=1,
        status=status,
        lote_id=lote_id,
        origem_arquivo=origem,
    )
    db.add(v)
    db.flush()
    return v

def add_lote(cliente_id, data, bandeira, vendas):
    vb = sum(v.valor_bruto for v in vendas)
    vl = sum(v.valor_liquido for v in vendas)
    lote = TransferenciaCartao(
        cliente_id=cliente_id,
        data=data,
        bandeira=bandeira,
        valor_bruto=vb,
        taxa_total=vb - vl,
        valor_liquido=vl,
        qtd_transacoes=len(vendas),
        status=StatusTransferenciaCartao.pendente,
    )
    db.add(lote)
    db.flush()
    for v in vendas:
        v.status  = StatusVendaCartao.fechado
        v.lote_id = lote.id
    return lote

def add_credito_banco(cliente_id, data, valor, descricao, lote_id=None):
    mov = MovimentacaoBancaria(
        cliente_id=cliente_id,
        tipo="pix_ted",
        sentido="recebimento",
        data_movimento=data,
        valor=valor,
        descricao=descricao,
        status=StatusMovimentacaoBancaria.importada,
        transferencia_cartao_id=lote_id,
    )
    if lote_id:
        mov.status = StatusMovimentacaoBancaria.conciliada
    db.add(mov)
    db.flush()
    return mov


# ─────────────────────────────────────────────────────────────────────────────
# PRESTI (id=1)
# ─────────────────────────────────────────────────────────────────────────────
print("→ Criando dados para PRESTI...")

D = hoje - timedelta(days=1)   # ontem

# Vendas PENDENTES (aparecerão na tela de conciliação cartão para fechar)
p1 = add_venda(1, D, D + timedelta(1), *PORTADORES[0], Decimal("350.00"))
p2 = add_venda(1, D, D + timedelta(1), *PORTADORES[1], Decimal("280.00"))
p3 = add_venda(1, D, D + timedelta(1), *PORTADORES[2], Decimal("500.00"))
p4 = add_venda(1, D, D + timedelta(1), *PORTADORES[3], Decimal("420.00"))
p5 = add_venda(1, D, D + timedelta(1), *PORTADORES[4], Decimal("180.00"))
# segundo dia pendente
D2 = hoje
p6 = add_venda(1, D2, D2 + timedelta(1), *PORTADORES[5], Decimal("650.00"))
p7 = add_venda(1, D2, D2 + timedelta(1), *PORTADORES[6], Decimal("310.00"))

db.flush()

# Lote JÁ FECHADO — aguardando banco (3 dias atrás, Visa)
D3 = hoje - timedelta(days=4)
f1 = add_venda(1, D3, D3 + timedelta(1), *PORTADORES[7], Decimal("290.00"),
               status=StatusVendaCartao.fechado)
f2 = add_venda(1, D3, D3 + timedelta(1), *PORTADORES[0], Decimal("410.00"),
               status=StatusVendaCartao.fechado)
db.flush()
lote_presti_visa = add_lote(1, D3 + timedelta(1), "Visa", [f1, f2])
# lote Visa: bruto=700, liq ≈ 682.50

# Lote JÁ FECHADO — Mastercard — com crédito bancário disponível para match
D4 = hoje - timedelta(days=4)
f3 = add_venda(1, D4, D4 + timedelta(1), *PORTADORES[2], Decimal("600.00"),
               status=StatusVendaCartao.fechado)
f4 = add_venda(1, D4, D4 + timedelta(1), *PORTADORES[3], Decimal("320.00"),
               status=StatusVendaCartao.fechado)
db.flush()
lote_presti_master = add_lote(1, D4 + timedelta(1), "Mastercard", [f3, f4])
# Mastercard bruto=920, liq ≈ 892.49

# Crédito bancário que bate com o lote Mastercard (match automático disponível)
add_credito_banco(1, D4 + timedelta(2), lote_presti_master.valor_liquido,
                  "STONE PAGAMENTOS LTDA - REF CARTAO 28/05")

# Crédito bancário que bate exatamente com o lote Visa (match automático)
add_credito_banco(1, D3 + timedelta(2), lote_presti_visa.valor_liquido,
                  "STONE PAGAMENTOS LTDA - REF CARTAO 24/05")

# Crédito bancário "quase certo" — diferença pequena (simula taxa de antecipação)
add_credito_banco(1, hoje - timedelta(1),
                  lote_presti_master.valor_liquido - Decimal("1.50"),
                  "STONE ANTECIPACAO - REF CARTAO")

print(f"   Lote Visa    #{lote_presti_visa.id}:   R$ {lote_presti_visa.valor_liquido}")
print(f"   Lote Master  #{lote_presti_master.id}: R$ {lote_presti_master.valor_liquido}")
print(f"   Vendas pendentes: {len([p1,p2,p3,p4,p5,p6,p7])}")


# ─────────────────────────────────────────────────────────────────────────────
# REF DOR (id=2)
# ─────────────────────────────────────────────────────────────────────────────
print("→ Criando dados para REF DOR...")

D5 = hoje - timedelta(days=2)

# Vendas pendentes
r1 = add_venda(2, D5, D5 + timedelta(1), *PORTADORES[8], Decimal("480.00"))
r2 = add_venda(2, D5, D5 + timedelta(1), *PORTADORES[9], Decimal("240.00"))
r3 = add_venda(2, D5, D5 + timedelta(1), *PORTADORES[1], Decimal("390.00"))

# Lote fechado Visa — sem crédito bancário (extrato não foi importado ainda)
D6 = hoje - timedelta(days=6)
r4 = add_venda(2, D6, D6 + timedelta(1), *PORTADORES[4], Decimal("550.00"),
               status=StatusVendaCartao.fechado)
r5 = add_venda(2, D6, D6 + timedelta(1), *PORTADORES[5], Decimal("330.00"),
               status=StatusVendaCartao.fechado)
r6 = add_venda(2, D6, D6 + timedelta(1), *PORTADORES[6], Decimal("275.00"),
               status=StatusVendaCartao.fechado)
db.flush()
lote_refdor_visa = add_lote(2, D6 + timedelta(1), "Visa", [r4, r5, r6])

# Lote fechado Elo — com crédito bancário disponível
D7 = hoje - timedelta(days=5)
r7 = add_venda(2, D7, D7 + timedelta(1), *PORTADORES[8], Decimal("720.00"),
               status=StatusVendaCartao.fechado)
r8 = add_venda(2, D7, D7 + timedelta(1), *PORTADORES[0], Decimal("190.00"),
               status=StatusVendaCartao.fechado)
db.flush()
lote_refdor_elo = add_lote(2, D7 + timedelta(1), "Elo", [r7, r8])

# Crédito bancário exato para o lote Elo
add_credito_banco(2, D7 + timedelta(2), lote_refdor_elo.valor_liquido,
                  "CIELO PAGAMENTOS - CREDITO LOJA")

print(f"   Lote Visa    #{lote_refdor_visa.id}:   R$ {lote_refdor_visa.valor_liquido}")
print(f"   Lote Elo     #{lote_refdor_elo.id}:   R$ {lote_refdor_elo.valor_liquido}")
print(f"   Vendas pendentes: {len([r1,r2,r3])}")


# ─────────────────────────────────────────────────────────────────────────────
db.commit()
db.close()

print()
print("✅ Seed concluído!")
print()
print("PRESTI   → http://localhost:8888/conciliacao?cliente_id=1")
print("PRESTI   → http://localhost:8888/conciliacao/banco?cliente_id=1")
print("REF DOR  → http://localhost:8888/conciliacao?cliente_id=2")
print("REF DOR  → http://localhost:8888/conciliacao/banco?cliente_id=2")
