"""Completa o vinculo de grupo empresarial em bancos legados.

Revision ID: 0004_legacy_grupo_empresarial
Revises: 0003_plaintext_basic_fields
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "0004_legacy_grupo_empresarial"
down_revision = "0003_plaintext_basic_fields"
branch_labels = None
depends_on = None


def _foreign_key_exists() -> bool:
    return any(
        foreign_key.get("constrained_columns") == ["grupo_empresarial_id"]
        and foreign_key.get("referred_table") == "grupos_empresariais"
        for foreign_key in inspect(op.get_bind()).get_foreign_keys("clientes_bpo")
    )


def upgrade() -> None:
    """Adiciona a coluna que ``create_all`` nao inclui em tabelas existentes."""
    inspector = inspect(op.get_bind())
    if "grupos_empresariais" not in inspector.get_table_names():
        op.create_table(
            "grupos_empresariais",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nome", sa.String(length=150), nullable=False),
            sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column(
                "criado_em",
                sa.DateTime(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("funcionario_id", sa.Integer(), nullable=True),
            sa.Column(
                "public_id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["funcionario_id"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
            sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
            sa.UniqueConstraint("public_id", name="uq_grupos_empresariais_public_id"),
        )
        op.create_index(
            "ix_grupos_empresariais_deleted_at",
            "grupos_empresariais",
            ["deleted_at"],
        )
        op.execute(
            'CREATE TRIGGER "trg_grupos_empresariais_updated_at" '
            'BEFORE UPDATE ON "grupos_empresariais" '
            "FOR EACH ROW EXECUTE FUNCTION flic_set_updated_at()"
        )
        op.execute(
            'CREATE TRIGGER "trg_grupos_empresariais_audit" '
            'AFTER INSERT OR UPDATE OR DELETE ON "grupos_empresariais" '
            "FOR EACH ROW EXECUTE FUNCTION flic_audit_event()"
        )

    columns = {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("clientes_bpo")
    }
    if "grupo_empresarial_id" not in columns:
        op.add_column(
            "clientes_bpo",
            sa.Column("grupo_empresarial_id", sa.Integer(), nullable=True),
        )

    if not _foreign_key_exists():
        op.create_foreign_key(
            "fk_clientes_bpo_grupo_empresarial_id",
            "clientes_bpo",
            "grupos_empresariais",
            ["grupo_empresarial_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    raise RuntimeError("A migration de compatibilidade exige downgrade manual e revisado.")
