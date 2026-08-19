"""Matriz central de permissões e dependências de autorização."""
from __future__ import annotations

from enum import Enum
from typing import Callable

from fastapi import Depends, HTTPException

from app.auth import get_usuario_atual
from app.models import PerfilUsuario, Usuario


class Permission(str, Enum):
    LANCAMENTOS = "lancamentos"
    CONCILIACAO = "conciliacao"
    CONTAS_PAGAR = "contas_pagar"
    ROTINAS = "rotinas"
    GESTAO = "gestao"
    ADMIN_CLIENTES = "admin_clientes"
    ADMIN_USUARIOS = "admin_usuarios"
    LOGS = "logs"


ROLE_PERMISSIONS: dict[PerfilUsuario, frozenset[Permission]] = {
    PerfilUsuario.coordenador: frozenset(Permission),
    PerfilUsuario.editor: frozenset(
        {
            Permission.LANCAMENTOS,
            Permission.CONCILIACAO,
            Permission.CONTAS_PAGAR,
            Permission.ROTINAS,
            Permission.GESTAO,
            Permission.ADMIN_CLIENTES,
        }
    ),
    PerfilUsuario.funcionario: frozenset(
        {
            Permission.LANCAMENTOS,
            Permission.CONCILIACAO,
            Permission.CONTAS_PAGAR,
            Permission.ROTINAS,
            Permission.GESTAO,
        }
    ),
    PerfilUsuario.secretaria: frozenset({Permission.LANCAMENTOS}),
    PerfilUsuario.medico: frozenset(
        {
            Permission.LANCAMENTOS,
            Permission.CONTAS_PAGAR,
            Permission.GESTAO,
        }
    ),
}


def has_permission(usuario: Usuario, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(usuario.perfil, frozenset())


def require_permission(permission: Permission) -> Callable:
    def dependency(usuario: Usuario = Depends(get_usuario_atual)) -> Usuario:
        if not has_permission(usuario, permission):
            raise HTTPException(status_code=403, detail="Acesso não permitido para este perfil.")
        return usuario

    return dependency
