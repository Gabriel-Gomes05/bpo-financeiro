from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from time import time
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, SECRET_KEY
from app.database import get_db
from app.models import Usuario, PerfilUsuario

EXPIRE_MINUTES = ACCESS_TOKEN_EXPIRE_MINUTES
ALGORITHM = JWT_ALGORITHM
MAX_TENTATIVAS_LOGIN = 5
JANELA_TENTATIVAS_SEGUNDOS = 15 * 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_tentativas_login: dict[str, list[float]] = {}


# ---------------------------------------------------------------------------
# Funções de senha e token
# ---------------------------------------------------------------------------

def hash_senha(senha: str) -> str:
    """Gera um hash bcrypt irreversível para armazenamento da senha."""
    return pwd_context.hash(senha)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """Compara uma senha informada com o hash bcrypt persistido."""
    return pwd_context.verify(senha_plana, senha_hash)


def criar_token(data: dict) -> str:
    """Cria um JWT assinado com expiração configurada para a sessão web."""
    payload = data.copy()
    expira = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES)
    payload.update({"exp": expira})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str) -> Optional[dict]:
    """Valida assinatura e expiração do JWT, retornando `None` se inválido."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def login_bloqueado(chave: str) -> bool:
    """Informa se IP/e-mail excedeu o limite de tentativas na janela atual."""
    agora = time()
    tentativas = [
        ts for ts in _tentativas_login.get(chave, [])
        if agora - ts < JANELA_TENTATIVAS_SEGUNDOS
    ]
    _tentativas_login[chave] = tentativas
    return len(tentativas) >= MAX_TENTATIVAS_LOGIN


def registrar_tentativa_login(chave: str) -> None:
    """Registra uma falha de autenticação para controle de força bruta."""
    agora = time()
    tentativas = [
        ts for ts in _tentativas_login.get(chave, [])
        if agora - ts < JANELA_TENTATIVAS_SEGUNDOS
    ]
    tentativas.append(agora)
    _tentativas_login[chave] = tentativas


def limpar_tentativas_login(chave: str) -> None:
    """Remove falhas acumuladas após uma autenticação bem-sucedida."""
    _tentativas_login.pop(chave, None)


# ---------------------------------------------------------------------------
# Dependências FastAPI
# ---------------------------------------------------------------------------

def get_token_do_cookie(request: Request) -> Optional[str]:
    """Obtém o token JWT do cookie HttpOnly da requisição."""
    return request.cookies.get("access_token")


def get_usuario_atual(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Lê o JWT do cookie. Se inválido ou ausente, redireciona para /login.
    Use como Depends() em qualquer rota protegida.
    """
    token = get_token_do_cookie(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    payload = decodificar_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    usuario_id = payload.get("sub")
    if not usuario_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    usuario = db.query(Usuario).filter(
        Usuario.id == int(usuario_id),
        Usuario.ativo == True
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )

    return usuario


def requer_coordenador(usuario: Usuario = Depends(get_usuario_atual)) -> Usuario:
    """Autoriza somente coordenadores e responde 403 para os demais perfis."""
    """Garante que apenas coordenadores acessem a rota."""
    if usuario.perfil != PerfilUsuario.coordenador:
        raise HTTPException(status_code=403, detail="Acesso restrito ao coordenador.")
    return usuario


def tem_acesso_geral(usuario: Usuario) -> bool:
    """Informa se o perfil pode operar todos os clientes da organização."""
    return usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor)


# ---------------------------------------------------------------------------
# Middleware: redireciona para /login se cookie ausente ou inválido
# ---------------------------------------------------------------------------

class AuthMiddleware:
    """
    Middleware simples que protege todas as rotas exceto /login e /static.
    Rotas protegidas exigem cookie access_token válido.
    """

    ROTAS_PUBLICAS = {"/login", "/favicon.ico"}
    PREFIXOS_PUBLICOS = ("/static",)

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Permite rotas públicas sem autenticação
        if path in self.ROTAS_PUBLICAS or any(path.startswith(p) for p in self.PREFIXOS_PUBLICOS):
            await self.app(scope, receive, send)
            return

        # Verifica cookie
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode("utf-8")
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        token_morsel = cookie.get("access_token")
        token = token_morsel.value if token_morsel else None

        if not token or not decodificar_token(token):
            response = RedirectResponse(url="/login", status_code=303)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
