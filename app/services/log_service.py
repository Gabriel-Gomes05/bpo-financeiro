import logging

from sqlalchemy.orm import Session

from app.models import LogAuditoria

logger = logging.getLogger(__name__)


def registrar(
    db: Session,
    acao: str,
    modulo: str,
    usuario_id: int | None = None,
    usuario_nome: str = "",
    cliente_id: int | None = None,
    cliente_nome: str | None = None,
    detalhes: str | None = None,
    ip: str | None = None,
) -> None:
    entry = LogAuditoria(
        usuario_id=usuario_id,
        usuario_nome=usuario_nome,
        acao=acao,
        modulo=modulo,
        cliente_id=cliente_id,
        cliente_nome=cliente_nome,
        detalhes=detalhes,
        ip=ip,
    )
    db.add(entry)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "audit_log_persistence_failed",
            extra={
                "action": acao,
                "audit_module": modulo,
                "actor_id": usuario_id,
                "client_id": cliente_id,
            },
        )
