from calendar import monthrange
from datetime import date
from decimal import Decimal
from io import BytesIO
import html
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from app.jinja import templates
from sqlalchemy.orm import Session

from app.auth import get_usuario_atual
from app.database import get_db
from app.utils import cliente_ativo as _ca
from app.models import (
    ClienteBPO, ContaPagar, MovimentacaoBancaria, PerfilUsuario,
    StatusContaPagar, StatusMovimentacaoBancaria, StatusTransferenciaCartao,
    TransferenciaCartao, Usuario,
)

ROOT = Path(__file__).resolve().parents[2]
REPORTLAB_PATH = ROOT / ".tools" / "reportlab"
if REPORTLAB_PATH.exists():
    sys.path.insert(0, str(REPORTLAB_PATH))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

router = APIRouter()


def clientes_do_usuario(db: Session, usuario: Usuario):
    if usuario.perfil in (PerfilUsuario.coordenador, PerfilUsuario.editor):
        return db.query(ClienteBPO).filter(ClienteBPO.ativo == True).all()
    return db.query(ClienteBPO).filter(
        ClienteBPO.funcionario_id == usuario.id,
        ClienteBPO.ativo == True,
    ).all()


def formatar_brl(valor: Decimal) -> str:
    return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _parse_data_aprovacao(data: Optional[str]) -> tuple[date, str]:
    data_selecionada = data or date.today().isoformat()
    try:
        data_obj = date.fromisoformat(data_selecionada)
    except ValueError:
        data_obj = date.today()
        data_selecionada = data_obj.isoformat()
    return data_obj, data_selecionada


def _parse_saldo(saldo: Optional[str]) -> Decimal:
    if not saldo:
        return Decimal("0")
    try:
        return Decimal(str(saldo).replace(",", "."))
    except Exception:
        return Decimal("0")


def _contas_para_aprovacao(db: Session, cliente_id: int, data_obj: date) -> list[ContaPagar]:
    return (
        db.query(ContaPagar)
        .filter(
            ContaPagar.cliente_id == cliente_id,
            ContaPagar.vencimento <= data_obj,
            ContaPagar.status.in_([StatusContaPagar.aguardando_aprovacao, StatusContaPagar.agendado]),
        )
        .order_by(ContaPagar.vencimento.asc(), ContaPagar.descricao.asc())
        .all()
    )


def _p(texto) -> str:
    return html.escape(str(texto or ""))


