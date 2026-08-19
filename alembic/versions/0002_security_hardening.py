"""Auditoria, constraints e isolamento multi-cliente incrementais.

Revision ID: 0002_security_hardening
Revises: 0001_schema_baseline
"""
from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql

from app.config import DATABASE_RUNTIME_ROLE
from app.database import Base
from app import models  # noqa: F401

revision = "0002_security_hardening"
down_revision = "0001_schema_baseline"
branch_labels = None
depends_on = None

IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _quoted_identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise RuntimeError("DATABASE_RUNTIME_ROLE contém identificador inválido.")
    return f'"{value}"'


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _constraint_exists(name: str) -> bool:
    return bool(
        op.get_bind().execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
            {"name": name},
        ).first()
    )


def _foreign_key_exists(table: str, local_column: str, remote_table: str) -> bool:
    for foreign_key in inspect(op.get_bind()).get_foreign_keys(table):
        if (
            foreign_key.get("referred_table") == remote_table
            and foreign_key.get("constrained_columns") == [local_column]
        ):
            return True
    return False


def _unique_column_exists(table: str, column: str) -> bool:
    inspector = inspect(op.get_bind())
    return any(
        index.get("unique") and index.get("column_names") == [column]
        for index in inspector.get_indexes(table)
    ) or any(
        constraint.get("column_names") == [column]
        for constraint in inspector.get_unique_constraints(table)
    )


def _add_not_valid_check(table: str, name: str, expression: str) -> None:
    if not _constraint_exists(name):
        op.execute(
            sa.text(
                f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" '
                f"CHECK ({expression}) NOT VALID"
            )
        )


