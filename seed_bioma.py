#!/usr/bin/env python3
"""
Seed de dados BIOMA (cliente_id=9) — 3 ciclos de teste completos

Cobre o fluxo completo do sistema:
  Lançamentos → Conc. Cartão → Conc. Banco (lotes) → Fechamento
  Lançamentos → Conc. Banco (PIX/TED) → Fechamento
  Saídas banco → Conc. Banco (saídas) → Fechamento (despesas)

Ciclo 1 — 02-06/Jun  Visa + PIX/TED
Ciclo 2 — 09-13/Jun  Mastercard + PIX/TED
Ciclo 3 — 16-20/Jun  Elo + PIX/TED
"""

import sys, os
sys.path.insert(0, "/app")
os.environ.setdefault("DATABASE_URL", "postgresql://bpo:bpo@db:5432/bpo_financeiro")

from datetime import date, timedelta
from decimal import Decimal

from app.database import SessionLocal
from app.models import (
    Atendimento, MovimentacaoBancaria, VendaCartao,
    CondicaoPagamento, FormaPagamento, StatusConciliacao,
    StatusMovimentacaoBancaria, StatusVendaCartao,
)

CLIENTE_ID = 9  # BIOMA

TAXA = {"Visa": Decimal("2.73"), "Mastercard": Decimal("2.83"), "Elo": Decimal("3.34")}

def liq(bruto: Decimal, bandeira: str) -> Decimal:
    t = TAXA.get(bandeira, Decimal("0"))
    return (bruto * (1 - t / 100)).quantize(Decimal("0.01"))


def at_cartao(data, paciente, cpf, valor, dig, bandeira, medico, servico, data_prev):
    taxa = TAXA.get(bandeira, Decimal("0"))
    vl = liq(valor, bandeira)
    return Atendimento(
        cliente_id=CLIENTE_ID,
        data_atendimento=data,
        nome_paciente=paciente,
        cpf_paciente=cpf,
        medico=medico,
        descricao_servico=servico,
        valor_servico=valor,
        condicao_pagamento=CondicaoPagamento.avista,
        parcela_numero=1,
        parcela_total=1,
        forma_pagamento=FormaPagamento.cartao_credito,
        ultimos_digitos_cartao=dig,
        bandeira_cartao=bandeira,
        taxa_cartao=taxa,
        valor_liquido=vl,
        valor_clinica=vl,
        data_prevista_recebimento=data_prev,
        status_conciliacao=StatusConciliacao.pendente,
    )


def at_pix(data, paciente, cpf, valor, medico, servico, forma=FormaPagamento.pix):
    cond = CondicaoPagamento.pix if forma == FormaPagamento.pix else CondicaoPagamento.transferencia
    return Atendimento(
        cliente_id=CLIENTE_ID,
        data_atendimento=data,
        nome_paciente=paciente,
        cpf_paciente=cpf,
        medico=medico,
        descricao_servico=servico,
        valor_servico=valor,
        condicao_pagamento=cond,
        parcela_numero=1,
        parcela_total=1,
        forma_pagamento=forma,
        valor_liquido=valor,
        valor_clinica=valor,
        data_prevista_recebimento=data,
        status_conciliacao=StatusConciliacao.pendente,
    )


def venda(data_venda, data_pag, bandeira, valor_bruto, dig, descricao="Consulta"):
    taxa = TAXA.get(bandeira, Decimal("0"))
    vl = liq(valor_bruto, bandeira)
    return VendaCartao(
        cliente_id=CLIENTE_ID,
        data_venda=data_venda,
        data_pagamento=data_pag,
        bandeira=bandeira,
        ultimos_digitos=dig,
        valor_bruto=valor_bruto,
        taxa_percentual=taxa,
        valor_liquido=vl,
        parcelas=1,
        descricao=descricao,
        status=StatusVendaCartao.pendente,
    )


def mov_rec(data, valor, descricao, cpf_meio=None):
    return MovimentacaoBancaria(
        cliente_id=CLIENTE_ID,
        tipo="pix_ted",
        sentido="recebimento",
        data_movimento=data,
        valor=valor,
        descricao=descricao,
        cpf_digitos_meio=cpf_meio,
        status=StatusMovimentacaoBancaria.importada,
        origem_arquivo="seed_bioma",
    )


