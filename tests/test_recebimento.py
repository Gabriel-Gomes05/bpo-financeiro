from datetime import date

import pytest

from app.services.recebimento_service import prever_recebimento


@pytest.mark.parametrize("dia, esperado", [(7, 9), (10, 14), (11, 15), (12, 15), (13, 15)])
@pytest.mark.parametrize("intervalo", [0, 30, 60, 90])
def test_antecipacao_dois_dias_uteis(dia, esperado, intervalo):
    assert prever_recebimento(date(2026, 9, dia), intervalo, "cartao_credito", True) == date(2026, 9, esperado)


def test_credito_sem_antecipacao_preserva_prazo():
    assert prever_recebimento(date(2026, 9, 11), 30, "cartao_credito", False) == date(2026, 10, 11)


@pytest.mark.parametrize("dia, esperado", [(7, 8), (11, 14), (12, 14), (13, 14)])
def test_debito_antecipado_um_dia_util(dia, esperado):
    assert prever_recebimento(date(2026, 9, dia), 0, "cartao_debito", True) == date(2026, 9, esperado)


def test_debito_sem_antecipacao_preserva_prazo():
    assert prever_recebimento(date(2026, 9, 11), 0, "cartao_debito", False) == date(2026, 9, 11)


@pytest.mark.parametrize("forma", ["pix", "dinheiro", "boleto", None])
def test_outros_meios_preservam_prazo(forma):
    assert prever_recebimento(date(2026, 9, 11), 0, forma, True) == date(2026, 9, 11)
