"""Completa o vinculo de grupo empresarial em bancos legados.

Revision ID: 0004_legacy_grupo_empresarial
Revises: 0003_plaintext_basic_fields
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


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