def _gerar_pdf_aprovacao(
    cliente: ClienteBPO,
    contas: list[ContaPagar],
    data_obj: date,
    saldo_conta: Decimal,
    total_despesas: Decimal,
    saldo_final: Decimal,
    usuario: Usuario,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Relatorio de aprovacao - {cliente.nome}",
    )

    navy = colors.HexColor("#222049")
    blue = colors.HexColor("#5e93cc")
    ink = colors.HexColor("#1f2937")
    muted = colors.HexColor("#64748b")
    light = colors.HexColor("#f5f9fc")
    border = colors.HexColor("#dbe5ef")
    green = colors.HexColor("#078234")
    red = colors.HexColor("#b91c1c")

    styles = {
        "eyebrow": ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=8, textColor=blue, leading=10),
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=19, textColor=navy, leading=23),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=9, textColor=muted, leading=13),
        "label": ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=7.5, textColor=muted, leading=9),
        "value": ParagraphStyle("value", fontName="Helvetica-Bold", fontSize=10, textColor=ink, leading=12),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8, textColor=ink, leading=10),
        "cell_right": ParagraphStyle("cell_right", fontName="Helvetica-Bold", fontSize=8, textColor=ink, leading=10, alignment=TA_RIGHT),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7.5, textColor=muted, leading=10),
        "sign": ParagraphStyle("sign", fontName="Helvetica", fontSize=8, textColor=ink, leading=11, alignment=TA_CENTER),
    }

    story = []
    story.append(Paragraph("RELATORIO DE APROVACAO", styles["eyebrow"]))
    story.append(Paragraph("Pagamentos pendentes para aprovacao do cliente", styles["title"]))
    story.append(Paragraph(
        "Documento gerado para conferencia dos pagamentos em aberto, saldos informados e aprovacao formal antes da execucao.",
        styles["subtitle"],
    ))
    story.append(Spacer(1, 5 * mm))

    header_data = [
        [
            Paragraph("Cliente", styles["label"]),
            Paragraph("Aprovar ate", styles["label"]),
            Paragraph("Gerado em", styles["label"]),
            Paragraph("Responsavel", styles["label"]),
        ],
        [
            Paragraph(_p(cliente.nome), styles["value"]),
            Paragraph(data_obj.strftime("%d/%m/%Y"), styles["value"]),
            Paragraph(date.today().strftime("%d/%m/%Y"), styles["value"]),
            Paragraph(_p(usuario.nome), styles["value"]),
        ],
    ]
    header = Table(header_data, colWidths=[58 * mm, 34 * mm, 34 * mm, 50 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), light),
        ("BOX", (0, 0), (-1, -1), 0.7, border),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, border),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(header)
    story.append(Spacer(1, 6 * mm))

    rows = [[
        Paragraph("Pagamento", styles["label"]),
        Paragraph("Descricao", styles["label"]),
        Paragraph("Fornecedor", styles["label"]),
        Paragraph("Valor", styles["label"]),
    ]]
    if contas:
        for conta in contas:
            rows.append([
                Paragraph(conta.vencimento.strftime("%d/%m/%Y"), styles["cell"]),
                Paragraph(_p(conta.descricao), styles["cell"]),
                Paragraph(_p(conta.fornecedor or "-"), styles["cell"]),
                Paragraph(f"R$ {formatar_brl(conta.valor or Decimal('0'))}", styles["cell_right"]),
            ])
    else:
        rows.append([
            Paragraph("Nenhuma conta pendente para aprovacao ate esta data.", styles["cell"]),
            "",
            "",
            "",
        ])

    tabela = Table(rows, colWidths=[28 * mm, 74 * mm, 46 * mm, 28 * mm], repeatRows=1)
    tabela_style = [
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.7, border),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, border),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    if not contas:
        tabela_style.append(("SPAN", (0, 1), (-1, 1)))
    tabela.setStyle(TableStyle(tabela_style))
    story.append(tabela)
    story.append(Spacer(1, 6 * mm))

    saldo_color = green if saldo_final >= 0 else red
    resumo = Table([
        ["Total de despesas", f"R$ {formatar_brl(total_despesas)}"],
        ["Saldo em conta informado", f"R$ {formatar_brl(saldo_conta)}"],
        ["Saldo final provisorio", f"R$ {formatar_brl(saldo_final)}"],
    ], colWidths=[116 * mm, 60 * mm])
    resumo.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, border),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, border),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#f0fdf4") if saldo_final >= 0 else colors.HexColor("#fff1f2")),
        ("TEXTCOLOR", (0, 0), (0, -1), navy),
        ("TEXTCOLOR", (1, 2), (1, 2), saldo_color),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(resumo)
    story.append(Spacer(1, 7 * mm))

    story.append(Paragraph(
        "Ao aprovar este relatorio, o cliente confirma a ciencia dos pagamentos listados e autoriza a continuidade do processo financeiro conforme os valores apresentados.",
        styles["small"],
    ))
    story.append(Spacer(1, 11 * mm))

    assinatura = Table([
        ["", ""],
        [
            Paragraph("Aprovado por", styles["sign"]),
            Paragraph("Data da aprovacao", styles["sign"]),
        ],
    ], colWidths=[82 * mm, 82 * mm])
    assinatura.setStyle(TableStyle([
        ("LINEABOVE", (0, 1), (0, 1), 0.8, navy),
        ("LINEABOVE", (1, 1), (1, 1), 0.8, navy),
        ("TOPPADDING", (0, 0), (-1, 0), 16 * mm),
        ("TOPPADDING", (0, 1), (-1, 1), 3 * mm),
    ]))
    story.append(assinatura)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


