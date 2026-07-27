"""
Script de seed com dados de exemplo.
Execute da raiz do projeto:
    docker-compose exec web python seed.py
Ou fora do Docker (com banco acessivel):
    python seed.py
"""

import os
import sys
from datetime import date, timedelta

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(__file__))

from app.auth import hash_senha
from app.database import SessionLocal
from app.models import (
    Atendimento,
    ClienteBPO,
    CondicaoPagamento,
    ContaPagar,
    ContaRecorrente,
    DiaSemana,
    DivergenciaConciliacao,
    FechamentoDiario,
    FormaPagamento,
    MaquininhaCliente,
    MovimentacaoBancaria,
    OrcamentoValor,
    PerfilUsuario,
    StatusConciliacao,
    StatusContaPagar,
    StatusMovimentacaoBancaria,
    StatusTransferenciaCartao,
    TaxaCartaoCliente,
    TarefaRotina,
    TipoContaPagar,
    TransferenciaCartao,
    Usuario,
)
from app.constants import GRUPOS_DRE

db = SessionLocal()

SEED_ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "")
SEED_USER_PASSWORD = os.getenv("SEED_USER_PASSWORD", "")
if not SEED_ADMIN_PASSWORD or not SEED_USER_PASSWORD:
    raise RuntimeError(
        "Defina SEED_ADMIN_PASSWORD e SEED_USER_PASSWORD antes de executar o seed."
    )


def limpar():
    """Remove dados existentes para recomeçar do zero."""
    db.execute(text("""
        TRUNCATE TABLE
            divergencias_conciliacao,
            movimentacoes_bancarias,
            atendimentos,
            fechamentos_diarios,
            tarefas_rotina,
            contas_pagar,
            clientes_bpo,
            usuarios
        RESTART IDENTITY CASCADE
    """))
    db.commit()
    print("Banco limpo.")


def criar_usuarios():
    usuarios = [
        Usuario(
            nome="Renato C.",
            email="renato@bpo.com",
            senha_hash=hash_senha(SEED_ADMIN_PASSWORD),
            perfil=PerfilUsuario.coordenador,
            ativo=True,
        ),
        Usuario(
            nome="Ana S.",
            email="ana@bpo.com",
            senha_hash=hash_senha(SEED_USER_PASSWORD),
            perfil=PerfilUsuario.funcionario,
            ativo=True,
        ),
        Usuario(
            nome="Marcos R.",
            email="marcos@bpo.com",
            senha_hash=hash_senha(SEED_USER_PASSWORD),
            perfil=PerfilUsuario.funcionario,
            ativo=True,
        ),
        Usuario(
            nome="Julia L.",
            email="julia@bpo.com",
            senha_hash=hash_senha(SEED_USER_PASSWORD),
            perfil=PerfilUsuario.funcionario,
            ativo=True,
        ),
    ]
    db.add_all(usuarios)
    db.commit()
    print(f"{len(usuarios)} usuarios criados.")
    return {u.email: u for u in usuarios}


