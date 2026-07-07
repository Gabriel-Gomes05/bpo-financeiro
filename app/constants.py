"""Categorias do DRE — usadas em Orçamento, DRE e Contas a Pagar."""

GRUPOS_DRE = [
    {
        "nome": "RECEITAS",
        "tipo": "receita",
        "categorias": [
            {"key": "rec_consultas",     "nome": "Consultas Médicas"},
            {"key": "rec_procedimentos", "nome": "Procedimentos"},
            {"key": "rec_exames",        "nome": "Exames"},
            {"key": "rec_convenios",     "nome": "Convênios"},
            {"key": "rec_outros",        "nome": "Outros Recebimentos"},
        ],
    },
    {
        "nome": "CUSTOS VARIÁVEIS",
        "tipo": "despesa",
        "categorias": [
            {"key": "cv_material",   "nome": "Material Médico / Hospitalar"},
            {"key": "cv_terceiros",  "nome": "Exames Terceirizados"},
            {"key": "cv_honorarios", "nome": "Honorários Médicos"},
        ],
    },
    {
        "nome": "DESPESAS FIXAS",
        "tipo": "despesa",
        "categorias": [
            {"key": "df_aluguel",    "nome": "Aluguel"},
            {"key": "df_folha",      "nome": "Folha de Pagamento"},
            {"key": "df_encargos",   "nome": "Encargos Sociais"},
            {"key": "df_energia",    "nome": "Energia Elétrica"},
            {"key": "df_agua",       "nome": "Água e Esgoto"},
            {"key": "df_internet",   "nome": "Internet e Telefone"},
            {"key": "df_manutencao", "nome": "Manutenção"},
            {"key": "df_limpeza",    "nome": "Limpeza e Higiene"},
        ],
    },
    {
        "nome": "DESPESAS ADMINISTRATIVAS",
        "tipo": "despesa",
        "categorias": [
            {"key": "da_contabil",  "nome": "Honorários Contábeis"},
            {"key": "da_impostos",  "nome": "Impostos e Taxas"},
            {"key": "da_software",  "nome": "Software e Sistemas"},
            {"key": "da_marketing", "nome": "Marketing"},
            {"key": "da_seguros",   "nome": "Seguros"},
            {"key": "da_outros",    "nome": "Outros"},
        ],
    },
]

# Apenas categorias de despesa, com grupo, para usar no select de Contas a Pagar
CATEGORIAS_DESPESA = [
    {"key": cat["key"], "nome": cat["nome"], "grupo": grupo["nome"]}
    for grupo in GRUPOS_DRE
    if grupo["tipo"] == "despesa"
    for cat in grupo["categorias"]
]

# Mapa key → nome para lookups rápidos
CATEGORIA_NOME: dict[str, str] = {
    cat["key"]: cat["nome"]
    for grupo in GRUPOS_DRE
    for cat in grupo["categorias"]
}
