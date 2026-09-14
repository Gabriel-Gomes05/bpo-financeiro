"""Amplia regras bancárias para conciliação automática.

Revision ID: 0013_regras_conciliacao
Revises: 0012_regras_bancarias
"""
import sqlalchemy as sa
from alembic import op

revision = "0013_regras_conciliacao"
down_revision = "0012_regras_bancarias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("regras_negocio_bancarias", sa.Column("acao", sa.String(30), nullable=False, server_default="transferencia"))
    op.add_column("regras_negocio_bancarias", sa.Column("plano_conta_id", sa.Integer(), sa.ForeignKey("planos_conta.id"), nullable=True))
    op.alter_column("regras_negocio_bancarias", "conta_origem_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("regras_negocio_bancarias", "conta_destino_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM regras_negocio_bancarias WHERE acao <> 'transferencia'")
    op.alter_column("regras_negocio_bancarias", "conta_destino_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("regras_negocio_bancarias", "conta_origem_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("regras_negocio_bancarias", "plano_conta_id")
    op.drop_column("regras_negocio_bancarias", "acao")
