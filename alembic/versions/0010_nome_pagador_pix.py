"""Adiciona o nome do pagador para recebimentos via Pix.

Revision ID: 0010_nome_pagador_pix
Revises: 0009_servico_plano_conta
"""
import sqlalchemy as sa
from alembic import op

revision = "0010_nome_pagador_pix"
down_revision = "0009_servico_plano_conta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("atendimentos", sa.Column("nome_pagador_pix", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("atendimentos", "nome_pagador_pix")
