from datetime import datetime, date
from decimal import Decimal
from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text, Enum, Uuid, func
)
from sqlalchemy.orm import declared_attr, relationship

from app.database import Base
from app.field_encryption import EncryptedText


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PerfilUsuario(str, PyEnum):
    coordenador = "coordenador"
    editor = "editor"
    funcionario = "funcionario"
    secretaria = "secretaria"
    medico = "medico"


class CondicaoPagamento(str, PyEnum):
    avista = "avista"
    parcelado = "parcelado"
    pix = "pix"
    transferencia = "transferencia"
    dinheiro = "dinheiro"


class FormaPagamento(str, PyEnum):
    cartao_credito = "cartao_credito"
    pix = "pix"
    transferencia = "transferencia"
    dinheiro = "dinheiro"


class StatusConciliacao(str, PyEnum):
    pendente = "pendente"
    conciliado = "conciliado"
    divergencia = "divergencia"


class StatusMovimentacaoBancaria(str, PyEnum):
    importada = "importada"
    conciliada = "conciliada"
    divergencia = "divergencia"
    revisada = "revisada"


class TipoContaBancaria(str, PyEnum):
    bancaria = "bancaria"
    cartao = "cartao"


class StatusTransferenciaCartao(str, PyEnum):
    pendente = "pendente"
    conciliada = "conciliada"


class StatusExtratoLinha(str, PyEnum):
    importado = "importado"
    conciliado = "conciliado"
    ignorado = "ignorado"


class StatusVendaCartao(str, PyEnum):
    pendente = "pendente"
    conciliado = "conciliado"
    fechado = "fechado"
    cancelado = "cancelado"


class TipoContaPagar(str, PyEnum):
    fixa = "fixa"
    pontual = "pontual"


class StatusContaPagar(str, PyEnum):
    pendente = "pendente"
    aguardando_aprovacao = "aguardando_aprovacao"
    agendado = "agendado"
    pago = "pago"
    cancelado = "cancelado"


class DiaSemana(str, PyEnum):
    seg = "seg"
    ter = "ter"
    qua = "qua"
    qui = "qui"
    sex = "sex"


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

