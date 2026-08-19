from app.field_encryption import EncryptedText
from app.models import (
    Atendimento,
    CentroCusto,
    ClienteBPO,
    LogAuditoria,
    MovimentacaoBancaria,
    TarefaRotina,
    Usuario,
)


def test_basic_registration_fields_are_plaintext() -> None:
    plaintext_columns = (
        Usuario.__table__.c.nome,
        Usuario.__table__.c.email,
        ClienteBPO.__table__.c.nome,
        ClienteBPO.__table__.c.razao_social,
        ClienteBPO.__table__.c.cnpj,
        CentroCusto.__table__.c.nome,
        TarefaRotina.__table__.c.descricao,
        LogAuditoria.__table__.c.usuario_nome,
        LogAuditoria.__table__.c.cliente_nome,
    )

    assert all(
        not isinstance(column.type, EncryptedText)
        for column in plaintext_columns
    )


def test_clinical_banking_and_financial_fields_remain_encrypted() -> None:
    encrypted_columns = (
        ClienteBPO.__table__.c.banco,
        ClienteBPO.__table__.c.agencia,
        ClienteBPO.__table__.c.conta,
        Atendimento.__table__.c.nome_paciente,
        Atendimento.__table__.c.cpf_paciente,
        MovimentacaoBancaria.__table__.c.identificador_externo,
        MovimentacaoBancaria.__table__.c.descricao,
    )

    assert all(
        isinstance(column.type, EncryptedText)
        for column in encrypted_columns
    )