def _add_not_valid_fk(
    table: str,
    name: str,
    local_columns: str,
    remote_table: str,
    remote_columns: str,
) -> None:
    if not _constraint_exists(name):
        op.execute(
            sa.text(
                f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" '
                f"FOREIGN KEY ({local_columns}) "
                f'REFERENCES "{remote_table}" ({remote_columns}) NOT VALID'
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    tables = sorted(
        table
        for table in Base.metadata.tables
        if table not in {"audit_events", "alembic_version"}
    )

    for table in tables:
        columns = _columns(table)
        with op.batch_alter_table(table) as batch:
            if "public_id" not in columns:
                batch.add_column(sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=True))
            if "created_at" not in columns:
                batch.add_column(
                    sa.Column(
                        "created_at",
                        sa.DateTime(timezone=True),
                        server_default=sa.text("now()"),
                        nullable=False,
                    )
                )
            if "updated_at" not in columns:
                batch.add_column(
                    sa.Column(
                        "updated_at",
                        sa.DateTime(timezone=True),
                        server_default=sa.text("now()"),
                        nullable=False,
                    )
                )
            if "deleted_at" not in columns:
                batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
            if "created_by" not in columns:
                batch.add_column(sa.Column("created_by", sa.Integer(), nullable=True))
            if "updated_by" not in columns:
                batch.add_column(sa.Column("updated_by", sa.Integer(), nullable=True))

        op.execute(sa.text(f'UPDATE "{table}" SET public_id = gen_random_uuid() WHERE public_id IS NULL'))
        op.alter_column(table, "public_id", nullable=False)
        if not _unique_column_exists(table, "public_id"):
            op.execute(
                sa.text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS "uq_{table}_public_id" '
                    f'ON "{table}" (public_id)'
                )
            )
        op.execute(
            sa.text(
                f'CREATE INDEX IF NOT EXISTS "ix_{table}_deleted_at" '
                f'ON "{table}" (deleted_at)'
            )
        )
        for actor_column in ("created_by", "updated_by"):
            constraint_name = f"fk_{table}_{actor_column}_usuarios"
            if not _foreign_key_exists(table, actor_column, "usuarios"):
                _add_not_valid_fk(
                    table,
                    constraint_name,
                    f'"{actor_column}"',
                    "usuarios",
                    '"id"',
                )

    if "auth_version" not in _columns("usuarios"):
        op.add_column(
            "usuarios",
            sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False),
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION flic_set_updated_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$
        """
    )
    for table in tables:
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS "trg_{table}_updated_at" ON "{table}"'))
        op.execute(
            sa.text(
                f'CREATE TRIGGER "trg_{table}_updated_at" BEFORE UPDATE ON "{table}" '
                "FOR EACH ROW EXECUTE FUNCTION flic_set_updated_at()"
            )
        )

    # Índices operacionais mais usados.
    for table in tables:
        if "cliente_id" in _columns(table):
            op.execute(
                sa.text(
                    f'CREATE INDEX IF NOT EXISTS "ix_{table}_cliente_id" '
                    f'ON "{table}" (cliente_id)'
                )
            )
            op.execute(
                sa.text(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS "uq_{table}_id_cliente_id" '
                    f'ON "{table}" (id, cliente_id)'
                )
            )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_contas_pagar_cliente_status_vencimento "
        "ON contas_pagar (cliente_id, status, vencimento)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_atendimentos_cliente_status_data "
        "ON atendimentos (cliente_id, status_conciliacao, data_atendimento)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_movimentacoes_cliente_status_data "
        "ON movimentacoes_bancarias (cliente_id, status, data_movimento)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_events_table_time "
        "ON audit_events (table_name, occurred_at DESC)"
    )

    # Regras novas passam a valer imediatamente; dados legados são validados
    # em uma migration posterior após o relatório de inconsistências.
    checks = (
        ("contas_pagar", "ck_contas_pagar_valor_positivo", "valor > 0"),
        ("atendimentos", "ck_atendimentos_valor_positivo", "valor_servico > 0"),
        ("movimentacoes_bancarias", "ck_movimentacoes_valor_positivo", "valor > 0"),
        ("vendas_cartao", "ck_vendas_cartao_valor_positivo", "valor_bruto > 0"),
        ("taxas_cartao_cliente", "ck_taxa_cartao_percentual", "taxa_percentual BETWEEN 0 AND 100"),
        ("taxas_antecipacao_cliente", "ck_taxa_antecipacao_percentual", "taxa_percentual BETWEEN 0 AND 100"),
        ("orcamento_valores", "ck_orcamento_mes", "mes BETWEEN 1 AND 12"),
        ("contas_recorrentes", "ck_conta_recorrente_dia", "dia_vencimento BETWEEN 1 AND 31"),
    )
    for table, name, expression in checks:
        _add_not_valid_check(table, name, expression)

    tenant_fks = (
        ("atendimentos", "fk_atendimento_centro_mesmo_cliente", '"centro_custo_id", "cliente_id"', "centros_custo", '"id", "cliente_id"'),
        ("movimentacoes_bancarias", "fk_mov_conta_bancaria_mesmo_cliente", '"conta_bancaria_id", "cliente_id"', "contas_bancarias", '"id", "cliente_id"'),
        ("movimentacoes_bancarias", "fk_mov_atendimento_mesmo_cliente", '"conciliada_com_atendimento_id", "cliente_id"', "atendimentos", '"id", "cliente_id"'),
        ("movimentacoes_bancarias", "fk_mov_conta_pagar_mesmo_cliente", '"conta_pagar_id", "cliente_id"', "contas_pagar", '"id", "cliente_id"'),
        ("movimentacoes_bancarias", "fk_mov_transferencia_mesmo_cliente", '"transferencia_cartao_id", "cliente_id"', "transferencias_cartao", '"id", "cliente_id"'),
        ("vendas_cartao", "fk_venda_atendimento_mesmo_cliente", '"atendimento_id", "cliente_id"', "atendimentos", '"id", "cliente_id"'),
        ("vendas_cartao", "fk_venda_lote_mesmo_cliente", '"lote_id", "cliente_id"', "transferencias_cartao", '"id", "cliente_id"'),
        ("taxas_cartao_cliente", "fk_taxa_maquininha_mesmo_cliente", '"maquininha_id", "cliente_id"', "maquininhas_cliente", '"id", "cliente_id"'),
        ("extratos_bancarios", "fk_extrato_transferencia_mesmo_cliente", '"transferencia_id", "cliente_id"', "transferencias_cartao", '"id", "cliente_id"'),
        ("extratos_bancarios", "fk_extrato_conta_mesmo_cliente", '"conta_pagar_id", "cliente_id"', "contas_pagar", '"id", "cliente_id"'),
    )
    for args in tenant_fks:
        _add_not_valid_fk(*args)

    # Unicidade de orçamento somente se o legado já estiver consistente.
    duplicates = bind.execute(
        text(
            "SELECT 1 FROM orcamento_valores GROUP BY cliente_id, categoria_key, mes, ano "
            "HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if not duplicates:
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_orcamento_cliente_categoria_periodo "
            "ON orcamento_valores (cliente_id, categoria_key, mes, ano)"
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION flic_audit_event()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE
          row_data jsonb;
          actor_text text;
          request_text text;
        BEGIN
          row_data := CASE WHEN TG_OP = 'DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
          actor_text := current_setting('app.user_id', true);
          request_text := current_setting('app.request_id', true);
          INSERT INTO audit_events (
            table_name, operation, record_public_id, actor_id, database_role, request_id
          ) VALUES (
            TG_TABLE_NAME,
            TG_OP,
            NULLIF(row_data->>'public_id', '')::uuid,
            NULLIF(actor_text, '')::integer,
            current_user,
            NULLIF(request_text, '')::uuid
          );
          RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$
        """
    )
    for table in tables:
        if table == "logs_auditoria":
            continue
        op.execute(sa.text(f'DROP TRIGGER IF EXISTS "trg_{table}_audit" ON "{table}"'))
        op.execute(
            sa.text(
                f'CREATE TRIGGER "trg_{table}_audit" AFTER INSERT OR UPDATE OR DELETE '
                f'ON "{table}" FOR EACH ROW EXECUTE FUNCTION flic_audit_event()'
            )
        )

    runtime_role = _quoted_identifier(DATABASE_RUNTIME_ROLE)
    op.execute(f"REVOKE CREATE ON SCHEMA public FROM {runtime_role}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {runtime_role}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {runtime_role}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {runtime_role}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES GRANT SELECT, INSERT, UPDATE, DELETE "
        f"ON TABLES TO {runtime_role}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES GRANT USAGE, SELECT ON SEQUENCES TO {runtime_role}"
    )


def downgrade() -> None:
    raise RuntimeError("Hardening de segurança exige downgrade manual e revisado.")
