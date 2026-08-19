from datetime import date

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.auth import AuthMiddleware
from app.database import criar_tabelas, migrar_schema
from app.jinja import templates  # garante que T e now ficam registrados no startup
from app.routers import auth, dashboard, lancamentos, conciliacao, conciliacao_banco, contas_pagar, contas_pagar_conciliacao, fechamento, rotinas, admin, gestao, cliente_ativo, logs, plano_contas, procedimentos, importacoes
from app.config import ALLOWED_ORIGINS
from app.security import SecurityHeadersMiddleware

app = FastAPI(title="FLIC", docs_url=None, redoc_url=None)

# 1. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,          # necessário para cookies JWT
    allow_methods=["GET", "POST"],   # apenas o que o app usa
    allow_headers=["Content-Type"],
)

# 2. Autenticacao via cookie JWT
app.add_middleware(AuthMiddleware)

# 3. Headers e validacao de origem como camada externa
app.add_middleware(SecurityHeadersMiddleware)

# Arquivos estáticos (JS, imagens, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Registra todos os routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(lancamentos.router)
app.include_router(conciliacao.router)
app.include_router(conciliacao_banco.router)
app.include_router(contas_pagar.router)
app.include_router(contas_pagar_conciliacao.router)
app.include_router(fechamento.router)
app.include_router(rotinas.router)
app.include_router(gestao.router)
app.include_router(cliente_ativo.router)
app.include_router(admin.router)
app.include_router(logs.router)
app.include_router(plano_contas.router)
app.include_router(procedimentos.router)
app.include_router(importacoes.router)

@app.on_event("startup")
async def startup():
    """Cria tabelas e aplica migrações."""
    criar_tabelas()
    migrar_schema()
    print("FLIC iniciado. Acesse: http://localhost:8888")
