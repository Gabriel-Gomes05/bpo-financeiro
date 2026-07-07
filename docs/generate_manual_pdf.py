from __future__ import annotations

import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / ".tools" / "reportlab"))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


class Node:
    def __init__(self, tag: str, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.parent = parent
        self.children: list[Node | str] = []

    def text(self) -> str:
        parts = []
        for child in self.children:
            parts.append(child.text() if isinstance(child, Node) else child)
        return re.sub(r"\s+", " ", "".join(parts)).strip()


class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in {"meta", "link", "br", "hr", "img", "input"}:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, attrs, self.current))

    def handle_endtag(self, tag):
        cursor = self.current
        while cursor is not self.root:
            if cursor.tag == tag:
                self.current = cursor.parent
                return
            cursor = cursor.parent

    def handle_data(self, data):
        self.current.children.append(data)


NAVY = colors.HexColor("#222049")
BLUE = colors.HexColor("#5e93cc")
INK = colors.HexColor("#222049")
MUTED = colors.HexColor("#64748b")
LIGHT = colors.HexColor("#f5f9fc")
BORDER = colors.HexColor("#dbe5ef")


def find_all(node: Node, tag: str) -> list[Node]:
    found = []
    for child in node.children:
        if isinstance(child, Node):
            if child.tag == tag:
                found.append(child)
            found.extend(find_all(child, tag))
    return found


def direct_nodes(node: Node, tags: set[str]) -> list[Node]:
    return [child for child in node.children if isinstance(child, Node) and child.tag in tags]


def safe_text(text: str) -> str:
    return html.escape(text, quote=False)


styles = getSampleStyleSheet()
title = ParagraphStyle("Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25,
                       leading=29, textColor=INK, alignment=TA_LEFT, spaceAfter=7)
kicker = ParagraphStyle("Kicker", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8,
                        leading=10, textColor=BLUE, spaceAfter=4)
h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=12,
                    leading=14, textColor=INK, spaceBefore=9, spaceAfter=4)
body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.4,
                      leading=13, textColor=INK, spaceAfter=6)
lead = ParagraphStyle("Lead", parent=body, fontSize=11, leading=15, textColor=colors.HexColor("#475569"), spaceAfter=9)
small = ParagraphStyle("Small", parent=body, fontSize=8, leading=11, textColor=MUTED)
callout = ParagraphStyle("Callout", parent=body, leftIndent=10, rightIndent=8, borderColor=BLUE,
                         borderWidth=1, borderPadding=8, backColor=colors.HexColor("#edf6ff"), spaceBefore=5, spaceAfter=8)
cell = ParagraphStyle("Cell", parent=body, fontSize=8.3, leading=10.5, spaceAfter=0)
cell_head = ParagraphStyle("CellHead", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)


class ManualDoc(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(filename, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                         topMargin=15 * mm, bottomMargin=16 * mm, title="Manual do Usuário - FLIC",
                         author="FLIC")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="content")
        self.addPageTemplates(PageTemplate(id="manual", frames=frame, onPage=self.draw_page))

    def draw_page(self, canvas, doc):
        if doc.page == 1:
            canvas.saveState()
            canvas.setFillColor(NAVY)
            canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
            canvas.setFillColor(BLUE)
            canvas.rect(0, 0, 18 * mm, A4[1], fill=1, stroke=0)
            canvas.restoreState()
            return
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(15 * mm, 8 * mm, "Manual do Usuário • FLIC")
        canvas.drawRightString(A4[0] - 15 * mm, 8 * mm, str(doc.page))
        canvas.restoreState()


def make_table(node: Node):
    rows = []
    for tr in find_all(node, "tr"):
        cells = direct_nodes(tr, {"th", "td"})
        if cells:
            rows.append([Paragraph(safe_text(c.text()), cell_head if c.tag == "th" else cell) for c in cells])
    if not rows:
        return None
    cols = max(len(row) for row in rows)
    widths = [170 * mm / cols] * cols
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), .4, BORDER),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def list_flow(node: Node):
    ordered = node.tag == "ol"
    items = []
    for li in direct_nodes(node, {"li"}):
        items.append(ListItem(Paragraph(safe_text(li.text()), body), leftIndent=13))
    return ListFlowable(items, bulletType="1" if ordered else "bullet", start="1", leftIndent=18,
                        bulletFontName="Helvetica-Bold", bulletColor=BLUE, spaceAfter=7)


