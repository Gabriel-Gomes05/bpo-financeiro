"""Contas bancárias por tipo: Conta Corrente, Investimentos e Cartão de Crédito.

Revision ID: 0017_tipos_conta_bancaria
Revises: 0016_secretaria_historico
"""
import sqlalchemy as sa
from alembic import op

revision = "0017_tipos_conta_bancaria"
down_revision = "0016_secretaria_historico"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Contas existentes continuam "bancaria" (Conta Corrente); "cartao" já existia no enum.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tipocontabancaria ADD VALUE IF NOT EXISTS 'investimento'")
    op.add_column("contas_bancarias", sa.Column("descricao", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("contas_bancarias", "descricao")
    # O valor 'investimento' permanece no enum: o PostgreSQL não remove valores de ENUM.