def criar_clientes(usuarios):
    ana = usuarios["ana@bpo.com"]
    marcos = usuarios["marcos@bpo.com"]
    julia = usuarios["julia@bpo.com"]

    clientes_data = [
        dict(nome="PRESTI", especialidade="Ortopedia", funcionario_id=ana.id),
        dict(nome="REF DOR", especialidade="Dor Cronica", funcionario_id=ana.id),
        dict(nome="RHEJB", especialidade="Reumatologia", funcionario_id=ana.id),
        dict(nome="MRA STONE", especialidade="Urologia", funcionario_id=marcos.id),
        dict(nome="AAA", especialidade="Clinica Geral", funcionario_id=marcos.id),
        dict(nome="i9Med", especialidade="Medicina do Trabalho", funcionario_id=marcos.id),
        dict(nome="FRATELLI", especialidade="Cirurgia Geral", funcionario_id=julia.id),
        dict(nome="NEO LIFE", especialidade="Oncologia", funcionario_id=julia.id),
        dict(nome="BIOMA", especialidade="Nutricao", funcionario_id=julia.id),
    ]

    clientes = []
    bancos = ["Sicredi", "Itau", "Santander", "Bradesco", "Banco do Brasil", "Caixa", "BTG", "Inter", "Stone"]
    redes = ["Stone", "Cielo", "Rede", "PagSeguro", "Getnet", "Ton", "Stone", "Cielo", "Rede"]
    for idx, data in enumerate(clientes_data):
        data.update({
            "razao_social": f"{data['nome']} Servicos Medicos Ltda",
            "cnpj": f"12.345.67{idx:02d}/0001-{idx:02d}",
            "regime_tributario": "Simples Nacional" if idx % 2 == 0 else "Lucro Presumido",
            "tem_maquininha": idx % 3 != 1,
            "antecipa": idx % 4 == 0,
            "banco": bancos[idx],
            "agencia": f"{1000 + idx}",
            "conta": f"{23450 + idx}-0",
            "rede_maquininha": redes[idx],
        })
        cliente = ClienteBPO(**data, ativo=True)
        db.add(cliente)
        clientes.append(cliente)
    db.commit()
    print(f"{len(clientes)} clientes criados.")
    return clientes


ROTINAS_PADRAO = [
    ("Salvar extratos", "09:00", DiaSemana.seg),
    ("Salvar extratos", "09:00", DiaSemana.ter),
    ("Salvar extratos", "09:00", DiaSemana.qua),
    ("Salvar extratos", "09:00", DiaSemana.qui),
    ("Salvar extratos", "09:00", DiaSemana.sex),
    ("Validar saidas", "09:50", DiaSemana.seg),
    ("Validar saidas", "09:50", DiaSemana.ter),
    ("Validar saidas", "09:50", DiaSemana.qua),
    ("Validar saidas", "09:50", DiaSemana.qui),
    ("Validar saidas", "09:50", DiaSemana.sex),
    ("Atualizar extratos no Drive", "10:00", DiaSemana.seg),
    ("Atualizar extratos no Drive", "10:00", DiaSemana.ter),
    ("Atualizar extratos no Drive", "10:00", DiaSemana.qua),
    ("Atualizar extratos no Drive", "10:00", DiaSemana.qui),
    ("Atualizar extratos no Drive", "10:00", DiaSemana.sex),
    ("Responder e-mail/zap", "10:10", DiaSemana.seg),
    ("Responder e-mail/zap", "10:10", DiaSemana.ter),
    ("Responder e-mail/zap", "10:10", DiaSemana.qua),
    ("Responder e-mail/zap", "10:10", DiaSemana.qui),
    ("Responder e-mail/zap", "10:10", DiaSemana.sex),
    ("Cobrar boletos", "10:40", DiaSemana.seg),
    ("Cobrar boletos", "10:40", DiaSemana.ter),
    ("Cobrar boletos", "10:40", DiaSemana.qua),
    ("Cobrar boletos", "10:40", DiaSemana.qui),
    ("Cobrar boletos", "10:40", DiaSemana.sex),
    ("Lancar contas a pagar", "11:00", DiaSemana.seg),
    ("Lancar contas a pagar", "11:00", DiaSemana.ter),
    ("Lancar contas a pagar", "11:00", DiaSemana.qua),
    ("Lancar contas a pagar", "11:00", DiaSemana.qui),
    ("Lancar contas a pagar", "11:00", DiaSemana.sex),
    ("Atualizar despesas", "17:00", DiaSemana.seg),
    ("Atualizar despesas", "17:00", DiaSemana.ter),
    ("Atualizar despesas", "17:00", DiaSemana.qua),
    ("Atualizar despesas", "17:00", DiaSemana.qui),
    ("Atualizar despesas", "17:00", DiaSemana.sex),
    ("Atualizar receitas/inadimplentes", "18:00", DiaSemana.seg),
    ("Atualizar receitas/inadimplentes", "18:00", DiaSemana.ter),
    ("Atualizar receitas/inadimplentes", "18:00", DiaSemana.qua),
    ("Atualizar receitas/inadimplentes", "18:00", DiaSemana.qui),
    ("Atualizar receitas/inadimplentes", "18:00", DiaSemana.sex),
]

