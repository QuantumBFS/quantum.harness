"""Render the shared report model as a publication-style A4 PDF."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    LongTable,
    PageBreak as PdfPageBreak,
    PageTemplate,
    Paragraph as PdfParagraph,
    Preformatted,
    Spacer,
    Table as PdfTable,
    TableStyle,
)

from analysis.locale import EN_LOCALE, ReportLocale
from analysis.report_model import (
    Callout,
    CodeBlock,
    Equation,
    Figure,
    PageBreak,
    Paragraph,
    ReportDocument,
    Table,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT = RIGHT = 17 * mm
TOP = 18 * mm
BOTTOM = 17 * mm
FRAME_WIDTH = PAGE_WIDTH - LEFT - RIGHT
FRAME_HEIGHT = PAGE_HEIGHT - TOP - BOTTOM
INK = colors.HexColor("#172B3A")
MUTED = colors.HexColor("#5B6C78")
BLUE = colors.HexColor("#175A7A")
BLUE_DARK = colors.HexColor("#123E56")
BLUE_SOFT = colors.HexColor("#E8F2F6")
GREEN = colors.HexColor("#277C5A")
GREEN_SOFT = colors.HexColor("#E5F3ED")
ORANGE = colors.HexColor("#B95C23")
ORANGE_SOFT = colors.HexColor("#FAEEE5")
LINE = colors.HexColor("#D7E0E6")
WASH = colors.HexColor("#F5F8FA")


def render_pdf(
    report: ReportDocument,
    destination: Path,
    locale: ReportLocale = EN_LOCALE,
) -> Path:
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    fonts = _register_fonts(locale)
    styles = _styles(fonts, locale)
    frame = Frame(LEFT, BOTTOM, FRAME_WIDTH, FRAME_HEIGHT, id="body")
    document = BaseDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=LEFT,
        rightMargin=RIGHT,
        topMargin=TOP,
        bottomMargin=BOTTOM,
        title=report.title,
        author=report.author,
        subject=locale.pdf_subject,
        creator=locale.pdf_creator,
        pageCompression=1,
        invariant=1,
    )
    def on_page(canvas, document):
        _header_footer(canvas, document, locale, fonts)

    document.addPageTemplates(PageTemplate(id="body", frames=(frame,), onPage=on_page))
    story: List[object] = []
    story.extend(_title_page(report, styles, locale))
    figure_number = 0
    table_number = 0
    for section_number, section in enumerate(report.sections, start=1):
        section_blocks = list(section.blocks)
        starts_new_page = bool(section_blocks) and isinstance(section_blocks[0], PageBreak)
        if starts_new_page:
            if story and not isinstance(story[-1], PdfPageBreak):
                story.append(PdfPageBreak())
            section_blocks = section_blocks[1:]
        elif section_number > 1:
            story.append(Spacer(1, 4 * mm))
        story.append(
            PdfParagraph(_section_label(locale, section_number), styles["section_kicker"])
        )
        story.append(PdfParagraph(_escape(section.title), styles["h1"]))
        story.append(Spacer(1, 2.5 * mm))
        for block in section_blocks:
            if isinstance(block, Paragraph):
                story.append(PdfParagraph(_escape(block.text), styles["body"]))
            elif isinstance(block, Equation):
                story.extend(_equation(block, styles))
            elif isinstance(block, Figure):
                figure_number += 1
                story.extend(_figure(block, figure_number, styles, locale))
            elif isinstance(block, Table):
                table_number += 1
                story.extend(_table(block, table_number, styles, locale))
            elif isinstance(block, Callout):
                story.extend(_callout(block, styles))
            elif isinstance(block, CodeBlock):
                story.extend(_code(block, styles))
            elif isinstance(block, PageBreak):
                if story and not isinstance(story[-1], PdfPageBreak):
                    story.append(PdfPageBreak())
        story.append(Spacer(1, 4 * mm))
    document.build(story)
    return output


def _register_fonts(locale: ReportLocale = EN_LOCALE) -> Dict[str, str]:
    fonts = {
        "body": "Helvetica",
        "bold": "Helvetica-Bold",
        "italic": "Helvetica-Oblique",
        "serif": "Times-Roman",
        "serif_bold": "Times-Bold",
        "mono": "Courier",
        "cjk": "Helvetica",
    }
    if locale.code != "zh":
        return fonts
    cjk_candidates: Tuple[Tuple[Path, int], ...] = (
        (Path("/System/Library/Fonts/STHeiti Medium.ttc"), 0),
        (Path("/System/Library/Fonts/Hiragino Sans GB.ttc"), 0),
        (Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"), 0),
    )
    for path, subfont in cjk_candidates:
        if not path.is_file():
            continue
        try:
            pdfmetrics.registerFont(
                TTFont("IntegratedCJK", str(path), subfontIndex=subfont)
            )
            for role in ("body", "bold", "italic", "serif", "serif_bold", "cjk"):
                fonts[role] = "IntegratedCJK"
            return fonts
        except Exception:
            continue
    raise RuntimeError("no usable CJK font found for Chinese PDF rendering")


def _styles(
    fonts: Dict[str, str],
    locale: ReportLocale = EN_LOCALE,
) -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body_size = 8.7 if locale.code == "zh" else 8.35
    body_leading = 11.7 if locale.code == "zh" else 11.15
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName=fonts["serif_bold"],
            fontSize=29,
            leading=31,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            fontName=fonts["serif"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#DCEBF0"),
            spaceAfter=11,
        ),
        "author": ParagraphStyle(
            "Author",
            fontName=fonts["cjk"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#B9D1D9"),
        ),
        "abstract_label": ParagraphStyle(
            "AbstractLabel",
            fontName=fonts["bold"],
            fontSize=7.2,
            leading=9,
            textColor=BLUE,
            spaceAfter=4,
        ),
        "abstract": ParagraphStyle(
            "Abstract",
            fontName=fonts["serif"],
            fontSize=9.3,
            leading=12.6,
            textColor=INK,
            spaceAfter=8,
        ),
        "section_kicker": ParagraphStyle(
            "SectionKicker",
            fontName=fonts["bold"],
            fontSize=6.8,
            leading=8,
            textColor=ORANGE,
            spaceBefore=2,
            spaceAfter=3,
        ),
        "h1": ParagraphStyle(
            "H1",
            fontName=fonts["serif_bold"],
            fontSize=20,
            leading=22,
            textColor=INK,
            keepWithNext=True,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "Body",
            fontName=fonts["body"],
            fontSize=body_size,
            leading=body_leading,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=6.5,
            allowWidows=0,
            allowOrphans=0,
        ),
        "caption": ParagraphStyle(
            "Caption",
            fontName=fonts["body"],
            fontSize=7.1,
            leading=9.2,
            textColor=colors.HexColor("#3E505C"),
            spaceBefore=4,
        ),
        "table_note": ParagraphStyle(
            "TableNote",
            fontName=fonts["italic"],
            fontSize=6.7,
            leading=8.5,
            textColor=MUTED,
            spaceBefore=3,
            spaceAfter=6,
        ),
        "table_cell": ParagraphStyle(
            "TableCell",
            fontName=fonts["body"],
            fontSize=6.25,
            leading=7.6,
            textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "TableHead",
            fontName=fonts["bold"],
            fontSize=6.15,
            leading=7.3,
            textColor=colors.white,
        ),
        "callout_label": ParagraphStyle(
            "CalloutLabel",
            fontName=fonts["bold"],
            fontSize=7,
            leading=8.5,
            textColor=BLUE,
            spaceAfter=3,
        ),
        "callout_body": ParagraphStyle(
            "CalloutBody",
            fontName=fonts["body"],
            fontSize=8,
            leading=10.5,
            textColor=INK,
        ),
        "code_title": ParagraphStyle(
            "CodeTitle",
            fontName=fonts["bold"],
            fontSize=7,
            leading=8.5,
            textColor=colors.HexColor("#0C5660"),
            spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "Code",
            fontName=fonts["mono"],
            fontSize=6.7,
            leading=8.2,
            textColor=colors.HexColor("#DCEAF0"),
        ),
        "code_explanation": ParagraphStyle(
            "CodeExplanation",
            fontName=fonts["italic"],
            fontSize=6.7,
            leading=8.5,
            textColor=colors.HexColor("#B8CCD5"),
            spaceBefore=4,
        ),
        "toc": ParagraphStyle(
            "TOC",
            fontName=fonts["body"],
            fontSize=8,
            leading=11,
            textColor=INK,
        ),
    }


def _title_page(
    report: ReportDocument,
    styles: Dict[str, ParagraphStyle],
    locale: ReportLocale,
) -> List[object]:
    kicker = "QUANTUM HARNESS · CHALLENGE 122"
    if locale.code == "zh":
        kicker += f" · {_escape(locale.labels['technical_report'])}"
    title_content = [
        Spacer(1, 9 * mm),
        PdfParagraph(
            kicker,
            ParagraphStyle(
            "HeroKicker", parent=styles["section_kicker"], textColor=colors.HexColor("#9CE0D5")
            ),
        ),
        PdfParagraph(_escape(report.title), styles["title"]),
        PdfParagraph(_escape(report.subtitle), styles["subtitle"]),
        PdfParagraph(_escape(report.author), styles["author"]),
        Spacer(1, 8 * mm),
    ]
    hero = PdfTable([[title_content]], colWidths=[FRAME_WIDTH])
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#123E56")),
                ("BOX", (0, 0), (-1, -1), 0, colors.HexColor("#123E56")),
                ("LEFTPADDING", (0, 0), (-1, -1), 13 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 13 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 8 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10 * mm),
            ]
        )
    )
    result_table = PdfTable(
        [
            [
                PdfParagraph(
                    f"<b>0.498739</b><br/><font size='6'>{_escape(locale.labels['clean_result'])}</font>",
                    styles["toc"],
                ),
                PdfParagraph(
                    f"<b>0.456469</b><br/><font size='6'>{_escape(locale.labels['nishimori_result'])}</font>",
                    styles["toc"],
                ),
                PdfParagraph(
                    f"<b>0.444107</b><br/><font size='6'>{_escape(locale.labels['weak_result'])}</font>",
                    styles["toc"],
                ),
            ]
        ],
        colWidths=[FRAME_WIDTH / 3] * 3,
    )
    result_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BLUE_SOFT),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    toc_rows = [
        (
            PdfParagraph(f"<b>{index:02d}</b>", styles["toc"]),
            PdfParagraph(_escape(section.title), styles["toc"]),
        )
        for index, section in enumerate(report.sections, start=1)
    ]
    toc = PdfTable(toc_rows, colWidths=[13 * mm, FRAME_WIDTH - 13 * mm])
    toc.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -2), 0.35, LINE),
                ("TEXTCOLOR", (0, 0), (0, -1), BLUE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
            ]
        )
    )
    return [
        hero,
        Spacer(1, 7 * mm),
        PdfParagraph(_escape(locale.labels["abstract"]), styles["abstract_label"]),
        PdfParagraph(_escape(report.abstract), styles["abstract"]),
        Spacer(1, 2 * mm),
        result_table,
        Spacer(1, 7 * mm),
        PdfParagraph(_escape(locale.labels["contents"]), styles["abstract_label"]),
        toc,
        PdfPageBreak(),
    ]


def _equation(block: Equation, styles: Dict[str, ParagraphStyle]) -> List[object]:
    expression_style = ParagraphStyle(
        f"Equation{block.number}",
        fontName="Courier-Bold",
        fontSize=7.5,
        leading=10,
        textColor=BLUE_DARK,
    )
    number_style = ParagraphStyle(
        f"EquationNumber{block.number}",
        fontName="Times-Roman",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=MUTED,
    )
    table = PdfTable(
        [[
            PdfParagraph(_escape(block.expression), expression_style),
            PdfParagraph(f"({_escape(block.number)})", number_style),
        ]],
        colWidths=[FRAME_WIDTH - 15 * mm, 12 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFC")),
                ("LINEBEFORE", (0, 0), (0, -1), 2.2, BLUE),
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("LEFTPADDING", (0, 0), (0, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    explanation = PdfParagraph(_escape(block.explanation), styles["table_note"])
    return [Spacer(1, 2 * mm), KeepTogether([table, explanation]), Spacer(1, 1 * mm)]


def _figure(
    block: Figure,
    number: int,
    styles: Dict[str, ParagraphStyle],
    locale: ReportLocale,
) -> List[object]:
    source = block.source if block.source.is_absolute() else PACKAGE_ROOT / block.source
    if not source.is_file():
        raise ValueError(f"missing report figure: {source}")
    with PILImage.open(source) as image:
        width, height = image.size
    max_width = FRAME_WIDTH
    max_height = 82 * mm
    scale = min(max_width / width, max_height / height)
    figure = Image(str(source), width=width * scale, height=height * scale)
    caption = PdfParagraph(
        f"<b>{_escape(locale.labels['figure'])} {number}.</b> {_escape(block.caption)} "
        f"<font color='#5B6C78'><i>{_escape(locale.labels['interpretation_limit'])}:</i> "
        f"{_escape(block.inference_limit)}</font>",
        styles["caption"],
    )
    return [
        Spacer(1, 2.5 * mm),
        KeepTogether([figure, caption]),
        Spacer(1, 2.5 * mm),
    ]


def _table(
    block: Table,
    number: int,
    styles: Dict[str, ParagraphStyle],
    locale: ReportLocale,
) -> List[object]:
    column_count = len(block.columns)
    if column_count == 2:
        widths = [0.27 * FRAME_WIDTH, 0.73 * FRAME_WIDTH]
    elif column_count == 3:
        widths = [0.18 * FRAME_WIDTH, 0.42 * FRAME_WIDTH, 0.40 * FRAME_WIDTH]
    elif column_count == 4:
        widths = [0.15 * FRAME_WIDTH, 0.19 * FRAME_WIDTH, 0.34 * FRAME_WIDTH, 0.32 * FRAME_WIDTH]
    elif column_count == 5:
        widths = [0.15 * FRAME_WIDTH, 0.37 * FRAME_WIDTH, 0.23 * FRAME_WIDTH, 0.10 * FRAME_WIDTH, 0.15 * FRAME_WIDTH]
    elif column_count == 7:
        widths = [0.19 * FRAME_WIDTH, 0.11 * FRAME_WIDTH, 0.10 * FRAME_WIDTH, 0.20 * FRAME_WIDTH, 0.09 * FRAME_WIDTH, 0.13 * FRAME_WIDTH, 0.18 * FRAME_WIDTH]
    else:
        widths = [FRAME_WIDTH / column_count] * column_count
    data = [
        [PdfParagraph(_escape(cell), styles["table_head"]) for cell in block.columns]
    ]
    data.extend(
        [PdfParagraph(_escape(cell), styles["table_cell"]) for cell in row]
        for row in block.rows
    )
    table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#214A60")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), (colors.white, WASH)),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
            ]
        )
    )
    title = PdfParagraph(
        f"<b>{_escape(locale.labels['table'])} {number}.</b> {_escape(block.title)}",
        styles["caption"],
    )
    note = PdfParagraph(_escape(block.note), styles["table_note"])
    return [Spacer(1, 2 * mm), title, table, note, Spacer(1, 1.5 * mm)]


def _callout(block: Callout, styles: Dict[str, ParagraphStyle]) -> List[object]:
    palette = {
        "result": (GREEN, GREEN_SOFT),
        "warning": (ORANGE, ORANGE_SOFT),
        "principle": (BLUE, BLUE_SOFT),
        "oracle": (BLUE, BLUE_SOFT),
    }
    accent, background = palette.get(block.tone, (BLUE, BLUE_SOFT))
    label = ParagraphStyle(
        f"CalloutLabel{block.tone}",
        parent=styles["callout_label"],
        textColor=accent,
    )
    content = [
        PdfParagraph(_escape(block.title).upper(), label),
        PdfParagraph(_escape(block.text), styles["callout_body"]),
    ]
    table = PdfTable([[content]], colWidths=[FRAME_WIDTH])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("LINEBEFORE", (0, 0), (0, -1), 2.4, accent),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [Spacer(1, 2 * mm), KeepTogether([table]), Spacer(1, 2 * mm)]


def _code(block: CodeBlock, styles: Dict[str, ParagraphStyle]) -> List[object]:
    code = Preformatted(
        block.code,
        styles["code"],
        maxLineLength=82,
        splitChars=" ,()=",
    )
    content = [
        PdfParagraph(_escape(block.title).upper(), styles["code_title"]),
        code,
        PdfParagraph(_escape(block.explanation), styles["code_explanation"]),
    ]
    table = PdfTable([[content]], colWidths=[FRAME_WIDTH])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#122B39")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return [Spacer(1, 2 * mm), KeepTogether([table]), Spacer(1, 2 * mm)]


def _header_footer(
    canvas,
    document,
    locale: ReportLocale,
    fonts: Dict[str, str],
) -> None:
    canvas.saveState()
    page = canvas.getPageNumber()
    if page > 1:
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.45)
        canvas.line(LEFT, PAGE_HEIGHT - 12 * mm, PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 12 * mm)
        canvas.setFont(fonts["body"], 6.8)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            LEFT, PAGE_HEIGHT - 9.2 * mm, locale.labels["header_title"]
        )
        canvas.drawRightString(
            PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 9.2 * mm, locale.labels["header_team"]
        )
    canvas.setFont(fonts["body"], 7)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(PAGE_WIDTH / 2, 8.5 * mm, str(page))
    canvas.restoreState()


def _escape(value: object) -> str:
    return html.escape(str(value), quote=False).replace("\n", "<br/>")


def _section_label(locale: ReportLocale, number: int) -> str:
    if locale.code == "zh":
        return f"第 {number:02d} 节"
    return f"SECTION {number:02d}"