def mov_pag(data, valor, descricao):
    return MovimentacaoBancaria(
        cliente_id=CLIENTE_ID,
        tipo="pix_ted",
        sentido="pagamento",
        data_movimento=data,
        valor=valor,
        descricao=descricao,
        status=StatusMovimentacaoBancaria.importada,
        origem_arquivo="seed_bioma",
    )


def main():
    db = SessionLocal()
    try:
        registros = []

        # ──────────────────────────────────────────────────────────────
        # CICLO 1 — 02 a 06/Jun   Visa + PIX
        # ──────────────────────────────────────────────────────────────

        # Atendimentos cartão Visa (5 verdes + 1 amarelo)
        registros += [
            at_cartao(date(2026,6,2), "Ana Lima",      "033.111.222-01", Decimal("480.00"), "1234", "Visa",
                      "Dr. Paulo Assis",   "Consulta Ortopedia",   date(2026,7,2)),
            at_cartao(date(2026,6,2), "Bruno Melo",    "033.111.222-02", Decimal("320.00"), "5678", "Visa",
                      "Dra. Sandra Reis",  "Retorno Fisioterapia", date(2026,7,2)),
            at_cartao(date(2026,6,3), "Carla Nunes",   "033.111.222-03", Decimal("750.00"), "9012", "Visa",
                      "Dr. Paulo Assis",   "Consulta + Exame",     date(2026,7,3)),
            at_cartao(date(2026,6,4), "Diego Ramos",   "033.111.222-04", Decimal("195.00"), "3456", "Visa",
                      "Dra. Sandra Reis",  "Sessão Fisioterapia",  date(2026,7,4)),
            at_cartao(date(2026,6,5), "Elisa Torres",  "033.111.222-05", Decimal("560.00"), "7890", "Visa",
                      "Dr. Paulo Assis",   "Procedimento Estético",date(2026,7,5)),
            # este terá venda com valor R$3 diferente → amarelo (revisar)
            at_cartao(date(2026,6,6), "Fabio Costa",   "033.111.222-06", Decimal("890.00"), "2345", "Visa",
                      "Dr. Paulo Assis",   "Avaliação Inicial",    date(2026,7,6)),
        ]

        # Vendas cartão Visa — 5 exatas (verde) + 1 com diff R$3 (amarelo)
        registros += [
            venda(date(2026,6,2), date(2026,7,2),  "Visa", Decimal("480.00"), "1234"),
            venda(date(2026,6,2), date(2026,7,2),  "Visa", Decimal("320.00"), "5678"),
            venda(date(2026,6,3), date(2026,7,3),  "Visa", Decimal("750.00"), "9012"),
            venda(date(2026,6,4), date(2026,7,4),  "Visa", Decimal("195.00"), "3456"),
            venda(date(2026,6,5), date(2026,7,5),  "Visa", Decimal("560.00"), "7890"),
            venda(date(2026,6,6), date(2026,7,6),  "Visa", Decimal("887.00"), "2345"),  # diff R$3 → amarelo
        ]

        # Atendimentos PIX — 3 verdes (dd=0) + 1 amarelo (dd=3)
        registros += [
            at_pix(date(2026,6,2), "Gisele Matos",    "044.111.333-01", Decimal("350.00"), "Dr. Paulo Assis",  "Consulta PIX"),
            at_pix(date(2026,6,3), "Henrique Vaz",    "044.111.333-02", Decimal("1200.00"),"Dra. Sandra Reis", "Pacote Sessões"),
            at_pix(date(2026,6,4), "Inês Barbosa",    "044.111.333-03", Decimal("430.00"), "Dr. Paulo Assis",  "Consulta + Retorno"),
            at_pix(date(2026,6,5), "João Ferreira",   "044.111.333-04", Decimal("280.00"), "Dra. Sandra Reis", "Avaliação"),
        ]

        # MovimentacaoBancaria recebimento PIX — 3 no mesmo dia (verde) + 1 com 3 dias de diff (amarelo)
        registros += [
            mov_rec(date(2026,6,2), Decimal("350.00"),  "PIX REC GISELE MATOS",     "111333"),
            mov_rec(date(2026,6,3), Decimal("1200.00"), "PIX REC HENRIQUE VAZ",      "111333"),
            mov_rec(date(2026,6,4), Decimal("430.00"),  "PIX REC INES BARBOSA",      "111333"),
            mov_rec(date(2026,6,8), Decimal("280.00"),  "PIX REC JOAO FERREIRA"),     # 3 dias depois → amarelo
        ]

        # Saídas bancárias — compatíveis com contas agendadas existentes
        # Honorarios contabeis R$916 (venc 03/Jun) + Aluguel R$3636 (venc 06/Jun)
        registros += [
            mov_pag(date(2026,6,5),  Decimal("916.00"),  "TED PAG HONORARIOS CONTABEIS ESCRITORIO"),
            mov_pag(date(2026,6,7),  Decimal("3636.00"), "TED PAG ALUGUEL CONSULTORIO JUNHO"),
        ]

        # ──────────────────────────────────────────────────────────────
        # CICLO 2 — 09 a 13/Jun   Mastercard + PIX
        # ──────────────────────────────────────────────────────────────

        registros += [
            at_cartao(date(2026,6,9),  "Karol Pinto",   "055.222.444-01", Decimal("640.00"), "1111", "Mastercard",
                      "Dr. Paulo Assis",  "Consulta Ortopedia",    date(2026,7,9)),
            at_cartao(date(2026,6,10), "Lucas Rocha",   "055.222.444-02", Decimal("890.00"), "2222", "Mastercard",
                      "Dra. Sandra Reis", "Avaliação Completa",    date(2026,7,10)),
            at_cartao(date(2026,6,11), "Marina Alves",  "055.222.444-03", Decimal("225.00"), "3333", "Mastercard",
                      "Dr. Paulo Assis",  "Retorno",               date(2026,7,11)),
            # este terá venda com valor R$3 diferente → amarelo
            at_cartao(date(2026,6,12), "Nelson Cruz",   "055.222.444-04", Decimal("1150.00"), "4444", "Mastercard",
                      "Dra. Sandra Reis", "Procedimento Cirúrgico",date(2026,7,12)),
        ]

        registros += [
            venda(date(2026,6,9),  date(2026,7,9),  "Mastercard", Decimal("640.00"),  "1111"),
            venda(date(2026,6,10), date(2026,7,11), "Mastercard", Decimal("890.00"),  "2222"),  # dd=1 → ainda verde
            venda(date(2026,6,11), date(2026,7,11), "Mastercard", Decimal("225.00"),  "3333"),
            venda(date(2026,6,12), date(2026,7,12), "Mastercard", Decimal("1147.00"), "4444"),  # diff R$3 → amarelo
        ]

        registros += [
            at_pix(date(2026,6,9),  "Olga Sousa",    "066.222.555-01", Decimal("490.00"), "Dr. Paulo Assis",  "Consulta PIX"),
            at_pix(date(2026,6,10), "Pedro Lima",    "066.222.555-02", Decimal("780.00"), "Dra. Sandra Reis", "Pacote 5 Sessões"),
            at_pix(date(2026,6,11), "Quênia Dias",   "066.222.555-03", Decimal("360.00"), "Dr. Paulo Assis",  "Avaliação TED",
                   FormaPagamento.transferencia),
        ]

        registros += [
            mov_rec(date(2026,6,9),  Decimal("490.00"), "PIX REC OLGA SOUSA",    "222555"),
            mov_rec(date(2026,6,10), Decimal("780.00"), "PIX REC PEDRO LIMA",    "222555"),
            mov_rec(date(2026,6,11), Decimal("360.00"), "TED REC QUENIA DIAS",   "222555"),
        ]

        # ──────────────────────────────────────────────────────────────
        # CICLO 3 — 16 a 20/Jun   Elo + PIX
        # ──────────────────────────────────────────────────────────────

        registros += [
            at_cartao(date(2026,6,16), "Rafael Moura",  "077.333.666-01", Decimal("520.00"), "5555", "Elo",
                      "Dr. Paulo Assis",  "Consulta Ortopedia",     date(2026,7,16)),
            at_cartao(date(2026,6,17), "Sara Neves",    "077.333.666-02", Decimal("930.00"), "6666", "Elo",
                      "Dra. Sandra Reis", "Procedimento Estético",  date(2026,7,17)),
            at_cartao(date(2026,6,18), "Tiago Mendes",  "077.333.666-03", Decimal("310.00"), "7777", "Elo",
                      "Dr. Paulo Assis",  "Retorno Pós-Op",         date(2026,7,18)),
            at_cartao(date(2026,6,19), "Ursula Faria",  "077.333.666-04", Decimal("650.00"), "8888", "Elo",
                      "Dra. Sandra Reis", "Avaliação Inicial",      date(2026,7,19)),
        ]

        registros += [
            venda(date(2026,6,16), date(2026,7,16), "Elo", Decimal("520.00"), "5555"),
            venda(date(2026,6,17), date(2026,7,17), "Elo", Decimal("930.00"), "6666"),
            venda(date(2026,6,18), date(2026,7,18), "Elo", Decimal("310.00"), "7777"),
            venda(date(2026,6,19), date(2026,7,19), "Elo", Decimal("650.00"), "8888"),
            # venda sem nenhum atendimento correspondente → sem sugestão (cinza, para testar busca manual)
            venda(date(2026,6,20), date(2026,7,20), "Elo", Decimal("420.00"), "9999", "Consulta sem lançamento"),
        ]

        registros += [
            at_pix(date(2026,6,16), "Vera Castro",    "088.333.777-01", Decimal("660.00"),  "Dr. Paulo Assis",  "Consulta PIX"),
            at_pix(date(2026,6,17), "Wilson Gomes",   "088.333.777-02", Decimal("1100.00"), "Dra. Sandra Reis", "Pacote Premium"),
            at_pix(date(2026,6,18), "Ximena Rocha",   "088.333.777-03", Decimal("450.00"),  "Dr. Paulo Assis",  "Avaliação TED",
                   FormaPagamento.transferencia),
        ]

        registros += [
            mov_rec(date(2026,6,16), Decimal("660.00"),  "PIX REC VERA CASTRO",   "333777"),
            mov_rec(date(2026,6,17), Decimal("1100.00"), "PIX REC WILSON GOMES",  "333777"),
            mov_rec(date(2026,6,18), Decimal("450.00"),  "TED REC XIMENA ROCHA",  "333777"),
        ]

        # ──────────────────────────────────────────────────────────────
        # Inserção
        # ──────────────────────────────────────────────────────────────
        for obj in registros:
            db.add(obj)

        db.commit()

        ats  = sum(1 for o in registros if isinstance(o, Atendimento))
        vcs  = sum(1 for o in registros if isinstance(o, VendaCartao))
        movs = sum(1 for o in registros if isinstance(o, MovimentacaoBancaria))

        print(f"\n✅ Seed BIOMA concluído!")
        print(f"   {ats}  atendimentos lançados")
        print(f"   {vcs}  vendas cartão (maquininha)")
        print(f"   {movs} movimentações bancárias (extrato)")
        print()
        print("Resumo por ciclo:")
        print("  Ciclo 1 (02-06/Jun): 6 Visa + 4 PIX | 6 vendas Visa | 4 mov PIX + 2 saídas")
        print("  Ciclo 2 (09-13/Jun): 4 Mastercard + 3 PIX | 4 vendas Master | 3 mov PIX")
        print("  Ciclo 3 (16-20/Jun): 4 Elo + 3 PIX | 5 vendas Elo (1 sem match) | 3 mov PIX")
        print()
        print("Fluxo de teste:")
        print("  1. Lançamentos → confirme os atendimentos criados (filtrar Jun/2026)")
        print("  2. Conciliação Cartão → concilie verdes automaticamente (Conciliar Todos Prontos)")
        print("     → Fechar Lote → redireciona para Conciliação Banco")
        print("  3. Conciliação Banco → aba Lotes: concilie o lote com o crédito bancário")
        print("     → aba PIX/TED: concilie os atendimentos PIX")
        print("     → aba Saídas: concilie os débitos com as contas agendadas")
        print("  4. Fechamento Mensal → selecione BIOMA + Jun/2026 → veja o resultado")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
