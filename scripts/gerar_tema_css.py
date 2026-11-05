"""Gera static/css/flic-tema.css: adapta ao modo escuro as classes Tailwind usadas nos templates.

Os templates usam classes utilitárias (bg-white, text-slate-700, bg-amber-50...) e algumas cores fixas
em style="". Em vez de reescrever cada tela, este script lê todos os templates, encontra as classes
de cor realmente usadas e gera as regras equivalentes para `html.dark`.

Rode sempre que criar telas novas:  python scripts/gerar_tema_css.py
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATES = RAIZ / "app" / "templates"
JS = RAIZ / "static" / "js"
SAIDA = RAIZ / "static" / "css" / "flic-tema.css"

PALETA = {
    "red": {100: "#fee2e2", 200: "#fecaca", 300: "#fca5a5", 400: "#f87171", 500: "#ef4444"},
    "rose": {100: "#ffe4e6", 200: "#fecdd3", 300: "#fda4af", 400: "#fb7185", 500: "#f43f5e"},
    "orange": {100: "#ffedd5", 200: "#fed7aa", 300: "#fdba74", 400: "#fb923c", 500: "#f97316"},
    "amber": {100: "#fef3c7", 200: "#fde68a", 300: "#fcd34d", 400: "#fbbf24", 500: "#f59e0b"},
    "yellow": {100: "#fef9c3", 200: "#fef08a", 300: "#fde047", 400: "#facc15", 500: "#eab308"},
    "lime": {100: "#ecfccb", 200: "#d9f99d", 300: "#bef264", 400: "#a3e635", 500: "#84cc16"},
    "green": {100: "#dcfce7", 200: "#bbf7d0", 300: "#86efac", 400: "#4ade80", 500: "#22c55e"},
    "emerald": {100: "#d1fae5", 200: "#a7f3d0", 300: "#6ee7b7", 400: "#34d399", 500: "#10b981"},
    "teal": {100: "#ccfbf1", 200: "#99f6e4", 300: "#5eead4", 400: "#2dd4bf", 500: "#14b8a6"},
    "cyan": {100: "#cffafe", 200: "#a5f3fc", 300: "#67e8f9", 400: "#22d3ee", 500: "#06b6d4"},
    "sky": {100: "#e0f2fe", 200: "#bae6fd", 300: "#7dd3fc", 400: "#38bdf8", 500: "#0ea5e9"},
    "blue": {100: "#dbeafe", 200: "#bfdbfe", 300: "#93c5fd", 400: "#60a5fa", 500: "#3b82f6"},
    "indigo": {100: "#e0e7ff", 200: "#c7d2fe", 300: "#a5b4fc", 400: "#818cf8", 500: "#6366f1"},
    "violet": {100: "#ede9fe", 200: "#ddd6fe", 300: "#c4b5fd", 400: "#a78bfa", 500: "#8b5cf6"},
    "purple": {100: "#f3e8ff", 200: "#e9d5ff", 300: "#d8b4fe", 400: "#c084fc", 500: "#a855f7"},
    "fuchsia": {100: "#fae8ff", 200: "#f5d0fe", 300: "#f0abfc", 400: "#e879f9", 500: "#d946ef"},
    "pink": {100: "#fce7f3", 200: "#fbcfe8", 300: "#f9a8d4", 400: "#f472b6", 500: "#ec4899"},
}
NEUTROS = {"gray", "slate", "zinc", "neutral", "stone"}
VARIANTES = {"": "", "hover": ":hover", "focus": ":focus", "group-hover": "", "active": ":active"}

TOKEN = re.compile(
    r"(?<![\w:-])((?:hover|focus|group-hover|active):)?(bg|text|border|divide|ring)-"
    r"(white|black|(?:" + "|".join(sorted(NEUTROS | set(PALETA))) + r")-(?:50|100|200|300|400|500|600|700|800|900))"
    r"(/\d+)?(?![\w-])"
)


def esc(classe: str) -> str:
    return re.sub(r"([:/\[\]#.%])", r"\\\1", classe)


def rgba(hexa: str, alfa: float) -> str:
    hexa = hexa.lstrip("#")
    r, g, b = (int(hexa[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alfa:.2f})"


def valor_dark(prop: str, cor: str, opacidade: float | None) -> str | None:
    """Valor da propriedade no modo escuro (None = mantém o original)."""
    if cor == "black":
        return None
    if cor == "white":
        if prop == "bg":
            return "var(--surface)" if opacidade is None else f"rgba(23,27,36,{opacidade:.2f})"
        return None  # text-white / border-white continuam brancos
    familia, tom = cor.rsplit("-", 1)
    tom = int(tom)
    if familia in NEUTROS:
        if prop == "bg":
            base = {50: "var(--surface-2)", 100: "var(--surface-3)", 200: "var(--surface-4)", 300: "var(--border-strong)"}.get(tom)
            if base and opacidade is not None:
                return {50: "rgba(255,255,255,.03)", 100: "rgba(255,255,255,.05)", 200: "rgba(255,255,255,.08)", 300: "rgba(255,255,255,.12)"}[tom]
            return base
        if prop == "text":
            if tom >= 800:
                return "var(--text)"
            if tom >= 600:
                return "var(--text-2)"
            if tom >= 400:
                return "var(--text-3)"
            return "var(--text-4)"
        if prop in ("border", "divide", "ring"):
            return "var(--border-strong)" if tom >= 300 else "var(--border)"
    pal = PALETA[familia]
    if prop == "bg":
        if tom <= 200:
            alfa = {50: .09, 100: .15, 200: .22}[tom]
            if opacidade is not None:
                alfa = alfa * max(opacidade, .3) * 1.6
            return rgba(pal[500], min(alfa, .3))
        return None
    if prop == "text":
        if tom >= 600:
            return pal[{600: 400, 700: 300, 800: 200, 900: 200}[tom]]
        return None
    if prop in ("border", "divide", "ring"):
        if tom <= 300:
            return rgba(pal[500], {50: .14, 100: .2, 200: .28, 300: .4}[tom])
        return None
    return None


def regra(variante: str, prop: str, cor: str, opacidade: str | None) -> str | None:
    op = int(opacidade[1:]) / 100 if opacidade else None
    valor = valor_dark(prop, cor, op)
    if not valor:
        return None
    classe = f"{variante or ''}{prop}-{cor}{opacidade or ''}"
    sufixo = VARIANTES[(variante or "").rstrip(":")]
    seletor = f"html.dark .{esc(classe)}{sufixo}"
    if variante == "group-hover:":
        seletor = f"html.dark .group:hover .{esc(classe)}"
    if prop == "bg":
        return f"{seletor}{{background-color:{valor}}}"
    if prop == "text":
        return f"{seletor}{{color:{valor}}}"
    if prop == "border":
        return f"{seletor}{{border-color:{valor}}}"
    if prop == "ring":
        return f"{seletor}{{--tw-ring-color:{valor}}}"
    return f"{seletor}>:not([hidden])~:not([hidden]){{border-color:{valor}}}"


# Cores fixas em style="" → equivalente escuro.
INLINE_FUNDO = {
    "#fff": "var(--surface)", "#ffffff": "var(--surface)", "white": "var(--surface)",
    "#f8fafc": "var(--surface-2)", "#fafbfc": "var(--surface-2)", "#f4f4f4": "var(--bg)", "#f6f9fc": "var(--surface-2)",
    "#eef4fb": "rgba(79,143,214,.12)", "#eff6ff": "rgba(59,130,246,.10)", "#eef2ff": "rgba(99,102,241,.10)",
    "#e0e7ff": "rgba(99,102,241,.16)", "#fffbeb": "rgba(245,158,11,.10)", "#f0fdf4": "rgba(34,197,94,.10)",
    "#dcfce7": "rgba(34,197,94,.16)", "#f0f7f0": "rgba(34,197,94,.10)", "#fef2f2": "rgba(239,68,68,.10)",
    "#fff7f7": "rgba(239,68,68,.08)", "#fee2e2": "rgba(239,68,68,.16)", "#e2e8f0": "var(--surface-4)",
}
INLINE_TEXTO = {
    "#222049": "var(--text)", "#1e293b": "var(--text)", "#374151": "var(--text-2)", "#475569": "var(--text-2)",
    "#64748b": "var(--text-3)", "#94a3b8": "var(--text-3)", "#b91c1c": "#fca5a5", "#dc2626": "#f87171",
    "#15803d": "#86efac", "#16a34a": "#4ade80", "#2d6a2d": "#86efac",
}
INLINE_BORDA = {
    "#e2e8f0": "var(--border)", "#cbd5e1": "var(--border-strong)", "#dbe5ef": "var(--border)", "#dbe7f5": "var(--border)",
    "#bfd4ee": "rgba(79,143,214,.35)", "#fecaca": "rgba(239,68,68,.3)", "#fca5a5": "rgba(239,68,68,.35)",
    "#bbf7d0": "rgba(34,197,94,.3)", "#b6d9b6": "rgba(34,197,94,.3)",
}


def regras_inline() -> list[str]:
    linhas = []
    for hexa, valor in INLINE_FUNDO.items():
        for prop in ("background", "background-color"):
            for sep in (":", ": "):
                linhas.append(f'html.dark [style*="{prop}{sep}{hexa};"],html.dark [style$="{prop}{sep}{hexa}"]{{background:{valor}!important}}')
    for hexa, valor in INLINE_TEXTO.items():
        for sep in (":", ": "):
            linhas.append(f'html.dark [style^="color{sep}{hexa}"],html.dark [style*=";color{sep}{hexa}"],html.dark [style*="; color{sep}{hexa}"]{{color:{valor}!important}}')
    for hexa, valor in INLINE_BORDA.items():
        linhas.append(f'html.dark [style*="border-color:{hexa}"],html.dark [style*="border-color: {hexa}"],html.dark [style*="solid {hexa}"]{{border-color:{valor}!important}}')
    return linhas


def main() -> None:
    fontes = list(TEMPLATES.rglob("*.html")) + list(JS.rglob("*.js")) + [RAIZ / "static" / "app.js"]
    encontrados = set()
    for arquivo in fontes:
        if arquivo.exists():
            for m in TOKEN.finditer(arquivo.read_text(encoding="utf-8", errors="ignore")):
                encontrados.add(m.groups())
    regras = sorted({r for t in encontrados if (r := regra(*t))})
    cabecalho = "/* Gerado por scripts/gerar_tema_css.py — não editar à mão. */\n"
    SAIDA.write_text(cabecalho + "\n".join(regras + regras_inline()) + "\n", encoding="utf-8")
    print(f"{len(regras)} regras de classe + inline -> {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
