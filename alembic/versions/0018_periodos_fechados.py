"""Fechamento de período com extrato bancário (PDF) obrigatório.

Revision ID: 0018_periodos_fechados
Revises: 0017_tipos_conta_bancaria
"""
import sqlalchemy as sa
from alembic import op

revision = "0018_periodos_fechados"
down_revision = "0017_tipos_conta_bancaria"
branch_labels = None
depends_on = None


def _colunas_auditoria():
    return [
        sa.Column("public_id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
    ]


def _indices_e_triggers(tabela: str) -> None:
    op.create_index(f"ix_{tabela}_id", tabela, ["id"])
    op.create_index(f"ix_{tabela}_public_id", tabela, ["public_id"], unique=True)
    op.create_index(f"ix_{tabela}_deleted_at", tabela, ["deleted_at"])
    op.execute(f'CREATE TRIGGER "trg_{tabela}_updated_at" BEFORE UPDATE ON "{tabela}" '
               "FOR EACH ROW EXECUTE FUNCTION flic_set_updated_at()")
    op.execute(f'CREATE TRIGGER "trg_{tabela}_audit" AFTER INSERT OR UPDATE OR DELETE '
               f'ON "{tabela}" FOR EACH ROW EXECUTE FUNCTION flic_audit_event()')


def upgrade() -> None:
    op.create_table(
        "periodos_fechados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes_bpo.id"), nullable=False),
        sa.Column("data_inicio", sa.Date(), nullable=False),
        sa.Column("data_fim", sa.Date(), nullable=False),
        sa.Column("total_receitas", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_despesas", sa.Numeric(14, 2), nullable=False),
        sa.Column("resultado", sa.Numeric(14, 2), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("fechado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("fechado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        *_colunas_auditoria(),
        sa.CheckConstraint("data_fim >= data_inicio", name="ck_periodos_fechados_datas"),
    )
    op.create_index("ix_periodos_fechados_cliente_id", "periodos_fechados", ["cliente_id"])
    _indices_e_triggers("periodos_fechados")

    op.create_table(
        "extratos_periodos_fechados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("periodo_id", sa.Integer(), sa.ForeignKey("periodos_fechados.id"), nullable=False),
        sa.Column("conta_bancaria_id", sa.Integer(), sa.ForeignKey("contas_bancarias.id"), nullable=True),
        sa.Column("nome_arquivo", sa.String(255), nullable=False),
        sa.Column("caminho", sa.Text(), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=False),
        sa.Column("enviado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        *_colunas_auditoria(),
    )
    op.create_index("ix_extratos_periodos_fechados_periodo_id", "extratos_periodos_fechados", ["periodo_id"])
    _indices_e_triggers("extratos_periodos_fechados")


def downgrade() -> None:
    op.drop_table("extratos_periodos_fechados")
    op.drop_table("periodos_fechados")