class AuditMixin:
    """Metadados comuns para rastreabilidade e exposição por UUID."""

    public_id = Column(Uuid(as_uuid=True), default=uuid4, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    @declared_attr
    def created_by(cls):
        return Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    @declared_attr
    def updated_by(cls):
        return Column(Integer, ForeignKey("usuarios.id"), nullable=True)


class Usuario(AuditMixin, Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    perfil = Column(Enum(PerfilUsuario), nullable=False, default=PerfilUsuario.funcionario)
    ativo = Column(Boolean, default=True, nullable=False)
    auth_version = Column(Integer, default=0, nullable=False, server_default="0")
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    # clientes atribuídos a este funcionário
    clientes = relationship("ClienteBPO", back_populates="funcionario", foreign_keys="ClienteBPO.funcionario_id")


class ClienteBPO(AuditMixin, Base):
    __tablename__ = "clientes_bpo"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(Text, nullable=False)
    razao_social = Column(Text)
    cnpj = Column(Text)
    especialidade = Column(String(100))
    regime_tributario = Column(String(50))
    tem_maquininha = Column(Boolean, default=False, nullable=False)
    antecipa = Column(Boolean, default=False, nullable=False)
    banco = Column(EncryptedText("clientes_bpo.banco"))
    agencia = Column(EncryptedText("clientes_bpo.agencia"))
    conta = Column(EncryptedText("clientes_bpo.conta"))
    funcionario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    rede_maquininha = Column(String(50))

    funcionario = relationship("Usuario", back_populates="clientes", foreign_keys=[funcionario_id])
    atendimentos = relationship("Atendimento", back_populates="cliente")
    centros_custo = relationship("CentroCusto", back_populates="cliente", order_by="CentroCusto.nome")
    contas_pagar = relationship("ContaPagar", back_populates="cliente")
    fechamentos = relationship("FechamentoDiario", back_populates="cliente")
    rotinas = relationship("TarefaRotina", back_populates="cliente")
    divergencias_conciliacao = relationship("DivergenciaConciliacao", back_populates="cliente")
    movimentacoes_bancarias = relationship("MovimentacaoBancaria", back_populates="cliente")
    contas_bancarias = relationship("ContaBancaria", back_populates="cliente")
    transferencias_cartao = relationship("TransferenciaCartao", back_populates="cliente")
    extratos_bancarios = relationship("ExtratoLinhaBancaria", back_populates="cliente")
    regras_auto_match = relationship("RegraAutoMatch", back_populates="cliente")
    taxas_cartao = relationship("TaxaCartaoCliente", back_populates="cliente")
    taxas_antecipacao = relationship("TaxaAntecipacaoCliente", back_populates="cliente")
    contas_recorrentes = relationship("ContaRecorrente", back_populates="cliente")
    maquininhas = relationship("MaquininhaCliente", back_populates="cliente", order_by="MaquininhaCliente.id")
    anotacoes = relationship("AnotacaoCliente", back_populates="cliente", order_by="AnotacaoCliente.criado_em.desc()", cascade="all, delete-orphan")


class Atendimento(AuditMixin, Base):
    __tablename__ = "atendimentos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    data_atendimento = Column(Date, nullable=False)
    nome_paciente = Column(EncryptedText("atendimentos.nome_paciente"))
    cpf_paciente = Column(EncryptedText("atendimentos.cpf_paciente", deterministic=True))
    medico = Column(EncryptedText("atendimentos.medico"))
    especialidade = Column(String(100))
    tipo_servico = Column(String(100))
    descricao_servico = Column(EncryptedText("atendimentos.descricao_servico"))
    valor_servico = Column(Numeric(12, 2), nullable=False)
    condicao_pagamento = Column(Enum(CondicaoPagamento), nullable=False)
    parcela_numero = Column(Integer, default=1)
    parcela_total = Column(Integer, default=1)
    data_prevista_recebimento = Column(Date)
    forma_pagamento = Column(Enum(FormaPagamento))
    ultimos_digitos_cartao = Column(EncryptedText("atendimentos.ultimos_digitos_cartao", deterministic=True))
    bandeira_cartao = Column(String(30))
    taxa_cartao = Column(Numeric(5, 2))          # percentual, ex: 2.50
    valor_liquido = Column(Numeric(12, 2))
    data_credito = Column(Date)
    banco_recebimento = Column(EncryptedText("atendimentos.banco_recebimento"))
    status_conciliacao = Column(Enum(StatusConciliacao), default=StatusConciliacao.pendente)
    arquivado_conciliacao_banco = Column(Boolean, default=False, nullable=False)
    valor_clinica = Column(Numeric(12, 2))
    percentual_medico = Column(Numeric(5, 2))    # percentual, ex: 30.00
    valor_medico = Column(Numeric(12, 2))
    data_pagamento_medico = Column(Date)
    observacao = Column(EncryptedText("atendimentos.observacao"))
    centro_custo_id = Column(Integer, ForeignKey("centros_custo.id"), nullable=True)
    lancado_por_id = Column(Integer, ForeignKey("usuarios.id"))
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="atendimentos")
    centro_custo = relationship("CentroCusto", back_populates="atendimentos", foreign_keys="[Atendimento.centro_custo_id]")
    rateios_centro_custo = relationship("AtendimentoCentroCustoRateio", back_populates="atendimento", cascade="all, delete-orphan")
    lancado_por = relationship("Usuario", foreign_keys=[lancado_por_id])


class CentroCusto(AuditMixin, Base):
    __tablename__ = "centros_custo"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(30), nullable=True)
    nome = Column(Text, nullable=False)
    is_medico = Column(Boolean, default=False, nullable=False)
    especialidade = Column(String(100), nullable=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="centros_custo")
    atendimentos = relationship("Atendimento", back_populates="centro_custo", foreign_keys="[Atendimento.centro_custo_id]")


class AtendimentoCentroCustoRateio(AuditMixin, Base):
    __tablename__ = "atendimentos_centros_custo_rateio"

    id = Column(Integer, primary_key=True, index=True)
    atendimento_id = Column(Integer, ForeignKey("atendimentos.id"), nullable=False)
    centro_custo_id = Column(Integer, ForeignKey("centros_custo.id"), nullable=False)
    percentual = Column(Numeric(5, 2), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)

    atendimento = relationship("Atendimento", back_populates="rateios_centro_custo")
    centro_custo = relationship("CentroCusto", foreign_keys=[centro_custo_id])


