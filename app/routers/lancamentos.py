import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.jinja import templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.authorization import Permission, require_permission
from app.database import get_db
from app.models import (
    Atendimento, AtendimentoCentroCustoRateio, CentroCusto, ClienteBPO, CondicaoPagamento, FormaPagamento,
    PlanoConta, StatusConciliacao, TaxaAntecipacaoCliente, TaxaCartaoCliente,
    Usuario, PerfilUsuario,
)
from app.services.log_service import registrar as _log


def formatar_brl(valor) -> str:
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

router = APIRouter()
require_lancamentos = require_permission(Permission.LANCAMENTOS)


def clientes_do_usuario(db: Session, usuario: Usuario):
    if usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor):
        return db.query(ClienteBPO).filter(ClienteBPO.ativo == True).all()
    return db.query(ClienteBPO).filter(
        ClienteBPO.funcionario_id == usuario.id,
        ClienteBPO.ativo == True,
    ).all()


def _calcular_intervalos(forma_pagamento: str, parcela_total: int, recorrencia: Optional[str]):
    if forma_pagamento == "cartao_credito":
        n = max(int(parcela_total), 1)
        return [30 * i for i in range(1, n + 1)]
    if recorrencia:
        try:
            intervalos = [int(x.strip()) for x in recorrencia.split("/") if x.strip().isdigit()]
            if intervalos:
                return sorted(intervalos)
        except (ValueError, AttributeError):
            pass
    return [0]


def _str(lst: List[str], i: int) -> str:
    return lst[i].strip() if i < len(lst) else ""


def _decimal(lst: List[str], i: int) -> Optional[Decimal]:
    v = _str(lst, i).replace(",", ".")
    try:
        return Decimal(v) if v else None
    except InvalidOperation:
        return None


def _parse_rateios_json(raw: str, centros_validos: dict[int, CentroCusto], valor: Decimal) -> list[dict]:
    try:
        payload = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []

    rateios = []
    soma = Decimal("0")
    centros_usados: set[int] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            cc_id = int(item.get("centro_custo_id") or 0)
        except (TypeError, ValueError):
            continue
        cc = centros_validos.get(cc_id)
        pct = _decimal([str(item.get("percentual") or "")], 0)
        if not cc or pct is None or pct <= 0 or pct > 100 or cc.id in centros_usados:
            continue
        centros_usados.add(cc.id)
        soma += pct
        rateios.append({
            "centro": cc,
            "percentual": pct,
            "valor": (valor * pct / Decimal("100")).quantize(Decimal("0.01")),
        })
    if not rateios or soma != Decimal("100"):
        return []

    diferenca = valor - sum((r["valor"] for r in rateios), Decimal("0"))
    rateios[-1]["valor"] += diferenca
    return rateios


def _int(lst: List[str], i: int, default: int = 1) -> int:
    v = _str(lst, i)
    try:
        return int(v) if v else default
    except ValueError:
        return default


def _taxa_cartao(db: Session, cliente_id: int, bandeira: str) -> Optional[Decimal]:
    if not bandeira:
        return None
    # Para clientes com antecipação: usa a taxa de antecipação selecionada, se houver
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if cliente and cliente.antecipa:
        ant = db.query(TaxaAntecipacaoCliente).filter(
            TaxaAntecipacaoCliente.cliente_id == cliente_id,
            TaxaAntecipacaoCliente.bandeira == bandeira,
            TaxaAntecipacaoCliente.selecionada == True,
            TaxaAntecipacaoCliente.ativo == True,
        ).first()
        if ant:
            return Decimal(str(ant.taxa_percentual))
    # Fallback: taxa normal por bandeira
    taxa = db.query(TaxaCartaoCliente).filter(
        TaxaCartaoCliente.cliente_id == cliente_id,
        TaxaCartaoCliente.bandeira == bandeira,
        TaxaCartaoCliente.ativo == True,
    ).first()
    return Decimal(str(taxa.taxa_percentual)) if taxa else None


