"""Perfil secretária vinculado a um cliente e histórico imutável de alterações.

Revision ID: 0016_secretaria_historico
Revises: 0015_aviso_recorrente
"""
import re

import sqlalchemy as sa
from alembic import op

from app.config import DATABASE_RUNTIME_ROLE

revision = "0016_secretaria_historico"
down_revision = "0015_aviso_recorrente"
branch_labels = None
depends_on = None


def _quoted_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", value):
        raise RuntimeError("DATABASE_RUNTIME_ROLE contém identificador inválido.")
    return f'"{value}"'


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes_bpo.id"), nullable=True))
    op.create_index("ix_usuarios_cliente_id", "usuarios", ["cliente_id"])
    # NOT VALID: secretárias antigas sem cliente continuam no banco (o login delas é
    # bloqueado com FLIC-AUT-010), mas qualquer gravação nova já exige o vínculo.
    op.execute(
        "ALTER TABLE usuarios ADD CONSTRAINT ck_usuarios_secretaria_cliente "
        "CHECK (perfil::text <> 'secretaria' OR cliente_id IS NOT NULL) NOT VALID"
    )

    op.create_table(
        "historico_alteracoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operacao_id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("usuario_nome", sa.Text(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("cliente_nome", sa.Text(), nullable=True),
        sa.Column("acao", sa.String(30), nullable=False),
        sa.Column("modulo", sa.String(50), nullable=False),
        sa.Column("entidade", sa.String(60), nullable=False),
        sa.Column("entidade_id", sa.Integer(), nullable=True),
        sa.Column("campo", sa.String(80), nullable=True),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_novo", sa.Text(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for coluna in ("operacao_id", "usuario_id", "cliente_id", "criado_em"):
        op.create_index(f"ix_historico_alteracoes_{coluna}", "historico_alteracoes", [coluna])
    op.create_index("ix_historico_alteracoes_entidade", "historico_alteracoes", ["entidade", "entidade_id"])

    # Imutável para qualquer papel do banco (inclusive o dono): só INSERT é aceito.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION flic_historico_imutavel()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'historico_alteracoes é imutável (operação % bloqueada)', TG_OP
            USING ERRCODE = 'insufficient_privilege';
        END;
        $$
        """
    )
    op.execute(
        'CREATE TRIGGER "trg_historico_alteracoes_imutavel" BEFORE UPDATE OR DELETE '
        'ON "historico_alteracoes" FOR EACH ROW EXECUTE FUNCTION flic_historico_imutavel()'
    )
    op.execute(
        'CREATE TRIGGER "trg_historico_alteracoes_sem_truncate" BEFORE TRUNCATE '
        'ON "historico_alteracoes" FOR EACH STATEMENT EXECUTE FUNCTION flic_historico_imutavel()'
    )
    runtime_role = _quoted_identifier(DATABASE_RUNTIME_ROLE)
    existe = op.get_bind().execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :nome"), {"nome": DATABASE_RUNTIME_ROLE}
    ).first()
    if existe:
        op.execute(f"GRANT SELECT, INSERT ON historico_alteracoes TO {runtime_role}")
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON historico_alteracoes FROM {runtime_role}")
        op.execute(f"GRANT USAGE, SELECT ON SEQUENCE historico_alteracoes_id_seq TO {runtime_role}")


def downgrade() -> None:
    op.drop_table("historico_alteracoes")
    op.execute("DROP FUNCTION IF EXISTS flic_historico_imutavel()")
    op.drop_constraint("ck_usuarios_secretaria_cliente", "usuarios", type_="check")
    op.drop_index("ix_usuarios_cliente_id", table_name="usuarios")
    op.drop_column("usuarios", "cliente_id")