def section_story(section: Node):
    story = []
    content = [c for c in section.children if isinstance(c, Node)]
    for node in content:
        cls = node.attrs.get("class", "")
        text = node.text()
        if not text and node.tag not in {"table"}:
            continue
        if node.tag == "div" and "kicker" in cls:
            story.append(Paragraph(safe_text(text.upper()), kicker))
        elif node.tag == "h2":
            story.extend([Paragraph(safe_text(text), title), Spacer(1, 4 * mm)])
        elif node.tag == "h3":
            story.append(Paragraph(safe_text(text), h3))
        elif node.tag == "p":
            story.append(Paragraph(safe_text(text), lead if "lead" in cls else (small if "small" in cls else body)))
        elif node.tag in {"ol", "ul"}:
            story.append(list_flow(node))
        elif node.tag == "table":
            table = make_table(node)
            if table:
                story.extend([table, Spacer(1, 3 * mm)])
        elif node.tag == "div" and "callout" in cls:
            story.append(Paragraph(safe_text(text), callout))
        elif node.tag == "div" and "grid" in cls:
            cards = direct_nodes(node, {"div"})
            card_flows = []
            for card in cards:
                headings = direct_nodes(card, {"h3"})
                paras = direct_nodes(card, {"p"})
                card_text = f"<b>{safe_text(headings[0].text())}</b><br/>{safe_text(paras[0].text())}" if headings and paras else safe_text(card.text())
                card_flows.append(Paragraph(card_text, callout))
            for i in range(0, len(card_flows), 2):
                pair = card_flows[i:i + 2]
                if len(pair) == 1:
                    pair.append("")
                t = Table([pair], colWidths=[84 * mm, 84 * mm], hAlign="LEFT")
                t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                       ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
                story.append(KeepTogether(t))
        elif node.tag == "div" and "flow" in cls:
            labels = [d.text() for d in direct_nodes(node, {"div"})]
            if labels:
                cells = [Paragraph(safe_text(label), cell_head) for label in labels]
                t = Table([cells], colWidths=[170 * mm / len(cells)] * len(cells))
                t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 1, BLUE),
                                       ("INNERGRID", (0, 0), (-1, -1), 2, colors.white), ("TOPPADDING", (0, 0), (-1, -1), 7),
                                       ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
                story.extend([t, Spacer(1, 3 * mm)])
    return story


def build():
    parser = TreeParser()
    parser.feed((ROOT / "Manual_do_Usuario_FLIC.html").read_text(encoding="utf-8"))
    sections = [s for s in find_all(parser.root, "section") if "page" in s.attrs.get("class", "")]
    story = [Spacer(1, 43 * mm), Paragraph("FLIC", ParagraphStyle("CoverBrand", parent=kicker, fontSize=12, textColor=BLUE)),
             Spacer(1, 20 * mm), Paragraph("Manual do Usuário", ParagraphStyle("CoverTitle", parent=title, fontSize=34, leading=39, textColor=colors.white)),
             Spacer(1, 5 * mm), Paragraph("Guia prático para operar lançamentos, conciliações, contas a pagar, rotinas, fechamentos e relatórios.",
                                         ParagraphStyle("CoverSub", parent=lead, fontSize=14, leading=20, textColor=colors.HexColor("#dbeeff"))),
             Spacer(1, 45 * mm), Paragraph("Versão de apoio • 22 de junho de 2026 • Uso interno", ParagraphStyle("CoverFoot", parent=small, textColor=colors.HexColor("#c8dff5"))),
             PageBreak()]
    for index, section in enumerate(sections[1:]):
        story.extend(section_story(section))
        if index < len(sections[1:]) - 1:
            story.append(PageBreak())
    ManualDoc(str(ROOT / "Manual_do_Usuario_FLIC.pdf")).build(story)


if __name__ == "__main__":
    build()
