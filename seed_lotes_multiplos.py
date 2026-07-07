"""Seed com 6 lotes de cartao em dias/bandeiras variados para testes."""
from datetime import date
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
cliente   = db.query(ClienteBPO).filter(ClienteBPO.ativo == True).first()
cid       = cliente.id
func_user = db.query(Usuario).filter(Usuario.perfil == PerfilUsuario.funcionario, Usuario.ativo == True).first()

# 6 lotes = 6 combinacoes (data_atendimento, data_credito, bandeira, pacientes)
LOTES = [
    {
        "dia_atend":   date(2026, 5, 20),
        "dia_credito": date(2026, 5, 22),
        "pacientes": [
            ("Maria Oliveira",  "Visa",       980.00,  960.40),
            ("Carlos Lima",     "Visa",      1200.00, 1176.00),
            ("Fernanda Costa",  "Visa",       750.00,  735.00),
        ],
    },
    {
        "dia_atend":   date(2026, 5, 20),
        "dia_credito": date(2026, 5, 22),
        "pacientes": [
            ("Ricardo Sousa",   "Mastercard", 1100.00, 1078.00),
            ("Paula Mendes",    "Mastercard",  890.00,  872.20),
        ],
    },
    {
        "dia_atend":   date(2026, 5, 22),
        "dia_credito": date(2026, 5, 24),
        "pacientes": [
            ("Bruno Alves",     "Visa",      1350.00, 1323.00),
            ("Tatiane Rocha",   "Visa",      1050.00, 1029.00),
            ("Diego Farias",    "Visa",       800.00,  784.00),
            ("Aline Souza",     "Visa",       600.00,  588.00),
        ],
    },
    {
        "dia_atend":   date(2026, 5, 22),
        "dia_credito": date(2026, 5, 24),
        "pacientes": [
            ("Mariana Teles",   "Mastercard", 1600.00, 1568.00),
            ("Lucas Borges",    "Mastercard",  950.00,  931.00),
        ],
    },
    {
        "dia_atend":   date(2026, 5, 24),
        "dia_credito": date(2026, 5, 26),
        "pacientes": [
            ("Patrícia Neves",  "Visa",      2200.00, 2156.00),
            ("Rodrigo Pinto",   "Visa",       780.00,  764.40),
        ],
    },
    {
        "dia_atend":   date(2026, 5, 26),
        "dia_credito": date(2026, 5, 28),
        "pacientes": [
            ("Ana Clara",       "Visa",      1500.00, 1470.00),
            ("Joana Souza",     "Visa",      1650.00, 1617.00),
            ("Antonio Nunes",   "Mastercard",1750.00, 1715.00),
            ("Jose Filho",      "Mastercard",1980.00, 1940.40),
        ],
    },
]

# ── Coleta todas as datas para limpar ──────────────────────────────────────
todas_datas_atend  = list({l["dia_atend"]  for l in LOTES})
todas_datas_cred   = list({l["dia_credito"] for l in LOTES})

print("Limpando dados anteriores...")
for d in todas_datas_cred:
    db.execute(text("""
        UPDATE movimentacoes_bancarias SET transferencia_cartao_id=NULL
        WHERE cliente_id=:c AND transferencia_cartao_id IN (
            SELECT id FROM transferencias_cartao WHERE cliente_id=:c AND data=:d)
    """), {"c": cid, "d": d})
    db.execute(text(
        "DELETE FROM transferencias_cartao WHERE cliente_id=:c AND data=:d"
    ), {"c": cid, "d": d})
    db.execute(text(
        "DELETE FROM movimentacoes_bancarias WHERE cliente_id=:c AND data_movimento=:d AND origem_arquivo='seed-multiplos.ofx'"
    ), {"c": cid, "d": d})

for d in todas_datas_atend:
    db.execute(text("""
        UPDATE movimentacoes_bancarias SET conciliada_com_atendimento_id=NULL
        WHERE conciliada_com_atendimento_id IN (
            SELECT id FROM atendimentos WHERE cliente_id=:c AND data_atendimento=:d AND forma_pagamento='cartao_credito')
    """), {"c": cid, "d": d})
    db.execute(text(
        "DELETE FROM atendimentos WHERE cliente_id=:c AND data_atendimento=:d AND forma_pagamento='cartao_credito'"
    ), {"c": cid, "d": d})

