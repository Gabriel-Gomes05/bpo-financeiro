"""Bootstrap HTTP da aplicação FLIC."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.auth import AuthMiddleware
from app.config import ALLOWED_ORIGINS, APP_ENV, APP_NAME, APP_VERSION, PORT
from app.database import engine, schema_esta_atualizado
from app.jinja import templates
from app.logging_config import RequestLoggingMiddleware, configure_logging
from app.redis_client import redis_async
from app.routers import (
    admin,
    auth,
    cliente_ativo,
    conciliacao,
    conciliacao_banco,
    contas_pagar,
    contas_pagar_conciliacao,
    dashboard,
    fechamento,
    gestao,
    lancamentos,
    logs,
    importacoes,
    plano_contas,
    procedimentos,
    rotinas,
)
from app.security import MaxBodySizeMiddleware, SecurityMiddleware

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "application_started",
        extra={"port": PORT},
    )
    yield
    await redis_async().aclose()
    engine.dispose()
    logger.info("application_stopped")


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(AuthMiddleware)
app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def manter_empresa_selecionada(request: Request, call_next):
    path = request.url.path
    operacional = path == "/" or any(
        path == prefix or path.startswith(prefix + "/")
        for prefix in ("/conciliacao", "/lancamentos", "/contas-pagar", "/fechamento",
                       "/rotinas", "/gestao", "/admin/taxas-cartao")
    )
    if operacional:
        empresa = request.cookies.get("cliente_ativo", "")
        if not empresa.isdigit():
            return RedirectResponse("/painel", status_code=303)
        if request.method == "GET" and request.query_params.get("cliente_id") != empresa:
            return RedirectResponse(str(request.url.include_query_params(cliente_id=empresa)), status_code=303)
    return await call_next(request)

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


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
async def ready():
    checks = {"database": "ok", "redis": "ok"}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            if not schema_esta_atualizado(connection):
                checks["database"] = "schema_outdated"
    except SQLAlchemyError:
        checks["database"] = "error"
    try:
        await redis_async().ping()
    except RedisError:
        checks["redis"] = "error"
    status_code = 200 if all(value == "ok" for value in checks.values()) else 503
    return JSONResponse(
        {"status": "ok" if status_code == 200 else "degraded", "checks": checks},
        status_code=status_code,
    )


@app.get("/version", include_in_schema=False)
async def version():
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "environment": APP_ENV,
    }


def _wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "").lower()


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, _: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    if _wants_json(request):
        return JSONResponse(
            {
                "success": False,
                "message": "Dados da requisição inválidos.",
                "request_id": request_id,
            },
            status_code=422,
        )
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "status_code": 422,
            "message": "Confira os dados informados e tente novamente.",
            "request_id": request_id,
        },
        status_code=422,
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "unhandled_request_error",
        exc_info=exc,
        extra={"request_id": request_id, "path": request.url.path},
    )
    if _wants_json(request):
        return JSONResponse(
            {
                "success": False,
                "message": "Não foi possível concluir a solicitação.",
                "request_id": request_id,
            },
            status_code=500,
        )
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "status_code": 500,
            "message": "Não foi possível concluir a solicitação.",
            "request_id": request_id,
        },
        status_code=500,
    )
