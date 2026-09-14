from datetime import date, timedelta


def prever_recebimento(
    data_atendimento: date, dias: int, forma: str | None, antecipa: bool,
) -> date:
    """Calcula cartões antecipados em dias úteis; demais formas mantêm o prazo informado."""
    dias_uteis = {"cartao_credito": 2, "cartao_debito": 1}.get(forma)
    if not antecipa or dias_uteis is None:
        return data_atendimento + timedelta(days=dias)

    prevista = data_atendimento
    restantes = dias_uteis
    while restantes:
        prevista += timedelta(days=1)
        if prevista.weekday() < 5:
            restantes -= 1
    return prevista