DIA_SEMANA_MAP = {0: "seg", 1: "ter", 2: "qua", 3: "qui", 4: "sex"}


def criar_rotinas_hoje(clientes):
    hoje = date.today()
    dia_semana_num = hoje.weekday()

    if dia_semana_num > 4:
        print("Hoje e fim de semana; sem rotinas geradas.")
        return

    dia_semana_str = DIA_SEMANA_MAP[dia_semana_num]
    rotinas_do_dia = [r for r in ROTINAS_PADRAO if r[2].value == dia_semana_str]

    tarefas = []
    for cliente in clientes:
        for descricao, horario, dia in rotinas_do_dia:
            tarefas.append(
                TarefaRotina(
                    cliente_id=cliente.id,
                    funcionario_id=cliente.funcionario_id,
                    data=hoje,
                    descricao=descricao,
                    horario_previsto=horario,
                    dia_semana=dia,
                    concluida=False,
                )
            )

    db.add_all(tarefas)
    db.commit()
    print(f"{len(tarefas)} tarefas de rotina criadas para hoje.")


def criar_contas_pagar_exemplo(clientes):
    hoje = date.today()
    exemplos = []

    pacotes = [
        ("Aluguel do consultorio", "Imobiliaria XYZ", TipoContaPagar.fixa, 3500.00, 5, StatusContaPagar.agendado, "df_aluguel"),
        ("Conta de energia", "Cemig", TipoContaPagar.fixa, 420.00, -2, StatusContaPagar.pendente, "df_energia"),
        ("Material de escritorio", "Papelaria Central", TipoContaPagar.pontual, 180.00, 15, StatusContaPagar.pendente, "da_outros"),
        ("Honorarios contabeis", "Contabilidade Prime", TipoContaPagar.fixa, 780.00, 2, StatusContaPagar.agendado, "da_contabil"),
        ("Software de gestao", "ClinicSoft", TipoContaPagar.fixa, 299.90, 8, StatusContaPagar.aguardando_aprovacao, "da_software"),
        ("Material medico", "MedSupply", TipoContaPagar.pontual, 1260.00, -6, StatusContaPagar.pago, "cv_material"),
    ]

    for idx, cliente in enumerate(clientes):
        for descricao, fornecedor, tipo, valor, offset, status, categoria in pacotes:
            exemplos.append(
                ContaPagar(
                    cliente_id=cliente.id,
                    descricao=descricao,
                    fornecedor=fornecedor,
                    tipo=tipo,
                    valor=valor + (idx * 17),
                    vencimento=hoje + timedelta(days=offset),
                    data_pagamento=hoje - timedelta(days=4) if status == StatusContaPagar.pago else None,
                    status=status,
                    categoria_dre=categoria,
                    observacao="Dado de teste gerado pelo seed.",
                )
            )

        exemplos.append(
            ContaPagar(
                cliente_id=cliente.id,
                descricao="Campanha de marketing local",
                fornecedor="Agencia Alto Fluxo",
                tipo=TipoContaPagar.pontual,
                valor=950.00 + (idx * 23),
                vencimento=hoje + timedelta(days=20),
                status=StatusContaPagar.cancelado if idx % 3 == 0 else StatusContaPagar.pendente,
                categoria_dre="da_marketing",
                observacao="Cenario para testar status cancelado/pendente.",
            )
        )

    cliente = next((c for c in clientes if c.nome == "PRESTI"), clientes[0])
    exemplos.extend([
        ContaPagar(
            cliente_id=cliente.id,
            descricao="Repasse laboratorio imagem",
            fornecedor="Lab Diagnostico",
            tipo=TipoContaPagar.pontual,
            valor=840.00,
            vencimento=hoje - timedelta(days=1),
            status=StatusContaPagar.agendado,
            categoria_dre="cv_terceiros",
            observacao="Saida bancaria com match exato no extrato.",
        ),
        ContaPagar(
            cliente_id=cliente.id,
            descricao="Folha assistentes",
            fornecedor="Equipe interna",
            tipo=TipoContaPagar.fixa,
            valor=2250.00,
            vencimento=hoje,
            status=StatusContaPagar.agendado,
            categoria_dre="df_folha",
            observacao="Saida bancaria para testar divergencia de valor.",
        ),
    ])

    db.add_all(exemplos)
    db.commit()
    print(f"{len(exemplos)} contas a pagar de exemplo criadas.")


