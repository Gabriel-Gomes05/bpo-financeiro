"""Testes da seleção automática de taxa por faixa de parcelamento."""
from types import SimpleNamespace

from app.services.conciliacao_service import _selecionar_taxa_por_parcelas


def taxa(id, faixa, inicial=None, final=None, maquininha_id=None):
    """Cria um objeto mínimo com os atributos usados pela regra."""
    return SimpleNamespace(
        id=id,
        faixa_parcelamento=faixa,
        parcela_inicial=inicial,
        parcela_final=final,
        maquininha_id=maquininha_id,
    )


def test_faixas_padrao():
    taxas = [
        taxa(1, "avista_credito"),
        taxa(2, "parcelado_2_6"),
        taxa(3, "parcelado_6_12"),
    ]
    assert _selecionar_taxa_por_parcelas(taxas, 1).id == 1
    assert _selecionar_taxa_por_parcelas(taxas, 6).id == 2
    assert _selecionar_taxa_por_parcelas(taxas, 7).id == 3


def test_personalizada_tem_prioridade():
    taxas = [
        taxa(1, "parcelado_2_6"),
        taxa(2, "personalizada", 3, 5),
    ]
    assert _selecionar_taxa_por_parcelas(taxas, 4).id == 2


def test_faixa_personalizada_mais_especifica_vence():
    taxas = [
        taxa(1, "personalizada", 2, 10),
        taxa(2, "personalizada", 4, 6),
    ]
    assert _selecionar_taxa_por_parcelas(taxas, 5).id == 2


def test_sem_faixa_compativel():
    assert _selecionar_taxa_por_parcelas([taxa(1, "parcelado_2_6")], 18) is None