class ContaPagar(AuditMixin, Base):
    __tablename__ = "contas_pagar"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    descricao = Column(EncryptedText("contas_pagar.descricao"), nullable=False)
    fornecedor = Column(EncryptedText("contas_pagar.fornecedor"))
    tipo = Column(Enum(TipoContaPagar), nullable=False, default=TipoContaPagar.pontual)
    valor = Column(Numeric(12, 2), nullable=False)
    vencimento = Column(Date, nullable=False)
    data_pagamento = Column(Date)            # null se ainda não pago
    status = Column(Enum(StatusContaPagar), default=StatusContaPagar.pendente, nullable=False)
    categoria_dre = Column(String(60))        # chave da categoria do DRE (ex: df_aluguel)
    especialidade = Column(String(100), nullable=True)
    documento_path = Column(EncryptedText("contas_pagar.documento_path"))
    observacao = Column(EncryptedText("contas_pagar.observacao"))
    arquivado_conciliacao_banco = Column(Boolean, default=False, nullable=False)
    lancado_por_id = Column(Integer, ForeignKey("usuarios.id"))
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="contas_pagar")
    rateios_centro_custo = relationship("ContaPagarCentroCustoRateio", back_populates="conta", cascade="all, delete-orphan")
    pagamentos_parciais = relationship("PagamentoParcialContaPagar", back_populates="conta", cascade="all, delete-orphan")
    lancado_por = relationship("Usuario", foreign_keys=[lancado_por_id])

    @property
    def valor_pago_total(self):
        return sum((p.valor or Decimal("0") for p in self.pagamentos_parciais), Decimal("0"))

    @property
    def saldo_pendente(self):
        saldo = Decimal(str(self.valor or 0)) - self.valor_pago_total
        return max(saldo, Decimal("0"))


class PagamentoParcialContaPagar(AuditMixin, Base):
    __tablename__ = "pagamentos_parciais_contas_pagar"

    id = Column(Integer, primary_key=True, index=True)
    conta_pagar_id = Column(Integer, ForeignKey("contas_pagar.id", ondelete="CASCADE"), nullable=False)
    movimentacao_id = Column(Integer, ForeignKey("movimentacoes_bancarias.id"), nullable=True, unique=True)
    valor = Column(Numeric(12, 2), nullable=False)
    data_pagamento = Column(Date, nullable=False)
    observacao = Column(EncryptedText("pagamentos_parciais_contas_pagar.observacao"))
    criado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    conta = relationship("ContaPagar", back_populates="pagamentos_parciais")
    movimentacao = relationship("MovimentacaoBancaria", foreign_keys=[movimentacao_id])
    criado_por = relationship("Usuario", foreign_keys=[criado_por_id])


class ContaPagarCentroCustoRateio(AuditMixin, Base):
    __tablename__ = "contas_pagar_centros_custo_rateio"

    id = Column(Integer, primary_key=True, index=True)
    conta_pagar_id = Column(Integer, ForeignKey("contas_pagar.id"), nullable=False)
    centro_custo_id = Column(Integer, ForeignKey("centros_custo.id"), nullable=False)
    categoria_key = Column(String(60), nullable=False)
    percentual = Column(Numeric(5, 2), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)

    conta = relationship("ContaPagar", back_populates="rateios_centro_custo")
    centro_custo = relationship("CentroCusto", foreign_keys=[centro_custo_id])


class FechamentoDiario(AuditMixin, Base):
    __tablename__ = "fechamentos_diarios"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    data = Column(Date, nullable=False)
    total_despesas_dia = Column(Numeric(12, 2), default=0)
    total_receitas_dia = Column(Numeric(12, 2), default=0)
    saldo_conta = Column(Numeric(12, 2), default=0)       # informado manualmente
    saldo_provisorio_final = Column(Numeric(12, 2), default=0)
    observacao = Column(EncryptedText("fechamentos_diarios.observacao"))
    enviado_cliente = Column(Boolean, default=False)
    enviado_em = Column(DateTime)
    gerado_por_id = Column(Integer, ForeignKey("usuarios.id"))
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="fechamentos")
    gerado_por = relationship("Usuario", foreign_keys=[gerado_por_id])