def criar_cadastros_financeiros_exemplo(clientes):
    hoje = date.today()
    recorrentes = []
    orcamentos = []
    maquininhas = []

    for idx, cliente in enumerate(clientes):
        recorrentes.extend([
            ContaRecorrente(
                cliente_id=cliente.id,
                descricao="Aluguel recorrente",
                fornecedor="Imobiliaria XYZ",
                valor=3500.00 + idx * 40,
                dia_vencimento=5,
                dias_antecedencia=3,
                email_destino="financeiro@bpo.com",
                ativo=True,
            ),
            ContaRecorrente(
                cliente_id=cliente.id,
                descricao="Internet e telefone",
                fornecedor="Operadora Fibra",
                valor=189.90 + idx * 5,
                dia_vencimento=12,
                dias_antecedencia=2,
                email_destino="financeiro@bpo.com",
                ativo=True,
            ),
        ])

        maquininha = MaquininhaCliente(
            cliente_id=cliente.id,
            rede=cliente.rede_maquininha or "Stone",
            apelido=f"{cliente.rede_maquininha or 'Stone'} principal",
            antecipa=cliente.antecipa,
            ativa=cliente.tem_maquininha,
        )
        db.add(maquininha)
        db.flush()
        maquininhas.append(maquininha)

        for bandeira, taxa in [("Visa", 2.49), ("Mastercard", 2.59), ("Elo", 3.10)]:
            db.add(TaxaCartaoCliente(
                cliente_id=cliente.id,
                maquininha_id=maquininha.id,
                bandeira=bandeira,
                faixa_parcelamento="avista_credito",
                taxa_percentual=taxa + (idx * 0.03),
                ativo=True,
            ))

        for grupo in GRUPOS_DRE:
            for cat in grupo["categorias"]:
                base = 18000 if grupo["tipo"] == "receita" else 2500
                orcamentos.append(OrcamentoValor(
                    cliente_id=cliente.id,
                    categoria_key=cat["key"],
                    mes=hoje.month,
                    ano=hoje.year,
                    valor_orcado=base + (idx * 350),
                ))

    db.add_all(recorrentes)
    db.add_all(orcamentos)
    db.commit()
    print(
        f"{len(recorrentes)} contas recorrentes, "
        f"{len(orcamentos)} orcamentos e "
        f"{len(maquininhas)} maquininhas criados."
    )


def criar_fechamentos_exemplo(clientes, usuarios):
    hoje = date.today()
    renato = usuarios["renato@bpo.com"]
    fechamentos = []

    for idx, cliente in enumerate(clientes):
        for offset in [2, 1, 0]:
            receitas = 4200 + idx * 310 + offset * 180
            despesas = 1350 + idx * 120 + offset * 95
            fechamentos.append(FechamentoDiario(
                cliente_id=cliente.id,
                data=hoje - timedelta(days=offset),
                total_receitas_dia=receitas,
                total_despesas_dia=despesas,
                saldo_conta=25000 + idx * 1250 - offset * 700,
                saldo_provisorio_final=25000 + idx * 1250 + receitas - despesas,
                observacao="Fechamento de teste gerado automaticamente.",
                enviado_cliente=offset == 2,
                gerado_por_id=renato.id,
            ))

    db.add_all(fechamentos)
    db.commit()
    print(f"{len(fechamentos)} fechamentos diarios criados.")


