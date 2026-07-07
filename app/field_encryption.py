"""Criptografia autenticada para campos sensiveis persistidos pelo SQLAlchemy."""
from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESSIV
from sqlalchemy.types import Text, TypeDecorator


PREFIX = "enc:v1:"

# Campos que devem existir apenas cifrados no PostgreSQL. O booleano final
# indica criptografia deterministica, reservada a igualdade/UNIQUE.
SENSITIVE_FIELDS = (
    ("usuarios", "nome", "usuarios.nome", False),
    ("usuarios", "email", "usuarios.email", True),
    ("clientes_bpo", "nome", "clientes_bpo.nome", False),
    ("clientes_bpo", "razao_social", "clientes_bpo.razao_social", False),
    ("clientes_bpo", "cnpj", "clientes_bpo.cnpj", True),
    ("clientes_bpo", "banco", "clientes_bpo.banco", False),
    ("clientes_bpo", "agencia", "clientes_bpo.agencia", False),
    ("clientes_bpo", "conta", "clientes_bpo.conta", False),
    ("centros_custo", "nome", "centros_custo.nome", False),
    ("atendimentos", "nome_paciente", "atendimentos.nome_paciente", False),
    ("atendimentos", "cpf_paciente", "atendimentos.cpf_paciente", True),
    ("atendimentos", "medico", "atendimentos.medico", False),
    ("atendimentos", "descricao_servico", "atendimentos.descricao_servico", False),
    ("atendimentos", "ultimos_digitos_cartao", "atendimentos.ultimos_digitos_cartao", True),
    ("atendimentos", "banco_recebimento", "atendimentos.banco_recebimento", False),
    ("atendimentos", "observacao", "atendimentos.observacao", False),
    ("contas_pagar", "descricao", "contas_pagar.descricao", False),
    ("contas_pagar", "fornecedor", "contas_pagar.fornecedor", False),
    ("contas_pagar", "documento_path", "contas_pagar.documento_path", False),
    ("contas_pagar", "observacao", "contas_pagar.observacao", False),
    ("pagamentos_parciais_contas_pagar", "observacao", "pagamentos_parciais_contas_pagar.observacao", False),
    ("fechamentos_diarios", "observacao", "fechamentos_diarios.observacao", False),
    ("tarefas_rotina", "descricao", "tarefas_rotina.descricao", False),
    ("divergencias_conciliacao", "motivo", "divergencias_conciliacao.motivo", False),
    ("movimentacoes_bancarias", "identificador_externo", "movimentacoes_bancarias.identificador_externo", True),
    ("movimentacoes_bancarias", "descricao", "movimentacoes_bancarias.descricao", False),
    ("movimentacoes_bancarias", "digitos_cartao", "movimentacoes_bancarias.digitos_cartao", True),
    ("movimentacoes_bancarias", "cpf_digitos_meio", "movimentacoes_bancarias.cpf_digitos_meio", True),
    ("movimentacoes_bancarias", "origem_arquivo", "movimentacoes_bancarias.origem_arquivo", False),
    ("contas_bancarias", "banco", "contas_bancarias.banco", False),
    ("contas_bancarias", "agencia", "contas_bancarias.agencia", False),
    ("contas_bancarias", "conta", "contas_bancarias.conta", False),
    ("extratos_bancarios", "descricao", "extratos_bancarios.descricao", False),
    ("extratos_bancarios", "origem_arquivo", "extratos_bancarios.origem_arquivo", False),
    ("regras_auto_match", "padrao_descricao", "regras_auto_match.padrao_descricao", False),
    ("contas_recorrentes", "descricao", "contas_recorrentes.descricao", False),
    ("contas_recorrentes", "fornecedor", "contas_recorrentes.fornecedor", False),
    ("contas_recorrentes", "email_destino", "contas_recorrentes.email_destino", True),
    ("vendas_cartao", "ultimos_digitos", "vendas_cartao.ultimos_digitos", True),
    ("vendas_cartao", "nome_portador", "vendas_cartao.nome_portador", False),
    ("vendas_cartao", "descricao", "vendas_cartao.descricao", False),
    ("vendas_cartao", "origem_arquivo", "vendas_cartao.origem_arquivo", False),
    ("logs_auditoria", "usuario_nome", "logs_auditoria.usuario_nome", False),
    ("logs_auditoria", "cliente_nome", "logs_auditoria.cliente_nome", False),
    ("logs_auditoria", "detalhes", "logs_auditoria.detalhes", False),
    ("logs_auditoria", "ip", "logs_auditoria.ip", False),
    ("anotacoes_clientes", "titulo", "anotacoes_clientes.titulo", False),
    ("anotacoes_clientes", "conteudo", "anotacoes_clientes.conteudo", False),
)


