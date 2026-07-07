"""
Instância única de Jinja2Templates compartilhada por todos os routers.
Registra T (strings) e now como globais — disponíveis em qualquer template
sem precisar passar como contexto.
"""

from datetime import date
from fastapi.templating import Jinja2Templates
from app.strings import T


class _Today:
    """Proxy para date.today() — permite {{ now.strftime(...) }} nos templates."""
    def strftime(self, fmt: str) -> str:
        return date.today().strftime(fmt)
    def __bool__(self) -> bool:
        return True
    def __str__(self) -> str:
        return date.today().isoformat()


templates = Jinja2Templates(directory="app/templates")
templates.env.globals["T"] = T
templates.env.globals["now"] = _Today()
