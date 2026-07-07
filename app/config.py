"""
Configurações da aplicação lidas do arquivo .env.
Todos os módulos importam daqui — nunca leem os.getenv diretamente.
"""
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# --- Banco de dados ---
DATABASE_URL: str = os.environ["DATABASE_URL"]
APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()
DB_SSL_MODE: str = os.getenv("DB_SSL_MODE", "prefer").strip().lower()
DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "5"))
DB_POOL_TIMEOUT_SECONDS: int = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "10"))
DB_STATEMENT_TIMEOUT_MS: int = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "30000"))
DB_IDLE_TRANSACTION_TIMEOUT_MS: int = int(os.getenv("DB_IDLE_TRANSACTION_TIMEOUT_MS", "30000"))

# --- JWT ---
SECRET_KEY: str = os.environ["SECRET_KEY"]
FIELD_ENCRYPTION_KEY: str = os.environ.get("FIELD_ENCRYPTION_KEY", "").strip()
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# --- Segurança / CORS ---
HTTPS_ONLY: bool = os.getenv("HTTPS_ONLY", "false").lower() == "true"
ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8888").split(",")
    if o.strip()
]

# --- Upload de arquivos ---
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")

# --- E-mail (SMTP) ---
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASS: str = os.getenv("SMTP_PASS", "")
EMAIL_FROM: str = os.getenv("EMAIL_FROM", "FLIC <noreply@bpo.com>")


def _validar_configuracao_sensivel() -> None:
    """Interrompe o startup quando segredos ou controles críticos são inseguros."""
    exemplos = {
        "GERE-COM-openssl-rand-hex-32",
        "troque-isso-em-producao-use-uma-chave-longa-e-aleatoria",
        "change-me",
        "changeme",
    }
    if SECRET_KEY in exemplos or len(SECRET_KEY) < 32:
        raise RuntimeError(
            "SECRET_KEY fraca ou padrao. Gere uma chave com: openssl rand -hex 32"
        )
    if not FIELD_ENCRYPTION_KEY:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY ausente. Execute: python scripts/setup_encryption_key.py"
        )
    try:
        import base64
        chave_campos = base64.urlsafe_b64decode(FIELD_ENCRYPTION_KEY.encode("ascii"))
    except Exception as exc:
        raise RuntimeError("FIELD_ENCRYPTION_KEY invalida.") from exc
    if len(chave_campos) != 64:
        raise RuntimeError("FIELD_ENCRYPTION_KEY deve representar 64 bytes aleatorios.")
    if FIELD_ENCRYPTION_KEY == SECRET_KEY:
        raise RuntimeError("FIELD_ENCRYPTION_KEY deve ser diferente da SECRET_KEY.")
    if "*" in ALLOWED_ORIGINS:
        raise RuntimeError("ALLOWED_ORIGINS nao deve usar '*' em app com cookies.")
    if DB_SSL_MODE not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
        raise RuntimeError("DB_SSL_MODE invalido.")
    if DB_POOL_SIZE < 1 or DB_MAX_OVERFLOW < 0:
        raise RuntimeError("Configuracao de pool do banco invalida.")
    if DB_STATEMENT_TIMEOUT_MS < 1000 or DB_IDLE_TRANSACTION_TIMEOUT_MS < 1000:
        raise RuntimeError("Timeouts do banco devem ser de pelo menos 1000 ms.")

    if APP_ENV == "production":
        banco = urlparse(DATABASE_URL)
        senha = banco.password or ""
        senhas_fracas = {"bpo123", "password", "postgres", "admin", "123456", "changeme"}
        if len(senha) < 16 or senha.lower() in senhas_fracas:
            raise RuntimeError("Senha do banco fraca em producao; use pelo menos 16 caracteres aleatorios.")
        if DB_SSL_MODE not in {"require", "verify-ca", "verify-full"}:
            raise RuntimeError("Producao exige DB_SSL_MODE=require, verify-ca ou verify-full.")
        if not HTTPS_ONLY:
            raise RuntimeError("Producao exige HTTPS_ONLY=true.")


_validar_configuracao_sensivel()
