"""Cria regras automáticas de negócio bancário.

Revision ID: 0012_regras_bancarias
Revises: 0011_fluxo_aprovacao
"""
import sqlalchemy as sa
from alembic import op

revision = "0012_regras_bancarias"
down_revision = "0011_fluxo_aprovacao"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regras_negocio_bancarias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes_bpo.id"), nullable=False),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("padrao_descricao", sa.Text(), nullable=False),
        sa.Column("conta_origem_id", sa.Integer(), sa.ForeignKey("contas_bancarias.id"), nullable=False),
        sa.Column("conta_destino_id", sa.Integer(), sa.ForeignKey("contas_bancarias.id"), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
    )
    op.create_index("ix_regras_negocio_bancarias_id", "regras_negocio_bancarias", ["id"])
    op.create_index("ix_regras_negocio_bancarias_cliente_id", "regras_negocio_bancarias", ["cliente_id"])
    op.create_index("ix_regras_negocio_bancarias_public_id", "regras_negocio_bancarias", ["public_id"], unique=True)
    op.create_index("ix_regras_negocio_bancarias_deleted_at", "regras_negocio_bancarias", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("regras_negocio_bancarias")