@router.get("/fechamento", response_class=HTMLResponse)
async def pagina_fechamento(
    request: Request,
    cliente_id: Optional[int] = None,
    data: Optional[str] = None,
    saldo: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cliente_id = _ca(request, cliente_id)
    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]
    data_obj, data_selecionada = _parse_data_aprovacao(data)

    cliente = None
    contas = []
    total_despesas = Decimal("0")
    saldo_conta = _parse_saldo(saldo)

    if cliente_id and cliente_id in ids_permitidos:
        cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
        contas = _contas_para_aprovacao(db, cliente_id, data_obj)
        total_despesas = sum((c.valor or Decimal("0")) for c in contas)

    saldo_final = saldo_conta - total_despesas

    texto_whatsapp = ""
    if cliente:
        linhas = [
            f"*{cliente.nome} - Aprovação de pagamentos*",
            f"Contas pendentes até {date.fromisoformat(data_selecionada).strftime('%d/%m/%Y')}",
            "",
        ]
        for conta in contas:
            linhas.append(
                f"- {conta.vencimento.strftime('%d/%m/%Y')} | {conta.descricao} | "
                f"{conta.fornecedor or '-'} | R$ {formatar_brl(conta.valor or Decimal('0'))}"
            )
        linhas += [
            "",
            f"*Total de despesas:* R$ {formatar_brl(total_despesas)}",
            f"*Saldo em conta no momento:* R$ {formatar_brl(saldo_conta)}",
            f"*Saldo final provisório:* R$ {formatar_brl(saldo_final)}",
        ]
        texto_whatsapp = "\n".join(linhas)

    ultimas_contas = (
        db.query(ContaPagar)
        .filter(
            ContaPagar.cliente_id.in_(ids_permitidos),
            ContaPagar.status != StatusContaPagar.pago,
        )
        .order_by(ContaPagar.vencimento.asc())
        .limit(10)
        .all()
    )

    return templates.TemplateResponse("fechamento.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "cliente_selecionado": cliente_id,
        "data_selecionada": data_selecionada,
        "cliente": cliente,
        "contas": contas,
        "total_despesas": total_despesas,
        "saldo_conta": saldo_conta,
        "saldo_final": saldo_final,
        "texto_whatsapp": texto_whatsapp,
        "ultimas_contas": ultimas_contas,
        "formatar_brl": formatar_brl,
    })


@router.get("/fechamento/aprovacao.pdf")
async def pdf_aprovacao(
    request: Request,
    cliente_id: int,
    data: Optional[str] = None,
    saldo: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cliente_id_cookie = _ca(request, cliente_id)
    cliente_id = cliente_id_cookie or cliente_id
    ids_permitidos = [c.id for c in clientes_do_usuario(db, usuario)]
    if cliente_id not in ids_permitidos:
        raise HTTPException(status_code=404)

    data_obj, _ = _parse_data_aprovacao(data)
    saldo_conta = _parse_saldo(saldo)
    cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404)

    contas = _contas_para_aprovacao(db, cliente_id, data_obj)
    total_despesas = sum((c.valor or Decimal("0")) for c in contas)
    saldo_final = saldo_conta - total_despesas
    pdf_bytes = _gerar_pdf_aprovacao(
        cliente=cliente,
        contas=contas,
        data_obj=data_obj,
        saldo_conta=saldo_conta,
        total_despesas=total_despesas,
        saldo_final=saldo_final,
        usuario=usuario,
    )
    filename = f"aprovacao_pagamentos_{cliente_id}_{data_obj.isoformat()}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/fechamento/mensal", response_class=HTMLResponse)
