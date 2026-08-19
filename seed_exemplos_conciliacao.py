"""
Seed: exemplos completos para testar a Conciliação de Cartão.

Cria Atendimentos (lançamentos) com forma_pagamento=cartao_credito
que correspondem às VendaCartao pendentes já existentes.

Cenários cobertos por cliente:
  PRESTI (id=1) — 6 vendas pendentes:
    • 4 sugestao_pronta (verde)   — valor exato + dígitos + data próxima
    • 1 revisar (amarelo)         — diferença de R$2,00 no valor
    • 1 sem sugestão              — para testar busca manual / criar lançamento

  REF DOR (id=2) — 3 vendas pendentes:
    • 2 sugestao_pronta (verde)
    • 1 revisar (amarelo)         — diferença de R$2,00

Execute:
  docker exec bpo-financeiro-web-1 python seed_exemplos_conciliacao.py
"""

import sys
sys.path.insert(0, ".")

from datetime import date, timedelta
from decimal import Decimal

from app.database import SessionLocal
from app.models import (
    Atendimento,
    CondicaoPagamento,
    FormaPagamento,
    StatusConciliacao,
    StatusVendaCartao,
    VendaCartao,
)

db = SessionLocal()

hoje = date.today()

# ─────────────────────────────────────────────────────────────────────────────
# Utilitários
# ─────────────────────────────────────────────────────────────────────────────

def liquido(bruto: Decimal, taxa_pct: Decimal) -> Decimal:
    return (bruto * (1 - taxa_pct / 100)).quantize(Decimal("0.01"))


TAXAS = {"Visa": Decimal("2.50"), "Mastercard": Decimal("2.99"), "Elo": Decimal("3.20")}


def add_at(cliente_id, data_atend, nome, bandeira, digitos, valor, data_prev,
           taxa=None, obs=None):
    t = taxa or TAXAS.get(bandeira, Decimal("2.99"))
    vl = liquido(valor, t)
    at = Atendimento(
        cliente_id=cliente_id,
        data_atendimento=data_atend,
        nome_paciente=nome,
        medico="Dr. Exemplo",
        especialidade="Clinica Geral",
        tipo_servico="Consulta",
        valor_servico=valor,
        condicao_pagamento=CondicaoPagamento.avista,
        forma_pagamento=FormaPagamento.cartao_credito,
        ultimos_digitos_cartao=digitos,
        bandeira_cartao=bandeira,
        taxa_cartao=t,
        valor_liquido=vl,
        data_prevista_recebimento=data_prev,
        status_conciliacao=StatusConciliacao.pendente,
        observacao=obs,
    )
    db.add(at)
    db.flush()
    return at


# ─────────────────────────────────────────────────────────────────────────────
# Carregar vendas pendentes existentes
# ─────────────────────────────────────────────────────────────────────────────

vendas_pendentes = (
    db.query(VendaCartao)
    .filter(VendaCartao.status == StatusVendaCartao.pendente)
    .order_by(VendaCartao.cliente_id, VendaCartao.id)
    .all()
)

print(f"Vendas pendentes encontradas: {len(vendas_pendentes)}")
for v in vendas_pendentes:
    print(f"  [{v.id}] cliente={v.cliente_id} {v.data_pagamento} "
          f"{v.bandeira} *{v.ultimos_digitos} R${v.valor_bruto}")

# ─────────────────────────────────────────────────────────────────────────────
# PRESTI (id=1)  — vendas pendentes: IDs 1,2,3,4,6,7
# ─────────────────────────────────────────────────────────────────────────────
print("\n→ Criando atendimentos para PRESTI (id=1)...")

presti = [v for v in vendas_pendentes if v.cliente_id == 1]

