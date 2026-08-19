"""Cria o primeiro coordenador de forma idempotente."""
from __future__ import annotations

import os

from app.auth import hash_senha, normalizar_email
from app.database import SessionLocal
from app.models import PerfilUsuario, Usuario


name = os.getenv("BOOTSTRAP_ADMIN_NAME", "").strip()
email = normalizar_email(os.getenv("BOOTSTRAP_ADMIN_EMAIL", ""))
password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
if not name or not email or not password:
    raise RuntimeError(
        "Defina BOOTSTRAP_ADMIN_NAME, BOOTSTRAP_ADMIN_EMAIL e "
        "BOOTSTRAP_ADMIN_PASSWORD."
    )

with SessionLocal() as db:
    existing = db.query(Usuario).filter(Usuario.email == email).first()
    if existing:
        print("Administrador inicial ja existe; nenhuma alteracao foi feita.")
    else:
        db.add(
            Usuario(
                nome=name,
                email=email,
                senha_hash=hash_senha(password),
                perfil=PerfilUsuario.coordenador,
                ativo=True,
            )
        )
        db.commit()
        print("Administrador inicial criado; a senha nao foi exibida.")
