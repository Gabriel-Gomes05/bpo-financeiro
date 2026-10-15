"""Cria o gestor de tarefas (pessoais ou vinculadas a cliente).

Revision ID: 0014_tarefas
Revises: 0013_regras_conciliacao
"""
import sqlalchemy as sa
from alembic import op

revision = "0014_tarefas"
down_revision = "0013_regras_conciliacao"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tarefas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titulo", sa.String(200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("responsavel_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes_bpo.id"), nullable=True),
        sa.Column("modulo", sa.String(40), nullable=True),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("prazo", sa.Date(), nullable=True),
        sa.Column("concluida", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("concluida_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("public_id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
    )
    op.create_index("ix_tarefas_id", "tarefas", ["id"])
    op.create_index("ix_tarefas_responsavel_id", "tarefas", ["responsavel_id"])
    op.create_index("ix_tarefas_cliente_id", "tarefas", ["cliente_id"])
    op.create_index("ix_tarefas_public_id", "tarefas", ["public_id"], unique=True)
    op.create_index("ix_tarefas_deleted_at", "tarefas", ["deleted_at"])
    op.execute(
        'CREATE TRIGGER "trg_tarefas_updated_at" BEFORE UPDATE ON "tarefas" '
        "FOR EACH ROW EXECUTE FUNCTION flic_set_updated_at()"
    )
    op.execute(
        'CREATE TRIGGER "trg_tarefas_audit" AFTER INSERT OR UPDATE OR DELETE '
        'ON "tarefas" FOR EACH ROW EXECUTE FUNCTION flic_audit_event()'
    )


def downgrade() -> None:
    op.drop_table("tarefas")
