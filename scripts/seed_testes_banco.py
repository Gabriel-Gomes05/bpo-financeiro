"""Adiciona cenários fictícios em cliente separado, sem limpar registros existentes.

Execução: Get-Content -Raw -Encoding UTF8 scripts/seed_testes_banco.py |
          docker compose exec -T web python -
"""
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.database import SessionLocal
from app.models import (
    Atendimento, CentroCusto, ClienteBPO, CondicaoPagamento, ContaBancaria,
    ContaPagar, FormaPagamento, MovimentacaoBancaria, PagamentoParcialContaPagar,
    PerfilUsuario, PlanoConta, StatusConciliacao, StatusContaPagar,
    StatusMovimentacaoBancaria, StatusTransferenciaCartao, StatusVendaCartao,
    TipoContaBancaria, TransferenciaCartao, Usuario, VendaCartao,
)
from app.services.contas_bancarias_service import registrar_transferencia


def popular():
    hoje = date.today()
    nome = "DEMO - Testes Banco e Conciliacao"
    with SessionLocal() as db:
        cliente = db.query(ClienteBPO).filter(ClienteBPO.nome == nome).first()
        if cliente:
            print(json.dumps({"cliente_id": cliente.id, "cliente": nome, "status": "Dados de teste ja existem; nada foi duplicado."}))
            return
        admin = db.query(Usuario).filter(Usuario.email == "admin.local@example.com", Usuario.ativo.is_(True)).one()
        assert admin.perfil == PerfilUsuario.coordenador
        cliente = ClienteBPO(nome=nome, razao_social="Empresa ficticia para testes locais", ativo=True, tem_maquininha=True)
        db.add(cliente)
        db.flush()
        centros = [CentroCusto(cliente_id=cliente.id, nome=nome_cc, ativo=True) for nome_cc in ["Administrativo DEMO", "Atendimento DEMO"]]
        db.add_all(centros)
        contas = [ContaBancaria(cliente_id=cliente.id, nome=nome_conta, banco=banco, agencia="0001", conta=numero,
            tipo=TipoContaBancaria.bancaria, ativo=True, saldo_atual=Decimal(saldo),
            saldo_data_referencia=datetime.combine(hoje-timedelta(days=10), datetime.min.time()), saldo_atualizado_em=datetime.now())
            for nome_conta, banco, numero, saldo in [
                ("DEMO Principal", "Banco Azul DEMO", "10001-1", "20000"),
                ("DEMO Operacional", "Banco Verde DEMO", "20002-2", "8000"),
                ("DEMO Reserva", "Banco Violeta DEMO", "30003-3", "12000"),
            ]]
        db.add_all(contas)
        db.flush()
        planos = {}
        for tipo in ["receita", "despesa"]:
            plano = PlanoConta(cliente_id=cliente.id, tipo=tipo, nome=f"{tipo.title()} DEMO", grupo="Testes", chave=f"demo_banco_{cliente.id}_{tipo}", ativo=True)
            db.add(plano)
            planos[tipo] = plano
        db.flush()

        def movimento(conta, sentido, valor, descricao, status=StatusMovimentacaoBancaria.importada, **kwargs):
            mov = MovimentacaoBancaria(cliente_id=cliente.id, conta_bancaria_id=conta.id,
                tipo="pix_ted", sentido=sentido, data_movimento=hoje, valor=Decimal(valor),
                descricao="DEMO - " + descricao, origem_arquivo="DEMO testes locais", status=status, **kwargs)
            db.add(mov)
            db.flush()
            return mov

        receitas = []
        for i in range(8):
            valor = Decimal(250 + i*100)
            at = Atendimento(cliente_id=cliente.id, data_atendimento=hoje, data_prevista_recebimento=hoje,
                nome_paciente=f"Paciente Ficticio DEMO {i+1}", descricao_servico=f"DEMO Recebimento {i+1} - " + ("conciliado para editar" if i < 3 else "pendente para conciliar"),
                valor_servico=valor, valor_liquido=valor, valor_clinica=valor,
                condicao_pagamento=CondicaoPagamento.avista, forma_pagamento=FormaPagamento.pix,
                centro_custo_id=centros[1].id, plano_conta_id=planos["receita"].id, lancado_por_id=admin.id,
                status_conciliacao=StatusConciliacao.conciliado if i < 3 else StatusConciliacao.pendente,
                data_credito=hoje if i < 3 else None)
            db.add(at)
            db.flush()
            receitas.append(at)
            if i < 7:
                movimento(contas[i % 2], "recebimento", valor, at.descricao_servico,
                    status=StatusMovimentacaoBancaria.conciliada if i < 3 else StatusMovimentacaoBancaria.importada,
                    conciliada_com_atendimento_id=at.id if i < 3 else None)

        despesas = []
        for i, (descricao, valor) in enumerate([
            ("Aluguel pago", "1800"), ("Internet paga", "190"), ("Material com pagamento parcial", "900"),
            ("Energia agendada", "420"), ("Limpeza agendada", "650"), ("Software agendado", "280"),
            ("Fornecedor pendente", "770"), ("Manutencao pendente", "390"),
        ]):
            conta = ContaPagar(cliente_id=cliente.id, descricao="DEMO - " + descricao, fornecedor="Fornecedor Ficticio DEMO",
                valor=Decimal(valor), vencimento=hoje, data_competencia=hoje, forma_pagamento=FormaPagamento.pix,
                status=StatusContaPagar.pago if i < 2 else StatusContaPagar.agendado if i < 6 else StatusContaPagar.pendente,
                data_pagamento=hoje if i < 2 else None, plano_conta_id=planos["despesa"].id, lancado_por_id=admin.id)
            db.add(conta)
            db.flush()
            despesas.append(conta)
            if i < 6:
                pago = Decimal("300") if i == 2 else conta.valor
                mov = movimento(contas[i % 2], "pagamento", pago, descricao,
                    status=StatusMovimentacaoBancaria.conciliada if i < 3 else StatusMovimentacaoBancaria.importada,
                    conta_pagar_id=conta.id if i < 3 else None)
                if i < 3:
                    db.add(PagamentoParcialContaPagar(conta_pagar_id=conta.id, movimentacao_id=mov.id,
                        valor=pago, data_pagamento=hoje, criado_por_id=admin.id, observacao="DEMO pagamento para testes"))
        # Uma série semanal permite testar exclusão e alteração dos próximos registros.
        serie = []
        for i in range(4):
            conta = ContaPagar(cliente_id=cliente.id, descricao=f"DEMO Recorrencia semanal {i+1}/4", valor=Decimal("150"),
                vencimento=hoje+timedelta(days=i*7), data_competencia=hoje, recorrencia_intervalo="semanal",
                status=StatusContaPagar.pendente, plano_conta_id=planos["despesa"].id, lancado_por_id=admin.id)
            db.add(conta)
            serie.append(conta)
        db.flush()
        for conta in serie:
            conta.recorrencia_grupo_id = serie[0].id

        # Lote de cartão com duas vendas e crédito bancário conciliado.
        lote = TransferenciaCartao(cliente_id=cliente.id, data=hoje, bandeira="Visa", valor_bruto=Decimal("1000"),
            valor_liquido=Decimal("970"), taxa_total=Decimal("30"), qtd_transacoes=2, status=StatusTransferenciaCartao.conciliada)
        db.add(lote)
        db.flush()
        for i in range(2):
            at = Atendimento(cliente_id=cliente.id, data_atendimento=hoje, nome_paciente=f"Paciente Cartao DEMO {i+1}",
                descricao_servico="DEMO Cartao em lote conciliado", valor_servico=Decimal("500"), valor_liquido=Decimal("485"),
                valor_clinica=Decimal("485"), forma_pagamento=FormaPagamento.cartao_credito, condicao_pagamento=CondicaoPagamento.avista,
                bandeira_cartao="Visa", taxa_cartao=Decimal("3"), data_credito=hoje, status_conciliacao=StatusConciliacao.conciliado,
                centro_custo_id=centros[1].id, plano_conta_id=planos["receita"].id, lancado_por_id=admin.id)
            db.add(at)
            db.flush()
            db.add(VendaCartao(cliente_id=cliente.id, data_venda=hoje, data_pagamento=hoje, bandeira="Visa",
                valor_bruto=Decimal("500"), valor_liquido=Decimal("485"), taxa_percentual=Decimal("3"),
                atendimento_id=at.id, lote_id=lote.id, status=StatusVendaCartao.fechado))
        movimento(contas[0], "recebimento", "970", "Credito lote Visa", StatusMovimentacaoBancaria.conciliada, transferencia_cartao_id=lote.id)
        movimento(contas[1], "recebimento", "123.45", "Credito sem correspondencia para testar busca")
        movimento(contas[0], "pagamento", "87.65", "Debito sem correspondencia para testar cadastro")
        registrar_transferencia(db, cliente.id, contas[0].id, contas[1].id, Decimal("1200"), hoje, "DEMO reforco operacional")
        registrar_transferencia(db, cliente.id, contas[1].id, contas[2].id, Decimal("500"), hoje, "DEMO envio para reserva")
        db.commit()
        print(json.dumps({"cliente_id": cliente.id, "cliente": nome, "data": hoje.isoformat(),
            "contas_bancarias": len(contas), "recebimentos": 10, "contas_pagar": 12,
            "movimentos": db.query(MovimentacaoBancaria).filter_by(cliente_id=cliente.id).count(),
            "transferencias_internas": 2, "lotes_cartao": 1}, ensure_ascii=True))


if __name__ == "__main__":
    popular()
