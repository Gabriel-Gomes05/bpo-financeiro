from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import (
    DATABASE_URL, DB_IDLE_TRANSACTION_TIMEOUT_MS, DB_MAX_OVERFLOW,
    DB_POOL_SIZE, DB_POOL_TIMEOUT_SECONDS, DB_SSL_MODE,
    DB_STATEMENT_TIMEOUT_MS,
)

_connect_args = {}
if DATABASE_URL.startswith("postgresql"):
    _connect_args = {
        "sslmode": DB_SSL_MODE,
        "application_name": "flic_web",
        "options": (
            f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS} "
            f"-c lock_timeout=10000 "
            f"-c idle_in_transaction_session_timeout={DB_IDLE_TRANSACTION_TIMEOUT_MS}"
        ),
        "connect_timeout": 10,
    }

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=900,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT_SECONDS,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def schema_esta_atualizado(connection) -> bool:
    """Confere se todas as tabelas e colunas mapeadas existem no banco."""
    from app import models  # noqa: F401

    inspector = inspect(connection)
    tabelas_existentes = set(inspector.get_table_names())
    for nome_tabela, tabela in Base.metadata.tables.items():
        if nome_tabela not in tabelas_existentes:
            return False
        colunas_existentes = {
            coluna["name"] for coluna in inspector.get_columns(nome_tabela)
        }
        colunas_modelo = {coluna.name for coluna in tabela.columns}
        if not colunas_modelo.issubset(colunas_existentes):
            return False
    return True


@event.listens_for(Session, "before_flush")
def _preencher_auditoria(session: Session, _flush_context, _instances) -> None:
    """Propaga ator e request ID para a auditoria de aplicação e banco."""
    actor_id = session.info.get("actor_id")
    if actor_id and session.bind and session.bind.dialect.name == "postgresql":
        session.connection().execute(
            text("SELECT set_config('app.user_id', :actor_id, true)"),
            {"actor_id": str(actor_id)},
        )
        request_id = session.info.get("request_id")
        if request_id:
            session.connection().execute(
                text("SELECT set_config('app.request_id', :request_id, true)"),
                {"request_id": str(request_id)},
            )
    for obj in session.new:
        if hasattr(obj, "created_by") and getattr(obj, "created_by", None) is None:
            obj.created_by = actor_id
        if hasattr(obj, "updated_by"):
            obj.updated_by = actor_id
    for obj in session.dirty:
        if hasattr(obj, "updated_by"):
            obj.updated_by = actor_id


