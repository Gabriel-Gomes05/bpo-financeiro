from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from app.jinja import templates
from sqlalchemy.orm import Session

from app.auth import requer_coordenador
from app.database import get_db
from app.models import LogAuditoria, Usuario

router = APIRouter()

MODULOS = ["auth", "lancamentos", "conciliacao", "contas_pagar", "admin", "rotinas"]


@router.get("/logs", response_class=HTMLResponse)
async def pagina_logs(
    request: Request,
    modulo: Optional[str] = Query(None),
    usuario_id: Optional[str] = Query(None),   # str para aceitar string vazia do form
    data_inicio: Optional[str] = Query(None),
    data_fim: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(requer_coordenador),
):
    # converte usuario_id para int, ignorando string vazia
    uid: Optional[int] = None
    if usuario_id and usuario_id.strip():
        try:
            uid = int(usuario_id)
        except ValueError:
            pass

    q = db.query(LogAuditoria)

    if modulo and modulo.strip():
        q = q.filter(LogAuditoria.modulo == modulo.strip())
    if uid:
        q = q.filter(LogAuditoria.usuario_id == uid)
    if data_inicio and data_inicio.strip():
        try:
            di = date.fromisoformat(data_inicio.strip())
            q = q.filter(LogAuditoria.criado_em >= datetime(di.year, di.month, di.day, 0, 0, 0))
        except ValueError:
            pass
    if data_fim and data_fim.strip():
        try:
            df = date.fromisoformat(data_fim.strip())
            q = q.filter(LogAuditoria.criado_em <= datetime(df.year, df.month, df.day, 23, 59, 59))
        except ValueError:
            pass

    logs = q.order_by(LogAuditoria.criado_em.desc()).limit(500).all()
    todos_usuarios = db.query(Usuario).order_by(Usuario.nome).all()

    return templates.TemplateResponse("logs.html", {
        "request": request,
        "usuario": usuario,
        "clientes": [],
        "logs": logs,
        "modulos": MODULOS,
        "usuarios": todos_usuarios,
        "filtro_modulo": modulo or "",
        "filtro_usuario_id": uid,
        "filtro_data_inicio": data_inicio or "",
        "filtro_data_fim": data_fim or "",
    })
