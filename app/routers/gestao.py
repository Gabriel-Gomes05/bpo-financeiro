from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.constants import GRUPOS_DRE
from app.database import get_db
from app.utils import cliente_ativo as _ca
from app.models import (
    Atendimento, AtendimentoCentroCustoRateio, CentroCusto, ClienteBPO, ContaPagar, ContaPagarCentroCustoRateio, OrcamentoValor,
    FechamentoDiario, PerfilUsuario, StatusConciliacao, StatusContaPagar, Usuario,
)

router = APIRouter()


def clientes_do_usuario(db: Session, usuario: Usuario):
    if usuario.perfil == PerfilUsuario.coordenador:
        return db.query(ClienteBPO).filter(ClienteBPO.ativo == True).all()
    return db.query(ClienteBPO).filter(
        ClienteBPO.funcionario_id == usuario.id,
        ClienteBPO.ativo == True,
    ).all()


def _brl(v) -> str:
    return f"{float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(valor, base) -> Decimal:
    valor = Decimal(str(valor or 0))
    base = Decimal(str(base or 0))
    if not base:
        return Decimal("0")
    return (valor / base * Decimal("100")).quantize(Decimal("0.01"))


def _retroceder_mes(mes: int, ano: int, quantidade: int = 1) -> tuple[int, int]:
    for _ in range(quantidade):
        if mes == 1:
            mes = 12
            ano -= 1
        else:
            mes -= 1
    return mes, ano


def _meses_no_intervalo(inicio: date, fim: date) -> list[tuple[int, int]]:
    meses = []
    mes = inicio.month
    ano = inicio.year
    while (ano, mes) <= (fim.year, fim.month):
        meses.append((mes, ano))
        if mes == 12:
            mes = 1
            ano += 1
        else:
            mes += 1
    return meses


def _resolver_periodo(periodo: str, mes: int, ano: int, hoje: date) -> tuple[date, date, str]:
    periodo = periodo if periodo in {"hoje", "7d", "30d", "90d", "ano", "mes"} else "mes"
    if periodo == "hoje":
        return hoje, hoje, periodo
    if periodo == "7d":
        return hoje - timedelta(days=6), hoje, periodo
    if periodo == "30d":
        return hoje - timedelta(days=29), hoje, periodo
    if periodo == "90d":
        return hoje - timedelta(days=89), hoje, periodo
    if periodo == "ano":
        return date(ano, 1, 1), date(ano, 12, 31), periodo
    return date(ano, mes, 1), date(ano, mes, monthrange(ano, mes)[1]), "mes"


def _key_centro_custo(cc: CentroCusto | None) -> str | None:
    if not cc:
        return None
    codigo = (cc.codigo or "").strip()
    return codigo or f"centro_custo:{cc.id}"


def _grupos_dre_cliente(db: Session, cliente_id: int | None) -> list[dict]:
    if not cliente_id:
        return GRUPOS_DRE

    centros = db.query(CentroCusto).filter(
        CentroCusto.cliente_id == cliente_id,
        CentroCusto.ativo == True,
    ).order_by(CentroCusto.codigo.asc(), CentroCusto.nome.asc()).all()

    receitas_por_key: dict[str, dict] = {}
    for cc in centros:
        key = _key_centro_custo(cc)
        if not key:
            continue
        if key not in receitas_por_key:
            receitas_por_key[key] = {
                "key": key,
                "codigo": (cc.codigo or "").strip(),
                "nome": cc.nome,
            }

    contas_plano = list(receitas_por_key.values())

    grupos = []
    if contas_plano:
        grupos.append({
            "nome": "RECEITAS POR PLANO DE CONTA",
            "tipo": "receita",
            "categorias": list(contas_plano),
        })
        grupos.append({
            "nome": "DESPESAS POR PLANO DE CONTA",
            "tipo": "despesa",
            "categorias": list(contas_plano),
        })
    else:
        grupos.append(GRUPOS_DRE[0])
        grupos.extend(g for g in GRUPOS_DRE if g["tipo"] == "despesa")

    return grupos


