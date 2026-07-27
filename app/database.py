"""Engine e sessões de runtime; migrations são executadas somente pelo Alembic."""
from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import (
    DATABASE_URL,
    DB_IDLE_TRANSACTION_TIMEOUT_MS,
    DB_MAX_OVERFLOW,
    DB_POOL_SIZE,
    DB_POOL_TIMEOUT_SECONDS,
    DB_SSL_MODE,
    DB_STATEMENT_TIMEOUT_MS,
)

_connect_args = {}
if DATABASE_URL.startswith("postgresql"):
    _connect_args = {
        "sslmode": DB_SSL_MODE,
        "application_name": "flic_web",
        "options": (
            f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS} "
            "-c lock_timeout=10000 "
            f"-c idle_in_transaction_session_timeout={DB_IDLE_TRANSACTION_TIMEOUT_MS}"
        ),
        "connect_timeout": 10,
    }

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=900,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT_SECONDS,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


@event.listens_for(Session, "before_flush")
def _preencher_auditoria(session: Session, _flush_context, _instances) -> None:
    actor_id = session.info.get("actor_id")
    if actor_id and session.bind and session.bind.dialect.name == "postgresql":
        session.connection().execute(
            text("SELECT set_config('app.user_id', :actor_id, true)"),
            {"actor_id": str(actor_id)},
        )
        request_id = session.info.get("request_id")
        if request_id:
            session.connection().execute(
                text("SELECT set_config('app.request_id', :request_id, true)"),
                {"request_id": str(request_id)},
            )
    for obj in session.new:
        if hasattr(obj, "created_by") and getattr(obj, "created_by", None) is None:
            obj.created_by = actor_id
        if hasattr(obj, "updated_by"):
            obj.updated_by = actor_id
    for obj in session.dirty:
        if hasattr(obj, "updated_by"):
            obj.updated_by = actor_id


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
