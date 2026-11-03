import asyncio
import importlib.util
import json
import logging
import re
from pathlib import Path

import pytest
from fastapi import HTTPException, Request

from app import main
from app.errors import AREAS, CATALOGO, CODIGO_POR_IMPORTACAO, ErroFlic, codigo_por_status, com_codigo, erro, public_import_error

RAIZ = Path(__file__).resolve().parents[1]
FORMATO = re.compile(r"^FLIC-([A-Z]{3})-(\d{3})$")
REFERENCIA = re.compile(r"FLIC-[A-Z]{3}-\d{3}")


def _arquivos_app():
    return [p for p in (RAIZ / "app").rglob("*") if p.suffix in {".py", ".html"} and "__pycache__" not in p.parts]


def _texto_app():
    return {p: p.read_text(encoding="utf-8") for p in _arquivos_app()}


# --- Catálogo --------------------------------------------------------------------

def test_catalogo_bem_formado():
    slugs = [d.slug for d in CATALOGO.values() if d.slug]
    assert len(slugs) == len(set(slugs))
    for codigo, d in CATALOGO.items():
        m = FORMATO.match(codigo)
        assert m and m.group(1) in AREAS, codigo
        assert d.codigo == codigo
        assert 400 <= d.status <= 599, codigo
        for campo in (d.titulo, d.mensagem, d.causa, d.solucao):
            assert campo and campo.strip() == campo, codigo


def test_todo_codigo_citado_no_sistema_existe_no_catalogo():
    citados = {(p.relative_to(RAIZ).as_posix(), c) for p, t in _texto_app().items() for c in REFERENCIA.findall(t)}
    inexistentes = sorted(f"{p}: {c}" for p, c in citados if c not in CATALOGO)
    assert not inexistentes, inexistentes


def test_todo_codigo_do_catalogo_e_usado():
    textos = _texto_app()
    tudo = "\n".join(textos.values())
    sem_uso = []
    for codigo, d in CATALOGO.items():
        if d.slug:
            usado = f"erro={d.slug}" in tudo
        else:
            usado = tudo.count(f'"{codigo}"') >= 2  # a definição + ao menos um uso
        if not usado:
            sem_uso.append(codigo)
    assert not sem_uso, f"Códigos sem uso (remova ou use): {sem_uso}"


def test_nenhum_erro_http_sem_codigo():
    """Erros novos devem usar erro("FLIC-...") em vez de HTTPException direto."""
    padrao = re.compile(r"raise HTTPException\(\s*(?:status_code=)?(?:4|5)\d\d")
    restantes = [f"{p.relative_to(RAIZ)}:{i}" for p, t in _texto_app().items() if p.suffix == ".py"
                 for i, linha in enumerate(t.splitlines(), 1) if padrao.search(linha)]
    assert not restantes, restantes


def test_toda_importacao_com_falha_generica_tem_codigo():
    operacoes = {m for t in _texto_app().values() for m in re.findall(r'public_import_error\([^,]+,\s*"([a-z_]+)"\)', t)}
    assert operacoes and operacoes <= set(CODIGO_POR_IMPORTACAO), operacoes - set(CODIGO_POR_IMPORTACAO)


def test_documento_da_biblia_atualizado():
    spec = importlib.util.spec_from_file_location("gerar", RAIZ / "scripts" / "gerar_catalogo_erros.py")
    gerar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gerar)
    atual = (RAIZ / "docs" / "CODIGOS_DE_ERRO.md").read_text(encoding="utf-8")
    assert atual == gerar.gerar(), "Rode: python scripts/gerar_catalogo_erros.py"
    for codigo in CATALOGO:
        assert f"`{codigo}`" in atual


# --- Uso ---------------------------------------------------------------------------

def test_erro_flic_e_http_exception_com_status_e_mensagem_do_catalogo():
    e = erro("FLIC-PAG-010")
    assert isinstance(e, HTTPException) and isinstance(e, ErroFlic)
    assert (e.status_code, e.detail, e.codigo) == (404, "Conta indisponível.", "FLIC-PAG-010")
    assert erro("FLIC-REC-001", "Data inválida.").detail == "Data inválida."
    assert com_codigo("FLIC-TAR-005") == "[FLIC-TAR-005] Informe um título com até 200 caracteres."


