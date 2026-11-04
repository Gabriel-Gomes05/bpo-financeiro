"""Conciliação agrupada: um movimento do extrato com vários lançamentos.

Revision ID: 0021_conciliacao_agrupada
Revises: 0020_regra_cria_lancamento
"""
import sqlalchemy as sa
from alembic import op

revision = "0021_conciliacao_agrupada"
down_revision = "0020_regra_cria_lancamento"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("atendimentos", sa.Column("movimentacao_grupo_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_atendimentos_movimentacao_grupo", "atendimentos", "movimentacoes_bancarias",
                          ["movimentacao_grupo_id"], ["id"])
    op.create_index("ix_atendimentos_movimentacao_grupo_id", "atendimentos", ["movimentacao_grupo_id"])

    # Antes: um pagamento por movimento. Agora: um por (movimento, conta).
    op.drop_constraint("pagamentos_parciais_contas_pagar_movimentacao_id_key", "pagamentos_parciais_contas_pagar",
                       type_="unique")
    op.create_unique_constraint("uq_pagamento_parcial_mov_conta", "pagamentos_parciais_contas_pagar",
                                ["movimentacao_id", "conta_pagar_id"])
    op.create_index("ix_pagamentos_parciais_contas_pagar_movimentacao_id", "pagamentos_parciais_contas_pagar",
                    ["movimentacao_id"])


def downgrade() -> None:
    op.drop_index("ix_pagamentos_parciais_contas_pagar_movimentacao_id", table_name="pagamentos_parciais_contas_pagar")
    op.drop_constraint("uq_pagamento_parcial_mov_conta", "pagamentos_parciais_contas_pagar", type_="unique")
    op.create_unique_constraint("pagamentos_parciais_contas_pagar_movimentacao_id_key",
                                "pagamentos_parciais_contas_pagar", ["movimentacao_id"])
    op.drop_index("ix_atendimentos_movimentacao_grupo_id", table_name="atendimentos")
    op.drop_constraint("fk_atendimentos_movimentacao_grupo", "atendimentos", type_="foreignkey")
    op.drop_column("atendimentos", "movimentacao_grupo_id")