class TarefaRotina(AuditMixin, Base):
    __tablename__ = "tarefas_rotina"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    funcionario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    data = Column(Date, nullable=False)
    descricao = Column(Text, nullable=False)
    horario_previsto = Column(String(10))    # ex: "09:00"
    concluida = Column(Boolean, default=False)
    concluida_em = Column(DateTime)
    dia_semana = Column(Enum(DiaSemana))

    cliente = relationship("ClienteBPO", back_populates="rotinas")
    funcionario = relationship("Usuario", foreign_keys=[funcionario_id])


class DivergenciaConciliacao(AuditMixin, Base):
    __tablename__ = "divergencias_conciliacao"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    tipo = Column(String(20), nullable=False)        # "cartao" ou "pix_ted"
    data_extrato = Column(Date)
    valor = Column(Numeric(12, 2))
    digitos_cartao = Column(String(4))
    motivo = Column(EncryptedText("divergencias_conciliacao.motivo"))
    resolvida = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="divergencias_conciliacao")


class MovimentacaoBancaria(AuditMixin, Base):
    __tablename__ = "movimentacoes_bancarias"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    conta_bancaria_id = Column(Integer, ForeignKey("contas_bancarias.id"), nullable=True)
    identificador_externo = Column(EncryptedText("movimentacoes_bancarias.identificador_externo", deterministic=True), nullable=True)
    origem_manual = Column(Boolean, default=False, nullable=False)
    tipo = Column(String(20), nullable=False)        # "cartao" ou "pix_ted"
    sentido = Column(String(15), nullable=False, server_default="recebimento")  # "recebimento" | "pagamento"
    data_movimento = Column(Date, nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    descricao = Column(EncryptedText("movimentacoes_bancarias.descricao"))
    digitos_cartao = Column(EncryptedText("movimentacoes_bancarias.digitos_cartao", deterministic=True))
    cpf_digitos_meio = Column(EncryptedText("movimentacoes_bancarias.cpf_digitos_meio", deterministic=True))
    origem_arquivo = Column(EncryptedText("movimentacoes_bancarias.origem_arquivo"))
    status = Column(Enum(StatusMovimentacaoBancaria), default=StatusMovimentacaoBancaria.importada, nullable=False)
    conciliada_com_atendimento_id = Column(Integer, ForeignKey("atendimentos.id"))
    conta_pagar_id = Column(Integer, ForeignKey("contas_pagar.id"), nullable=True)
    transferencia_cartao_id = Column(Integer, ForeignKey("transferencias_cartao.id"), nullable=True)
    arquivado_conciliacao_banco = Column(Boolean, default=False, nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="movimentacoes_bancarias")
    atendimento = relationship("Atendimento", foreign_keys=[conciliada_com_atendimento_id])
    conta_pagar = relationship("ContaPagar", foreign_keys=[conta_pagar_id])
    lote_cartao = relationship("TransferenciaCartao", foreign_keys=[transferencia_cartao_id])
    conta_bancaria = relationship("ContaBancaria", back_populates="movimentacoes")


class ContaBancaria(AuditMixin, Base):
    __tablename__ = "contas_bancarias"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    nome = Column(String(100), nullable=False)           # ex: "Conta Principal", "Conta Cartão"
    tipo = Column(Enum(TipoContaBancaria), nullable=False)
    banco = Column(EncryptedText("contas_bancarias.banco"))
    agencia = Column(EncryptedText("contas_bancarias.agencia"))
    conta = Column(EncryptedText("contas_bancarias.conta"))
    saldo_atual = Column(Numeric(14, 2), nullable=True)
    saldo_data_referencia = Column(DateTime, nullable=True)
    saldo_atualizado_em = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="contas_bancarias")
    movimentacoes = relationship("MovimentacaoBancaria", back_populates="conta_bancaria")


class TransferenciaCartao(AuditMixin, Base):
    """Agrupamento diário por bandeira gerado ao fechar o dia de cartão."""
    __tablename__ = "transferencias_cartao"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    data = Column(Date, nullable=False)
    bandeira = Column(String(50), nullable=False)        # Visa, Mastercard, Elo...
    valor_bruto = Column(Numeric(12, 2), nullable=False)
    taxa_total = Column(Numeric(12, 2), default=0)
    valor_liquido = Column(Numeric(12, 2), nullable=False)
    qtd_transacoes = Column(Integer, default=0)
    status = Column(Enum(StatusTransferenciaCartao), default=StatusTransferenciaCartao.pendente, nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="transferencias_cartao")
    extrato_linha = relationship("ExtratoLinhaBancaria", back_populates="transferencia", uselist=False)


