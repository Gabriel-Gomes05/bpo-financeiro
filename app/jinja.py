"""
Instância única de Jinja2Templates compartilhada por todos os routers.
Registra T (strings) e now como globais — disponíveis em qualquer template
sem precisar passar como contexto.
"""

from datetime import date
from fastapi.templating import Jinja2Templates
from app.strings import T


class ApplicationTemplates(Jinja2Templates):
    """Mantém uma API única de renderização durante upgrades do Starlette."""

    def TemplateResponse(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.pop("context", {})
            request = context.get("request")
            if request is None:
                raise RuntimeError("O contexto do template deve incluir request.")
            return super().TemplateResponse(
                request=request,
                name=name,
                context=context,
                **kwargs,
            )
        return super().TemplateResponse(*args, **kwargs)


class _Today:
    """Proxy para date.today() — permite {{ now.strftime(...) }} nos templates."""
    def strftime(self, fmt: str) -> str:
        return date.today().strftime(fmt)
    def __bool__(self) -> bool:
        return True
    def __str__(self) -> str:
        return date.today().isoformat()


templates = ApplicationTemplates(directory="app/templates")
templates.env.globals["T"] = T
templates.env.globals["now"] = _Today()
