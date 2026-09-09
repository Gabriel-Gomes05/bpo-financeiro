from datetime import date, timedelta


def prever_recebimento(
    data_atendimento: date, dias: int, forma: str | None, antecipa: bool,
) -> date:
    """Crédito antecipado vence em D+2 úteis (segunda a sexta), em todas as parcelas."""
    if not antecipa or forma != "cartao_credito":
        return data_atendimento + timedelta(days=dias)

    prevista = data_atendimento
    restantes = 2
    while restantes:
        prevista += timedelta(days=1)
        if prevista.weekday() < 5:
            restantes -= 1
    return prevista
