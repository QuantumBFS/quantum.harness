"""Deterministic, text-extractable A4 PDF rendering."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)

from .locale import get_locale
from .report_model import Callout, Equation, Figure, Paragraph as Text, ReportDocument, Table


def render_pdf(document: ReportDocument, destination: Path) -> Path:
    locale = get_locale(document.language)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    font = _register_cjk_font()
    facts_json = json.dumps(
        document.numeric_facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    facts_hash = hashlib.sha256(facts_json.encode("utf-8")).hexdigest()
    styles = _styles(font)
    pdf = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=_safe(document.title),
        author=_safe(document.author),
        subject=(
            f"{document.status}; numeric-facts-sha256={facts_hash}; "
            f"summary-sha256={document.summary_sha256}"
        ),
        creator="learning-mit deterministic report renderer",
        invariant=1,
        pageCompression=1,
    )
    story = [
        Spacer(1, 20 * mm),
        Paragraph(html.escape(_safe(document.exploratory_label)), styles["status"]),
        Spacer(1, 8 * mm),
        Paragraph(html.escape(_safe(document.title)), styles["title"]),
        Paragraph(html.escape(_safe(document.subtitle)), styles["subtitle"]),
        Spacer(1, 10 * mm),
        Paragraph(html.escape(_safe(document.abstract)), styles["abstract"]),
        Spacer(1, 14 * mm),
        Paragraph(html.escape(_safe(document.author)), styles["author"]),
        PageBreak(),
    ]
    figure_number = 0
    table_number = 0
    for section_index, section in enumerate(document.sections, 1):
        label = (
            f"第 {section_index:02d} 节"
            if document.language == "zh"
            else f"{locale.labels['section']} {section_index:02d}"
        )
        story.extend(
            [
                Paragraph(html.escape(_safe(label)), styles["kicker"]),
                Paragraph(html.escape(_safe(section.title)), styles["h1"]),
                Spacer(1, 3 * mm),
            ]
        )
        for block in section.blocks:
            if isinstance(block, Text):
                story.append(Paragraph(html.escape(_safe(block.text)), styles["body"]))
            elif isinstance(block, Equation):
                story.append(
                    Paragraph(html.escape(_safe(block.expression)), styles["equation"])
                )
                story.append(
                    Paragraph(html.escape(_safe(block.explanation)), styles["note"])
                )
            elif isinstance(block, Callout):
                story.append(
                    LongTable(
                        [[Paragraph(html.escape(_safe(block.title)), styles["callout_title"])],
                         [Paragraph(html.escape(_safe(block.text)), styles["body"])]],
                        colWidths=[174 * mm],
                        style=TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E8F3EE")),
                                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#277C5A")),
                                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                ("TOPPADDING", (0, 0), (-1, -1), 8),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                            ]
                        ),
                    )
                )
            elif isinstance(block, Figure):
                figure_number += 1
                story.extend(_figure(block, figure_number, destination.parent, styles, locale.labels))
            elif isinstance(block, Table):
                table_number += 1
                story.extend(_table(block, table_number, styles, locale.labels))
        if section_index != len(document.sections):
            story.append(PageBreak())

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#62737D"))
        canvas.drawString(17 * mm, 9 * mm, _safe(document.exploratory_label))
        canvas.drawRightString(
            A4[0] - 17 * mm,
            9 * mm,
            f"{locale.labels['page']} {doc.page}",
        )
        canvas.restoreState()

    pdf.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return destination


def _figure(block: Figure, number: int, root: Path, styles: dict, labels: dict) -> list:
    source = root / block.source
    if not source.is_file():
        raise ValueError(f"missing report figure: {source}")
    with PILImage.open(source) as image:
        width, height = image.size
    display_width = 174 * mm
    display_height = display_width * height / width
    if display_height > 150 * mm:
        display_height = 150 * mm
        display_width = display_height * width / height
    return [
        KeepTogether(
            [
                Spacer(1, 3 * mm),
                Image(str(source), width=display_width, height=display_height),
                Paragraph(
                    f"<b>{html.escape(labels['figure'])} {number}.</b> "
                    f"{html.escape(_safe(block.caption))}",
                    styles["caption"],
                ),
                Paragraph(
                    f"<b>{html.escape(labels['interpretation'])}:</b> "
                    f"{html.escape(_safe(block.inference_limit))}",
                    styles["note"],
                ),
            ]
        )
    ]


def _table(block: Table, number: int, styles: dict, labels: dict) -> list:
    rows = [
        [Paragraph(html.escape(_safe(value)), styles["table_head"]) for value in block.columns]
    ]
    rows.extend(
        [Paragraph(html.escape(_safe(value)), styles["table_cell"]) for value in row]
        for row in block.rows
    )
    widths = [174 * mm / len(block.columns)] * len(block.columns)
    table = LongTable(
        rows,
        colWidths=widths,
        repeatRows=1,
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F1F4")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD7DD")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        ),
    )
    return [
        Paragraph(
            f"<b>{html.escape(labels['table'])} {number}.</b> "
            f"{html.escape(_safe(block.title))}",
            styles["caption"],
        ),
        table,
        Paragraph(html.escape(_safe(block.note)), styles["note"]),
    ]


def _register_cjk_font() -> str:
    candidates = (
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            pdfmetrics.registerFont(
                TTFont("LearningMitCJK", str(path), subfontIndex=0)
            )
            return "LearningMitCJK"
        except Exception:
            continue
    raise RuntimeError("no usable local CJK font found for PDF rendering")


def _styles(font: str) -> dict[str, ParagraphStyle]:
    return {
        "status": ParagraphStyle("status", fontName=font, fontSize=9, leading=12, textColor=colors.HexColor("#B95C23")),
        "title": ParagraphStyle("title", fontName=font, fontSize=28, leading=34, textColor=colors.HexColor("#173B50")),
        "subtitle": ParagraphStyle("subtitle", fontName=font, fontSize=13, leading=18, textColor=colors.HexColor("#47616F")),
        "abstract": ParagraphStyle("abstract", fontName=font, fontSize=10.5, leading=16, textColor=colors.HexColor("#172B3A")),
        "author": ParagraphStyle("author", fontName=font, fontSize=9, leading=12, textColor=colors.HexColor("#5B6C78")),
        "kicker": ParagraphStyle("kicker", fontName=font, fontSize=7.5, leading=10, textColor=colors.HexColor("#B95C23")),
        "h1": ParagraphStyle("h1", fontName=font, fontSize=20, leading=25, textColor=colors.HexColor("#172B3A")),
        "body": ParagraphStyle("body", fontName=font, fontSize=9.2, leading=14, textColor=colors.HexColor("#172B3A"), spaceAfter=7),
        "equation": ParagraphStyle("equation", fontName=font, fontSize=10.2, leading=14, leftIndent=10, textColor=colors.HexColor("#175A7A"), spaceBefore=6),
        "caption": ParagraphStyle("caption", fontName=font, fontSize=7.8, leading=10.5, textColor=colors.HexColor("#344C59"), spaceBefore=4),
        "note": ParagraphStyle("note", fontName=font, fontSize=7.2, leading=9.5, textColor=colors.HexColor("#657680"), spaceAfter=6),
        "callout_title": ParagraphStyle("callout_title", fontName=font, fontSize=9, leading=12, textColor=colors.HexColor("#277C5A")),
        "table_head": ParagraphStyle("table_head", fontName=font, fontSize=7.4, leading=9.5, textColor=colors.HexColor("#173B50")),
        "table_cell": ParagraphStyle("table_cell", fontName=font, fontSize=7.1, leading=9.3, textColor=colors.HexColor("#273C48")),
    }


def _safe(value: str) -> str:
    return value.replace("—", "-").replace("–", "-").replace("‑", "-")
