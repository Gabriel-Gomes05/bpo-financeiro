"""Adiciona fluxo de pagamento não conciliado e controle informativo de recebimento.

Revision ID: 0011_fluxo_aprovacao
Revises: 0010_nome_pagador_pix
"""
import sqlalchemy as sa
from alembic import op

revision = "0011_fluxo_aprovacao"
down_revision = "0010_nome_pagador_pix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE statuscontapagar ADD VALUE IF NOT EXISTS 'pago_nao_conciliado'")
    op.add_column(
        "contas_pagar",
        sa.Column("recebido", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("contas_pagar", "recebido")
    # PostgreSQL não permite remover diretamente um valor de enum.
