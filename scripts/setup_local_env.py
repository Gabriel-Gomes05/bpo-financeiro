"""Cria um .env local consistente sem exibir segredos no terminal."""
from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".env.example"
TARGET = ROOT / ".env"


def _key() -> str:
    return base64.urlsafe_b64encode(os.urandom(64)).decode("ascii")


if TARGET.exists():
    print(".env ja existe; nenhuma alteracao foi feita.")
    raise SystemExit(0)

migration_password = secrets.token_hex(24)
runtime_password = secrets.token_hex(24)
redis_password = secrets.token_hex(24)
values = {
    "MIGRATION_DB_PASSWORD": migration_password,
    "APP_DB_PASSWORD": runtime_password,
    "MIGRATION_DATABASE_URL": (
        f"postgresql://flic_migrator:{migration_password}@db:5432/flic"
    ),
    "DATABASE_URL": f"postgresql://flic_app:{runtime_password}@db:5432/flic",
    "SECRET_KEY": secrets.token_hex(64),
    "FIELD_ENCRYPTION_KEY": _key(),
    "BACKUP_ENCRYPTION_KEY": _key(),
    "REDIS_PASSWORD": redis_password,
    "REDIS_URL": f"redis://:{redis_password}@redis:6379/0",
}

lines: list[str] = []
for line in SOURCE.read_text(encoding="utf-8").splitlines():
    key, separator, _ = line.partition("=")
    if separator and key in values:
        line = f"{key}={values[key]}"
    lines.append(line)

TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print(".env local criado com segredos independentes; valores nao foram exibidos.")
