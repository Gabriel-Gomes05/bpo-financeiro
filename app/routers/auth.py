import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.auth import (
    criar_token,
    decodificar_token,
    get_token_da_requisicao,
    get_usuario_atual,
    normalizar_email,
    revogar_token,
    verificar_senha_constante,
)
from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    LOGIN_RATE_LIMIT_ACCOUNT,
    LOGIN_RATE_LIMIT_IP,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS,
)
from app.database import get_db
from app.jinja import templates
from app.models import Usuario
from app.rate_limit import clear, consume, inspect_limit, opaque_key
from app.security import client_ip, secure_cookie_for
from app.services.log_service import registrar as _log

router = APIRouter()
logger = logging.getLogger(__name__)
GENERIC_LOGIN_ERROR = "Não foi possível entrar com as credenciais informadas."


@router.get("/login", response_class=HTMLResponse)
async def pagina_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def fazer_login(
    request: Request,
    email: str = Form(..., max_length=320),
    senha: str = Form(..., max_length=256),
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    email_normalizado = normalizar_email(email)
    account_hash = opaque_key(email_normalizado)
    account_key = f"rate:login:account:{account_hash}"
    ip_key = f"rate:login:ip:{ip}"

    try:
        account_allowed, account_retry = await inspect_limit(
            account_key, LOGIN_RATE_LIMIT_ACCOUNT
        )
        ip_allowed, ip_retry = await inspect_limit(ip_key, LOGIN_RATE_LIMIT_IP)
    except RedisError:
        logger.exception("login_rate_limit_unavailable")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": "Autenticação temporariamente indisponível."},
            status_code=503,
        )

    if not account_allowed or not ip_allowed:
        retry_after = max(account_retry if not account_allowed else 0, ip_retry if not ip_allowed else 0)
        _log(db, "Login bloqueado", "auth", detalhes="Limite de tentativas excedido", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": GENERIC_LOGIN_ERROR},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    usuario = db.query(Usuario).filter(
        Usuario.email == email_normalizado,
        Usuario.ativo.is_(True),
        Usuario.deleted_at.is_(None),
    ).first()
    senha_valida = verificar_senha_constante(
        senha,
        usuario.senha_hash if usuario else None,
    )
    if not usuario or not senha_valida:
        try:
            await consume(
                account_key,
                LOGIN_RATE_LIMIT_ACCOUNT,
                LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            )
            await consume(
                ip_key,
                LOGIN_RATE_LIMIT_IP,
                LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            )
        except RedisError:
            logger.exception("login_rate_limit_record_failed")
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "erro": "Autenticação temporariamente indisponível."},
                status_code=503,
            )
        _log(db, "Login falhou", "auth", detalhes="Credenciais inválidas", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": GENERIC_LOGIN_ERROR},
            status_code=400,
        )

    await clear(account_key)
    token = criar_token({"sub": str(usuario.id)}, auth_version=usuario.auth_version)
    _log(
        db,
        "Login realizado",
        "auth",
        usuario_id=usuario.id,
        usuario_nome=usuario.nome,
        ip=ip,
    )
    response = RedirectResponse(url="/inicio", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=secure_cookie_for(request),
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@router.get("/inicio", response_class=HTMLResponse)
async def pagina_inicio(
    request: Request,
    usuario: Usuario = Depends(get_usuario_atual),
):
    return templates.TemplateResponse(
        "inicio.html", {"request": request, "usuario": usuario},
    )


@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    token = get_token_da_requisicao(request)
    payload = decodificar_token(token) if token else None
    if payload:
        await revogar_token(payload)
    _log(
        db,
        "Logout",
        "auth",
        usuario_id=usuario.id,
        usuario_nome=usuario.nome,
        ip=client_ip(request),
    )
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="strict",
        secure=secure_cookie_for(request),
        path="/",
    )
    return response