@router.get("/lancamentos", response_class=HTMLResponse)
async def listar_lancamentos(
    request: Request,
    cliente_id: Optional[int] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    status_conciliacao: Optional[str] = None,
    forma_pagamento: Optional[str] = None,
    flash: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_lancamentos),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    hoje = date.today()
    di_str = data_inicio or hoje.replace(day=1).isoformat()
    df_str = data_fim or hoje.isoformat()
    try:
        di = date.fromisoformat(di_str)
        df = date.fromisoformat(df_str)
    except ValueError:
        di = hoje.replace(day=1)
        df = hoje
        di_str, df_str = di.isoformat(), df.isoformat()

    status_conciliacao = status_conciliacao if status_conciliacao in {s.value for s in StatusConciliacao} else None
    forma_pagamento = forma_pagamento if forma_pagamento in {f.value for f in FormaPagamento} else None

    query = db.query(Atendimento).filter(Atendimento.cliente_id.in_(ids_permitidos))
    if cliente_id and cliente_id in ids_permitidos:
        query = query.filter(Atendimento.cliente_id == cliente_id)
    query = query.filter(
        Atendimento.data_atendimento >= di,
        Atendimento.data_atendimento <= df,
    )
    if status_conciliacao:
        query = query.filter(Atendimento.status_conciliacao == status_conciliacao)
    if forma_pagamento:
        query = query.filter(Atendimento.forma_pagamento == forma_pagamento)

    atendimentos = query.order_by(Atendimento.data_atendimento.desc(), Atendimento.criado_em.desc()).all()

    return templates.TemplateResponse("lancamentos.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "atendimentos": atendimentos,
        "cliente_selecionado": cliente_id,
        "data_inicio": di_str,
        "data_fim": df_str,
        "status_conciliacao_selecionado": status_conciliacao,
        "forma_pagamento_selecionada": forma_pagamento,
        "flash": flash,
        "formatar_brl": formatar_brl,
    })


@router.get("/lancamentos/novo", response_class=HTMLResponse)
async def pagina_novo_lancamento(
    request: Request,
    cliente_id: Optional[int] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    centros = db.query(CentroCusto).filter(
        CentroCusto.cliente_id.in_(ids_permitidos),
        CentroCusto.ativo == True,
    ).order_by(CentroCusto.nome).all()
    centros_por_cliente: dict = {}
    for cc in centros:
        centros_por_cliente.setdefault(cc.cliente_id, []).append({
            "id": cc.id, "codigo": cc.codigo, "nome": cc.nome,
            "is_medico": bool(cc.is_medico), "especialidade": cc.especialidade or "",
        })

    planos_conta_receita = db.query(PlanoConta).filter(
        PlanoConta.tipo == "receita",
        PlanoConta.ativo == True,
        or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id.in_(ids_permitidos)),
    ).order_by(PlanoConta.nome).all()

    return templates.TemplateResponse("lancamento_novo.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "cliente_selecionado": cliente_id if cliente_id in ids_permitidos else None,
        "hoje": date.today().isoformat(),
        "centros_por_cliente": centros_por_cliente,
        "planos_conta_receita": planos_conta_receita,
    })


