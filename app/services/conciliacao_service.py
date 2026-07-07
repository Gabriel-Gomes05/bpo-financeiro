import re
import unicodedata
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import List, Tuple

import pandas as pd
from sqlalchemy.orm import Session

from app.models import (
    Atendimento,
    CondicaoPagamento,
    DivergenciaConciliacao,
    ExtratoLinhaBancaria,
    FormaPagamento,
    MovimentacaoBancaria,
    StatusConciliacao,
    StatusExtratoLinha,
    StatusMovimentacaoBancaria,
    StatusTransferenciaCartao,
    StatusVendaCartao,
    TaxaCartaoCliente,
    TransferenciaCartao,
    VendaCartao,
)


def ler_arquivo_extrato(caminho: str) -> pd.DataFrame:
    """Le Excel ou CSV e normaliza colunas esperadas."""
    if caminho.endswith(".csv"):
        df = pd.read_csv(caminho, decimal=",", thousands=".")
    else:
        df = pd.read_excel(caminho)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _extrair_coluna(df: pd.DataFrame, candidatas: list, padrao=None):
    for nome in candidatas:
        if nome in df.columns:
            return df[nome]
    return padrao


def _extrair_cpf_digitos_meio(cpf: str | None) -> str | None:
    """Extrai os 6 dígitos do meio do CPF (posições 3–8 dos 11 dígitos)."""
    if not cpf:
        return None
    apenas_digitos = re.sub(r"\D", "", str(cpf))
    if len(apenas_digitos) != 11:
        return None
    return apenas_digitos[3:9]


def _decimal_seguro(valor) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def _norm_col(nome: str) -> str:
    """Remove acentos, lowercase, substitui não-alfanuméricos por underscore."""
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = re.sub(r"[^a-z0-9]+", "_", nome.strip().lower())
    return nome.strip("_")


def _norm_texto(valor: str | None) -> str:
    if not valor:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()
    return re.sub(r"\s+", " ", texto)


def _nome_bate(nome_atendimento: str | None, texto_extrato: str | None) -> bool:
    nome = _norm_texto(nome_atendimento)
    texto = _norm_texto(texto_extrato)
    if len(nome) < 3 or len(texto) < 3:
        return False
    return nome in texto or texto in nome


def _procedimento_bate(atendimento: Atendimento, texto_extrato: str | None) -> bool:
    texto = _norm_texto(texto_extrato)
    if len(texto) < 3:
        return False
    procedimentos = [
        _norm_texto(atendimento.descricao_servico),
        _norm_texto(atendimento.tipo_servico),
    ]
    return any(
        len(proc) >= 3 and (proc in texto or texto in proc)
        for proc in procedimentos
    )


def _contar_criterios(valor_ok: bool, data_ok: bool, nome_ok: bool, procedimento_ok: bool) -> int:
    return sum(1 for ok in (valor_ok, data_ok, nome_ok, procedimento_ok) if ok)


def limpar_divergencias_anteriores(db: Session, cliente_id: int, tipo: str):
    """Remove divergencias nao resolvidas antes de reprocessar o extrato."""
    db.query(DivergenciaConciliacao).filter(
        DivergenciaConciliacao.cliente_id == cliente_id,
        DivergenciaConciliacao.tipo == tipo,
        DivergenciaConciliacao.resolvida == False,
    ).delete()
    db.commit()


def limpar_movimentacoes_anteriores(db: Session, cliente_id: int, tipo: str):
    """Remove apenas movimentacoes importadas livres do mesmo tipo para o cliente."""
    db.query(MovimentacaoBancaria).filter(
        MovimentacaoBancaria.cliente_id == cliente_id,
        MovimentacaoBancaria.tipo == tipo,
        MovimentacaoBancaria.conciliada_com_atendimento_id.is_(None),
        MovimentacaoBancaria.transferencia_cartao_id.is_(None),
        MovimentacaoBancaria.conta_pagar_id.is_(None),
        MovimentacaoBancaria.status.in_([
            StatusMovimentacaoBancaria.importada,
            StatusMovimentacaoBancaria.divergencia,
            StatusMovimentacaoBancaria.revisada,
        ]),
    ).delete()
    db.commit()


def _criar_movimentacao(
    db: Session,
    cliente_id: int,
    tipo: str,
    data_movimento,
    valor,
    origem_arquivo: str,
    digitos_cartao: str | None = None,
    descricao: str | None = None,
    sentido: str = "recebimento",
):
    movimentacao = MovimentacaoBancaria(
        cliente_id=cliente_id,
        tipo=tipo,
        sentido=sentido,
        data_movimento=data_movimento,
        valor=valor,
        digitos_cartao=digitos_cartao,
        descricao=descricao,
        origem_arquivo=origem_arquivo,
        status=StatusMovimentacaoBancaria.importada,
    )
    db.add(movimentacao)
    db.flush()
    return movimentacao


# ---------------------------------------------------------------------------
# Importação de lançamentos (Atendimentos via planilha)
# ---------------------------------------------------------------------------