def _carregar_dre_periodo(
    db: Session,
    cliente_id: int,
    mes: int,
    ano: int,
    inicio: date | None = None,
    fim: date | None = None,
) -> dict:
    inicio = inicio or date(ano, mes, 1)
    fim = fim or date(ano, mes, monthrange(ano, mes)[1])
    meses_orcamento = _meses_no_intervalo(inicio, fim)

    orcado_map: dict[str, Decimal] = {}
    for mes_ref, ano_ref in meses_orcamento:
        rows = db.query(OrcamentoValor).filter(
            OrcamentoValor.cliente_id == cliente_id,
            OrcamentoValor.mes == mes_ref,
            OrcamentoValor.ano == ano_ref,
        ).all()
        for r in rows:
            orcado_map[r.categoria_key] = (
                orcado_map.get(r.categoria_key, Decimal("0"))
                + (r.valor_orcado or Decimal("0"))
            )

    ats = db.query(Atendimento).filter(
        Atendimento.cliente_id == cliente_id,
        Atendimento.status_conciliacao == StatusConciliacao.conciliado,
        Atendimento.data_credito >= inicio,
        Atendimento.data_credito <= fim,
    ).all()
    total_real_rec = sum(
        (a.valor_liquido or a.valor_servico or Decimal("0")) for a in ats
    )
    real_rec_por_cat: dict[str, Decimal] = {}
    for a in ats:
        if a.rateios_centro_custo:
            total_base = a.valor_liquido or a.valor_servico or Decimal("0")
            for rateio in a.rateios_centro_custo:
                cat_key = _key_centro_custo(rateio.centro_custo)
                if cat_key:
                    valor_rateio = (total_base * rateio.percentual / Decimal("100")).quantize(Decimal("0.01"))
                    real_rec_por_cat[cat_key] = real_rec_por_cat.get(cat_key, Decimal("0")) + valor_rateio
        else:
            cat_key = _key_centro_custo(a.centro_custo)
            if cat_key:
                real_rec_por_cat[cat_key] = (
                    real_rec_por_cat.get(cat_key, Decimal("0"))
                    + (a.valor_liquido or a.valor_servico or Decimal("0"))
                )

    cps = db.query(ContaPagar).filter(
        ContaPagar.cliente_id == cliente_id,
        ContaPagar.status == StatusContaPagar.pago,
        ContaPagar.data_pagamento >= inicio,
        ContaPagar.data_pagamento <= fim,
    ).all()
    total_real_desp = sum((c.valor or Decimal("0")) for c in cps)

    real_por_cat: dict[str, Decimal] = {}
    for cp in cps:
        if cp.rateios_centro_custo:
            for rateio in cp.rateios_centro_custo:
                real_por_cat[rateio.categoria_key] = (
                    real_por_cat.get(rateio.categoria_key, Decimal("0"))
                    + (rateio.valor or Decimal("0"))
                )
        elif cp.categoria_dre:
            real_por_cat[cp.categoria_dre] = (
                real_por_cat.get(cp.categoria_dre, Decimal("0"))
                + (cp.valor or Decimal("0"))
            )

    grupos_dre = []
    total_orcado_rec = Decimal("0")
    total_orcado_desp = Decimal("0")
    linhas_categoria = []

    grupos_base = _grupos_dre_cliente(db, cliente_id)
    receita_dinamica = bool(grupos_base and grupos_base[0]["nome"] == "RECEITAS POR PLANO DE CONTA")

    if receita_dinamica:
        receitas_mapeadas = sum(real_rec_por_cat.values(), Decimal("0"))
        receitas_sem_plano = total_real_rec - receitas_mapeadas
        if receitas_sem_plano:
            grupos_base[0]["categorias"].append({
                "key": "receitas_sem_plano",
                "codigo": "",
                "nome": "Receitas sem plano de conta",
            })
            real_rec_por_cat["receitas_sem_plano"] = receitas_sem_plano
        chaves_plano = {cat["key"] for cat in grupos_base[1]["categorias"]} if len(grupos_base) > 1 else set()
        despesas_mapeadas = sum(
            valor for key, valor in real_por_cat.items() if key in chaves_plano
        )
        despesas_sem_plano = total_real_desp - despesas_mapeadas
        if despesas_sem_plano:
            grupos_base[1]["categorias"].append({
                "key": "despesas_sem_plano",
                "codigo": "",
                "nome": "Despesas sem plano de conta",
            })
            real_por_cat["despesas_sem_plano"] = despesas_sem_plano

    for grupo in grupos_base:
        cats = []
        grupo_orcado = Decimal("0")
        grupo_real_calc = Decimal("0")
        for cat in grupo["categorias"]:
            chave_orcamento = f"{grupo['tipo']}:{cat['key']}"
            # Mantém leitura dos orçamentos antigos sem prefixo.
            orcado = orcado_map.get(
                chave_orcamento,
                orcado_map.get(cat["key"], Decimal("0")),
            )
            grupo_orcado += orcado
            if grupo["tipo"] == "despesa":
                cat_real = real_por_cat.get(cat["key"], Decimal("0"))
            elif receita_dinamica:
                cat_real = real_rec_por_cat.get(cat["key"], Decimal("0"))
            else:
                cat_real = Decimal("0")
            grupo_real_calc += cat_real
            cat_dict = {
                "key": cat["key"],
                "codigo": cat.get("codigo"),
                "nome": cat["nome"],
                "orcado": orcado,
                "real": cat_real,
                "dif": cat_real - orcado,
                "tipo": grupo["tipo"],
                "grupo_nome": grupo["nome"],
            }
            cats.append(cat_dict)
            linhas_categoria.append(cat_dict)

        if grupo["tipo"] == "receita":
            total_orcado_rec += grupo_orcado
            grupo_real_val = grupo_real_calc if receita_dinamica else total_real_rec
        else:
            total_orcado_desp += grupo_orcado
            grupo_real_val = grupo_real_calc

        grupos_dre.append({
            "nome": grupo["nome"],
            "tipo": grupo["tipo"],
            "categorias": cats,
            "grupo_orcado": grupo_orcado,
            "grupo_real": grupo_real_val,
            "grupo_dif": grupo_real_val - grupo_orcado,
        })

    resultado_orcado = total_orcado_rec - total_orcado_desp
    resultado_real = total_real_rec - total_real_desp
    resultado_dif = resultado_real - resultado_orcado

    maiores_despesas = sorted(
        [l for l in linhas_categoria if l["tipo"] == "despesa" and (l["real"] or l["orcado"])],
        key=lambda item: item["real"],
        reverse=True,
    )[:5]

    maiores_desvios = sorted(
        [l for l in linhas_categoria if l["tipo"] == "despesa" and (l["real"] or l["orcado"])],
        key=lambda item: abs(item["dif"]),
        reverse=True,
    )[:5]

    return {
        "inicio": inicio,
        "fim": fim,
        "grupos_dre": grupos_dre,
        "total_orcado_rec": total_orcado_rec,
        "total_real_rec": total_real_rec,
        "total_orcado_desp": total_orcado_desp,
        "total_real_desp": total_real_desp,
        "resultado_orcado": resultado_orcado,
        "resultado_real": resultado_real,
        "resultado_dif": resultado_dif,
        "linhas_categoria": linhas_categoria,
        "maiores_despesas": maiores_despesas,
        "maiores_desvios": maiores_desvios,
        "margem_real_pct": _pct(resultado_real, total_real_rec),
        "margem_orcada_pct": _pct(resultado_orcado, total_orcado_rec),
        "peso_despesa_pct": _pct(total_real_desp, total_real_rec),
    }


