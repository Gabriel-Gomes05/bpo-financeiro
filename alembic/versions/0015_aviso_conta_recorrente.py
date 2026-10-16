"""Antecedência do alerta de vencimento nas contas a pagar recorrentes.

Revision ID: 0015_aviso_recorrente
Revises: 0014_tarefas
"""
import sqlalchemy as sa
from alembic import op

revision = "0015_aviso_recorrente"
down_revision = "0014_tarefas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contas_pagar", sa.Column("aviso_dias_antes", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_contas_pagar_aviso_dias_antes", "contas_pagar",
        "aviso_dias_antes IS NULL OR aviso_dias_antes BETWEEN 0 AND 30",
    )
    # Séries recorrentes já existentes passam a avisar com o padrão de 3 dias.
    op.execute("UPDATE contas_pagar SET aviso_dias_antes = 3 WHERE recorrencia_grupo_id IS NOT NULL")


def downgrade() -> None:
    op.drop_constraint("ck_contas_pagar_aviso_dias_antes", "contas_pagar", type_="check")
    op.drop_column("contas_pagar", "aviso_dias_antes")
