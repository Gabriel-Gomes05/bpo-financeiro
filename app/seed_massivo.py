from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.database import SessionLocal
from app.models import (
    Atendimento,
    ClienteBPO,
    CondicaoPagamento,
    ContaPagar,
    DiaSemana,
    DivergenciaConciliacao,
    FechamentoDiario,
    FormaPagamento,
    MovimentacaoBancaria,
    PerfilUsuario,
    StatusConciliacao,
    StatusContaPagar,
    StatusMovimentacaoBancaria,
    StatusTransferenciaCartao,
    StatusVendaCartao,
    TarefaRotina,
    TipoContaPagar,
    TransferenciaCartao,
    Usuario,
    VendaCartao,
)

MARKER = "SEED_MASSIVO"
ORIGEM = "seed_massivo.csv"
DATA_INICIO = date(2026, 8, 3)
LOTE_INICIO = date(2026, 9, 1)

BANDEIRAS = ["Visa", "Mastercard", "Elo"]
TAXAS = {
    "Visa": Decimal("2.50"),
    "Mastercard": Decimal("2.99"),
    "Elo": Decimal("3.20"),
}
CATEGORIAS = [
    "df_aluguel",
    "df_folha",
    "df_energia",
    "df_internet",
    "da_contabil",
    "da_software",
    "da_impostos",
    "cv_material",
]
DIAS_SEMANA = {
    0: DiaSemana.seg,
    1: DiaSemana.ter,
    2: DiaSemana.qua,
    3: DiaSemana.qui,
    4: DiaSemana.sex,
}


def brl(valor: int | str) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def liquido(valor: Decimal, bandeira: str) -> Decimal:
    taxa = TAXAS[bandeira]
    return (valor * (Decimal("1") - taxa / Decimal("100"))).quantize(Decimal("0.01"))


def dia_util(base: date, offset: int) -> date:
    d = base + timedelta(days=offset)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d


def limpar_massivo(db):
    db.execute(text("""
        UPDATE movimentacoes_bancarias
        SET conciliada_com_atendimento_id = NULL,
            transferencia_cartao_id = NULL,
            conta_pagar_id = NULL
        WHERE origem_arquivo = :origem
    """), {"origem": ORIGEM})
    db.execute(text("""
        UPDATE vendas_cartao
        SET atendimento_id = NULL, lote_id = NULL
        WHERE origem_arquivo = :origem
    """), {"origem": ORIGEM})
    db.execute(text("DELETE FROM movimentacoes_bancarias WHERE origem_arquivo = :origem"), {"origem": ORIGEM})
    db.execute(text("DELETE FROM vendas_cartao WHERE origem_arquivo = :origem"), {"origem": ORIGEM})
    db.execute(text("""
        DELETE FROM transferencias_cartao
        WHERE data >= :ini AND data < :fim
    """), {"ini": LOTE_INICIO, "fim": LOTE_INICIO + timedelta(days=30)})
    db.execute(text("DELETE FROM divergencias_conciliacao WHERE motivo LIKE :m"), {"m": f"%{MARKER}%"})
    db.execute(text("DELETE FROM fechamentos_diarios WHERE observacao LIKE :m"), {"m": f"%{MARKER}%"})
    db.execute(text("DELETE FROM tarefas_rotina WHERE descricao LIKE :m"), {"m": f"%{MARKER}%"})
    db.execute(text("DELETE FROM contas_pagar WHERE observacao LIKE :m"), {"m": f"%{MARKER}%"})
    db.execute(text("DELETE FROM atendimentos WHERE observacao LIKE :m"), {"m": f"%{MARKER}%"})
    db.commit()


def usuario_padrao(db, cliente: ClienteBPO) -> Usuario:
    usuario = None
    if cliente.funcionario_id:
        usuario = db.query(Usuario).filter(Usuario.id == cliente.funcionario_id).first()
    if not usuario:
        usuario = db.query(Usuario).filter(Usuario.perfil == PerfilUsuario.funcionario).first()
    return usuario


