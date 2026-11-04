"""Regra bancária pode criar o lançamento quando não houver correspondente.

Revision ID: 0020_regra_cria_lancamento
Revises: 0019_conta_pagar_conta_banco
"""
import sqlalchemy as sa
from alembic import op

revision = "0020_regra_cria_lancamento"
down_revision = "0019_conta_pagar_conta_banco"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Regras existentes mantêm o comportamento atual (só vinculam); a opção é ligada por regra.
    op.add_column("regras_negocio_bancarias",
                  sa.Column("criar_lancamento", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("regras_negocio_bancarias", "criar_lancamento")