@router.post("/lancamentos")
async def criar_lancamentos(
    request: Request,
    cliente_id: int = Form(...),
    data_atendimento: date = Form(...),
    nome_paciente: List[str] = Form(default=[]),
    cpf_paciente: List[str] = Form(default=[]),
    centro_custo_id: List[str] = Form(default=[]),
    rateios_json: List[str] = Form(default=[]),
    especialidade: List[str] = Form(default=[]),
    descricao_servico: List[str] = Form(default=[]),
    plano_conta_id: List[str] = Form(default=[]),
    valor_servico: List[str] = Form(default=[]),
    forma_pagamento: List[str] = Form(default=[]),
    condicao_pagamento: List[str] = Form(default=[]),
    parcela_total: List[str] = Form(default=[]),
    recorrencia: List[str] = Form(default=[]),
    ultimos_digitos_cartao: List[str] = Form(default=[]),
    bandeira_cartao: List[str] = Form(default=[]),
    percentual_medico: List[str] = Form(default=[]),
    observacao: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_lancamentos),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    if cliente_id not in ids_permitidos:
        return RedirectResponse(url="/lancamentos?erro=acesso_negado", status_code=303)

    cliente = next((c for c in clientes if c.id == cliente_id), None)
    centros_validos = {
        cc.id: cc for cc in db.query(CentroCusto).filter(
            CentroCusto.cliente_id == cliente_id,
            CentroCusto.ativo == True,
        ).all()
    }
    planos_validos = {
        pc.id: pc for pc in db.query(PlanoConta).filter(
            PlanoConta.tipo == "receita",
            PlanoConta.ativo == True,
            or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == cliente_id),
        ).all()
    }
    n = len(valor_servico)

    for i in range(n):
        valor = _decimal(valor_servico, i)
        if not valor:
            continue  # linha vazia — ignora

        forma = _str(forma_pagamento, i) or None
        condicao = _str(condicao_pagamento, i) or "avista"
        n_parcelas = _int(parcela_total, i, 1)
        rec = _str(recorrencia, i) or None

        is_parcelado = condicao == "parcelado"
        intervalos = _calcular_intervalos(forma or "", n_parcelas, rec) if is_parcelado else [0]
        if (
            cliente
            and cliente.antecipa
            and is_parcelado
            and forma == FormaPagamento.cartao_credito.value
            and intervalos
        ):
            intervalos = [intervalos[0] for _ in intervalos]
        num = len(intervalos)

        valor_parcela = (valor / Decimal(num)).quantize(Decimal("0.01"))
        valor_ultima = valor - valor_parcela * (num - 1)

        cc_id_str = _str(centro_custo_id, i)
        cc_id = int(cc_id_str) if cc_id_str.isdigit() else None
        rateio_raw = _str(rateios_json, i)
        rateios = _parse_rateios_json(rateio_raw, centros_validos, valor)
        if rateio_raw not in ("", "[]") and not rateios:
            db.rollback()
            return RedirectResponse(
                url=f"/lancamentos?cliente_id={cliente_id}&flash=Rateio+inv%C3%A1lido%3A+use+centros+diferentes+e+feche+100%25",
                status_code=303,
            )
        if rateios:
            cc = rateios[0]["centro"]
            cc_id = cc.id
        else:
            cc = centros_validos.get(cc_id) if cc_id else None

        especialidade_valor = _str(especialidade, i) or next(
            (r["centro"].especialidade for r in rateios if r["centro"].is_medico and r["centro"].especialidade),
            None,
        )
        pc_id_str = _str(plano_conta_id, i)
        plano = planos_validos.get(int(pc_id_str)) if pc_id_str.isdigit() else None

        pct_medico = _decimal(percentual_medico, i)
        bandeira = _str(bandeira_cartao, i) or None
        taxa_pct = _taxa_cartao(db, cliente_id, bandeira) if forma == FormaPagamento.cartao_credito.value else None

        for p, dias in enumerate(intervalos, 1):
            v = valor_ultima if p == num else valor_parcela
            valor_liquido = v
            if taxa_pct is not None:
                valor_liquido = (v * (Decimal("1") - taxa_pct / Decimal("100"))).quantize(Decimal("0.01"))

            valor_medico_parc = None
            if pct_medico:
                valor_medico_parc = (v * pct_medico / Decimal("100")).quantize(Decimal("0.01"))

            valor_clinica = valor_liquido - valor_medico_parc if valor_medico_parc is not None else valor_liquido

            atendimento = Atendimento(
                cliente_id=cliente_id,
                data_atendimento=data_atendimento,
                nome_paciente=_str(nome_paciente, i) or None,
                cpf_paciente=_str(cpf_paciente, i) or None,
                centro_custo_id=cc_id,
                medico=cc.nome if cc else None,
                especialidade=especialidade_valor,
                descricao_servico=_str(descricao_servico, i) or None,
                plano_conta_id=plano.id if plano else None,
                valor_servico=v,
                condicao_pagamento=condicao,
                parcela_numero=p,
                parcela_total=num,
                data_prevista_recebimento=data_atendimento + timedelta(days=dias),
                forma_pagamento=forma or None,
                ultimos_digitos_cartao=_str(ultimos_digitos_cartao, i) or None,
                bandeira_cartao=bandeira,
                taxa_cartao=taxa_pct,
                valor_liquido=valor_liquido,
                valor_clinica=valor_clinica,
                status_conciliacao=StatusConciliacao.pendente,
                percentual_medico=pct_medico or None,
                valor_medico=valor_medico_parc,
                observacao=_str(observacao, i) or None,
                lancado_por_id=usuario.id,
            )
            db.add(atendimento)
            db.flush()
            for r in rateios:
                db.add(AtendimentoCentroCustoRateio(
                    atendimento_id=atendimento.id,
                    centro_custo_id=r["centro"].id,
                    percentual=r["percentual"],
                    valor=(v * r["percentual"] / Decimal("100")).quantize(Decimal("0.01")),
                ))

    db.commit()
    cliente_obj = next((c for c in clientes if c.id == cliente_id), None)
    _log(
        db, f"Lançamentos criados", "lancamentos",
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        cliente_id=cliente_id, cliente_nome=cliente_obj.nome if cliente_obj else None,
        detalhes=f"{n} lançamento(s) em {data_atendimento.strftime('%d/%m/%Y')}",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(
        url=f"/lancamentos?cliente_id={cliente_id}&data_inicio={data_atendimento.isoformat()}&data_fim={data_atendimento.isoformat()}",
        status_code=303,
    )


@router.get("/lancamentos/{at_id}/editar", response_class=HTMLResponse)
async def form_editar_lancamento(
    at_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_lancamentos),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    at = db.query(Atendimento).filter(Atendimento.id == at_id).first()
    if not at or at.cliente_id not in ids_permitidos:
        return RedirectResponse(url="/lancamentos", status_code=303)
    centros_custo = db.query(CentroCusto).filter(
        CentroCusto.cliente_id == at.cliente_id,
        CentroCusto.ativo == True,
    ).order_by(CentroCusto.nome).all()
    planos_conta_receita = db.query(PlanoConta).filter(
        PlanoConta.tipo == "receita",
        PlanoConta.ativo == True,
        or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == at.cliente_id),
    ).order_by(PlanoConta.nome).all()
    return templates.TemplateResponse("lancamento_editar.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "at": at,
        "centros_custo": centros_custo,
        "planos_conta_receita": planos_conta_receita,
        "hoje": date.today().isoformat(),
        "formatar_brl": formatar_brl,
    })