def criar_conciliacao_exemplo(clientes, usuarios):
    """Cria um cenario visual rico para a tela de conciliacao."""
    hoje = date.today()
    ana = usuarios["ana@bpo.com"]
    cliente = next((c for c in clientes if c.nome == "PRESTI"), clientes[0])

    atendimentos = [
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=6),
            nome_paciente="Mariana Lopes",
            cpf_paciente="111.222.333-44",
            medico="Dr. Renato Alves",
            especialidade=cliente.especialidade,
            tipo_servico="Consulta",
            descricao_servico="Consulta ortopedica",
            valor_servico=420.00,
            condicao_pagamento=CondicaoPagamento.avista,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje - timedelta(days=4),
            forma_pagamento=FormaPagamento.cartao_credito,
            ultimos_digitos_cartao="4821",
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=294.00,
            percentual_medico=30.00,
            valor_medico=126.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=5),
            nome_paciente="Carlos Henrique",
            cpf_paciente="555.666.777-88",
            medico="Dra. Fernanda Luz",
            especialidade=cliente.especialidade,
            tipo_servico="Retorno",
            descricao_servico="Retorno presencial",
            valor_servico=380.00,
            condicao_pagamento=CondicaoPagamento.avista,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje - timedelta(days=3),
            forma_pagamento=FormaPagamento.cartao_credito,
            ultimos_digitos_cartao="9134",
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=266.00,
            percentual_medico=30.00,
            valor_medico=114.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=3),
            nome_paciente="Patricia Moura",
            cpf_paciente="999.000.111-22",
            medico="Dr. Renato Alves",
            especialidade=cliente.especialidade,
            tipo_servico="Exame",
            descricao_servico="Exame de imagem",
            valor_servico=250.00,
            condicao_pagamento=CondicaoPagamento.pix,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje - timedelta(days=2),
            forma_pagamento=FormaPagamento.pix,
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=175.00,
            percentual_medico=30.00,
            valor_medico=75.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=2),
            nome_paciente="Joao Pedro Lima",
            cpf_paciente="333.444.555-66",
            medico="Dra. Fernanda Luz",
            especialidade=cliente.especialidade,
            tipo_servico="Consulta",
            descricao_servico="Consulta de acompanhamento",
            valor_servico=610.00,
            condicao_pagamento=CondicaoPagamento.transferencia,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje - timedelta(days=1),
            forma_pagamento=FormaPagamento.transferencia,
            status_conciliacao=StatusConciliacao.divergencia,
            valor_clinica=427.00,
            percentual_medico=30.00,
            valor_medico=183.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=1),
            nome_paciente="Bianca Souza",
            cpf_paciente="777.888.999-00",
            medico="Dr. Renato Alves",
            especialidade=cliente.especialidade,
            tipo_servico="Procedimento",
            descricao_servico="Procedimento ambulatorial",
            valor_servico=720.00,
            condicao_pagamento=CondicaoPagamento.parcelado,
            parcela_numero=1,
            parcela_total=2,
            data_prevista_recebimento=hoje + timedelta(days=1),
            forma_pagamento=FormaPagamento.cartao_credito,
            ultimos_digitos_cartao="2210",
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=504.00,
            percentual_medico=30.00,
            valor_medico=216.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=7),
            nome_paciente="Aline Prado",
            cpf_paciente="123.123.123-12",
            medico="Dr. Renato Alves",
            especialidade=cliente.especialidade,
            tipo_servico="Consulta",
            descricao_servico="Consulta inicial joelho",
            valor_servico=540.00,
            condicao_pagamento=CondicaoPagamento.avista,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje - timedelta(days=5),
            forma_pagamento=FormaPagamento.cartao_credito,
            ultimos_digitos_cartao="4451",
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=378.00,
            percentual_medico=30.00,
            valor_medico=162.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=6),
            nome_paciente="Ricardo Paes",
            cpf_paciente="234.234.234-23",
            medico="Dra. Fernanda Luz",
            especialidade=cliente.especialidade,
            tipo_servico="Retorno",
            descricao_servico="Retorno pos procedimento",
            valor_servico=310.00,
            condicao_pagamento=CondicaoPagamento.pix,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje - timedelta(days=5),
            forma_pagamento=FormaPagamento.pix,
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=217.00,
            percentual_medico=30.00,
            valor_medico=93.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=5),
            nome_paciente="Clara Menezes",
            cpf_paciente="345.345.345-34",
            medico="Dr. Renato Alves",
            especialidade=cliente.especialidade,
            tipo_servico="Procedimento",
            descricao_servico="Infiltracao guiada",
            valor_servico=890.00,
            condicao_pagamento=CondicaoPagamento.parcelado,
            parcela_numero=1,
            parcela_total=3,
            data_prevista_recebimento=hoje - timedelta(days=2),
            forma_pagamento=FormaPagamento.cartao_credito,
            ultimos_digitos_cartao="7712",
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=623.00,
            percentual_medico=30.00,
            valor_medico=267.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=4),
            nome_paciente="Mateus Araujo",
            cpf_paciente="456.456.456-45",
            medico="Dra. Fernanda Luz",
            especialidade=cliente.especialidade,
            tipo_servico="Consulta",
            descricao_servico="Consulta lombar",
            valor_servico=470.00,
            condicao_pagamento=CondicaoPagamento.transferencia,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje - timedelta(days=1),
            forma_pagamento=FormaPagamento.transferencia,
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=329.00,
            percentual_medico=30.00,
            valor_medico=141.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=3),
            nome_paciente="Helena Castro",
            cpf_paciente="567.567.567-56",
            medico="Dr. Renato Alves",
            especialidade=cliente.especialidade,
            tipo_servico="Exame",
            descricao_servico="Ultrassom articular",
            valor_servico=285.00,
            condicao_pagamento=CondicaoPagamento.pix,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje - timedelta(days=1),
            forma_pagamento=FormaPagamento.pix,
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=199.50,
            percentual_medico=30.00,
            valor_medico=85.50,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=2),
            nome_paciente="Sergio Nunes",
            cpf_paciente="678.678.678-67",
            medico="Dra. Fernanda Luz",
            especialidade=cliente.especialidade,
            tipo_servico="Consulta",
            descricao_servico="Avaliacao trauma esportivo",
            valor_servico=655.00,
            condicao_pagamento=CondicaoPagamento.avista,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje,
            forma_pagamento=FormaPagamento.cartao_credito,
            ultimos_digitos_cartao="9080",
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=458.50,
            percentual_medico=30.00,
            valor_medico=196.50,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje - timedelta(days=1),
            nome_paciente="Luciana Ferraz",
            cpf_paciente="789.789.789-78",
            medico="Dr. Renato Alves",
            especialidade=cliente.especialidade,
            tipo_servico="Procedimento",
            descricao_servico="Procedimento ambulatorial ombro",
            valor_servico=980.00,
            condicao_pagamento=CondicaoPagamento.parcelado,
            parcela_numero=2,
            parcela_total=2,
            data_prevista_recebimento=hoje + timedelta(days=2),
            forma_pagamento=FormaPagamento.cartao_credito,
            ultimos_digitos_cartao="5520",
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=686.00,
            percentual_medico=30.00,
            valor_medico=294.00,
            lancado_por_id=ana.id,
        ),
        Atendimento(
            cliente_id=cliente.id,
            data_atendimento=hoje,
            nome_paciente="Fernando Bittencourt",
            cpf_paciente="890.890.890-89",
            medico="Dra. Fernanda Luz",
            especialidade=cliente.especialidade,
            tipo_servico="Consulta",
            descricao_servico="Consulta coluna cervical",
            valor_servico=360.00,
            condicao_pagamento=CondicaoPagamento.transferencia,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=hoje + timedelta(days=1),
            forma_pagamento=FormaPagamento.transferencia,
            status_conciliacao=StatusConciliacao.pendente,
            valor_clinica=252.00,
            percentual_medico=30.00,
            valor_medico=108.00,
            lancado_por_id=ana.id,
        ),
    ]

    db.add_all(atendimentos)
    db.commit()

    movimentacoes = [
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="cartao",
            data_movimento=hoje - timedelta(days=4),
            valor=420.00,
            descricao="Lote Stone 26/05 - consulta Mariana Lopes",
            digitos_cartao="4821",
            origem_arquivo="extrato-cartao-maio.xlsx",
            status=StatusMovimentacaoBancaria.importada,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="cartao",
            data_movimento=hoje - timedelta(days=5),
            valor=540.00,
            descricao="Stone lote 24 - Aline Prado",
            digitos_cartao="4451",
            origem_arquivo="extrato-cartao-maio.xlsx",
            status=StatusMovimentacaoBancaria.importada,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_movimento=hoje - timedelta(days=5),
            valor=310.00,
            descricao="PIX Ricardo Paes",
            origem_arquivo="extrato-pix-semana.csv",
            status=StatusMovimentacaoBancaria.importada,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="cartao",
            data_movimento=hoje - timedelta(days=2),
            valor=383.00,
            descricao="Lote Stone 28/05 - retorno Carlos Henrique",
            digitos_cartao="9134",
            origem_arquivo="extrato-cartao-maio.xlsx",
            status=StatusMovimentacaoBancaria.divergencia,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_movimento=hoje - timedelta(days=2),
            valor=250.00,
            descricao="PIX Patricia Moura",
            origem_arquivo="extrato-pix-semana.csv",
            status=StatusMovimentacaoBancaria.importada,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_movimento=hoje - timedelta(days=1),
            valor=612.00,
            descricao="TED Joao Pedro Lima",
            origem_arquivo="extrato-pix-semana.csv",
            status=StatusMovimentacaoBancaria.divergencia,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="cartao",
            data_movimento=hoje - timedelta(days=2),
            valor=892.00,
            descricao="Stone lote 27 - Clara Menezes",
            digitos_cartao="7712",
            origem_arquivo="extrato-cartao-maio.xlsx",
            status=StatusMovimentacaoBancaria.divergencia,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_movimento=hoje - timedelta(days=1),
            valor=470.00,
            descricao="TED Mateus Araujo",
            origem_arquivo="extrato-pix-semana.csv",
            status=StatusMovimentacaoBancaria.importada,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_movimento=hoje - timedelta(days=1),
            valor=286.50,
            descricao="PIX Helena Castro",
            origem_arquivo="extrato-pix-semana.csv",
            status=StatusMovimentacaoBancaria.divergencia,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="cartao",
            data_movimento=hoje,
            valor=655.00,
            descricao="Stone lote 29 - Sergio Nunes",
            digitos_cartao="9080",
            origem_arquivo="extrato-cartao-maio.xlsx",
            status=StatusMovimentacaoBancaria.importada,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="cartao",
            data_movimento=hoje + timedelta(days=1),
            valor=980.00,
            descricao="Stone agenda futura - Luciana Ferraz",
            digitos_cartao="5520",
            origem_arquivo="extrato-cartao-maio.xlsx",
            status=StatusMovimentacaoBancaria.importada,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_movimento=hoje + timedelta(days=1),
            valor=360.00,
            descricao="TED Fernando Bittencourt",
            origem_arquivo="extrato-pix-semana.csv",
            status=StatusMovimentacaoBancaria.importada,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="cartao",
            data_movimento=hoje,
            valor=999.00,
            descricao="Credito sem identificacao no extrato",
            digitos_cartao="0000",
            origem_arquivo="extrato-cartao-maio.xlsx",
            status=StatusMovimentacaoBancaria.importada,
        ),
    ]

    contas_saida = (
        db.query(ContaPagar)
        .filter(
            ContaPagar.cliente_id == cliente.id,
            ContaPagar.status == StatusContaPagar.agendado,
        )
        .order_by(ContaPagar.vencimento.asc(), ContaPagar.id.asc())
        .limit(5)
        .all()
    )
    saidas_banco = [
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            sentido="pagamento",
            data_movimento=conta.vencimento,
            valor=conta.valor if conta.descricao != "Folha assistentes" else 2247.50,
            descricao=f"PAGAMENTO {conta.fornecedor or conta.descricao}",
            origem_arquivo="extrato-banco-completo.csv",
            status=(
                StatusMovimentacaoBancaria.divergencia
                if conta.descricao == "Folha assistentes"
                else StatusMovimentacaoBancaria.importada
            ),
        )
        for conta in contas_saida
    ]

    lotes_cartao = [
        TransferenciaCartao(
            cliente_id=cliente.id,
            data=hoje - timedelta(days=1),
            bandeira="Visa",
            valor_bruto=1200.00,
            taxa_total=29.88,
            valor_liquido=1170.12,
            qtd_transacoes=3,
            status=StatusTransferenciaCartao.pendente,
        ),
        TransferenciaCartao(
            cliente_id=cliente.id,
            data=hoje,
            bandeira="Mastercard",
            valor_bruto=980.00,
            taxa_total=25.38,
            valor_liquido=954.62,
            qtd_transacoes=2,
            status=StatusTransferenciaCartao.pendente,
        ),
    ]
    repasses_cartao = [
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            sentido="recebimento",
            data_movimento=hoje,
            valor=1170.12,
            descricao="REPASSE STONE VISA",
            origem_arquivo="extrato-banco-completo.csv",
            status=StatusMovimentacaoBancaria.importada,
        ),
        MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            sentido="recebimento",
            data_movimento=hoje + timedelta(days=1),
            valor=954.62,
            descricao="REPASSE STONE MASTERCARD",
            origem_arquivo="extrato-banco-completo.csv",
            status=StatusMovimentacaoBancaria.importada,
        ),
    ]

    movimentacoes.extend(saidas_banco)
    movimentacoes.extend(repasses_cartao)

    divergencias = [
        DivergenciaConciliacao(
            cliente_id=cliente.id,
            tipo="cartao",
            data_extrato=hoje - timedelta(days=2),
            valor=383.00,
            digitos_cartao="9134",
            motivo="Valor proximo ao lancamento do sistema. Revisar taxa ou diferenca.",
            resolvida=False,
        ),
        DivergenciaConciliacao(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_extrato=hoje - timedelta(days=1),
            valor=612.00,
            motivo="Transferencia com pequena variacao para conferencia manual.",
            resolvida=False,
        ),
        DivergenciaConciliacao(
            cliente_id=cliente.id,
            tipo="cartao",
            data_extrato=hoje - timedelta(days=2),
            valor=892.00,
            digitos_cartao="7712",
            motivo="Valor importado com pequena variacao. Sugerir revisao e conciliacao manual.",
            resolvida=False,
        ),
        DivergenciaConciliacao(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_extrato=hoje - timedelta(days=1),
            valor=286.50,
            motivo="PIX com diferenca pequena para demonstrar conferencia.",
            resolvida=False,
        ),
        DivergenciaConciliacao(
            cliente_id=cliente.id,
            tipo="cartao",
            data_extrato=hoje,
            valor=999.00,
            digitos_cartao="0000",
            motivo="Movimentacao sem correspondencia clara no sistema.",
            resolvida=False,
        ),
    ]

    db.add_all(lotes_cartao)
    db.add_all(movimentacoes)
    db.add_all(divergencias)
    db.commit()
    print(
        f"{len(atendimentos)} atendimentos, "
        f"{len(movimentacoes)} movimentacoes bancarias importadas e "
        f"{len(divergencias)} divergencias criadas."
    )


if __name__ == "__main__":
    print("Iniciando seed...")
    limpar()
    usuarios = criar_usuarios()
    clientes = criar_clientes(usuarios)
    criar_rotinas_hoje(clientes)
    criar_contas_pagar_exemplo(clientes)
    criar_cadastros_financeiros_exemplo(clientes)
    criar_fechamentos_exemplo(clientes, usuarios)
    criar_conciliacao_exemplo(clientes, usuarios)
    db.close()
    print("\nSeed concluido. As senhas permanecem somente nas variaveis de ambiente.")
    print("  Coordenador: renato@bpo.com")
    print("  Funcionarios: ana@bpo.com, marcos@bpo.com, julia@bpo.com")