def criar_receitas(db, cliente: ClienteBPO, usuario: Usuario):
    atendimentos = []
    vendas = []
    movs = []

    for i in range(12):
        d = dia_util(DATA_INICIO, i)

        # Recebimento PIX/TED com match bancario.
        valor_pix = brl(180 + cliente.id * 15 + i * 17)
        forma = FormaPagamento.pix if i % 2 == 0 else FormaPagamento.transferencia
        cond = CondicaoPagamento.pix if forma == FormaPagamento.pix else CondicaoPagamento.transferencia
        at_pix = Atendimento(
            cliente_id=cliente.id,
            data_atendimento=d,
            nome_paciente=f"Paciente {cliente.nome} PIX {i + 1:02d}",
            cpf_paciente=f"100.200.{cliente.id:03d}-{i:02d}",
            medico=f"Dr(a). Teste {cliente.nome}",
            especialidade=cliente.especialidade,
            tipo_servico="Consulta",
            descricao_servico=f"{MARKER} atendimento PIX/TED",
            valor_servico=valor_pix,
            condicao_pagamento=cond,
            forma_pagamento=forma,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=d,
            valor_liquido=valor_pix,
            valor_clinica=valor_pix,
            status_conciliacao=StatusConciliacao.pendente,
            observacao=MARKER,
            lancado_por_id=usuario.id,
        )
        atendimentos.append(at_pix)
        movs.append(MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            sentido="recebimento",
            data_movimento=d if i % 4 else d + timedelta(days=1),
            valor=valor_pix if i % 5 else valor_pix + brl("2.50"),
            descricao=f"{MARKER} PIX/TED paciente {i + 1:02d}",
            cpf_digitos_meio=f"{cliente.id:03d}{i:03d}",
            origem_arquivo=ORIGEM,
            status=StatusMovimentacaoBancaria.importada,
        ))

        # Dinheiro para testar lancamentos sem conciliacao bancaria.
        valor_dinheiro = brl(90 + cliente.id * 8 + i * 9)
        atendimentos.append(Atendimento(
            cliente_id=cliente.id,
            data_atendimento=d,
            nome_paciente=f"Paciente {cliente.nome} DIN {i + 1:02d}",
            medico=f"Dr(a). Teste {cliente.nome}",
            especialidade=cliente.especialidade,
            tipo_servico="Retorno",
            descricao_servico=f"{MARKER} atendimento dinheiro",
            valor_servico=valor_dinheiro,
            condicao_pagamento=CondicaoPagamento.dinheiro,
            forma_pagamento=FormaPagamento.dinheiro,
            parcela_numero=1,
            parcela_total=1,
            data_prevista_recebimento=d,
            valor_liquido=valor_dinheiro,
            valor_clinica=valor_dinheiro,
            status_conciliacao=StatusConciliacao.pendente,
            observacao=MARKER,
            lancado_por_id=usuario.id,
        ))

        if cliente.tem_maquininha:
            for j in range(2):
                bandeira = BANDEIRAS[(i + j + cliente.id) % len(BANDEIRAS)]
                valor = brl(240 + cliente.id * 20 + i * 23 + j * 75)
                digitos = f"{cliente.id}{i:02d}{j}"[-4:].zfill(4)
                data_pag = d + timedelta(days=30)
                at_cartao = Atendimento(
                    cliente_id=cliente.id,
                    data_atendimento=d,
                    nome_paciente=f"Paciente {cliente.nome} CARD {i + 1:02d}-{j + 1}",
                    medico=f"Dr(a). Teste {cliente.nome}",
                    especialidade=cliente.especialidade,
                    tipo_servico="Procedimento",
                    descricao_servico=f"{MARKER} atendimento cartao",
                    valor_servico=valor,
                    condicao_pagamento=CondicaoPagamento.avista,
                    forma_pagamento=FormaPagamento.cartao_credito,
                    parcela_numero=1,
                    parcela_total=1,
                    data_prevista_recebimento=data_pag,
                    ultimos_digitos_cartao=digitos,
                    bandeira_cartao=bandeira,
                    taxa_cartao=TAXAS[bandeira],
                    valor_liquido=liquido(valor, bandeira),
                    valor_clinica=liquido(valor, bandeira),
                    status_conciliacao=StatusConciliacao.pendente,
                    observacao=MARKER,
                    lancado_por_id=usuario.id,
                )
                atendimentos.append(at_cartao)

                valor_venda = valor
                if i % 6 == 2 and j == 1:
                    valor_venda = valor + brl("3.00")
                vendas.append(VendaCartao(
                    cliente_id=cliente.id,
                    data_venda=d,
                    data_pagamento=data_pag,
                    bandeira=bandeira,
                    ultimos_digitos=digitos,
                    nome_portador=f"PORTADOR {cliente.nome} {i + 1:02d}{j + 1}",
                    valor_bruto=valor_venda,
                    taxa_percentual=TAXAS[bandeira],
                    valor_liquido=liquido(valor_venda, bandeira),
                    parcelas=1,
                    descricao=f"{MARKER} venda cartao",
                    status=StatusVendaCartao.pendente,
                    origem_arquivo=ORIGEM,
                ))

            # Venda sem atendimento correspondente.
            if i in (3, 9):
                bandeira = BANDEIRAS[(i + cliente.id) % len(BANDEIRAS)]
                valor_extra = brl(333 + cliente.id * 11 + i * 7)
                vendas.append(VendaCartao(
                    cliente_id=cliente.id,
                    data_venda=d,
                    data_pagamento=d + timedelta(days=30),
                    bandeira=bandeira,
                    ultimos_digitos=f"9{cliente.id}{i}"[-4:].zfill(4),
                    nome_portador=f"SEM MATCH {cliente.nome} {i}",
                    valor_bruto=valor_extra,
                    taxa_percentual=TAXAS[bandeira],
                    valor_liquido=liquido(valor_extra, bandeira),
                    parcelas=1,
                    descricao=f"{MARKER} venda sem atendimento",
                    status=StatusVendaCartao.pendente,
                    origem_arquivo=ORIGEM,
                ))

    db.add_all(atendimentos + vendas + movs)
    db.commit()
    return len(atendimentos), len(vendas), len(movs)