for v in presti:
    # Verifica se já existe atendimento vinculado ou pendente com mesmo dígito+valor
    ja_existe = db.query(Atendimento).filter(
        Atendimento.cliente_id == 1,
        Atendimento.ultimos_digitos_cartao == v.ultimos_digitos,
        Atendimento.valor_servico == v.valor_bruto,
        Atendimento.bandeira_cartao == v.bandeira,
        Atendimento.status_conciliacao == StatusConciliacao.pendente,
        Atendimento.forma_pagamento == FormaPagamento.cartao_credito,
    ).first()
    if ja_existe:
        print(f"  Já existe atendimento para venda {v.id} — pulando")
        continue

    if v.id == presti[-1].id:
        # Última venda do PRESTI: SEM atendimento correspondente (testa busca manual)
        print(f"  Venda {v.id} ({v.bandeira} *{v.ultimos_digitos} R${v.valor_bruto})"
              f" → sem atendimento (busca manual)")
        continue

    # Alterna entre sugestão exata e uma com pequena diferença de R$2
    if v.id == presti[2].id:
        # Terceira venda: valor diferente (R$2 a menos = cenário "revisar")
        valor_at = v.valor_bruto - Decimal("2.00")
        obs = "Valor diverge R$2,00 do extrato — use o botão Revisar"
    else:
        valor_at = v.valor_bruto
        obs = None

    at = add_at(
        cliente_id=1,
        data_atend=v.data_venda,
        nome=f"Paciente {v.nome_portador or v.ultimos_digitos}",
        bandeira=v.bandeira,
        digitos=v.ultimos_digitos,
        valor=valor_at,
        data_prev=v.data_pagamento,
        obs=obs,
    )
    print(f"  Venda {v.id} ({v.bandeira} *{v.ultimos_digitos} R${v.valor_bruto})"
          f" → Atendimento #{at.id} R${at.valor_servico}"
          f" {'[REVISAR]' if obs else '[PRONTO]'}")

# ─────────────────────────────────────────────────────────────────────────────
# REF DOR (id=2)  — vendas pendentes: IDs 12,13,14
# ─────────────────────────────────────────────────────────────────────────────
print("\n→ Criando atendimentos para REF DOR (id=2)...")

refdor = [v for v in vendas_pendentes if v.cliente_id == 2]

for i, v in enumerate(refdor):
    ja_existe = db.query(Atendimento).filter(
        Atendimento.cliente_id == 2,
        Atendimento.ultimos_digitos_cartao == v.ultimos_digitos,
        Atendimento.valor_servico == v.valor_bruto,
        Atendimento.bandeira_cartao == v.bandeira,
        Atendimento.status_conciliacao == StatusConciliacao.pendente,
        Atendimento.forma_pagamento == FormaPagamento.cartao_credito,
    ).first()
    if ja_existe:
        print(f"  Já existe atendimento para venda {v.id} — pulando")
        continue

    if i == 1:
        # Segunda venda REF DOR: valor diferente (R$2 a mais = cenário "revisar")
        valor_at = v.valor_bruto + Decimal("2.00")
        obs = "Valor diverge R$2,00 do extrato — use o botão Revisar"
    else:
        valor_at = v.valor_bruto
        obs = None

    at = add_at(
        cliente_id=2,
        data_atend=v.data_venda,
        nome=f"Paciente {v.nome_portador or v.ultimos_digitos}",
        bandeira=v.bandeira,
        digitos=v.ultimos_digitos,
        valor=valor_at,
        data_prev=v.data_pagamento,
        obs=obs,
    )
    print(f"  Venda {v.id} ({v.bandeira} *{v.ultimos_digitos} R${v.valor_bruto})"
          f" → Atendimento #{at.id} R${at.valor_servico}"
          f" {'[REVISAR]' if obs else '[PRONTO]'}")

# ─────────────────────────────────────────────────────────────────────────────
db.commit()
db.close()

print()
print("✅ Seed de exemplos concluído!")
print()
print("Acesse:")
print("  PRESTI  → http://localhost:8888/conciliacao?cliente_id=1")
print("  REF DOR → http://localhost:8888/conciliacao?cliente_id=2")
print()
print("Fluxo de teste:")
print("  1. Clique nos botões VERDES (Pronto) para conciliar automaticamente")
print("  2. Clique no AMARELO (Revisar) → inspecione a diferença → concilie")
print("  3. Para a venda sem sugestão: busque manualmente ou crie lançamento")
print("  4. Após todas conciliadas → 'Fechar lote'")
print("  5. Vá para Conciliação Banco → veja os lotes aguardando")
