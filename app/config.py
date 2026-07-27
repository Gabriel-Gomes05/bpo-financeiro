"""Configuração centralizada e validada da aplicação."""
from __future__ import annotations

import base64
import ipaddress
import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Variável obrigatória ausente: {name}.")
    return value


def _int(name: str, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} deve ser um número inteiro.") from exc
    if value < minimum or (maximum is not None and value > maximum):
        raise RuntimeError(f"{name} fora do intervalo permitido.")
    return value


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, str(default).lower()).strip().lower()
    if raw not in {"true", "false"}:
        raise RuntimeError(f"{name} deve ser true ou false.")
    return raw == "true"


def _csv(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


# Aplicação
APP_NAME = os.getenv("APP_NAME", "FLIC").strip() or "FLIC"
APP_VERSION = os.getenv("APP_VERSION", "1.0.0").strip() or "1.0.0"
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
APP_URL = _required("APP_URL").rstrip("/")
HOST = os.getenv("HOST", "0.0.0.0").strip()
PORT = _int("PORT", 8000, minimum=1, maximum=65535)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

# Banco de dados
DATABASE_URL = _required("DATABASE_URL")
MIGRATION_DATABASE_URL = os.getenv("MIGRATION_DATABASE_URL", "").strip()
DATABASE_RUNTIME_ROLE = os.getenv("DATABASE_RUNTIME_ROLE", "flic_app").strip()
DB_SSL_MODE = os.getenv("DB_SSL_MODE", "prefer").strip().lower()
DB_ALLOW_INSECURE_PRIVATE = _bool("DB_ALLOW_INSECURE_PRIVATE")
DB_POOL_SIZE = _int("DB_POOL_SIZE", 5, minimum=1, maximum=100)
DB_MAX_OVERFLOW = _int("DB_MAX_OVERFLOW", 5, minimum=0, maximum=100)
DB_POOL_TIMEOUT_SECONDS = _int("DB_POOL_TIMEOUT_SECONDS", 10, minimum=1, maximum=120)
DB_STATEMENT_TIMEOUT_MS = _int("DB_STATEMENT_TIMEOUT_MS", 30000, minimum=1000)
DB_IDLE_TRANSACTION_TIMEOUT_MS = _int(
    "DB_IDLE_TRANSACTION_TIMEOUT_MS", 30000, minimum=1000
)

# Sessão e autenticação
SECRET_KEY = _required("SECRET_KEY")
FIELD_ENCRYPTION_KEY = _required("FIELD_ENCRYPTION_KEY")
BACKUP_ENCRYPTION_KEY = os.getenv("BACKUP_ENCRYPTION_KEY", "").strip()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
JWT_ISSUER = os.getenv("JWT_ISSUER", "flic").strip()
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "flic-web").strip()
ACCESS_TOKEN_EXPIRE_MINUTES = _int(
    "ACCESS_TOKEN_EXPIRE_MINUTES", 480, minimum=5, maximum=1440
)

# Redis, revogação e rate limiting
REDIS_URL = _required("REDIS_URL")
LOGIN_RATE_LIMIT_ACCOUNT = _int("LOGIN_RATE_LIMIT_ACCOUNT", 5, minimum=1, maximum=100)
LOGIN_RATE_LIMIT_IP = _int("LOGIN_RATE_LIMIT_IP", 20, minimum=1, maximum=1000)
LOGIN_RATE_LIMIT_WINDOW_SECONDS = _int(
    "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 900, minimum=60, maximum=86400
)
GLOBAL_RATE_LIMIT_REQUESTS = _int(
    "GLOBAL_RATE_LIMIT_REQUESTS", 300, minimum=10, maximum=100000
)
GLOBAL_RATE_LIMIT_WINDOW_SECONDS = _int(
    "GLOBAL_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1, maximum=3600
)