class ExtratoLinhaBancaria(AuditMixin, Base):
    """Linhas importadas do extrato da conta bancária principal."""
    __tablename__ = "extratos_bancarios"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    data = Column(Date, nullable=False)
    descricao = Column(EncryptedText("extratos_bancarios.descricao"))
    valor = Column(Numeric(12, 2), nullable=False)
    tipo = Column(String(10), nullable=False)            # "credito" ou "debito"
    status = Column(Enum(StatusExtratoLinha), default=StatusExtratoLinha.importado, nullable=False)
    transferencia_id = Column(Integer, ForeignKey("transferencias_cartao.id"), nullable=True)
    conta_pagar_id = Column(Integer, ForeignKey("contas_pagar.id"), nullable=True)
    origem_arquivo = Column(EncryptedText("extratos_bancarios.origem_arquivo"))
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="extratos_bancarios")
    transferencia = relationship("TransferenciaCartao", back_populates="extrato_linha", foreign_keys=[transferencia_id])
    conta_pagar = relationship("ContaPagar", foreign_keys=[conta_pagar_id])


class MaquininhaCliente(AuditMixin, Base):
    """Maquininha(s) de cartão de um cliente — permite múltiplas por cliente."""
    __tablename__ = "maquininhas_cliente"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    rede = Column(String(50), nullable=False)        # Stone, Cielo, Ton...
    apelido = Column(String(100), nullable=True)     # ex: "Stone Consultório 2"
    antecipa = Column(Boolean, default=False, nullable=False)
    ativa = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="maquininhas")
    taxas = relationship("TaxaCartaoCliente", back_populates="maquininha")


class TaxaCartaoCliente(AuditMixin, Base):
    """Taxa por bandeira + faixa de parcelamento por maquininha/cliente."""
    __tablename__ = "taxas_cartao_cliente"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    maquininha_id = Column(Integer, ForeignKey("maquininhas_cliente.id"), nullable=True)
    bandeira = Column(String(50), nullable=False)           # Visa, Mastercard, Elo...
    # avista_credito | avista_debito | parcelado_2_6 | parcelado_6_12 | personalizada
    faixa_parcelamento = Column(String(20), nullable=False, server_default="avista")
    parcela_inicial = Column(Integer, nullable=True)
    parcela_final = Column(Integer, nullable=True)
    taxa_percentual = Column(Numeric(5, 2), nullable=False)  # ex: 2.50
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="taxas_cartao")
    maquininha = relationship("MaquininhaCliente", back_populates="taxas")


class TaxaAntecipacaoCliente(AuditMixin, Base):
    """Taxas de antecipação por bandeira — usadas quando o cliente tem antecipa=True.
    Várias taxas podem ser cadastradas por bandeira; apenas uma fica selecionada por vez."""
    __tablename__ = "taxas_antecipacao_cliente"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    bandeira = Column(String(50), nullable=False)
    descricao = Column(String(100), nullable=False)   # ex: "1x", "2x a 6x", "Padrão Jun/26"
    taxa_percentual = Column(Numeric(5, 2), nullable=False)
    selecionada = Column(Boolean, default=False, nullable=False)  # taxa ativa no período
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="taxas_antecipacao")


class RegraAutoMatch(AuditMixin, Base):
    """Regras para conciliar automaticamente linhas do extrato com transferências de cartão."""
    __tablename__ = "regras_auto_match"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    nome = Column(String(100), nullable=False)           # ex: "Recebimento Mastercard"
    padrao_descricao = Column(EncryptedText("regras_auto_match.padrao_descricao"), nullable=False)
    bandeira = Column(String(50))                        # Visa, Mastercard... (null = qualquer)
    ativo = Column(Boolean, default=True, nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="regras_auto_match")