def get_db():
    """Dependência do FastAPI — fornece sessão do banco e garante fechamento."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def criar_tabelas():
    """Cria todas as tabelas no banco se ainda não existirem."""
    from app.models import Base as ModelsBase  # importação local para evitar circular
    ModelsBase.metadata.create_all(bind=engine)


def migrar_schema():
    """Adiciona colunas novas em tabelas existentes (idempotente)."""
    from sqlalchemy import text
    from app.constants import GRUPOS_DRE
    from app.field_encryption import SENSITIVE_FIELDS, encrypt_value, is_encrypted
    with engine.connect() as conn:
        conn.execute(text("ALTER TYPE perfilusuario ADD VALUE IF NOT EXISTS 'editor'"))
        conn.execute(text("ALTER TYPE perfilusuario ADD VALUE IF NOT EXISTS 'secretaria'"))
        conn.execute(text("ALTER TYPE perfilusuario ADD VALUE IF NOT EXISTS 'medico'"))
        conn.execute(text(
            "ALTER TABLE contas_pagar ADD COLUMN IF NOT EXISTS categoria_dre VARCHAR(60)"
        ))
        conn.execute(text(
            "ALTER TABLE clientes_bpo ADD COLUMN IF NOT EXISTS rede_maquininha VARCHAR(50)"
        ))
        conn.execute(text(
            "ALTER TABLE movimentacoes_bancarias "
            "ADD COLUMN IF NOT EXISTS sentido VARCHAR(15) NOT NULL DEFAULT 'recebimento'"
        ))
        conn.execute(text(
            "ALTER TABLE movimentacoes_bancarias "
            "ADD COLUMN IF NOT EXISTS conta_pagar_id INTEGER REFERENCES contas_pagar(id)"
        ))
        conn.execute(text(
            "ALTER TABLE movimentacoes_bancarias "
            "ADD COLUMN IF NOT EXISTS conta_bancaria_id INTEGER REFERENCES contas_bancarias(id)"
        ))
        conn.execute(text(
            "ALTER TABLE movimentacoes_bancarias ADD COLUMN IF NOT EXISTS identificador_externo VARCHAR(120)"
        ))
        conn.execute(text(
            "ALTER TABLE movimentacoes_bancarias ADD COLUMN IF NOT EXISTS origem_manual BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_mov_banco_fitid "
            "ON movimentacoes_bancarias (conta_bancaria_id, identificador_externo) "
            "WHERE conta_bancaria_id IS NOT NULL AND identificador_externo IS NOT NULL"
        ))
        conn.execute(text(
            "ALTER TABLE contas_bancarias ADD COLUMN IF NOT EXISTS saldo_atual NUMERIC(14,2)"
        ))
        conn.execute(text(
            "ALTER TABLE contas_bancarias ADD COLUMN IF NOT EXISTS saldo_data_referencia TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE contas_bancarias ADD COLUMN IF NOT EXISTS saldo_atualizado_em TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE extratos_bancarios "
            "ADD COLUMN IF NOT EXISTS conta_pagar_id INTEGER REFERENCES contas_pagar(id)"
        ))
        conn.execute(text(
            "ALTER TABLE movimentacoes_bancarias "
            "ADD COLUMN IF NOT EXISTS cpf_digitos_meio VARCHAR(6)"
        ))
        conn.execute(text(
            "ALTER TABLE clientes_bpo "
            "ADD COLUMN IF NOT EXISTS tem_maquininha BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text(
            "ALTER TABLE clientes_bpo "
            "ADD COLUMN IF NOT EXISTS antecipa BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text(
            "ALTER TABLE taxas_cartao_cliente "
            "ADD COLUMN IF NOT EXISTS faixa_parcelamento VARCHAR(20) NOT NULL DEFAULT 'avista'"
        ))
        conn.execute(text(
            "ALTER TABLE taxas_cartao_cliente ADD COLUMN IF NOT EXISTS parcela_inicial INTEGER"
        ))
        conn.execute(text(
            "ALTER TABLE taxas_cartao_cliente ADD COLUMN IF NOT EXISTS parcela_final INTEGER"
        ))
        conn.execute(text(
            "ALTER TABLE taxas_cartao_cliente "
            "ADD COLUMN IF NOT EXISTS maquininha_id INTEGER REFERENCES maquininhas_cliente(id)"
        ))
        conn.execute(text(
            "ALTER TABLE movimentacoes_bancarias "
            "ADD COLUMN IF NOT EXISTS transferencia_cartao_id INTEGER REFERENCES transferencias_cartao(id)"
        ))
        conn.execute(text(
            "ALTER TABLE movimentacoes_bancarias "
            "ADD COLUMN IF NOT EXISTS arquivado_conciliacao_banco BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text(
            "ALTER TABLE atendimentos "
            "ADD COLUMN IF NOT EXISTS arquivado_conciliacao_banco BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text(
            "ALTER TABLE contas_pagar "
            "ADD COLUMN IF NOT EXISTS arquivado_conciliacao_banco BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pagamentos_parciais_contas_pagar (
                id SERIAL PRIMARY KEY,
                conta_pagar_id INTEGER NOT NULL REFERENCES contas_pagar(id) ON DELETE CASCADE,
                movimentacao_id INTEGER UNIQUE REFERENCES movimentacoes_bancarias(id),
                valor NUMERIC(12,2) NOT NULL,
                data_pagamento DATE NOT NULL,
                observacao TEXT,
                criado_por_id INTEGER REFERENCES usuarios(id),
                criado_em TIMESTAMP DEFAULT now() NOT NULL
            )
        """))
        conn.execute(text("ALTER TYPE statuscontapagar ADD VALUE IF NOT EXISTS 'agendado'"))
        # Enum e tabela de vendas de cartão (maquininha)
        conn.execute(text(
            "DO $$ BEGIN "
            "  CREATE TYPE statusvendacartao AS ENUM ('pendente','conciliado','fechado','cancelado'); "
            "EXCEPTION WHEN duplicate_object THEN NULL; "
            "END $$;"
        ))
        conn.execute(text(
            "ALTER TYPE statusvendacartao ADD VALUE IF NOT EXISTS 'conciliado'"
        ))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vendas_cartao (
                id SERIAL PRIMARY KEY,
                cliente_id INTEGER NOT NULL REFERENCES clientes_bpo(id),
                data_venda DATE NOT NULL,
                data_pagamento DATE NOT NULL,
                bandeira VARCHAR(50),
                ultimos_digitos VARCHAR(4),
                nome_portador VARCHAR(150),
                valor_bruto NUMERIC(12,2) NOT NULL,
                taxa_percentual NUMERIC(5,2),
                valor_liquido NUMERIC(12,2),
                parcelas INTEGER DEFAULT 1,
                descricao VARCHAR(255),
                status statusvendacartao NOT NULL DEFAULT 'pendente',
                atendimento_id INTEGER REFERENCES atendimentos(id),
                lote_id INTEGER REFERENCES transferencias_cartao(id),
                origem_arquivo VARCHAR(255),
                criado_em TIMESTAMP DEFAULT now() NOT NULL
            )
        """))
        conn.execute(text(
            "ALTER TABLE vendas_cartao "
            "ADD COLUMN IF NOT EXISTS atendimento_id INTEGER REFERENCES atendimentos(id)"
        ))
        # Migra maquininhas únicas existentes para a nova tabela
        conn.execute(text("""
            INSERT INTO maquininhas_cliente (cliente_id, rede, antecipa, ativa)
            SELECT id, rede_maquininha, antecipa, true
            FROM clientes_bpo
            WHERE tem_maquininha = true
              AND rede_maquininha IS NOT NULL
              AND id NOT IN (SELECT DISTINCT cliente_id FROM maquininhas_cliente)
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS centros_custo (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(150) NOT NULL,
                cliente_id INTEGER NOT NULL REFERENCES clientes_bpo(id),
                ativo BOOLEAN NOT NULL DEFAULT true,
                criado_em TIMESTAMP DEFAULT now() NOT NULL
            )
        """))
        conn.execute(text(
            "ALTER TABLE atendimentos ADD COLUMN IF NOT EXISTS centro_custo_id INTEGER REFERENCES centros_custo(id)"
        ))
        conn.execute(text(
            "ALTER TABLE centros_custo ADD COLUMN IF NOT EXISTS codigo VARCHAR(30)"
        ))
        conn.execute(text(
            "ALTER TABLE centros_custo ADD COLUMN IF NOT EXISTS is_medico BOOLEAN NOT NULL DEFAULT false"
        ))
        conn.execute(text(
            "ALTER TABLE centros_custo ADD COLUMN IF NOT EXISTS especialidade VARCHAR(100)"
        ))
        conn.execute(text(
            "ALTER TABLE contas_pagar ADD COLUMN IF NOT EXISTS especialidade VARCHAR(100)"
        ))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS atendimentos_centros_custo_rateio (
                id SERIAL PRIMARY KEY,
                atendimento_id INTEGER NOT NULL REFERENCES atendimentos(id) ON DELETE CASCADE,
                centro_custo_id INTEGER NOT NULL REFERENCES centros_custo(id),
                percentual NUMERIC(5,2) NOT NULL,
                valor NUMERIC(12,2) NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS contas_pagar_centros_custo_rateio (
                id SERIAL PRIMARY KEY,
                conta_pagar_id INTEGER NOT NULL REFERENCES contas_pagar(id) ON DELETE CASCADE,
                centro_custo_id INTEGER NOT NULL REFERENCES centros_custo(id),
                categoria_key VARCHAR(60) NOT NULL,
                percentual NUMERIC(5,2) NOT NULL,
                valor NUMERIC(12,2) NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS anotacoes_clientes (
                id SERIAL PRIMARY KEY,
                cliente_id INTEGER NOT NULL REFERENCES clientes_bpo(id) ON DELETE CASCADE,
                autor_id INTEGER REFERENCES usuarios(id),
                categoria VARCHAR(50) NOT NULL DEFAULT 'procedimento',
                titulo VARCHAR(150) NOT NULL,
                conteudo TEXT NOT NULL,
                criado_em TIMESTAMP DEFAULT now() NOT NULL,
                atualizado_em TIMESTAMP DEFAULT now() NOT NULL
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_anotacoes_clientes_cliente_id "
            "ON anotacoes_clientes (cliente_id)"
        ))
        # Converte os campos protegidos para TEXT e cifra o legado em uma unica
        # transacao. A migracao e retomavel: valores ja cifrados nao sao tocados.
        for tabela, coluna, contexto, deterministico in SENSITIVE_FIELDS:
            conn.execute(text(
                f'ALTER TABLE "{tabela}" ALTER COLUMN "{coluna}" TYPE TEXT'
            ))
            registros = conn.execute(text(
                f'SELECT id, "{coluna}" FROM "{tabela}" '
                f'WHERE "{coluna}" IS NOT NULL AND "{coluna}" <> \'\''
            )).all()
            for registro_id, valor in registros:
                if is_encrypted(valor):
                    continue
                cifrado = encrypt_value(valor, contexto, deterministico)
                conn.execute(
                    text(f'UPDATE "{tabela}" SET "{coluna}" = :valor WHERE id = :id'),
                    {"valor": cifrado, "id": registro_id},
                )
        # Plano de contas global (fallback quando o cliente nao tem centro de custo proprio)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS planos_conta (
                id SERIAL PRIMARY KEY,
                tipo VARCHAR(10) NOT NULL,
                grupo VARCHAR(80) NOT NULL,
                chave VARCHAR(60) NOT NULL,
                codigo VARCHAR(30),
                nome VARCHAR(150) NOT NULL,
                cliente_id INTEGER REFERENCES clientes_bpo(id),
                ativo BOOLEAN NOT NULL DEFAULT true,
                criado_em TIMESTAMP DEFAULT now() NOT NULL
            )
        """))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_planos_conta_chave_global "
            "ON planos_conta (chave) WHERE cliente_id IS NULL"
        ))
        conn.execute(text(
            "ALTER TABLE contas_pagar ADD COLUMN IF NOT EXISTS plano_conta_id INTEGER REFERENCES planos_conta(id)"
        ))
        conn.execute(text(
            "ALTER TABLE atendimentos ADD COLUMN IF NOT EXISTS plano_conta_id INTEGER REFERENCES planos_conta(id)"
        ))
        conn.execute(text(
            "ALTER TABLE contas_pagar ADD COLUMN IF NOT EXISTS data_competencia DATE"
        ))
        conn.execute(text(
            "ALTER TABLE contas_pagar ADD COLUMN IF NOT EXISTS forma_pagamento formapagamento"
        ))
        conn.execute(text(
            "ALTER TABLE contas_pagar ADD COLUMN IF NOT EXISTS recorrencia_intervalo VARCHAR(20)"
        ))
        conn.execute(text(
            "ALTER TABLE contas_pagar ADD COLUMN IF NOT EXISTS recorrencia_grupo_id INTEGER REFERENCES contas_pagar(id)"
        ))
        conn.execute(text(
            "ALTER TABLE contas_pagar ADD COLUMN IF NOT EXISTS recorrencia_dias INTEGER"
        ))
        # Semeia o plano de contas global a partir das categorias estaticas de GRUPOS_DRE
        for grupo in GRUPOS_DRE:
            for categoria in grupo["categorias"]:
                conn.execute(text("""
                    INSERT INTO planos_conta (tipo, grupo, chave, nome, ativo)
                    SELECT :tipo, :grupo, :chave, :nome, true
                    WHERE NOT EXISTS (
                        SELECT 1 FROM planos_conta WHERE chave = :chave AND cliente_id IS NULL
                    )
                """), {
                    "tipo": grupo["tipo"],
                    "grupo": grupo["nome"],
                    "chave": categoria["key"],
                    "nome": categoria["nome"],
                })
        # Backfill: liga contas a pagar existentes ao plano de contas semeado, quando
        # a categoria_dre bater com uma chave global (nao mexe em chaves de rateio,
        # que sao codigos/ids de centro de custo, nao chaves de GRUPOS_DRE).
        conn.execute(text("""
            UPDATE contas_pagar cp SET plano_conta_id = pc.id
            FROM planos_conta pc
            WHERE pc.cliente_id IS NULL AND pc.chave = cp.categoria_dre
              AND cp.plano_conta_id IS NULL
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS grupos_empresariais (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(150) NOT NULL,
                ativo BOOLEAN NOT NULL DEFAULT true,
                criado_em TIMESTAMP DEFAULT now() NOT NULL
            )
        """))
        conn.execute(text(
            "ALTER TABLE clientes_bpo ADD COLUMN IF NOT EXISTS grupo_empresarial_id "
            "INTEGER REFERENCES grupos_empresariais(id) ON DELETE SET NULL"
        ))
        conn.execute(text(
            "ALTER TABLE grupos_empresariais ADD COLUMN IF NOT EXISTS funcionario_id INTEGER REFERENCES usuarios(id)"
        ))
        conn.execute(text("ALTER TYPE formapagamento ADD VALUE IF NOT EXISTS 'boleto'"))
        conn.execute(text("ALTER TYPE formapagamento ADD VALUE IF NOT EXISTS 'cheque'"))
        conn.execute(text("ALTER TYPE formapagamento ADD VALUE IF NOT EXISTS 'debito_automatico'"))
        conn.execute(text("ALTER TYPE formapagamento ADD VALUE IF NOT EXISTS 'cartao_debito'"))
        # Impede que novos papeis ganhem acesso implicito ao schema/banco.
        conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        conn.execute(text("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC"))
        conn.execute(text("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC"))
        conn.execute(text("ALTER DEFAULT PRIVILEGES REVOKE ALL ON TABLES FROM PUBLIC"))
        conn.execute(text("ALTER DEFAULT PRIVILEGES REVOKE ALL ON SEQUENCES FROM PUBLIC"))
        conn.commit()