def importar_lancamentos(db: Session, cliente_id: int, df: pd.DataFrame) -> int:
    """Importa lançamentos do Excel/CSV. Deleta os pendentes e recria."""
    df = df.copy()
    df.columns = [_norm_col(c) for c in df.columns]

    def _col(*names):
        for n in names:
            if n in df.columns:
                return n
        return None

    c_data     = _col("data_atendimento", "data_do_atendimento", "data")
    c_nome     = _col("nome_paciente", "paciente", "nome")
    c_cpf      = _col("cpf_paciente", "cpf_paciente_responsavel", "cpf")
    c_medico   = _col("medico")
    c_espec    = _col("especialidade")
    c_tipo_srv = _col("tipo_servico", "tipo_de_servico")
    c_desc     = _col("descricao_servico", "descricao_do_servico", "descricao")
    c_valor    = _col("valor_servico", "valor_do_servico", "valor")
    c_condicao = _col("condicao_pagamento", "condicoes_do_pagamento", "condicao")
    c_parcela  = _col("parcela", "parcela_numero")
    c_prev     = _col("data_prevista_recebimento", "data_prevista", "data_prevista_de_recebimento")
    c_forma    = _col("forma_pagamento", "forma_de_pagamento")
    c_taxa     = _col("taxa_cartao", "taxa_do_cartao", "taxa")
    c_digitos  = _col("4_ultimos_digitos_do_cartao", "ultimos_digitos_do_cartao", "ultimos_digitos", "digitos_cartao")
    c_bandeira = _col("bandeira_cartao", "bandeira_do_cartao", "bandeira")
    c_liquido  = _col("valor_liquido")
    c_credito  = _col("data_credito", "data_do_credito")
    c_obs      = _col("observacao")

    if not c_data or not c_valor:
        raise ValueError("Arquivo não contém colunas de data e valor reconhecíveis.")

    db.query(Atendimento).filter(
        Atendimento.cliente_id == cliente_id,
        Atendimento.status_conciliacao == StatusConciliacao.pendente,
    ).delete()
    db.commit()

    _FORMA = {
        "cartao": FormaPagamento.cartao_credito,
        "cartao_credito": FormaPagamento.cartao_credito,
        "cartao_de_credito": FormaPagamento.cartao_credito,
        "credito": FormaPagamento.cartao_credito,
        "pix": FormaPagamento.pix,
        "transferencia": FormaPagamento.transferencia,
        "ted": FormaPagamento.transferencia,
        "doc": FormaPagamento.transferencia,
        "dinheiro": FormaPagamento.dinheiro,
    }
    _COND = {
        "avista": CondicaoPagamento.avista,
        "a_vista": CondicaoPagamento.avista,
        "parcelado": CondicaoPagamento.parcelado,
        "pix": CondicaoPagamento.pix,
        "transferencia": CondicaoPagamento.transferencia,
        "dinheiro": CondicaoPagamento.dinheiro,
    }

    importados = 0
    for _, row in df.iterrows():
        try:
            data_atend = pd.to_datetime(row[c_data]).date()
            valor = _decimal_seguro(row[c_valor])
        except Exception:
            continue

        def _v(col, row=row):
            if col and pd.notna(row.get(col)):
                s = str(row[col]).strip()
                return s or None
            return None

        forma_k = re.sub(r"[^a-z0-9]+", "_", (_v(c_forma) or "").lower()).strip("_")
        forma = _FORMA.get(forma_k, FormaPagamento.cartao_credito)

        cond_k = re.sub(r"[^a-z0-9]+", "_", (_v(c_condicao) or "").lower()).strip("_")
        condicao = _COND.get(cond_k, CondicaoPagamento.avista)

        data_prev = None
        if c_prev:
            try:
                data_prev = pd.to_datetime(row[c_prev]).date()
            except Exception:
                pass

        data_cred = None
        if c_credito:
            try:
                data_cred = pd.to_datetime(row[c_credito]).date()
            except Exception:
                pass

        digitos = None
        if c_digitos and pd.notna(row.get(c_digitos)):
            d = str(row[c_digitos]).strip().split(".")[0]
            if d:
                digitos = d.zfill(4)[-4:]

        taxa = None
        if c_taxa and pd.notna(row.get(c_taxa)):
            try:
                taxa = Decimal(str(row[c_taxa]))
            except Exception:
                pass

        liquido = None
        if c_liquido and pd.notna(row.get(c_liquido)):
            try:
                liquido = _decimal_seguro(row[c_liquido])
            except Exception:
                pass

        parcela = 1
        if c_parcela and pd.notna(row.get(c_parcela)):
            try:
                parcela = int(row[c_parcela])
            except Exception:
                pass

        db.add(Atendimento(
            cliente_id=cliente_id,
            data_atendimento=data_atend,
            nome_paciente=_v(c_nome),
            cpf_paciente=_v(c_cpf),
            medico=_v(c_medico),
            especialidade=_v(c_espec),
            tipo_servico=_v(c_tipo_srv),
            descricao_servico=_v(c_desc),
            valor_servico=valor,
            condicao_pagamento=condicao,
            parcela_numero=parcela,
            data_prevista_recebimento=data_prev or data_atend,
            forma_pagamento=forma,
            ultimos_digitos_cartao=digitos,
            bandeira_cartao=_v(c_bandeira),
            taxa_cartao=taxa,
            valor_liquido=liquido,
            data_credito=data_cred,
            status_conciliacao=StatusConciliacao.pendente,
            observacao=_v(c_obs),
        ))
        importados += 1

    db.commit()
    return importados