class ContaRecorrente(AuditMixin, Base):
    """Contas fixas recorrentes com aviso automático por e-mail próximo ao vencimento."""
    __tablename__ = "contas_recorrentes"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    descricao = Column(EncryptedText("contas_recorrentes.descricao"), nullable=False)
    fornecedor = Column(EncryptedText("contas_recorrentes.fornecedor"))
    valor = Column(Numeric(12, 2))
    dia_vencimento = Column(Integer, nullable=False)          # 1–31
    dias_antecedencia = Column(Integer, default=3, nullable=False)
    email_destino = Column(EncryptedText("contas_recorrentes.email_destino", deterministic=True), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    ultimo_aviso_em = Column(Date)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="contas_recorrentes")


class OrcamentoValor(AuditMixin, Base):
    """Valores orçados por categoria DRE, cliente e período (mês/ano)."""
    __tablename__ = "orcamento_valores"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    categoria_key = Column(String(60), nullable=False)
    mes = Column(Integer, nullable=False)
    ano = Column(Integer, nullable=False)
    valor_orcado = Column(Numeric(12, 2), default=0, nullable=False)

    cliente = relationship("ClienteBPO")


class VendaCartao(AuditMixin, Base):
    """Linha individual do extrato da maquininha (pré-lote)."""
    __tablename__ = "vendas_cartao"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id"), nullable=False)
    data_venda = Column(Date, nullable=False)
    data_pagamento = Column(Date, nullable=False)
    bandeira = Column(String(50))
    ultimos_digitos = Column(EncryptedText("vendas_cartao.ultimos_digitos", deterministic=True))
    nome_portador = Column(EncryptedText("vendas_cartao.nome_portador"))
    valor_bruto = Column(Numeric(12, 2), nullable=False)
    taxa_percentual = Column(Numeric(5, 2))
    valor_liquido = Column(Numeric(12, 2))
    parcelas = Column(Integer, default=1)
    descricao = Column(EncryptedText("vendas_cartao.descricao"))
    status = Column(Enum(StatusVendaCartao), default=StatusVendaCartao.pendente, nullable=False)
    atendimento_id = Column(Integer, ForeignKey("atendimentos.id"), nullable=True)
    lote_id = Column(Integer, ForeignKey("transferencias_cartao.id"), nullable=True)
    origem_arquivo = Column(EncryptedText("vendas_cartao.origem_arquivo"))
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    cliente = relationship("ClienteBPO")
    atendimento = relationship("Atendimento", foreign_keys=[atendimento_id])
    lote = relationship("TransferenciaCartao", foreign_keys=[lote_id])


class LogAuditoria(AuditMixin, Base):
    """Registro de ações realizadas pelos usuários no sistema."""
    __tablename__ = "logs_auditoria"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    usuario_nome = Column(Text, nullable=False, default="")
    acao = Column(String(120), nullable=False)
    modulo = Column(String(50), nullable=False)
    cliente_id = Column(Integer, nullable=True)
    cliente_nome = Column(Text, nullable=True)
    detalhes = Column(EncryptedText("logs_auditoria.detalhes"), nullable=True)
    ip = Column(EncryptedText("logs_auditoria.ip"), nullable=True)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)

    usuario = relationship("Usuario", foreign_keys=[usuario_id])


class AnotacaoCliente(AuditMixin, Base):
    """Anotações internas de procedimentos e orientações específicas do cliente."""
    __tablename__ = "anotacoes_clientes"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes_bpo.id", ondelete="CASCADE"), nullable=False, index=True)
    autor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    categoria = Column(String(50), nullable=False, default="procedimento")
    titulo = Column(EncryptedText("anotacoes_clientes.titulo"), nullable=False)
    conteudo = Column(EncryptedText("anotacoes_clientes.conteudo"), nullable=False)
    criado_em = Column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    cliente = relationship("ClienteBPO", back_populates="anotacoes")
    autor = relationship("Usuario", foreign_keys=[autor_id])


class AuditEvent(Base):
    """Trilha técnica imutável sem snapshots de PII, tokens ou hashes."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True)
    table_name = Column(String(80), nullable=False, index=True)
    operation = Column(String(10), nullable=False)
    record_public_id = Column(Uuid(as_uuid=True), nullable=True, index=True)
    actor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    database_role = Column(String(80), nullable=False)
    request_id = Column(Uuid(as_uuid=True), nullable=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
