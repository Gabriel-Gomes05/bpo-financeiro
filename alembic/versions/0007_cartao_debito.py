"""Adiciona cartão de débito às formas de pagamento.

Revision ID: 0007_cartao_debito
Revises: 0006_plano_contas_padrao
"""
from alembic import op

revision = "0007_cartao_debito"
down_revision = "0006_plano_contas_padrao"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE formapagamento ADD VALUE IF NOT EXISTS 'cartao_debito'")


def downgrade() -> None:
    # O PostgreSQL não permite remover com segurança um valor de enum em uso.
    pass