# ---------------------------------------------------------------------------
# Parse OFX (bancos brasileiros — formato SGML OFX 1.x)
# ---------------------------------------------------------------------------

def parse_ofx(caminho: str) -> pd.DataFrame:
    """Lê o OFX e preserva identificação da conta e saldo informado pelo banco."""
    for enc in ("latin-1", "utf-8", "utf-8-sig"):
        try:
            with open(caminho, "r", encoding=enc, errors="ignore") as f:
                conteudo = f.read()
            break
        except Exception:
            conteudo = ""

    registros = []
    blocos = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", conteudo, re.DOTALL | re.IGNORECASE)

    for bloco in blocos:
        def _tag(t):
            m = re.search(rf"<{t}>(.*?)(?=<|\Z)", bloco, re.IGNORECASE | re.DOTALL)
            return m.group(1).strip() if m else None

        dtposted = _tag("DTPOSTED")
        trnamt = _tag("TRNAMT")
        memo = _tag("MEMO") or _tag("NAME") or ""
        fitid = _tag("FITID") or ""

        if not dtposted or not trnamt:
            continue
        try:
            data = datetime.strptime(dtposted[:8], "%Y%m%d").date()
            valor = Decimal(trnamt.replace(",", "."))
        except Exception:
            continue

        registros.append({"data": data, "valor": float(valor), "descricao": memo, "fitid": fitid})

    if not registros:
        raise ValueError("Nenhuma transação encontrada no arquivo OFX.")

    df = pd.DataFrame(registros)

    def _tag_global(tag):
        match = re.search(rf"<{tag}>(.*?)(?=<|\Z)", conteudo, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else None

    saldo_raw = _tag_global("BALAMT")
    saldo_data_raw = _tag_global("DTASOF")
    df.attrs["ofx_banco"] = _tag_global("BANKID") or "Banco OFX"
    df.attrs["ofx_conta"] = _tag_global("ACCTID") or "Conta não identificada"
    if saldo_raw:
        try:
            df.attrs["ofx_saldo"] = Decimal(saldo_raw.replace(",", "."))
        except InvalidOperation:
            pass
    if saldo_data_raw:
        try:
            df.attrs["ofx_saldo_data"] = datetime.strptime(saldo_data_raw[:14], "%Y%m%d%H%M%S")
        except ValueError:
            try:
                df.attrs["ofx_saldo_data"] = datetime.strptime(saldo_data_raw[:8], "%Y%m%d")
            except ValueError:
                pass
    return df


# ---------------------------------------------------------------------------
# Funções de matching exportadas (usadas em conciliacao.py e conciliacao_banco.py)
# ---------------------------------------------------------------------------

def score_sugestao(movimentacao: MovimentacaoBancaria, atendimento: Atendimento):
    valor_banco = Decimal(str(movimentacao.valor or 0))
    valor_at = Decimal(str(atendimento.valor_servico or 0))
    diff_valor = abs(valor_banco - valor_at)

    data_banco = movimentacao.data_movimento
    data_ref = atendimento.data_prevista_recebimento or atendimento.data_atendimento
    diff_dias = abs((data_banco - data_ref).days) if data_banco and data_ref else 99

    return float(diff_valor) * 100 + diff_dias, diff_valor, diff_dias


def buscar_sugestao(movimentacao: MovimentacaoBancaria, receitas: list):
    """Retorna o melhor Atendimento candidato para a movimentacao, ou None."""
    candidatos = []
    for at in receitas:
        fp = at.forma_pagamento.value if at.forma_pagamento else ""
        if movimentacao.tipo == "cartao" and fp != "cartao_credito":
            continue
        if movimentacao.tipo == "pix_ted" and fp not in {"pix", "transferencia"}:
            continue
        # CPF match para PIX: se o extrato traz os 6 dígitos do meio, exige correspondência
        if movimentacao.tipo == "pix_ted" and movimentacao.cpf_digitos_meio:
            cpf_at = _extrair_cpf_digitos_meio(at.cpf_paciente)
            if cpf_at and cpf_at != movimentacao.cpf_digitos_meio:
                continue

        sc, dv, dd = score_sugestao(movimentacao, at)
        if dv > Decimal("5.00") or dd > 5:
            continue
        candidatos.append((sc, dv, dd, at))

    if not candidatos:
        return None

    candidatos.sort(key=lambda x: x[0])
    _, dv, dd, at = candidatos[0]

    nome_ok = _nome_bate(at.nome_paciente, movimentacao.descricao)
    procedimento_ok = _procedimento_bate(at, movimentacao.descricao)
    valor_ok = dv == Decimal("0.00")
    data_ok = dd == 0
    criterios_batidos = _contar_criterios(valor_ok, data_ok, nome_ok, procedimento_ok)
    cpf_confirmado = (
        movimentacao.tipo == "pix_ted"
        and movimentacao.cpf_digitos_meio
        and _extrair_cpf_digitos_meio(at.cpf_paciente) == movimentacao.cpf_digitos_meio
    )

    if valor_ok and data_ok and nome_ok:
        status = "sugestao_pronta"
        motivo = "Valor, data e nome confirmados."
    elif criterios_batidos >= 2:
        status = "sugestao_verde"
        motivo = f"Sugestao forte: {criterios_batidos} criterios batendo." + (" CPF confirmado." if cpf_confirmado else "")
    elif dv <= Decimal("5.00") and dd <= 3:
        status = "revisar"
        motivo = "Sugestao: valor, data, nome ou procedimento precisam de conferencia manual." + (" CPF confirmado." if cpf_confirmado else "")
    else:
        status = "revisar"
        motivo = "Sugestao: correspondencia provavel, precisa de validacao manual."

    return {
        "atendimento": at,
        "status": status,
        "motivo": motivo,
        "diferenca_valor": float(dv),
        "diferenca_dias": dd,
        "criterios_batidos": criterios_batidos,
    }


# ---------------------------------------------------------------------------
# Conciliação de cartão
# ---------------------------------------------------------------------------

def conciliar_cartao(
    db: Session,
    cliente_id: int,
    df: pd.DataFrame,
    origem_arquivo: str,
) -> Tuple[List[dict], List[dict]]:
    conciliados = []
    divergencias = []

    col_valor    = _extrair_coluna(df, ["valor_bruto", "valor", "gross_amount", "bruto"])
    col_data     = _extrair_coluna(df, ["data_credito", "data", "date", "data_pagamento"])
    col_digitos  = _extrair_coluna(df, ["ultimos_digitos", "final_cartao", "card_last4", "digitos"])
    col_taxa     = _extrair_coluna(df, ["taxa", "mdr", "taxa_percentual", "fee"])
    col_liquido  = _extrair_coluna(df, ["valor_liquido", "valor_liq", "net_amount", "liquido"])
    col_bandeira = _extrair_coluna(df, ["bandeira", "brand", "bandeira_cartao", "flag"])
    col_descricao = _extrair_coluna(df, ["descricao", "historico", "titulo", "estabelecimento"])

    if col_valor is None or col_data is None:
        raise ValueError("Arquivo nao contem colunas de valor e data reconheciveis.")

    for idx, row in df.iterrows():
        try:
            valor_bruto  = _decimal_seguro(row[col_valor.name])
            data_credito = pd.to_datetime(row[col_data.name]).date()
        except Exception:
            divergencias.append({"linha": idx + 2, "motivo": "Linha com dado invalido", "dados": row.to_dict()})
            continue

        digitos       = str(row[col_digitos.name]).strip().zfill(4)[-4:] if col_digitos is not None else None
        taxa_pct      = Decimal(str(row[col_taxa.name])) if col_taxa is not None else None
        valor_liquido = _decimal_seguro(row[col_liquido.name]) if col_liquido is not None else None
        bandeira_arquivo = str(row[col_bandeira.name]).strip() if col_bandeira is not None and pd.notna(row[col_bandeira.name]) else None
        descricao        = str(row[col_descricao.name]).strip() if col_descricao is not None and pd.notna(row[col_descricao.name]) else None

        if valor_liquido is None and bandeira_arquivo:
            # Sem valor líquido no arquivo: usa taxa à vista como fallback
            taxa_cad = (
                db.query(TaxaCartaoCliente)
                .filter(
                    TaxaCartaoCliente.cliente_id == cliente_id,
                    TaxaCartaoCliente.bandeira == bandeira_arquivo,
                    TaxaCartaoCliente.faixa_parcelamento == "avista",
                    TaxaCartaoCliente.ativo == True,
                )
                .first()
                or db.query(TaxaCartaoCliente)
                .filter(
                    TaxaCartaoCliente.cliente_id == cliente_id,
                    TaxaCartaoCliente.bandeira == bandeira_arquivo,
                    TaxaCartaoCliente.ativo == True,
                )
                .first()
            )
            if taxa_cad:
                fator = Decimal("1") - (Decimal(str(taxa_cad.taxa_percentual)) / Decimal("100"))
                valor_liquido = (valor_bruto * fator).quantize(Decimal("0.01"))
                if taxa_pct is None:
                    taxa_pct = Decimal(str(taxa_cad.taxa_percentual))

        movimentacao = _criar_movimentacao(
            db=db, cliente_id=cliente_id, tipo="cartao",
            data_movimento=data_credito, valor=valor_bruto,
            origem_arquivo=origem_arquivo, digitos_cartao=digitos, descricao=descricao,
        )

        data_min = data_credito - timedelta(days=3)
        data_max = data_credito + timedelta(days=3)

        query = db.query(Atendimento).filter(
            Atendimento.cliente_id == cliente_id,
            Atendimento.status_conciliacao == StatusConciliacao.pendente,
            Atendimento.forma_pagamento == FormaPagamento.cartao_credito,
            Atendimento.valor_servico == valor_bruto,
            Atendimento.data_prevista_recebimento >= data_min,
            Atendimento.data_prevista_recebimento <= data_max,
        )
        if digitos:
            query = query.filter(Atendimento.ultimos_digitos_cartao == digitos)

        match = query.first()

        if match:
            match.status_conciliacao = StatusConciliacao.conciliado
            match.data_credito = data_credito
            if taxa_pct is not None:
                match.taxa_cartao = taxa_pct
            if valor_liquido is not None:
                match.valor_liquido = valor_liquido
            movimentacao.status = StatusMovimentacaoBancaria.conciliada
            movimentacao.conciliada_com_atendimento_id = match.id
            db.commit()
            conciliados.append({
                "atendimento_id": match.id,
                "paciente": match.nome_paciente,
                "valor": float(match.valor_servico),
                "data_credito": data_credito.strftime("%d/%m/%Y"),
                "movimentacao_id": movimentacao.id,
            })
        else:
            movimentacao.status = StatusMovimentacaoBancaria.divergencia
            db.add(DivergenciaConciliacao(
                cliente_id=cliente_id, tipo="cartao",
                data_extrato=data_credito, valor=valor_bruto, digitos_cartao=digitos,
                motivo="Sem lancamento correspondente no sistema",
            ))
            db.commit()
            divergencias.append({
                "linha": idx + 2,
                "motivo": "Nenhum lancamento correspondente encontrado",
                "valor": float(valor_bruto),
                "data_credito": data_credito.strftime("%d/%m/%Y"),
                "digitos": digitos,
                "movimentacao_id": movimentacao.id,
            })

    return conciliados, divergencias


# ---------------------------------------------------------------------------
# Conciliação PIX / TED
# ---------------------------------------------------------------------------

def conciliar_pix_ted(
    db: Session,
    cliente_id: int,
    df: pd.DataFrame,
    origem_arquivo: str,
) -> Tuple[List[dict], List[dict]]:
    conciliados = []
    divergencias = []

    col_valor     = _extrair_coluna(df, ["valor", "valor_bruto", "amount"])
    col_data      = _extrair_coluna(df, ["data", "date", "data_credito", "data_pagamento"])
    col_descricao = _extrair_coluna(df, ["descricao", "historico", "titulo", "favorecido", "memo"])
    col_cpf_meio  = _extrair_coluna(df, ["cpf_digitos_meio", "cpf_meio", "cpf_6_digitos", "digitos_cpf"])

    if col_valor is None or col_data is None:
        raise ValueError("Arquivo nao contem colunas de valor e data reconheciveis.")

    for idx, row in df.iterrows():
        try:
            valor          = _decimal_seguro(row[col_valor.name])
            data_transacao = pd.to_datetime(row[col_data.name]).date()
        except Exception:
            divergencias.append({"linha": idx + 2, "motivo": "Dado invalido na linha"})
            continue

        # Ignora débitos (valor negativo no extrato bancário)
        if valor <= Decimal("0"):
            continue

        descricao = str(row[col_descricao.name]).strip() if col_descricao is not None and pd.notna(row[col_descricao.name]) else None

        cpf_meio = None
        if col_cpf_meio is not None and pd.notna(row.get(col_cpf_meio.name)):
            raw = re.sub(r"\D", "", str(row[col_cpf_meio.name]))
            cpf_meio = raw[:6] if len(raw) >= 6 else (raw or None)

        movimentacao = _criar_movimentacao(
            db=db, cliente_id=cliente_id, tipo="pix_ted",
            data_movimento=data_transacao, valor=valor,
            origem_arquivo=origem_arquivo, descricao=descricao,
        )
        if cpf_meio:
            movimentacao.cpf_digitos_meio = cpf_meio

        receitas = db.query(Atendimento).filter(
            Atendimento.cliente_id == cliente_id,
            Atendimento.status_conciliacao == StatusConciliacao.pendente,
            Atendimento.forma_pagamento.in_([FormaPagamento.pix, FormaPagamento.transferencia]),
        ).all()
        sugestao = buscar_sugestao(movimentacao, receitas)
        if sugestao:
            # A importacao apenas cria a movimentacao. A sugestao sera exibida
            # e so sera efetivada por uma acao explicita do usuario.
            movimentacao.status = StatusMovimentacaoBancaria.importada
            db.commit()
        else:
            movimentacao.status = StatusMovimentacaoBancaria.divergencia
            db.add(DivergenciaConciliacao(
                cliente_id=cliente_id, tipo="pix_ted",
                data_extrato=data_transacao, valor=valor,
                motivo="Sem lancamento correspondente no sistema",
            ))
            db.commit()
            divergencias.append({
                "linha": idx + 2,
                "motivo": "Nenhum lancamento correspondente",
                "valor": float(valor),
                "data": data_transacao.strftime("%d/%m/%Y"),
                "movimentacao_id": movimentacao.id,
            })

    return conciliados, divergencias


# ---------------------------------------------------------------------------
# Lotes de cartão e extrato conta corrente
# ---------------------------------------------------------------------------

def limpar_movimentacoes_banco_livres(db: Session, cliente_id: int):
    """Remove apenas movimentacoes bancarias ainda sem vinculo de conciliacao."""
    db.query(MovimentacaoBancaria).filter(
        MovimentacaoBancaria.cliente_id == cliente_id,
        MovimentacaoBancaria.tipo == "pix_ted",
        MovimentacaoBancaria.conciliada_com_atendimento_id.is_(None),
        MovimentacaoBancaria.transferencia_cartao_id.is_(None),
        MovimentacaoBancaria.conta_pagar_id.is_(None),
        MovimentacaoBancaria.status.in_([
            StatusMovimentacaoBancaria.importada,
            StatusMovimentacaoBancaria.divergencia,
            StatusMovimentacaoBancaria.revisada,
        ]),
    ).delete()
    db.commit()


def importar_movimentacoes_bancarias(
    db: Session,
    cliente_id: int,
    df: pd.DataFrame,
    origem_arquivo: str,
    conta_bancaria_id: int | None = None,
) -> dict:
    """
    Importa o extrato da conta corrente como movimentacoes bancarias livres.
    Creditos ficam disponiveis para Pix/TED ou para vincular com lotes de cartao.
    Debitos ficam disponiveis para contas a pagar.
    """
    col_valor     = _extrair_coluna(df, ["valor", "amount", "credito", "valor_bruto", "vlr"])
    col_data      = _extrair_coluna(df, ["data", "date", "data_lancamento", "data_credito", "dt_lancamento"])
    col_descricao = _extrair_coluna(df, ["descricao", "historico", "memo", "titulo", "complemento"])
    col_tipo      = _extrair_coluna(df, ["tipo", "type", "dc", "natureza", "debcred"])
    col_cpf_meio  = _extrair_coluna(df, ["cpf_digitos_meio", "cpf_meio", "cpf_6_digitos", "digitos_cpf"])
    col_fitid     = _extrair_coluna(df, ["fitid", "identificador_externo", "id_transacao"])

    if col_valor is None or col_data is None:
        raise ValueError("Arquivo nao contem colunas de valor e data reconheciveis.")

    importados = 0

    for _, row in df.iterrows():
        try:
            valor_raw = _decimal_seguro(row[col_valor.name])
            data_movimento = pd.to_datetime(row[col_data.name]).date()
        except Exception:
            continue

        if col_tipo is not None and pd.notna(row.get(col_tipo.name)):
            tipo_raw = _norm_col(str(row[col_tipo.name]))
            is_credito = tipo_raw in {"c", "cr", "cred", "credito", "credit", "c_r", "entrada"}
            sentido = "recebimento" if is_credito else "pagamento"
        else:
            sentido = "recebimento" if valor_raw > Decimal("0") else "pagamento"

        valor = abs(valor_raw)
        if valor <= Decimal("0"):
            continue

        fitid = None
        if col_fitid is not None and pd.notna(row.get(col_fitid.name)):
            fitid = str(row[col_fitid.name]).strip() or None
        if fitid and conta_bancaria_id and db.query(MovimentacaoBancaria.id).filter(
            MovimentacaoBancaria.conta_bancaria_id == conta_bancaria_id,
            MovimentacaoBancaria.identificador_externo == fitid,
        ).first():
            continue

        descricao = (
            str(row[col_descricao.name]).strip()
            if col_descricao is not None and pd.notna(row.get(col_descricao.name))
            else None
        )

        mov = _criar_movimentacao(
            db=db,
            cliente_id=cliente_id,
            tipo="pix_ted",
            sentido=sentido,
            data_movimento=data_movimento,
            valor=valor,
            origem_arquivo=origem_arquivo,
            descricao=descricao,
        )
        mov.conta_bancaria_id = conta_bancaria_id
        mov.identificador_externo = fitid

        if col_cpf_meio is not None and pd.notna(row.get(col_cpf_meio.name)):
            raw = re.sub(r"\D", "", str(row[col_cpf_meio.name]))
            mov.cpf_digitos_meio = raw[:6] if len(raw) >= 6 else (raw or None)

        importados += 1

    db.commit()
    return {"importados": importados}


def gerar_transferencias_cartao(db: Session, cliente_id: int) -> int:
    """
    Agrupa Atendimentos conciliados por cartão em TransferenciaCartao
    por (data_credito, bandeira_cartao). Cria ou atualiza os registros.
    Retorna o número de novos lotes criados.
    """
    from sqlalchemy import func

    FORMAS_CARTAO = [FormaPagamento.cartao_credito]

    rows = (
        db.query(
            Atendimento.data_credito,
            Atendimento.bandeira_cartao,
            func.sum(Atendimento.valor_servico).label("valor_bruto"),
            func.sum(
                func.coalesce(Atendimento.valor_liquido, Atendimento.valor_servico)
            ).label("valor_liquido"),
            func.count(Atendimento.id).label("qtd"),
        )
        .filter(
            Atendimento.cliente_id == cliente_id,
            Atendimento.status_conciliacao == StatusConciliacao.conciliado,
            Atendimento.forma_pagamento.in_(FORMAS_CARTAO),
            Atendimento.data_credito.isnot(None),
        )
        .group_by(Atendimento.data_credito, Atendimento.bandeira_cartao)
        .all()
    )

    criados = 0
    for row in rows:
        bandeira = row.bandeira_cartao or "Outros"
        vbruto = Decimal(str(row.valor_bruto or "0"))
        vliq   = Decimal(str(row.valor_liquido or "0"))

        existente = db.query(TransferenciaCartao).filter(
            TransferenciaCartao.cliente_id == cliente_id,
            TransferenciaCartao.data == row.data_credito,
            TransferenciaCartao.bandeira == bandeira,
        ).first()

        if existente is None:
            db.add(TransferenciaCartao(
                cliente_id=cliente_id,
                data=row.data_credito,
                bandeira=bandeira,
                valor_bruto=vbruto,
                taxa_total=vbruto - vliq,
                valor_liquido=vliq,
                qtd_transacoes=row.qtd,
                status=StatusTransferenciaCartao.pendente,
            ))
            criados += 1
        elif existente.status == StatusTransferenciaCartao.pendente:
            existente.valor_bruto = vbruto
            existente.taxa_total  = vbruto - vliq
            existente.valor_liquido = vliq
            existente.qtd_transacoes = row.qtd

    db.commit()
    return criados


def buscar_sugestao_venda(venda: "VendaCartao", atendimentos: list) -> dict | None:
    """Retorna o melhor Atendimento para uma VendaCartao, ou None."""
    candidatos = []
    for at in atendimentos:
        fp = at.forma_pagamento.value if at.forma_pagamento else ""
        if fp != "cartao_credito":
            continue

        # Se ambos têm dígitos, exige match
        vb = Decimal(str(venda.valor_bruto or 0))
        va = Decimal(str(at.valor_servico or 0))
        diff_valor = abs(vb - va)

        data_ref = at.data_prevista_recebimento or at.data_atendimento
        diff_dias = abs((venda.data_pagamento - data_ref).days) if data_ref else 99

        # Só considera candidatos razoáveis
        if diff_valor > Decimal("50.00") or diff_dias > 7:
            continue

        score = float(diff_valor) * 10 + diff_dias
        candidatos.append((score, diff_valor, diff_dias, at))

    if not candidatos:
        return None

    candidatos.sort(key=lambda x: x[0])
    _, dv, dd, at = candidatos[0]

    nome_ok = _nome_bate(at.nome_paciente, venda.nome_portador)
    procedimento_ok = _procedimento_bate(at, venda.descricao)
    valor_ok = dv == Decimal("0.00")
    data_ok = dd == 0
    criterios_batidos = _contar_criterios(valor_ok, data_ok, nome_ok, procedimento_ok)

    if valor_ok and data_ok and nome_ok:
        status = "sugestao_pronta"
        motivo = "Valor, data e nome confirmados."
    elif criterios_batidos >= 2:
        status = "sugestao_verde"
        motivo = f"Sugestao forte: {criterios_batidos} criterios batendo."
    elif dv <= Decimal("5.00") and dd <= 5:
        status = "revisar"
        motivo = "Sugestao: valor, data, nome ou procedimento precisam de conferencia manual."
    else:
        status = "revisar"
        motivo = "Correspondência provável, confira antes de conciliar."

    return {
        "atendimento": at,
        "status": status,
        "motivo": motivo,
        "diferenca_valor": float(dv),
        "diferenca_dias": dd,
        "criterios_batidos": criterios_batidos,
    }


def importar_vendas_cartao(
    db: Session,
    cliente_id: int,
    df: pd.DataFrame,
    origem_arquivo: str,
) -> int:
    """
    Importa extrato da maquininha como VendaCartao individuais.
    Colunas esperadas: data_venda, data_pagamento, bandeira, ultimos_digitos,
    nome_portador, valor_bruto, taxa_percentual, valor_liquido, parcelas.
    """
    df = df.copy()
    df.columns = [_norm_col(c) for c in df.columns]

    def _col(*names):
        for n in names:
            if n in df.columns:
                return n
        return None

    c_data_v  = _col("data_venda", "data_da_venda", "data_transacao", "data")
    c_data_p  = _col("data_pagamento", "data_credito", "data_do_credito", "data_repasse")
    c_bandeira = _col("bandeira", "bandeira_cartao", "brand", "rede")
    c_digitos  = _col("ultimos_digitos", "4_ultimos_digitos", "digitos_cartao", "final_cartao", "card_last4")
    c_portador = _col("nome_portador", "portador", "titular", "nome", "cliente")
    c_bruto    = _col("valor_bruto", "valor", "gross_amount", "bruto", "valor_da_venda")
    c_taxa     = _col("taxa_percentual", "taxa", "mdr", "fee", "taxa_pct")
    c_liquido  = _col("valor_liquido", "liquido", "net_amount", "valor_liq")
    c_parcelas = _col("parcelas", "num_parcelas", "parcelamento", "qtd_parcelas")
    c_desc     = _col("descricao", "estabelecimento", "historico")

    if not c_bruto or not c_data_p:
        raise ValueError(
            "Arquivo não contém colunas de valor e data de pagamento reconhecíveis. "
            "Colunas necessárias: valor_bruto (ou valor), data_pagamento (ou data_credito)."
        )

    importados = 0
    for _, row in df.iterrows():
        try:
            valor_bruto = _decimal_seguro(row[c_bruto])
            data_pgto   = pd.to_datetime(row[c_data_p]).date()
        except Exception:
            continue

        if valor_bruto <= Decimal("0"):
            continue

        data_venda = data_pgto
        if c_data_v:
            try:
                data_venda = pd.to_datetime(row[c_data_v]).date()
            except Exception:
                pass

        def _v(col):
            if col and pd.notna(row.get(col)):
                s = str(row[col]).strip()
                return s if s and s.lower() not in ("nan", "none", "") else None
            return None

        digitos = None
        if c_digitos and pd.notna(row.get(c_digitos)):
            d = str(row[c_digitos]).strip().split(".")[0]
            digitos = d.zfill(4)[-4:] if d else None

        taxa = None
        if c_taxa and pd.notna(row.get(c_taxa)):
            try:
                taxa = Decimal(str(row[c_taxa]))
            except Exception:
                pass

        liquido = None
        if c_liquido and pd.notna(row.get(c_liquido)):
            try:
                liquido = _decimal_seguro(row[c_liquido])
            except Exception:
                pass

        if liquido is None and taxa is not None:
            fator = Decimal("1") - (taxa / Decimal("100"))
            liquido = (valor_bruto * fator).quantize(Decimal("0.01"))

        if liquido is None:
            liquido = valor_bruto

        parcelas = 1
        if c_parcelas and pd.notna(row.get(c_parcelas)):
            try:
                parcelas = int(row[c_parcelas])
            except Exception:
                pass

        db.add(VendaCartao(
            cliente_id=cliente_id,
            data_venda=data_venda,
            data_pagamento=data_pgto,
            bandeira=_v(c_bandeira),
            ultimos_digitos=digitos,
            nome_portador=_v(c_portador),
            valor_bruto=valor_bruto,
            taxa_percentual=taxa,
            valor_liquido=liquido,
            parcelas=parcelas,
            descricao=_v(c_desc),
            status=StatusVendaCartao.pendente,
            origem_arquivo=origem_arquivo,
        ))
        importados += 1

    db.commit()
    return importados


def fechar_lote_dia(
    db: Session,
    cliente_id: int,
    data_pagamento,
    bandeira: str | None,
) -> TransferenciaCartao:
    """
    Agrupa as VendaCartao pendentes de um dia/bandeira em um TransferenciaCartao (lote).
    Retorna o lote criado ou atualizado.
    """
    from sqlalchemy import func as sqlfunc

    filtro = [
        VendaCartao.cliente_id == cliente_id,
        VendaCartao.data_pagamento == data_pagamento,
        VendaCartao.status == StatusVendaCartao.conciliado,
    ]
    if bandeira:
        filtro.append(VendaCartao.bandeira == bandeira)

    vendas = db.query(VendaCartao).filter(*filtro).all()
    if not vendas:
        raise ValueError("Nenhuma venda pendente encontrada para fechar.")

    bandeira_lote = bandeira or vendas[0].bandeira or "Outros"
    valor_bruto   = sum(v.valor_bruto for v in vendas)
    valor_liquido = sum(v.valor_liquido or v.valor_bruto for v in vendas)
    taxa_total    = valor_bruto - valor_liquido

    lote = db.query(TransferenciaCartao).filter(
        TransferenciaCartao.cliente_id == cliente_id,
        TransferenciaCartao.data == data_pagamento,
        TransferenciaCartao.bandeira == bandeira_lote,
        TransferenciaCartao.status == StatusTransferenciaCartao.pendente,
    ).first()

    if lote is None:
        lote = TransferenciaCartao(
            cliente_id=cliente_id,
            data=data_pagamento,
            bandeira=bandeira_lote,
            valor_bruto=valor_bruto,
            taxa_total=taxa_total,
            valor_liquido=valor_liquido,
            qtd_transacoes=len(vendas),
            status=StatusTransferenciaCartao.pendente,
        )
        db.add(lote)
        db.flush()
    else:
        lote.valor_bruto    = valor_bruto
        lote.taxa_total     = taxa_total
        lote.valor_liquido  = valor_liquido
        lote.qtd_transacoes = len(vendas)

    for v in vendas:
        v.status  = StatusVendaCartao.fechado
        v.lote_id = lote.id

    db.commit()
    return lote


def importar_extrato_conta_corrente(
    db: Session,
    cliente_id: int,
    df: pd.DataFrame,
    origem_arquivo: str,
) -> dict:
    """
    Importa extrato da conta corrente como ExtratoLinhaBancaria.
    A conciliacao fica pendente para confirmacao individual ou em lote.
    """
    col_valor     = _extrair_coluna(df, ["valor", "amount", "credito", "valor_bruto", "vlr"])
    col_data      = _extrair_coluna(df, ["data", "date", "data_lancamento", "data_credito", "dt_lancamento"])
    col_descricao = _extrair_coluna(df, ["descricao", "historico", "memo", "titulo", "complemento"])
    col_tipo      = _extrair_coluna(df, ["tipo", "type", "dc", "natureza", "debcred"])

    if col_valor is None or col_data is None:
        raise ValueError("Arquivo não contém colunas de valor e data reconhecíveis.")

    importados = 0

    for idx, row in df.iterrows():
        try:
            valor_raw  = _decimal_seguro(row[col_valor.name])
            data_linha = pd.to_datetime(row[col_data.name]).date()
        except Exception:
            continue

        if col_tipo is not None and pd.notna(row.get(col_tipo.name)):
            tipo_raw = str(row[col_tipo.name]).strip().upper()
            tipo = "credito" if tipo_raw in ("C", "CR", "CRED", "CREDITO", "CREDIT", "C/R") else "debito"
            valor = abs(valor_raw)
        else:
            tipo  = "credito" if valor_raw > Decimal("0") else "debito"
            valor = abs(valor_raw)

        if valor <= Decimal("0"):
            continue

        descricao = (
            str(row[col_descricao.name]).strip()
            if col_descricao is not None and pd.notna(row.get(col_descricao.name))
            else None
        )

        linha = ExtratoLinhaBancaria(
            cliente_id=cliente_id,
            data=data_linha,
            descricao=descricao,
            valor=valor,
            tipo=tipo,
            status=StatusExtratoLinha.importado,
            origem_arquivo=origem_arquivo,
        )
        db.add(linha)
        db.flush()
        importados += 1

    db.commit()
    return {"importados": importados}
