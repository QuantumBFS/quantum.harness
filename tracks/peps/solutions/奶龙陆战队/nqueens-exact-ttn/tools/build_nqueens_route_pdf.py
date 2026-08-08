from __future__ import annotations

from html import escape
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(
    "/Users/susstring/.codex/.chatgpt-projects/"
    "g-p-6a66e576208c819183ec882e73d5a8ec"
)
PROJECT = ROOT / "nqueens-rank-scan"
OUTPUT = ROOT / "output/pdf/nqueens_exact_ttn_gpu_cluster_technical_route_zh.pdf"

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT = 19 * mm
RIGHT = 19 * mm
TOP = 19 * mm
BOTTOM = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT - RIGHT

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#176B87")
CYAN = colors.HexColor("#64CCC5")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#52616B")
PALE = colors.HexColor("#EDF6F7")
PALE_BLUE = colors.HexColor("#EAF1F8")
GRID = colors.HexColor("#B8C6D1")
CODE_BG = colors.HexColor("#F4F6F8")


pdfmetrics.registerFont(
    TTFont("CJK", "/System/Library/Fonts/STHeiti Light.ttc")
)
pdfmetrics.registerFont(
    TTFont("CJKBold", "/System/Library/Fonts/STHeiti Medium.ttc")
)
pdfmetrics.registerFont(
    TTFont(
        "UnicodeMath",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    )
)
pdfmetrics.registerFont(TTFont("Mono", "/System/Library/Fonts/Menlo.ttc"))
pdfmetrics.registerFontFamily(
    "CJK",
    normal="CJK",
    bold="CJKBold",
    italic="CJK",
    boldItalic="CJKBold",
)


styles = getSampleStyleSheet()
BODY = ParagraphStyle(
    "BodyCJK",
    parent=styles["BodyText"],
    fontName="CJK",
    fontSize=9.4,
    leading=15.3,
    textColor=INK,
    alignment=TA_JUSTIFY,
    wordWrap="CJK",
    spaceAfter=5.5,
)
INTRO = ParagraphStyle(
    "Intro",
    parent=BODY,
    fontSize=11,
    leading=18,
    textColor=NAVY,
    alignment=TA_LEFT,
    spaceAfter=9,
)
H1 = ParagraphStyle(
    "Heading1CJK",
    parent=BODY,
    fontName="CJKBold",
    fontSize=18,
    leading=24,
    textColor=NAVY,
    spaceBefore=14,
    spaceAfter=9,
    keepWithNext=True,
)
H2 = ParagraphStyle(
    "Heading2CJK",
    parent=BODY,
    fontName="CJKBold",
    fontSize=13.2,
    leading=18,
    textColor=BLUE,
    spaceBefore=11,
    spaceAfter=6,
    keepWithNext=True,
)
H3 = ParagraphStyle(
    "Heading3CJK",
    parent=BODY,
    fontName="CJKBold",
    fontSize=10.7,
    leading=15,
    textColor=NAVY,
    spaceBefore=8,
    spaceAfter=4,
    keepWithNext=True,
)
BULLET = ParagraphStyle(
    "BulletCJK",
    parent=BODY,
    leftIndent=14,
    firstLineIndent=-8,
    bulletIndent=3,
    spaceAfter=3.3,
)
NUMBERED = ParagraphStyle(
    "NumberedCJK",
    parent=BULLET,
    leftIndent=18,
    firstLineIndent=-13,
)
QUOTE = ParagraphStyle(
    "QuoteCJK",
    parent=BODY,
    leftIndent=12,
    rightIndent=8,
    borderColor=CYAN,
    borderWidth=0,
    borderPadding=7,
    backColor=PALE,
    textColor=NAVY,
    spaceBefore=4,
    spaceAfter=8,
)
MATH = ParagraphStyle(
    "Math",
    parent=BODY,
    fontName="UnicodeMath",
    fontSize=10,
    leading=16,
    alignment=TA_CENTER,
    leftIndent=10,
    rightIndent=10,
    textColor=INK,
    backColor=colors.HexColor("#FAFCFD"),
    borderColor=colors.HexColor("#DDE8EE"),
    borderWidth=0.4,
    borderPadding=7,
    spaceBefore=5,
    spaceAfter=8,
)
CODE = ParagraphStyle(
    "Code",
    parent=BODY,
    fontName="Mono",
    fontSize=6.9,
    leading=10.2,
    leftIndent=7,
    rightIndent=7,
    backColor=CODE_BG,
    borderColor=GRID,
    borderWidth=0.35,
    borderPadding=6,
    spaceBefore=4,
    spaceAfter=8,
)
TABLE_CELL = ParagraphStyle(
    "TableCell",
    parent=BODY,
    fontSize=7.3,
    leading=10.3,
    alignment=TA_LEFT,
    spaceAfter=0,
)
TABLE_HEAD = ParagraphStyle(
    "TableHead",
    parent=TABLE_CELL,
    fontName="CJKBold",
    textColor=colors.white,
)
CAPTION = ParagraphStyle(
    "Caption",
    parent=BODY,
    fontSize=7.5,
    leading=10,
    textColor=MUTED,
    alignment=TA_CENTER,
)
TOC_HEADING = ParagraphStyle(
    "TOCHeading",
    parent=H1,
    fontSize=20,
    alignment=TA_CENTER,
    spaceAfter=15,
)
TOC_LEVELS = [
    ParagraphStyle(
        "TOC1",
        fontName="CJKBold",
        fontSize=9.5,
        leading=14,
        leftIndent=0,
        firstLineIndent=0,
        textColor=NAVY,
        spaceBefore=4,
    ),
    ParagraphStyle(
        "TOC2",
        fontName="CJK",
        fontSize=8.3,
        leading=12,
        leftIndent=13,
        firstLineIndent=0,
        textColor=INK,
    ),
    ParagraphStyle(
        "TOC3",
        fontName="CJK",
        fontSize=7.7,
        leading=11,
        leftIndent=27,
        firstLineIndent=0,
        textColor=MUTED,
    ),
]


class TechnicalDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=LEFT,
            rightMargin=RIGHT,
            topMargin=TOP,
            bottomMargin=BOTTOM,
            title="N 皇后固定张量网络的精确 TTN 收缩与 GPU 集群路线",
            author="Codex 与 susstring",
            subject="精确张量网络、对称收缩、外存归并与 GPU 集群实现",
        )
        frame = Frame(
            LEFT,
            BOTTOM,
            CONTENT_WIDTH,
            PAGE_HEIGHT - TOP - BOTTOM,
            id="normal",
        )
        self.addPageTemplates(
            PageTemplate(id="main", frames=frame, onPage=self._page)
        )
        self._heading_counter = 0

    def beforeDocument(self):
        self._heading_counter = 0

    def _page(self, canvas, doc):
        page = canvas.getPageNumber()
        if page == 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D8E2E9"))
        canvas.setLineWidth(0.4)
        canvas.line(LEFT, PAGE_HEIGHT - 13 * mm, PAGE_WIDTH - RIGHT, PAGE_HEIGHT - 13 * mm)
        canvas.setFont("CJK", 7.2)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            LEFT,
            PAGE_HEIGHT - 10.2 * mm,
            "N 皇后精确 TTN 收缩与 GPU 集群技术路线",
        )
        canvas.drawRightString(
            PAGE_WIDTH - RIGHT,
            9.5 * mm,
            f"{page}",
        )
        canvas.setFillColor(BLUE)
        canvas.rect(LEFT, 8.7 * mm, 18 * mm, 0.7 * mm, fill=1, stroke=0)
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        names = {
            "Heading1CJK": 0,
            "Heading2CJK": 1,
            "Heading3CJK": 2,
        }
        level = names.get(flowable.style.name)
        if level is None:
            return
        text = flowable.getPlainText()
        self._heading_counter += 1
        key = f"heading-{self._heading_counter}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, key))


