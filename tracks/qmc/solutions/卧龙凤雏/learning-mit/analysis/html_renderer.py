"""Self-contained offline HTML rendering for the shared report model."""

from __future__ import annotations

import base64
import hashlib
import html
import json
from pathlib import Path

from .locale import get_locale
from .report_model import Callout, Equation, Figure, Paragraph, ReportDocument, Table


def render_html(document: ReportDocument, destination: Path) -> Path:
    locale = get_locale(document.language)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    facts_json = json.dumps(
        document.numeric_facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    facts_hash = hashlib.sha256(facts_json.encode("utf-8")).hexdigest()
    toc = "".join(
        f'<a href="#{html.escape(section.slug)}"><span>{index:02d}</span>'
        f"{html.escape(section.title)}</a>"
        for index, section in enumerate(document.sections, 1)
    )
    figure_number = 0
    table_number = 0
    sections = []
    for index, section in enumerate(document.sections, 1):
        blocks = []
        for block in section.blocks:
            if isinstance(block, Paragraph):
                blocks.append(f"<p>{_text(block.text)}</p>")
            elif isinstance(block, Equation):
                blocks.append(
                    f'<div class="equation"><code>{html.escape(_safe(block.expression))}</code>'
                    f"<p>{_text(block.explanation)}</p></div>"
                )
            elif isinstance(block, Figure):
                figure_number += 1
                blocks.append(_figure(block, figure_number, destination.parent, locale.labels))
            elif isinstance(block, Table):
                table_number += 1
                blocks.append(_table(block, table_number, locale.labels))
            elif isinstance(block, Callout):
                blocks.append(
                    f'<aside class="callout {html.escape(block.tone)}">'
                    f"<strong>{html.escape(_safe(block.title))}</strong>"
                    f"<p>{_text(block.text)}</p></aside>"
                )
        section_label = (
            f"第 {index:02d} 节"
            if document.language == "zh"
            else f"{locale.labels['section']} {index:02d}"
        )
        sections.append(
            f'<section id="{html.escape(section.slug)}"><div class="kicker">'
            f"{html.escape(section_label)}</div><h2>{html.escape(_safe(section.title))}</h2>"
            f"{''.join(blocks)}</section>"
        )
    page = f"""<!doctype html>
<html lang="{locale.html_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="learning-mit-status" content="{html.escape(document.status)}">
<meta name="numeric-facts-sha256" content="{facts_hash}">
<title>{html.escape(_safe(document.title))}</title>
<style>{_css()}</style>
</head>
<body>
<header class="hero"><div class="hero-inner">
<div class="eyebrow">Quantum Harness · Challenge 122</div>
<div class="status">{html.escape(document.exploratory_label)}</div>
<h1>{html.escape(_safe(document.title))}</h1>
<p class="subtitle">{html.escape(_safe(document.subtitle))}</p>
<p class="author">{html.escape(_safe(document.author))}</p>
<p class="abstract">{_text(document.abstract)}</p>
</div></header>
<div class="shell"><nav><div class="toc-title">{html.escape(locale.labels["contents"])}</div>
{toc}</nav><main>{''.join(sections)}</main></div>
<footer><span>{html.escape(_safe(document.author))}</span><span>{html.escape(document.status)}</span></footer>
<script id="numeric-facts" type="application/json">{html.escape(facts_json)}</script>
<script id="figure-data-hashes" type="application/json">{json.dumps(document.figure_data_hashes)}</script>
</body></html>
"""
    destination.write_text(page, encoding="utf-8")
    return destination


def _figure(block: Figure, number: int, root: Path, labels: dict[str, str]) -> str:
    source = root / block.source
    if not source.is_file():
        raise ValueError(f"missing report figure: {source}")
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    return (
        '<figure><img src="data:image/png;base64,'
        + encoded
        + f'" alt="{html.escape(_safe(block.caption))}"><figcaption><strong>'
        + f"{html.escape(labels['figure'])} {number}.</strong> {_text(block.caption)}"
        + f'<span class="limit"><strong>{html.escape(labels["interpretation"])}:</strong> '
        + f"{_text(block.inference_limit)}</span></figcaption></figure>"
    )


def _table(block: Table, number: int, labels: dict[str, str]) -> str:
    headings = "".join(f"<th>{html.escape(_safe(value))}</th>" for value in block.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_text(value)}</td>" for value in row) + "</tr>"
        for row in block.rows
    )
    return (
        f'<div class="report-table"><h3>{html.escape(labels["table"])} {number}. '
        f"{html.escape(_safe(block.title))}</h3><div class=\"table-scroll\"><table>"
        f"<thead><tr>{headings}</tr></thead><tbody>{rows}</tbody></table></div>"
        f'<p class="note">{_text(block.note)}</p></div>'
    )