def criar_lotes(db, cliente: ClienteBPO):
    if not cliente.tem_maquininha:
        return 0, 0

    lotes = []
    movs = []
    for i, bandeira in enumerate(BANDEIRAS):
        data_lote = LOTE_INICIO + timedelta(days=cliente.id + i)
        bruto = brl(1800 + cliente.id * 120 + i * 430)
        taxa_total = (bruto * TAXAS[bandeira] / Decimal("100")).quantize(Decimal("0.01"))
        liquido_lote = bruto - taxa_total
        lote = TransferenciaCartao(
            cliente_id=cliente.id,
            data=data_lote,
            bandeira=bandeira,
            valor_bruto=bruto,
            taxa_total=taxa_total,
            valor_liquido=liquido_lote,
            qtd_transacoes=3 + i,
            status=StatusTransferenciaCartao.pendente,
        )
        db.add(lote)
        db.flush()

        valor_banco = liquido_lote
        if i == 2:
            valor_banco = liquido_lote - brl("1.75")
        movs.append(MovimentacaoBancaria(
            cliente_id=cliente.id,
            tipo="pix_ted",
            sentido="recebimento",
            data_movimento=data_lote,
            valor=valor_banco,
            descricao=f"{MARKER} REPASSE {cliente.rede_maquininha or 'MAQUININHA'} {bandeira}",
            origem_arquivo=ORIGEM,
            status=StatusMovimentacaoBancaria.importada,
        ))
        lotes.append(lote)

    db.add_all(movs)
    db.commit()
    return len(lotes), len(movs)


def criar_despesas(db, cliente: ClienteBPO, usuario: Usuario):
    contas = []
    movs = []
    fornecedores = [
        "Aluguel Teste",
        "Energia Teste",
        "Internet Teste",
        "Contabilidade Teste",
        "Software Teste",
        "Material Medico Teste",
        "Impostos Teste",
        "Folha Teste",
        "Limpeza Teste",
        "Marketing Teste",
    ]
    status_cycle = [
        StatusContaPagar.pendente,
        StatusContaPagar.agendado,
        StatusContaPagar.pago,
        StatusContaPagar.cancelado,
        StatusContaPagar.aguardando_aprovacao,
    ]

    for i in range(14):
        venc = DATA_INICIO + timedelta(days=i * 2)
        valor = brl(160 + cliente.id * 25 + i * 38)
        status = status_cycle[i % len(status_cycle)]
        data_pagamento = venc if status == StatusContaPagar.pago else None
        conta = ContaPagar(
            cliente_id=cliente.id,
            descricao=f"{MARKER} despesa {i + 1:02d} - {fornecedores[i % len(fornecedores)]}",
            fornecedor=fornecedores[i % len(fornecedores)],
            tipo=TipoContaPagar.fixa if i % 3 == 0 else TipoContaPagar.pontual,
            valor=valor,
            vencimento=venc,
            data_pagamento=data_pagamento,
            status=status,
            categoria_dre=CATEGORIAS[i % len(CATEGORIAS)],
            observacao=MARKER,
            lancado_por_id=usuario.id,
        )
        db.add(conta)
        db.flush()
        contas.append(conta)

        if status in (StatusContaPagar.agendado, StatusContaPagar.pago):
            movs.append(MovimentacaoBancaria(
                cliente_id=cliente.id,
                tipo="pix_ted",
                sentido="pagamento",
                data_movimento=venc if i % 4 else venc + timedelta(days=1),
                valor=valor if i % 5 else valor + brl("4.00"),
                descricao=f"{MARKER} PAGAMENTO {fornecedores[i % len(fornecedores)]}",
                origem_arquivo=ORIGEM,
                status=StatusMovimentacaoBancaria.importada,
                conta_pagar_id=conta.id if status == StatusContaPagar.pago else None,
            ))

    db.add_all(movs)
    db.commit()
    return len(contas), len(movs)


