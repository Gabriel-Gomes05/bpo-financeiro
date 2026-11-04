"""Conta bancária do cliente escolhida no lançamento de contas a pagar.

Revision ID: 0019_conta_pagar_conta_banco
Revises: 0018_periodos_fechados
"""
import sqlalchemy as sa
from alembic import op

revision = "0019_conta_pagar_conta_banco"
down_revision = "0018_periodos_fechados"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Opcional: contas já lançadas ficam como "Não informada".
    op.add_column("contas_pagar", sa.Column("conta_bancaria_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_contas_pagar_conta_bancaria", "contas_pagar", "contas_bancarias",
                          ["conta_bancaria_id"], ["id"])
    op.create_index("ix_contas_pagar_conta_bancaria_id", "contas_pagar", ["conta_bancaria_id"])


def downgrade() -> None:
    op.drop_index("ix_contas_pagar_conta_bancaria_id", table_name="contas_pagar")
    op.drop_constraint("fk_contas_pagar_conta_bancaria", "contas_pagar", type_="foreignkey")
    op.drop_column("contas_pagar", "conta_bancaria_id")
