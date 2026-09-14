"""Vincula cada serviço a exatamente um plano de contas.

Revision ID: 0009_servico_plano_conta
Revises: 0008_servicos_cadastro
"""
import sqlalchemy as sa
from alembic import op

revision = "0009_servico_plano_conta"
down_revision = "0008_servicos_cadastro"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("servicos_cadastro", sa.Column("plano_conta_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_servicos_cadastro_plano_conta", "servicos_cadastro", "planos_conta",
        ["plano_conta_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_servicos_cadastro_plano_conta", "servicos_cadastro", type_="foreignkey")
    op.drop_column("servicos_cadastro", "plano_conta_id")