db.commit()

# ── Cria atendimentos ──────────────────────────────────────────────────────
print("Criando atendimentos...")
for lote in LOTES:
    for nome, bandeira, valor, liquido in lote["pacientes"]:
        db.add(Atendimento(
            cliente_id=cid,
            data_atendimento=lote["dia_atend"],
            nome_paciente=nome,
            especialidade="Ortopedia",
            tipo_servico="Consulta",
            descricao_servico=f"Consulta - {nome}",
            valor_servico=Decimal(str(valor)),
            condicao_pagamento=CondicaoPagamento.avista,
            forma_pagamento=FormaPagamento.cartao_credito,
            parcela_numero=1, parcela_total=1,
            data_prevista_recebimento=lote["dia_credito"],
            bandeira_cartao=bandeira,
            status_conciliacao=StatusConciliacao.conciliado,
            data_credito=lote["dia_credito"],
            valor_liquido=Decimal(str(liquido)),
            lancado_por_id=func_user.id,
        ))
db.commit()

# ── Gera lotes (TransferenciaCartao) ──────────────────────────────────────
print("Gerando lotes...")
gerar_transferencias_cartao(db, cid)

lotes_db = db.query(TransferenciaCartao).filter(
    TransferenciaCartao.cliente_id == cid,
    TransferenciaCartao.data.in_(todas_datas_cred),
).order_by(TransferenciaCartao.data, TransferenciaCartao.bandeira).all()

# ── Cria créditos bancários com valor EXATO ────────────────────────────────
print("Criando créditos bancários...")
for lote in lotes_db:
    db.add(MovimentacaoBancaria(
        cliente_id=cid, tipo="pix_ted",
        data_movimento=lote.data,
        valor=lote.valor_liquido,
        descricao=f"Stone crédito {lote.bandeira} {lote.data.strftime('%d/%m')}",
        status=StatusMovimentacaoBancaria.importada,
        origem_arquivo="seed-multiplos.ofx",
    ))
db.commit()

movs_db = db.query(MovimentacaoBancaria).filter(
    MovimentacaoBancaria.cliente_id == cid,
    MovimentacaoBancaria.origem_arquivo == "seed-multiplos.ofx",
).order_by(MovimentacaoBancaria.data_movimento, MovimentacaoBancaria.descricao).all()

# ── Relatório ──────────────────────────────────────────────────────────────
SEP = "=" * 72
print(f"\n{SEP}")
print(f"Cliente : {cliente.nome} (id={cid})")
print(f"Lotes   : {len(lotes_db)}   |   Créditos banco: {len(movs_db)}")
print(SEP)

print(f"\n{'Data Cred.':<12} {'Bandeira':<12} {'Tx':>3}  {'Bruto':>10}  {'Líquido':>10}  Status")
print("-" * 72)
for lote in lotes_db:
    print(f"  {lote.data.strftime('%d/%m/%Y')}  {lote.bandeira:<12} {lote.qtd_transacoes:>3}  "
          f"R$ {float(lote.valor_bruto):>8.2f}  R$ {float(lote.valor_liquido):>8.2f}  [{lote.status.value}]")

print(f"\n{'Data':<12} {'Descrição':<45}  {'Valor':>10}")
print("-" * 72)
for m in movs_db:
    print(f"  {m.data_movimento.strftime('%d/%m/%Y')}  {(m.descricao or ''):<43}  R$ {float(m.valor):>8.2f}")

print(f"\nComparação lote × crédito:")
print("-" * 72)
for lote in lotes_db:
    mov = next((m for m in movs_db
                if m.valor == lote.valor_liquido and m.data_movimento == lote.data), None)
    status = "BATE ✓" if mov else "NÃO BATE ✗"
    mov_val = float(mov.valor) if mov else 0.0
    print(f"  {lote.data.strftime('%d/%m')} {lote.bandeira:<12} R$ {float(lote.valor_liquido):>9.2f}  <->  "
          f"Stone R$ {mov_val:>9.2f}  {status}")

print(f"\nAcesse:")
print(f"  http://localhost:8888/conciliacao/banco?cliente_id={cid}")
print(f"\nClique 'Auto-conciliar por valor exato' para vincular todos os lotes.\n")
db.close()