# HTTP e proxy
HTTPS_ONLY = APP_ENV == "production"
EXTRA_ALLOWED_ORIGINS = _csv("EXTRA_ALLOWED_ORIGINS")
ALLOWED_ORIGINS = list(dict.fromkeys([APP_URL, *EXTRA_ALLOWED_ORIGINS]))
TRUSTED_PROXY_CIDRS = _csv("TRUSTED_PROXY_CIDRS")
MAX_REQUEST_BODY_BYTES = _int(
    "MAX_REQUEST_BODY_BYTES", 12 * 1024 * 1024, minimum=1024, maximum=100 * 1024 * 1024
)
UPLOAD_DIR = _required("UPLOAD_DIR")

# SMTP
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = _int("SMTP_PORT", 587, minimum=1, maximum=65535)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "").strip()
EMAIL_FROM = os.getenv("EMAIL_FROM", "FLIC <noreply@example.invalid>").strip()


def _decode_key(name: str, encoded: str) -> bytes:
    try:
        value = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception as exc:
        raise RuntimeError(f"{name} não é Base64 válida.") from exc
    if len(value) != 64:
        raise RuntimeError(f"{name} deve representar exatamente 64 bytes aleatórios.")
    return value


def _validar_origens() -> None:
    if not ALLOWED_ORIGINS:
        raise RuntimeError("ALLOWED_ORIGINS deve conter pelo menos uma origem explícita.")
    for origin in ALLOWED_ORIGINS:
        parsed = urlparse(origin)
        if (
            origin == "*"
            or parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(f"Origem CORS inválida: {origin}.")
        if APP_ENV == "production" and parsed.scheme != "https":
            raise RuntimeError("Produção exige somente origens CORS HTTPS.")


def _validar_configuracao() -> None:
    if APP_ENV not in {"development", "test", "production"}:
        raise RuntimeError("APP_ENV deve ser development, test ou production.")
    if LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise RuntimeError("LOG_LEVEL inválido.")
    if JWT_ALGORITHM != "HS256":
        raise RuntimeError("JWT_ALGORITHM deve permanecer HS256 nesta implantação.")
    if len(SECRET_KEY) < 64:
        raise RuntimeError("SECRET_KEY deve ter pelo menos 64 caracteres aleatórios.")
    field_key = _decode_key("FIELD_ENCRYPTION_KEY", FIELD_ENCRYPTION_KEY)
    if FIELD_ENCRYPTION_KEY == SECRET_KEY:
        raise RuntimeError("FIELD_ENCRYPTION_KEY deve ser diferente da SECRET_KEY.")
    if BACKUP_ENCRYPTION_KEY:
        backup_key = _decode_key("BACKUP_ENCRYPTION_KEY", BACKUP_ENCRYPTION_KEY)
        if backup_key == field_key:
            raise RuntimeError("BACKUP_ENCRYPTION_KEY deve ser independente da chave de campos.")
    if DB_SSL_MODE not in {
        "disable",
        "allow",
        "prefer",
        "require",
        "verify-ca",
        "verify-full",
    }:
        raise RuntimeError("DB_SSL_MODE inválido.")
    for network in TRUSTED_PROXY_CIDRS:
        try:
            ipaddress.ip_network(network, strict=False)
        except ValueError as exc:
            raise RuntimeError(f"TRUSTED_PROXY_CIDRS contém rede inválida: {network}.") from exc
    _validar_origens()

    if APP_ENV == "production":
        database = urlparse(DATABASE_URL)
        password = database.password or ""
        if len(password) < 16:
            raise RuntimeError("A senha do banco deve ter pelo menos 16 caracteres em produção.")
        if DB_SSL_MODE not in {"require", "verify-ca", "verify-full"}:
            hostname = database.hostname or ""
            private_database = hostname in {"db", "localhost"} or hostname.endswith(
                ".internal"
            )
            try:
                private_database = private_database or ipaddress.ip_address(
                    hostname
                ).is_private
            except ValueError:
                pass
            if not DB_ALLOW_INSECURE_PRIVATE or not private_database:
                raise RuntimeError(
                    "Produção exige TLS no PostgreSQL externo. Para banco privado "
                    "na mesma rede Docker, habilite DB_ALLOW_INSECURE_PRIVATE=true."
                )
        if not BACKUP_ENCRYPTION_KEY:
            raise RuntimeError("Produção exige BACKUP_ENCRYPTION_KEY independente.")


_validar_configuracao()