def _saldo_atual(db: Session, cliente_id: int, fim: date) -> dict | None:
    fechamento = (
        db.query(FechamentoDiario)
        .filter(
            FechamentoDiario.cliente_id == cliente_id,
            FechamentoDiario.data <= fim,
        )
        .order_by(FechamentoDiario.data.desc())
        .first()
    )
    if not fechamento:
        return None
    return {
        "valor": fechamento.saldo_conta or fechamento.saldo_provisorio_final or Decimal("0"),
        "data": fechamento.data,
    }


def _proximos_vencimentos(db: Session, cliente_id: int, hoje: date) -> dict:
    status_abertos = [
        StatusContaPagar.pendente,
        StatusContaPagar.aguardando_aprovacao,
        StatusContaPagar.agendado,
    ]
    contas = (
        db.query(ContaPagar)
        .filter(
            ContaPagar.cliente_id == cliente_id,
            ContaPagar.status.in_(status_abertos),
            ContaPagar.vencimento <= hoje + timedelta(days=30),
        )
        .order_by(ContaPagar.vencimento.asc())
        .all()
    )
    vencidas = [c for c in contas if c.vencimento < hoje]
    hoje_lista = [c for c in contas if c.vencimento == hoje]
    sete = [c for c in contas if hoje < c.vencimento <= hoje + timedelta(days=7)]
    trinta = [c for c in contas if hoje + timedelta(days=7) < c.vencimento <= hoje + timedelta(days=30)]

    def resumo(lista):
        return {
            "qtd": len(lista),
            "valor": sum((c.valor or Decimal("0")) for c in lista),
            "itens": lista[:4],
        }

    return {
        "vencidas": resumo(vencidas),
        "hoje": resumo(hoje_lista),
        "sete_dias": resumo(sete),
        "trinta_dias": resumo(trinta),
    }