def _text(value: object) -> str:
    return html.escape(_safe(str(value))).replace("\n", "<br>")


def _safe(value: str) -> str:
    return value.replace("—", "-").replace("–", "-").replace("‑", "-")


def _css() -> str:
    return """
:root{--ink:#172b3a;--muted:#5c6d78;--paper:#fff;--wash:#eef3f5;--line:#d6e0e5;
--blue:#175a7a;--green:#277c5a;--orange:#b95c23;--serif:"Songti SC","STSong",Georgia,serif;
--sans:"PingFang SC","Hiragino Sans GB",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth;background:var(--wash)}
body{margin:0;color:var(--ink);background:var(--wash);font:16px/1.72 var(--sans)}
.hero{color:white;background:linear-gradient(135deg,#102e40,#175a7a 65%,#277c5a)}
.hero-inner{max-width:1120px;margin:auto;padding:72px 42px 58px}.eyebrow{letter-spacing:.14em;
text-transform:uppercase;color:#bde5e0;font-size:.76rem}.status{display:inline-block;margin-top:28px;
padding:6px 10px;border:1px solid #f1c79e;color:#ffe0bd;font-weight:800;letter-spacing:.08em}
h1{max-width:900px;margin:18px 0 12px;font:700 clamp(2.6rem,7vw,5.4rem)/1 var(--serif)}
.subtitle{max-width:850px;color:#dcebf0;font:1.25rem/1.5 var(--serif)}.author{color:#bdd0d8}
.abstract{max-width:900px;margin-top:30px;padding-top:24px;border-top:1px solid #ffffff40;font-family:var(--serif)}
.shell{max-width:1240px;margin:0 auto;display:grid;grid-template-columns:260px minmax(0,1fr);gap:34px;padding:38px 28px}
nav{position:sticky;top:18px;align-self:start;background:white;border:1px solid var(--line);padding:20px}
.toc-title{font-weight:800;margin-bottom:10px}nav a{display:flex;gap:10px;padding:7px 0;color:var(--ink);
text-decoration:none;border-bottom:1px solid #edf1f3;font-size:.86rem}nav a span{color:var(--orange)}
main{min-width:0}section{background:white;border:1px solid var(--line);padding:34px 42px;margin-bottom:24px}
.kicker{color:var(--orange);font-weight:800;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase}
h2{margin:6px 0 20px;font:700 2rem/1.15 var(--serif)}h3{font-size:1rem}p{margin:0 0 14px}
.equation{margin:20px 0;padding:18px 22px;border-left:4px solid var(--blue);background:#eef6f8}
.equation code{font-size:1.03rem;white-space:normal}.equation p{margin:8px 0 0;color:var(--muted)}
.callout{padding:20px 22px;margin:18px 0;background:#e8f3ee;border-left:4px solid var(--green)}
.callout.warning{background:#faeee5;border-color:var(--orange)}figure{margin:28px 0}figure img{display:block;width:100%;
height:auto;border:1px solid var(--line)}figcaption{padding:10px 2px;color:#40525e;font-size:.88rem}
.limit{display:block;margin-top:5px;color:var(--muted)}.table-scroll{overflow-x:auto}table{width:100%;
border-collapse:collapse;font-size:.88rem}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line);
vertical-align:top}th{background:#edf4f6}.note{color:var(--muted);font-size:.82rem}
footer{display:flex;justify-content:space-between;max-width:1180px;margin:0 auto;padding:26px;color:var(--muted)}
@media(max-width:800px){.shell{display:block;padding:18px}.hero-inner{padding:48px 24px}nav{position:static;margin-bottom:20px}
section{padding:25px 20px}h1{font-size:2.7rem}}@media print{nav{display:none}.shell{display:block}section{break-before:page;border:0}}
"""
