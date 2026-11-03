"""Gera docs/CODIGOS_DE_ERRO.md a partir do catálogo em app/errors.py.

Uso:  python scripts/gerar_catalogo_erros.py
O teste tests/test_codigos_erro.py falha se o documento estiver desatualizado.
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.errors import AREAS, CATALOGO  # noqa: E402

DESTINO = RAIZ / "docs" / "CODIGOS_DE_ERRO.md"


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def gerar() -> str:
    linhas = [
        "# Códigos de erro do FLIC",
        "",
        "> Documento gerado automaticamente a partir de `app/errors.py`.",
        "> Não edite à mão: altere o catálogo e rode `python scripts/gerar_catalogo_erros.py`.",
        "",
        "Todo erro mostrado pelo FLIC traz um código no formato **`FLIC-ÁREA-NNN`**.",
        "Dentro do sistema, a mesma lista está em **Códigos de erro** (menu lateral, `/ajuda/erros`).",
        "",
        "## Como ler um erro",
        "",
        "- **Página de erro:** mostra o código, a mensagem, o que fazer e um *identificador* da requisição.",
        "- **Aviso na tela** (após salvar ou importar): a mensagem começa com o código, por exemplo",
        "  `[FLIC-IMP-102] Linha 7: ignorada — valor inválido (abc).`",
        "- **API / JSON:** o corpo traz `code`, `message` e `request_id`.",
        "- **Log do servidor:** os eventos `http_error`, `unhandled_request_error` e `file_processing_failed`",
        "  levam o campo `error_code`. Para investigar, procure pelo identificador da requisição:",
        "  `docker compose logs web | grep <identificador>`.",
        "",
        "## Faixas de numeração",
        "",
        "| Faixa | Uso |",
        "|---|---|",
        "| `FLIC-GER-4xx/5xx` | Códigos gerais, atribuídos pelo status HTTP quando o erro ainda não tem código próprio. |",
        "| `FLIC-<ÁREA>-001…099` | Erros de regra de negócio e validação de cada área. |",
        "| `FLIC-IMP-101…199` | Avisos linha a linha das importações (a linha é ignorada ou um campo fica em branco). |",
        "| `FLIC-IMP-901…999` | Falhas inesperadas de importação, uma por tipo de arquivo (detalhes no log). |",
        "",
        "## Áreas",
        "",
        "| Sigla | Área | Códigos |",
        "|---|---|---|",
    ]
    for sigla, nome in AREAS.items():
        qtd = sum(1 for c in CATALOGO if c.split("-")[1] == sigla)
        linhas.append(f"| `{sigla}` | [{nome}](#{_ancora(f'{sigla} — {nome}')}) | {qtd} |")
    linhas.append("")

    for sigla, nome in AREAS.items():
        itens = [d for c, d in sorted(CATALOGO.items()) if c.split("-")[1] == sigla]
        if not itens:
            continue
        linhas += [f"## {sigla} — {nome}", "", "| Código | HTTP | Título | Mensagem | Causa | O que fazer |",
                   "|---|---|---|---|---|---|"]
        for d in itens:
            titulo = d.titulo + (f" <br>`?erro={d.slug}`" if d.slug else "")
            linhas.append(
                f"| `{d.codigo}` | {d.status} | {_celula(titulo)} | {_celula(d.mensagem)} "
                f"| {_celula(d.causa)} | {_celula(d.solucao)} |"
            )
        linhas.append("")

    linhas += [
        "## Como criar um código novo",
        "",
        "1. Escolha a área e o próximo número livre da faixa em `app/errors.py` (lista `_DEFINICOES`).",
        "2. Preencha título, mensagem, causa e o que fazer, pensando em quem vai ler: o usuário e o suporte.",
        "3. No código, use `raise erro(\"FLIC-XXX-NNN\")` para páginas de erro ou",
        "   `com_codigo(\"FLIC-XXX-NNN\", mensagem)` para avisos na tela.",
        "4. Rode `python scripts/gerar_catalogo_erros.py` e faça commit do documento junto.",
        "5. Nunca reutilize um código para outro significado: códigos antigos aparecem em logs e chamados.",
        "",
    ]
    return "\n".join(linhas)


def _ancora(titulo: str) -> str:
    """Âncora no padrão do GitHub: minúsculas, sem pontuação, espaços viram hífen (acentos ficam)."""
    import re
    return re.sub(r"[^\w\- ]", "", titulo.lower()).replace(" ", "-")


if __name__ == "__main__":
    DESTINO.write_text(gerar(), encoding="utf-8", newline="\n")
    print(f"{DESTINO.relative_to(RAIZ)} atualizado ({len(CATALOGO)} códigos).")
