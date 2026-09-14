from datetime import date
from decimal import Decimal

from app.models import VendaCartao
from app.routers.conciliacao import _aplicar_taxa_individual


def venda() -> VendaCartao:
    return VendaCartao(
        cliente_id=1,
        data_venda=date.today(),
        data_pagamento=date.today(),
        valor_bruto=Decimal("100.00"),
        taxa_percentual=Decimal("2.00"),
        valor_liquido=Decimal("98.00"),
    )


def test_aplica_taxa_somente_na_venda_e_recalcula_liquido():
    item = venda()

    assert _aplicar_taxa_individual(item, "3,50") is True
    assert item.taxa_percentual == Decimal("3.50")
    assert item.valor_liquido == Decimal("96.50")


def test_mantem_valores_quando_taxa_nao_foi_informada():
    item = venda()

    assert _aplicar_taxa_individual(item, "") is True
    assert item.taxa_percentual == Decimal("2.00")
    assert item.valor_liquido == Decimal("98.00")


def test_rejeita_taxa_invalida_sem_alterar_venda():
    item = venda()

    assert _aplicar_taxa_individual(item, "100.01") is False
    assert _aplicar_taxa_individual(item, "invalida") is False
    assert item.taxa_percentual == Decimal("2.00")
    assert item.valor_liquido == Decimal("98.00")