def _insights_dre(dre_atual: dict, comparativo: dict, vencimentos: dict | None = None) -> list[dict]:
    insights = []
    resultado_real = dre_atual["resultado_real"]
    margem_real_pct = dre_atual["margem_real_pct"]
    delta_resultado = comparativo["delta_resultado"]
    peso_despesa_pct = dre_atual["peso_despesa_pct"]

    if resultado_real >= 0:
        insights.append({
            "titulo": "Operacao positiva",
            "texto": f"O periodo fechou com resultado positivo de R$ {_brl(resultado_real)} e margem de {margem_real_pct}%.",
            "tom": "emerald",
        })
    else:
        insights.append({
            "titulo": "Resultado em alerta",
            "texto": f"O periodo fechou negativo em R$ {_brl(resultado_real)}. Vale revisar despesas e ritmo de recebimentos.",
            "tom": "rose",
        })

    if delta_resultado >= 0:
        insights.append({
            "titulo": "Melhora vs mes anterior",
            "texto": f"O resultado evoluiu em R$ {_brl(delta_resultado)} frente ao mes anterior.",
            "tom": "sky",
        })
    else:
        insights.append({
            "titulo": "Queda vs mes anterior",
            "texto": f"O resultado recuou R$ {_brl(abs(delta_resultado))} frente ao mes anterior.",
            "tom": "amber",
        })

    maiores_despesas = dre_atual["maiores_despesas"]
    if maiores_despesas:
        maior = maiores_despesas[0]
        insights.append({
            "titulo": "Maior pressao de caixa",
            "texto": f"{maior['nome']} foi a maior despesa do periodo, com R$ {_brl(maior['real'])}.",
            "tom": "slate",
        })

    insights.append({
        "titulo": "Peso das despesas",
        "texto": f"As despesas representam {peso_despesa_pct}% da receita no periodo.",
        "tom": "slate",
    })

    if vencimentos and vencimentos["vencidas"]["qtd"]:
        insights.append({
            "titulo": "Contas vencidas",
            "texto": f"Existem {vencimentos['vencidas']['qtd']} conta(s) vencida(s), somando R$ {_brl(vencimentos['vencidas']['valor'])}.",
            "tom": "rose",
        })
    elif vencimentos and vencimentos["sete_dias"]["qtd"]:
        insights.append({
            "titulo": "Proximos vencimentos",
            "texto": f"Ha {vencimentos['sete_dias']['qtd']} conta(s) vencendo nos proximos 7 dias.",
            "tom": "amber",
        })

    return insights


# ---------------------------------------------------------------------------
# RECEITAS
# ---------------------------------------------------------------------------