def latex_to_text(value: str) -> str:
    s = value.strip()
    s = s.replace("{,}", ",")
    s = s.replace(r"\mathbf1", "1").replace(r"\mathbf 1", "1")
    replacements = {
        r"\sum": "Σ",
        r"\prod": "Π",
        r"\Delta": "Δ",
        r"\alpha": "α",
        r"\ell": "ℓ",
        r"\le": "≤",
        r"\ge": "≥",
        r"\ne": "≠",
        r"\in": "∈",
        r"\subseteq": "⊆",
        r"\cup": "∪",
        r"\cap": "∩",
        r"\varnothing": "∅",
        r"\mapsto": "↦",
        r"\rightarrow": "→",
        r"\to": "→",
        r"\pm": "±",
        r"\times": "×",
        r"\otimes": "⊗",
        r"\sim": "∼",
        r"\mid": "|",
        r"\setminus": "∖",
        r"\lfloor": "⌊",
        r"\rfloor": "⌋",
        r"\rangle": "⟩",
        r"\ldots": "…",
        r"\cdots": "⋯",
        r"\quad": "  ",
        r"\qquad": "    ",
        r"\,": " ",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    s = re.sub(r"\\tag\{([^{}]+)\}", r"  (\1)", s)
    s = re.sub(r"\\xrightarrow\{([^{}]+)\}", r" --\1→ ", s)
    s = re.sub(r"\\binom\s*([A-Za-z0-9]+)\s*([A-Za-z0-9]+)", r"C(\1,\2)", s)
    s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", s)
    for command in (
        "text",
        "mathrm",
        "operatorname",
        "mathcal",
        "mathbb",
        "boldsymbol",
        "mathbf",
        "boxed",
        "widehat",
    ):
        s = re.sub(rf"\\{command}\{{([^{{}}]+)\}}", r"\1", s)
        s = re.sub(rf"\\{command}\b", "", s)
    for command in (
        "min",
        "max",
        "log",
        "dim",
        "bmod",
    ):
        s = re.sub(rf"\\{command}\{{([^{{}}]+)\}}", r"\1", s)
        s = re.sub(rf"\\{command}\b", command, s)
    s = s.replace(r"\begin{cases}", "{").replace(r"\end{cases}", "}")
    s = s.replace(r"\substack", "")
    s = s.replace(r"\\", " ; ")
    s = s.replace("&", " ")
    s = s.replace("{", "(").replace("}", ")")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


INLINE_TOKEN = re.compile(r"(`[^`]+`|\\\(.+?\\\))")


def inline_markup(value: str) -> str:
    parts: list[str] = []
    position = 0
    for match in INLINE_TOKEN.finditer(value):
        parts.append(_plain_markup(value[position : match.start()]))
        token = match.group(0)
        if token.startswith("`"):
            parts.append(
                f'<font name="Mono" color="#17324D">{escape(token[1:-1])}</font>'
            )
        else:
            parts.append(
                f'<font name="UnicodeMath">{escape(latex_to_text(token[2:-2]))}</font>'
            )
        position = match.end()
    parts.append(_plain_markup(value[position:]))
    return "".join(parts)


def _plain_markup(value: str) -> str:
    escaped = escape(value)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" color="#176B87"><u>\1</u></a>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)
    return escaped


def table_widths(rows: list[list[str]]) -> list[float]:
    columns = max(len(row) for row in rows)
    maxima = []
    for column in range(columns):
        maximum = max(
            len(re.sub(r"[`*_]", "", row[column])) if column < len(row) else 0
            for row in rows
        )
        maxima.append(max(5, min(maximum, 32)))
    total = sum(maxima)
    minimum = 19 * mm if columns <= 6 else 13 * mm
    raw = [CONTENT_WIDTH * maximum / total for maximum in maxima]
    adjusted = [max(minimum, width) for width in raw]
    scale = CONTENT_WIDTH / sum(adjusted)
    return [width * scale for width in adjusted]


def markdown_table(rows: list[list[str]]) -> Table:
    normalized_columns = max(len(row) for row in rows)
    data = []
    for row_index, row in enumerate(rows):
        padded = row + [""] * (normalized_columns - len(row))
        style = TABLE_HEAD if row_index == 0 else TABLE_CELL
        data.append([Paragraph(inline_markup(cell.strip()), style) for cell in padded])
    table = Table(
        data,
        colWidths=table_widths(rows),
        repeatRows=1,
        hAlign="CENTER",
        splitByRow=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "CJKBold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, GRID),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def markdown_flowables(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    output = []
    paragraph: list[str] = []
    index = 0

    def flush_paragraph():
        if not paragraph:
            return
        text = " ".join(item.strip() for item in paragraph)
        output.append(Paragraph(inline_markup(text), BODY))
        paragraph.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            index += 1
            continue
        if stripped.startswith("```"):
            flush_paragraph()
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            code = "\n".join(code_lines)
            output.append(
                Preformatted(
                    code,
                    CODE,
                    maxLineLength=88,
                    splitChars=" /,._-",
                )
            )
            continue
        if stripped == r"\[":
            flush_paragraph()
            index += 1
            math_lines = []
            while index < len(lines) and lines[index].strip() != r"\]":
                math_lines.append(lines[index].strip())
                index += 1
            if index < len(lines):
                index += 1
            formula = latex_to_text("\n".join(math_lines))
            output.append(Paragraph(escape(formula), MATH))
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            style = H1 if level == 1 else H2 if level == 2 else H3
            output.append(Paragraph(inline_markup(title), style))
            index += 1
            continue
        if stripped in ("---", "***"):
            flush_paragraph()
            output.append(Spacer(1, 4))
            divider = Table([[""]], colWidths=[CONTENT_WIDTH], rowHeights=[0.7])
            divider.setStyle(
                TableStyle([("BACKGROUND", (0, 0), (-1, -1), CYAN)])
            )
            output.append(divider)
            output.append(Spacer(1, 6))
            index += 1
            continue
        if (
            "|" in stripped
            and index + 1 < len(lines)
            and is_table_separator(lines[index + 1])
        ):
            flush_paragraph()
            rows = [split_table_row(stripped)]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(split_table_row(lines[index]))
                index += 1
            output.append(markdown_table(rows))
            output.append(Spacer(1, 7))
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            quote_lines = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip()[1:].strip())
                index += 1
            output.append(
                Paragraph(inline_markup(" ".join(quote_lines)), QUOTE)
            )
            continue
        bullet = re.match(r"^[-*]\s+(.+)", stripped)
        numbered = re.match(r"^(\d+)\.\s+(.+)", stripped)
        if bullet:
            flush_paragraph()
            output.append(
                Paragraph(
                    inline_markup(bullet.group(1)),
                    BULLET,
                    bulletText="•",
                )
            )
            index += 1
            continue
        if numbered:
            flush_paragraph()
            output.append(
                Paragraph(
                    inline_markup(numbered.group(2)),
                    NUMBERED,
                    bulletText=f"{numbered.group(1)}.",
                )
            )
            index += 1
            continue
        paragraph.append(line)
        index += 1
    flush_paragraph()
    return output


def cover_story():
    title = Paragraph(
        "N 皇后固定张量网络的<br/>精确 TTN 收缩与 GPU 集群路线",
        ParagraphStyle(
            "CoverTitle",
            fontName="CJKBold",
            fontSize=27,
            leading=38,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
    )
    subtitle = Paragraph(
        "底层代数 · 收缩不变量 · 对称表示 · 外存归并 · V100 实测 / A100 部署",
        ParagraphStyle(
            "CoverSubtitle",
            fontName="CJK",
            fontSize=11,
            leading=18,
            textColor=BLUE,
            alignment=TA_CENTER,
        ),
    )
    rule = Table([[""]], colWidths=[86 * mm], rowHeights=[1.6])
    rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CYAN)]))
    meta = Table(
        [
            ["文档版本", "2026-07-30"],
            ["数学路线", "固定局部因子网络上的精确整数收缩"],
            ["当前验证", "Q(1) 至 Q(12)；N=15 推进至 111/120 概念节点"],
            ["GPU 验证", "8×Tesla V100-SXM2 32 GB；A100 部署方案已整理"],
        ],
        colWidths=[30 * mm, 108 * mm],
    )
    meta.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "CJK"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.4),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("TEXTCOLOR", (0, 0), (0, -1), BLUE),
                ("TEXTCOLOR", (1, 0), (1, -1), INK),
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.3, GRID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return [
        Spacer(1, 28 * mm),
        title,
        Spacer(1, 9 * mm),
        subtitle,
        Spacer(1, 9 * mm),
        rule,
        Spacer(1, 28 * mm),
        meta,
        Spacer(1, 26 * mm),
        Paragraph(
            "技术路线整理稿",
            ParagraphStyle(
                "CoverFooter",
                fontName="CJK",
                fontSize=9,
                textColor=MUTED,
                alignment=TA_CENTER,
            ),
        ),
        PageBreak(),
    ]


