"""Render the shared report model as one offline HTML document."""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import List

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


def render_html(report: ReportDocument, destination: Path) -> Path:
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    sections: List[str] = []
    figure_number = 0
    table_number = 0
    for section_number, section in enumerate(report.sections, start=1):
        blocks: List[str] = []
        for block in section.blocks:
            if isinstance(block, Paragraph):
                blocks.append(f"<p>{_text(block.text)}</p>")
            elif isinstance(block, Equation):
                blocks.append(_equation(block))
            elif isinstance(block, Figure):
                figure_number += 1
                blocks.append(_figure(block, figure_number))
            elif isinstance(block, Table):
                table_number += 1
                blocks.append(_table(block, table_number))
            elif isinstance(block, Callout):
                blocks.append(_callout(block))
            elif isinstance(block, CodeBlock):
                blocks.append(_code(block))
            elif isinstance(block, PageBreak):
                blocks.append('<div class="page-break" aria-hidden="true"></div>')
        sections.append(
            f'<section id="{html.escape(section.slug)}" class="report-section">'
            f'<div class="section-kicker">Section {section_number:02d}</div>'
            f"<h2>{html.escape(section.title)}</h2>"
            f"{''.join(blocks)}</section>"
        )
    toc = "".join(
        f'<a href="#{html.escape(section.slug)}">'
        f'<span>{index:02d}</span>{html.escape(section.title)}</a>'
        for index, section in enumerate(report.sections, start=1)
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{html.escape(report.title)}</title>
<style>{_css()}</style>
</head>
<body>
<header class="hero">
  <div class="hero-inner">
    <div class="eyebrow">Quantum Harness · Challenge 122 · Technical Report</div>
    <h1>{html.escape(report.title)}</h1>
    <p class="subtitle">{html.escape(report.subtitle)}</p>
    <div class="author">{html.escape(report.author)}</div>
    <div class="hero-rule"></div>
    <h2>Abstract</h2>
    <p class="abstract">{_text(report.abstract)}</p>
    <div class="result-strip">
      <div><strong>0.498739</strong><span>Clean Ising MC</span></div>
      <div><strong>0.456469</strong><span>Nishimori</span></div>
      <div><strong>0.444107</strong><span>Weak self-dual</span></div>
    </div>
  </div>
</header>
<div class="shell">
  <nav aria-label="Report contents">
    <div class="toc-title">Contents</div>
    {toc}
  </nav>
  <main>{''.join(sections)}</main>
</div>
<footer>
  <span>Team 卧龙凤雏</span>
  <span>Frozen-data report · 29 July 2026</span>
</footer>
</body>
</html>
"""
    output.write_text(document, encoding="utf-8")
    return output


def _equation(block: Equation) -> str:
    return (
        '<div class="equation">'
        f'<div class="equation-expression">{html.escape(block.expression)}</div>'
        f'<div class="equation-number">({html.escape(block.number)})</div>'
        f'<p>{_text(block.explanation)}</p>'
        "</div>"
    )


def _figure(block: Figure, number: int) -> str:
    source = block.source if block.source.is_absolute() else PACKAGE_ROOT / block.source
    if not source.is_file():
        raise ValueError(f"missing report figure: {source}")
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    return (
        '<figure class="report-figure">'
        f'<img src="data:image/png;base64,{encoded}" alt="{html.escape(block.alt_text)}">'
        "<figcaption>"
        f"<strong>Figure {number}.</strong> {_text(block.caption)}"
        f'<span class="limit"><strong>Interpretation limit:</strong> {_text(block.inference_limit)}</span>'
        "</figcaption></figure>"
    )


def _table(block: Table, number: int) -> str:
    headings = "".join(f"<th>{html.escape(column)}</th>" for column in block.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_text(cell)}</td>" for cell in row) + "</tr>"
        for row in block.rows
    )
    return (
        '<figure class="report-table">'
        f'<figcaption><strong>Table {number}.</strong> {html.escape(block.title)}</figcaption>'
        f'<div class="table-scroll"><table><thead><tr>{headings}</tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
        f'<p class="table-note">{_text(block.note)}</p>'
        "</figure>"
    )


def _callout(block: Callout) -> str:
    tone = block.tone if block.tone in {"result", "principle", "warning", "oracle"} else "principle"
    return (
        f'<aside class="callout {tone}"><div class="callout-label">'
        f"{html.escape(block.title)}</div><p>{_text(block.text)}</p></aside>"
    )


def _code(block: CodeBlock) -> str:
    return (
        '<div class="code-panel">'
        f"<h3>{html.escape(block.title)}</h3>"
        f"<pre><code>{html.escape(block.code)}</code></pre>"
        f"<p>{_text(block.explanation)}</p>"
        "</div>"
    )


def _text(value: object) -> str:
    escaped = html.escape(str(value))
    escaped = escaped.replace("Xoshiro256++", "<code>Xoshiro256++</code>")
    escaped = escaped.replace("c_eff", "<em>c</em><sub>eff</sub>")
    escaped = escaped.replace("c=1/2", "<em>c</em> = 1/2")
    return escaped


def _css() -> str:
    return """
:root {
  --ink: #172B3A;
  --muted: #5B6C78;
  --paper: #FFFFFF;
  --wash: #F2F6F8;
  --line: #D7E0E6;
  --blue: #175A7A;
  --blue-soft: #E5F1F6;
  --green: #277C5A;
  --green-soft: #E5F3ED;
  --orange: #B95C23;
  --orange-soft: #FAEEE5;
  --mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  --serif: Iowan Old Style, Palatino Linotype, Book Antiqua, Georgia, serif;
  --sans: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; background: var(--wash); }
body { margin: 0; color: var(--ink); background: var(--wash); font: 16px/1.72 var(--sans); }
.hero { color: white; background:
  radial-gradient(circle at 84% 15%, rgba(96,190,190,.25), transparent 28rem),
  linear-gradient(135deg, #102E40 0%, #164D66 58%, #1E6A72 100%); }
.hero-inner { max-width: 1120px; margin: 0 auto; padding: 82px 42px 62px; }
.eyebrow { color: #BDE5E0; text-transform: uppercase; letter-spacing: .15em; font-size: .76rem; font-weight: 750; }
h1 { max-width: 850px; margin: 14px 0 8px; font: 700 clamp(2.8rem, 7vw, 5.7rem)/.98 var(--serif); letter-spacing: -.04em; }
.subtitle { max-width: 800px; margin: 20px 0 12px; color: #DDECF1; font: 1.25rem/1.48 var(--serif); }
.author { color: #AFC8D1; font-size: .92rem; }
.hero-rule { width: 76px; height: 3px; margin: 35px 0 27px; background: #74D1C3; }
.hero h2 { margin: 0 0 7px; font-size: .78rem; text-transform: uppercase; letter-spacing: .14em; color: #BDE5E0; }
.abstract { max-width: 900px; margin: 0; color: #F0F6F8; font-family: var(--serif); font-size: 1.08rem; }
.result-strip { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); max-width: 760px; margin-top: 38px; border: 1px solid rgba(255,255,255,.2); }
.result-strip div { padding: 16px 20px; border-right: 1px solid rgba(255,255,255,.2); }
.result-strip div:last-child { border-right: 0; }
.result-strip strong { display: block; font: 700 1.55rem var(--serif); color: #FFF; }
.result-strip span { color: #BFD1D8; font-size: .76rem; text-transform: uppercase; letter-spacing: .08em; }
.shell { display: grid; grid-template-columns: 260px minmax(0, 820px); gap: 54px; max-width: 1180px; margin: 0 auto; padding: 50px 28px 90px; align-items: start; }
nav { position: sticky; top: 24px; padding: 19px 0; border-top: 3px solid var(--blue); border-bottom: 1px solid var(--line); }
.toc-title { margin: 0 12px 11px; font-size: .74rem; font-weight: 800; text-transform: uppercase; letter-spacing: .13em; color: var(--blue); }
nav a { display: grid; grid-template-columns: 27px 1fr; gap: 4px; padding: 7px 12px; color: var(--muted); text-decoration: none; font-size: .82rem; line-height: 1.3; border-left: 2px solid transparent; }
nav a span { color: #91A2AD; font-family: var(--mono); font-size: .72rem; }
nav a:hover, nav a:focus { color: var(--blue); background: var(--blue-soft); border-left-color: var(--blue); }
main { min-width: 0; }
.report-section { margin: 0 0 88px; scroll-margin-top: 22px; }
.section-kicker { margin-bottom: 7px; color: var(--orange); font: 750 .72rem var(--sans); letter-spacing: .14em; text-transform: uppercase; }
.report-section > h2 { margin: 0 0 30px; color: var(--ink); font: 700 2.4rem/1.08 var(--serif); letter-spacing: -.025em; }
.report-section > p { margin: 0 0 20px; hyphens: auto; }
.report-section > p:first-of-type::first-letter { float: left; margin: .05em .09em 0 0; color: var(--blue); font: 700 3.6rem/.78 var(--serif); }
.equation { position: relative; margin: 30px 0; padding: 25px 58px 20px 26px; background: #F8FBFC; border-left: 4px solid var(--blue); box-shadow: inset 0 0 0 1px var(--line); }
.equation-expression { overflow-wrap: anywhere; color: #123E56; font: 600 1.02rem/1.55 var(--mono); }
.equation-number { position: absolute; top: 25px; right: 20px; color: var(--muted); font-family: var(--serif); }
.equation p { margin: 14px 0 0; color: var(--muted); font-size: .92rem; }
.report-figure, .report-table { margin: 37px 0; }
.report-figure img { display: block; width: 100%; height: auto; border: 1px solid var(--line); background: white; }
figcaption { margin-top: 12px; color: #3E505C; font-size: .88rem; line-height: 1.55; }
.limit { display: block; margin-top: 5px; color: var(--muted); }
.table-scroll { margin-top: 12px; overflow-x: auto; border: 1px solid var(--line); background: white; }
table { width: 100%; border-collapse: collapse; font-size: .80rem; line-height: 1.45; }
th { padding: 10px 11px; color: white; background: #214A60; text-align: left; font-size: .72rem; text-transform: uppercase; letter-spacing: .035em; }
td { padding: 9px 11px; border-top: 1px solid var(--line); vertical-align: top; overflow-wrap: anywhere; }
tbody tr:nth-child(even) { background: #F4F7F9; }
.table-note { margin: 9px 0 0; color: var(--muted); font-size: .82rem; }
.callout { margin: 30px 0; padding: 20px 24px; border-left: 4px solid var(--blue); background: var(--blue-soft); }
.callout.result { border-left-color: var(--green); background: var(--green-soft); }
.callout.warning { border-left-color: var(--orange); background: var(--orange-soft); }
.callout-label { margin-bottom: 5px; color: var(--blue); font-size: .75rem; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; }
.callout.result .callout-label { color: var(--green); }
.callout.warning .callout-label { color: var(--orange); }
.callout p { margin: 0; }
.code-panel { margin: 30px 0; color: #DCEAF0; background: #122B39; border-radius: 3px; overflow: hidden; }
.code-panel h3 { margin: 0; padding: 14px 20px; color: #94DDD0; background: #0C202C; font-size: .82rem; text-transform: uppercase; letter-spacing: .08em; }
pre { margin: 0; padding: 20px; overflow-x: auto; white-space: pre; font: .82rem/1.62 var(--mono); }
.code-panel p { margin: 0; padding: 0 20px 20px; color: #B8CCD5; font-size: .86rem; }
code { font-family: var(--mono); font-size: .92em; }
footer { display: flex; justify-content: space-between; gap: 20px; padding: 26px max(28px, calc((100vw - 1120px)/2)); color: #AFC3CD; background: #102E40; font-size: .78rem; }
.page-break { height: 0; }
@media (max-width: 900px) {
  .shell { display: block; padding-top: 24px; }
  nav { position: static; margin-bottom: 48px; columns: 2; }
  .toc-title { column-span: all; }
  nav a { break-inside: avoid; }
  .hero-inner { padding: 58px 28px 46px; }
}
@media (max-width: 620px) {
  body { font-size: 15px; }
  .result-strip { grid-template-columns: 1fr; }
  .result-strip div { border-right: 0; border-bottom: 1px solid rgba(255,255,255,.2); }
  nav { columns: 1; }
  .report-section > h2 { font-size: 2rem; }
  .shell { padding-inline: 18px; }
  footer { display: block; }
}
@media print {
  body { background: white; font-size: 10pt; }
  .hero { color: var(--ink); background: white; }
  .hero-inner { padding: 20mm 18mm 10mm; }
  .hero h1, .hero .abstract { color: var(--ink); }
  .hero .subtitle, .hero .author { color: var(--muted); }
  nav { display: none; }
  .shell { display: block; max-width: none; padding: 0 18mm; }
  .report-section { margin-bottom: 12mm; }
  .page-break { break-before: page; }
  .report-figure, .report-table, .callout, .equation, .code-panel { break-inside: avoid; }
  footer { display: none; }
}
"""