@pytest.mark.parametrize("status,codigo", [(400, "FLIC-GER-400"), (403, "FLIC-GER-403"), (404, "FLIC-GER-404"),
                                           (418, "FLIC-GER-400"), (500, "FLIC-GER-500"), (502, "FLIC-GER-500")])
def test_codigo_generico_por_status(status, codigo):
    assert codigo_por_status(status) == codigo


def test_falha_de_importacao_registra_codigo_no_log(caplog):
    logger = logging.getLogger("teste.importacao")
    try:
        raise RuntimeError("falha")
    except RuntimeError:
        with caplog.at_level(logging.ERROR):
            mensagem = public_import_error(logger, "importar_visao_contas_a_receber")
    assert mensagem.startswith("[FLIC-IMP-903] ")
    assert caplog.records[-1].error_code == "FLIC-IMP-903"


def _request(json_=False):
    headers = [(b"accept", b"application/json")] if json_ else []
    req = Request({"type": "http", "method": "GET", "scheme": "http", "server": ("testserver", 80),
                   "path": "/x", "headers": headers, "query_string": b""})
    req.state.request_id = "req-123"
    return req


def test_pagina_de_erro_mostra_codigo_solucao_e_identificador():
    resposta = asyncio.run(main.http_error_handler(_request(), erro("FLIC-PAG-010")))
    html = resposta.body.decode()
    assert resposta.status_code == 404
    assert "FLIC-PAG-010" in html and "Conta indisponível." in html
    assert CATALOGO["FLIC-PAG-010"].solucao in html
    assert "req-123" in html and 'href="/ajuda/erros#FLIC-PAG-010"' in html


def test_json_de_erro_traz_codigo():
    resposta = asyncio.run(main.http_error_handler(_request(json_=True), erro("FLIC-AUT-002")))
    corpo = json.loads(resposta.body)
    assert resposta.status_code == 403
    assert corpo == {"success": False, "code": "FLIC-AUT-002", "message": "Perfil somente leitura.",
                     "detail": "Perfil somente leitura.", "request_id": "req-123"}


def test_erro_sem_codigo_recebe_codigo_geral_em_portugues():
    resposta = asyncio.run(main.http_error_handler(_request(json_=True), HTTPException(404)))
    corpo = json.loads(resposta.body)
    assert corpo["code"] == "FLIC-GER-404"
    assert corpo["message"] == CATALOGO["FLIC-GER-404"].mensagem


def test_redirecionamento_nao_vira_erro():
    resposta = asyncio.run(main.http_error_handler(_request(), HTTPException(303, headers={"Location": "/login"})))
    assert resposta.status_code == 303 and resposta.headers["location"] == "/login"


def test_validacao_e_erro_inesperado_tem_codigo():
    validacao = asyncio.run(main.validation_error_handler(_request(json_=True), None))
    assert json.loads(validacao.body)["code"] == "FLIC-GER-422"
    inesperado = asyncio.run(main.unhandled_error_handler(_request(json_=True), RuntimeError("x")))
    assert inesperado.status_code == 500 and json.loads(inesperado.body)["code"] == "FLIC-GER-500"


def test_pagina_ajuda_lista_todos_os_codigos():
    from types import SimpleNamespace

    from app.routers import ajuda
    req = Request({"type": "http", "method": "GET", "scheme": "http", "server": ("testserver", 80),
                   "path": "/ajuda/erros", "headers": [], "query_string": b""})
    usuario = SimpleNamespace(id=1, nome="Ana", perfil="coordenador")
    html = asyncio.run(ajuda.codigos_de_erro(req, usuario)).body.decode()
    for codigo in CATALOGO:
        assert f'id="{codigo}"' in html


def test_selo_de_erro_das_telas_de_cadastro():
    from app.jinja import _codigo_erro
    assert _codigo_erro("email_duplicado") == "FLIC-CAD-007"
    assert _codigo_erro("inexistente") == "FLIC-GER-400"
    assert _codigo_erro(None) == "FLIC-GER-400"
