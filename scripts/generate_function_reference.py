"""Gera uma referência navegável de todas as funções Python mantidas no projeto."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "REFERENCIA_FUNCOES.md"
IGNORED_PARTS = {
    ".git", ".agents", ".claude", ".codex", ".tools",
    ".venv", "venv", "__pycache__", "uploads", "backups",
}

VERBS = {
    "adicionar": "adiciona",
    "alternar": "alterna",
    "aplicar": "aplica",
    "arquivar": "arquiva",
    "atualizar": "atualiza",
    "buscar": "busca",
    "calcular": "calcula",
    "carregar": "carrega",
    "conciliar": "concilia",
    "criar": "cria",
    "decodificar": "decodifica",
    "decrypt": "decifra",
    "decrypt_value": "decifra o valor persistido e valida sua integridade",
    "editar": "edita",
    "encrypt": "cifra",
    "encrypt_value": "cifra o valor antes da persistência",
    "enviar": "envia",
    "excluir": "exclui",
    "extrair": "extrai",
    "fazer": "executa",
    "fechar": "fecha",
    "filtrar": "filtra",
    "formatar": "formata",
    "gerar": "gera",
    "get": "obtém",
    "ignorar": "ignora",
    "importar": "importa",
    "limpar": "limpa",
    "listar": "lista",
    "marcar": "marca",
    "migrar": "migra",
    "montar": "monta",
    "normalizar": "normaliza",
    "obter": "obtém",
    "pagina": "renderiza a página de",
    "processar": "processa",
    "registrar": "registra",
    "requer": "valida a permissão necessária para",
    "resolver": "resolve",
    "restaurar": "restaura",
    "salvar": "salva",
    "selecionar": "seleciona",
    "tem": "informa se existe permissão ou condição para",
    "toggle": "alterna o estado de",
    "validar": "valida",
    "verificar": "verifica",
}


def python_files() -> list[Path]:
    """Retorna os arquivos Python versionáveis, ignorando ambientes e dados locais."""
    files = list(ROOT.glob("*.py"))
    for source_dir in (ROOT / "app", ROOT / "scripts", ROOT / "docs"):
        if not source_dir.exists():
            continue
        for path in source_dir.rglob("*.py"):
            files.append(path)
    clean_files = []
    for path in files:
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        clean_files.append(path)
    return sorted(set(clean_files), key=lambda item: item.relative_to(ROOT).as_posix())


def route_of(node: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str = "") -> str | None:
    """Extrai método e caminho de um decorator FastAPI, quando houver."""
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        method = decorator.func.attr.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"} or not decorator.args:
            continue
        path = decorator.args[0]
        if isinstance(path, ast.Constant) and isinstance(path.value, str):
            return f"`{method} {prefix}{path.value}`"
    return None


def router_prefix(tree: ast.Module) -> str:
    """Lê o prefixo declarado em `router = APIRouter(prefix=...)`."""
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if not isinstance(node.value.func, ast.Name) or node.value.func.id != "APIRouter":
            continue
        for keyword in node.value.keywords:
            if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value)
    return ""


def signature_of(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Reconstrói uma assinatura curta sem copiar o corpo da função."""
    arguments = ast.unparse(node.args)
    result = f"{node.name}({arguments})"
    if node.returns:
        result += f" -> {ast.unparse(node.returns)}"
    return result.replace("\n", " ")


def humanize(identifier: str) -> str:
    """Converte um identificador snake_case em texto legível."""
    return identifier.strip("_").replace("_", " ") or identifier


def inferred_description(node: ast.FunctionDef | ast.AsyncFunctionDef, route: str | None) -> str:
    """Produz uma descrição previsível quando a função ainda não possui docstring."""
    docstring = ast.get_docstring(node)
    if docstring:
        return " ".join(docstring.strip().split())
    clean_name = node.name.strip("_")
    parts = clean_name.split("_")
    first = parts[0] if parts else clean_name
    verb = VERBS.get(clean_name) or VERBS.get(first)
    subject_parts = parts[1:] if VERBS.get(first) else parts
    subject = humanize("_".join(subject_parts))
    if route:
        action = f"{verb} {subject}" if verb else f"executa o fluxo {humanize(clean_name)}"
        return f"Endpoint que {action.strip()} e devolve a resposta HTTP correspondente."
    if verb:
        return f"Função auxiliar que {verb} {subject}.".replace("  ", " ")
    return f"Função auxiliar responsável pelo fluxo “{humanize(clean_name)}”."


def functions_in(path: Path) -> tuple[ast.Module, list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]]]:
    """Lista funções e métodos com o nome qualificado da classe quando aplicável."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]] = []

    class FunctionVisitor(ast.NodeVisitor):
        """Percorre funções de módulo, métodos e funções locais aninhadas."""

        def __init__(self) -> None:
            self.parents: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.parents.append(node.name)
            self.generic_visit(node)
            self.parents.pop()

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            qualified = ".".join((*self.parents, node.name))
            found.append((node, qualified))
            self.parents.append(node.name)
            self.generic_visit(node)
            self.parents.pop()

        visit_FunctionDef = _visit_function
        visit_AsyncFunctionDef = _visit_function

    FunctionVisitor().visit(tree)
    return tree, found


def generate() -> str:
    """Monta o Markdown completo e determinístico da referência."""
    lines = [
        "# Referência de funções",
        "",
        "> Arquivo gerado por `python scripts/generate_function_reference.py`.",
        "> Não edite manualmente; melhore nomes/docstrings no código e gere novamente.",
        "",
        "Esta referência ajuda o desenvolvedor a localizar responsabilidades. Ela complementa",
        "o código e não substitui a leitura das regras de negócio e validações de acesso.",
        "",
    ]
    total = 0
    for path in python_files():
        tree, entries = functions_in(path)
        if not entries:
            continue
        relative = path.relative_to(ROOT).as_posix()
        lines.extend((f"## `{relative}`", ""))
        module_doc = ast.get_docstring(tree)
        prefix = router_prefix(tree)
        if module_doc:
            lines.extend((" ".join(module_doc.split()), ""))
        for node, qualified_name in entries:
            total += 1
            route = route_of(node, prefix)
            location = f"[{qualified_name}](../{relative}#L{node.lineno})"
            lines.append(f"### `{signature_of(node)}`")
            lines.append("")
            lines.append(f"- Local: {location}")
            if route:
                lines.append(f"- Rota: {route}")
            lines.append(f"- Responsabilidade: {inferred_description(node, route)}")
            lines.append("")
    lines.extend(("---", "", f"Total documentado: **{total} funções e métodos**.", ""))
    return "\n".join(lines)


def main() -> int:
    """Gera o arquivo ou valida se a versão commitada está atualizada."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="não grava; falha se estiver desatualizado")
    args = parser.parse_args()
    content = generate()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            print("REFERENCIA_FUNCOES.md está desatualizada. Execute o gerador.")
            return 1
        print("Referência de funções atualizada.")
        return 0
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Referência gerada em {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
