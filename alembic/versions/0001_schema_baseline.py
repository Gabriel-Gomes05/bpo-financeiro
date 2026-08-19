"""Cria ou adota o schema funcional existente.

Revision ID: 0001_schema_baseline
Revises:
"""
from alembic import op

from app.database import Base
from app import models  # noqa: F401

revision = "0001_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create_all é intencional somente nesta baseline: cria banco vazio e não
    # altera tabelas existentes. Toda evolução posterior usa operações versionadas.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # A baseline pode adotar um banco pré-existente; removê-lo seria destrutivo.
    raise RuntimeError("A baseline não oferece downgrade destrutivo.")
