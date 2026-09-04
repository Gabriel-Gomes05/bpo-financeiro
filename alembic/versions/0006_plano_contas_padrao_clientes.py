"""Carrega o plano de contas padrão fornecido pelo cliente.

Revision ID: 0006_plano_contas_padrao
Revises: 0005_legacy_plano_contas
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_plano_contas_padrao"
down_revision = "0005_legacy_plano_contas"
branch_labels = None
depends_on = None


GRUPOS = {
    "01": ("Pessoal", ["Salário base", "Pró-labore", "FGTS", "INSS/IRF", "13º Salário", "Férias + 1/3", "Vale Transporte", "Vale Refeição", "Convênio médico", "Outras despesas com pessoal"]),
    "02": ("Estrutural", ["Aluguel", "Condomínio", "Conta de energia", "Conta de água", "IPTU", "Demais taxas do imóvel"]),
    "03": ("Marketing", ["Planos de Marketing", "Ações de divulgação", "Materiais de Marketing", "Consultoria em Marketing"]),
    "04": ("Tecnologia", ["Licenças de Software", "Manutenção de Software e equipamentos", "Pequenos equipamentos de informática", "Prontuário Eletrônico", "Host de e-mail", "Aluguel de equipamentos", "Hospedagem na Nuvem"]),
    "05": ("Consumo", ["Materiais de Escritório", "Materiais de Copa e Cozinha", "Materiais de limpeza", "Demais materiais de consumo"]),
    "06": ("Congressos", ["Passagens aéreas / rodoviárias", "Hospedagem", "Inscrição", "Alimentação", "Demais custos de congressos"]),
    "07": ("Serviços", ["BPO", "Contabilidade", "Limpeza", "Motoboy", "Manutenções diversas", "Outros Serviços Diversos", "Repasses aos Médicos"]),
    "08": ("Diversos", ["Estacionamento", "Transporte e Alimentação", "Taxas Cremesp", "Seguros", "Cartório", "Conta de telefone + TV por assinatura", "Sólida Reembolso", "Link de internet", "Demais Custos Diversos"]),
    "09": ("Bancárias", ["Tarifas de Manutenção", "Tarifas de serviços", "Taxa Cartão"]),
    "10": ("Procedimentos", ["Materiais para procedimentos"]),
    "11": ("Investimentos", ["Compra de Máquinas e equipamentos", "Compra de Móveis e Utensílios", "Obras"]),
    "12": ("Financeiras", ["Multas e Juros"]),
    "13": ("Impostos", ["PIS", "COFINS", "ISS", "DAS (Simples Nacional)", "IRPJ", "CSLL"]),
    "14": ("Não Operacionais", ["Distribuição de Lucros"]),
    "20": ("Receitas", ["Consulta", "Procedimentos", "Cirurgia", "Exames", "Outras receitas", "Sublocação"]),
}

LEGADOS = ("rec_consultas", "rec_procedimentos", "rec_exames", "rec_convenios", "rec_outros",
    "cv_material", "cv_terceiros", "cv_honorarios", "df_aluguel", "df_folha", "df_encargos",
    "df_energia", "df_agua", "df_internet", "df_manutencao", "df_limpeza", "da_contabil",
    "da_impostos", "da_software", "da_marketing", "da_seguros", "da_outros")


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE planos_conta SET ativo=false WHERE cliente_id IS NULL AND chave = ANY(:chaves)"), {"chaves": list(LEGADOS)})
    for prefixo, (grupo, nomes) in GRUPOS.items():
        tipo = "receita" if prefixo == "20" else "despesa"
        for indice, nome in enumerate(nomes, 1):
            codigo = f"{prefixo}.{indice:02d}"
            bind.execute(sa.text(
                "INSERT INTO planos_conta (tipo, grupo, chave, codigo, nome, ativo) "
                "VALUES (:tipo, :grupo, :chave, :codigo, :nome, true) "
                "ON CONFLICT (chave) WHERE cliente_id IS NULL DO UPDATE SET "
                "tipo=EXCLUDED.tipo, grupo=EXCLUDED.grupo, codigo=EXCLUDED.codigo, nome=EXCLUDED.nome, ativo=true"
            ), {"tipo": tipo, "grupo": grupo, "chave": f"padrao_{codigo.replace('.', '_')}", "codigo": codigo, "nome": nome})


def downgrade() -> None:
    op.execute("UPDATE planos_conta SET ativo=false WHERE cliente_id IS NULL AND chave LIKE 'padrao_%'")
    op.execute(sa.text("UPDATE planos_conta SET ativo=true WHERE cliente_id IS NULL AND chave = ANY(:chaves)").bindparams(chaves=list(LEGADOS)))
