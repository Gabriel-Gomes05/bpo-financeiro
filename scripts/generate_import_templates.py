"""Gera o modelo de contas a pagar com as colunas aceitas pelo importador."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation


COLUNAS = {
    "descricao": "Obrigatoria. Descricao da despesa.",
    "fornecedor": "Nome do fornecedor (opcional).",
    "valor": "Obrigatorio. Valor positivo de cada ocorrencia, em reais.",
    "vencimento": "Obrigatorio. Data no formato DD/MM/AAAA ou data do Excel.",
    "data_competencia": "Data de competencia. Em branco, usa o vencimento.",
    "forma_pagamento": "pix, transferencia, cartao_credito, cartao_debito, dinheiro, boleto, cheque ou debito_automatico.",
    "plano_de_contas": "Codigo ou nome de uma conta de despesa ativa e disponivel para a empresa.",
    "recorrente": "sim ou nao. Em branco, considera o intervalo ou tipo informado.",
    "recorrencia_intervalo": "mensal, semanal, quinzenal ou personalizado. Avanca vencimento e competencia.",
    "recorrencia_dias": "Numero inteiro de dias, obrigatorio para intervalo personalizado.",
    "recorrencia_qtd": "Quantidade total de ocorrencias (incluindo a primeira), de 1 a 60. Padrao: 1.",
    "tipo": "pontual ou fixa. Coluna opcional para compatibilidade com modelos anteriores.",
    "observacao": "Observacoes (opcional).",
}


def gerar(destino: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Contas a pagar"
    ws.append(list(COLUNAS))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:M1001"
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="245A72")
        ws.column_dimensions[cell.column_letter].width = max(22, len(cell.value) + 3)
    for row in ws.iter_rows(min_row=2, max_row=1001, min_col=3, max_col=5):
        row[0].number_format = '#,##0.00'
        row[1].number_format = row[2].number_format = "dd/mm/yyyy"
    for coluna, opcoes in {
        "F": "pix,transferencia,cartao_credito,cartao_debito,dinheiro,boleto,cheque,debito_automatico",
        "H": "sim,nao",
        "I": "mensal,semanal,quinzenal,personalizado",
        "L": "pontual,fixa",
    }.items():
        validacao = DataValidation(type="list", formula1=f'"{opcoes}"', allow_blank=True)
        validacao.showErrorMessage = True
        validacao.errorTitle = "Valor invalido"
        validacao.error = "Selecione uma opcao da lista."
        ws.add_data_validation(validacao)
        validacao.add(f"{coluna}2:{coluna}1001")
    instrucoes = wb.create_sheet("Instrucoes")
    instrucoes.append(["Coluna", "Preenchimento"])
    for nome, descricao in COLUNAS.items():
        instrucoes.append([nome, descricao])
    instrucoes.column_dimensions["A"].width = 26
    instrucoes.column_dimensions["B"].width = 115
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb.save(destino)


if __name__ == "__main__":
    gerar(Path(__file__).resolve().parents[1] / "static/modelos/modelo_contas_pagar.xlsx")
