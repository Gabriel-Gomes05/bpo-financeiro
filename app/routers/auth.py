from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy.orm import Session

from app.auth import (
    criar_token,
    get_usuario_atual,
    limpar_tentativas_login,
    login_bloqueado,
    registrar_tentativa_login,
    verificar_senha,
)
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, HTTPS_ONLY
from app.database import get_db
from app.models import Usuario
from app.services.log_service import registrar as _log

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def pagina_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def fazer_login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else "desconhecido"
    chave_tentativa = f"{ip}:{email.lower().strip()}"
    if login_bloqueado(chave_tentativa):
        _log(db, "Login bloqueado", "auth", detalhes=f"e-mail: {email}", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": "Muitas tentativas. Aguarde alguns minutos."},
            status_code=429,
        )

    usuario = db.query(Usuario).filter(
        Usuario.email == email,
        Usuario.ativo == True
    ).first()

    if not usuario or not verificar_senha(senha, usuario.senha_hash):
        registrar_tentativa_login(chave_tentativa)
        _log(db, "Login falhou", "auth", detalhes=f"e-mail: {email}", ip=ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "erro": "E-mail ou senha incorretos."},
            status_code=400,
        )

    limpar_tentativas_login(chave_tentativa)
    token = criar_token({"sub": str(usuario.id)})
    _log(db, "Login realizado", "auth", usuario_id=usuario.id, usuario_nome=usuario.nome, ip=ip)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,        # inacessível ao JavaScript
        samesite="strict",    # bloqueia envio cross-site (proteção CSRF)
        secure=HTTPS_ONLY,    # somente via HTTPS em produção
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    _log(db, "Logout", "auth", usuario_id=usuario.id, usuario_nome=usuario.nome, ip=request.client.host if request.client else None)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="strict",
        secure=HTTPS_ONLY,
        path="/",
    )
    return response
