"""Torna campos cadastrais basicos legiveis para relatorios e integracoes.

Revision ID: 0003_plaintext_basic_fields
Revises: 0002_security_hardening
"""
from __future__ import annotations

import re
from collections.abc import Callable

from alembic import op
from sqlalchemy import text

from app.field_encryption import decrypt_value, encrypt_value


revision = "0003_plaintext_basic_fields"
down_revision = "0002_security_hardening"
branch_labels = None
depends_on = None

BATCH_SIZE = 500
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")

# Esta lista faz parte do historico imutavel da migration. Nao importar a
# classificacao atual da aplicacao, pois ela pode evoluir em revisoes futuras.
BASIC_FIELDS = (
    ("usuarios", "nome", "usuarios.nome", False),
    ("usuarios", "email", "usuarios.email", True),
    ("clientes_bpo", "nome", "clientes_bpo.nome", False),
    ("clientes_bpo", "razao_social", "clientes_bpo.razao_social", False),
    ("clientes_bpo", "cnpj", "clientes_bpo.cnpj", True),
    ("centros_custo", "nome", "centros_custo.nome", False),
    ("tarefas_rotina", "descricao", "tarefas_rotina.descricao", False),
    ("logs_auditoria", "usuario_nome", "logs_auditoria.usuario_nome", False),
    ("logs_auditoria", "cliente_nome", "logs_auditoria.cliente_nome", False),
)


def _identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise RuntimeError(f"Identificador invalido na migration: {value!r}")
    return f'"{value}"'


def _transform_fields(
    transform: Callable[[str, str, bool], str],
) -> None:
    bind = op.get_bind()
    for table, column, context, deterministic in BASIC_FIELDS:
        table_sql = _identifier(table)
        column_sql = _identifier(column)
        last_id = 0
        while True:
            rows = bind.execute(
                text(
                    f"SELECT id, {column_sql} AS field_value "
                    f"FROM {table_sql} "
                    f"WHERE id > :last_id AND {column_sql} IS NOT NULL "
                    "ORDER BY id LIMIT :batch_size"
                ),
                {"last_id": last_id, "batch_size": BATCH_SIZE},
            ).all()
            if not rows:
                break

            for row in rows:
                row_data = row._mapping
                current = row_data["field_value"]
                updated = transform(current, context, deterministic)
                if updated != current:
                    bind.execute(
                        text(
                            f"UPDATE {table_sql} SET {column_sql} = :value "
                            "WHERE id = :row_id"
                        ),
                        {"value": updated, "row_id": row_data["id"]},
                    )
            last_id = rows[-1]._mapping["id"]


def upgrade() -> None:
    _transform_fields(
        lambda value, context, _deterministic: decrypt_value(value, context)
    )


def downgrade() -> None:
    _transform_fields(
        lambda value, context, deterministic: encrypt_value(
            value,
            context,
            deterministic=deterministic,
        )
    )