def build_story():
    story = cover_story()
    story.append(Paragraph("目录", TOC_HEADING))
    toc = TableOfContents()
    toc.levelStyles = TOC_LEVELS
    toc.dotsMinLevel = 0
    story.append(toc)
    story.append(PageBreak())
    story.append(Paragraph("阅读说明", H1))
    story.append(
        Paragraph(
            "本文将两部分内容整合为一个连续技术说明：第一篇解释精确 TTN "
            "计数路线的数学基础、正确性与实验边界；第二篇给出面向 V100/A100 "
            "服务器的 GPU 和多卡迁移架构。文中的 TTN 主要指局部因子网络的"
            "二叉收缩树，而不是由完整解枚举后压缩得到的状态 TTN。",
            INTRO,
        )
    )
    summary_data = [
        ["层次", "核心职责", "精确性依据"],
        ["局部网络", "用 W_ij 表示列与对角线兼容性", "0/1 因子乘积就是合法性指示值"],
        ["收缩树", "选择有限和的结合顺序", "部分收缩不变量与整数分配律"],
        ["对称表示", "列反射轨道商、行反射 DAG 复用", "群作用下的张量等价"],
        ["外存归并", "分块生成并精确合并同键贡献", "每个连接贡献恰处理一次"],
        ["GPU 多卡", "互斥键范围并行 sort/reduce", "相同键只进入一张卡"],
    ]
    story.append(markdown_table(summary_data))
    story.append(Spacer(1, 10))
    story.append(PageBreak())
    story.extend(
        markdown_flowables(
            PROJECT / "TECHNICAL_ROUTE_EXACT_TTN_NQUEENS.md"
        )
    )
    story.append(PageBreak())
    story.extend(markdown_flowables(PROJECT / "GPU_CLUSTER_ROUTE.md"))
    story.append(PageBreak())
    story.append(Paragraph("附录：复现入口与验证边界", H1))
    story.append(
        Paragraph(
            "当前推荐入口："
            "<font name=\"Mono\">python/contract_symmetric_parity_ttn.py</font>",
            BODY,
        )
    )
    story.append(
        Preformatted(
            "CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 python3 \\\n"
            "  python/contract_symmetric_parity_ttn.py \\\n"
            "  --n-min 12 --n-max 12 --join-chunk-pairs 8000000 \\\n"
            "  --block-reducer cuda --cuda-devices 0,1,2,3,4,5,6,7",
            CODE,
            maxLineLength=88,
            splitChars=" /,._-",
        )
    )
    story.append(
        Paragraph(
            "8×V100 路线已经精确得到 N=11 标量 2680 和 N=12 标量 14200。"
            "N=15 数据是同一预算下完成 111/120 概念节点后的精确部分前沿，"
            "并未得到最终标量。A100 尚需按目标服务器的显存、CUDA/CuPy 版本"
            "和本地 NVMe 条件重新基准测试。",
            BODY,
        )
    )
    return story


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = TechnicalDocTemplate(str(OUTPUT))
    doc.multiBuild(build_story())
    print(OUTPUT)


if __name__ == "__main__":
    main()