class FieldEncryptionError(RuntimeError):
    """Indica chave inválida, formato desconhecido ou falha de integridade."""

    pass


@lru_cache(maxsize=1)
def _key() -> bytes:
    """Carrega e valida a chave de 64 bytes, mantendo-a em cache no processo."""
    from app.config import FIELD_ENCRYPTION_KEY
    encoded = FIELD_ENCRYPTION_KEY
    if not encoded:
        raise FieldEncryptionError(
            "FIELD_ENCRYPTION_KEY nao configurada. Execute scripts/setup_encryption_key.py."
        )
    try:
        key = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception as exc:
        raise FieldEncryptionError("FIELD_ENCRYPTION_KEY nao e Base64 valida.") from exc
    if len(key) != 64:
        raise FieldEncryptionError("FIELD_ENCRYPTION_KEY deve representar exatamente 64 bytes.")
    return key


def is_encrypted(value: object) -> bool:
    """Informa se o valor usa o envelope versionado de criptografia do projeto."""
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_value(value: object, context: str, deterministic: bool = False) -> str | None:
    """Cifra um valor com contexto autenticado e retorna texto seguro para persistência."""
    if value is None:
        return None
    text = str(value)
    if text == "" or is_encrypted(text):
        return text
    data = text.encode("utf-8")
    aad = [context.encode("utf-8")]
    if deterministic:
        encrypted = AESSIV(_key()).encrypt(data, aad)
        mode = "d"
    else:
        nonce = os.urandom(12)
        encrypted = nonce + AESGCM(_key()[:32]).encrypt(nonce, data, aad[0])
        mode = "r"
    token = base64.urlsafe_b64encode(encrypted).decode("ascii")
    return f"{PREFIX}{mode}:{token}"


def decrypt_value(value: object, context: str) -> str | None:
    """Valida e decifra um valor; aceita plaintext somente para migração de legado."""
    if value is None:
        return None
    text = str(value)
    if text == "" or not is_encrypted(text):
        return text  # compatibilidade apenas durante a migracao de dados legados
    try:
        _, _, mode, token = text.split(":", 3)
        encrypted = base64.urlsafe_b64decode(token.encode("ascii"))
        aad = context.encode("utf-8")
        if mode == "d":
            return AESSIV(_key()).decrypt(encrypted, [aad]).decode("utf-8")
        if mode == "r":
            nonce, ciphertext = encrypted[:12], encrypted[12:]
            return AESGCM(_key()[:32]).decrypt(nonce, ciphertext, aad).decode("utf-8")
    except (ValueError, InvalidTag, UnicodeDecodeError) as exc:
        raise FieldEncryptionError(f"Falha de integridade ao descriptografar {context}.") from exc
    raise FieldEncryptionError(f"Formato criptografado desconhecido em {context}.")


class EncryptedText(TypeDecorator):
    """TEXT criptografado; modo deterministico permite igualdade/UNIQUE."""

    impl = Text
    cache_ok = True

    def __init__(self, context: str, *, deterministic: bool = False, **kwargs):
        """Configura o contexto da coluna e se ela precisa permitir comparação exata."""
        super().__init__(**kwargs)
        self.context = context
        self.deterministic = deterministic

    def process_bind_param(self, value, dialect):
        """Cifra valores automaticamente antes de enviá-los ao banco."""
        return encrypt_value(value, self.context, self.deterministic)

    def process_result_value(self, value, dialect):
        """Decifra valores automaticamente ao materializar um objeto ORM."""
        return decrypt_value(value, self.context)