@router.get("/gestao/receitas", response_class=HTMLResponse)
async def gestao_receitas(
    request: Request,
    cliente_id: Optional[int] = None,
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cliente_id = _ca(request, cliente_id)
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year
    clientes = clientes_do_usuario(db, usuario)
    ids = [c.id for c in clientes]

    atendimentos = []
    total = Decimal("0")

    if cliente_id and cliente_id in ids:
        from calendar import monthrange
        ultimo = monthrange(ano, mes)[1]
        inicio = date(ano, mes, 1)
        fim = date(ano, mes, ultimo)

        atendimentos = (
            db.query(Atendimento)
            .filter(
                Atendimento.cliente_id == cliente_id,
                Atendimento.data_atendimento >= inicio,
                Atendimento.data_atendimento <= fim,
            )
            .order_by(Atendimento.data_atendimento.desc())
            .all()
        )
        total = sum(
            (a.valor_liquido or a.valor_servico or Decimal("0")) for a in atendimentos
        )

    return templates.TemplateResponse("gestao_receitas.html", {
        "request": request, "usuario": usuario,
        "clientes": clientes, "cliente_selecionado": cliente_id,
        "mes": mes, "ano": ano,
        "atendimentos": atendimentos,
        "total": total, "brl": _brl,
    })


# ---------------------------------------------------------------------------
# DESPESAS
# ---------------------------------------------------------------------------

@router.get("/gestao/despesas", response_class=HTMLResponse)
async def gestao_despesas(
    request: Request,
    cliente_id: Optional[int] = None,
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    regime: str = "vencimento",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cliente_id = _ca(request, cliente_id)
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year
    if regime not in ("vencimento", "caixa", "competencia"):
        regime = "vencimento"
    clientes = clientes_do_usuario(db, usuario)
    ids = [c.id for c in clientes]

    contas = []
    total = Decimal("0")

    if cliente_id and cliente_id in ids:
        from calendar import monthrange
        ultimo = monthrange(ano, mes)[1]
        inicio = date(ano, mes, 1)
        fim = date(ano, mes, ultimo)

        if regime == "competencia":
            data_filtro = func.coalesce(ContaPagar.data_competencia, ContaPagar.vencimento)
        elif regime == "caixa":
            data_filtro = ContaPagar.data_pagamento
        else:
            data_filtro = ContaPagar.vencimento

        contas = (
            db.query(ContaPagar)
            .filter(
                ContaPagar.cliente_id == cliente_id,
                data_filtro >= inicio,
                data_filtro <= fim,
            )
            .order_by(data_filtro.desc())
            .all()
        )
        total = sum((c.valor or Decimal("0")) for c in contas)

    return templates.TemplateResponse("gestao_despesas.html", {
        "request": request, "usuario": usuario,
        "clientes": clientes, "cliente_selecionado": cliente_id,
        "mes": mes, "ano": ano, "regime": regime,
        "contas": contas,
        "total": total, "brl": _brl,
    })


# ---------------------------------------------------------------------------
# ORÇAMENTO
# ---------------------------------------------------------------------------

@router.get("/gestao/orcamento", response_class=HTMLResponse)
async def gestao_orcamento(
    request: Request,
    cliente_id: Optional[int] = None,
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cliente_id = _ca(request, cliente_id)
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year
    clientes = clientes_do_usuario(db, usuario)
    ids = [c.id for c in clientes]

    valores_map: dict[str, Decimal] = {}
    grupos = _grupos_dre_cliente(db, cliente_id)
    total_receitas_orcadas = Decimal("0")
    total_despesas_orcadas = Decimal("0")
    receita_base_real = Decimal("0")
    despesa_base_real = Decimal("0")
    mes_base, ano_base = _retroceder_mes(mes, ano, 1)
    if cliente_id and cliente_id in ids:
        rows = db.query(OrcamentoValor).filter(
            OrcamentoValor.cliente_id == cliente_id,
            OrcamentoValor.mes == mes,
            OrcamentoValor.ano == ano,
        ).all()
        valores_map = {r.categoria_key: r.valor_orcado for r in rows}
        for grupo in grupos:
            total_grupo = sum(
                (
                    valores_map.get(
                        f"{grupo['tipo']}:{cat['key']}",
                        valores_map.get(cat["key"], Decimal("0")),
                    )
                    or Decimal("0")
                )
                for cat in grupo["categorias"]
            )
            if grupo["tipo"] == "receita":
                total_receitas_orcadas += total_grupo
            else:
                total_despesas_orcadas += total_grupo

        # A recomendação usa o realizado da competência anterior, não o orçamento atual.
        dre_anterior = _carregar_dre_periodo(db, cliente_id, mes_base, ano_base)
        receita_base_real = dre_anterior["total_real_rec"]
        despesa_base_real = dre_anterior["total_real_desp"]

    margem_recomendada = Decimal("20")
    fator_despesa = Decimal("1") - (margem_recomendada / Decimal("100"))
    limite_despesas = receita_base_real * fator_despesa
    receita_necessaria = (
        despesa_base_real / fator_despesa if fator_despesa else Decimal("0")
    )

    return templates.TemplateResponse("gestao_orcamento.html", {
        "request": request, "usuario": usuario,
        "clientes": clientes, "cliente_selecionado": cliente_id,
        "mes": mes, "ano": ano,
        "grupos": grupos,
        "valores": valores_map,
        "total_receitas_orcadas": total_receitas_orcadas,
        "total_despesas_orcadas": total_despesas_orcadas,
        "receita_base_real": receita_base_real,
        "despesa_base_real": despesa_base_real,
        "mes_base": mes_base,
        "ano_base": ano_base,
        "margem_recomendada": margem_recomendada,
        "limite_despesas": limite_despesas,
        "receita_necessaria": receita_necessaria,
        "brl": _brl,
    })


@router.post("/gestao/orcamento")
async def salvar_orcamento(
    request: Request,
    cliente_id: int = Form(...),
    mes: int = Form(...),
    ano: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    if cliente_id not in [c.id for c in clientes]:
        return RedirectResponse(url="/gestao/orcamento", status_code=303)

    form = await request.form()

    # Upsert por categoria do plano DRE ativo para o cliente.
    for grupo in _grupos_dre_cliente(db, cliente_id):
        for cat in grupo["categorias"]:
            chave_orcamento = f"{grupo['tipo']}:{cat['key']}"
            raw = form.get(
                f"val_{grupo['tipo']}_{cat['key']}", "0"
            ).replace(",", ".").strip()
            try:
                valor = Decimal(raw)
            except Exception:
                valor = Decimal("0")

            row = db.query(OrcamentoValor).filter(
                OrcamentoValor.cliente_id == cliente_id,
                OrcamentoValor.categoria_key == chave_orcamento,
                OrcamentoValor.mes == mes,
                OrcamentoValor.ano == ano,
            ).first()

            if row:
                row.valor_orcado = valor
            else:
                db.add(OrcamentoValor(
                    cliente_id=cliente_id,
                    categoria_key=chave_orcamento,
                    mes=mes, ano=ano,
                    valor_orcado=valor,
                ))

    db.commit()
    return RedirectResponse(
        url=f"/gestao/orcamento?cliente_id={cliente_id}&mes={mes}&ano={ano}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# DRE
# ---------------------------------------------------------------------------

@router.get("/gestao/dre/apresentacao", response_class=HTMLResponse)
async def gestao_dre_apresentacao(
    request: Request,
    cliente_id: int,
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    periodo: str = "mes",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year
    clientes = clientes_do_usuario(db, usuario)
    cliente = next((c for c in clientes if c.id == cliente_id), None)
    if not cliente:
        return RedirectResponse(url="/gestao/dre", status_code=303)

    inicio, fim, periodo = _resolver_periodo(periodo, mes, ano, hoje)
    atual = _carregar_dre_periodo(db, cliente_id, mes, ano, inicio, fim)
    mes_ant, ano_ant = _retroceder_mes(mes, ano, 1)
    anterior = _carregar_dre_periodo(db, cliente_id, mes_ant, ano_ant)
    comparativo = {
        "mes": mes_ant,
        "ano": ano_ant,
        "receitas_real": anterior["total_real_rec"],
        "despesas_real": anterior["total_real_desp"],
        "resultado_real": anterior["resultado_real"],
        "margem_real_pct": anterior["margem_real_pct"],
        "delta_receitas": atual["total_real_rec"] - anterior["total_real_rec"],
        "delta_despesas": atual["total_real_desp"] - anterior["total_real_desp"],
        "delta_resultado": atual["resultado_real"] - anterior["resultado_real"],
        "delta_margem_pct": atual["margem_real_pct"] - anterior["margem_real_pct"],
    }
    serie_mensal = []
    for deslocamento in range(5, -1, -1):
        mes_ref, ano_ref = _retroceder_mes(mes, ano, deslocamento)
        ref = _carregar_dre_periodo(db, cliente_id, mes_ref, ano_ref)
        serie_mensal.append({
            "label": f"{mes_ref:02d}/{ano_ref}",
            "receita": ref["total_real_rec"],
            "despesa": ref["total_real_desp"],
            "resultado": ref["resultado_real"],
        })
    vencimentos = _proximos_vencimentos(db, cliente_id, hoje)
    insights = _insights_dre(atual, comparativo, vencimentos)
    return templates.TemplateResponse("gestao_dre_apresentacao.html", {
        "request": request,
        "usuario": usuario,
        "cliente": cliente,
        "mes": mes,
        "ano": ano,
        "periodo": periodo,
        "dre": atual,
        "comparativo": comparativo,
        "serie_mensal": serie_mensal,
        "insights": insights,
        "vencimentos": vencimentos,
        "brl": _brl,
    })

@router.get("/gestao/dre", response_class=HTMLResponse)
async def gestao_dre(
    request: Request,
    cliente_id: Optional[int] = None,
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    periodo: str = "mes",
    visao: str = "simples",
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cliente_id = _ca(request, cliente_id)
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year
    inicio_periodo, fim_periodo, periodo = _resolver_periodo(periodo, mes, ano, hoje)
    clientes = clientes_do_usuario(db, usuario)
    ids = [c.id for c in clientes]

    grupos_dre = []
    total_orcado_rec = Decimal("0")
    total_orcado_desp = Decimal("0")
    total_real_rec = Decimal("0")
    total_real_desp = Decimal("0")
    resultado_orcado = Decimal("0")
    resultado_real = Decimal("0")
    resultado_dif = Decimal("0")
    dre_cliente = None
    comparativo = None
    serie_mensal = []
    insights = []
    saldo_atual = None
    vencimentos = None
    visao = "cliente" if visao == "cliente" else "simples"

    if cliente_id and cliente_id in ids:
        atual = _carregar_dre_periodo(
            db,
            cliente_id,
            mes,
            ano,
            inicio_periodo,
            fim_periodo,
        )
        grupos_dre = atual["grupos_dre"]
        total_orcado_rec = atual["total_orcado_rec"]
        total_real_rec = atual["total_real_rec"]
        total_orcado_desp = atual["total_orcado_desp"]
        total_real_desp = atual["total_real_desp"]
        resultado_orcado = atual["resultado_orcado"]
        resultado_real = atual["resultado_real"]
        resultado_dif = atual["resultado_dif"]
        dre_cliente = atual
        saldo_atual = _saldo_atual(db, cliente_id, fim_periodo)
        vencimentos = _proximos_vencimentos(db, cliente_id, hoje)

        mes_ant, ano_ant = _retroceder_mes(mes, ano, 1)
        anterior = _carregar_dre_periodo(db, cliente_id, mes_ant, ano_ant)

        comparativo = {
            "mes": mes_ant,
            "ano": ano_ant,
            "receitas_real": anterior["total_real_rec"],
            "despesas_real": anterior["total_real_desp"],
            "resultado_real": anterior["resultado_real"],
            "margem_real_pct": anterior["margem_real_pct"],
            "delta_receitas": total_real_rec - anterior["total_real_rec"],
            "delta_despesas": total_real_desp - anterior["total_real_desp"],
            "delta_resultado": resultado_real - anterior["resultado_real"],
            "delta_margem_pct": dre_cliente["margem_real_pct"] - anterior["margem_real_pct"],
        }
        for deslocamento in range(5, -1, -1):
            mes_ref, ano_ref = _retroceder_mes(mes, ano, deslocamento)
            ref = _carregar_dre_periodo(db, cliente_id, mes_ref, ano_ref)
            serie_mensal.append({
                "mes": mes_ref,
                "ano": ano_ref,
                "label": f"{mes_ref:02d}/{ano_ref}",
                "receita": ref["total_real_rec"],
                "despesa": ref["total_real_desp"],
                "resultado": ref["resultado_real"],
                "margem_pct": ref["margem_real_pct"],
            })
        insights = _insights_dre(dre_cliente, comparativo, vencimentos)

    return templates.TemplateResponse("gestao_dre.html", {
        "request": request, "usuario": usuario,
        "clientes": clientes, "cliente_selecionado": cliente_id,
        "mes": mes, "ano": ano,
        "periodo": periodo,
        "visao": visao,
        "grupos_dre": grupos_dre,
        "total_orcado_rec": total_orcado_rec,
        "total_real_rec": total_real_rec,
        "total_orcado_desp": total_orcado_desp,
        "total_real_desp": total_real_desp,
        "resultado_orcado": resultado_orcado,
        "resultado_real": resultado_real,
        "resultado_dif": resultado_dif,
        "dre_cliente": dre_cliente,
        "comparativo": comparativo,
        "serie_mensal": serie_mensal,
        "insights": insights,
        "saldo_atual": saldo_atual,
        "vencimentos": vencimentos,
        "brl": _brl,
    })
