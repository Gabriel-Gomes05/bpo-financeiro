"""Cria cadastro de serviços globais e por cliente.

Revision ID: 0008_servicos_cadastro
Revises: 0007_cartao_debito
"""
import sqlalchemy as sa
from alembic import op
from uuid import UUID

revision = "0008_servicos_cadastro"
down_revision = "0007_cartao_debito"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "servicos_cadastro",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes_bpo.id"), nullable=True),
        sa.Column("codigo", sa.String(30), nullable=True),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
    )
    op.create_index("ix_servicos_cadastro_id", "servicos_cadastro", ["id"])
    op.create_index("ix_servicos_cadastro_public_id", "servicos_cadastro", ["public_id"], unique=True)
    op.create_index("ix_servicos_cadastro_deleted_at", "servicos_cadastro", ["deleted_at"])
    tabela = sa.table(
        "servicos_cadastro", sa.column("codigo"), sa.column("nome"),
        sa.column("cliente_id"), sa.column("ativo"), sa.column("public_id", sa.Uuid()),
    )
    op.bulk_insert(tabela, [
        {"codigo": "SRV-001", "nome": "Consulta", "cliente_id": None, "ativo": True, "public_id": UUID("10000000-0000-4000-8000-000000000001")},
        {"codigo": "SRV-002", "nome": "Procedimento", "cliente_id": None, "ativo": True, "public_id": UUID("10000000-0000-4000-8000-000000000002")},
        {"codigo": "SRV-003", "nome": "Cirurgia", "cliente_id": None, "ativo": True, "public_id": UUID("10000000-0000-4000-8000-000000000003")},
        {"codigo": "SRV-004", "nome": "Exame", "cliente_id": None, "ativo": True, "public_id": UUID("10000000-0000-4000-8000-000000000004")},
        {"codigo": "SRV-005", "nome": "Retorno", "cliente_id": None, "ativo": True, "public_id": UUID("10000000-0000-4000-8000-000000000005")},
        {"codigo": "SRV-006", "nome": "Outros serviços", "cliente_id": None, "ativo": True, "public_id": UUID("10000000-0000-4000-8000-000000000006")},
    ])


def downgrade() -> None:
    op.drop_table("servicos_cadastro")
