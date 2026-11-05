"""
Instância única de Jinja2Templates compartilhada por todos os routers.
Registra T (strings) e now como globais — disponíveis em qualquer template
sem precisar passar como contexto.
"""

from datetime import date
from fastapi.templating import Jinja2Templates
from app.errors import POR_SLUG
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


def _codigo_erro(slug) -> str:
    """Código do catálogo para o ?erro=<slug> das telas de cadastro."""
    definicao = POR_SLUG.get(slug or "")
    return definicao.codigo if definicao else "FLIC-GER-400"


templates = ApplicationTemplates(directory="app/templates")
templates.env.globals["T"] = T
templates.env.globals["now"] = _Today()
templates.env.globals["codigo_erro"] = _codigo_erro


def _brl(valor) -> str:
    """1234.5 -> '1.234,50' (apresentação; não arredonda regras de negócio)."""
    try:
        numero = float(valor or 0)
    except (TypeError, ValueError):
        return "0,00"
    return f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _rotulo_perfil(perfil) -> str:
    valor = getattr(perfil, "value", perfil) or ""
    return {
        "coordenador": "Coordenador", "editor": "Editor", "funcionario": "Funcionário",
        "secretaria": "Secretária", "medico": "Médico",
    }.get(str(valor), str(valor).capitalize())


templates.env.filters["brl"] = _brl
templates.env.filters["rotulo_perfil"] = _rotulo_perfil
