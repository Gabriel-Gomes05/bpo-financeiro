"""Completa o plano de contas e recorrencia em bancos legados.

Revision ID: 0005_legacy_plano_contas
Revises: 0004_legacy_grupo_empresarial
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "0005_legacy_plano_contas"
down_revision = "0004_legacy_grupo_empresarial"
branch_labels = None
depends_on = None

PLANOS_GLOBAIS = (
    ("receita", "RECEITAS", "rec_consultas", "Consultas Médicas"),
    ("receita", "RECEITAS", "rec_procedimentos", "Procedimentos"),
    ("receita", "RECEITAS", "rec_exames", "Exames"),
    ("receita", "RECEITAS", "rec_convenios", "Convênios"),
    ("receita", "RECEITAS", "rec_outros", "Outros Recebimentos"),
    ("despesa", "CUSTOS VARIÁVEIS", "cv_material", "Material Médico / Hospitalar"),
    ("despesa", "CUSTOS VARIÁVEIS", "cv_terceiros", "Exames Terceirizados"),
    ("despesa", "CUSTOS VARIÁVEIS", "cv_honorarios", "Honorários Médicos"),
    ("despesa", "DESPESAS FIXAS", "df_aluguel", "Aluguel"),
    ("despesa", "DESPESAS FIXAS", "df_folha", "Folha de Pagamento"),
    ("despesa", "DESPESAS FIXAS", "df_encargos", "Encargos Sociais"),
    ("despesa", "DESPESAS FIXAS", "df_energia", "Energia Elétrica"),
    ("despesa", "DESPESAS FIXAS", "df_agua", "Água e Esgoto"),
    ("despesa", "DESPESAS FIXAS", "df_internet", "Internet e Telefone"),
    ("despesa", "DESPESAS FIXAS", "df_manutencao", "Manutenção"),
    ("despesa", "DESPESAS FIXAS", "df_limpeza", "Limpeza e Higiene"),
    ("despesa", "DESPESAS ADMINISTRATIVAS", "da_contabil", "Honorários Contábeis"),
    ("despesa", "DESPESAS ADMINISTRATIVAS", "da_impostos", "Impostos e Taxas"),
    ("despesa", "DESPESAS ADMINISTRATIVAS", "da_software", "Software e Sistemas"),
    ("despesa", "DESPESAS ADMINISTRATIVAS", "da_marketing", "Marketing"),
    ("despesa", "DESPESAS ADMINISTRATIVAS", "da_seguros", "Seguros"),
    ("despesa", "DESPESAS ADMINISTRATIVAS", "da_outros", "Outros"),
)


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _foreign_key_exists(table: str, column: str, remote_table: str) -> bool:
    return any(
        foreign_key.get("constrained_columns") == [column]
        and foreign_key.get("referred_table") == remote_table
        for foreign_key in inspect(op.get_bind()).get_foreign_keys(table)
    )


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def _add_fk(table: str, column: str, remote_table: str, *, ondelete: str | None = None) -> None:
    if not _foreign_key_exists(table, column, remote_table):
        op.create_foreign_key(
            f"fk_{table}_{column}_{remote_table}",
            table,
            remote_table,
            [column],
            ["id"],
            ondelete=ondelete,
        )


def _create_planos_conta() -> None:
    if "planos_conta" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "planos_conta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("grupo", sa.String(length=80), nullable=False),
        sa.Column("chave", sa.String(length=60), nullable=False),
        sa.Column("codigo", sa.String(length=30), nullable=True),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
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
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes_bpo.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["usuarios.id"]),
        sa.UniqueConstraint("public_id", name="uq_planos_conta_public_id"),
    )
    op.create_index("ix_planos_conta_deleted_at", "planos_conta", ["deleted_at"])
    op.create_index("ix_planos_conta_cliente_id", "planos_conta", ["cliente_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_planos_conta_chave_global ON planos_conta (chave) "
        "WHERE cliente_id IS NULL"
    )
    op.execute(
        'CREATE TRIGGER "trg_planos_conta_updated_at" BEFORE UPDATE ON "planos_conta" '
        "FOR EACH ROW EXECUTE FUNCTION flic_set_updated_at()"
    )
    op.execute(
        'CREATE TRIGGER "trg_planos_conta_audit" AFTER INSERT OR UPDATE OR DELETE '
        'ON "planos_conta" FOR EACH ROW EXECUTE FUNCTION flic_audit_event()'
    )


def upgrade() -> None:
    _create_planos_conta()

    for value in ("boleto", "cheque", "debito_automatico"):
        op.execute(f"ALTER TYPE formapagamento ADD VALUE IF NOT EXISTS '{value}'")

    _add_column("atendimentos", sa.Column("plano_conta_id", sa.Integer(), nullable=True))
    _add_fk("atendimentos", "plano_conta_id", "planos_conta")

    _add_column("contas_pagar", sa.Column("data_competencia", sa.Date(), nullable=True))
    _add_column(
        "contas_pagar",
        sa.Column(
            "forma_pagamento",
            postgresql.ENUM(name="formapagamento", create_type=False),
            nullable=True,
        ),
    )
    _add_column("contas_pagar", sa.Column("plano_conta_id", sa.Integer(), nullable=True))
    _add_fk("contas_pagar", "plano_conta_id", "planos_conta")
    _add_column("contas_pagar", sa.Column("recorrencia_intervalo", sa.String(20), nullable=True))
    _add_column("contas_pagar", sa.Column("recorrencia_dias", sa.Integer(), nullable=True))
    _add_column("contas_pagar", sa.Column("recorrencia_grupo_id", sa.Integer(), nullable=True))
    _add_fk("contas_pagar", "recorrencia_grupo_id", "contas_pagar")

    for tipo, grupo, chave, nome in PLANOS_GLOBAIS:
        op.execute(
            sa.text(
                "INSERT INTO planos_conta (tipo, grupo, chave, nome, ativo) "
                "VALUES (:tipo, :grupo, :chave, :nome, true) "
                "ON CONFLICT (chave) WHERE cliente_id IS NULL DO NOTHING"
            ).bindparams(tipo=tipo, grupo=grupo, chave=chave, nome=nome)
        )

    op.execute(
        "UPDATE contas_pagar AS cp SET plano_conta_id = pc.id "
        "FROM planos_conta AS pc "
        "WHERE pc.cliente_id IS NULL AND pc.chave = cp.categoria_dre "
        "AND cp.plano_conta_id IS NULL"
    )


def downgrade() -> None:
    raise RuntimeError("A migration de compatibilidade exige downgrade manual e revisado.")