@router.post("/lancamentos/{at_id}/editar")
async def salvar_edicao_lancamento(
    at_id: int,
    request: Request,
    data_atendimento: date = Form(...),
    nome_paciente: str = Form(""),
    cpf_paciente: str = Form(""),
    centro_custo_id: str = Form(""),
    especialidade: str = Form(""),
    descricao_servico: str = Form(""),
    plano_conta_id: str = Form(""),
    valor_servico: str = Form(...),
    forma_pagamento: str = Form(""),
    condicao_pagamento: str = Form("avista"),
    parcela_numero: int = Form(1),
    parcela_total: int = Form(1),
    ultimos_digitos_cartao: str = Form(""),
    bandeira_cartao: str = Form(""),
    percentual_medico: str = Form(""),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_lancamentos),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    at = db.query(Atendimento).filter(Atendimento.id == at_id).first()

    if not at or at.cliente_id not in ids_permitidos:
        return RedirectResponse(url="/lancamentos", status_code=303)
    if at.status_conciliacao == StatusConciliacao.conciliado:
        return RedirectResponse(
            url=f"/lancamentos?cliente_id={at.cliente_id}&flash=Atendimento+já+conciliado%2C+não+pode+ser+editado",
            status_code=303,
        )

    try:
        valor = Decimal(str(valor_servico).replace(",", "."))
    except InvalidOperation:
        return RedirectResponse(url=f"/lancamentos/{at_id}/editar", status_code=303)

    pct_medico = None
    if percentual_medico.strip():
        try:
            pct_medico = Decimal(str(percentual_medico).replace(",", "."))
        except InvalidOperation:
            pass

    bandeira = bandeira_cartao.strip() or None
    forma = forma_pagamento.strip() or None
    taxa_pct = _taxa_cartao(db, at.cliente_id, bandeira) if forma == FormaPagamento.cartao_credito.value else None

    valor_liquido = valor
    if taxa_pct is not None:
        valor_liquido = (valor * (Decimal("1") - taxa_pct / Decimal("100"))).quantize(Decimal("0.01"))

    valor_medico_calc = None
    if pct_medico:
        valor_medico_calc = (valor * pct_medico / Decimal("100")).quantize(Decimal("0.01"))

    valor_clinica = valor_liquido - valor_medico_calc if valor_medico_calc is not None else valor_liquido

    cc_id = int(centro_custo_id) if centro_custo_id.strip().isdigit() else None
    cc = db.query(CentroCusto).filter(
        CentroCusto.id == cc_id,
        CentroCusto.cliente_id == at.cliente_id,
        CentroCusto.ativo.is_(True),
    ).first() if cc_id else None
    if cc_id and not cc:
        return RedirectResponse(
            url=f"/lancamentos/{at_id}/editar?erro=centro_custo_invalido",
            status_code=303,
        )

    pc_id = int(plano_conta_id) if plano_conta_id.strip().isdigit() else None
    plano = db.query(PlanoConta).filter(
        PlanoConta.id == pc_id, PlanoConta.tipo == "receita", PlanoConta.ativo == True,
        or_(PlanoConta.cliente_id.is_(None), PlanoConta.cliente_id == at.cliente_id),
    ).first() if pc_id else None

    at.data_atendimento = data_atendimento
    at.nome_paciente = nome_paciente.strip() or None
    at.cpf_paciente = cpf_paciente.strip() or None
    at.centro_custo_id = cc_id
    at.medico = cc.nome if cc else None
    at.especialidade = especialidade.strip() or None
    at.plano_conta_id = plano.id if plano else None
    at.descricao_servico = descricao_servico.strip() or None
    at.valor_servico = valor
    at.condicao_pagamento = condicao_pagamento
    at.parcela_numero = parcela_numero
    at.parcela_total = parcela_total
    at.forma_pagamento = forma or None
    at.ultimos_digitos_cartao = ultimos_digitos_cartao.strip() or None
    at.bandeira_cartao = bandeira
    at.taxa_cartao = taxa_pct
    at.valor_liquido = valor_liquido
    at.percentual_medico = pct_medico
    at.valor_medico = valor_medico_calc
    at.valor_clinica = valor_clinica
    at.observacao = observacao.strip() or None

    db.commit()
    _log(
        db, "Lançamento editado", "lancamentos",
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        cliente_id=at.cliente_id,
        detalhes=f"Atendimento #{at_id} editado",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(
        url=f"/lancamentos?cliente_id={at.cliente_id}&data_inicio={data_atendimento.isoformat()}&data_fim={data_atendimento.isoformat()}",
        status_code=303,
    )


@router.post("/lancamentos/{at_id}/excluir")
async def excluir_lancamento(
    at_id: int,
    request: Request,
    cliente_id: int = Form(...),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(require_lancamentos),
):
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    at = db.query(Atendimento).filter(Atendimento.id == at_id).first()

    if not at or at.cliente_id not in ids_permitidos or at.cliente_id != cliente_id:
        return RedirectResponse(url=f"/lancamentos?cliente_id={cliente_id}", status_code=303)

    if at.status_conciliacao == StatusConciliacao.conciliado:
        return RedirectResponse(
            url=f"/lancamentos?cliente_id={cliente_id}&flash=Atendimento+já+conciliado%2C+não+pode+ser+excluído",
            status_code=303,
        )

    data_at = at.data_atendimento.isoformat()
    db.delete(at)
    db.commit()
    _log(
        db, "Lançamento excluído", "lancamentos",
        usuario_id=usuario.id, usuario_nome=usuario.nome,
        cliente_id=cliente_id,
        detalhes=f"Atendimento #{at_id} excluído",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse(
        url=f"/lancamentos?cliente_id={cliente_id}&data_inicio={data_at}&data_fim={data_at}",
        status_code=303,
    )
