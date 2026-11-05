"""Gera as imagens da aba Tutorial (static/tutorial/*.webp) a partir do FLIC rodando localmente.

Uso (com o app local no ar e os usuários de QA cadastrados):
    pip install playwright pillow
    python scripts/gerar_prints_tutorial.py [http://127.0.0.1:8888]

Os prints usam somente dados fictícios do ambiente de QA.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8888"
SAIDA = Path(__file__).resolve().parents[1] / "static" / "tutorial"

USUARIOS = {
    "coordenador": ("qa.admin@flic.test", "QaTeste#2026", 8),
    "editor": ("qa.editor@flic.test", "QaEditor#2026", 8),
    "funcionario": ("qa.funcionario@flic.test", "QaFunc#2026", 9),
    "medico": ("qa.medico@flic.test", "QaMedico#2026", 1),
    "secretaria": ("maria.qa1793799363@flic.test", "Maria#2026", None),
}

# (arquivo, perfil, caminho, ação opcional)
PRINTS = [
    ("login", None, "/login", None),
    ("painel", "coordenador", "/painel", None),
    ("dashboard", "coordenador", "/", None),
    ("tarefas", "coordenador", "/tarefas", None),
    ("lancamentos", "coordenador", "/lancamentos?data_inicio=2026-09-01&data_fim=2026-11-30", None),
    ("lancamento-novo", "coordenador", "/lancamentos/novo", None),
    ("conciliacao-cartao", "coordenador", "/conciliacao", None),
    ("conciliacao-banco", "coordenador", "/conciliacao/banco?cliente_id=8", None),
    ("conciliacao-banco-lista", "coordenador", "/conciliacao/banco?cliente_id=8", "rolar:1100"),
    ("conciliacao-varios", "coordenador", "/conciliacao/banco?cliente_id=8", "conciliar_varios"),
    ("importacoes", "coordenador", "/importacoes", None),
    ("contas-pagar", "coordenador", "/contas-pagar", None),
    ("conta-pagar-nova", "coordenador", "/contas-pagar/novo", None),
    ("aprovacao", "coordenador", "/fechamento", None),
    ("receitas", "coordenador", "/gestao/receitas", None),
    ("despesas", "coordenador", "/gestao/despesas", None),
    ("orcamento", "coordenador", "/gestao/orcamento", None),
    ("dre", "coordenador", "/gestao/dre", None),
    ("fechamento-mensal", "coordenador", "/fechamento/mensal", None),
    ("clientes", "coordenador", "/admin/clientes", None),
    ("anotacoes", "coordenador", "/admin/anotacoes-clientes", None),
    ("grupos", "coordenador", "/admin/grupos", None),
    ("servicos", "coordenador", "/admin/servicos", None),
    ("funcionarios", "coordenador", "/admin/funcionarios", None),
    ("plano-contas", "coordenador", "/admin/plano-contas", None),
    ("auditoria-historico", "coordenador", "/auditoria/historico", None),
    ("auditoria-extratos", "coordenador", "/auditoria/extratos", None),
    ("secretarias", "coordenador", "/admin/secretarias", None),
    ("logs", "coordenador", "/logs", None),
    ("ajuda-erros", "coordenador", "/ajuda/erros", None),
    ("tema-escuro", "coordenador", "/", "escuro"),
    ("menu-recolhido", "coordenador", "/", "recolhido"),
    # menu e tela inicial de cada perfil
    ("menu-coordenador", "coordenador", "/", None),
    ("menu-editor", "editor", "/", None),
    ("menu-funcionario", "funcionario", "/", None),
    ("menu-medico", "medico", "/", None),
    ("menu-secretaria", "secretaria", "/lancamentos?data_inicio=2026-09-01&data_fim=2026-11-30", None),
    ("secretaria-novo", "secretaria", "/lancamentos/novo", None),
]


def salvar(png: bytes, nome: str) -> None:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    img.save(SAIDA / f"{nome}.webp", "WEBP", quality=82, method=6)


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch(channel="chrome")
        contextos = {}

        def pagina(perfil, tema="claro", menu="aberta"):
            chave = (perfil, tema, menu)
            if chave in contextos:
                return contextos[chave]
            ctx = nav.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script(
                f"try{{localStorage.setItem('flic-tema','{tema}');localStorage.setItem('flic-sidebar','{'recolhida' if menu == 'recolhida' else 'aberta'}')}}catch(e){{}}")
            pg = ctx.new_page()
            if perfil:
                email, senha, empresa = USUARIOS[perfil]
                pg.goto(BASE + "/login")
                pg.fill("#email", email)
                pg.fill("#senha", senha)
                pg.click("button[type=submit]")
                pg.wait_for_load_state("networkidle")
                if empresa:
                    pg.request.post(BASE + "/cliente/selecionar", form={"cliente_id": str(empresa)},
                                    headers={"Origin": BASE, "Referer": BASE + "/painel"})
                else:
                    pg.goto(BASE + "/painel")
            contextos[chave] = pg
            return pg

        for nome, perfil, caminho, acao in PRINTS:
            tema = "escuro" if acao == "escuro" else "claro"
            menu = "recolhida" if acao == "recolhido" else "aberta"
            pg = pagina(perfil, tema, menu)
            if perfil and USUARIOS[perfil][2] and caminho != "/painel":
                # abrir o Painel geral limpa a empresa ativa: seleciona de novo antes de cada tela
                pg.request.post(BASE + "/cliente/selecionar", form={"cliente_id": str(USUARIOS[perfil][2])},
                                headers={"Origin": BASE, "Referer": BASE + "/painel"})
            pg.goto(BASE + caminho)
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(900)
            if acao and acao.startswith("rolar:"):
                pg.evaluate("y => window.scrollTo(0, y)", int(acao.split(":", 1)[1]))
                pg.wait_for_timeout(400)
            if acao == "conciliar_varios":
                # página grande: clica e marca pelo próprio navegador, sem varrer o DOM pelo Playwright
                pg.evaluate("""() => {
                    const btn = [...document.querySelectorAll('button[onclick^="abrirAgrupar"]')]
                        .find(b => b.offsetParent !== null && b.dataset.lista === 'banco-recebimento')
                        || [...document.querySelectorAll('button[onclick^="abrirAgrupar"]')].find(b => b.offsetParent !== null);
                    btn.scrollIntoView({block: 'center'}); btn.click();
                    const caixas = [...document.querySelectorAll('#form-agrupar [data-lista]:not(.hidden) input[type=checkbox]')];
                    caixas.slice(0, 2).forEach(c => { c.checked = true; });
                    caixas[0] && caixas[0].dispatchEvent(new Event('change', {bubbles: true}));
                }""")
                pg.wait_for_timeout(500)
            salvar(pg.screenshot(), nome)
            print("ok", nome)
        nav.close()


if __name__ == "__main__":
    main()
