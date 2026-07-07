"""Audita conexao, schema, FKs, ORM/criptografia e telas GET principais."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sqlalchemy import inspect, text

from app.auth import criar_token
from app.database import Base, SessionLocal, engine
from app.models import ClienteBPO, PerfilUsuario, Usuario  # registra todos os mappers


erros: list[str] = []
insp = inspect(engine)

with engine.connect() as conn:
    assert conn.execute(text("SELECT 1")).scalar_one() == 1
    tabelas_banco = set(insp.get_table_names())
    tabelas_modelo = set(Base.metadata.tables)
    ausentes = sorted(tabelas_modelo - tabelas_banco)
    if ausentes:
        erros.append(f"tabelas ausentes: {ausentes}")

    fks_verificadas = 0
    for tabela in sorted(tabelas_modelo & tabelas_banco):
        for fk in insp.get_foreign_keys(tabela):
            locais = fk.get("constrained_columns") or []
            remotas = fk.get("referred_columns") or []
            tabela_remota = fk.get("referred_table")
            if len(locais) != 1 or len(remotas) != 1 or not tabela_remota:
                continue
            local, remota = locais[0], remotas[0]
            quantidade = conn.execute(text(
                f'SELECT count(*) FROM "{tabela}" origem '
                f'LEFT JOIN "{tabela_remota}" destino '
                f'ON origem."{local}" = destino."{remota}" '
                f'WHERE origem."{local}" IS NOT NULL AND destino."{remota}" IS NULL'
            )).scalar_one()
            fks_verificadas += 1
            if quantidade:
                erros.append(f"FK orfa {tabela}.{local}: {quantidade}")

with SessionLocal() as db:
    modelos_lidos = 0
    relacionamentos_lidos = 0
    for mapper in Base.registry.mappers:
        modelo = mapper.class_
        registro = db.query(modelo).first()
        modelos_lidos += 1
        if registro is None:
            continue
        try:
            for coluna in mapper.columns:
                getattr(registro, coluna.key)
            for relacao in mapper.relationships:
                getattr(registro, relacao.key)
                relacionamentos_lidos += 1
        except Exception as exc:
            erros.append(f"ORM {modelo.__name__}: {type(exc).__name__}: {exc}")

    usuario = db.query(Usuario).filter(
        Usuario.perfil == PerfilUsuario.coordenador,
        Usuario.ativo == True,
    ).first() or db.query(Usuario).filter(Usuario.ativo == True).first()
    cliente = db.query(ClienteBPO).filter(ClienteBPO.ativo == True).first()
    assert usuario is not None and cliente is not None
    token = criar_token({"sub": str(usuario.id)})
    cliente_id = cliente.id

rotas = (
    "/", "/lancamentos", "/conciliacao", "/conciliacao/lancamentos",
    "/conciliacao/banco", "/contas-pagar",
    "/contas-pagar/conciliacao-cartao", "/contas-pagar/conciliacao-banco",
    "/fechamento", "/fechamento/mensal", "/rotinas",
    "/gestao/receitas", "/gestao/despesas", "/gestao/orcamento",
    "/gestao/dre", "/gestao/dre/apresentacao", "/admin/equipe",
    "/admin/clientes", "/admin/funcionarios", "/admin/anotacoes-clientes",
    "/admin/taxas-cartao", "/admin/centros-custo", "/logs",
)

cookies = {"access_token": token, "cliente_ativo": str(cliente_id)}
with httpx.Client(base_url="http://127.0.0.1:8000", cookies=cookies, timeout=30) as client:
    for rota in rotas:
        resposta = client.get(rota, params={"cliente_id": cliente_id}, follow_redirects=False)
        if resposta.status_code not in (200, 302, 303):
            erros.append(f"GET {rota}: HTTP {resposta.status_code}")

assert not erros, "\n".join(erros)
print(
    f"db=ok; tabelas={len(tabelas_modelo)}; fks={fks_verificadas}; "
    f"modelos={modelos_lidos}; relacionamentos={relacionamentos_lidos}; "
    f"rotas_get={len(rotas)}; erros=0"
)