async def fechamento_mensal(
    request: Request,
    cliente_id: Optional[int] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
):
    cliente_id = _ca(request, cliente_id)
    hoje = date.today()
    di_str = data_inicio or hoje.replace(day=1).isoformat()
    df_str = data_fim or hoje.replace(day=monthrange(hoje.year, hoje.month)[1]).isoformat()

    try:
        di = date.fromisoformat(di_str)
        df = date.fromisoformat(df_str)
    except ValueError:
        di = hoje.replace(day=1)
        df = hoje.replace(day=monthrange(hoje.year, hoje.month)[1])
        di_str, df_str = di.isoformat(), df.isoformat()

    clientes = clientes_do_usuario(db, usuario)
    ids_permitidos = [c.id for c in clientes]

    cliente = None
    receitas_banco = []   # MovimentacaoBancaria PIX/TED conciliadas
    lotes_cartao = []     # TransferenciaCartao conciliadas no banco
    contas = []
    total_receitas = Decimal("0")
    total_receitas_banco = Decimal("0")
    total_receitas_cartao = Decimal("0")
    total_despesas = Decimal("0")

    if cliente_id and cliente_id in ids_permitidos:
        cliente = db.query(ClienteBPO).filter(ClienteBPO.id == cliente_id).first()

        # Receitas PIX/TED: movimentações bancárias de recebimento conciliadas com atendimento
        # Fonte: banco confirmado — Atendimento é só para conciliação, não para receita
        receitas_banco = (
            db.query(MovimentacaoBancaria)
            .filter(
                MovimentacaoBancaria.cliente_id == cliente_id,
                MovimentacaoBancaria.sentido == "recebimento",
                MovimentacaoBancaria.status == StatusMovimentacaoBancaria.conciliada,
                MovimentacaoBancaria.conciliada_com_atendimento_id.isnot(None),
                MovimentacaoBancaria.transferencia_cartao_id.is_(None),
                MovimentacaoBancaria.data_movimento >= di,
                MovimentacaoBancaria.data_movimento <= df,
            )
            .order_by(MovimentacaoBancaria.data_movimento.asc())
            .all()
        )
        total_receitas_banco = sum((m.valor or Decimal("0")) for m in receitas_banco)

        # Receitas de cartão: lotes conciliados no banco
        lotes_cartao = (
            db.query(TransferenciaCartao)
            .filter(
                TransferenciaCartao.cliente_id == cliente_id,
                TransferenciaCartao.status == StatusTransferenciaCartao.conciliada,
                TransferenciaCartao.data >= di,
                TransferenciaCartao.data <= df,
            )
            .order_by(TransferenciaCartao.data.asc(), TransferenciaCartao.bandeira)
            .all()
        )
        total_receitas_cartao = sum((l.valor_liquido or Decimal("0")) for l in lotes_cartao)

        total_receitas = total_receitas_banco + total_receitas_cartao

        contas = (
            db.query(ContaPagar)
            .filter(
                ContaPagar.cliente_id == cliente_id,
                ContaPagar.status == StatusContaPagar.pago,
                ContaPagar.data_pagamento >= di,
                ContaPagar.data_pagamento <= df,
            )
            .order_by(ContaPagar.data_pagamento.asc())
            .all()
        )
        total_despesas = sum((c.valor or Decimal("0")) for c in contas)

    resultado = total_receitas - total_despesas

    return templates.TemplateResponse("fechamento_mensal.html", {
        "request": request,
        "usuario": usuario,
        "clientes": clientes,
        "cliente_selecionado": cliente_id,
        "cliente": cliente,
        "data_inicio": di_str,
        "data_fim": df_str,
        "receitas_banco": receitas_banco,
        "lotes_cartao": lotes_cartao,
        "contas": contas,
        "total_receitas": total_receitas,
        "total_receitas_banco": total_receitas_banco,
        "total_receitas_cartao": total_receitas_cartao,
        "total_despesas": total_despesas,
        "resultado": resultado,
        "formatar_brl": formatar_brl,
    })
