#!/usr/bin/env python3
"""Render TECHNICAL_REPORT.md as a polished, reproducible PDF."""

from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "TECHNICAL_REPORT.md"
OUTPUT = ROOT / "output" / "pdf" / "technical-report.pdf"
FIGURE = ROOT / "figures" / "observer_resolution.png"

FONT_ROOT = Path("/System/Library/Fonts/Supplemental")
FONT_FILES = {
    "Report": FONT_ROOT / "Verdana.ttf",
    "Report-Bold": FONT_ROOT / "Verdana Bold.ttf",
    "Report-Italic": FONT_ROOT / "Verdana Italic.ttf",
    "Report-BoldItalic": FONT_ROOT / "Verdana Bold Italic.ttf",
}

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#20639B")
TEAL = colors.HexColor("#218380")
PALE = colors.HexColor("#EAF2F8")
LIGHT = colors.HexColor("#F5F7F9")
AMBER = colors.HexColor("#D98E04")
TEXT = colors.HexColor("#202A33")
MUTED = colors.HexColor("#5B6872")


def register_fonts() -> None:
    for name, path in FONT_FILES.items():
        if not path.exists():
            raise FileNotFoundError("Required report font missing: {}".format(path))
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily(
        "Report",
        normal="Report",
        bold="Report-Bold",
        italic="Report-Italic",
        boldItalic="Report-BoldItalic",
    )


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Report-Bold",
            fontSize=24,
            leading=30,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=8 * mm,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="Report",
            fontSize=12,
            leading=17,
            textColor=BLUE,
            spaceAfter=5 * mm,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Report-Bold",
            fontSize=16,
            leading=20,
            textColor=NAVY,
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Report-Bold",
            fontSize=12,
            leading=15,
            textColor=TEAL,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Report",
            fontSize=9,
            leading=13,
            textColor=TEXT,
            spaceAfter=2.6 * mm,
            alignment=TA_LEFT,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Report",
            fontSize=8.8,
            leading=12.5,
            leftIndent=5 * mm,
            firstLineIndent=-3.5 * mm,
            bulletIndent=0,
            textColor=TEXT,
            spaceAfter=1.5 * mm,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.4,
            leading=10,
            leftIndent=5 * mm,
            rightIndent=3 * mm,
            borderColor=colors.HexColor("#D9E1E8"),
            borderWidth=0.5,
            borderPadding=5,
            backColor=LIGHT,
            textColor=colors.HexColor("#263238"),
            spaceAfter=2.5 * mm,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["Normal"],
            fontName="Report-Italic",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontName="Report",
            fontSize=7.5,
            leading=10,
            textColor=MUTED,
        ),
        "status": ParagraphStyle(
            "Status",
            parent=base["Normal"],
            fontName="Report-Bold",
            fontSize=10,
            leading=14,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
    }


def readable_math(text: str) -> str:
    """Translate the report's compact TeX notation into PDF-friendly text."""

    value = text
    value = value.replace(r"\(", "").replace(r"\)", "")
    value = value.replace(r"\[", "").replace(r"\]", "")
    replacements = {
        r"\pm": "±",
        r"\le": "≤",
        r"\ge": "≥",
        r"\times": "×",
        r"\pi": "π",
        r"\alpha": "α",
        r"\beta": "β",
        r"\delta": "δ",
        r"\varepsilon": "ε",
        r"\infty": "∞",
        r"\sum": "Σ",
        r"\tanh": "tanh",
        r"\log": "log",
        r"\mid": "|",
        r"\qquad": "  ",
        r"\ldots": "…",
        r"\dots": "…",
        r"\langle": "<",
        r"\rangle": ">",
        r"\frac12": "1/2",
        r"\sqrt2": "√2",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    for _ in range(3):
        value = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", value)
    value = re.sub(r"\\(?:operatorname|mathrm|text|rm)\{([^{}]*)\}", r"\1", value)
    value = value.replace("_{", "_").replace("^{", "^")
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\\([A-Za-z]+)", r"\1", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value


def inline(text: str) -> str:
    value = escape(readable_math(text.strip()))
    value = value.replace("+/-", "±")
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"\*(.+?)\*", r"<i>\1</i>", value)
    value = re.sub(r"\bpi\b", "π", value)
    return value


def page_header_footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    if doc.page > 1:
        canvas.setStrokeColor(colors.HexColor("#D9E1E8"))
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, height - 15 * mm, width - 18 * mm, height - 15 * mm)
        canvas.setFont("Report", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            18 * mm,
            height - 11.5 * mm,
            "Quantum Harness #122 · Ranger Observer Ceff",
        )
    canvas.setFont("Report", 7)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(width / 2, 9 * mm, "Page {}".format(doc.page))
    canvas.restoreState()