def criar_operacional(db, cliente: ClienteBPO, usuario: Usuario):
    tarefas = []
    fechamentos = []
    divergencias = []

    for i in range(10):
        d = dia_util(DATA_INICIO, i)
        tarefas.append(TarefaRotina(
            cliente_id=cliente.id,
            funcionario_id=usuario.id,
            data=d,
            descricao=f"{MARKER} rotina teste {i + 1:02d}",
            horario_previsto=f"{9 + (i % 8):02d}:00",
            concluida=i % 3 == 0,
            concluida_em=datetime.combine(d, datetime.min.time()) + timedelta(hours=10) if i % 3 == 0 else None,
            dia_semana=DIAS_SEMANA.get(d.weekday()),
        ))

    for i in range(8):
        d = DATA_INICIO + timedelta(days=i)
        receitas = brl(1800 + cliente.id * 130 + i * 210)
        despesas = brl(700 + cliente.id * 80 + i * 95)
        saldo = brl(10000 + cliente.id * 500 + i * 150)
        fechamentos.append(FechamentoDiario(
            cliente_id=cliente.id,
            data=d,
            total_receitas_dia=receitas,
            total_despesas_dia=despesas,
            saldo_conta=saldo,
            saldo_provisorio_final=saldo + receitas - despesas,
            observacao=f"{MARKER} fechamento diario",
            enviado_cliente=i % 2 == 0,
            enviado_em=datetime.combine(d, datetime.min.time()) + timedelta(hours=18) if i % 2 == 0 else None,
            gerado_por_id=usuario.id,
        ))

    divergencias.extend([
        DivergenciaConciliacao(
            cliente_id=cliente.id,
            tipo="cartao",
            data_extrato=DATA_INICIO + timedelta(days=2),
            valor=brl(399 + cliente.id),
            digitos_cartao=f"{cliente.id}777"[-4:].zfill(4),
            motivo=f"{MARKER} cartao sem correspondencia exata",
            resolvida=False,
        ),
        DivergenciaConciliacao(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_extrato=DATA_INICIO + timedelta(days=4),
            valor=brl(512 + cliente.id),
            motivo=f"{MARKER} PIX/TED com diferenca pequena",
            resolvida=False,
        ),
        DivergenciaConciliacao(
            cliente_id=cliente.id,
            tipo="pix_ted",
            data_extrato=DATA_INICIO + timedelta(days=6),
            valor=brl(870 + cliente.id),
            motivo=f"{MARKER} saida bancaria sem conta vinculada",
            resolvida=False,
        ),
    ])

    db.add_all(tarefas + fechamentos + divergencias)
    db.commit()
    return len(tarefas), len(fechamentos), len(divergencias)


def main():
    db = SessionLocal()
    try:
        limpar_massivo(db)
        clientes = db.query(ClienteBPO).filter(ClienteBPO.ativo == True).order_by(ClienteBPO.id).all()
        totais = {
            "atendimentos": 0,
            "vendas_cartao": 0,
            "movimentacoes": 0,
            "lotes": 0,
            "contas": 0,
            "tarefas": 0,
            "fechamentos": 0,
            "divergencias": 0,
        }

        for cliente in clientes:
            usuario = usuario_padrao(db, cliente)
            at, vendas, mov_rec = criar_receitas(db, cliente, usuario)
            lotes, mov_lotes = criar_lotes(db, cliente)
            contas, mov_desp = criar_despesas(db, cliente, usuario)
            tarefas, fechamentos, divergencias = criar_operacional(db, cliente, usuario)

            totais["atendimentos"] += at
            totais["vendas_cartao"] += vendas
            totais["movimentacoes"] += mov_rec + mov_lotes + mov_desp
            totais["lotes"] += lotes
            totais["contas"] += contas
            totais["tarefas"] += tarefas
            totais["fechamentos"] += fechamentos
            totais["divergencias"] += divergencias

            print(
                f"{cliente.id:02d} {cliente.nome:<12} | "
                f"atend={at:3d} vendas={vendas:3d} mov={mov_rec + mov_lotes + mov_desp:3d} "
                f"lotes={lotes:2d} contas={contas:2d}"
            )

        print("\nSeed massivo concluido.")
        for chave, valor in totais.items():
            print(f"{chave}: {valor}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