def title_page(s: dict[str, ParagraphStyle]) -> list:
    story: list = [
        Spacer(1, 15 * mm),
        Paragraph("Observer-dependent<br/>effective central charge", s["title"]),
        Paragraph(
            "Quantum Harness challenge #122 · Technical report",
            s["subtitle"],
        ),
        HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=9 * mm),
    ]
    status = Table(
        [[Paragraph(
            "AUDITED OBSERVER-DEPENDENT CFT PLATFORM<br/>"
            "<font size='8'>Exact oracles · scalable Gaussian inference · global information ordering</font>",
            s["status"],
        )]],
        colWidths=[165 * mm],
    )
    status.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 1, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]
        )
    )
    story.extend(
        [
            status,
            Spacer(1, 10 * mm),
            Paragraph("<b>Team</b> Ranger / JunkaiWang-TheoPhy", s["body"]),
            Paragraph("<b>Date</b> 30 July 2026", s["body"]),
            Spacer(1, 5 * mm),
            Paragraph(
                "<b>Delivered:</b> source code, 61 focused tests, Slurm-ready "
                "configuration, aggregate CSV/JSON data, seven algorithmic "
                "innovations, global information-order diagnostics, and an "
                "exact local measurement-RG witness.",
                s["body"],
            ),
            Spacer(1, 6 * mm),
        ]
    )
    quick = [
        [
            Paragraph("<font color='#FFFFFF'><b>Calibration</b></font>", s["small"]),
            Paragraph("<font color='#FFFFFF'><b>Estimate</b></font>", s["small"]),
            Paragraph("<font color='#FFFFFF'><b>Status</b></font>", s["small"]),
        ],
        [
            Paragraph("Clean Ising", s["small"]),
            Paragraph("0.49999662", s["small"]),
            Paragraph("Pass", s["small"]),
        ],
        [
            Paragraph("Nishimori", s["small"]),
            Paragraph("0.4474 ± 0.0164*", s["small"]),
            Paragraph("Reference-connected", s["small"]),
        ],
        [
            Paragraph("Weak self-dual", s["small"]),
            Paragraph("0.5533 / 0.4019", s["small"]),
            Paragraph("Convergence mapped", s["small"]),
        ],
    ]
    table = Table(quick, colWidths=[55 * mm, 50 * mm, 60 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D2DC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 2 * mm),
            Paragraph(
                "* Reduced correction model; the full model and all windows "
                "are reported in the results table.",
                s["small"],
            ),
            PageBreak(),
        ]
    )
    return story


def markdown_table(rows: list[list[str]], s: dict[str, ParagraphStyle]) -> Table:
    width = 165 * mm
    count = len(rows[0])
    if count == 6:
        col_widths = [36 * mm, 29 * mm, 18 * mm, 24 * mm, 20 * mm, 38 * mm]
    else:
        col_widths = [width / count] * count
    cells = []
    for row_index, row in enumerate(rows):
        rendered = []
        for cell in row:
            content = inline(cell)
            if row_index == 0:
                content = "<font color='#FFFFFF'><b>{}</b></font>".format(content)
            rendered.append(Paragraph(content, s["small"]))
        cells.append(rendered)
    table = Table(cells, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Report-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D2DC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def parse_report(s: dict[str, ParagraphStyle]) -> list:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    story: list = []
    paragraph: list[str] = []
    index = 0
    skipped_titles = 0

    def flush() -> None:
        if paragraph:
            story.append(Paragraph(inline(" ".join(paragraph)), s["body"]))
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            flush()
            index += 1
            continue
        if stripped.startswith("# "):
            flush()
            skipped_titles += 1
            if skipped_titles > 1:
                story.append(Paragraph(inline(stripped[2:]), s["h1"]))
            index += 1
            continue
        if stripped.startswith("## "):
            flush()
            if stripped == "## Quantum Harness challenge 122 technical report":
                index += 1
                continue
            story.append(Paragraph(inline(stripped[3:]), s["h1"]))
            index += 1
            continue
        if stripped.startswith("### "):
            flush()
            heading = stripped[4:]
            story.append(Paragraph(inline(heading), s["h2"]))
            if heading == "6.2 Observer-resolution curves" and FIGURE.exists():
                image = Image(str(FIGURE), width=158 * mm, height=111 * mm)
                story.append(
                    KeepTogether(
                        [
                            image,
                            Paragraph(
                                "Figure 1. Production observer-dependent "
                                "central-charge estimates. Error bars are one "
                                "standard error; exact complete-loss endpoints "
                                "have zero Monte Carlo error.",
                                s["caption"],
                            ),
                        ]
                    )
                )
            index += 1
            continue
        if stripped.startswith("|"):
            flush()
            table_rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    table_rows.append(cells)
                index += 1
            if table_rows:
                story.append(markdown_table(table_rows, s))
                story.append(Spacer(1, 3 * mm))
            continue
        if stripped.startswith("- "):
            flush()
            story.append(
                KeepTogether(
                    [
                        Paragraph("• " + inline(stripped[2:]), s["bullet"]),
                        Spacer(1, 0.01),
                    ]
                )
            )
            index += 1
            continue
        if line.startswith("    "):
            flush()
            code_lines = []
            while index < len(lines) and (
                lines[index].startswith("    ") or not lines[index].strip()
            ):
                if lines[index].startswith("    "):
                    code_lines.append(escape(lines[index][4:]))
                else:
                    code_lines.append("")
                index += 1
            story.append(Paragraph("<br/>".join(code_lines), s["code"]))
            continue
        if stripped.startswith("Team:") or stripped.startswith("Submission date:") or stripped.startswith("Status:"):
            index += 1
            continue
        paragraph.append(stripped)
        index += 1
    flush()
    return story


def main() -> int:
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "tmp" / "pdfs").mkdir(parents=True, exist_ok=True)
    style = styles()
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=21 * mm,
        bottomMargin=17 * mm,
        title="Observer-dependent effective central charge",
        author="Ranger / JunkaiWang-TheoPhy",
        subject="Quantum Harness challenge 122 technical report",
    )
    story = title_page(style)
    story.extend(parse_report(style))
    document.build(
        story,
        onFirstPage=page_header_footer,
        onLaterPages=page_header_footer,
    )
    print("wrote {}".format(OUTPUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
